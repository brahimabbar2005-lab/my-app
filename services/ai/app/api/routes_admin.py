"""Feedback, analytics and maintenance endpoints."""
from __future__ import annotations

import logging
import secrets

from fastapi import APIRouter, Depends, Header, HTTPException
from sqlalchemy.orm import Session as OrmSession

from app.api.deps import get_db, require_admin_key, require_widget_key
from app.config import get_settings
from app.db import repo
from app.knowledge.retriever import get_retriever
from app.schemas import AnalyticsEvent, FeedbackRequest

log = logging.getLogger(__name__)

def require_sync_secret(x_sync_secret: str | None = Header(default=None)) -> None:
    """Auth for the WordPress plugin.

    Separate from the admin key on purpose: the plugin needs to say "content
    changed", nothing more, so a compromised WordPress install cannot read the
    moderation queue or the analytics.
    """
    expected = get_settings().sync_secret
    if not expected:
        raise HTTPException(status_code=503, detail="SYNC_SECRET is not configured")
    if not x_sync_secret or not secrets.compare_digest(x_sync_secret, expected):
        raise HTTPException(status_code=401, detail="invalid sync secret")


public = APIRouter(prefix="/api", tags=["feedback"], dependencies=[Depends(require_widget_key)])
admin = APIRouter(prefix="/api/admin", tags=["admin"], dependencies=[Depends(require_admin_key)])
sync = APIRouter(prefix="/api/admin", tags=["sync"], dependencies=[Depends(require_sync_secret)])


@public.post("/feedback")
async def submit_feedback(payload: FeedbackRequest, db: OrmSession = Depends(get_db)):
    entry = repo.record_feedback(
        db, payload.message_id, payload.helpful, payload.reason, payload.comment
    )
    if entry is None:
        raise HTTPException(status_code=404, detail="message not found")

    repo.record_event(
        db,
        "feedback_positive" if payload.helpful else "feedback_negative",
        message_id=payload.message_id,
        properties={"reason": payload.reason},
    )
    return {"ok": True}


@public.post("/events")
async def track(payload: AnalyticsEvent, db: OrmSession = Depends(get_db)):
    """Client-side product events.

    Accepts only the names in the AnalyticsEvent enum, so the widget cannot be
    used to write arbitrary rows.
    """
    repo.record_event(
        db,
        payload.name,
        session_id=payload.session_id,
        conversation_id=payload.conversation_id,
        message_id=payload.message_id,
        properties=payload.properties,
    )
    return {"ok": True}


# ---------------------------------------------------------------------------
@admin.get("/stats")
async def stats(days: int = 7, db: OrmSession = Depends(get_db)):
    return repo.stats(db, days=days)


@admin.get("/flagged")
async def flagged(limit: int = 50, db: OrmSession = Depends(get_db)):
    """The moderation queue: answers that failed a check or got a thumbs down."""
    rows = repo.flagged_messages(db, limit=limit)
    return {
        "count": len(rows),
        "messages": [
            {
                "id": row.id,
                "conversation_id": row.conversation_id,
                "created_at": row.created_at.isoformat(),
                "content": row.content,
                "intents": row.intents,
                "quality_issues": row.quality_issues,
                "resources": row.resources,
                "affiliates": row.affiliates,
                "retrieval": (row.retrieval_debug or {}).get("retrieved", [])[:5],
                "feedback": [
                    {"helpful": f.helpful, "reason": f.reason, "comment": f.comment}
                    for f in row.feedback
                ],
            }
            for row in rows
        ],
    }


@admin.post("/flagged/{message_id}/resolve")
async def resolve(message_id: str, status: str = "approved", db: OrmSession = Depends(get_db)):
    if status not in {"approved", "corrected", "ignored"}:
        raise HTTPException(status_code=400, detail="status must be approved, corrected or ignored")
    from app.db.models import Message

    message = db.get(Message, message_id)
    if not message:
        raise HTTPException(status_code=404, detail="message not found")
    message.review_status = status
    message.flagged_for_review = False
    db.commit()
    return {"ok": True, "status": status}


@admin.get("/content-gaps")
async def content_gaps(limit: int = 50, db: OrmSession = Depends(get_db)):
    """Questions travellers ask that ComeMorocco has no good page for.

    This is the editorial brief list. Ordered by how often it has come up.
    """
    rows = repo.top_content_gaps(db, limit=limit)
    return {
        "count": len(rows),
        "gaps": [
            {
                "example_question": row.example_question,
                "occurrences": row.occurrences,
                "intents": row.intents,
                "destinations": row.destinations,
                "best_score": row.best_score,
                "first_seen": row.created_at.isoformat(),
            }
            for row in rows
        ],
    }


@admin.post("/reindex")
async def reindex():
    """Reload the knowledge base from disk and rebuild the index.

    Called by scripts/wp_sync.py after a content export, so updating what the
    assistant knows never requires a deployment.
    """
    counts = get_retriever().rebuild()
    log.info("knowledge base reindexed: %s", counts)
    return {"ok": True, **counts}


@admin.post("/purge")
async def purge(db: OrmSession = Depends(get_db)):
    """Apply the retention policy. Intended to run nightly from cron."""
    result = repo.purge_expired(db)
    log.info("retention purge removed %s", result)
    return {"ok": True, **result}


@sync.post("/content-changed")
async def content_changed(payload: dict | None = None):
    """Called by the WordPress plugin when published content changes.

    Authenticated with the sync secret rather than the admin key, because the
    plugin holds the former and should never hold the latter. The plugin fires
    this non-blocking and debounced, so this handler only has to be fast and
    idempotent — the nightly sync is the backstop if it never arrives.
    """
    counts = get_retriever().rebuild()
    log.info("reindexed after a content change from WordPress: %s", counts)
    return {"ok": True, **counts}


@admin.get("/providers")
async def providers():
    """Model provider chain and the health the router has recorded for each."""
    from app.core.providers.router import get_router

    return {"chain": get_router().snapshot()}


@admin.get("/config")
async def config():
    """Effective configuration, with secrets redacted."""
    settings = get_settings()
    return {
        "environment": settings.environment,
        "provider": settings.llm_provider,
        "answer_model": settings.active_answer_model,
        "utility_model": settings.active_utility_model,
        "model_classification_enabled": settings.model_classification_enabled,
        "live_data_enabled": settings.live_data_enabled,
        "affiliates_enabled": settings.affiliates_enabled,
        "quality_check_enabled": settings.quality_check_enabled,
        "supported_languages": settings.supported_languages,
        "rate_limit_per_minute": settings.rate_limit_per_minute,
        "rate_limit_per_day": settings.rate_limit_per_day,
        "conversation_retention_days": settings.conversation_retention_days,
        "model_key_set": bool(settings.model_key),
        "llm_chain": settings.llm_chain,
        "workers_ai_configured": settings.workers_ai_configured,
        "app_key_set": bool(settings.app_key),
        "widget_key_set": bool(settings.widget_key),
    }
