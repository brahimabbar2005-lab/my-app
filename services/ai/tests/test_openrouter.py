"""OpenRouter provider, tested against a mocked HTTP transport.

These reproduce OpenRouter's wire format — including the parts that break
naive clients: ": OPENROUTER PROCESSING" keep-alive comments in the stream,
upstream failures returned with HTTP 200 and an error body, and reasoning
text a model may inline in <think> tags, possibly split across chunks.

No request reaches the real API. The first real call happens with
`python scripts/check_model.py`.
"""
from __future__ import annotations

import json

import httpx
import pytest

from app.config import get_settings
from app.core import llm


@pytest.fixture
def openrouter(monkeypatch):
    """Switch to OpenRouter with a mocked transport; record every request."""
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-or-test-key")
    monkeypatch.setenv("LLM_PROVIDER", "openrouter")
    monkeypatch.setenv("OPENROUTER_MODEL", "nvidia/nemotron-3.5-lightning:free")
    get_settings.cache_clear()

    state = {"requests": [], "responder": None}

    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content) if request.content else {}
        state["requests"].append({"url": str(request.url), "headers": request.headers, "body": body})
        return state["responder"](request, body)

    monkeypatch.setattr(llm, "_transport", httpx.MockTransport(handler))
    yield state
    get_settings.cache_clear()


def reply(text: str, **extra):
    def responder(request, body):
        return httpx.Response(200, json={
            "model": body["model"],
            "choices": [{"message": {"role": "assistant", "content": text}, "finish_reason": "stop"}],
            "usage": {"prompt_tokens": 120, "completion_tokens": 30},
            **extra,
        })
    return responder


def sse(*events: str):
    def responder(request, body):
        return httpx.Response(200, headers={"content-type": "text/event-stream"},
                              content="".join(events).encode())
    return responder


def chunk(text: str) -> str:
    return "data: " + json.dumps({"choices": [{"delta": {"content": text}}]}) + "\n\n"


