"""Loads the built knowledge base into memory and keeps it reloadable.

The knowledge base is small enough (240 pages, 104 commercial records) to hold
in memory. Re-indexing after a WordPress change is therefore a file swap plus
`KnowledgeBase.reload()`, not a deployment.
"""
from __future__ import annotations

import json
import logging
import threading
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

log = logging.getLogger(__name__)


@dataclass
class KnowledgeBase:
    directory: Path
    items: list[dict[str, Any]] = field(default_factory=list)
    by_id: dict[str, dict[str, Any]] = field(default_factory=dict)
    destination_coverage: dict[str, Any] = field(default_factory=dict)
    intent_map: dict[str, Any] = field(default_factory=dict)
    content_gaps: list[dict[str, Any]] = field(default_factory=list)
    programs: list[dict[str, Any]] = field(default_factory=list)
    activities: list[dict[str, Any]] = field(default_factory=list)
    affiliate_review_notes: list[dict[str, Any]] = field(default_factory=list)
    golden_questions: list[dict[str, Any]] = field(default_factory=list)
    multi_turn_tests: list[dict[str, Any]] = field(default_factory=list)
    source_examples: list[dict[str, Any]] = field(default_factory=list)
    manifest: dict[str, Any] = field(default_factory=dict)

    _lock: threading.RLock = field(default_factory=threading.RLock, repr=False)

    # -- loading ------------------------------------------------------------
    def _read(self, name: str) -> dict[str, Any]:
        path = self.directory / name
        if not path.exists():
            raise FileNotFoundError(
                f"{path} is missing. Run:  python scripts/build_knowledge_base.py"
            )
        return json.loads(path.read_text(encoding="utf-8"))

    def reload(self) -> dict[str, int]:
        with self._lock:
            content = self._read("content.json")
            affiliates = self._read("affiliates.json")
            try:
                golden = self._read("golden.json")
            except FileNotFoundError:
                golden = {"questions": [], "multi_turn": [], "source_examples": []}

            self.items = content["items"]
            self.by_id = {item["id"]: item for item in self.items}
            self.destination_coverage = content.get("destination_coverage", {})
            self.intent_map = content.get("intent_map", {})
            self.content_gaps = content.get("content_gaps", [])

            self.programs = affiliates["programs"]
            self.activities = affiliates["activities"]
            self.affiliate_review_notes = affiliates.get("review_notes", [])

            self.golden_questions = golden.get("questions", [])
            self.multi_turn_tests = golden.get("multi_turn", [])
            self.source_examples = golden.get("source_examples", [])

            try:
                self.manifest = self._read("manifest.json")
            except FileNotFoundError:
                self.manifest = {}

        counts = {
            "content_items": len(self.items),
            "programs": len(self.programs),
            "activities": len(self.activities),
            "golden_questions": len(self.golden_questions),
        }
        log.info("knowledge base loaded: %s", counts)
        return counts

    # -- lookups ------------------------------------------------------------
    def get(self, content_id: str) -> dict[str, Any] | None:
        return self.by_id.get(str(content_id))

    def destinations(self) -> list[str]:
        return [entry["destination"] for entry in self.destination_coverage.values()]

    def linkable_items(self) -> list[dict[str, Any]]:
        """Pages the link engine is allowed to propose.

        The content map marks some pages "Do not proactively link" (contact,
        terms, thin pages). Those stay retrievable as context but never become
        a recommendation.
        """
        return [
            item
            for item in self.items
            if item.get("link_behavior", "").lower() != "do not proactively link"
        ]

    def health(self) -> dict[str, Any]:
        return {
            "content_items": len(self.items),
            "linkable_items": len(self.linkable_items()),
            "affiliate_programs": len(self.programs),
            "usable_affiliate_programs": sum(1 for p in self.programs if p.get("usable")),
            "activities": len(self.activities),
            "usable_activities": sum(1 for a in self.activities if a.get("usable")),
            "golden_questions": len(self.golden_questions),
            "built_at": self.manifest.get("built_at"),
        }


_kb: KnowledgeBase | None = None


def get_knowledge_base(directory: Path | None = None) -> KnowledgeBase:
    global _kb
    if _kb is None:
        from app.config import get_settings

        _kb = KnowledgeBase(directory or get_settings().knowledge_dir)
        _kb.reload()
    return _kb
