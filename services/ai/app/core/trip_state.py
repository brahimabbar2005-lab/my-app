"""Maintain a structured picture of the traveller's trip across turns.

Raw chat history alone is not enough. When someone says "actually, we'd like
to add Essaouira", the assistant has to know the trip is still 10 days, still
two adults, still arriving in Casablanca. Keeping that as a structured object
makes it explicit, inspectable and testable — and it is what makes the
multi-turn golden tests (MT-001 to MT-010) pass, since most of them are about
constraints that must survive later turns or be dropped when corrected.
"""
from __future__ import annotations

import json
import logging
import re
from typing import Any

from app.schemas import TripState

log = logging.getLogger(__name__)

NUMBER_WORDS = {
    "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7,
    "eight": 8, "nine": 9, "ten": 10, "eleven": 11, "twelve": 12, "thirteen": 13,
    "fourteen": 14, "fifteen": 15, "sixteen": 16, "seventeen": 17, "eighteen": 18,
    "nineteen": 19, "twenty": 20, "a couple of": 2, "a few": 3,
}

MONTHS = ("january", "february", "march", "april", "may", "june", "july", "august",
          "september", "october", "november", "december")

SEASONS = {
    "december": "winter", "january": "winter", "february": "winter",
    "march": "spring", "april": "spring", "may": "spring",
    "june": "summer", "july": "summer", "august": "summer",
    "september": "autumn", "october": "autumn", "november": "autumn",
}


def _number(token: str) -> int | None:
    token = token.strip().lower()
    if token.isdigit():
        return int(token)
    return NUMBER_WORDS.get(token)


