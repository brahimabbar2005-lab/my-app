"""Provider fallback chain: OpenRouter A → OpenRouter B → Workers AI.

Both providers run against mocked HTTP transports. The mocks route on URL,
so one handler can make OpenRouter answer 429 and Workers AI answer 200.
"""

from __future__ import annotations

import json
import re

import httpx
import pytest

from app.config import get_settings
from app.core import llm
from app.core.llm import ModelUnavailable
from app.core.providers import router as router_mod
from app.core.providers import workers_ai
from app.core.providers.base import ProviderHealth
from app.core.providers.router import get_router, parse_chain

MODEL_A = "vendor/model-a:free"
MODEL_B = "vendor/model-b:free"
CF_MODEL = "@cf/vendor/some-instruct-model"


@pytest.fixture
def chain(monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-or-test-key")
    monkeypatch.setenv("LLM_PROVIDER", "openrouter")
    monkeypatch.setenv("OPENROUTER_MODEL", MODEL_A)
    monkeypatch.setenv("OPENROUTER_FALLBACK_MODEL", MODEL_B)
    monkeypatch.setenv("CLOUDFLARE_ACCOUNT_ID", "acct123")
    monkeypatch.setenv("CLOUDFLARE_API_TOKEN", "cf-test-token")
    monkeypatch.setenv("WORKERS_AI_MODEL", CF_MODEL)
    monkeypatch.delenv("LLM_CHAIN", raising=False)
    get_settings.cache_clear()

    state = {"calls": [], "openrouter": {}, "workers": None}

    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content) if request.content else {}
        url = str(request.url)
        if "openrouter" in url:
            model = body["model"]
            state["calls"].append(f"openrouter:{model}")
            return state["openrouter"][model](body)
        state["calls"].append("workers_ai:" + url.split("/ai/run/")[1])
        state["auth"] = request.headers.get("authorization")
        return state["workers"](body)

    transport = httpx.MockTransport(handler)
    monkeypatch.setattr(llm, "_transport", transport)
    monkeypatch.setattr(workers_ai, "_transport", transport)
    yield state
    get_settings.cache_clear()


def or_ok(text):
    return lambda body: (
        httpx.Response(
            200,
            headers={"content-type": "text/event-stream"},
            content=(
                "data: " + json.dumps({"choices": [{"delta": {"content": text}}]}) + "\n\ndata: [DONE]\n\n"
            ).encode(),
        )
        if body.get("stream")
        else httpx.Response(
            200,
            json={
                "model": body["model"],
                "choices": [{"message": {"content": text}, "finish_reason": "stop"}],
                "usage": {"prompt_tokens": 10, "completion_tokens": 5},
            },
        )
    )


def status(code, message="nope"):
    return lambda body: httpx.Response(code, json={"error": {"message": message}})


def cf_ok(text):
    def respond(body):
        if body.get("stream"):
            events = (
                "".join(
                    "data: " + json.dumps({"response": piece}) + "\n\n"
                    for piece in re.findall(r"\S+\s*", text)
                )
                + "data: "
                + json.dumps({"response": "", "usage": {"prompt_tokens": 7, "completion_tokens": 3}})
                + "\n\ndata: [DONE]\n\n"
            )
            return httpx.Response(200, headers={"content-type": "text/event-stream"}, content=events.encode())
        return httpx.Response(
            200,
            json={
                "success": True,
                "errors": [],
                "result": {"response": text, "usage": {"prompt_tokens": 7, "completion_tokens": 3}},
            },
        )

    return respond


def cf_status(code, message):
    return lambda body: httpx.Response(
        code, json={"success": False, "errors": [{"code": 4006, "message": message}]}
    )


async def collect(gen):
    return [item async for item in gen]


# ------------------------------------------------------------------ chain
def test_default_chain_is_built_from_the_keys_that_are_set(chain):
    keys = [p.key for p in get_router().providers]
    assert keys == [f"openrouter:{MODEL_A}", f"openrouter:{MODEL_B}", f"workers_ai:{CF_MODEL}"]


def test_llm_chain_overrides_the_default_and_keeps_colons_in_model_ids(chain, monkeypatch):
    monkeypatch.setenv("LLM_CHAIN", f"workers_ai:{CF_MODEL}, openrouter:{MODEL_B}, bogus:x, openrouter")
    get_settings.cache_clear()
    keys = [p.key for p in get_router().providers]
    assert keys == [f"workers_ai:{CF_MODEL}", f"openrouter:{MODEL_B}"]


