"""The response pipeline.

    language  →  intent  →  trip state  →  safety  →  retrieval  →  link ranking
              →  affiliate gating  →  generation  →  quality check  →  response

Two decisions shape this file:

**Links and affiliates are chosen before generation, not after.** The model is
told what will appear beneath its answer so it can lead into it naturally,
but it does not get to decide what appears. That is what keeps "relevance
before revenue" a property of the system rather than a hope about the prompt.

**Classification and extraction run concurrently.** They are independent, both
hit the small model, and doing them in sequence would put ~600ms on every
response for no reason.
"""
from __future__ import annotations

import asyncio
import logging
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, AsyncIterator

from app.config import get_settings
from app.core import safety
from app.core.intent import classify_rules, classify_with_model
from app.core.llm import ModelUnavailable, Usage, complete, stream
from app.core.prompts import build_system_prompt
from app.core.quality import review
from app.core.trip_state import extract_rules, extract_with_model
from app.knowledge.affiliates import select_affiliates
from app.knowledge.links import detect_content_gap, select_links
from app.knowledge.retriever import get_retriever
from app.core.actions import propose_actions
from app.schemas import (
    AffiliateCard,
    AIActionOut,
    Classification,
    ResourceCard,
    TripState,
)

log = logging.getLogger(__name__)


@dataclass
class AnswerResult:
    answer: str
    classification: Classification
    trip: TripState
    resources: list[ResourceCard] = field(default_factory=list)
    affiliates: list[AffiliateCard] = field(default_factory=list)
    notices: list[str] = field(default_factory=list)
    usage: Usage = field(default_factory=Usage)
    latency_ms: int = 0
    flagged_for_review: bool = False
    quality_issues: list[dict[str, str]] = field(default_factory=list)
    content_gap: dict[str, Any] | None = None
    actions: list[AIActionOut] = field(default_factory=list)
    debug: dict[str, Any] = field(default_factory=dict)
    message_id: str = field(default_factory=lambda: uuid.uuid4().hex)


NOTICE_NO_LIVE_DATA = (
    "This is general guidance, not a live check — schedules, prices and availability change."
)
NOTICE_OFFICIAL_SOURCE = (
    "For visas and entry rules, always confirm with the Moroccan consulate for your nationality."
)


def retrieval_query_with_trip(message: str, trip: TripState) -> str:
    """The question plus durable trip context the question does not already
    contain.

    Appending context the message already names ("Marrakech or Fes…?" +
    "Marrakech Fes") doubled the city terms, and generic city pages then
    outranked the page that answers the question (the first-timers guide lost
    to "Flights to Marrakech"). Only genuinely new context is added.
    """
    lowered = message.lower()
    extra = [d for d in trip.destinations if d.lower() not in lowered]
    extra += [i for i in trip.interests if i.lower() not in lowered]
    return " ".join([message, *extra]) if extra else message


