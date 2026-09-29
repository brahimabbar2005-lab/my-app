"""ComeMorocco AI service."""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from app.api import routes_admin, routes_chat
from app.config import ROOT, get_settings
from app.core import safety
from app.core.llm import available as model_available
from app.db.models import init_db
from app.infra.logging import configure_logging
from app.knowledge.retriever import get_retriever

log = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    configure_logging()
    settings = get_settings()
    init_db()
    # Build the index at startup rather than on the first request, so the
    # first traveller of the day does not pay for it.
    retriever = get_retriever()
    log.info("ComeMorocco AI starting: %s", retriever.kb.health())
    if not model_available():
        log.warning(
            "No model key set (ANTHROPIC_API_KEY or OPENROUTER_API_KEY) — chat will return the fallback message"
        )
    else:
        log.info(
            "model: %s via %s | model calls per question: %d",
            settings.active_answer_model,
            settings.llm_provider,
            1 + (2 if settings.model_classification_enabled else 0) + (1 if settings.quality_check_enabled else 0),
        )
        if settings.on_free_tier:
            log.info("free model: optional model calls are off to stay within OpenRouter's daily request limit")
    if settings.environment != "development" and not settings.widget_key:
        log.warning("WIDGET_KEY is not set in a non-development environment")
    yield
    log.info("ComeMorocco AI shutting down")


app = FastAPI(
    title="ComeMorocco AI",
    description="Morocco travel assistant for ComeMorocco.com",
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/api/docs",
    openapi_url="/api/openapi.json",
)

_settings = get_settings()
app.add_middleware(
    CORSMiddleware,
    allow_origins=_settings.cors_origins,
    allow_credentials=False,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Content-Type", "X-Widget-Key", "X-Admin-Key"],
    max_age=3600,
)

app.include_router(routes_chat.router)
app.include_router(routes_admin.public)
app.include_router(routes_admin.admin)
app.include_router(routes_admin.sync)

# The widget is served from here in development. In production it is served by
# the WordPress plugin from the site's own domain.
widget_dir = ROOT / "widget"
if widget_dir.exists():
    app.mount("/widget", StaticFiles(directory=widget_dir, html=True), name="widget")


@app.exception_handler(Exception)
async def unhandled(request: Request, exc: Exception):
    """Travellers never see a stack trace (02_MVP_SCOPE §36)."""
    log.exception("unhandled error on %s: %s", request.url.path, exc)
    return JSONResponse(
        status_code=500,
        content={"error": "internal_error", "answer": safety.fallback("model_unavailable")},
    )


@app.get("/health")
async def health():
    retriever = get_retriever()
    return {
        "status": "ok",
        "model_configured": model_available(),
        "provider": get_settings().llm_provider,
        "model": get_settings().active_answer_model,
        "knowledge": retriever.kb.health(),
    }


@app.get("/")
async def root():
    return {"service": "ComeMorocco AI", "docs": "/api/docs", "health": "/health"}
