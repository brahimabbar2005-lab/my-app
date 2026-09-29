"""Retrieval over the ComeMorocco content map.

Two-stage scoring:

1. **Lexical (BM25)** over title, SEO fields, excerpt, keywords, topics,
   destinations and the pre-written "related traveler questions". This runs
   locally with no API call, which keeps retrieval off the latency budget and
   makes the eval harness reproducible.

2. **Metadata boosts** using the columns the content map already carries:
   destination match, intent match, editorial priority, and how well the page
   supports AI answers. A page about Marrakech hotels should not win a
   transport question just because it repeats the city name.

An embedding backend can be layered on top later via `HybridIndex`; the
interface is the same, so nothing downstream changes.
"""
from __future__ import annotations

import math
import re
from collections import Counter
from dataclasses import dataclass
from typing import Any, Iterable

from app.core.lexicon import fold

TOKEN_RE = re.compile(r"[a-z0-9]+")

STOPWORDS = {
    "a", "about", "after", "all", "also", "am", "an", "and", "any", "are", "as",
    "at", "be", "been", "before", "being", "best", "between", "but", "by", "can",
    "do", "does", "for", "from", "get", "go", "going", "good", "has", "have",
    "how", "i", "if", "in", "into", "is", "it", "its", "just", "know", "like",
    "me", "more", "most", "much", "my", "need", "no", "not", "of", "on", "one",
    "only", "or", "our", "out", "over", "should", "so", "some", "than", "that",
    "the", "their", "them", "then", "there", "these", "they", "this", "to", "up",
    "us", "use", "very", "want", "was", "we", "what", "when", "where", "which",
    "who", "why", "will", "with", "would", "you", "your", "guide", "morocco",
    "moroccan", "travel", "traveler", "traveller", "trip",
    # Forum filler. These match page titles by accident ("steak place" ->
    # "Top 3 Places to Visit") without saying anything about the subject.
    "place", "places", "spot", "spots", "thing", "things", "anyone", "someone",
    "everyone", "please", "thanks", "hello", "guys", "recommend", "recommendation",
    "recommendations", "advice", "suggestions", "wondering", "looking",
}

# Travellers and the content map do not always use the same word for a place or
# a topic. These are one-way expansions applied to the *query* only.
SYNONYMS: dict[str, tuple[str, ...]] = {
    "marrakesh": ("marrakech",),
    "marrakech": ("marrakesh",),
    "fez": ("fes",),
    "fes": ("fez",),
    "sahara": ("desert", "merzouga", "erg", "chebbi", "chigaga"),
    "desert": ("sahara", "merzouga", "dunes"),
    "merzouga": ("sahara", "desert", "chebbi"),
    "riad": ("accommodation", "hotel", "stay"),
    "riads": ("accommodation", "hotel", "stay"),
    "hotel": ("accommodation", "riad", "stay"),
    "hotels": ("accommodation", "riad", "stay"),
    "hostel": ("accommodation", "budget", "backpacking"),
    "train": ("trains", "oncf", "rail", "transportation", "boraq"),
    "trains": ("train", "oncf", "rail", "transportation"),
    "bus": ("buses", "ctm", "supratours", "transportation"),
    "taxi": ("transportation", "grand", "petit"),
    "drive": ("driving", "car", "rental", "road"),
    "driving": ("car", "rental", "road"),
    "car": ("rental", "driving", "road"),
    "kids": ("family", "children", "child"),
    "children": ("family", "kids"),
    "child": ("family", "kids"),
    "baby": ("family", "children", "toddler"),
    "toddler": ("family", "children"),
    "honeymoon": ("couples", "romantic"),
    "couple": ("couples", "romantic"),
    "cost": ("budget", "money", "price", "prices"),
    "costs": ("budget", "money", "price"),
    "money": ("budget", "cash", "currency", "dirham"),
    "cheap": ("budget", "affordable"),
    "budget": ("money", "cheap", "affordable"),
    "weather": ("season", "seasons", "climate", "temperature"),
    "rain": ("weather", "season"),
    "hot": ("weather", "summer", "heat"),
    "pack": ("packing", "clothes", "clothing"),
    "packing": ("clothes", "clothing", "wear"),
    "wear": ("clothing", "dress", "packing"),
    "safe": ("safety", "scams"),
    "safety": ("safe", "scams"),
    "scam": ("scams", "safety"),
    "food": ("eat", "restaurants", "cuisine", "tagine"),
    "eat": ("food", "restaurants"),
    "hike": ("hiking", "trek", "trekking", "mountains", "atlas"),
    "hiking": ("trek", "mountains", "atlas"),
    "surf": ("surfing", "taghazout", "beach"),
    "beach": ("beaches", "coast", "essaouira", "agadir"),
    "itinerary": ("itineraries", "route", "days"),
    "first": ("timers", "beginner", "beginners"),
    "beginner": ("first", "timers", "beginners"),
    "days": ("itinerary", "itineraries"),
    "visa": ("entry", "requirements", "passport"),
    "sim": ("esim", "connectivity", "data"),
    "esim": ("sim", "connectivity", "data"),
    "hammam": ("spa", "wellness"),
    "shopping": ("souk", "souks", "market"),
    "souk": ("shopping", "market", "medina"),
}


