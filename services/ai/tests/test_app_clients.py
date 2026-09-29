"""Mobile-app access: the app key, signed-in callers, and their rate limits."""

from __future__ import annotations

import time

import jwt
import pytest
from fastapi import HTTPException

from app.api.deps import require_widget_key
from app.config import get_settings
from app.infra import ratelimit
from app.infra.auth import GUEST, caller_from_authorization

SECRET = "test-jwt-secret-at-least-32-bytes-long!!"


def token(sub="user-123", aud="authenticated", exp_in=3600, secret=SECRET):
    claims = {"sub": sub, "aud": aud, "exp": int(time.time()) + exp_in, "role": "authenticated"}
    return jwt.encode(claims, secret, algorithm="HS256")


@pytest.fixture
def supabase_secret(monkeypatch):
    monkeypatch.setenv("SUPABASE_JWT_SECRET", SECRET)
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


# ------------------------------------------------------------------ keys
@pytest.fixture
def keys(monkeypatch):
    monkeypatch.setenv("WIDGET_KEY", "widget-k")
    monkeypatch.setenv("APP_KEY", "app-k")
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def test_widget_key_is_still_accepted(keys):
    require_widget_key(x_widget_key="widget-k", x_app_key=None)


def test_app_key_is_accepted(keys):
    require_widget_key(x_widget_key=None, x_app_key="app-k")


def test_wrong_or_missing_key_is_rejected(keys):
    for widget, app in [(None, None), ("nope", None), (None, "nope")]:
        with pytest.raises(HTTPException) as err:
            require_widget_key(x_widget_key=widget, x_app_key=app)
        assert err.value.status_code == 401


def test_no_keys_configured_means_open_in_development(monkeypatch):
    monkeypatch.delenv("WIDGET_KEY", raising=False)
    monkeypatch.delenv("APP_KEY", raising=False)
    get_settings.cache_clear()
    require_widget_key(x_widget_key=None, x_app_key=None)
    get_settings.cache_clear()


# ------------------------------------------------------------------ auth
def test_no_header_is_a_guest():
    assert caller_from_authorization(None) is GUEST
    assert caller_from_authorization("Basic abc") is GUEST


def test_valid_supabase_token_identifies_the_user(supabase_secret):
    caller = caller_from_authorization(f"Bearer {token()}")
    assert caller.signed_in and caller.user_id == "user-123"


@pytest.mark.parametrize(
    "bad",
    [
        token(exp_in=-10),  # expired
        token(aud="anon"),  # wrong audience
        token(secret="another-secret-that-is-also-32-bytes!!"),  # forged
        "not-a-jwt",
    ],
)
def test_invalid_tokens_fall_back_to_guest(supabase_secret, bad):
    assert caller_from_authorization(f"Bearer {bad}") is GUEST


def test_token_without_verification_config_is_a_guest(monkeypatch):
    monkeypatch.delenv("SUPABASE_JWT_SECRET", raising=False)
    monkeypatch.delenv("SUPABASE_URL", raising=False)
    get_settings.cache_clear()
    assert caller_from_authorization(f"Bearer {token()}") is GUEST
    get_settings.cache_clear()


# ------------------------------------------------------------------ limits
@pytest.fixture
def small_limits(monkeypatch):
    monkeypatch.setenv("RATE_LIMIT_PER_MINUTE", "2")
    monkeypatch.setenv("RATE_LIMIT_PER_DAY", "100")
    monkeypatch.setenv("SIGNED_IN_RATE_MULTIPLIER", "3")
    get_settings.cache_clear()
    monkeypatch.setattr(ratelimit, "_limiter", ratelimit.SlidingWindowLimiter())
    yield
    get_settings.cache_clear()


def test_guests_hit_the_guest_limit(small_limits):
    results = [ratelimit.check_rate("guest-session").allowed for _ in range(3)]
    assert results == [True, True, False]


def test_signed_in_users_get_a_higher_limit(small_limits):
    results = [ratelimit.check_rate("s", user_id="u1").allowed for _ in range(7)]
    assert results == [True] * 6 + [False]


def test_signed_in_limit_follows_the_account_across_sessions(small_limits):
    for i in range(6):
        assert ratelimit.check_rate(f"rotating-{i}", user_id="u2").allowed
    assert not ratelimit.check_rate("fresh-session", user_id="u2").allowed
