"""Classify the question before answering it.

A rule pass runs first because it is free, deterministic and testable against
the golden set. It handles the cases that matter most for control flow:
off-topic, impossible actions, live-data requests, commercial intent, and
which destinations are in play.

The model pass is a refinement, not the primary mechanism. If it is
unavailable or slow, the rules still produce a usable classification, so the
service degrades rather than fails.
"""
from __future__ import annotations

import json
import logging
import re
from typing import Any

from app.core.language import detect_language
from app.schemas import Classification, TripState

log = logging.getLogger(__name__)

# --------------------------------------------------------------------------
# Morocco places the assistant knows about. Used for destination extraction and
# for deciding whether a question is actually about Morocco.
# --------------------------------------------------------------------------
PLACES: dict[str, tuple[str, ...]] = {
    "Marrakech": ("marrakech", "marrakesh", "medina of marrakech", "jemaa", "gueliz", "palmeraie"),
    "Fes": ("fes", "fez", "fès"),
    "Chefchaouen": ("chefchaouen", "chaouen", "blue city", "blue town"),
    "Casablanca": ("casablanca", "casa ", "cmn"),
    "Rabat": ("rabat",),
    "Tangier": ("tangier", "tanger", "tangiers"),
    "Essaouira": ("essaouira", "mogador"),
    "Merzouga": ("merzouga", "erg chebbi", "hassilabied"),
    "Agadir": ("agadir", "taghazout", "tamraght", "aourir"),
    "Ouarzazate": ("ouarzazate", "ait benhaddou", "ait ben haddou", "aït benhaddou"),
    "Dades": ("dades", "dadès", "boumalne", "skoura"),
    "Todra": ("todra", "todgha", "tinghir"),
    "Sahara Desert": ("sahara", "desert", "erg chigaga", "zagora", "mhamid", "dunes"),
    "Atlas Mountains": ("atlas mountains", "high atlas", "toubkal", "imlil", "ourika", "ouzoud", "middle atlas"),
    "Meknes": ("meknes", "meknès"),
    "Volubilis": ("volubilis",),
    "Asilah": ("asilah",),
    "Oualidia": ("oualidia",),
    "Dakhla": ("dakhla",),
    "Ifrane": ("ifrane", "azrou"),
    "Safi": ("safi",),
    "El Jadida": ("el jadida", "mazagan"),
    "Tetouan": ("tetouan", "tétouan", "martil", "cabo negro"),
    "Legzira": ("legzira", "sidi ifni", "mirleft"),
    "Tafraout": ("tafraout", "anti-atlas", "anti atlas"),
    "Agafay": ("agafay",),
}

