"""Database operations, kept out of the route handlers."""
from __future__ import annotations

import datetime as dt
import hashlib
import re
import uuid
from typing import Any

from sqlalchemy import delete, desc, func, select
from sqlalchemy.orm import Session as OrmSession

from app.config import get_settings
from app.db.models import (
    ContentGap,
    Conversation,
    Event,
    Feedback,
    Message,
    Session,
    UsageCounter,
    get_sessionmaker,
)
from app.schemas import TripState


def session_scope():
    return get_sessionmaker()()


def hash_ip(ip: str | None) -> str | None:
    """Salted hash. The salt is the widget key, so hashes are not portable."""
    if not ip:
        return None
    salt = get_settings().widget_key or "comemorocco"
    return hashlib.sha256(f"{salt}:{ip}".encode()).hexdigest()[:32]


# ---------------------------------------------------------------- sessions
_SESSION_ID = re.compile(r"^[a-f0-9]{16,32}$")


def get_or_create_session(
    db: OrmSession,
    session_id: str | None,
    *,
    ip: str | None = None,
    user_agent: str | None = None,
    locale: str | None = None,
) -> Session:
    """Find the caller's session, or start one.

    The session id is asserted by the client — it is a random value the widget
    generates and keeps in localStorage, not something the server hands out.
    So an id we have never seen is adopted rather than replaced: replacing it
    would give the caller a different session on every request, which silently
    breaks conversation continuity and makes per-session rate limiting
    useless.

    Adopting a client-asserted id means someone can rotate ids to dodge the
    per-session limit. That is expected, and why the rate-limit key also
    contains the hashed IP.
    """
    if session_id:
        existing = db.get(Session, session_id)
        if existing:
            existing.last_seen_at = dt.datetime.now(dt.timezone.utc)
            db.commit()
            return existing

    record = Session(
        # Only adopt an id that looks like one we would have issued, so the
        # column cannot be used to store arbitrary caller-controlled strings.
        id=session_id if session_id and _SESSION_ID.match(session_id) else uuid.uuid4().hex,
        ip_hash=hash_ip(ip),
        user_agent_family=(user_agent or "")[:64] or None,
        locale=locale,
    )
    db.add(record)
    db.commit()
    return record


def get_or_create_conversation(
    db: OrmSession,
    session: Session,
    conversation_id: str | None,
    *,
    entry_page: str | None = None,
) -> tuple[Conversation, bool]:
    if conversation_id:
        existing = db.get(Conversation, conversation_id)
        if existing and existing.session_id == session.id:
            return existing, False

    conversation = Conversation(session_id=session.id, entry_page=entry_page)
    db.add(conversation)
    db.commit()
    return conversation, True


def history_for(db: OrmSession, conversation: Conversation) -> list[dict[str, str]]:
    settings = get_settings()
    rows = (
        db.execute(
            select(Message)
            .where(Message.conversation_id == conversation.id)
            .order_by(desc(Message.created_at))
            .limit(settings.max_history_turns)
        )
        .scalars()
        .all()
    )
    return [{"role": row.role, "content": row.content} for row in reversed(rows)]


def trip_state_for(conversation: Conversation) -> TripState:
    return TripState.from_dict(conversation.trip_state or {})


# ---------------------------------------------------------------- messages
def record_user_message(db: OrmSession, conversation: Conversation, content: str) -> Message:
    message = Message(conversation_id=conversation.id, role="user", content=content)
    db.add(message)
    conversation.message_count += 1
    db.commit()
    return message


def record_assistant_message(db: OrmSession, conversation: Conversation, result) -> Message:
    """Persist an AnswerResult and update the conversation's carried state."""
    message = Message(
        id=result.message_id,
        conversation_id=conversation.id,
        role="assistant",
        content=result.answer,
        intents=result.classification.intents,
        resources=[r.model_dump() for r in result.resources],
        affiliates=[a.model_dump() for a in result.affiliates],
        retrieval_debug=result.debug,
        quality_issues=result.quality_issues or None,
        flagged_for_review=result.flagged_for_review,
        review_status="open" if result.flagged_for_review else "none",
        input_tokens=result.usage.input_tokens,
        output_tokens=result.usage.output_tokens,
        latency_ms=result.latency_ms,
        model=get_settings().active_answer_model,
    )
    db.add(message)

    conversation.trip_state = result.trip.to_dict()
    conversation.language = result.classification.language
    already = set(conversation.linked_content_ids or [])
    already.update(r.content_id for r in result.resources)
    conversation.linked_content_ids = sorted(already)
    conversation.message_count += 1

    add_usage(db, result.usage.input_tokens, result.usage.output_tokens, commit=False)

    if result.content_gap:
        record_content_gap(db, result.content_gap, commit=False)

    db.commit()
    return message


# ---------------------------------------------------------------- feedback
def record_feedback(
    db: OrmSession, message_id: str, helpful: bool, reason: str | None, comment: str | None
) -> Feedback | None:
    message = db.get(Message, message_id)
    if not message:
        return None
    entry = Feedback(message_id=message_id, helpful=helpful, reason=reason, comment=comment)
    db.add(entry)
    # Negative feedback puts the answer in front of a human. This is the
    # signal the moderation dashboard is built around.
    if not helpful and message.review_status == "none":
        message.review_status = "open"
        message.flagged_for_review = True
    db.commit()
    return entry


# ---------------------------------------------------------------- analytics
def record_event(
    db: OrmSession,
    name: str,
    *,
    session_id: str | None = None,
    conversation_id: str | None = None,
    message_id: str | None = None,
    properties: dict[str, Any] | None = None,
) -> None:
    db.add(
        Event(
            name=name,
            session_id=session_id,
            conversation_id=conversation_id,
            message_id=message_id,
            properties=properties or {},
        )
    )
    db.commit()


