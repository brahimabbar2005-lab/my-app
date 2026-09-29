"""Trip context in, action proposals out (app/core/actions.py)."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.core.actions import merge_trip_context, propose_actions
from app.schemas import AffiliateCard, ChatRequest, Classification, ResourceCard, TripContext, TripState


def card(i: str = "GYG-008") -> AffiliateCard:
    return AffiliateCard(
        affiliate_id=i,
        name="Desert",
        category="Desert Tour",
        url="https://gyg.me/x",
        label="Desert",
        reason="r",
    )


def resource(i: str = "4079") -> ResourceCard:
    return ResourceCard(
        content_id=i,
        title="Sahara guide",
        url="https://comemorocco.com/x/",
        anchor_text="a",
        reason="r",
        score=2.0,
    )


def test_proposes_trip_actions_only_for_selected_cards_and_detected_places():
    classification = Classification(
        intents=["ACTIVITY", "DESERT"], language="en", destinations=["Marrakech", "Sahara Desert"]
    )
    actions = propose_actions(classification, [resource()], [card()])
    assert [a.id for a in actions] == [
        "add_to_trip:listing:GYG-008",
        "add_to_trip:article:4079",
        "save_place:marrakech",
        "save_place:merzouga",
    ]
    assert all(a.access == "write" and not a.requires_confirmation for a in actions)
    assert actions[0].args == {"item_type": "listing", "ref_id": "GYG-008", "title": "Desert"}


@pytest.mark.parametrize("intent", ["OFF_TOPIC", "GREETING", "SAFETY", "IMPOSSIBLE_ACTION", "PROBLEM"])
def test_no_actions_for_off_topic_safety_or_problems(intent):
    classification = Classification(intents=[intent], language="en", destinations=["Marrakech"])
    assert propose_actions(classification, [resource()], [card()]) == []


def test_actions_are_capped_and_places_deduplicated():
    classification = Classification(
        intents=["ITINERARY"], language="en", destinations=["Agadir", "Taghazout"]
    )
    actions = propose_actions(classification, [resource(str(i)) for i in range(6)], [])
    assert len(actions) == 5
    places = propose_actions(classification, [], [])
    assert [a.id for a in places] == ["save_place:agadir"]


def test_trip_context_fills_gaps_but_never_overrides_the_conversation():
    trip = TripState(trip_duration_days=5, excluded_destinations=["Fes"], destinations=["Marrakech"])
    merged = merge_trip_context(
        trip, TripContext(day_count=10, destinations=["Fes", "Essaouira", "marrakech"])
    )
    assert merged.trip_duration_days == 5  # the traveller said 5 in this conversation
    assert merged.destinations == ["Marrakech", "Essaouira"]  # Fes was ruled out; no duplicates
    assert trip.destinations == ["Marrakech"], "the original trip state is not mutated"
    empty = merge_trip_context(TripState(), TripContext(day_count=7, start_date="2026-10-01"))
    assert empty.trip_duration_days == 7 and empty.travel_dates == "from 2026-10-01"
    assert merge_trip_context(trip, None) is trip


def test_trip_context_is_validated():
    with pytest.raises(ValidationError):
        ChatRequest(message="hi", trip_context={"day_count": 500})
    with pytest.raises(ValidationError):
        ChatRequest(message="hi", trip_context={"start_date": "next week"})
    ok = ChatRequest(message="hi", trip_context={"day_count": 4, "destinations": ["  Fes ", ""]})
    assert ok.trip_context.destinations == ["Fes"]
