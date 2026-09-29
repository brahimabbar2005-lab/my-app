"""Abuse and cost protection.

The chat endpoint is a public, expensive API endpoint. Without this it is a
free proxy to a frontier model (02_MVP_SCOPE §30).

Sliding-window counters kept in memory. That is correct for a single instance
and deliberately simple; the `Limiter` interface is small enough that swapping
in Redis for a multi-instance deployment is a class, not a refactor.
"""
from __future__ import annotations

import re
import threading
import time
from collections import defaultdict, deque
from dataclasses import dataclass

from app.config import get_settings


@dataclass
class LimitVerdict:
    allowed: bool
    reason: str | None = None
    retry_after_seconds: int = 0


class SlidingWindowLimiter:
    def __init__(self) -> None:
        self._minute: dict[str, deque[float]] = defaultdict(deque)
        self._day: dict[str, deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()
        self._last_sweep = time.time()

    def _sweep(self, now: float) -> None:
        """Drop keys with no recent activity so memory does not grow forever."""
        if now - self._last_sweep < 300:
            return
        self._last_sweep = now
        for store, window in ((self._minute, 60), (self._day, 86_400)):
            for key in list(store.keys()):
                bucket = store[key]
                while bucket and now - bucket[0] > window:
                    bucket.popleft()
                if not bucket:
                    del store[key]

    def check(self, key: str, multiplier: int = 1) -> LimitVerdict:
        settings = get_settings()
        now = time.time()
        per_minute = settings.rate_limit_per_minute * multiplier
        per_day = settings.rate_limit_per_day * multiplier
        with self._lock:
            self._sweep(now)

            minute = self._minute[key]
            while minute and now - minute[0] > 60:
                minute.popleft()
            if len(minute) >= per_minute:
                wait = int(60 - (now - minute[0])) + 1
                return LimitVerdict(False, "too_fast", wait)

            day = self._day[key]
            while day and now - day[0] > 86_400:
                day.popleft()
            if len(day) >= per_day:
                return LimitVerdict(False, "daily_limit", 3600)

            minute.append(now)
            day.append(now)
        return LimitVerdict(True)


# Shared addresses are normal: a family, an office, a hotel lobby, a mobile
# carrier's NAT. The per-IP ceiling is a multiple of the per-session one so it
# catches abuse without punishing them.
IP_LIMIT_MULTIPLIER = 5

_limiter = SlidingWindowLimiter()


def check_rate(session_key: str, ip_key: str | None = None, user_id: str | None = None) -> LimitVerdict:
    """Check the session and the IP independently.

    Combining both into one key looked right but was not: session ids are
    asserted by the client, so anyone rotating them produced a fresh combined
    key every request and never hit a limit. Checking the buckets separately
    means a rotated session id still runs into the per-IP limit.

    The IP bucket is given a higher ceiling because households, offices and
    mobile carriers legitimately share one address.

    Signed-in callers (a verified Supabase user id) are limited per account,
    at SIGNED_IN_RATE_MULTIPLIER times the guest limits.
    """
    if user_id:
        # A verified account is a stronger identity than a client-chosen
        # session id, so it is the bucket, and it gets a higher ceiling.
        multiplier = max(1, get_settings().signed_in_rate_multiplier)
        verdict = _limiter.check(f"u:{user_id}", multiplier=multiplier)
    else:
        multiplier = 1
        verdict = _limiter.check(f"s:{session_key}")
    if not verdict.allowed:
        return verdict
    if ip_key:
        return _limiter.check(f"i:{ip_key}", multiplier=IP_LIMIT_MULTIPLIER * multiplier)
    return verdict


# ---------------------------------------------------------------------------
# Input validation beyond length
# ---------------------------------------------------------------------------
PROMPT_INJECTION = re.compile(
    r"(ignore (all |your |the )?(previous|prior|above) (instructions|prompts|rules)"
    r"|disregard (your|the|all) (instructions|rules|system prompt)"
    r"|you are now (a|an|no longer)"
    r"|reveal (your|the) (system )?(prompt|instructions)"
    r"|print (your|the) (system )?(prompt|instructions)"
    r"|repeat (everything|the text) above"
    r"|\bDAN mode\b"
    r"|act as (?:an? )?(?:unrestricted|jailbroken|uncensored))",
    re.IGNORECASE,
)

# A wall of repeated characters is a token-burn attempt, not a question.
REPETITION = re.compile(r"(.)\1{60,}")


@dataclass
class InputVerdict:
    ok: bool
    reason: str | None = None
    cleaned: str = ""


def validate_message(text: str) -> InputVerdict:
    settings = get_settings()
    stripped = text.strip()

    if not stripped:
        return InputVerdict(False, "empty")
    if len(stripped) > settings.max_message_chars:
        return InputVerdict(False, "message_too_long")
    if REPETITION.search(stripped):
        return InputVerdict(False, "spam")

    # Injection attempts are not blocked — that would break legitimate
    # questions containing the same words — but they are neutralised by being
    # marked as quoted user content, and flagged for monitoring.
    if PROMPT_INJECTION.search(stripped):
        return InputVerdict(True, "possible_injection", stripped)

    return InputVerdict(True, None, stripped)