class Orchestrator:
    def __init__(self) -> None:
        self.retriever = get_retriever()

    # ----------------------------------------------------------------- setup
    async def _understand(
        self,
        message: str,
        history: list[dict[str, str]],
        trip: TripState,
        locale: str | None,
        *,
        use_model: bool,
    ) -> tuple[Classification, TripState]:
        base = classify_rules(message, locale)
        if not use_model:
            return base, extract_rules(message, trip)

        classification_task = classify_with_model(message, history, trip, base)
        trip_task = extract_with_model(message, trip)
        classification, new_trip = await asyncio.gather(
            classification_task, trip_task, return_exceptions=True
        )
        if isinstance(classification, BaseException):
            log.warning("classification failed: %s", classification)
            classification = base
        if isinstance(new_trip, BaseException):
            log.warning("trip extraction failed: %s", new_trip)
            new_trip = extract_rules(message, trip)
        return classification, new_trip

    def _prepare(
        self,
        message: str,
        classification: Classification,
        trip: TripState,
        page_url: str | None,
        already_linked: set[str],
    ) -> tuple[list[dict[str, Any]], list[ResourceCard], list[AffiliateCard], dict[str, Any]]:
        settings = get_settings()

        # Retrieval query: the question plus durable trip context, so a
        # follow-up like "would you add Fes?" still retrieves usefully.
        query = retrieval_query_with_trip(message, trip)

        candidates = self.retriever.retrieve(query, classification, page_url=page_url)
        context_items = self.retriever.context_items(candidates)

        link_decision = select_links(candidates, classification, already_linked=already_linked)

        affiliate_decision = select_affiliates(
            message,
            classification,
            trip,
            self.retriever.kb.programs,
            self.retriever.kb.activities,
            enabled=settings.affiliates_enabled,
        )

        gap = detect_content_gap(message, candidates, classification)

        debug = {
            "retrieved": [
                {"id": c.item["id"], "title": c.item["title"], "score": c.score,
                 "lexical": c.lexical, "boost": c.boost, "reasons": c.reasons}
                for c in candidates[:8]
            ],
            "links_suppressed": link_decision.suppressed,
            "affiliate_blocked": affiliate_decision.reason_blocked,
            "affiliate_categories": affiliate_decision.considered,
        }
        return context_items, link_decision.resources, affiliate_decision.cards, {"debug": debug, "gap": gap}

    def _notices(self, classification: Classification, live_enabled: bool) -> list[str]:
        notices: list[str] = []
        if classification.needs_live_data and not live_enabled:
            notices.append(NOTICE_NO_LIVE_DATA)
        if "VISA" in classification.intents:
            notices.append(NOTICE_OFFICIAL_SOURCE)
        return notices

    # -------------------------------------------------------------- answering
    async def answer(
        self,
        message: str,
        *,
        history: list[dict[str, str]] | None = None,
        trip: TripState | None = None,
        page_url: str | None = None,
        locale: str | None = None,
        already_linked: set[str] | None = None,
        use_model_classification: bool | None = None,
    ) -> AnswerResult:
        started = time.perf_counter()
        settings = get_settings()
        history = history or []
        trip = trip or TripState()
        already_linked = already_linked or set()
        usage = Usage()

        if len(message) > settings.max_message_chars:
            message = message[: settings.max_message_chars]

        if use_model_classification is None:
            use_model_classification = settings.model_classification_enabled
        classification, trip = await self._understand(
            message, history, trip, locale, use_model=use_model_classification
        )

        verdict = safety.check_input(message, classification)
        if not verdict.allow:
            return AnswerResult(
                answer=verdict.refusal or safety.fallback("model_unavailable", classification.language),
                classification=classification,
                trip=trip,
                latency_ms=int((time.perf_counter() - started) * 1000),
                debug={"refused": verdict.category},
            )

        context_items, resources, affiliates, extra = self._prepare(
            message, classification, trip, page_url, already_linked
        )

        system = build_system_prompt(
            classification,
            trip,
            context_items,
            resources,
            affiliates,
            live_data_enabled=settings.live_data_enabled,
            site_url=settings.site_url,
            contact_url=settings.contact_url,
        )
        if verdict.guidance:
            system += f"\n\nHANDLE WITH CARE: {verdict.guidance}"

        try:
            draft = await complete(system, message, history=history)
            usage.add(draft.usage)
        except ModelUnavailable as exc:
            log.error("answer generation failed: %s", exc)
            # Retrieval and link selection do not depend on the model, so the
            # fallback still carries the pages that matched. This is what makes
            # "you can browse our Morocco guides" a real offer rather than a
            # dead end (Project outline §50).
            return AnswerResult(
                answer=safety.fallback("model_unavailable", classification.language),
                classification=classification,
                trip=trip,
                resources=resources,
                actions=propose_actions(classification, resources, []),
                notices=self._notices(classification, settings.live_data_enabled),
                latency_ms=int((time.perf_counter() - started) * 1000),
                flagged_for_review=True,
                content_gap=extra["gap"],
                debug={"error": str(exc), **extra["debug"]},
            )

        checked = await review(
            draft.text,
            message,
            classification,
            trip,
            live_data_used=settings.live_data_enabled,
        )
        usage.add(checked.usage)

        return AnswerResult(
            answer=checked.text,
            classification=classification,
            trip=trip,
            resources=resources,
            affiliates=affiliates,
            actions=propose_actions(classification, resources, affiliates),
            notices=self._notices(classification, settings.live_data_enabled),
            usage=usage,
            latency_ms=int((time.perf_counter() - started) * 1000),
            flagged_for_review=checked.flagged_for_review,
            quality_issues=checked.issues,
            content_gap=extra["gap"],
            debug=extra["debug"],
        )

    # -------------------------------------------------------------- streaming
    async def answer_stream(
        self,
        message: str,
        *,
        history: list[dict[str, str]] | None = None,
        trip: TripState | None = None,
        page_url: str | None = None,
        locale: str | None = None,
        already_linked: set[str] | None = None,
    ) -> AsyncIterator[tuple[str, Any]]:
        """Stream the answer.

        Yields ("meta", dict) first so the UI can render resource cards as soon
        as they are known, then ("delta", str) chunks, then ("done", AnswerResult).

        The quality check cannot run before the text has been shown, so in
        streaming mode it runs after and only records issues. Anything it would
        have repaired is flagged for the moderation queue instead. That is the
        trade-off for a responsive first token; the non-streaming path is used
        by the eval harness precisely because it does repair.
        """
        started = time.perf_counter()
        settings = get_settings()
        history = history or []
        trip = trip or TripState()
        already_linked = already_linked or set()
        usage = Usage()

        if len(message) > settings.max_message_chars:
            message = message[: settings.max_message_chars]

        classification, trip = await self._understand(
            message, history, trip, locale, use_model=settings.model_classification_enabled
        )

        verdict = safety.check_input(message, classification)
        if not verdict.allow:
            refusal = verdict.refusal or safety.fallback("model_unavailable", classification.language)
            yield "meta", {"resources": [], "affiliates": [], "notices": [],
                           "intents": classification.intents, "language": classification.language}
            yield "delta", refusal
            yield "done", AnswerResult(
                answer=refusal, classification=classification, trip=trip,
                latency_ms=int((time.perf_counter() - started) * 1000),
                debug={"refused": verdict.category},
            )
            return

        context_items, resources, affiliates, extra = self._prepare(
            message, classification, trip, page_url, already_linked
        )
        notices = self._notices(classification, settings.live_data_enabled)

        actions = propose_actions(classification, resources, affiliates)
        yield "meta", {
            "actions": [a.model_dump() for a in actions],
            "resources": [r.model_dump() for r in resources],
            "affiliates": [a.model_dump() for a in affiliates],
            "notices": notices,
            "intents": classification.intents,
            "language": classification.language,
            "trip_state": trip.to_dict(),
        }

        system = build_system_prompt(
            classification, trip, context_items, resources, affiliates,
            live_data_enabled=settings.live_data_enabled,
            site_url=settings.site_url, contact_url=settings.contact_url,
        )
        if verdict.guidance:
            system += f"\n\nHANDLE WITH CARE: {verdict.guidance}"

        chunks: list[str] = []
        try:
            async for kind, payload in stream(system, message, history=history):
                if kind == "delta":
                    chunks.append(payload)
                    yield "delta", payload
                elif kind == "usage":
                    usage.add(payload)
        except ModelUnavailable as exc:
            log.error("streaming failed: %s", exc)
            message_text = safety.fallback("model_unavailable", classification.language)
            yield "delta", message_text if not chunks else "\n\n" + message_text
            yield "done", AnswerResult(
                answer="".join(chunks) or message_text, classification=classification,
                trip=trip, resources=resources, affiliates=affiliates, notices=notices, actions=actions,
                usage=usage, latency_ms=int((time.perf_counter() - started) * 1000),
                flagged_for_review=True, debug={"error": str(exc)},
            )
            return

        text = "".join(chunks)
        issues = safety.scan_output(text)
        flagged = any(i["severity"] == "major" for i in issues)

        yield "done", AnswerResult(
            answer=text,
            classification=classification,
            trip=trip,
            resources=resources,
            affiliates=affiliates,
            notices=notices,
            actions=actions,
            usage=usage,
            latency_ms=int((time.perf_counter() - started) * 1000),
            flagged_for_review=flagged,
            quality_issues=issues,
            content_gap=extra["gap"],
            debug=extra["debug"],
        )


_orchestrator: Orchestrator | None = None


def get_orchestrator() -> Orchestrator:
    global _orchestrator
    if _orchestrator is None:
        _orchestrator = Orchestrator()
    return _orchestrator
