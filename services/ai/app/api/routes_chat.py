"""Chat endpoints.

Two shapes of the same pipeline:

  POST /api/chat          JSON in, JSON out. Used by the eval harness and by
                          any client that cannot handle SSE.
  POST /api/chat/stream   Server-sent events. What the widget uses, so the
                          traveller sees text appear rather than a spinner.

Both go through the same orchestrator, so behaviour cannot diverge between
what is tested and what is shipped.
"""
from __future__ import annotations

import json
import logging

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse, StreamingResponse
from sqlalchemy.orm import Session as OrmSession

from app.api.deps import client_ip, get_db, require_widget_key
from app.config import get_settings
from app.core import safety
from app.core.actions import merge_trip_context
from app.core.orchestrator import get_orchestrator
from app.db import repo
from app.infra.auth import caller_from_authorization
from app.infra.ratelimit import check_rate, validate_message
from app.schemas import ChatRequest, ChatResponse

log = logging.getLogger(__name__)
router = APIRouter(prefix="/api", tags=["chat"], dependencies=[Depends(require_widget_key)])





def _too_many(reason: str, retry_after: int, locale: str | None = None) -> JSONResponse:
    return JSONResponse(
        status_code=429,
        headers={"Retry-After": str(retry_after)},
        content={"error": reason, "answer": safety.fallback("rate_limited", locale)},
    )


def _prepare(db: OrmSession, request: Request, payload: ChatRequest):
    """Shared setup: session, conversation, limits, validation."""
    ip = client_ip(request)
    session = repo.get_or_create_session(
        db,
        payload.session_id,
        ip=ip,
        user_agent=request.headers.get("user-agent"),
        locale=payload.locale,
    )
    conversation, is_new = repo.get_or_create_conversation(
        db, session, payload.conversation_id, entry_page=payload.page_url
    )

    caller = caller_from_authorization(request.headers.get("authorization"))
    verdict = check_rate(session.id, repo.hash_ip(ip), user_id=caller.user_id)
    if not verdict.allowed:
        repo.record_event(db, "error_occurred", session_id=session.id,
                          conversation_id=conversation.id, properties={"reason": verdict.reason})
        return session, conversation, _too_many(verdict.reason or "rate_limited", verdict.retry_after_seconds, payload.locale)

    if repo.over_token_budget(db):
        log.error("daily token budget exhausted")
        return session, conversation, _too_many("budget_exhausted", 3600, payload.locale)

    check = validate_message(payload.message)
    if not check.ok:
        return session, conversation, JSONResponse(
            status_code=400,
            content={"error": check.reason, "answer": safety.fallback(check.reason or "empty", payload.locale)},
        )
    if check.reason == "possible_injection":
        repo.record_event(db, "error_occurred", session_id=session.id,
                          conversation_id=conversation.id, properties={"reason": "possible_injection"})

    if is_new:
        repo.record_event(db, "conversation_started", session_id=session.id,
                          conversation_id=conversation.id,
                          properties={"entry_page": payload.page_url})
    return session, conversation, None


@router.post("/chat", response_model=ChatResponse)
async def chat(payload: ChatRequest, request: Request, db: OrmSession = Depends(get_db)):
    session, conversation, error = _prepare(db, request, payload)
    if error is not None:
        return error

    history = repo.history_for(db, conversation)
    trip = merge_trip_context(repo.trip_state_for(conversation), payload.trip_context)
    repo.record_user_message(db, conversation, payload.message)
    repo.record_event(
        db,
        "follow_up_question" if history else "message_sent",
        session_id=session.id,
        conversation_id=conversation.id,
    )

    result = await get_orchestrator().answer(
        payload.message,
        history=history,
        trip=trip,
        page_url=payload.page_url,
        locale=payload.locale,
        already_linked=set(conversation.linked_content_ids or []),
    )

    message = repo.record_assistant_message(db, conversation, result)
    repo.record_event(
        db, "response_generated", session_id=session.id, conversation_id=conversation.id,
        message_id=message.id,
        properties={
            "intents": result.classification.intents,
            "resources": len(result.resources),
            "affiliates": len(result.affiliates),
            "latency_ms": result.latency_ms,
        },
    )

    return ChatResponse(
        session_id=session.id,
        conversation_id=conversation.id,
        message_id=message.id,
        answer=result.answer,
        resources=result.resources,
        affiliates=result.affiliates,
        intents=result.classification.intents,
        language=result.classification.language,
        trip_state=result.trip.to_dict(),
        notices=result.notices,
        actions=result.actions,
        latency_ms=result.latency_ms,
    )


