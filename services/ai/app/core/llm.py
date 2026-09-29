"""Model access: the one place that talks to a model provider.

Providers sit behind the same three functions — `complete`, `stream`,
`complete_json` — so nothing else in the app knows which one is in use:

  anthropic    the Anthropic SDK
  openrouter   OpenRouter's OpenAI-compatible HTTP API, called with httpx
  workers_ai   Cloudflare Workers AI (app/core/providers/workers_ai.py)

Which provider answers is decided by app/core/providers/router.py, which
walks the configured fallback chain.

OpenRouter is called directly rather than through the OpenAI SDK: httpx is
already a dependency, and the request is small enough that a second SDK would
add more surface than it saves.
"""
from __future__ import annotations

import asyncio
import json
import logging
import re
from dataclasses import dataclass, field
from typing import Any, AsyncIterator

import httpx

from app.config import get_settings

log = logging.getLogger(__name__)


class ModelUnavailable(RuntimeError):
    """Raised when the model cannot be reached. Callers show a fallback.

    `kind` tells the provider router how to treat the failure:
    rate_limit | quota | auth | timeout | network | provider_error | empty | config.
    """

    def __init__(self, message: str, *, kind: str = "provider_error", status: int | None = None):
        super().__init__(message)
        self.kind = kind
        self.status = status


def _kind_for_http_error(exc: httpx.HTTPError) -> str:
    return "timeout" if isinstance(exc, httpx.TimeoutException) else "network"


@dataclass
class Usage:
    input_tokens: int = 0
    output_tokens: int = 0

    def add(self, other: "Usage") -> None:
        self.input_tokens += other.input_tokens
        self.output_tokens += other.output_tokens

    @property
    def total(self) -> int:
        return self.input_tokens + self.output_tokens


@dataclass
class Completion:
    text: str
    usage: Usage = field(default_factory=Usage)
    model: str = ""
    stop_reason: str | None = None
    provider: str = ""


# Reasoning models sometimes put their thinking inline instead of in a separate
# field. It must never reach a traveller.
THINK_BLOCK = re.compile(r"<think(?:ing)?>.*?</think(?:ing)?>", re.DOTALL | re.IGNORECASE)
THINK_OPEN = re.compile(r"<think(?:ing)?>.*\Z", re.DOTALL | re.IGNORECASE)


def strip_reasoning(text: str) -> str:
    text = THINK_BLOCK.sub("", text)
    # An unterminated block means the budget ran out mid-thought.
    text = THINK_OPEN.sub("", text)
    return text.strip()


def _messages(history: list[dict[str, str]], message: str) -> list[dict[str, Any]]:
    """History as strictly alternating user/assistant turns ending on user."""
    settings = get_settings()
    trimmed = history[-settings.max_history_turns :] if history else []
    out: list[dict[str, Any]] = []
    for entry in trimmed:
        role = entry.get("role")
        content = (entry.get("content") or "").strip()
        if role not in {"user", "assistant"} or not content:
            continue
        if out and out[-1]["role"] == role:
            out[-1]["content"] += "\n\n" + content
        else:
            out.append({"role": role, "content": content})
    while out and out[0]["role"] != "user":
        out.pop(0)
    if out and out[-1]["role"] == "user":
        out[-1]["content"] += "\n\n" + message
    else:
        out.append({"role": "user", "content": message})
    return out


def available() -> bool:
    from app.core.providers.router import get_router

    return get_router().available()


def provider_name() -> str:
    return get_settings().llm_provider


# ===========================================================================
# Anthropic
# ===========================================================================
_anthropic = None
_anthropic_lock = asyncio.Lock()


async def _anthropic_client():
    global _anthropic
    if _anthropic is not None:
        return _anthropic
    async with _anthropic_lock:
        if _anthropic is None:
            settings = get_settings()
            if not settings.anthropic_api_key:
                raise ModelUnavailable("ANTHROPIC_API_KEY is not configured", kind="config")
            try:
                from anthropic import AsyncAnthropic
            except ImportError as exc:  # pragma: no cover
                raise ModelUnavailable("anthropic package is not installed") from exc
            _anthropic = AsyncAnthropic(
                api_key=settings.anthropic_api_key,
                timeout=settings.request_timeout_seconds,
                max_retries=2,
            )
    return _anthropic


