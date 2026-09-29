"""Cloudflare Workers AI, called over its REST API.

  POST {base}/accounts/{account_id}/ai/run/{model}

Used as the last hosted fallback: the free plan allows a fixed number of
Neurons a day, after which Cloudflare answers 429 until the next UTC day.
The model is always named in configuration (WORKERS_AI_MODEL or LLM_CHAIN),
because which models the free plan may call changes over time.

Two response shapes exist depending on the model: the classic
`{"result": {"response": ...}}` and an OpenAI-style `{"result": {"choices": ...}}`.
Both are accepted, streaming and not.
"""

from __future__ import annotations

import json
import re
from collections.abc import AsyncIterator
from typing import Any

import httpx

from app.config import get_settings
from app.core.llm import Completion, ModelUnavailable, Usage, strip_reasoning
from app.core.providers.base import ProviderBase

# Tests replace this with an httpx.MockTransport; nothing else should.
_transport: httpx.AsyncBaseTransport | None = None

THINK_OPEN_TAG = re.compile(r"<think(?:ing)?>", re.IGNORECASE)
THINK_CLOSE_TAG = re.compile(r"</think(?:ing)?>", re.IGNORECASE)


def _error(response: httpx.Response) -> ModelUnavailable:
    try:
        body = response.json()
        errors = body.get("errors") or []
        detail = "; ".join(str(e.get("message", e)) for e in errors) or response.text[:300]
    except ValueError:
        detail = response.text[:300]
    code = response.status_code
    lowered = detail.lower()
    if code == 429 and ("daily" in lowered or "neurons" in lowered or "allocation" in lowered):
        return ModelUnavailable(
            f"Workers AI daily free allocation used up (429): {detail}", kind="quota", status=code
        )
    if code == 429:
        return ModelUnavailable(f"Workers AI rate limit (429): {detail}", kind="rate_limit", status=code)
    if code in (401, 403):
        return ModelUnavailable(
            f"Workers AI rejected the credentials ({code}). Check CLOUDFLARE_ACCOUNT_ID and "
            "CLOUDFLARE_API_TOKEN, "
            f"and that the model is available on your plan: {detail}",
            kind="auth",
            status=code,
        )
    return ModelUnavailable(f"Workers AI error {code}: {detail}", kind="provider_error", status=code)


def _text_from_result(result: Any) -> str:
    if isinstance(result, dict):
        if isinstance(result.get("response"), str):
            return result["response"]
        choices = result.get("choices") or []
        if choices:
            message = choices[0].get("message") or choices[0].get("delta") or {}
            return message.get("content") or ""
    return ""


def _usage_from(obj: Any) -> Usage | None:
    usage = obj.get("usage") if isinstance(obj, dict) else None
    if not usage:
        return None
    return Usage(usage.get("prompt_tokens", 0), usage.get("completion_tokens", 0))


class _ThinkFilter:
    """Drops <think>…</think> spans from a stream, even when tags are split across chunks."""

    def __init__(self) -> None:
        self.pending = ""
        self.in_think = False

    def feed(self, piece: str) -> str:
        self.pending += piece
        out = []
        while self.pending:
            if self.in_think:
                end = THINK_CLOSE_TAG.search(self.pending)
                if not end:
                    self.pending = self.pending[-20:]
                    break
                self.pending = self.pending[end.end() :]
                self.in_think = False
                continue
            start = THINK_OPEN_TAG.search(self.pending)
            if start:
                out.append(self.pending[: start.start()])
                self.pending = self.pending[start.end() :]
                self.in_think = True
                continue
            cut = self.pending.rfind("<")
            if cut != -1 and len(self.pending) - cut < 12:
                out.append(self.pending[:cut])
                self.pending = self.pending[cut:]
            else:
                out.append(self.pending)
                self.pending = ""
            break
        return "".join(out)

    def flush(self) -> str:
        rest, self.pending = ("" if self.in_think else self.pending), ""
        return rest


class WorkersAIProvider(ProviderBase):
    name = "workers_ai"

    def configured(self) -> bool:
        s = get_settings()
        return bool(s.cloudflare_account_id and s.cloudflare_api_token and self.model)

    def _client(self) -> httpx.AsyncClient:
        s = get_settings()
        return httpx.AsyncClient(
            base_url=f"{s.workers_ai_base_url.rstrip('/')}/accounts/{s.cloudflare_account_id}/ai/run/",
            timeout=httpx.Timeout(s.request_timeout_seconds, connect=10.0),
            transport=_transport,
        )

    def _headers(self) -> dict[str, str]:
        s = get_settings()
        if not (s.cloudflare_account_id and s.cloudflare_api_token):
            raise ModelUnavailable(
                "CLOUDFLARE_ACCOUNT_ID / CLOUDFLARE_API_TOKEN are not configured", kind="config"
            )
        return {"Authorization": f"Bearer {s.cloudflare_api_token}", "Content-Type": "application/json"}

    def _payload(self, system, messages, max_tokens, temperature, stream: bool) -> dict[str, Any]:
        return {
            "messages": [{"role": "system", "content": system}, *messages],
            "max_tokens": max_tokens,
            "temperature": temperature,
            "stream": stream,
        }

    async def complete(self, system, messages, max_tokens, temperature) -> Completion:
        headers = self._headers()
        try:
            async with self._client() as client:
                response = await client.post(
                    self.model,
                    json=self._payload(system, messages, max_tokens, temperature, False),
                    headers=headers,
                )
        except httpx.HTTPError as exc:
            kind = "timeout" if isinstance(exc, httpx.TimeoutException) else "network"
            raise ModelUnavailable(f"could not reach Workers AI: {exc}", kind=kind) from exc
        if response.status_code != 200:
            raise _error(response)
        data = response.json()
        if data.get("success") is False:
            raise _error(response)
        result = data.get("result") or {}
        text = strip_reasoning(_text_from_result(result))
        if not text:
            raise ModelUnavailable("Workers AI returned an empty answer", kind="empty")
        return Completion(
            text=text,
            usage=_usage_from(result) or Usage(),
            model=self.model,
            stop_reason=None,
            provider=self.name,
        )

    async def stream(self, system, messages, max_tokens, temperature) -> AsyncIterator[tuple[str, Any]]:
        headers = self._headers()
        usage = Usage()
        emitted = False
        think = _ThinkFilter()
        try:
            async with self._client() as client:
                async with client.stream(
                    "POST",
                    self.model,
                    json=self._payload(system, messages, max_tokens, temperature, True),
                    headers=headers,
                ) as response:
                    if response.status_code != 200:
                        await response.aread()
                        raise _error(response)
                    async for line in response.aiter_lines():
                        line = line.strip()
                        if not line.startswith("data:"):
                            continue
                        data = line[5:].strip()
                        if data == "[DONE]":
                            break
                        try:
                            chunk = json.loads(data)
                        except json.JSONDecodeError:
                            continue
                        usage = _usage_from(chunk) or usage
                        safe = think.feed(_text_from_result(chunk))
                        if not emitted:
                            safe = safe.lstrip()
                        if safe:
                            emitted = True
                            yield "delta", safe
        except ModelUnavailable:
            raise
        except httpx.HTTPError as exc:
            kind = "timeout" if isinstance(exc, httpx.TimeoutException) else "network"
            raise ModelUnavailable(f"could not reach Workers AI: {exc}", kind=kind) from exc

        rest = think.flush()
        if rest.strip():
            emitted = True
            yield "delta", rest
        if not emitted:
            raise ModelUnavailable("Workers AI streamed no answer text", kind="empty")
        yield "usage", usage