def extract_rules(text: str, current: TripState) -> TripState:
    """Cheap, deterministic extraction. Only fills fields it is confident about."""
    state = TripState.from_dict(current.to_dict())
    lowered = text.lower()

    # Duration --------------------------------------------------------------
    duration = re.search(
        r"\b(\d{1,2}|one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve|"
        r"thirteen|fourteen|fifteen|sixteen|seventeen|eighteen|nineteen|twenty)\s*"
        r"(day|days|night|nights|week|weeks)\b",
        lowered,
    )
    if duration:
        value = _number(duration.group(1))
        unit = duration.group(2)
        if value:
            days = value * 7 if unit.startswith("week") else value
            # "3 nights in Merzouga" is a leg, not the whole trip. Only treat a
            # duration as the trip length when it is not tied to one place.
            tail = lowered[duration.end(): duration.end() + 30]
            leg = re.match(r"\s*(in|at|around)\s+\w+", tail)
            if not leg or days >= 7:
                state.trip_duration_days = days
    if re.search(r"\b(a|one)\s+month\b", lowered):
        state.trip_duration_days = 30

    # Dates and season ------------------------------------------------------
    month = next((m for m in MONTHS if re.search(rf"\b{m}\b", lowered)), None)
    if month:
        state.travel_dates = month.capitalize()
        state.season = SEASONS[month]
    for phrase, season in (("christmas", "winter"), ("new year", "winter"), ("ramadan", None),
                           ("easter", "spring"), ("summer", "summer"), ("winter", "winter")):
        if phrase in lowered:
            state.travel_dates = state.travel_dates or phrase.title()
            if season:
                state.season = state.season or season

    # Party -----------------------------------------------------------------
    adults = re.search(r"\b(\d{1,2}|two|three|four|five|six)\s+adults?\b", lowered)
    if adults:
        state.party_adults = _number(adults.group(1))
    children = re.search(r"\b(\d{1,2}|one|two|three|four|five|six)\s+(kids?|children|child)\b", lowered)
    if children:
        state.party_children = _number(children.group(1))
    ages = re.findall(r"\b(?:aged?|they(?:'| a)?re)\s+(\d{1,2})\s*(?:and|,|&)\s*(\d{1,2})\b", lowered)
    if ages:
        state.children_ages = [str(a) for pair in ages for a in pair]
    single_age = re.search(r"\b(\d{1,2})[ -](?:month|year)[ -]old\b", lowered)
    if single_age and not state.children_ages:
        state.children_ages = [single_age.group(0)]
        state.party_children = state.party_children or 1

    # Traveller type --------------------------------------------------------
    if re.search(r"\b(my (wife|husband|partner|girlfriend|boyfriend|fianc)|as a couple|honeymoon)\b", lowered):
        state.traveler_type = "couple"
        state.party_adults = state.party_adults or 2
    if re.search(r"\b(travell?ing (alone|solo)|by myself|on my own|i'?m solo)\b", lowered):
        state.traveler_type = "solo"
        state.party_adults = state.party_adults or 1
    if state.party_children or re.search(r"\b(family of|with (my|our) (kids?|children))\b", lowered):
        state.traveler_type = "family"
    if re.search(r"\b(backpack\w*|hostel|shoestring)\b", lowered):
        state.traveler_type = state.traveler_type or "backpacker"
    if re.search(r"\b(retired|in (our|my) (60s|70s|80s)|senior)\b", lowered):
        state.traveler_type = "older travellers"

    # Budget ----------------------------------------------------------------
    if re.search(r"\b(budget|cheap|affordable|tight budget|shoestring|save money)\b", lowered):
        state.budget = "budget"
    if re.search(r"\b(luxur\w+|5.?star|high.?end|splurge|premium)\b", lowered):
        state.budget = "luxury"
    if re.search(r"\bmid.?range\b", lowered):
        state.budget = "mid-range"

    # Arrival / departure ---------------------------------------------------
    from app.core.intent import PLACES

    def place_after(pattern: str) -> str | None:
        match = re.search(pattern, lowered)
        if not match:
            return None
        window = lowered[match.end(): match.end() + 40]
        for place, aliases in PLACES.items():
            if any(alias in window for alias in aliases):
                return place
        return None

    arrival = place_after(r"\b(fly(ing)? into|arriv\w+ (in|at|into)|landing in|land in)\b")
    if arrival:
        state.arrival_city = arrival
    departure = place_after(r"\b(fly(ing)? (out|back|home) (of|from)|depart\w* from|leaving from)\b")
    if departure:
        state.departure_city = departure

    # Destinations ----------------------------------------------------------
    from app.core.intent import extract_destinations

    mentioned = extract_destinations(text)
    negated = []
    for place in mentioned:
        aliases = PLACES.get(place, (place.lower(),))
        for alias in aliases:
            position = lowered.find(alias)
            if position == -1:
                continue
            before = lowered[max(0, position - 45): position]
            if re.search(r"\b(skip|without|not |no |avoid|don'?t want|already (been|visited|did)|"
                         r"rather not|instead of|exclude)\b", before):
                negated.append(place)
            if re.search(r"\b(already (been|visited)|been to)\b", before):
                if place not in state.already_visited:
                    state.already_visited.append(place)
    for place in mentioned:
        if place in negated:
            if place not in state.excluded_destinations:
                state.excluded_destinations.append(place)
            if place in state.destinations:
                state.destinations.remove(place)
        elif place not in state.destinations and place not in state.excluded_destinations:
            state.destinations.append(place)

    # Interests -------------------------------------------------------------
    interest_map = {
        "desert": r"\b(desert|sahara|dunes|camel)\b",
        "culture": r"\b(culture|history|medina|museum|architecture|heritage)\b",
        "food": r"\b(food|eat|cuisine|cooking|restaurant)\b",
        "beach": r"\b(beach|coast|surf|swim)\b",
        "hiking": r"\b(hike|hiking|trek|mountain|atlas|toubkal)\b",
        "shopping": r"\b(shop|souk|carpet|rug|argan)\b",
        "relaxation": r"\b(relax|slow|unwind|chill|spa|hammam|stay put)\b",
        "nightlife": r"\b(nightlife|bars?|clubs?|party)\b",
    }
    for interest, pattern in interest_map.items():
        if re.search(pattern, lowered) and interest not in state.interests:
            state.interests.append(interest)

    # Pace and transport ----------------------------------------------------
    if re.search(r"\b(don'?t want to spend .* (driving|on (the )?(train|road))|hate long drives|"
                 r"not too much driving|relaxed pace|slow(ly)?|stay put|one base|single base)\b", lowered):
        state.travel_pace = "relaxed"
    if re.search(r"\b(pack(ed)? in|see as much|fast paced|cover a lot)\b", lowered):
        state.travel_pace = "fast"
    if re.search(r"\b(by train|take the train|prefer trains?|rail)\b", lowered):
        state.transport_preference = "train"
    if re.search(r"\b(rent(ing)? a car|self.?drive|road trip|drive ourselves)\b", lowered):
        state.transport_preference = "self-drive"
    if re.search(r"\b(private driver|driver|guided tour|tour company|organised tour|organized tour)\b", lowered):
        state.transport_preference = "private driver / tours"
    if re.search(r"\b(no (organised|organized) tours?|don'?t want (a )?tours?|independent)\b", lowered):
        state.transport_preference = "independent"

    # Accommodation ---------------------------------------------------------
    if re.search(r"\briad\b", lowered):
        state.accommodation_preference = "riad"
    if re.search(r"\b(resort|all.?inclusive|hotel with entertainment)\b", lowered):
        state.accommodation_preference = "resort"
    if re.search(r"\bhostel\b", lowered):
        state.accommodation_preference = "hostel"

    # Constraints -----------------------------------------------------------
    constraint_patterns = [
        (r"\bno (climbing|hiking|walking)\b", "no climbing or strenuous walking"),
        (r"\b(phone|handset) is locked\b", "phone is network-locked — eSIM is not an option"),
        (r"\b(wheelchair|mobility (issues|problems)|can'?t walk far)\b", "limited mobility"),
        (r"\b(coeliac|celiac|gluten.?free)\b", "gluten-free diet"),
        (r"\b(vegetarian|vegan)\b", "vegetarian or vegan diet"),
        (r"\b(car seat|baby seat)\b", "needs a child car seat"),
        (r"\b(don'?t want to change hotels|one hotel|same hotel)\b", "prefers not to change hotels often"),
        (r"\b(no (organised|organized) tours?)\b", "does not want organised tours"),
    ]
    for pattern, label in constraint_patterns:
        if re.search(pattern, lowered) and label not in state.constraints:
            state.constraints.append(label)

    return state