async def _anthropic_complete(system, messages, model, max_tokens, temperature) -> Completion:
    client = await _anthropic_client()
    try:
        response = await client.messages.create(
            model=model, max_tokens=max_tokens, temperature=temperature,
            system=system, messages=messages,
        )
    except Exception as exc:  # noqa: BLE001
        raise _anthropic_error(exc) from exc
    text = "".join(b.text for b in response.content if getattr(b, "type", "") == "text")
    return Completion(
        text=text.strip(),
        usage=Usage(getattr(response.usage, "input_tokens", 0), getattr(response.usage, "output_tokens", 0)),
        model=model,
        stop_reason=getattr(response, "stop_reason", None),
    )


async def _anthropic_stream(system, messages, model, max_tokens, temperature):
    client = await _anthropic_client()
    try:
        async with client.messages.stream(
            model=model, max_tokens=max_tokens, temperature=temperature,
            system=system, messages=messages,
        ) as streamed:
            async for text in streamed.text_stream:
                yield "delta", text
            final = await streamed.get_final_message()
            yield "usage", Usage(
                getattr(final.usage, "input_tokens", 0), getattr(final.usage, "output_tokens", 0)
            )
    except ModelUnavailable:
        raise
    except Exception as exc:  # noqa: BLE001
        raise _anthropic_error(exc) from exc


def _anthropic_error(exc: Exception) -> ModelUnavailable:
    status = getattr(exc, "status_code", None)
    name = type(exc).__name__
    if status == 429 or name == "RateLimitError":
        kind = "rate_limit"
    elif status in (401, 403) or name in {"AuthenticationError", "PermissionDeniedError"}:
        kind = "auth"
    elif name in {"APITimeoutError"}:
        kind = "timeout"
    elif name in {"APIConnectionError"}:
        kind = "network"
    else:
        kind = "provider_error"
    return ModelUnavailable(str(exc), kind=kind, status=status)


# ===========================================================================
# OpenRouter
# ===========================================================================
# Tests replace this with an httpx.MockTransport; nothing else should.
_transport: httpx.AsyncBaseTransport | None = None

# Reasoning tokens are generated before the answer and count against
# max_tokens. Without headroom a reasoning model can spend the whole budget
# thinking and return an empty answer.
REASONING_HEADROOM = 3000


def _openrouter_payload(system, messages, model, max_tokens, temperature, stream: bool) -> dict[str, Any]:
    settings = get_settings()
    payload: dict[str, Any] = {
        "model": model,
        "messages": [{"role": "system", "content": system}, *messages],
        "max_tokens": max_tokens + (REASONING_HEADROOM if settings.openrouter_reasoning_effort != "none" else 0),
        "temperature": temperature,
        "stream": stream,
    }
    if settings.openrouter_reasoning_effort != "none":
        # Keep thinking short, and keep it out of the response entirely.
        payload["reasoning"] = {"effort": settings.openrouter_reasoning_effort, "exclude": True}
    if stream:
        payload["stream_options"] = {"include_usage": True}
    return payload


def _openrouter_headers() -> dict[str, str]:
    settings = get_settings()
    if not settings.openrouter_api_key:
        raise ModelUnavailable("OPENROUTER_API_KEY is not configured", kind="config")
    return {
        "Authorization": f"Bearer {settings.openrouter_api_key}",
        "Content-Type": "application/json",
        # Optional attribution headers OpenRouter uses in its dashboards.
        "HTTP-Referer": settings.site_url,
        "X-Title": "ComeMorocco AI",
    }