INTENT_PATTERNS: list[tuple[str, str]] = [
    ("ITINERARY", r"\b(itinerar\w*|route|plan(ning)? (a|my|our)? ?trip|day by day|day-by-day|"
                  r"\d+\s*(hours?|days?|nights?|weeks?)\b|what (should|can) (i|we) do (in|for)|"
                  r"how many days|is (this|that|it) doable|does this (plan|route|itinerary))"),
    ("COMPARISON", r"\b(or|versus|vs\.?)\b.*\?|\b(better|which one|compare|difference between|"
                   r"should i (pick|choose)|worth (it|visiting|adding))\b"),
    ("DESTINATION", r"\b(what is .* like|worth visiting|should (i|we) (visit|go to)|where should (i|we) go|"
                    r"things to do|what to see|recommend(ations)? for)\b"),
    ("TRANSPORTATION", r"\b(get (from|to)|travel between|transport|getting around|how do (i|we) (get|reach)|"
                       r"transfer|grand taxi|petit taxi|taxi|bus|ctm|supratours)\b"),
    ("TRAIN", r"\b(train|oncf|al ?boraq|rail|railway)\b"),
    ("FLIGHT", r"\b(flight|flights|fly(ing)? (in|out|to|from)|airport|airline|ryanair|open.?jaw)\b"),
    ("CAR_RENTAL", r"\b(rent(al|ing)? a car|car rental|hire a car|self.?drive|driving (in|around)|road trip)\b"),
    ("HOTEL", r"\b(hotels?|riads?|hostels?|where (should|can|to) (i|we)? ?stay|accommodation|guesthouses?|airbnb|"
              r"place to stay|neighbou?rhood to stay|resorts?)\b"),
    ("ACTIVITY", r"\b(tours?|activity|activities|excursions?|day trips?|cooking class(es)?|hammams?|quads?|"
                 r"balloons?|camels?|surf(ing)?|experiences?|museums?)\b"),
    ("RESTAURANT", r"\b(restaurants?|where to eat|places? to eat|dinner|lunch|breakfast|brunch|rooftops?|"
                   r"cafes?|cafés?|steak(house)?s?|burgers?|pizza|seafood|sushi|bars?)\b"),
    ("FOOD", r"\b(food|eat|dish|dishes|tagine|tajine|couscous|cuisine|street food|vegetarian|vegan|"
             r"gluten|halal|tap water|drink)\b"),
    ("WEATHER", r"\b(weather|temperature|hot|cold|rain|raining|sunny|climate|degrees|forecast|"
                r"in (january|february|march|april|may|june|july|august|september|october|november|december))\b"),
    ("PACKING", r"\b(pack(s|ed|ing)?|what (should|do) i (wear|bring)|clothes|clothing|dress code|shorts|scarf|"
                r"suitcase|luggage)\b"),
    ("SAFETY", r"\b(safe|safety|dangerous|danger|scam|scams|harass|pickpocket|crime|solo woman|"
               r"as a woman|lgbt|gay|queer|risk)\b"),
    ("BUDGET", r"\b(budget|cost|costs|how much|price|prices|expensive|cheap|money|cash|dirham|mad\b|"
               r"atm|exchange|tip|tipping|bargain|haggle)\b"),
    ("CULTURE", r"\b(culture|custom|customs|etiquette|religion|mosque|ramadan|language|arabic|darija|"
                r"french|respectful|offend|tradition)\b"),
    ("FAMILY", r"\b(kids?|child|children|toddler|baby|babies|family|stroller|pushchair|teen|teenager)\b"),
    ("COUPLE", r"\b(my (wife|husband|partner|girlfriend|boyfriend|fianc)|couple|honeymoon|romantic|anniversary)\b"),
    ("SOLO", r"\b(solo|alone|by myself|on my own|travell?ing alone)\b"),
    ("SENIOR", r"\b(senior|elderly|retired|in (our|my) (60s|70s|80s)|\b(6[5-9]|7\d|8\d) ?(years old|yo)\b|"
               r"mobility|wheelchair|walking (is|can be) (hard|difficult))\b"),
    ("DESERT", r"\b(sahara|desert|merzouga|erg chebbi|erg chigaga|dune|dunes|camel trek|desert camp|agafay|zagora)\b"),
    ("HIKING", r"\b(hike|hiking|trek|trekking|toubkal|summit|mountain|gorge|waterfall)\b"),
    ("BEACH", r"\b(beach|beaches|coast|coastal|surf|swim|swimming|sea|ocean)\b"),
    ("SHOPPING", r"\b(shop|shopping|souk|souks|buy|rug|carpet|leather|argan|lantern|souvenir|haggl)\b"),
    ("VISA", r"\b(visa|entry requirement|passport|border|immigration|customs form|consulate|embassy)\b"),
    ("BOOKING", r"\b(book|booking|reserve|reservation|deposit|cancellation|pay(ment)?|paypal|"
                r"where can i (book|buy|get))\b"),
    ("PROBLEM", r"\b(problem|issue|stuck|lost|cancelled|canceled|delayed|missed|refund|complaint|"
                r"went wrong|help me|scammed|overcharged)\b"),
]