def add_usage(db: OrmSession, input_tokens: int, output_tokens: int, *, commit: bool = True) -> None:
    day = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d")
    counter = db.get(UsageCounter, day)
    if counter is None:
        # Column defaults are applied on INSERT, but this row is incremented
        # before it is flushed, so the values have to be set here.
        counter = UsageCounter(day=day, input_tokens=0, output_tokens=0, messages=0)
        db.add(counter)
    counter.input_tokens += input_tokens
    counter.output_tokens += output_tokens
    counter.messages += 1
    if commit:
        db.commit()


def today_usage(db: OrmSession) -> UsageCounter | None:
    day = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d")
    return db.get(UsageCounter, day)


def over_token_budget(db: OrmSession) -> bool:
    counter = today_usage(db)
    if counter is None:
        return False
    return (counter.input_tokens + counter.output_tokens) >= get_settings().daily_token_budget


# ------------------------------------------------------------- content gaps
_NORMALISE = re.compile(r"[^a-z0-9 ]")


def fingerprint(question: str) -> str:
    text = _NORMALISE.sub("", question.lower())
    words = sorted(set(w for w in text.split() if len(w) > 3))[:12]
    return hashlib.sha256(" ".join(words).encode()).hexdigest()[:32]


def record_content_gap(db: OrmSession, gap: dict[str, Any], *, commit: bool = True) -> None:
    key = fingerprint(gap["question"])
    existing = db.execute(select(ContentGap).where(ContentGap.fingerprint == key)).scalar_one_or_none()
    if existing:
        existing.occurrences += 1
        existing.best_score = max(existing.best_score, gap.get("best_score", 0.0))
    else:
        db.add(
            ContentGap(
                fingerprint=key,
                example_question=gap["question"],
                intents=gap.get("intents", []),
                destinations=gap.get("destinations", []),
                best_score=gap.get("best_score", 0.0),
            )
        )
    if commit:
        db.commit()


def top_content_gaps(db: OrmSession, limit: int = 50) -> list[ContentGap]:
    return (
        db.execute(
            select(ContentGap)
            .where(ContentGap.status == "open")
            .order_by(desc(ContentGap.occurrences))
            .limit(limit)
        )
        .scalars()
        .all()
    )


# ------------------------------------------------------------------- admin
def flagged_messages(db: OrmSession, limit: int = 50) -> list[Message]:
    return (
        db.execute(
            select(Message)
            .where(Message.review_status == "open")
            .order_by(desc(Message.created_at))
            .limit(limit)
        )
        .scalars()
        .all()
    )


def stats(db: OrmSession, days: int = 7) -> dict[str, Any]:
    since = dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=days)

    conversations = db.execute(
        select(func.count(Conversation.id)).where(Conversation.created_at >= since)
    ).scalar_one()
    messages = db.execute(
        select(func.count(Message.id)).where(Message.created_at >= since, Message.role == "user")
    ).scalar_one()
    positive = db.execute(
        select(func.count(Feedback.id)).where(Feedback.created_at >= since, Feedback.helpful.is_(True))
    ).scalar_one()
    negative = db.execute(
        select(func.count(Feedback.id)).where(Feedback.created_at >= since, Feedback.helpful.is_(False))
    ).scalar_one()
    latency = db.execute(
        select(func.avg(Message.latency_ms)).where(Message.created_at >= since, Message.role == "assistant")
    ).scalar_one()
    flagged = db.execute(select(func.count(Message.id)).where(Message.review_status == "open")).scalar_one()

    event_counts = dict(
        db.execute(
            select(Event.name, func.count(Event.id)).where(Event.created_at >= since).group_by(Event.name)
        ).all()
    )

    total_feedback = positive + negative
    return {
        "window_days": days,
        "conversations": conversations,
        "user_messages": messages,
        "messages_per_conversation": round(messages / conversations, 2) if conversations else 0,
        "feedback_positive": positive,
        "feedback_negative": negative,
        "helpful_rate": round(positive / total_feedback, 3) if total_feedback else None,
        "avg_latency_ms": int(latency) if latency else None,
        "flagged_open": flagged,
        "events": event_counts,
        "today_tokens": (lambda c: (c.input_tokens + c.output_tokens) if c else 0)(today_usage(db)),
    }


# --------------------------------------------------------------- retention
def purge_expired(db: OrmSession) -> dict[str, int]:
    """Delete conversation content past the retention window.

    Analytics events and aggregate counters survive; message text does not.
    """
    settings = get_settings()
    cutoff = dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=settings.conversation_retention_days)

    old_conversations = (
        db.execute(select(Conversation.id).where(Conversation.updated_at < cutoff)).scalars().all()
    )
    if not old_conversations:
        return {"conversations": 0, "messages": 0}

    message_ids = (
        db.execute(select(Message.id).where(Message.conversation_id.in_(old_conversations)))
        .scalars()
        .all()
    )
    db.execute(delete(Feedback).where(Feedback.message_id.in_(message_ids)))
    db.execute(delete(Message).where(Message.conversation_id.in_(old_conversations)))
    db.execute(delete(Conversation).where(Conversation.id.in_(old_conversations)))

    session_cutoff = dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=settings.session_ttl_days)
    orphan_sessions = (
        db.execute(
            select(Session.id)
            .outerjoin(Conversation, Conversation.session_id == Session.id)
            .where(Session.last_seen_at < session_cutoff, Conversation.id.is_(None))
        )
        .scalars()
        .all()
    )
    if orphan_sessions:
        db.execute(delete(Session).where(Session.id.in_(orphan_sessions)))

    db.commit()
    return {"conversations": len(old_conversations), "messages": len(message_ids)}