def _openrouter_error(response: httpx.Response) -> ModelUnavailable:
    try:
        detail = response.json().get("error", {}).get("message") or response.text[:300]
    except ValueError:
        detail = response.text[:300]
    code = response.status_code
    if code == 429:
        return ModelUnavailable(
            f"OpenRouter rate limit reached (429): {detail}. Free models allow 20 requests a "
            "minute and 50 a day without purchased credits; failed attempts also count.",
            kind="rate_limit", status=code,
        )
    if code == 402:
        return ModelUnavailable(f"OpenRouter reports insufficient credit (402): {detail}", kind="quota", status=code)
    if code == 401:
        return ModelUnavailable(
            "OpenRouter rejected the API key (401). Check OPENROUTER_API_KEY in .env.", kind="auth", status=code
        )
    return ModelUnavailable(f"OpenRouter error {code}: {detail}", kind="provider_error", status=code)


def _openrouter_client() -> httpx.AsyncClient:
    settings = get_settings()
    return httpx.AsyncClient(
        base_url=settings.openrouter_base_url,
        timeout=httpx.Timeout(settings.request_timeout_seconds, connect=10.0),
        transport=_transport,
    )


async def _openrouter_complete(system, messages, model, max_tokens, temperature) -> Completion:
    payload = _openrouter_payload(system, messages, model, max_tokens, temperature, stream=False)
    try:
        async with _openrouter_client() as client:
            response = await client.post("/chat/completions", json=payload, headers=_openrouter_headers())
    except httpx.HTTPError as exc:
        raise ModelUnavailable(f"could not reach OpenRouter: {exc}", kind=_kind_for_http_error(exc)) from exc

    if response.status_code != 200:
        raise _openrouter_error(response)

    data = response.json()
    # OpenRouter can return 200 with an error body when the upstream provider fails.
    if "error" in data and not data.get("choices"):
        raise ModelUnavailable(f"OpenRouter provider error: {data['error'].get('message', data['error'])}")

    choice = (data.get("choices") or [{}])[0]
    text = strip_reasoning((choice.get("message") or {}).get("content") or "")
    if not text:
        raise ModelUnavailable(
            "OpenRouter returned an empty answer "
            f"(finish_reason={choice.get('finish_reason')}); the model may have spent its "
            "budget reasoning.",
            kind="empty",
        )
    usage = data.get("usage") or {}
    return Completion(
        text=text,
        usage=Usage(usage.get("prompt_tokens", 0), usage.get("completion_tokens", 0)),
        model=data.get("model", model),
        stop_reason=choice.get("finish_reason"),
    )