# Questions that require information we have not actually checked.
LIVE_DATA_PATTERNS = re.compile(
    r"\b(today|tonight|tomorrow|right now|currently|at the moment|this (week|weekend|month|year)|"
    r"next (week|weekend|month)|last (few |couple of |)(weeks|months|days)|recent(ly)?|these days|"
    r"still (running|operating|open|closed|a thing)|"
    r"available|availability|in stock|open (now|today)|opening hours|schedule|timetable|"
    r"what time|departure time|exchange rate|"
    # Money: any price, fare, rate or tip amount is time-sensitive by nature.
    r"how much (should|do|does|would|is|are|will)|what (should|do) (i|we|you) (pay|tip)|"
    r"(current|typical|average|going|normal|fair) (price|rate|cost|fare)|"
    r"price of|cost of|costs? per|per (day|night|person) (cost|price|rate)|"
    r"is .{0,24}(a )?(reasonable|normal|fair|good|too much|rip.?off) (price|rate|amount)|"
    r"reasonable price|"
    # Rules that change without notice.
    r"(visa|entry) requirement|do i need a visa|vaccin\w*|"
    # Provider recommendations depend on who is operating and at what price now.
    r"recommend (a|an|any|some)? ?(reliable |affordable |good |cheap )?"
    r"(rental|car|company|companies|operator|driver|riad|hotel|agency)|"
    r"withdrawal limit|atm limit|daily limit|"
    r"is (it|the .*) (open|running|operating))\b",
    re.IGNORECASE,
)

# Things the MVP cannot do, however it is asked.
IMPOSSIBLE_PATTERNS = re.compile(
    r"\b(book (me|us|my|our)|make (a|the) (booking|reservation)|reserve (me|us|a table)|"
    r"buy (me|us) (a|the) ticket|cancel my|change my (booking|reservation|flight)|"
    r"check my (booking|reservation|order)|call (them|the hotel)|email (them|the)|"
    r"pay for (this|it|my))\b",
    re.IGNORECASE,
)

HIGH_COMMERCIAL = re.compile(
    r"\b(where can i book|book a|booking a|reserve a|rent a|hire a|compare|cheapest|best deal|"
    r"recommend (a|an) (company|operator|tour|driver|agency)|which (company|operator|site))\b",
    re.IGNORECASE,
)

ACCOMMODATION_IS_CONTEXT = re.compile(
    r"\b(staying (at|in)|we'?re staying|i'?m staying|we are staying|i am staying|"
    r"(already )?booked (a|our|my) (hotel|riad|resort)|our (hotel|riad|resort) is)\b",
    re.IGNORECASE,
)
ACCOMMODATION_REQUEST = re.compile(
    r"\b(where (should|can|to) (i|we)? ?stay|recommend (a|an|some) (hotel|riad|resort|hostel)|"
    r"(which|what) (hotel|riad|area|neighbou?rhood)|book (a|our) (hotel|riad)|best (hotels?|riads?))\b",
    re.IGNORECASE,
)

GREETING = re.compile(r"^\s*(hi|hey|hello|salam|salaam|bonjour|salut|hola|yo|good (morning|afternoon|evening))[\s!.,]*$",
                      re.IGNORECASE)

MOROCCO_HINT = re.compile(
    r"\b(morocco|moroccan|maroc|marrakech|marrakesh|fes|fez|casablanca|rabat|tangier|tanger|"
    r"chefchaouen|essaouira|merzouga|agadir|sahara|atlas|medina|riad|souk|tagine|tajine|dirham|"
    r"ouarzazate|dades|todra|taghazout|dakhla|meknes|volubilis|oncf|ctm|supratours)\b",
    re.IGNORECASE,
)

OFF_TOPIC = re.compile(
    r"\b(football match|premier league|write (me )?(code|a poem|an essay)|python|javascript|"
    r"stock market|crypto|bitcoin|who won|election|recipe for (?!tagine)|my homework|"
    r"capital of (?!morocco)|weather in (paris|london|new york|madrid))\b",
    re.IGNORECASE,
)


_FILLER = {
    "what", "about", "how", "is", "it", "worth", "the", "a", "an", "and", "or", "any",
    "thoughts", "on", "in", "to", "visit", "visiting", "going", "go", "should", "i", "we",
    "tell", "me", "morocco", "like", "there", "anyone", "been", "you", "your", "opinions",
}