def test_workers_ai_is_left_out_without_a_configured_model(chain, monkeypatch):
    monkeypatch.delenv("WORKERS_AI_MODEL")
    get_settings.cache_clear()
    assert all(p.name != "workers_ai" for p in get_router().providers)


def test_unconfigured_providers_are_dropped(chain, monkeypatch):
    monkeypatch.setenv("CLOUDFLARE_API_TOKEN", "")
    monkeypatch.setenv("LLM_CHAIN", f"workers_ai:{CF_MODEL},openrouter:{MODEL_A}")
    get_settings.cache_clear()
    assert [p.key for p in get_router().providers] == [f"openrouter:{MODEL_A}"]


def test_parse_chain_ignores_malformed_entries():
    assert parse_chain(["", "nonsense", "openrouter:"]) == []


# ------------------------------------------------------------------ complete
async def test_first_provider_answers_when_healthy(chain):
    chain["openrouter"][MODEL_A] = or_ok("Fes first.")
    result = await llm.complete("sys", "Marrakech or Fes?")
    assert result.text == "Fes first."
    assert result.provider == "openrouter"
    assert chain["calls"] == [f"openrouter:{MODEL_A}"]


async def test_429_falls_through_to_the_second_free_model(chain):
    chain["openrouter"][MODEL_A] = status(429, "rate limited")
    chain["openrouter"][MODEL_B] = or_ok("Model B here.")
    result = await llm.complete("sys", "hi")
    assert result.text == "Model B here."
    assert chain["calls"] == [f"openrouter:{MODEL_A}", f"openrouter:{MODEL_B}"]


async def test_both_openrouter_models_down_reaches_workers_ai(chain):
    chain["openrouter"][MODEL_A] = status(429)
    chain["openrouter"][MODEL_B] = status(503, "upstream down")
    chain["workers"] = cf_ok("Workers AI answer.")
    result = await llm.complete("sys", "hi")
    assert result.text == "Workers AI answer."
    assert result.provider == "workers_ai"
    assert result.usage.total == 10
    assert chain["calls"][-1] == f"workers_ai:{CF_MODEL}"
    assert chain["auth"] == "Bearer cf-test-token"


async def test_a_rate_limited_provider_is_skipped_while_cooling_down(chain):
    chain["openrouter"][MODEL_A] = status(429)
    chain["openrouter"][MODEL_B] = or_ok("B")
    await llm.complete("sys", "one")
    chain["calls"].clear()
    await llm.complete("sys", "two")
    assert chain["calls"] == [f"openrouter:{MODEL_B}"], "model A should be in cooldown"
    health = {h["provider"]: h for h in get_router().snapshot()}
    assert health[f"openrouter:{MODEL_A}"]["failures_by_kind"] == {"rate_limit": 1}
    assert health[f"openrouter:{MODEL_A}"]["available"] is False


async def test_every_provider_failing_raises_one_combined_error(chain):
    chain["openrouter"][MODEL_A] = status(429)
    chain["openrouter"][MODEL_B] = status(401)
    chain["workers"] = cf_status(429, "you have used up your daily free allocation of 10,000 neurons")
    with pytest.raises(ModelUnavailable) as err:
        await llm.complete("sys", "hi")
    message = str(err.value)
    assert "all model providers failed" in message
    assert "rate_limit" in message and "auth" in message and "quota" in message


async def test_when_everything_is_cooling_down_the_soonest_is_still_tried(chain):
    chain["openrouter"][MODEL_A] = status(429)
    chain["openrouter"][MODEL_B] = status(429)
    chain["workers"] = cf_status(429, "daily free allocation used")
    with pytest.raises(ModelUnavailable):
        await llm.complete("sys", "hi")
    chain["calls"].clear()
    chain["openrouter"][MODEL_A] = or_ok("recovered")
    result = await llm.complete("sys", "again")
    assert len(chain["calls"]) == 1, "only the provider that recovers first is attempted"
    assert result.text == "recovered"


async def test_single_provider_errors_are_passed_through_unchanged(monkeypatch, chain):
    monkeypatch.delenv("OPENROUTER_FALLBACK_MODEL")
    monkeypatch.delenv("WORKERS_AI_MODEL")
    get_settings.cache_clear()
    chain["openrouter"][MODEL_A] = status(429)
    with pytest.raises(ModelUnavailable) as err:
        await llm.complete("sys", "hi")
    assert "rate limit reached (429)" in str(err.value)
    assert err.value.kind == "rate_limit"


