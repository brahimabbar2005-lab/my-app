"""The provider contract and the health record the router keeps for each one.

A provider is one (service, model) pair. The same service with two models is
two providers, because free-tier limits are counted per model.
"""

from __future__ import annotations

import time
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from typing import Any, Protocol, runtime_checkable

from app.core.llm import Completion


@runtime_checkable
class LLMProvider(Protocol):
    name: str  # "openrouter", "workers_ai", "anthropic"
    model: str

    @property
    def key(self) -> str:
        """Stable identifier, "<name>:<model>"."""
        ...

    def configured(self) -> bool:
        """True when the credentials this provider needs are present."""
        ...

    async def complete(
        self, system: str, messages: list[dict[str, Any]], max_tokens: int, temperature: float
    ) -> Completion: ...

    def stream(
        self, system: str, messages: list[dict[str, Any]], max_tokens: int, temperature: float
    ) -> AsyncIterator[tuple[str, Any]]:
        """Yield ("delta", text) chunks, then ("usage", Usage)."""
        ...


class ProviderBase:
    name = ""

    def __init__(self, model: str):
        self.model = model

    @property
    def key(self) -> str:
        return f"{self.name}:{self.model}"

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"<{type(self).__name__} {self.key}>"


# How long a provider is skipped after a failure of each kind, in seconds.
# Repeated failures double the wait, up to MAX_COOLDOWN.
COOLDOWN_SECONDS = {
    "rate_limit": 60,
    "quota": 3600,
    "auth": 3600,
    "config": 3600,
    "timeout": 20,
    "network": 20,
    "provider_error": 20,
    "empty": 5,
    "garbled": 30,
}
MAX_COOLDOWN = 6 * 3600


@dataclass
class ProviderHealth:
    """What the router knows about one provider. Exposed on the admin API."""

    key: str
    requests: int = 0
    successes: int = 0
    failures: int = 0
    consecutive_failures: int = 0
    last_error: str | None = None
    last_error_kind: str | None = None
    last_latency_ms: int | None = None
    input_tokens: int = 0
    output_tokens: int = 0
    cooldown_until: float = 0.0
    failures_by_kind: dict[str, int] = field(default_factory=dict)

    def available(self, now: float | None = None) -> bool:
        return (now or time.monotonic()) >= self.cooldown_until

    def record_success(self, latency_ms: int, input_tokens: int = 0, output_tokens: int = 0) -> None:
        self.requests += 1
        self.successes += 1
        self.consecutive_failures = 0
        self.cooldown_until = 0.0
        self.last_latency_ms = latency_ms
        self.input_tokens += input_tokens
        self.output_tokens += output_tokens

    def record_failure(self, kind: str, message: str, latency_ms: int | None = None) -> None:
        self.requests += 1
        self.failures += 1
        self.consecutive_failures += 1
        self.last_error = message[:300]
        self.last_error_kind = kind
        self.last_latency_ms = latency_ms
        self.failures_by_kind[kind] = self.failures_by_kind.get(kind, 0) + 1
        base = COOLDOWN_SECONDS.get(kind, 20)
        wait = min(base * (2 ** (self.consecutive_failures - 1)), MAX_COOLDOWN)
        self.cooldown_until = time.monotonic() + wait

    def snapshot(self) -> dict[str, Any]:
        remaining = max(0.0, self.cooldown_until - time.monotonic())
        return {
            "provider": self.key,
            "available": remaining == 0,
            "cooldown_seconds": round(remaining),
            "requests": self.requests,
            "successes": self.successes,
            "failures": self.failures,
            "failures_by_kind": dict(self.failures_by_kind),
            "last_error_kind": self.last_error_kind,
            "last_error": self.last_error,
            "last_latency_ms": self.last_latency_ms,
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
        }
