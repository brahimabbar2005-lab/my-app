"""Provider routing: try each configured provider in order, skip the ones
that are cooling down, and fall through on failure.

    OpenRouter free model A → OpenRouter free model B → Workers AI → fallback

The chain comes from LLM_CHAIN when set:

    LLM_CHAIN=openrouter:vendor/model-a:free,openrouter:vendor/model-b:free,workers_ai:@cf/vendor/model

Otherwise it is derived from the keys that are present: the primary provider
(LLM_PROVIDER / whichever key is set), then OPENROUTER_FALLBACK_MODEL, then
Workers AI when CLOUDFLARE_* and WORKERS_AI_MODEL are set. With a single
provider this behaves exactly like calling it directly, errors included.

"Graceful fallback" when every provider fails is the caller's job: the
orchestrator already catches ModelUnavailable and answers with the fallback
message plus the resource cards.
"""

from __future__ import annotations

import asyncio
import logging
import re
import time
from collections.abc import AsyncIterator
from typing import Any

from app.config import Settings, get_settings
from app.core.llm import Completion, ModelUnavailable, Usage
from app.core.providers.base import ProviderBase, ProviderHealth
from app.core.providers.hosted import AnthropicProvider, OpenRouterProvider
from app.core.providers.workers_ai import WorkersAIProvider

log = logging.getLogger(__name__)

PROVIDER_CLASSES: dict[str, type[ProviderBase]] = {
    "openrouter": OpenRouterProvider,
    "workers_ai": WorkersAIProvider,
    "anthropic": AnthropicProvider,
}


# Degenerate output seen from free models with reasoning disabled: a word
# fragment stuttering ("résellsellsells"), or a switch into CJK script or
# bracket tokens ("【重要…") in a French or English answer. No supported
# answer language uses CJK, so any CJK character is treated as garbled.
GARBLED = re.compile(r"(\w{3,}?)\1{2,}|[\u3040-\u30ff\u4e00-\u9fff\uac00-\ud7af]|[【】]")

# Characters held back at the start of a streamed answer so garbled output
# can still be swapped for another provider before the traveller sees it.
PROBE_CHARS = 120


def looks_garbled(text: str) -> bool:
    return bool(GARBLED.search(text))


def parse_chain(entries: list[str]) -> list[ProviderBase]:
    providers: list[ProviderBase] = []
    for entry in entries:
        name, _, model = entry.partition(":")
        cls = PROVIDER_CLASSES.get(name.strip().lower())
        if cls is None or not model.strip():
            log.warning(
                "LLM_CHAIN: ignoring %r (expected <provider>:<model>, provider one of %s)",
                entry,
                ", ".join(PROVIDER_CLASSES),
            )
            continue
        providers.append(cls(model.strip()))
    return providers


def default_chain(settings: Settings) -> list[ProviderBase]:
    primary_cls = PROVIDER_CLASSES[settings.llm_provider]
    chain: list[ProviderBase] = [primary_cls(settings.active_answer_model)]
    if settings.openrouter_fallback_model and settings.openrouter_api_key:
        chain.append(OpenRouterProvider(settings.openrouter_fallback_model))
    if settings.workers_ai_configured:
        chain.append(WorkersAIProvider(settings.workers_ai_model or ""))
    return chain