async def test_utility_model_override_applies_to_the_primary_provider_only(chain):
    chain["openrouter"]["vendor/utility:free"] = status(429)
    chain["openrouter"][MODEL_B] = or_ok('{"intent": "transport"}')
    data = await llm.complete_json("classify", "train to Fes?", model="vendor/utility:free")
    assert data == {"intent": "transport"}
    assert chain["calls"] == ["openrouter:vendor/utility:free", f"openrouter:{MODEL_B}"]


# ------------------------------------------------------------------ stream
async def test_stream_falls_back_before_the_first_token(chain):
    chain["openrouter"][MODEL_A] = status(429)
    chain["openrouter"][MODEL_B] = status(500)
    chain["workers"] = cf_ok("Take the train")
    items = await collect(llm.stream("sys", "hi"))
    text = "".join(v for k, v in items if k == "delta")
    assert text == "Take the train"
    assert items[-1][0] == "usage" and items[-1][1].total == 10


async def test_stream_does_not_switch_provider_after_text_was_sent(chain, monkeypatch):
    shown = "Marrakech is a good first stop: compact medina, easy day trips, and plenty of riads. " * 2

    async def broken_after_first_token(self, *args, **kwargs):
        yield "delta", shown  # longer than the probe, so it reaches the traveller
        raise ModelUnavailable("connection dropped", kind="network")

    from app.core.providers.hosted import OpenRouterProvider

    monkeypatch.setattr(OpenRouterProvider, "stream", broken_after_first_token)
    chain["workers"] = cf_ok("should never be used")
    gen = llm.stream("sys", "hi")
    first = await gen.__anext__()
    assert first == ("delta", shown)
    with pytest.raises(ModelUnavailable):
        await gen.__anext__()
    assert not any(c.startswith("workers_ai") for c in chain["calls"])


async def test_workers_ai_stream_strips_split_think_blocks(chain, monkeypatch):
    monkeypatch.setenv("LLM_CHAIN", f"workers_ai:{CF_MODEL}")
    get_settings.cache_clear()

    def respond(body):
        pieces = ["<thi", "nk>secret plan</th", "ink>Hello ", "trav", "eller"]
        events = "".join("data: " + json.dumps({"response": p}) + "\n\n" for p in pieces) + "data: [DONE]\n\n"
        return httpx.Response(200, headers={"content-type": "text/event-stream"}, content=events.encode())

    chain["workers"] = respond
    items = await collect(llm.stream("sys", "hi"))
    text = "".join(v for k, v in items if k == "delta")
    assert text == "Hello traveller"
    assert "secret" not in text


async def test_workers_ai_accepts_openai_style_results(chain, monkeypatch):
    monkeypatch.setenv("LLM_CHAIN", f"workers_ai:{CF_MODEL}")
    get_settings.cache_clear()
    chain["workers"] = lambda body: httpx.Response(
        200,
        json={
            "success": True,
            "result": {
                "choices": [{"message": {"content": "OpenAI-shaped"}}],
                "usage": {"prompt_tokens": 1, "completion_tokens": 2},
            },
        },
    )
    result = await llm.complete("sys", "hi")
    assert result.text == "OpenAI-shaped"


async def test_workers_ai_daily_allocation_is_classified_as_quota(chain, monkeypatch):
    monkeypatch.setenv("LLM_CHAIN", f"workers_ai:{CF_MODEL}")
    get_settings.cache_clear()
    chain["workers"] = cf_status(429, "you have used up your daily free allocation of 10,000 neurons")
    with pytest.raises(ModelUnavailable) as err:
        await llm.complete("sys", "hi")
    assert err.value.kind == "quota"


# ------------------------------------------------------------------ health
def test_cooldown_grows_with_consecutive_failures_and_resets_on_success():
    health = ProviderHealth("x:y")
    health.record_failure("rate_limit", "429")
    first = health.cooldown_until
    health.record_failure("rate_limit", "429")
    assert health.cooldown_until > first
    health.record_success(120, 10, 5)
    assert health.available() and health.consecutive_failures == 0
    assert health.snapshot()["output_tokens"] == 5


def test_router_is_rebuilt_when_settings_change(chain, monkeypatch):
    first = get_router()
    assert get_router() is first
    get_settings.cache_clear()
    assert get_router() is not first
    assert router_mod._router_settings is get_settings()


async def test_default_answer_model_is_not_forced_onto_a_different_primary_provider(chain, monkeypatch):
    """Found in the first live run: with Workers AI first in LLM_CHAIN, the
    OpenRouter answer model was sent to Cloudflare."""
    monkeypatch.setenv("LLM_CHAIN", f"workers_ai:{CF_MODEL},openrouter:{MODEL_A}")
    get_settings.cache_clear()
    chain["workers"] = cf_ok("from workers")
    result = await llm.complete("sys", "hi")
    assert result.text == "from workers"
    assert chain["calls"] == [f"workers_ai:{CF_MODEL}"]
    chain["workers"] = cf_ok('{"intent": "desert"}')
    data = await llm.complete_json("sys", "hi")  # the utility model is an OpenRouter id too
    assert data == {"intent": "desert"}
    assert chain["calls"][-1] == f"workers_ai:{CF_MODEL}"