EXTRACTOR_PROMPT = """You maintain a structured trip profile for a Morocco travel assistant.

You will be given the trip profile so far and the traveller's newest message.
Return JSON only, with just the fields that the newest message ADDS or CHANGES.
Omit everything else. Never repeat unchanged values.

Fields:
 trip_duration_days (int), travel_dates (str), season (str),
 party_adults (int), party_children (int), children_ages (list of str),
 traveler_type (str), destinations (list), excluded_destinations (list),
 origin, arrival_city, departure_city (str), budget (str),
 interests (list), transport_preference (str), travel_pace (str),
 accommodation_preference (str), constraints (list of str), already_visited (list)

Critical rules:
- If the traveller rejects or corrects something, put it in excluded_destinations or
  constraints so it is never suggested again. A rejected assumption must not come back.
- If they say they have already been somewhere, add it to already_visited.
- Do not infer facts they did not state. An empty object is a correct answer.
- Lists you return are MERGED with what exists, except destinations, which is replaced
  only if they clearly restate the whole plan."""


async def extract_with_model(text: str, current: TripState) -> TripState:
    """Refine trip state with the utility model, merging over the rule pass."""
    from app.core.llm import complete_json

    base = extract_rules(text, current)
    try:
        data: dict[str, Any] = await complete_json(
            EXTRACTOR_PROMPT,
            f"Trip profile so far:\n{json.dumps(current.to_dict(), ensure_ascii=False)}\n\n"
            f"Newest message:\n{text}",
            max_tokens=500,
        )
    except Exception as exc:  # noqa: BLE001
        log.warning("model trip extraction failed, using rules only: %s", exc)
        return base

    if not isinstance(data, dict) or not data:
        return base

    merged = base.to_dict()
    list_fields = {"destinations", "excluded_destinations", "interests", "constraints",
                   "children_ages", "already_visited"}
    for key, value in data.items():
        if key not in TripState.__dataclass_fields__:
            continue
        if key in list_fields and isinstance(value, list):
            existing = merged.get(key, []) or []
            merged[key] = list(dict.fromkeys([*existing, *[str(v) for v in value]]))
        elif value not in (None, "", []):
            merged[key] = value

    state = TripState.from_dict(merged)
    # An excluded destination outranks a wanted one: corrections win.
    state.destinations = [d for d in state.destinations if d not in state.excluded_destinations]
    return state