def tokenise(text: str) -> list[str]:
    # Accents are folded so "désert" and "Fès" meet "desert" and "Fes".
    return [t for t in TOKEN_RE.findall(fold(text)) if t not in STOPWORDS and len(t) > 2]


def expand(tokens: Iterable[str]) -> list[str]:
    """Add synonym tokens to a query. Expansions are weighted lower downstream."""
    out = list(tokens)
    for token in list(tokens):
        out.extend(SYNONYMS.get(token, ()))
    return out


@dataclass
class ScoredItem:
    item: dict[str, Any]
    score: float
    lexical: float
    boost: float
    reasons: list[str]
    coverage: float = 0.0
    # Share of the question's non-place terms this page covers. A page that
    # matches only on the city name is not an answer: "best steak place in
    # Marrakech?" used to link the Marrakech *flights* guide, carried over the
    # threshold by destination and editorial boosts alone.
    topical: float = 1.0


class BM25Index:
    """Plain BM25 over the pre-tokenised content items."""

    k1 = 1.4
    b = 0.72

    def __init__(self, items: list[dict[str, Any]]):
        self.items = items
        self.doc_tokens: list[list[str]] = [item.get("tokens") or tokenise(item.get("search_text", "")) for item in items]
        self.doc_freqs: list[Counter] = [Counter(tokens) for tokens in self.doc_tokens]
        self.doc_len = [len(tokens) for tokens in self.doc_tokens]
        self.avg_len = (sum(self.doc_len) / len(self.doc_len)) if self.doc_len else 0.0

        df: Counter = Counter()
        for tokens in self.doc_tokens:
            for token in set(tokens):
                df[token] += 1
        n = max(len(items), 1)
        self.idf = {
            token: math.log(1 + (n - count + 0.5) / (count + 0.5))
            for token, count in df.items()
        }

    def score(self, query_tokens: list[str], weights: dict[str, float] | None = None) -> list[float]:
        weights = weights or {}
        scores = [0.0] * len(self.items)
        counted = Counter(query_tokens)
        for token, q_count in counted.items():
            idf = self.idf.get(token)
            if idf is None:
                continue
            weight = weights.get(token, 1.0) * min(q_count, 2)
            for i, freqs in enumerate(self.doc_freqs):
                tf = freqs.get(token, 0)
                if not tf:
                    continue
                denom = tf + self.k1 * (1 - self.b + self.b * (self.doc_len[i] / (self.avg_len or 1)))
                scores[i] += weight * idf * (tf * (self.k1 + 1)) / denom
        return scores


# A page's title is the most reliable statement of what it is about — more
# reliable than the content map's content_type, which is inconsistent (the
# "Flights to Marrakech" page is typed as a money guide). A page that merely
# mentions the traveller's words in its metadata used to outrank one whose
# title is about exactly what they asked.
TITLE_WEIGHT = 0.55

