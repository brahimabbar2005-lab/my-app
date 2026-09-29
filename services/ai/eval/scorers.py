"""Scoring for the golden-question evaluation.

The dataset's most useful column is "Must NOT Do", because it states a
concrete failure mode per question rather than an abstract quality target.
Scoring is therefore built around failures avoided, not similarity to a
reference answer — there is no single correct answer to "how many days do I
really need", and the dataset is explicit that inventing a consensus is itself
a failure.

Four scorers:

  mechanical   regex checks, free, runs on every answer
  structural   length, links, hedging — matched against the row's expectations
  rubric       a model judging against the row's own columns
  retrieval    did the expected ComeMorocco content surface

Mechanical and structural are deterministic, so a regression is attributable.
The rubric costs a model call per question and is what catches "technically
fine but does not sound like a person".
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Any

from app.core import safety

# ---------------------------------------------------------------------------
GENERIC_OPENINGS = re.compile(
    r"^\s*(absolutely|great question|certainly|of course|sure[!,]|i'?d be happy to|"
    r"thanks for (asking|reaching)|what a|morocco is (a|one of)|"
    r"that'?s a (great|good|common) question)",
    re.IGNORECASE,
)

HEDGE_ONLY = re.compile(
    r"\b(depends on (your|several|many|a number of)|both (options |)have (their |)"
    r"(advantages|pros and cons)|there are many factors|it varies|"
    r"ultimately (it|the choice) (depends|is up to you))\b",
    re.IGNORECASE,
)

RECOMMENDATION = re.compile(
    r"\b(i'?d |i would |my (pick|suggestion)|go with|i'?d (go|pick|choose|skip|avoid|keep|start|stick)|"
    r"personally|if it were (my|me)|i'?d lean|worth it|not worth|don'?t bother|skip it)\b",
    re.IGNORECASE,
)

UNCERTAINTY = re.compile(
    r"\b(can change|check (the |)(current|latest|official)|i can'?t confirm|i don'?t have|"
    r"varies|i'?m not sure|no reliable|before you (rely|book|travel)|verify|"
    r"worth checking|depends on your nationality)\b",
    re.IGNORECASE,
)

ANECDOTE_FRAMING = re.compile(
    r"\b(some (travellers|travelers|people)|one traveller|travellers (often |commonly |)"
    r"(report|mention|say)|reported|anecdotally|in the (community|groups)|"
    r"people often say|you'?ll hear)\b",
    re.IGNORECASE,
)

FALSE_PRECISION = re.compile(r"\b\d{3,5}(\.\d+)?\s*(mad|dirham|dh)\b(?!\s*(to|-|–|and))", re.IGNORECASE)


@dataclass
class Score:
    name: str
    value: float          # 0..1
    passed: bool
    detail: str = ""


@dataclass
class QuestionResult:
    question_id: str
    question: str
    answer: str
    scores: list[Score] = field(default_factory=list)
    failures: list[str] = field(default_factory=list)
    resources: list[str] = field(default_factory=list)
    affiliates: list[str] = field(default_factory=list)
    latency_ms: int = 0
    tokens: int = 0
    # Not a failure: the question is answerable, but ComeMorocco has no page
    # for it. Feeds the editorial brief list rather than the pass rate.
    content_gap: bool = False

    @property
    def overall(self) -> float:
        if not self.scores:
            return 0.0
        return round(sum(s.value for s in self.scores) / len(self.scores), 3)

    @property
    def passed(self) -> bool:
        return all(s.passed for s in self.scores)


# ---------------------------------------------------------------------------
def mechanical(answer: str) -> list[Score]:
    """Free checks. A major issue here is an automatic failure."""
    issues = safety.scan_output(answer)
    major = [i for i in issues if i["severity"] == "major"]
    minor = [i for i in issues if i["severity"] == "minor"]

    scores = [
        Score(
            "honesty",
            0.0 if major else 1.0,
            not major,
            "; ".join(i["detail"] for i in major) or "no fabricated experience or claimed actions",
        ),
        Score(
            "voice",
            max(0.0, 1.0 - 0.34 * len(minor)),
            len(minor) <= 1,
            "; ".join(i["detail"] for i in minor) or "clean",
        ),
    ]

    if GENERIC_OPENINGS.search(answer):
        scores.append(Score("opening", 0.0, False, "opens with filler instead of the answer"))
    else:
        scores.append(Score("opening", 1.0, True, "leads with the answer"))

    return scores


def structural(answer: str, row: dict[str, Any], resources: list[str], affiliates: list[str]) -> list[Score]:
    """Checks driven by the dataset row's own expectations."""
    scores: list[Score] = []
    words = len(answer.split())

    # Length. The style guide's targets, with generous ceilings — the failure
    # mode we care about is the wall of text, not a sentence too many.
    difficulty = (row.get("difficulty") or "Medium").lower()
    ceiling = {"easy": 180, "medium": 320, "hard": 650}.get(difficulty, 320)
    scores.append(
        Score("length", 1.0 if words <= ceiling else max(0.0, 1 - (words - ceiling) / ceiling),
              words <= ceiling, f"{words} words (ceiling {ceiling})")
    )

    # Recommendation. The dataset says when the source gave one — and when it
    # deliberately did not, so inventing one is the failure.
    expects_recommendation = bool(row.get("recommendation"))
    has_recommendation = bool(RECOMMENDATION.search(answer))
    if expects_recommendation:
        scores.append(Score("recommendation", 1.0 if has_recommendation else 0.0,
                            has_recommendation, "gives a clear recommendation"))
    else:
        scores.append(Score("recommendation", 1.0, True, "no recommendation expected"))

    # Decisiveness: pure hedging with no view is a style-guide failure.
    hedging = bool(HEDGE_ONLY.search(answer)) and not has_recommendation
    scores.append(Score("decisiveness", 0.0 if hedging else 1.0, not hedging,
                        "hedges without committing" if hedging else "commits to a view"))

    # Live data. If the row says the answer depends on current information, the
    # answer must say it cannot confirm it.
    if (row.get("live_data_required") or "No").lower() == "yes":
        flagged = bool(UNCERTAINTY.search(answer))
        scores.append(Score("live_data_honesty", 1.0 if flagged else 0.0, flagged,
                            "flags that this needs checking" if flagged
                            else "presents changeable information without qualification"))

    # Anecdote framing: where the source was one traveller's experience, the
    # answer must not restate it as general fact.
    if (row.get("evidence_type") or "").lower() in {"anecdote", "traveler experience", "mixed"}:
        framed = bool(ANECDOTE_FRAMING.search(answer)) or not FALSE_PRECISION.search(answer)
        scores.append(Score("anecdote_framing", 1.0 if framed else 0.0, framed,
                            "keeps traveller reports framed as reports"))

    # Affiliate discipline.
    affiliate_expected = (row.get("affiliate_relevant") or "No").lower() == "yes"
    if not affiliate_expected and affiliates:
        scores.append(Score("affiliate_discipline", 0.0, False,
                            f"showed {len(affiliates)} affiliate(s) on a non-commercial question"))
    else:
        scores.append(Score("affiliate_discipline", 1.0, True, "affiliate behaviour appropriate"))

    # Link discipline: never more than the complex-question ceiling.
    scores.append(Score("link_discipline", 1.0 if len(resources) <= 4 else 0.0,
                        len(resources) <= 4, f"{len(resources)} link(s)"))

    # Safety-sensitive rows must not read as a guarantee.
    if (row.get("safety_sensitive") or "No").lower() == "yes":
        absolute = re.search(r"\b(completely safe|totally safe|no risk|absolutely safe|"
                             r"you will be fine|guaranteed|never happens)\b", answer, re.IGNORECASE)
        scores.append(Score("safety_tone", 0.0 if absolute else 1.0, not absolute,
                            "absolute safety claim" if absolute else "proportionate"))

    return scores


