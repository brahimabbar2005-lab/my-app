"""Runtime configuration, read from the environment (and from .env)."""
from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# Read .env from the project root before any setting is looked up. Without
# this, a key written into .env is silently ignored and the service runs in
# fallback mode. Variables already set in the real environment win.
try:
    from dotenv import load_dotenv

    load_dotenv(ROOT / ".env", override=False)
except ImportError:  # pragma: no cover - dotenv is a declared dependency
    pass


# Every reader treats a blank value as unset. .env.example ships lines like
# `DATABASE_URL=` for the user to fill in; copied as-is, those must fall back
# to the default rather than become an empty string the app then tries to use.
def _str(name: str, default: str | None = None) -> str | None:
    raw = os.getenv(name)
    if raw is None or not raw.strip():
        return default
    return raw.strip()


def _bool(name: str, default: bool) -> bool:
    raw = _str(name)
    if raw is None:
        return default
    return raw.lower() in {"1", "true", "yes", "on"}


def _int(name: str, default: int) -> int:
    raw = _str(name)
    try:
        return int(raw) if raw is not None else default
    except ValueError:
        return default


def _float(name: str, default: float) -> float:
    raw = _str(name)
    try:
        return float(raw) if raw is not None else default
    except ValueError:
        return default


def _list(name: str, default: list[str]) -> list[str]:
    raw = _str(name)
    if raw is None:
        return default
    return [item.strip() for item in raw.split(",") if item.strip()]


@dataclass(frozen=True)
class Settings:
    """Plain values. Built by `load_settings()`, never with class defaults.

    Reading the environment inside a factory — rather than in the field
    defaults — matters: dataclass defaults are evaluated once, at import, so
    the old version froze whatever the environment held at that moment and
    `get_settings.cache_clear()` could not pick up a change.
    """

    # service
    environment: str
    log_level: str
    cors_origins: list[str]
    widget_key: str | None
    # Sent by the mobile app. Like WIDGET_KEY it ships inside the client, so it
    # is abuse friction, not a secret. Either key is accepted on /api/*.
    app_key: str | None
    admin_key: str | None
    sync_secret: str | None
    wordpress_url: str
    # Verifying signed-in app users (app/infra/auth.py). Either is enough.
    supabase_url: str | None
    supabase_jwt_secret: str | None

    # model
    # "anthropic" or "openrouter". Chosen automatically from whichever key is
    # set, unless LLM_PROVIDER says otherwise.
    llm_provider: str
    anthropic_api_key: str | None
    answer_model: str
    utility_model: str
    openrouter_api_key: str | None
    openrouter_model: str
    openrouter_utility_model: str
    openrouter_base_url: str
    # Reasoning models spend tokens thinking before they answer. "low" keeps
    # that short; "none" omits the parameter for models that reject it.
    openrouter_reasoning_effort: str
    # Whether intent classification and trip extraction also call the model,
    # on top of the rules. Each call costs one request against a provider's
    # rate limit; the rules alone are a working fallback.
    model_classification_enabled: bool
    # Provider fallback chain, e.g.
    #   openrouter:model-a:free,openrouter:model-b:free,workers_ai:@cf/...
    # Empty means "derive from the keys that are set" (see providers/router.py).
    llm_chain: list[str]
    openrouter_fallback_model: str | None
    cloudflare_account_id: str | None
    cloudflare_api_token: str | None
    # No default model on purpose: Cloudflare changes which models the free
    # plan can use, so the model is always named in configuration.
    workers_ai_model: str | None
    workers_ai_base_url: str
    # Skip a provider that has not started answering within this many seconds
    # (streaming), or has not finished within the second value (non-streaming).
    llm_first_token_timeout_seconds: float
    llm_provider_timeout_seconds: float
    max_answer_tokens: int
    temperature: float
    request_timeout_seconds: int

    # retrieval
    knowledge_dir: Path
    retrieval_candidates: int
    retrieval_context_items: int
    min_retrieval_score: float

    # conversation
    max_history_turns: int
    max_message_chars: int
    session_ttl_days: int
    conversation_retention_days: int

    # limits
    rate_limit_per_minute: int
    rate_limit_per_day: int
    # Signed-in users get this many times the guest limits.
    signed_in_rate_multiplier: int
    daily_token_budget: int

    # behaviour
    quality_check_enabled: bool
    affiliates_enabled: bool
    # No live weather/train/availability integration exists yet. While this is
    # false the assistant must never present schedules, prices or availability
    # as checked. Turning it on without wiring a real tool is a product bug.
    live_data_enabled: bool
    supported_languages: list[str]

    # storage
    database_url: str

    # site
    site_url: str
    contact_url: str

    @property
    def model_key(self) -> str | None:
        return self.openrouter_api_key if self.llm_provider == "openrouter" else self.anthropic_api_key

    @property
    def workers_ai_configured(self) -> bool:
        return bool(self.cloudflare_account_id and self.cloudflare_api_token and self.workers_ai_model)

    @property
    def active_answer_model(self) -> str:
        return self.openrouter_model if self.llm_provider == "openrouter" else self.answer_model

    @property
    def active_utility_model(self) -> str:
        return self.openrouter_utility_model if self.llm_provider == "openrouter" else self.utility_model

    @property
    def on_free_tier(self) -> bool:
        return self.llm_provider == "openrouter" and self.openrouter_model.endswith(":free")


