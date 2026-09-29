"""Configuration regressions.

Both of these broke a real first-time setup: `cp .env.example .env` produced
an empty DATABASE_URL that crashed startup, and settings were frozen at import
so nothing could override them afterwards.
"""
import os

from app.config import get_settings, load_settings


def test_blank_values_fall_back_to_defaults(monkeypatch):
    # Exactly what `cp .env.example .env` produces.
    monkeypatch.setenv("DATABASE_URL", "")
    monkeypatch.setenv("RATE_LIMIT_PER_MINUTE", "   ")
    monkeypatch.setenv("WIDGET_KEY", "")
    settings = load_settings()
    assert settings.database_url.startswith("sqlite:///")
    assert settings.rate_limit_per_minute == 8
    assert settings.widget_key is None


def test_settings_are_read_at_load_time_not_import_time(monkeypatch):
    monkeypatch.setenv("RATE_LIMIT_PER_MINUTE", "3")
    get_settings.cache_clear()
    try:
        assert get_settings().rate_limit_per_minute == 3
    finally:
        monkeypatch.delenv("RATE_LIMIT_PER_MINUTE")
        get_settings.cache_clear()


def test_env_example_is_safe_to_copy_verbatim(tmp_path, monkeypatch):
    """Load every line of .env.example as-is and make sure the app still builds
    a usable configuration from it."""
    from pathlib import Path

    example = Path(__file__).resolve().parents[1] / ".env.example"
    for line in example.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        monkeypatch.setenv(key.strip(), value.strip())

    settings = load_settings()
    assert settings.database_url
    assert settings.answer_model
    assert settings.rate_limit_per_minute > 0
    assert settings.live_data_enabled is False


def test_no_key_means_fallback_not_crash(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "")
    assert load_settings().anthropic_api_key is None