# ---------------------------------------------------------------- settings
def test_openrouter_is_chosen_when_it_is_the_only_key(monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-or-x")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "")
    monkeypatch.setenv("LLM_PROVIDER", "")
    from app.config import load_settings

    settings = load_settings()
    assert settings.llm_provider == "openrouter"
    assert settings.active_answer_model == "nvidia/nemotron-3.5-lightning:free"


def test_free_models_default_to_one_call_per_question(monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-or-x")
    monkeypatch.setenv("LLM_PROVIDER", "openrouter")
    monkeypatch.setenv("OPENROUTER_MODEL", "nvidia/nemotron-3.5-lightning:free")
    monkeypatch.delenv("QUALITY_CHECK_ENABLED", raising=False)
    monkeypatch.delenv("MODEL_CLASSIFICATION_ENABLED", raising=False)
    from app.config import load_settings

    settings = load_settings()
    assert settings.on_free_tier
    assert settings.model_classification_enabled is False
    assert settings.quality_check_enabled is False


def test_free_tier_defaults_can_be_overridden(monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-or-x")
    monkeypatch.setenv("LLM_PROVIDER", "openrouter")
    monkeypatch.setenv("QUALITY_CHECK_ENABLED", "true")
    from app.config import load_settings

    assert load_settings().quality_check_enabled is True


# -------------------------------------------------------------- completion
async def test_request_is_well_formed(openrouter):
    openrouter["responder"] = reply("Two nights in Merzouga is the usual sweet spot.")
    result = await llm.complete("You are a Morocco travel assistant.", "How long in Merzouga?")

    assert result.text == "Two nights in Merzouga is the usual sweet spot."
    request = openrouter["requests"][0]
    assert request["url"].endswith("/api/v1/chat/completions")
    assert request["headers"]["authorization"] == "Bearer sk-or-test-key"
    body = request["body"]
    assert body["model"] == "nvidia/nemotron-3.5-lightning:free"
    assert body["messages"][0] == {"role": "system", "content": "You are a Morocco travel assistant."}
    assert body["messages"][-1]["role"] == "user"
    # Reasoning is kept short and out of the response, with headroom so it
    # cannot consume the whole answer budget.
    assert body["reasoning"] == {"effort": "low", "exclude": True}
    assert body["max_tokens"] > get_settings().max_answer_tokens


async def test_inline_reasoning_is_removed(openrouter):
    openrouter["responder"] = reply("<think>They asked about Fes... medina...</think>Fes rewards a slower pace.")
    result = await llm.complete("system", "Is Fes worth it?")
    assert result.text == "Fes rewards a slower pace."


async def test_an_answer_cut_off_mid_reasoning_is_treated_as_a_failure(openrouter):
    openrouter["responder"] = reply("<think>Let me consider the route from Marrakech and")
    with pytest.raises(llm.ModelUnavailable):
        await llm.complete("system", "question")


async def test_empty_answer_is_a_failure_not_a_blank_reply(openrouter):
    openrouter["responder"] = reply("")
    with pytest.raises(llm.ModelUnavailable, match="empty"):
        await llm.complete("system", "question")


async def test_rate_limit_is_explained(openrouter):
    openrouter["responder"] = lambda r, b: httpx.Response(
        429, json={"error": {"message": "Rate limit exceeded: free-models-per-day"}}
    )
    with pytest.raises(llm.ModelUnavailable, match="50 a day"):
        await llm.complete("system", "question")


async def test_bad_key_is_explained(openrouter):
    openrouter["responder"] = lambda r, b: httpx.Response(401, json={"error": {"message": "No auth"}})
    with pytest.raises(llm.ModelUnavailable, match="OPENROUTER_API_KEY"):
        await llm.complete("system", "question")


async def test_upstream_error_inside_a_200_is_caught(openrouter):
    openrouter["responder"] = lambda r, b: httpx.Response(
        200, json={"error": {"message": "Provider returned error", "code": 502}}
    )
    with pytest.raises(llm.ModelUnavailable, match="Provider returned error"):
        await llm.complete("system", "question")


async def test_json_is_recovered_from_prose(openrouter):
    """This model does not support enforced JSON output."""
    openrouter["responder"] = reply(
        'Sure, here it is:\n```json\n{"intents": ["DESERT"], "complexity": "simple"}\n```'
    )
    data = await llm.complete_json("classify", "Sahara?")
    assert data == {"intents": ["DESERT"], "complexity": "simple"}


# --------------------------------------------------------------- streaming
async def collect(**kwargs):
    text, usage = [], None
    async for kind, payload in llm.stream("system", "question", **kwargs):
        if kind == "delta":
            text.append(payload)
        else:
            usage = payload
    return "".join(text), usage


async def test_stream_ignores_keepalive_comments(openrouter):
    openrouter["responder"] = sse(
        ": OPENROUTER PROCESSING\n\n",
        chunk("Take the train"),
        ": OPENROUTER PROCESSING\n\n",
        chunk(" to Fes."),
        "data: " + json.dumps({"choices": [], "usage": {"prompt_tokens": 90, "completion_tokens": 6}}) + "\n\n",
        "data: [DONE]\n\n",
    )
    text, usage = await collect()
    assert text == "Take the train to Fes."
    assert usage.input_tokens == 90 and usage.output_tokens == 6


async def test_stream_never_shows_reasoning_even_when_tags_are_split(openrouter):
    openrouter["responder"] = sse(
        chunk("<thi"),
        chunk("nk>The user wants Fes. Maybe mention the "),
        chunk("medina.</th"),
        chunk("ink>Fes is best"),
        chunk(" on foot."),
        "data: [DONE]\n\n",
    )
    text, _ = await collect()
    assert text == "Fes is best on foot."
    assert "medina" not in text and "think" not in text


async def test_stream_keeps_a_genuine_less_than_sign(openrouter):
    openrouter["responder"] = sse(chunk("It is < 3 hours"), chunk(" by train."), "data: [DONE]\n\n")
    text, _ = await collect()
    assert text == "It is < 3 hours by train."


async def test_stream_error_status_is_explained(openrouter):
    openrouter["responder"] = lambda r, b: httpx.Response(429, json={"error": {"message": "slow down"}})
    with pytest.raises(llm.ModelUnavailable, match="rate limit"):
        await collect()


async def test_stream_with_no_text_is_a_failure(openrouter):
    openrouter["responder"] = sse(chunk("<think>only thinking, never answering"), "data: [DONE]\n\n")
    with pytest.raises(llm.ModelUnavailable):
        await collect()


# --------------------------------------------------- the whole pipeline
async def test_a_question_costs_one_request_on_the_free_tier(openrouter):
    """The point of the free-tier defaults: 50 requests a day means ~50
    questions, not ~12."""
    from app.core.orchestrator import Orchestrator

    openrouter["responder"] = reply(
        "Honestly, for a first trip I'd start with Marrakech — easier to navigate, "
        "and a natural base for the desert."
    )
    result = await Orchestrator().answer("Marrakech or Fes for a first trip?")

    assert len(openrouter["requests"]) == 1
    assert result.answer.startswith("Honestly, for a first trip")
    # Retrieval and link selection still run — they never needed the model.
    assert result.resources


async def test_a_failed_request_still_returns_the_useful_parts(openrouter):
    from app.core.orchestrator import Orchestrator

    openrouter["responder"] = lambda r, b: httpx.Response(429, json={"error": {"message": "limit"}})
    result = await Orchestrator().answer("How many days do I need in Marrakech?")

    assert "try again" in result.answer.lower()
    assert result.resources, "the fallback should still carry the matching guide"
    assert len(openrouter["requests"]) == 1, "a failure must not be retried into the daily quota"
