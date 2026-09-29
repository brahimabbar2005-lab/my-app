"""Logging.

Structured JSON in production so lines are queryable; readable text in
development. Message text is never logged — only ids, timings and counts.
"""
from __future__ import annotations

import json
import logging
import sys
from typing import Any

from app.config import get_settings

SAFE_EXTRA = {
    "conversation_id", "message_id", "session_id", "intents", "language",
    "latency_ms", "input_tokens", "output_tokens", "resources", "affiliates",
    "flagged", "event", "score", "reason", "complexity",
}


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "time": self.formatTime(record, "%Y-%m-%dT%H:%M:%S%z"),
        }
        for key, value in record.__dict__.items():
            if key in SAFE_EXTRA:
                payload[key] = value
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=False)


def configure_logging() -> None:
    settings = get_settings()
    handler = logging.StreamHandler(sys.stdout)
    if settings.environment == "development":
        handler.setFormatter(logging.Formatter("%(levelname)-7s %(name)-28s %(message)s"))
    else:
        handler.setFormatter(JsonFormatter())

    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(settings.log_level.upper())

    for noisy in ("httpx", "httpcore", "anthropic"):
        logging.getLogger(noisy).setLevel(logging.WARNING)