class ProviderRouter:
    def __init__(self, providers: list[ProviderBase]):
        if not providers:
            raise ValueError("a provider router needs at least one provider")
        # Unconfigured providers are dropped, unless none is configured: then
        # the first one stays so its "key is not configured" error surfaces.
        configured = [p for p in providers if p.configured()]
        self.providers = configured or providers[:1]
        self.health: dict[str, ProviderHealth] = {}

    def _health(self, provider: ProviderBase) -> ProviderHealth:
        if provider.key not in self.health:
            self.health[provider.key] = ProviderHealth(provider.key)
        return self.health[provider.key]

    def available(self) -> bool:
        return any(p.configured() for p in self.providers)

    def _chain_for(self, model: str | None) -> list[ProviderBase]:
        """The chain, with the primary provider switched to `model` when a
        caller asks for a specific model (the utility model, for example)."""
        chain = list(self.providers)
        # Model names are provider-specific: only apply an override to a
        # primary provider of the configured LLM_PROVIDER kind. Otherwise an
        # OpenRouter model id would be sent to Workers AI (which answers
        # "400 No route for that URI").
        if model and chain[0].model != model and chain[0].name == get_settings().llm_provider:
            chain[0] = type(chain[0])(model)
        return chain

    def _ordered(self, model: str | None) -> list[ProviderBase]:
        chain = self._chain_for(model)
        now = time.monotonic()
        ready = [p for p in chain if self._health(p).available(now)]
        if ready:
            return ready
        # Everything is cooling down: try the one that recovers first rather
        # than failing without a single attempt.
        return [min(chain, key=lambda p: self._health(p).cooldown_until)]

    @staticmethod
    def _exhausted(errors: list[tuple[ProviderBase, ModelUnavailable]]) -> ModelUnavailable:
        if len(errors) == 1:
            return errors[0][1]
        detail = "; ".join(f"{p.key}: {e.kind}" for p, e in errors)
        return ModelUnavailable(f"all model providers failed ({detail})", kind=errors[-1][1].kind)

    async def complete(
        self,
        system: str,
        messages: list[dict[str, Any]],
        *,
        model: str | None,
        max_tokens: int,
        temperature: float,
    ) -> Completion:
        errors: list[tuple[ProviderBase, ModelUnavailable]] = []
        for provider in self._ordered(model):
            health = self._health(provider)
            started = time.monotonic()
            try:
                result = await asyncio.wait_for(
                    provider.complete(system, messages, max_tokens, temperature),
                    timeout=get_settings().llm_provider_timeout_seconds,
                )
                if looks_garbled(result.text):
                    raise ModelUnavailable(f"garbled output: {result.text[:80]!r}", kind="garbled")
            except TimeoutError:
                exc = ModelUnavailable("no answer within the provider timeout", kind="timeout")
                health.record_failure(exc.kind, str(exc), int((time.monotonic() - started) * 1000))
                log.warning("provider %s timed out", provider.key)
                errors.append((provider, exc))
                continue
            except ModelUnavailable as exc:
                health.record_failure(exc.kind, str(exc), int((time.monotonic() - started) * 1000))
                log.warning("provider %s failed (%s): %s", provider.key, exc.kind, exc)
                errors.append((provider, exc))
                continue
            health.record_success(
                int((time.monotonic() - started) * 1000),
                result.usage.input_tokens,
                result.usage.output_tokens,
            )
            if errors:
                log.info("answered by fallback provider %s after %d failure(s)", provider.key, len(errors))
            result.provider = result.provider or provider.name
            return result
        raise self._exhausted(errors)

    async def stream(
        self,
        system: str,
        messages: list[dict[str, Any]],
        *,
        model: str | None,
        max_tokens: int,
        temperature: float,
    ) -> AsyncIterator[tuple[str, Any]]:
        """Fall through to the next provider only while nothing has been
        streamed yet. Once text is on the traveller's screen, a failure is
        raised: switching models mid-sentence would produce a garbled answer."""
        settings = get_settings()
        errors: list[tuple[ProviderBase, ModelUnavailable]] = []
        for provider in self._ordered(model):
            health = self._health(provider)
            started = time.monotonic()
            emitted = False
            usage = Usage()
            held: list[str] = []  # the probe: first characters, not yet shown
            source = provider.stream(system, messages, max_tokens, temperature)
            try:
                while True:
                    try:
                        if not emitted and not held:
                            # A provider that has not started answering in time is
                            # skipped; the traveller is not kept waiting on it.
                            kind, value = await asyncio.wait_for(
                                source.__anext__(), timeout=settings.llm_first_token_timeout_seconds
                            )
                        else:
                            kind, value = await source.__anext__()
                    except StopAsyncIteration:
                        break
                    if kind == "usage":
                        usage = value
                        continue
                    if kind != "delta":
                        continue
                    if emitted:
                        yield "delta", value
                        continue
                    held.append(value)
                    probe = "".join(held)
                    if looks_garbled(probe):
                        raise ModelUnavailable(f"garbled output: {probe[:80]!r}", kind="garbled")
                    if len(probe) >= PROBE_CHARS:
                        emitted = True
                        yield "delta", probe
                        held.clear()
                if held:
                    probe = "".join(held)
                    if looks_garbled(probe):
                        raise ModelUnavailable(f"garbled output: {probe[:80]!r}", kind="garbled")
                    emitted = True
                    yield "delta", probe
            except TimeoutError:
                exc = ModelUnavailable("no first token within the timeout", kind="timeout")
                health.record_failure(exc.kind, str(exc), int((time.monotonic() - started) * 1000))
                log.warning("provider %s did not start answering in time", provider.key)
                errors.append((provider, exc))
                await _close(source)
                continue
            except ModelUnavailable as exc:
                health.record_failure(exc.kind, str(exc), int((time.monotonic() - started) * 1000))
                log.warning("provider %s failed while streaming (%s): %s", provider.key, exc.kind, exc)
                await _close(source)
                if emitted:
                    raise
                errors.append((provider, exc))
                continue
            health.record_success(
                int((time.monotonic() - started) * 1000), usage.input_tokens, usage.output_tokens
            )
            yield "usage", usage
            return
        raise self._exhausted(errors)

    def snapshot(self) -> list[dict[str, Any]]:
        return [self._health(p).snapshot() for p in self.providers]


async def _close(source: AsyncIterator[Any]) -> None:
    aclose = getattr(source, "aclose", None)
    if aclose is not None:
        try:
            await aclose()
        except Exception:  # noqa: BLE001 - closing a failed stream must not mask the failure
            pass


_router: ProviderRouter | None = None
_router_settings: Settings | None = None


def get_router() -> ProviderRouter:
    """One router per settings object, so tests that clear the settings cache
    also start with fresh provider health."""
    global _router, _router_settings
    settings = get_settings()
    if _router is None or _router_settings is not settings:
        chain = parse_chain(settings.llm_chain) if settings.llm_chain else []
        _router = ProviderRouter(chain or default_chain(settings))
        _router_settings = settings
    return _router