# The title signal is strongest for short questions, which read like titles
# themselves. Long forum posts contain incidental rare words — "AFCON",
# "family", "last minute" — that collide with titles by chance, so the weight
# tapers once the question has more distinctive terms than a title does.
TITLE_TAPER_FROM = 4

# What a title says the page is about, keyed by the intent that wants it.
# Titles are reliable; the content map's content_type is not (an AFCON hotel
# guide and the flights guide are both mistyped). So topic is read from the
# title, and a page whose title is clearly about something else is penalised.
TOPIC_TERMS: dict[str, tuple[str, ...]] = {
    "TRANSPORTATION": ("transport", "transportation", "getting around", "bus", "buses", "taxi", "taxis",
                       "train", "trains", "transfer", "transfers", "driving", "road trip", "to marrakech",
                       "to fes", "to casablanca"),
    "TRAIN": ("train", "trains", "rail", "oncf", "boraq"),
    "CAR_RENTAL": ("car rental", "rent a car", "renting a car", "driving", "self-drive"),
    "FLIGHT": ("flight", "flights", "airline", "airlines", "airport"),
    "HOTEL": ("hotel", "hotels", "riad", "riads", "hostel", "hostels", "where to stay", "accommodation",
              "stays"),
    "ACTIVITY": ("tour", "tours", "day trip", "day trips", "activities", "things to do", "excursion",
                 "excursions", "experiences", "cooking class", "hammam"),
    "FAMILY": ("kids", "kid-friendly", "family", "families", "children", "child"),
    "DESERT": ("desert", "sahara", "merzouga", "dunes", "erg chebbi", "erg chigaga", "agafay"),
    "FOOD": ("food", "restaurant", "restaurants", "cuisine", "cooking", "dishes", "eat"),
    "RESTAURANT": ("restaurant", "restaurants", "rooftop", "where to eat"),
    "WEATHER": ("weather", "best time", "seasons", "in january", "in february", "in july", "in august",
                "in december", "month-by-month"),
    "PACKING": ("pack", "packing", "what to wear", "dress", "clothing"),
    "BUDGET": ("budget", "cost", "costs", "money", "prices", "cheap", "how far does"),
    "SAFETY": ("safe", "safety", "scam", "scams"),
    "HIKING": ("trek", "trekking", "hike", "hiking", "toubkal", "mountains"),
    "BEACH": ("beach", "beaches", "surf", "surfing", "coast"),
    "SHOPPING": ("shopping", "souk", "souks", "bargaining", "markets"),
    "CULTURE": ("etiquette", "culture", "customs", "manners", "ramadan"),
}

# Asking about trains is asking about transport; a general transport guide is
# on topic for it. Same for a desert tour and an activities page.
TOPIC_PARENTS: dict[str, tuple[str, ...]] = {
    "TRAIN": ("TRANSPORTATION",),
    "CAR_RENTAL": ("TRANSPORTATION",),
    "FLIGHT": ("TRANSPORTATION",),
    "DESERT": ("ACTIVITY",),
    "HIKING": ("ACTIVITY",),
    "RESTAURANT": ("FOOD",),
}

TOPIC_MATCH_BOOST = 0.15
TOPIC_MISMATCH_PENALTY = 0.15


def title_topics(title: str) -> set[str]:
    lowered = f" {title.lower()} "
    return {
        topic for topic, terms in TOPIC_TERMS.items()
        if any(re.search(rf"(?<![a-z]){re.escape(term)}(?![a-z])", lowered) for term in terms)
    }

# "from X to Y", "to Y from X", "between X and Y". Only consulted when the
# question is already about transport and names two places.
ROUTE_SHAPE = re.compile(r"\bfrom\b.+\bto\b|\bto\b.+\bfrom\b|\bbetween\b.+\band\b", re.IGNORECASE)

