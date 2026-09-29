#!/usr/bin/env python3
"""Make one real request to the configured model, and report what happened.

    python scripts/check_model.py

Uses a single request — on a free OpenRouter model, one of your 50 a day.
Run it once after putting a key in .env, before starting the server, so a
wrong key or model name shows up here with a clear message rather than as a
fallback reply in the widget.
"""
from __future__ import annotations

import asyncio
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.config import get_settings  # noqa: E402
from app.core import llm  # noqa: E402
from app.core.orchestrator import Orchestrator  # noqa: E402


async def main() -> int:
    settings = get_settings()
    if not settings.model_key:
        print("No model key found. Add OPENROUTER_API_KEY=... (or ANTHROPIC_API_KEY=...) to .env")
        return 1

    calls = 1 + (2 if settings.model_classification_enabled else 0) + (1 if settings.quality_check_enabled else 0)
    print(f"provider   {settings.llm_provider}")
    print(f"model      {settings.active_answer_model}")
    print(f"calls/question  {calls}" + ("   (free tier: optional calls off)" if settings.on_free_tier else ""))
    print()

    question = "Marrakech or Fes for a first trip?"
    print(f"Q: {question}\n")
    started = time.perf_counter()
    result = await Orchestrator().answer(question)
    elapsed = time.perf_counter() - started

    if result.debug.get("error"):
        print("The model could not be reached:\n")
        print(f"  {result.debug['error']}\n")
        return 1

    print(result.answer)
    print()
    for resource in result.resources:
        print(f"  [link] {resource.title}")
    print(f"\n{elapsed:.1f}s  ·  {result.usage.input_tokens} tokens in, {result.usage.output_tokens} out")

    issues = [i for i in result.quality_issues if i.get("severity") == "major"]
    if issues:
        print("\nThe output scan flagged:")
        for issue in issues:
            print(f"  - {issue['detail']}")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
