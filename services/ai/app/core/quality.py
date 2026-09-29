"""The check that runs between generating an answer and showing it.

Two passes:

1. A regex scan (app.core.safety.scan_output) that costs nothing and catches
   the failures with the highest cost — invented experience, claimed actions,
   sales pressure.
2. An optional model review for the judgement calls a regex cannot make, such
   as whether a stated constraint was ignored.

A major issue triggers one repair attempt. If the repair also fails, the
answer is still sent — a slightly flawed answer beats an error page — but the
response is flagged for the moderation queue.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

from app.config import get_settings
from app.core import safety
from app.core.llm import ModelUnavailable, Usage, complete, complete_json
from app.core.prompts import QUALITY_PROMPT
from app.schemas import Classification, TripState

log = logging.getLogger(__name__)


@dataclass
class QualityResult:
    text: str
    passed: bool = True
    issues: list[dict[str, str]] = field(default_factory=list)
    repaired: bool = False
    flagged_for_review: bool = False
    usage: Usage = field(default_factory=Usage)


def _severity(issues: list[dict[str, Any]]) -> str:
    if any(i.get("severity") == "major" for i in issues):
        return "major"
    if issues:
        return "minor"
    return "none"


async def review(
    draft: str,
    question: str,
    classification: Classification,
    trip: TripState,
    *,
    live_data_used: bool = False,
    use_model: bool | None = None,
) -> QualityResult:
    settings = get_settings()
    use_model = settings.quality_check_enabled if use_model is None else use_model

    issues: list[dict[str, Any]] = list(safety.scan_output(draft))
    usage = Usage()

    if use_model:
        constraints = "; ".join(trip.constraints) if trip.constraints else "none stated"
        excluded = ", ".join(trip.excluded_destinations) if trip.excluded_destinations else "none"
        payload = (
            f"Traveller asked: {question}\n\n"
            f"Stated constraints: {constraints}\n"
            f"Ruled out already: {excluded}\n"
            f"Live data was used: {'yes' if live_data_used else 'no — the assistant has no live sources'}\n\n"
            f"Draft answer:\n{draft}"
        )
        try:
            verdict = await complete_json(QUALITY_PROMPT, payload, max_tokens=500)
            if isinstance(verdict, dict):
                for issue in verdict.get("issues", []) or []:
                    issues.append(
                        {
                            "severity": verdict.get("severity", "minor"),
                            "code": "model_review",
                            "detail": str(issue)[:300],
                        }
                    )
                if verdict.get("rewrite_guidance"):
                    issues.append(
                        {
                            "severity": verdict.get("severity", "minor"),
                            "code": "rewrite_guidance",
                            "detail": str(verdict["rewrite_guidance"])[:500],
                        }
                    )
        except (ModelUnavailable, ValueError, KeyError) as exc:
            log.warning("quality model review skipped: %s", exc)

    severity = _severity(issues)
    if severity != "major":
        return QualityResult(text=draft, passed=True, issues=issues, usage=usage)

    # --- one repair attempt -------------------------------------------------
    problems = "\n".join(f"- {i['detail']}" for i in issues if i.get("severity") == "major")
    repair_system = (
        "You are fixing a draft answer from a Morocco travel assistant. Rewrite it so the listed "
        "problems are gone. Keep everything that was useful, keep the same length and the same "
        "direct, practical voice, and keep the recommendation. Do not add disclaimers, do not "
        "apologise, do not mention that anything was corrected. Return only the rewritten answer."
    )
    try:
        fixed = await complete(
            repair_system,
            f"Problems to fix:\n{problems}\n\nDraft:\n{draft}",
            max_tokens=settings.max_answer_tokens,
            temperature=0.3,
        )
        usage.add(fixed.usage)
        remaining = safety.scan_output(fixed.text)
        still_major = any(i["severity"] == "major" for i in remaining)
        return QualityResult(
            text=fixed.text or draft,
            passed=not still_major,
            issues=issues + remaining,
            repaired=True,
            flagged_for_review=still_major,
            usage=usage,
        )
    except ModelUnavailable as exc:
        log.warning("quality repair failed: %s", exc)
        return QualityResult(
            text=draft, passed=False, issues=issues, flagged_for_review=True, usage=usage
        )
