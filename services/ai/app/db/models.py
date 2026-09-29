"""Persistence.

SQLite by default so the project runs with no infrastructure; the schema is
plain SQLAlchemy, so pointing DATABASE_URL at Postgres is the only change
needed for production. pgvector is not used — retrieval is lexical and lives
in memory (see app/knowledge/index.py), which keeps the database to the
things that genuinely need durability.

Privacy shape (02_MVP_SCOPE §31): no accounts, no names, no emails. A session
is an opaque id in a first-party cookie. IP addresses are stored only as a
salted hash, and only for rate limiting.
"""
from __future__ import annotations

import datetime as dt
import uuid
from typing import Any

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    create_engine,
    func,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship, sessionmaker

from app.config import get_settings


def _uuid() -> str:
    return uuid.uuid4().hex


def _now() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc)


class Base(DeclarativeBase):
    pass


class Session(Base):
    """An anonymous browser session. No personal data."""

    __tablename__ = "sessions"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), default=_now)
    last_seen_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), default=_now)
    # Salted hash only, for abuse controls. Never the raw address.
    ip_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    user_agent_family: Mapped[str | None] = mapped_column(String(64), nullable=True)
    locale: Mapped[str | None] = mapped_column(String(8), nullable=True)

    conversations: Mapped[list["Conversation"]] = relationship(back_populates="session")


class Conversation(Base):
    __tablename__ = "conversations"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    session_id: Mapped[str] = mapped_column(ForeignKey("sessions.id"), index=True)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), default=_now)
    updated_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), default=_now, onupdate=_now)
    language: Mapped[str] = mapped_column(String(8), default="en")
    # The structured trip picture, carried across turns.
    trip_state: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    # Content ids already linked, so the same page is not recommended twice.
    linked_content_ids: Mapped[list[str]] = mapped_column(JSON, default=list)
    entry_page: Mapped[str | None] = mapped_column(String(500), nullable=True)
    message_count: Mapped[int] = mapped_column(Integer, default=0)

    session: Mapped[Session] = relationship(back_populates="conversations")
    messages: Mapped[list["Message"]] = relationship(
        back_populates="conversation", order_by="Message.created_at"
    )


class Message(Base):
    __tablename__ = "messages"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    conversation_id: Mapped[str] = mapped_column(ForeignKey("conversations.id"), index=True)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), default=_now)
    role: Mapped[str] = mapped_column(String(16))
    content: Mapped[str] = mapped_column(Text)

    # Assistant-message metadata. Null on user messages.
    intents: Mapped[list[str] | None] = mapped_column(JSON, nullable=True)
    resources: Mapped[list[dict] | None] = mapped_column(JSON, nullable=True)
    affiliates: Mapped[list[dict] | None] = mapped_column(JSON, nullable=True)
    retrieval_debug: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    quality_issues: Mapped[list[dict] | None] = mapped_column(JSON, nullable=True)
    flagged_for_review: Mapped[bool] = mapped_column(Boolean, default=False)
    review_status: Mapped[str] = mapped_column(String(16), default="none")  # none|open|approved|corrected
    input_tokens: Mapped[int] = mapped_column(Integer, default=0)
    output_tokens: Mapped[int] = mapped_column(Integer, default=0)
    latency_ms: Mapped[int] = mapped_column(Integer, default=0)
    model: Mapped[str | None] = mapped_column(String(64), nullable=True)

    conversation: Mapped[Conversation] = relationship(back_populates="messages")
    feedback: Mapped[list["Feedback"]] = relationship(back_populates="message")


Index("ix_messages_flagged", Message.flagged_for_review, Message.review_status)


class Feedback(Base):
    __tablename__ = "feedback"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    message_id: Mapped[str] = mapped_column(ForeignKey("messages.id"), index=True)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), default=_now)
    helpful: Mapped[bool] = mapped_column(Boolean)
    reason: Mapped[str | None] = mapped_column(String(32), nullable=True)
    comment: Mapped[str | None] = mapped_column(Text, nullable=True)

    message: Mapped[Message] = relationship(back_populates="feedback")


class Event(Base):
    """Product analytics. Aggregated reporting only — no profiling."""

    __tablename__ = "events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), default=_now, index=True)
    name: Mapped[str] = mapped_column(String(48), index=True)
    session_id: Mapped[str | None] = mapped_column(String(32), nullable=True)
    conversation_id: Mapped[str | None] = mapped_column(String(32), nullable=True)
    message_id: Mapped[str | None] = mapped_column(String(32), nullable=True)
    properties: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)


class ContentGap(Base):
    """Questions ComeMorocco has no good page for.

    This is the editorial flywheel from the blueprint: every unanswerable-from-
    site question is a content brief waiting to be written.
    """

    __tablename__ = "content_gaps"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), default=_now)
    updated_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), default=_now, onupdate=_now)
    # Normalised question text, so repeats increment a counter instead of
    # creating hundreds of near-identical rows.
    fingerprint: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    example_question: Mapped[str] = mapped_column(Text)
    intents: Mapped[list[str]] = mapped_column(JSON, default=list)
    destinations: Mapped[list[str]] = mapped_column(JSON, default=list)
    occurrences: Mapped[int] = mapped_column(Integer, default=1)
    best_score: Mapped[float] = mapped_column(Float, default=0.0)
    status: Mapped[str] = mapped_column(String(16), default="open")  # open|planned|written|ignored


class UsageCounter(Base):
    """Daily token spend, for the budget guard."""

    __tablename__ = "usage_counters"

    day: Mapped[str] = mapped_column(String(10), primary_key=True)  # YYYY-MM-DD
    input_tokens: Mapped[int] = mapped_column(Integer, default=0)
    output_tokens: Mapped[int] = mapped_column(Integer, default=0)
    messages: Mapped[int] = mapped_column(Integer, default=0)


# ---------------------------------------------------------------------------
_engine = None
_SessionLocal = None


def get_engine():
    global _engine
    if _engine is None:
        settings = get_settings()
        kwargs: dict[str, Any] = {"pool_pre_ping": True, "future": True}
        if settings.database_url.startswith("sqlite"):
            kwargs["connect_args"] = {"check_same_thread": False}
        _engine = create_engine(settings.database_url, **kwargs)
    return _engine


def get_sessionmaker():
    global _SessionLocal
    if _SessionLocal is None:
        _SessionLocal = sessionmaker(bind=get_engine(), expire_on_commit=False, future=True)
    return _SessionLocal


def init_db() -> None:
    settings = get_settings()
    if settings.database_url.startswith("sqlite"):
        from pathlib import Path

        path = settings.database_url.replace("sqlite:///", "")
        Path(path).parent.mkdir(parents=True, exist_ok=True)
    Base.metadata.create_all(get_engine())
