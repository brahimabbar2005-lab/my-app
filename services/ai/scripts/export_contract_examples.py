#!/usr/bin/env python3
"""Write real API payloads to packages/shared/contracts/v1/examples.

    python scripts/export_contract_examples.py          # write
    python scripts/export_contract_examples.py --check  # fail if they changed

The TypeScript contract tests parse these files with the zod schemas, and
tests/test_contract.py parses them with the Pydantic models. Both sides agree
on one set of real payloads, so a contract change on either side fails CI
until the other side is updated.

Runs without a model key: retrieval, links and affiliates are computed before
generation, and the answer is the service's own fallback text. Volatile values
(ids, latency) are normalised so the files only change when the shape does.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT.parents[1] / "packages" / "shared" / "contracts" / "v1" / "examples"
sys.path.insert(0, str(ROOT))

UUIDISH = re.compile(r"\b[0-9a-f]{8,}(?:-[0-9a-f]{4,}){0,4}\b")


def normalise(value):
    if isinstance(value, dict):
        out = {}
        for k, v in value.items():
            if k in {"latency_ms"}:
                out[k] = 0
            elif k in {"session_id", "conversation_id", "message_id"} and isinstance(v, str):
                out[k] = f"<{k}>"
            else:
                out[k] = normalise(v)
        return out
    if isinstance(value, list):
        return [normalise(v) for v in value]
    return value


def normalise_sse(text: str) -> str:
    blocks = []
    for block in text.strip().split("\n\n"):
        lines = []
        for line in block.split("\n"):
            if line.startswith("data: "):
                payload = normalise(json.loads(line[6:]))
                line = "data: " + json.dumps(payload, ensure_ascii=False, sort_keys=True)
            lines.append(line)
        blocks.append("\n".join(lines))
    return "\n\n".join(blocks) + "\n\n"


def generate() -> dict[str, str]:
    handle, db = tempfile.mkstemp(suffix=".db")
    os.close(handle)
    for key in ("ANTHROPIC_API_KEY", "OPENROUTER_API_KEY", "LLM_PROVIDER", "LLM_CHAIN",
                "CLOUDFLARE_API_TOKEN", "WORKERS_AI_MODEL", "OPENROUTER_FALLBACK_MODEL",
                "WIDGET_KEY", "APP_KEY"):
        os.environ[key] = ""
    os.environ["DATABASE_URL"] = f"sqlite:///{db}"
    os.environ["ENVIRONMENT"] = "test"

    from fastapi.testclient import TestClient

    from app.main import app

    files: dict[str, str] = {}
    with TestClient(app) as client:
        commercial = {"message": "Where can I book a desert tour from Marrakech to Merzouga?", "locale": "en"}
        response = client.post("/api/chat", json=commercial)
        response.raise_for_status()
        files["chat_response.commercial.json"] = json.dumps(normalise(response.json()), indent=2,
                                                            ensure_ascii=False, sort_keys=True) + "\n"

        advice = {"message": "Marrakech or Fes for a first trip? We have 5 days in April.", "locale": "en"}
        response = client.post("/api/chat", json=advice)
        response.raise_for_status()
        files["chat_response.advice.json"] = json.dumps(normalise(response.json()), indent=2,
                                                        ensure_ascii=False, sort_keys=True) + "\n"

        response = client.post("/api/chat/stream", json=commercial)
        response.raise_for_status()
        files["chat_stream.commercial.sse"] = normalise_sse(response.text)

        response = client.post("/api/chat", json={"message": "   "})
        files["chat_error.validation.json"] = json.dumps({"status": response.status_code}, indent=2) + "\n"

    os.unlink(db)
    return files


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    files = generate()
    OUT.mkdir(parents=True, exist_ok=True)
    stale = []
    for name, content in files.items():
        path = OUT / name
        if args.check:
            if not path.exists() or path.read_text() != content:
                stale.append(name)
        else:
            path.write_text(content)
            print(f"wrote {path.relative_to(ROOT.parents[1])}")
    if stale:
        print("contract examples are out of date: " + ", ".join(stale))
        print("run: python scripts/export_contract_examples.py")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