def _only_names_places(text: str) -> bool:
    """True when nothing but place names and filler remains."""
    lowered = f" {text.lower()} "
    for aliases in PLACES.values():
        for alias in sorted(aliases, key=len, reverse=True):
            lowered = lowered.replace(alias, " ")
    words = [w for w in re.findall(r"[a-z']+", lowered) if w not in _FILLER and len(w) > 2]
    return not words


def extract_destinations(text: str) -> list[str]:
    lowered = f" {text.lower()} "
    found: list[str] = []
    for place, aliases in PLACES.items():
        if any(alias in lowered for alias in aliases):
            found.append(place)
    # "Sahara Desert" and "Merzouga" both firing is fine and useful; the
    # retriever treats them as separate destination signals.
    return found


def _complexity(text: str, intents: list[str]) -> str:
    words = len(text.split())
    if "ITINERARY" in intents and (words > 25 or re.search(r"\b\d+\s*(day|days|night|nights|week|weeks)\b", text, re.I)):
        return "complex"
    if words > 60:
        return "complex"
    if {"COMPARISON", "ITINERARY", "BUDGET"} & set(intents) or words > 22:
        return "moderate"
    return "simple"


def classify_rules(text: str, language_hint: str | None = None) -> Classification:
    """Deterministic first pass. Always runs."""
    language = detect_language(text, language_hint)

    if GREETING.match(text):
        return Classification(intents=["GREETING"], language=language, complexity="simple")

    intents: list[str] = []
    for name, pattern in INTENT_PATTERNS:
        if re.search(pattern, text, re.IGNORECASE):
            intents.append(name)

    destinations = extract_destinations(text)

    if IMPOSSIBLE_PATTERNS.search(text):
        intents.insert(0, "IMPOSSIBLE_ACTION")

    # "We're staying at a resort — any day trips?" mentions accommodation as
    # context. They have somewhere to stay; the question is about something
    # else, and treating it as a hotel search sends them a hotel list.
    if "HOTEL" in intents and ACCOMMODATION_IS_CONTEXT.search(text) \
            and not ACCOMMODATION_REQUEST.search(text):
        intents.remove("HOTEL")

    # "Marrakech or Fes?" compares places, so it is a destination choice. The
    # guard matters: "train or bus from Marrakech to Fes?" also names two
    # places but is a transport question.
    travel_mode = {"TRANSPORTATION", "TRAIN", "FLIGHT", "CAR_RENTAL"}
    if "COMPARISON" in intents and len(destinations) >= 2 and not travel_mode & set(intents):
        if "DESTINATION" not in intents:
            intents.append("DESTINATION")

    if not intents and not destinations:
        if OFF_TOPIC.search(text) or not MOROCCO_HINT.search(text):
            # Short questions with no Morocco signal and no travel intent are
            # treated as off-topic; the orchestrator re-checks against the
            # conversation before committing to that.
            intents = ["OFF_TOPIC"]
    if OFF_TOPIC.search(text) and not MOROCCO_HINT.search(text):
        intents = ["OFF_TOPIC"]

    # A question that only names a place — "Chefchaouen?", "What about
    # Essaouira?" — is asking what the place is like.
    # Only when the place really is the whole question. "Can I change
    # terminals quickly in Casablanca?" has no recognised intent either, but
    # its subject is terminals, not Casablanca.
    if not intents and destinations and _only_names_places(text):
        intents = ["DESTINATION"]

    if not intents:
        intents = ["GENERAL"]

    commercial = "none"
    if HIGH_COMMERCIAL.search(text):
        commercial = "high"
    elif {"BOOKING", "HOTEL", "CAR_RENTAL", "ACTIVITY", "FLIGHT"} & set(intents):
        commercial = "medium"
    elif {"DESERT", "RESTAURANT"} & set(intents):
        commercial = "low"

    safety_sensitive = bool(
        {"SAFETY", "VISA"} & set(intents)
    ) or bool(re.search(r"\b(medical|medication|insulin|allerg|pregnan|disabilit|accessib|emergency|hospital)\b",
                        text, re.IGNORECASE))

    return Classification(
        intents=list(dict.fromkeys(intents)),
        language=language,
        commercial_intent=commercial,
        needs_live_data=bool(LIVE_DATA_PATTERNS.search(text)),
        safety_sensitive=safety_sensitive,
        complexity=_complexity(text, intents),
        destinations=destinations,
    )


