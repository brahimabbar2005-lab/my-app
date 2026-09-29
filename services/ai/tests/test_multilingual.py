"""French and Spanish questions against the English knowledge base.

Added after the app's end-to-end test (docs/ai-audit.md, finding 7): asked in
French for a desert tour from Marrakech, the service linked a hammam guide
and offered no partner options, while the same question in English worked.
The site's content is English, so a French or Spanish question has to reach
the same pages and the same partner options as its English equivalent.

Annotated like tests/test_retrieval_quality.py: acceptable first links, and
titles that must never be linked.
"""

from __future__ import annotations

import pytest

from app.core import safety
from app.core.intent import classify_rules
from app.knowledge.affiliates import select_affiliates
from app.knowledge.index import tokenise
from app.knowledge.links import select_links
from app.knowledge.retriever import get_retriever
from app.schemas import TripState


def links_for(question: str) -> list[str]:
    retriever = get_retriever()
    classification = classify_rules(question)
    decision = select_links(retriever.retrieve(question, classification), classification)
    return [resource.title for resource in decision.resources]


def affiliates_for(question: str) -> list[str]:
    retriever = get_retriever()
    classification = classify_rules(question)
    cards = select_affiliates(
        question, classification, TripState(), retriever.kb.programs, retriever.kb.activities
    )
    return [card.category for card in cards.cards]


# (label, question, acceptable first link, forbidden anywhere)
CASES = [
    (
        "fr: desert tour from Marrakech (the app's failing case)",
        "Où réserver une excursion dans le désert depuis Marrakech ?",
        ["Sahara", "Desert", "Merzouga"],
        ["Hammam"],
    ),
    (
        "fr: days in a city",
        "Combien de jours faut-il à Marrakech ?",
        ["How Many Days in Marrakech"],
        [],
    ),
    (
        "fr: riad or hotel",
        "Riad ou hôtel à Marrakech ?",
        ["Riad vs Hotel"],
        [],
    ),
    (
        "fr: visa",
        "Faut-il un visa pour aller au Maroc ?",
        ["Visa"],
        [],
    ),
    (
        "es: days in a city",
        "¿Cuántos días necesito en Marrakech?",
        ["How Many Days in Marrakech"],
        [],
    ),
    (
        "es: train or bus between cities",
        "¿Tren o autobús de Marrakech a Fez?",
        ["Morocco Trains", "Morocco Transportation"],
        ["Casablanca to Marrakech"],
    ),
    (
        "es: desert tour",
        "¿Dónde reservar una excursión al desierto desde Marrakech?",
        ["Sahara", "Desert", "Merzouga"],
        ["Hammam"],
    ),
]


@pytest.mark.parametrize("label,question,acceptable,forbidden", CASES, ids=[c[0] for c in CASES])
def test_multilingual_retrieval(label, question, acceptable, forbidden):
    titles = links_for(question)
    assert titles, f"{label}: no link"
    assert any(a.lower() in titles[0].lower() for a in acceptable), f"{label}: first link was {titles[0]!r}"
    for bad in forbidden:
        assert not any(bad.lower() in t.lower() for t in titles), (
            f"{label}: linked forbidden {bad!r} in {titles}"
        )


@pytest.mark.parametrize(
    "question",
    [
        "Où réserver une excursion dans le désert depuis Marrakech ?",
        "¿Dónde reservar una excursión al desierto desde Marrakech?",
    ],
)
def test_booking_intent_in_french_and_spanish_opens_desert_tours(question):
    assert "Desert Tour" in affiliates_for(question)


@pytest.mark.parametrize(
    "question",
    [
        "Faut-il réserver un circuit dans le désert à l'avance ?",  # advice, not arranging
        "Est-ce que ça vaut la peine d'aller dans le désert ?",
    ],
)
def test_french_advice_questions_still_get_no_affiliate(question):
    assert affiliates_for(question) == []


def test_accents_are_folded_so_french_and_english_spellings_meet():
    assert "desert" in tokenise("désert")
    assert tokenise("Fès") == tokenise("Fes")


@pytest.mark.parametrize("language", ["fr", "es", "ar"])
def test_fallback_messages_are_localised(language):
    english = safety.fallback("model_unavailable")
    localised = safety.fallback("model_unavailable", language)
    assert localised and localised != english


def test_fallback_defaults_to_english_for_unknown_languages():
    assert safety.fallback("model_unavailable", "xx") == safety.fallback("model_unavailable")


def test_english_desert_tour_from_marrakech_gets_desert_tours_not_day_trips():
    """Pre-existing English bug found while writing the French cases: without
    "Merzouga" in the question, "from marrakech" (a Day Trip signal) outscored
    the single word "desert", and waterfall day trips were offered for a Sahara
    tour — the failure affiliates.py describes as prevented."""
    assert affiliates_for("Where can I book a desert tour from Marrakech?")[0] == "Desert Tour"


def test_english_questions_are_never_bridged():
    from app.core.lexicon import bridge

    question = "Where can I book an excursion from Marrakech?"
    assert bridge(question, "en") == question
