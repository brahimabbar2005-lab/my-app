"""Test isolation.

All provider keys are blanked, so a real OpenRouter, Anthropic or Cloudflare
key in .env is never used by the test suite.

The app now reads .env at import time, so a developer who has put a real key
in .env would otherwise have every test run call the model — slow, billed,
and non-deterministic. Setting the variable to empty here, before anything
imports the app, wins over the file (load_dotenv never overrides a variable
that is already set).
"""
import os

os.environ["ANTHROPIC_API_KEY"] = ""
os.environ["OPENROUTER_API_KEY"] = ""
os.environ["LLM_PROVIDER"] = ""
# The fallback chain and app access settings too: a developer's real
# Cloudflare credentials in .env would otherwise add a live Workers AI
# provider to every test's chain. Tests that need them set them explicitly.
for name in (
    "LLM_CHAIN", "OPENROUTER_FALLBACK_MODEL", "CLOUDFLARE_ACCOUNT_ID", "CLOUDFLARE_API_TOKEN",
    "WORKERS_AI_MODEL", "APP_KEY", "SUPABASE_URL", "SUPABASE_JWT_SECRET",
):
    os.environ[name] = ""
os.environ.setdefault("ENVIRONMENT", "test")