PRIORITY_BOOST = {"core": 0.22, "important": 0.12, "standard": 0.04, "low": -0.10}
SUPPORT_BOOST = {"strong support": 0.15, "partial support": 0.05, "weak": -0.08, "unclear": -0.12}
LINK_BEHAVIOR_BOOST = {"usually link": 0.06, "link when relevant": 0.02, "do not proactively link": -0.60}

# Maps the internal intent vocabulary onto the content map's "Traveler Intent"
# column so an intent match can boost the right pages.
INTENT_TO_CONTENT_INTENT = {
    "DESTINATION": ("destination discovery", "inspiration"),
    "ITINERARY": ("itinerary planning", "trip planning"),
    "HOTEL": ("accommodation decision", "booking research"),
    "ACTIVITY": ("activity selection", "booking research"),
    "RESTAURANT": ("food recommendation",),
    "FOOD": ("food recommendation",),
    "TRANSPORTATION": ("transportation decision",),
    "TRAIN": ("transportation decision",),
    "FLIGHT": ("transportation decision", "booking research"),
    "CAR_RENTAL": ("transportation decision",),
    "WEATHER": ("weather planning", "packing decision"),
    "PACKING": ("packing decision", "pre-trip preparation"),
    "SAFETY": ("safety concern",),
    "BUDGET": ("budget planning",),
    "CULTURE": ("cultural question",),
    "FAMILY": ("trip planning", "activity selection"),
    "COUPLE": ("trip planning", "inspiration"),
    "SOLO": ("trip planning", "safety concern"),
    "SENIOR": ("trip planning",),
    "DESERT": ("activity selection", "destination discovery"),
    "HIKING": ("activity selection",),
    "BEACH": ("destination discovery", "activity selection"),
    "SHOPPING": ("cultural question", "activity selection"),
    "VISA": ("pre-trip preparation",),
    "BOOKING": ("booking research",),
    "PROBLEM": ("practical problem solving", "during-trip assistance"),
}

# Content types that answer a given intent. A hotel guide is a poor answer to a
# train question even when both mention Marrakech.
INTENT_TO_CONTENT_TYPE = {
    "TRANSPORTATION": ("transportation", "transport"),
    "TRAIN": ("transportation", "transport"),
    "CAR_RENTAL": ("transportation", "transport"),
    "HOTEL": ("hotel", "accommodation"),
    "ACTIVITY": ("activity", "tour", "experience"),
    "DESERT": ("tour", "activity", "desert"),
    "FOOD": ("food", "restaurant", "cooking"),
    "WEATHER": ("weather", "season"),
    "PACKING": ("packing", "weather"),
    "BUDGET": ("money", "budget"),
    "SAFETY": ("safety",),
    "ITINERARY": ("itinerary",),
    "DESTINATION": ("destination",),
    "CULTURE": ("culture",),
}