@pytest.mark.parametrize(
    "effort,expected_reasoning,headroom",
    [
        ("off", {"enabled": False}, False),
        ("low", {"effort": "low", "exclude": True}, True),
        ("none", None, False),
    ],
)
def test_reasoning_setting_is_sent_as_configured(monkeypatch, effort, expected_reasoning, headroom):
    monkeypatch.setenv("OPENROUTER_API_KEY", "k")
    monkeypatch.setenv("LLM_PROVIDER", "openrouter")
    monkeypatch.setenv("OPENROUTER_REASONING_EFFORT", effort)
    get_settings.cache_clear()
    payload = llm._openrouter_payload(
        "sys", [{"role": "user", "content": "hi"}], "m:free", 100, 0.5, stream=False
    )
    assert payload.get("reasoning") == expected_reasoning
    assert payload["max_tokens"] == (100 + llm.REASONING_HEADROOM if headroom else 100)
    get_settings.cache_clear()


async def test_a_failure_before_anything_was_shown_still_falls_through(chain, monkeypatch):
    async def breaks_early(self, *args, **kwargs):
        yield "delta", "Half an ans"  # still inside the probe, never shown
        raise ModelUnavailable("connection dropped", kind="network")

    from app.core.providers.hosted import OpenRouterProvider

    monkeypatch.setattr(OpenRouterProvider, "stream", breaks_early)
    chain["workers"] = cf_ok("Take the train to Fes.")
    items = await collect(llm.stream("sys", "hi"))
    assert "".join(v for k, v in items if k == "delta") == "Take the train to Fes."


@pytest.mark.parametrize(
    "garbage",
    ["Si vous cherchez où résellsellsells fromells réserver", "À Fès, comptez 2 jours【重要特rows(matrix"],
)
async def test_garbled_output_is_never_shown_and_the_next_provider_answers(chain, monkeypatch, garbage):
    async def garbled(self, *args, **kwargs):
        yield "delta", garbage

    from app.core.providers.hosted import OpenRouterProvider

    monkeypatch.setattr(OpenRouterProvider, "stream", garbled)
    chain["workers"] = cf_ok("Deux à trois jours suffisent.")
    items = await collect(llm.stream("sys", "hi"))
    text = "".join(v for k, v in items if k == "delta")
    assert text == "Deux à trois jours suffisent."
    kinds = {h["provider"]: h["failures_by_kind"] for h in get_router().snapshot()}
    assert kinds[f"openrouter:{MODEL_A}"] == {"garbled": 1}


async def test_a_provider_that_does_not_start_in_time_is_skipped(chain, monkeypatch):
    import asyncio

    monkeypatch.setenv("LLM_FIRST_TOKEN_TIMEOUT", "0.05")
    get_settings.cache_clear()

    async def slow(self, *args, **kwargs):
        await asyncio.sleep(5)
        yield "delta", "too late"

    from app.core.providers.hosted import OpenRouterProvider

    monkeypatch.setattr(OpenRouterProvider, "stream", slow)
    chain["workers"] = cf_ok("Fast answer.")
    items = await collect(llm.stream("sys", "hi"))
    assert "".join(v for k, v in items if k == "delta") == "Fast answer."
    health = {h["provider"]: h for h in get_router().snapshot()}
    assert health[f"openrouter:{MODEL_A}"]["failures_by_kind"] == {"timeout": 1}


async def test_non_streaming_answers_are_checked_for_garbage_too(chain):
    chain["openrouter"][MODEL_A] = or_ok("réservellsellsells in in in")
    chain["openrouter"][MODEL_B] = or_ok("A clean answer.")
    result = await llm.complete("sys", "hi")
    assert result.text == "A clean answer."


def test_arabic_and_accented_answers_are_not_mistaken_for_garbage():
    from app.core.providers.router import looks_garbled

    assert not looks_garbled("أكبر مدينة عتيقة مأهولة في العالم، خصص لها ثلاثة أيام.")
    assert not looks_garbled("Comptez 2 à 3 jours à Fès : médina, tanneries, Al Quaraouiyine.")
    assert not looks_garbled("Mississippi-style? No — Marrakech, 3–4 days, then Essaouira.")
