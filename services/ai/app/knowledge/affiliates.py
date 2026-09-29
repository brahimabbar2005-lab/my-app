"""Decides when a commercial recommendation is appropriate, and which one.

The affiliate map's most important column is "When NOT to Recommend". This
module encodes those gates as code so that revenue pressure cannot leak into
the answer through prompt drift.

The rule the whole file exists to enforce:

    An affiliate link is never recommended simply because it exists.

Gating happens in three steps:

1. **Intent gate** — the traveller has to be asking to book, compare or
   arrange something. "What should I see in Marrakech?" is deliberately a
   no-affiliate question, and that is encoded as a rule, not a judgement call.
2. **Category gate** — the request has to map onto a category we actually
   have inventory for.
3. **Match gate** — for activities, the destination has to match. A Fes
   question never returns an Agadir surf lesson.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from app.schemas import AffiliateCard, Classification, TripState
from app.core.lexicon import bridge

DISCLOSURE = "Partner link — ComeMorocco may earn a commission if you book through it."

# Phrases that show the traveller wants to arrange something now, rather than
# understand something. Without one of these (or an explicit booking intent)
# no affiliate is shown.
BOOKING_PHRASES = re.compile(
    r"\b("
    r"book|booking|reserve|reservation|where can i (get|buy|book|find|hire|rent)|"
    r"how (do|can) i (book|rent|hire|arrange|get)|recommend a (company|tour|driver|operator)|"
    r"which (company|operator|tour|site|app)|compare|cheapest|best deal|deals?|"
    r"rent(al)?|hire|pre-?book|tickets?|sign up|buy"
    r")\b",
    re.IGNORECASE,
)

# Advice-seeking framings. These ask "is this a good idea?", not "where do I
# get one?" — and the affiliate map says to answer them honestly first.
ADVISORY = re.compile(
    r"\b(should (i|we)|do (i|we) (need|have to)|is it worth|worth (it|renting|hiring|booking)|"
    r"would you (recommend|rent|hire)|what do you think about|is it (a )?good idea|"
    r"do (i|we) need to (book|rent|hire)|better to)\b",
    re.IGNORECASE,
)

# Unambiguous "I have decided, where do I get it" framings, which override the
# advisory guard when both appear.
EXPLICIT_BOOKING = re.compile(
    r"\b(where can i (book|rent|hire|buy)|i want to (book|rent|hire)|"
    r"i'?ve decided|i'?m going to (book|rent|hire)|how do i book|link to book|"
    r"show me (options|some options)|compare (prices|options))\b",
    re.IGNORECASE,
)

# Categories in the affiliate map, mapped to the triggers that open them.
CATEGORY_TRIGGERS: dict[str, dict[str, Any]] = {
    "Car Rental": {
        "intents": {"CAR_RENTAL"},
        "keywords": ("rent a car", "car rental", "hire a car", "self drive", "self-drive", "rental car"),
    },
    "Airport Transfer": {
        "intents": set(),
        "keywords": ("airport transfer", "airport pickup", "pick us up", "pick me up from the airport",
                     "transfer from the airport", "arrival transfer", "car seat", "pre-booked transfer"),
    },
    "Private Transfer": {
        "intents": set(),
        "keywords": ("private transfer", "private driver", "book a driver", "door to door", "door-to-door"),
    },
    "Accommodation": {
        "intents": {"HOTEL"},
        "keywords": ("book a hotel", "book a riad", "book a room", "booking.com", "find a hotel",
                     "find a riad", "book accommodation", "reserve a room"),
    },
    "Hostels": {
        "intents": set(),
        "keywords": ("hostel", "hostels", "dorm", "backpacker accommodation"),
    },
    "Tours & Activities": {
        "intents": {"ACTIVITY", "DESERT"},
        "keywords": ("book a tour", "desert tour", "sahara tour", "day trip", "excursion", "guided tour",
                     "camel ride", "cooking class", "quad", "hot air balloon", "surf lesson", "hammam"),
    },
    "Attractions": {
        "intents": set(),
        "keywords": ("tickets", "skip the line", "skip-the-line", "entry ticket", "audio tour", "museum ticket"),
    },
    "Flights": {
        "intents": {"FLIGHT"},
        "keywords": ("find flights", "book a flight", "cheap flights", "flight search", "fly into", "flights to"),
    },
    "Connectivity / eSIM": {
        "intents": set(),
        "keywords": ("esim", "e-sim", "sim card", "mobile data", "phone data", "stay connected", "roaming"),
    },
    "Travel Insurance": {
        "intents": set(),
        "keywords": ("travel insurance", "insured", "insurance policy", "medical cover"),
    },
    "Flight Compensation": {
        "intents": set(),
        # Deliberately narrow: only after an actual disruption AND a
        # compensation question. Never during planning.
        "keywords": ("compensation", "claim against the airline", "delayed flight", "cancelled flight",
                     "denied boarding", "flight was cancelled", "flight was delayed"),
        "requires": ("compensat", "claim", "refund", "entitled"),
    },
    "Luggage Storage": {
        "intents": set(),
        "keywords": ("luggage storage", "store my luggage", "leave my bags", "leave our bags",
                     "left luggage", "bag storage"),
    },
    "Ride-hailing": {
        "intents": set(),
        "keywords": ("ride hailing", "ride-hailing", "indrive", "uber", "careem", "taxi app", "bolt"),
    },
    "VPN / Privacy": {
        "intents": set(),
        "keywords": ("vpn", "public wifi security"),
    },
    "Password Manager": {
        "intents": set(),
        "keywords": ("password manager",),
    },
}

# specific category -> broader categories it should silence
SUPPRESSES: dict[str, set[str]] = {
    "Flight Compensation": {"Flights"},
    "Luggage Storage": {"Airport Transfer", "Flights"},
    "Attractions": {"Tours & Activities"},
    "Hostels": {"Accommodation"},
}

# Activity category → the words that mean the traveller wants that thing.
ACTIVITY_KEYWORDS: dict[str, tuple[str, ...]] = {
    # Two-word phrases outweigh "from marrakech" (a Day Trip signal), so "desert
    # tour from Marrakech" is not answered with waterfall day trips.
    "Desert Tour": ("desert", "sahara", "merzouga", "erg chebbi", "erg chigaga", "agafay", "dunes",
                    "desert tour", "desert trip", "desert excursion", "sahara tour", "sahara trip"),
    "Camel Ride": ("camel", "camel ride", "camel trek"),
    "Cooking Class": ("cooking class", "cooking", "learn to cook", "tagine class"),
    "Day Trip": ("day trip", "excursion", "from marrakech", "from agadir", "ourika", "ouzoud",
                 "ait benhaddou", "ait ben haddou", "essaouira day"),
    "Water Activity": ("surf", "surfing", "surf lesson", "boat", "cruise", "kayak"),
    "Adventure": ("quad", "buggy", "sandboard", "sand boarding", "balloon", "zip line", "atv"),
    "Mountain Activity": ("trek", "trekking", "hike", "hiking", "toubkal", "atlas", "gorge"),
    "Cultural Tour": ("city tour", "guided tour", "medina tour", "walking tour", "guide"),
    "Food Tour": ("food tour", "street food", "food walk", "tasting"),
    "Hammam / Wellness": ("hammam", "spa", "massage", "wellness"),
    "Historical / Sightseeing": ("museum", "heritage", "historical", "volubilis", "ruins"),
    "Airport Transfer": ("airport transfer", "airport pickup"),
    "Excursion": ("excursion", "stargazing", "star gazing", "lagoon"),
}

DESTINATION_ALIASES = {
    "marrakech": ("marrakech", "marrakesh"),
    "agadir": ("agadir", "taghazout", "tamraght"),
    "essaouira": ("essaouira",),
    "fes": ("fes", "fez"),
    "merzouga": ("merzouga", "erg chebbi", "sahara"),
    "chefchaouen": ("chefchaouen", "chaouen"),
    "casablanca": ("casablanca",),
    "rabat": ("rabat",),
    "tangier": ("tangier", "tanger"),
    "dakhla": ("dakhla",),
    "ouarzazate": ("ouarzazate", "ait benhaddou", "ait ben haddou"),
}


@dataclass
class AffiliateDecision:
    cards: list[AffiliateCard] = field(default_factory=list)
    reason_blocked: str | None = None
    considered: list[str] = field(default_factory=list)


def _text_of(messages: list[str]) -> str:
    return " ".join(messages).lower()


def _destination_matches(activity_destination: str | None, wanted: list[str]) -> bool:
    if not wanted:
        return False
    if not activity_destination:
        return False
    haystack = activity_destination.lower()
    for dest in wanted:
        for alias in DESTINATION_ALIASES.get(dest.lower(), (dest.lower(),)):
            if alias in haystack:
                return True
    return False


def detect_categories(question: str, classification: Classification) -> list[str]:
    """Which affiliate categories, if any, the question actually opens."""
    text = question.lower()
    hits: list[str] = []
    for category, rule in CATEGORY_TRIGGERS.items():
        keyword_hit = any(keyword in text for keyword in rule["keywords"])
        intent_hit = bool(rule["intents"] & set(classification.intents))
        if not (keyword_hit or intent_hit):
            continue
        required = rule.get("requires")
        if required and not any(token in text for token in required):
            continue
        hits.append(category)

    # When a specific category fires, the broader one it sits inside is noise.
    # Someone whose flight was cancelled wants a compensation claim, not a
    # flight search.
    for specific, broader in SUPPRESSES.items():
        if specific in hits:
            hits = [h for h in hits if h not in broader or h == specific]
    return hits


def select_affiliates(
    question: str,
    classification: Classification,
    trip: TripState,
    programs: list[dict[str, Any]],
    activities: list[dict[str, Any]],
    *,
    enabled: bool = True,
    max_cards: int = 2,
) -> AffiliateDecision:
    """Return commercial recommendations, or none, with the reason recorded."""
    if not enabled:
        return AffiliateDecision(reason_blocked="affiliates disabled by configuration")

    # PROBLEM covers "my flight was cancelled", "is the road flooded" — someone
    # with a problem wants help, not a shopping link.
    blocked_intents = {"OFF_TOPIC", "GREETING", "SAFETY", "VISA", "IMPOSSIBLE_ACTION", "PROBLEM"}
    if blocked_intents & set(classification.intents):
        return AffiliateDecision(reason_blocked="intent category never carries an affiliate")

    question = bridge(question, classification.language)
    text = question.lower()
    categories = detect_categories(question, classification)
    if not categories:
        return AffiliateDecision(reason_blocked="no affiliate category triggered")

    # "Should I rent a car?" is a request for advice, not for a rental site.
    # The affiliate map is explicit: answer the travel question honestly first,
    # and only show options if they come back wanting them.
    if ADVISORY.search(question) and not EXPLICIT_BOOKING.search(question):
        return AffiliateDecision(
            reason_blocked="advisory question — answer it before offering anything to book",
            considered=categories,
        )

    # The traveller must be trying to arrange something. This is the rule that
    # keeps "what should I see in Marrakech?" affiliate-free.
    #
    # Only "high" counts on its own. "Medium" is what merely mentioning a tour
    # or a hotel produces, and someone saying "we have a tour booked already"
    # must not be sold a tour — so medium needs an explicit booking phrase too.
    commercial = classification.commercial_intent == "high"
    if not (commercial or BOOKING_PHRASES.search(question)):
        return AffiliateDecision(
            reason_blocked="informational question — traveller is not trying to book anything",
            considered=categories,
        )

    cards: list[AffiliateCard] = []
    destinations = classification.destinations or trip.destinations

    # --- activity-level matches first (more specific than a program) --------
    if "Tours & Activities" in categories or "Attractions" in categories:
        # Score each activity category by how specifically the question matches
        # it. "Desert tour from Marrakech" hits both "Desert Tour" (via
        # "desert", "sahara") and "Day Trip" (via "from marrakech"), and
        # returning a waterfall day trip to someone asking about the Sahara is
        # exactly the failure the affiliate map warns about. Longer, more
        # specific keyword hits win.
        category_scores: dict[str, float] = {}
        for category, words in ACTIVITY_KEYWORDS.items():
            score = 0.0
            for word in words:
                if word in text:
                    # A two-word phrase is a far stronger signal than one word.
                    score += 1.0 + 0.5 * word.count(" ")
            if score:
                category_scores[category] = score

        if category_scores and destinations:
            best = max(category_scores.values())
            # Only consider categories within reach of the strongest signal.
            wanted = {c for c, s in category_scores.items() if s >= best - 0.5}

            matches = [
                activity
                for activity in activities
                if activity.get("usable")
                and activity.get("category") in wanted
                and _destination_matches(activity.get("destination"), destinations)
            ]
            matches.sort(key=lambda a: category_scores.get(a.get("category"), 0.0), reverse=True)

            seen_urls: set[str] = set()
            for activity in matches:
                if len(cards) >= max_cards:
                    break
                if activity["url"] in seen_urls:
                    # The affiliate map flags 12 short links shared across 25
                    # activities; never show the same URL twice.
                    continue
                seen_urls.add(activity["url"])
                cards.append(
                    AffiliateCard(
                        affiliate_id=activity["id"],
                        name=activity["name"],
                        category=activity.get("category") or "Activity",
                        url=activity["url"],
                        label=activity["name"],
                        reason=f"matches {activity.get('category', 'activity')} in {activity.get('destination')}",
                        disclosure=DISCLOSURE,
                    )
                )

    # --- program-level matches ---------------------------------------------
    if len(cards) < max_cards:
        for program in programs:
            if len(cards) >= max_cards:
                break
            if not program.get("usable"):
                continue
            if program.get("category") not in categories:
                continue
            # One card per category: two car-rental comparison sites in one
            # answer is noise, not choice.
            if any(card.category == program["category"] for card in cards):
                continue
            cards.append(
                AffiliateCard(
                    affiliate_id=program["id"],
                    name=program["name"],
                    category=program["category"],
                    url=program["url"],
                    label=f"Compare {program['category'].lower()} options",
                    reason=program.get("use_case") or program["category"],
                    disclosure=DISCLOSURE,
                )
            )

    if not cards:
        return AffiliateDecision(
            reason_blocked="category triggered but nothing matched destination/activity",
            considered=categories,
        )

    return AffiliateDecision(cards=cards, considered=categories)