async def _openrouter_stream(system, messages, model, max_tokens, temperature):
    payload = _openrouter_payload(system, messages, model, max_tokens, temperature, stream=True)
    usage = Usage()
    emitted = False
    # Inline <think> blocks are held back until they close, so a reasoning
    # trace can never be streamed to a traveller mid-sentence.
    pending = ""
    in_think = False

    try:
        async with _openrouter_client() as client:
            async with client.stream(
                "POST", "/chat/completions", json=payload, headers=_openrouter_headers()
            ) as response:
                if response.status_code != 200:
                    await response.aread()
                    raise _openrouter_error(response)

                async for line in response.aiter_lines():
                    line = line.strip()
                    # Blank lines separate events; ":" lines are keep-alive
                    # comments ("OPENROUTER PROCESSING").
                    if not line or line.startswith(":") or not line.startswith("data:"):
                        continue
                    data = line[5:].strip()
                    if data == "[DONE]":
                        break
                    try:
                        chunk = json.loads(data)
                    except json.JSONDecodeError:
                        continue
                    if "error" in chunk and not chunk.get("choices"):
                        raise ModelUnavailable(f"OpenRouter stream error: {chunk['error'].get('message')}")
                    if chunk.get("usage"):
                        usage = Usage(
                            chunk["usage"].get("prompt_tokens", 0),
                            chunk["usage"].get("completion_tokens", 0),
                        )
                    for choice in chunk.get("choices") or []:
                        piece = (choice.get("delta") or {}).get("content") or ""
                        if not piece:
                            continue
                        pending += piece
                        while pending:
                            if in_think:
                                end = re.search(r"</think(?:ing)?>", pending, re.IGNORECASE)
                                if not end:
                                    pending = pending[-20:]  # keep enough to catch a split tag
                                    break
                                pending = pending[end.end():]
                                in_think = False
                                continue
                            start = re.search(r"<think(?:ing)?>", pending, re.IGNORECASE)
                            if start:
                                before = pending[: start.start()]
                                if before:
                                    emitted = True
                                    yield "delta", before
                                pending = pending[start.end():]
                                in_think = True
                                continue
                            # Hold back a trailing "<" in case a tag is split
                            # across chunks.
                            cut = pending.rfind("<")
                            if cut != -1 and len(pending) - cut < 12:
                                safe, pending = pending[:cut], pending[cut:]
                            else:
                                safe, pending = pending, ""
                            if safe:
                                if not emitted:
                                    safe = safe.lstrip()
                                if safe:
                                    emitted = True
                                    yield "delta", safe
                            break
    except ModelUnavailable:
        raise
    except httpx.HTTPError as exc:
        raise ModelUnavailable(f"could not reach OpenRouter: {exc}", kind=_kind_for_http_error(exc)) from exc

    if pending and not in_think:
        emitted = True
        yield "delta", pending
    if not emitted:
        raise ModelUnavailable(
            "OpenRouter streamed no answer text; the model may have spent its budget reasoning.", kind="empty"
        )
    yield "usage", usage


# ===========================================================================
# Public interface
# ===========================================================================
async def complete(
    system: str,
    message: str,
    *,
    history: list[dict[str, str]] | None = None,
    model: str | None = None,
    max_tokens: int | None = None,
    temperature: float | None = None,
) -> Completion:
    settings = get_settings()
    messages = _messages(history or [], message)
    model = model or settings.active_answer_model
    max_tokens = max_tokens or settings.max_answer_tokens
    temperature = settings.temperature if temperature is None else temperature

    from app.core.providers.router import get_router

    return await get_router().complete(
        system, messages, model=model, max_tokens=max_tokens, temperature=temperature
    )


async def stream(
    system: str,
    message: str,
    *,
    history: list[dict[str, str]] | None = None,
    model: str | None = None,
    max_tokens: int | None = None,
    temperature: float | None = None,
) -> AsyncIterator[tuple[str, Any]]:
    """Yield ("delta", text) chunks, then ("usage", Usage)."""
    settings = get_settings()
    messages = _messages(history or [], message)
    model = model or settings.active_answer_model
    max_tokens = max_tokens or settings.max_answer_tokens
    temperature = settings.temperature if temperature is None else temperature

    from app.core.providers.router import get_router

    async for item in get_router().stream(
        system, messages, model=model, max_tokens=max_tokens, temperature=temperature
    ):
        yield item


JSON_BLOCK = re.compile(r"\{.*\}", re.DOTALL)


async def complete_json(
    system: str,
    message: str,
    *,
    model: str | None = None,
    max_tokens: int = 600,
) -> dict[str, Any]:
    """Utility call that must return a JSON object.

    Parsed loosely on purpose: some models (Nemotron 3.5 Lightning among them)
    do not support enforced JSON output, and wrap it in prose or code fences.
    Callers treat a failure here as "use the rules only".
    """
    settings = get_settings()
    result = await complete(
        system + "\n\nRespond with the JSON object only. No prose, no code fences.",
        message,
        model=model or settings.active_utility_model,
        max_tokens=max_tokens,
        temperature=0.0,
    )
    text = strip_reasoning(result.text)
    if text.startswith("```"):
        text = re.sub(r"^```[a-z]*\n?|```$", "", text).strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        match = JSON_BLOCK.search(text)
        if not match:
            raise ValueError(f"model did not return JSON: {text[:120]!r}") from None
        return json.loads(match.group(0))