def _provider() -> str:
    explicit = (_str("LLM_PROVIDER") or "").lower()
    if explicit in {"anthropic", "openrouter"}:
        return explicit
    # Auto: prefer Anthropic when both keys exist, OpenRouter when only it does.
    if _str("ANTHROPIC_API_KEY"):
        return "anthropic"
    if _str("OPENROUTER_API_KEY"):
        return "openrouter"
    return "anthropic"


def load_settings() -> Settings:
    provider = _provider()
    openrouter_model = _str("OPENROUTER_MODEL", "nvidia/nemotron-3.5-lightning:free")
    # Free OpenRouter models allow 50 requests a day without purchased
    # credits, and the full pipeline makes up to four calls per question. So
    # on a :free model the two optional calls default to off — one request per
    # question — unless explicitly turned back on.
    free_tier = provider == "openrouter" and openrouter_model.endswith(":free")
    return Settings(
        environment=_str("ENVIRONMENT", "development"),
        log_level=_str("LOG_LEVEL", "INFO"),
        cors_origins=_list("CORS_ORIGINS", ["http://localhost:8000", "https://comemorocco.com"]),
        widget_key=_str("WIDGET_KEY"),
        app_key=_str("APP_KEY"),
        supabase_url=_str("SUPABASE_URL"),
        supabase_jwt_secret=_str("SUPABASE_JWT_SECRET"),
        admin_key=_str("ADMIN_KEY"),
        sync_secret=_str("SYNC_SECRET"),
        wordpress_url=_str("WORDPRESS_URL", "https://comemorocco.com"),
        llm_provider=provider,
        anthropic_api_key=_str("ANTHROPIC_API_KEY"),
        answer_model=_str("ANSWER_MODEL", "claude-sonnet-4-6"),
        utility_model=_str("UTILITY_MODEL", "claude-haiku-4-5-20251001"),
        openrouter_api_key=_str("OPENROUTER_API_KEY"),
        openrouter_model=openrouter_model,
        openrouter_utility_model=_str("OPENROUTER_UTILITY_MODEL", openrouter_model),
        openrouter_base_url=_str("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1"),
        openrouter_reasoning_effort=(_str("OPENROUTER_REASONING_EFFORT", "low") or "low").lower(),
        model_classification_enabled=_bool("MODEL_CLASSIFICATION_ENABLED", not free_tier),
        llm_chain=_list("LLM_CHAIN", []),
        openrouter_fallback_model=_str("OPENROUTER_FALLBACK_MODEL"),
        cloudflare_account_id=_str("CLOUDFLARE_ACCOUNT_ID"),
        cloudflare_api_token=_str("CLOUDFLARE_API_TOKEN"),
        workers_ai_model=_str("WORKERS_AI_MODEL"),
        workers_ai_base_url=_str("WORKERS_AI_BASE_URL", "https://api.cloudflare.com/client/v4"),
        llm_first_token_timeout_seconds=_float("LLM_FIRST_TOKEN_TIMEOUT", 10.0),
        llm_provider_timeout_seconds=_float("LLM_PROVIDER_TIMEOUT", 45.0),
        max_answer_tokens=_int("MAX_ANSWER_TOKENS", 1400),
        temperature=_float("TEMPERATURE", 0.7),
        request_timeout_seconds=_int("REQUEST_TIMEOUT_SECONDS", 60),
        knowledge_dir=ROOT / "data" / "knowledge",
        retrieval_candidates=_int("RETRIEVAL_CANDIDATES", 12),
        retrieval_context_items=_int("RETRIEVAL_CONTEXT_ITEMS", 6),
        min_retrieval_score=_float("MIN_RETRIEVAL_SCORE", 0.85),
        max_history_turns=_int("MAX_HISTORY_TURNS", 12),
        max_message_chars=_int("MAX_MESSAGE_CHARS", 2000),
        session_ttl_days=_int("SESSION_TTL_DAYS", 30),
        conversation_retention_days=_int("CONVERSATION_RETENTION_DAYS", 90),
        rate_limit_per_minute=_int("RATE_LIMIT_PER_MINUTE", 8),
        rate_limit_per_day=_int("RATE_LIMIT_PER_DAY", 60),
        signed_in_rate_multiplier=_int("SIGNED_IN_RATE_MULTIPLIER", 3),
        daily_token_budget=_int("DAILY_TOKEN_BUDGET", 4_000_000),
        quality_check_enabled=_bool("QUALITY_CHECK_ENABLED", not free_tier),
        affiliates_enabled=_bool("AFFILIATES_ENABLED", True),
        live_data_enabled=_bool("LIVE_DATA_ENABLED", False),
        supported_languages=_list("SUPPORTED_LANGUAGES", ["en", "fr"]),
        database_url=_str("DATABASE_URL", f"sqlite:///{ROOT / 'data' / 'comemorocco.db'}"),
        site_url=_str("SITE_URL", "https://comemorocco.com"),
        contact_url=_str("CONTACT_URL", "https://comemorocco.com/contact/"),
    )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return load_settings()