class ContentIndex:
    """Lexical retrieval plus metadata boosts over the content map."""

    def __init__(self, items: list[dict[str, Any]]):
        self.items = items
        self.bm25 = BM25Index(items)
        # Every term that exists somewhere in the corpus (used to keep only
        # meaningful words from non-English queries, see core/lexicon.py).
        self.known_terms: set[str] = set(self.bm25.idf)
        self.title_tokens: list[set[str]] = [set(tokenise(item.get("title") or "")) for item in items]
        self.title_topics: list[set[str]] = [title_topics(item.get("title") or "") for item in items]

    def search(
        self,
        query: str,
        *,
        intents: list[str] | None = None,
        destinations: list[str] | None = None,
        limit: int = 12,
        min_score: float = 0.0,
        include_unlinkable: bool = True,
    ) -> list[ScoredItem]:
        intents = intents or []
        destinations = [d.lower() for d in (destinations or [])]

        # A route question travels between two named places. Car rental is
        # excluded: "pick up and drop off in Casablanca, then the desert" names
        # two places without being a journey between them, and treating it as
        # one suppressed the car rental guide that answers it.
        route = bool({"TRANSPORTATION", "TRAIN", "FLIGHT"} & set(intents)) and bool(ROUTE_SHAPE.search(query))
        base_tokens = tokenise(query)
        expanded = expand(base_tokens)
        # Original query terms outrank synonym expansions.
        weights = {t: 1.0 for t in expanded}
        for token in base_tokens:
            weights[token] = 1.6
        for token in expanded:
            if token not in base_tokens:
                weights.setdefault(token, 0.55)

        lexical = self.bm25.score(expanded, weights)
        top = max(lexical) if lexical else 0.0
        if top <= 0:
            top = 1.0

        # Normalising by the top hit alone makes the best result score 1.0 even
        # when nothing on the site is relevant. Coverage — how much of what the
        # traveller actually asked appears in the page — gives an absolute
        # reading, so "no good match" stays distinguishable from "good match".
        #
        # Coverage is measured over the most discriminative terms rather than
        # every token, because travellers write long posts. A 90-word question
        # about Merzouga is still a question about Merzouga, and demanding that
        # a page echo 40% of ninety words would mark every real question a gap.
        key_tokens = sorted(set(base_tokens), key=lambda t: self.bm25.idf.get(t, 0.0), reverse=True)[:8]
        base_set = set(key_tokens)

        place_tokens: set[str] = set()
        for dest in destinations:
            for token in tokenise(dest):
                place_tokens.add(token)
                place_tokens.update(SYNONYMS.get(token, ()))
        subject_tokens = base_set - place_tokens
        place_is_subject = bool({"DESTINATION", "ITINERARY"} & set(intents)) and bool(destinations)

        wanted_intents = set()
        for intent in intents:
            wanted_intents.update(INTENT_TO_CONTENT_INTENT.get(intent, ()))
        question_topics = {intent for intent in intents if intent in TOPIC_TERMS}
        for intent in list(question_topics):
            question_topics.update(TOPIC_PARENTS.get(intent, ()))

        wanted_types: set[str] = set()
        for intent in intents:
            wanted_types.update(INTENT_TO_CONTENT_TYPE.get(intent, ()))

        results: list[ScoredItem] = []
        for i, item in enumerate(self.items):
            if not include_unlinkable and item.get("link_behavior", "").lower() == "do not proactively link":
                continue

            normalised = lexical[i] / top  # 0..1 within this query
            if base_set:
                matched = base_set & set(self.bm25.doc_freqs[i])
                coverage = len(matched) / len(base_set)
            else:
                coverage = 0.0
            # A page that ranks top but only echoes one word of the question is
            # not a good recommendation, however well it ranks relatively.
            relevance = normalised * (0.25 + 0.75 * coverage)
            boost = 0.0
            reasons: list[str] = []

            # Title
            if base_set:
                title = self.title_tokens[i]
                in_title = sum(
                    1 for token in base_set
                    if token in title or any(syn in title for syn in SYNONYMS.get(token, ()))
                )
                title_coverage = in_title / len(base_set)
                taper = min(1.0, TITLE_TAPER_FROM / len(base_set))
                boost += TITLE_WEIGHT * taper * title_coverage
                if title_coverage >= 0.5:
                    reasons.append("title match")

            # Destination
            item_dests = {
                (item.get("primary_destination") or "").lower(),
                *[d.lower() for d in item.get("related_destinations", [])],
            }
            item_dests.discard("")
            if not destinations:
                # No city named: the country is the destination. Without this,
                # country-wide questions (weather, packing, money, visas) could
                # never earn the +0.30 that city questions get for free, and the
                # link threshold — calibrated with that boost present — left
                # them systematically unlinked.
                if (item.get("primary_destination") or "").lower() in {"morocco", ""}:
                    boost += 0.30
                    reasons.append("country-wide match")
            if destinations:
                # A journey is defined by both ends. For "train from Marrakech
                # to Fes", a Casablanca–Marrakech page is not half right, it is
                # a different route, so it gets the mismatch penalty.
                is_route = route and len(destinations) >= 2
                matched_all = all(d in item_dests for d in destinations)
                matched_any = any(d in item_dests for d in destinations)
                if is_route and matched_any and not matched_all:
                    boost -= 0.22
                    reasons.append("destination mismatch")
                elif matched_any:
                    boost += 0.30
                    reasons.append("destination match")
                elif (item.get("primary_destination") or "").lower() in {"morocco", ""}:
                    # A country-wide guide is a fair answer about any city.
                    # Judged on the primary destination: most city pages also
                    # list "Morocco" as related, and that used to let a
                    # Casablanca–Marrakech page escape the mismatch penalty on
                    # a question about Rabat and Tangier.
                    boost += 0.04
                else:
                    # Wrong city is a strong negative: it is the most common
                    # way a link recommendation goes visibly wrong.
                    boost -= 0.22
                    reasons.append("destination mismatch")

            # Intent
            # Scaled by how specific the page's tagging is. Some pages in the
            # content map carry nearly every intent — the flights guide has 9
            # — and a tag that applies to everything signals nothing.
            item_intents = {i2.lower() for i2 in item.get("traveler_intents", [])}
            if wanted_intents and item_intents & wanted_intents:
                boost += 0.16 * min(1.0, 3 / len(item_intents))
                reasons.append("intent match")

            # Content type
            # Title topic
            # Measured as overlap, not presence: "9 Best Family Hotels" shares
            # FAMILY with a question about family day trips, but it is mainly
            # a hotel page, which nobody asked for. A page that is only about
            # what was asked scores highest.
            page_topics = self.title_topics[i]
            if question_topics and page_topics:
                shared = question_topics & page_topics
                if shared:
                    overlap = len(shared) / len(question_topics | page_topics)
                    boost += TOPIC_MATCH_BOOST * 2 * overlap
                    reasons.append("topic in title")
                else:
                    boost -= TOPIC_MISMATCH_PENALTY
                    reasons.append("different topic")

            # Content type: kept, but light — it is often wrong in the map.
            content_type = (item.get("content_type") or "").lower()
            if wanted_types and any(t in content_type for t in wanted_types):
                boost += 0.08
                reasons.append("content type match")
            elif wanted_types and content_type and content_type != "other":
                boost -= 0.03

            # Editorial signals already in the content map
            boost += PRIORITY_BOOST.get((item.get("priority") or "").lower(), 0.0)
            boost += SUPPORT_BOOST.get((item.get("ai_content_support") or "").lower(), 0.0)
            boost += LINK_BEHAVIOR_BOOST.get((item.get("link_behavior") or "").lower(), 0.0)

            if subject_tokens:
                doc = self.bm25.doc_freqs[i]
                title = self.title_tokens[i]
                hits = sum(
                    1 for token in subject_tokens
                    if token in doc or token in title
                    or any(syn in doc or syn in title for syn in SYNONYMS.get(token, ()))
                )
                topical = hits / len(subject_tokens)
            else:
                # The question is only a place ("Chefchaouen?"), so the place
                # is the subject.
                topical = 1.0
            if "topic in title" in reasons:
                topical = max(topical, 0.5)
            # "48 hours in Casablanca?" — when the question is about spending
            # time in a place, the place is the subject, and that city's own
            # guide is the answer even if it never says "hours".
            if place_is_subject and (item.get("primary_destination") or "").lower() in destinations:
                topical = max(topical, 1.0)
            # A route question is about the journey. "Marrakech vs Agadir: 7 Key
            # Differences" names both cities but helps choose between them, not
            # travel between them.
            if route and len(destinations) >= 2 and not ({"TRANSPORTATION", "TRAIN", "FLIGHT"} & page_topics):
                topical = 0.0

            score = relevance + boost
            if score < min_score:
                continue
            results.append(
                ScoredItem(item=item, score=round(score, 4), lexical=round(relevance, 4),
                           boost=round(boost, 4), coverage=round(coverage, 3), reasons=reasons,
                           topical=round(topical, 3))
            )

        results.sort(key=lambda r: r.score, reverse=True)
        return results[:limit]
