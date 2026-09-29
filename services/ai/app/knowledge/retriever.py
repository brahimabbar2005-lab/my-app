"""Thin facade: knowledge base + index, rebuilt whenever content is re-synced."""
from __future__ import annotations

import logging
import threading
from typing import Any

from app.config import get_settings
from app.knowledge.index import ContentIndex, ScoredItem
from app.knowledge.loader import KnowledgeBase, get_knowledge_base
from app.schemas import Classification
from app.core.lexicon import retrieval_query

log = logging.getLogger(__name__)


class Retriever:
    def __init__(self, kb: KnowledgeBase | None = None):
        self.kb = kb or get_knowledge_base()
        self._lock = threading.RLock()
        self._index = ContentIndex(self.kb.items)

    def rebuild(self) -> dict[str, int]:
        """Reload the knowledge files and re-index. Safe to call at runtime."""
        with self._lock:
            counts = self.kb.reload()
            self._index = ContentIndex(self.kb.items)
        return counts

    def retrieve(
        self,
        query: str,
        classification: Classification,
        *,
        page_url: str | None = None,
        limit: int | None = None,
    ) -> list[ScoredItem]:
        settings = get_settings()
        limit = limit or settings.retrieval_candidates
        with self._lock:
            index = self._index
        query = retrieval_query(query, classification.language, index.known_terms)

        results = index.search(
            query,
            intents=classification.intents,
            destinations=classification.destinations,
            limit=limit,
        )

        # The page the traveller is reading is a weak hint: if one of the
        # retrieved pages *is* that page, it is usually not worth linking back
        # to, but it is worth using as context.
        if page_url:
            for scored in results:
                if scored.item["url"].rstrip("/") == page_url.rstrip("/"):
                    scored.reasons.append("currently open page")
        return results

    def context_items(self, results: list[ScoredItem]) -> list[dict[str, Any]]:
        """The subset passed to the model as retrieval context."""
        settings = get_settings()
        usable = [r for r in results if r.score >= settings.min_retrieval_score]
        return [r.item for r in usable[: settings.retrieval_context_items]]


_retriever: Retriever | None = None


def get_retriever() -> Retriever:
    global _retriever
    if _retriever is None:
        _retriever = Retriever()
    return _retriever