RUBRIC_PROMPT = """You are grading a Morocco travel assistant's answer against a reference row from \
an evaluation dataset built from real traveller questions and real community responses.

You are given: the question, what the community actually advised, what the answer MUST NOT do, and \
what a natural answer requires.

Return JSON only:
{"answered_question": 0-1, "usefulness": 0-1, "naturalness": 0-1, "must_not_do_respected": true/false,
 "violations": ["..."], "notes": "one sentence"}

Guidance:
- answered_question: did it address what was actually asked, including every sub-question?
- usefulness: would this help the traveller decide something? Reward specifics that change what
  they do — travel times, pacing, what to skip, what to check. Penalise generic description.
- naturalness: does this read like a knowledgeable person in a travel forum, or like an AI being
  thorough? Penalise brochure language, filler openings and padding.
- must_not_do_respected: false if the answer does any of the listed "must not do" items. This is
  the most important field. Be strict.
- The answer does NOT have to match the community response. The community is often wrong,
  contradictory or unhelpful. A better answer scores higher. But it must not invent a consensus
  the source does not support."""


def build_rubric_payload(row: dict[str, Any], answer: str) -> str:
    return (
        f"QUESTION:\n{row['question']}\n\n"
        f"WHAT THE COMMUNITY ADVISED:\n{row.get('extracted_advice') or 'Nothing captured in the source.'}\n\n"
        f"KEY FACTS FROM THE SOURCE:\n{row.get('key_facts') or 'None.'}\n\n"
        f"MUST NOT DO:\n{row.get('must_not_do') or 'Nothing specific.'}\n\n"
        f"NATURAL ANSWER REQUIREMENT:\n{row.get('natural_answer_requirement') or 'Be useful and direct.'}\n\n"
        f"ASSISTANT'S ANSWER:\n{answer}"
    )


def rubric_scores(verdict: dict[str, Any]) -> list[Score]:
    def clamp(value: Any) -> float:
        try:
            return max(0.0, min(1.0, float(value)))
        except (TypeError, ValueError):
            return 0.0

    respected = bool(verdict.get("must_not_do_respected", True))
    violations = "; ".join(str(v) for v in verdict.get("violations", []) or [])

    return [
        Score("answered_question", clamp(verdict.get("answered_question")),
              clamp(verdict.get("answered_question")) >= 0.6, verdict.get("notes", "")),
        Score("usefulness", clamp(verdict.get("usefulness")),
              clamp(verdict.get("usefulness")) >= 0.6, ""),
        Score("naturalness", clamp(verdict.get("naturalness")),
              clamp(verdict.get("naturalness")) >= 0.6, ""),
        Score("must_not_do", 1.0 if respected else 0.0, respected,
              violations or "respected the row's constraints"),
    ]


def retrieval_score(row: dict[str, Any], resources: list[str]) -> Score:
    """Did the page the dataset expects actually surface?"""
    expected = row.get("content_opportunity")
    if not expected:
        return Score("retrieval", 1.0, True, "no expected content for this row")
    if not resources:
        return Score("retrieval", 0.0, False, f"expected something like: {expected}")

    expected_words = {w for w in re.findall(r"[a-z]+", expected.lower()) if len(w) > 3}
    joined = " ".join(resources).lower()
    hits = sum(1 for w in expected_words if w in joined)
    ratio = hits / max(len(expected_words), 1)
    return Score("retrieval", round(ratio, 3), ratio >= 0.3,
                 f"linked: {'; '.join(resources)[:120]}")
