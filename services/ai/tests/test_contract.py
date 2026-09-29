"""The shared API contract, from the Python side.

packages/shared/contracts/v1/examples holds real payloads produced by this
service (scripts/export_contract_examples.py). The TypeScript zod schemas
parse the same files (packages/shared/test/contract.test.ts). If a Pydantic
model changes shape, this test or the TS test fails until both agree.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.schemas import AffiliateCard, ChatResponse, ResourceCard, TripState

EXAMPLES = Path(__file__).resolve().parents[3] / "packages" / "shared" / "contracts" / "v1" / "examples"

pytestmark = pytest.mark.skipif(not EXAMPLES.exists(), reason="shared contract examples not present")


@pytest.mark.parametrize("name", ["chat_response.commercial.json", "chat_response.advice.json"])
def test_chat_response_examples_match_the_model(name):
    payload = json.loads((EXAMPLES / name).read_text())
    parsed = ChatResponse.model_validate(payload)
    assert parsed.model_dump(mode="json").keys() == payload.keys()


def test_stream_example_follows_meta_delta_done():
    blocks = (EXAMPLES / "chat_stream.commercial.sse").read_text().strip().split("\n\n")
    events = []
    for block in blocks:
        lines = dict(line.split(": ", 1) for line in block.split("\n"))
        events.append((lines["event"], json.loads(lines["data"])))
    kinds = [kind for kind, _ in events]
    assert kinds[0] == "meta" and kinds[-1] == "done"
    assert set(kinds[1:-1]) == {"delta"}

    meta = events[0][1]
    for card in meta["resources"]:
        ResourceCard.model_validate(card)
    for card in meta["affiliates"]:
        AffiliateCard.model_validate(card)
    assert meta["affiliates"], "the commercial example should exercise affiliate cards"
    TripState.from_dict(meta["trip_state"])

    done = events[-1][1]
    assert {"conversation_id", "message_id", "latency_ms", "trip_state"} <= done.keys()


def test_trip_state_fields_are_all_known_to_the_shared_schema():
    """Every TripState field must be listed in packages/shared chat.ts."""
    ts_source = (EXAMPLES.parents[2] / "src" / "api" / "v1" / "chat.ts").read_text()
    block = ts_source.split("export const TripState = z.object({", 1)[1].split("});", 1)[0]
    missing = [f for f in TripState.__dataclass_fields__ if f"{f}:" not in block]
    assert not missing, f"TripState fields missing from the zod schema: {missing}"
