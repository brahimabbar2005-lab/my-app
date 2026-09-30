"""The orchestrator's retrieval path must pick the same pages as the
retriever tested in tests/test_retrieval_quality.py.

That file calls the retriever directly. The orchestrator first extracts trip
state from the message and appends it to the query — and the first live model
check showed the extra terms changing the links ("Marrakech or Fes for a
first trip?" linked "Flights to Marrakech"). This runs every annotated case
through the real `_prepare` path.
"""

from __future__ import annotations

import pytest

from app.core.intent import classify_rules
from app.core.orchestrator import Orchestrator, retrieval_query_with_trip
from app.core.trip_state import extract_rules
from app.schemas import TripState
from tests.test_retrieval_quality import CASES


@pytest.mark.parametrize("label,question,acceptable,forbidden", CASES, ids=[c[0] for c in CASES])
def test_orchestrator_links_match_the_annotated_cases(label, question, acceptable, forbidden):
    orchestrator = Orchestrator()
    classification = classify_rules(question)
    trip = extract_rules(question, TripState())
    _, resources, _, _ = orchestrator._prepare(question, classification, trip, None, set())
    titles = [r.title for r in resources]
    if acceptable:
        assert titles, f"{label}: no link"
        assert any(a.lower() in titles[0].lower() for a in acceptable), f"{label}: first link {titles[0]!r}"
    for bad in forbidden:
        assert not any(bad.lower() in t.lower() for t in titles), f"{label}: linked {bad!r}"


def test_trip_context_is_added_only_when_new():
    trip = TripState(destinations=["Marrakech", "Essaouira"], interests=["food"])
    assert retrieval_query_with_trip("Marrakech or Fes?", trip) == "Marrakech or Fes? Essaouira food"
    assert (
        retrieval_query_with_trip("Food in Essaouira and Marrakech?", trip)
        == "Food in Essaouira and Marrakech?"
    )
