"""Adapters for the two providers that already lived in llm.py.

Their wire code stays in llm.py untouched (the OpenRouter tests patch it
there); these classes only give it the provider interface.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any

from app.config import get_settings
from app.core import llm
from app.core.llm import Completion
from app.core.providers.base import ProviderBase


class OpenRouterProvider(ProviderBase):
    name = "openrouter"

    def configured(self) -> bool:
        return bool(get_settings().openrouter_api_key)

    async def complete(self, system, messages, max_tokens, temperature) -> Completion:
        result = await llm._openrouter_complete(system, messages, self.model, max_tokens, temperature)
        result.provider = self.name
        return result

    async def stream(self, system, messages, max_tokens, temperature) -> AsyncIterator[tuple[str, Any]]:
        async for item in llm._openrouter_stream(system, messages, self.model, max_tokens, temperature):
            yield item


class AnthropicProvider(ProviderBase):
    name = "anthropic"

    def configured(self) -> bool:
        return bool(get_settings().anthropic_api_key)

    async def complete(self, system, messages, max_tokens, temperature) -> Completion:
        result = await llm._anthropic_complete(system, messages, self.model, max_tokens, temperature)
        result.provider = self.name
        return result

    async def stream(self, system, messages, max_tokens, temperature) -> AsyncIterator[tuple[str, Any]]:
        async for item in llm._anthropic_stream(system, messages, self.model, max_tokens, temperature):
            yield item
