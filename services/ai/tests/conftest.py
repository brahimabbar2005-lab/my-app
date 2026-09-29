"""Test isolation.

Both provider keys are blanked, so a real OpenRouter or Anthropic key in .env
is never used by the test suite.

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
os.environ.setdefault("ENVIRONMENT", "test")