def _sse(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


@router.post("/chat/stream")
async def chat_stream(payload: ChatRequest, request: Request, db: OrmSession = Depends(get_db)):
    session, conversation, error = _prepare(db, request, payload)
    if error is not None:
        return error

    history = repo.history_for(db, conversation)
    trip = merge_trip_context(repo.trip_state_for(conversation), payload.trip_context)
    repo.record_user_message(db, conversation, payload.message)
    repo.record_event(
        db,
        "follow_up_question" if history else "message_sent",
        session_id=session.id,
        conversation_id=conversation.id,
    )
    already_linked = set(conversation.linked_content_ids or [])

    async def events():
        orchestrator = get_orchestrator()
        try:
            async for kind, data in orchestrator.answer_stream(
                payload.message,
                history=history,
                trip=trip,
                page_url=payload.page_url,
                locale=payload.locale,
                already_linked=already_linked,
            ):
                if kind == "meta":
                    yield _sse("meta", {"session_id": session.id,
                                        "conversation_id": conversation.id, **data})
                elif kind == "delta":
                    yield _sse("delta", {"text": data})
                elif kind == "done":
                    message = repo.record_assistant_message(db, conversation, data)
                    repo.record_event(
                        db, "response_generated", session_id=session.id,
                        conversation_id=conversation.id, message_id=message.id,
                        properties={
                            "intents": data.classification.intents,
                            "resources": len(data.resources),
                            "affiliates": len(data.affiliates),
                            "latency_ms": data.latency_ms,
                        },
                    )
                    yield _sse("done", {
                        "conversation_id": conversation.id,
                        "message_id": message.id,
                        "latency_ms": data.latency_ms,
                        "trip_state": data.trip.to_dict(),
                    })
        except Exception as exc:  # noqa: BLE001 - the stream must close cleanly
            log.exception("stream failed: %s", exc)
            repo.record_event(db, "error_occurred", session_id=session.id,
                              conversation_id=conversation.id, properties={"reason": "stream_failed"})
            yield _sse("error", {"answer": safety.fallback("model_unavailable", payload.locale)})

    return StreamingResponse(
        events(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache, no-transform",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # nginx must not buffer SSE
        },
    )


@router.get("/starters")
async def starters(lang: str = "en"):
    """Starter questions for an empty chat.

    Chosen to demonstrate what the assistant is actually good at — planning,
    trade-offs, logistics — rather than to advertise that a chatbot exists.
    """
    catalogue = {
        "en": [
            "I have 10 days and want Marrakech and the desert. What would you add?",
            "Marrakech or Fes for a first trip?",
            "How many nights do I really need in Merzouga?",
            "We're travelling with a 3-year-old. Is the desert too much?",
            "What's Morocco like in February?",
            "Train, bus or private driver between cities?",
        ],
        "fr": [
            "J'ai 10 jours, Marrakech et le désert. Qu'est-ce que vous ajouteriez ?",
            "Marrakech ou Fès pour un premier voyage ?",
            "Combien de nuits faut-il vraiment à Merzouga ?",
            "On voyage avec un enfant de 3 ans. Le désert, c'est trop ?",
            "Le Maroc en février, ça donne quoi ?",
            "Train, bus ou chauffeur privé entre les villes ?",
        ],
    }
    return {"starters": catalogue.get(lang, catalogue["en"])}