CLASSIFIER_PROMPT = """You classify Morocco travel questions for a travel assistant. \
Return JSON only, no prose.

Schema:
{"intents": [...], "commercial_intent": "none|low|medium|high", "needs_live_data": bool,
 "safety_sensitive": bool, "complexity": "simple|moderate|complex", "destinations": [...]}

Valid intents: DESTINATION ITINERARY HOTEL ACTIVITY RESTAURANT TRANSPORTATION TRAIN FLIGHT
CAR_RENTAL WEATHER PACKING SAFETY BUDGET FOOD CULTURE FAMILY COUPLE SOLO SENIOR DESERT HIKING
BEACH SHOPPING VISA BOOKING COMPARISON PROBLEM GENERAL OFF_TOPIC GREETING IMPOSSIBLE_ACTION

Rules:
- Multiple intents are normal. List the ones that actually drive the answer, most important first.
- needs_live_data is true only when a correct answer depends on something that changes: today's
  weather, a current schedule, live availability, a current price, current entry requirements.
- commercial_intent is "high" only when the traveller is trying to book, hire or compare providers.
  Asking what to see or where to go is not commercial intent.
- IMPOSSIBLE_ACTION when they ask the assistant to perform a booking, cancellation or lookup in
  someone else's system.
- destinations: Moroccan places named or clearly implied, using their common English spelling.
- Consider the conversation so far, not just the latest message."""


async def classify_with_model(
    text: str,
    history: list[dict[str, str]],
    trip: TripState,
    base: Classification,
) -> Classification:
    """Refine the rule pass with the utility model. Falls back silently."""
    from app.core.llm import complete_json

    context = ""
    if history:
        recent = history[-4:]
        context = "\n".join(f"{m['role']}: {m['content'][:300]}" for m in recent)
    trip_line = trip.summary()

    user = (
        (f"Conversation so far:\n{context}\n\n" if context else "")
        + (f"Known trip context: {trip_line}\n\n" if trip_line else "")
        + f"Latest message: {text}"
    )

    try:
        data: dict[str, Any] = await complete_json(CLASSIFIER_PROMPT, user, max_tokens=400)
    except Exception as exc:  # noqa: BLE001 - classification must never break chat
        log.warning("model classification failed, using rules only: %s", exc)
        return base

    if not isinstance(data, dict):
        return base

    intents = [i for i in data.get("intents", []) if isinstance(i, str)]
    merged = list(dict.fromkeys([*intents, *base.intents]))[:6]

    # The rules win on the two decisions with real consequences: we would
    # rather over-detect a live-data question than let the model invent a
    # schedule, and rather under-detect commercial intent than oversell.
    needs_live = bool(data.get("needs_live_data")) or base.needs_live_data
    commercial = data.get("commercial_intent", base.commercial_intent)
    if base.commercial_intent == "none" and commercial == "high":
        commercial = "medium"

    destinations = list(dict.fromkeys([*base.destinations, *[d for d in data.get("destinations", []) if isinstance(d, str)]]))

    return Classification(
        intents=merged or base.intents,
        language=base.language,
        commercial_intent=commercial if commercial in {"none", "low", "medium", "high"} else base.commercial_intent,
        needs_live_data=needs_live,
        safety_sensitive=bool(data.get("safety_sensitive")) or base.safety_sensitive,
        complexity=data.get("complexity", base.complexity) if data.get("complexity") in {"simple", "moderate", "complex"} else base.complexity,
        destinations=destinations,
        notes="model-refined",
    )
