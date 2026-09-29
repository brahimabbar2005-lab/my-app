"""Chooses which ComeMorocco pages to recommend, and how many.

Link selection is deliberately kept out of the language model. The specs are
explicit that links must be chosen because they help, not because they contain
a keyword, and a ranking system is more auditable than a model deciding in
prose. The model receives the retrieved pages as context and writes the answer;
this module decides what actually gets rendered as a resource card.

Rules implemented here (02_MVP_SCOPE §15–16, 04_ANSWER_STYLE_GUIDE §28–30):

  simple question    0–1 links
  recommendation     1–2 links
  complex itinerary  2–4 links

plus: never link a page marked "Do not proactively link"; never link a page
whose destination contradicts the question; never show two pages that are
near-duplicates of each other.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from app.knowledge.index import ScoredItem
from app.schemas import Classification, ResourceCard

# Maximum links by question complexity.
LINK_BUDGET = {"simple": 1, "moderate": 2, "complex": 4}

# Thresholds are calibrated against the live content map (see
# tests/test_retrieval.py, which asserts the separation still holds). On the
# current 240-page corpus: a strong match scores 1.3–2.1, a loose topical
# match ~1.0–1.1, and a question the site does not cover at all ~0.4.
MIN_LINK_SCORE = 1.15

# A second link has to clear a higher bar than the first: one good link beats
# two mediocre ones.
MARGINAL_LINK_SCORE = 1.45

# Below this, or with this little of the question actually covered, the
# question is an editorial gap even if something ranked.
GAP_SCORE = 1.15
GAP_COVERAGE = 0.2


@dataclass
class LinkDecision:
    resources: list[ResourceCard]
    considered: list[dict[str, Any]]
    suppressed: list[dict[str, Any]]


def _anchor_text(item: dict[str, Any], destinations: list[str]) -> str:
    """Pick the most natural anchor from the content map's own suggestions."""
    anchors = item.get("anchor_texts") or []
    if not anchors:
        return item["title"]
    if destinations:
        for anchor in anchors:
            if any(dest.lower() in anchor.lower() for dest in destinations):
                return anchor
    # Prefer the shortest specific anchor over the generic "our Morocco guide".
    scored = sorted(anchors, key=lambda a: (a.strip().lower() in {"our morocco guide", "this morocco guide"}, len(a)))
    return scored[0]


def _reason(scored: ScoredItem) -> str:
    if scored.reasons:
        return ", ".join(scored.reasons)
    return "topic match"


def _is_near_duplicate(a: dict[str, Any], b: dict[str, Any]) -> bool:
    """Two pages that would read as the same recommendation."""
    if a["id"] == b["id"]:
        return True
    if b["id"] in (a.get("related_ids") or []) and a.get("primary_topic") == b.get("primary_topic"):
        if a.get("primary_destination") == b.get("primary_destination"):
            return True
    a_title = re.sub(r"[^a-z0-9 ]", "", (a.get("title") or "").lower()).split()
    b_title = re.sub(r"[^a-z0-9 ]", "", (b.get("title") or "").lower()).split()
    if a_title and b_title:
        overlap = len(set(a_title) & set(b_title)) / max(len(set(a_title) | set(b_title)), 1)
        if overlap > 0.7:
            return True
    return False


def select_links(
    candidates: list[ScoredItem],
    classification: Classification,
    *,
    already_linked: set[str] | None = None,
) -> LinkDecision:
    """Rank retrieved pages down to the handful worth showing."""
    already_linked = already_linked or set()
    budget = LINK_BUDGET.get(classification.complexity, 1)

    # Off-topic, greetings and impossible actions get no links at all: there is
    # nothing useful to point at, and a link there reads as deflection.
    if {"OFF_TOPIC", "GREETING"} & set(classification.intents):
        return LinkDecision(resources=[], considered=[], suppressed=[])

    chosen: list[ResourceCard] = []
    chosen_items: list[dict[str, Any]] = []
    considered: list[dict[str, Any]] = []
    suppressed: list[dict[str, Any]] = []

    for scored in candidates:
        item = scored.item
        considered.append({"id": item["id"], "title": item["title"], "score": scored.score})

        if len(chosen) >= budget:
            break

        threshold = MIN_LINK_SCORE if not chosen else MARGINAL_LINK_SCORE
        if scored.score < threshold:
            suppressed.append({"id": item["id"], "why": f"score {scored.score} below {threshold}"})
            continue

        if scored.topical == 0:
            suppressed.append({"id": item["id"], "why": "matches only on the destination, not the subject"})
            continue

        # The same rule for country-wide questions, which need more evidence:
        # about half the site is "about Morocco", so being about Morocco is
        # not selective. A wheelchair-access question otherwise linked the
        # AFCON guide, which shares only the word "cities".
        if ("country-wide match" in scored.reasons and "topic in title" not in scored.reasons
                and scored.topical < 0.5):
            suppressed.append({"id": item["id"], "why": "country-wide page without a clear subject match"})
            continue

        if (item.get("link_behavior") or "").lower() == "do not proactively link":
            suppressed.append({"id": item["id"], "why": "content map says do not proactively link"})
            continue

        if "destination mismatch" in scored.reasons:
            suppressed.append({"id": item["id"], "why": "destination does not match the question"})
            continue

        if item["id"] in already_linked:
            suppressed.append({"id": item["id"], "why": "already linked earlier in this conversation"})
            continue

        if any(_is_near_duplicate(item, other) for other in chosen_items):
            suppressed.append({"id": item["id"], "why": "near-duplicate of a chosen link"})
            continue

        chosen.append(
            ResourceCard(
                content_id=item["id"],
                title=item["title"],
                url=item["url"],
                anchor_text=_anchor_text(item, classification.destinations),
                reason=_reason(scored),
                score=scored.score,
            )
        )
        chosen_items.append(item)

    return LinkDecision(resources=chosen, considered=considered, suppressed=suppressed)


def detect_content_gap(
    question: str,
    candidates: list[ScoredItem],
    classification: Classification,
) -> dict[str, Any] | None:
    """Flag questions ComeMorocco has no good page for.

    This is the content-gap engine from the blueprint: every question the AI
    answers well from general knowledge but cannot support with a page is an
    editorial opportunity. Logged, never shown to the traveller.
    """
    if {"OFF_TOPIC", "GREETING", "IMPOSSIBLE_ACTION"} & set(classification.intents):
        return None

    # Agree with the link engine: a page it would refuse to link because it
    # only shares the city name does not count as coverage either. Otherwise
    # "restaurants in Tetouan" would show no link *and* not be recorded as a
    # gap — the worst of both.
    topical = [
        c for c in candidates
        if c.topical > 0
        and "destination mismatch" not in c.reasons
        and not ("country-wide match" in c.reasons and "topic in title" not in c.reasons and c.topical < 0.5)
    ]
    best = topical[0] if topical else None
    score = best.score if best else 0.0
    coverage = best.coverage if best else 0.0

    # Two ways to be a gap: nothing ranked well, or something ranked but only
    # echoes a fraction of what was asked — the "$100 in Morocco" page turning
    # up for a question about private driver day rates.
    if score >= GAP_SCORE and coverage >= GAP_COVERAGE:
        return None

    return {
        "question": question[:400],
        "intents": classification.intents,
        "destinations": classification.destinations,
        "best_score": round(score, 4),
        "best_coverage": round(coverage, 3),
        "best_match": best.item["title"] if best else None,
    }
