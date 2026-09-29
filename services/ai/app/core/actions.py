"""Trip context in, action proposals out (Master Plan §13–14, §19–20).

The AI never writes user data. It *proposes* actions — "add this tour to My
Trip", "save Fes" — built by code from what was already selected by code (the
resource and affiliate cards) and the destinations the rules detected. The
app validates every proposal against the shared tool schemas
(packages/shared/src/api/v1/actions.ts, `authorizeToolCall`) and executes it
only when the traveller taps it.
"""

from __future__ import annotations

from app.schemas import AffiliateCard, AIActionOut, Classification, ResourceCard, TripContext, TripState

# Intents where suggesting trip changes would be tone-deaf or unsafe.
NO_ACTION_INTENTS = {"OFF_TOPIC", "GREETING", "SAFETY", "IMPOSSIBLE_ACTION", "PROBLEM"}

MAX_ACTIONS = 5

# Destination names the rules detect (intent.PLACES) -> app destination ids.
DESTINATION_IDS = {
    "marrakech": "marrakech",
    "fes": "fes",
    "chefchaouen": "chefchaouen",
    "merzouga": "merzouga",
    "sahara desert": "merzouga",
    "essaouira": "essaouira",
    "casablanca": "casablanca",
    "rabat": "rabat",
    "tangier": "tangier",
    "agadir": "agadir",
    "taghazout": "agadir",
    "ouarzazate": "ouarzazate",
    "dakhla": "dakhla",
}


def merge_trip_context(trip: TripState, context: TripContext | None) -> TripState:
    """Seed the conversation's trip state from the app's My Trip.

    The conversation wins: anything the traveller said (a different length, an
    excluded city) is kept. Trip context only fills gaps and adds destinations
    that were not ruled out.
    """
    if context is None:
        return trip
    merged = TripState.from_dict(trip.to_dict())
    if merged.trip_duration_days is None and context.day_count:
        merged.trip_duration_days = context.day_count
    if merged.travel_dates is None and context.start_date:
        merged.travel_dates = f"from {context.start_date}"
    excluded = {d.lower() for d in merged.excluded_destinations}
    present = {d.lower() for d in merged.destinations}
    for destination in context.destinations:
        if destination.lower() not in excluded and destination.lower() not in present:
            merged.destinations.append(destination)
            present.add(destination.lower())
    return merged


def propose_actions(
    classification: Classification,
    resources: list[ResourceCard],
    affiliates: list[AffiliateCard],
) -> list[AIActionOut]:
    if NO_ACTION_INTENTS & set(classification.intents):
        return []
    actions: list[AIActionOut] = []

    for card in affiliates:
        actions.append(_add_to_trip("listing", card.affiliate_id, card.label))
    for card in resources:
        actions.append(_add_to_trip("article", card.content_id, card.title))
    seen: set[str] = set()
    for name in classification.destinations:
        dest_id = DESTINATION_IDS.get(name.lower())
        if dest_id and dest_id not in seen:
            seen.add(dest_id)
            actions.append(
                AIActionOut(
                    id=f"save_place:{dest_id}",
                    tool="save_place",
                    args={"place_id": dest_id, "ref_type": "destination"},
                    access="write",
                    label=name,
                    requires_confirmation=False,
                )
            )
    return actions[:MAX_ACTIONS]


def _add_to_trip(item_type: str, ref_id: str, title: str) -> AIActionOut:
    return AIActionOut(
        id=f"add_to_trip:{item_type}:{ref_id}",
        tool="add_to_trip",
        args={"item_type": item_type, "ref_id": ref_id, "title": title[:200]},
        access="write",
        label=title[:200],
        requires_confirmation=False,
    )
