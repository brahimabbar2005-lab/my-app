"""Tests for the parts of the pipeline that must not drift.

These run without an API key. That is the point: classification, retrieval,
link selection, affiliate gating, trip state and the output scanner are all
deterministic, so a regression in any of them is caught on every commit rather
than on a nightly model run.

The model's prose is not tested here — it is graded by eval/harness.py against
the golden dataset.
"""
from __future__ import annotations

import pytest

from app.core.intent import classify_rules, extract_destinations
from app.core.language import detect_language
from app.core.safety import check_input, scan_output
from app.core.trip_state import extract_rules
from app.knowledge.affiliates import select_affiliates
from app.knowledge.links import detect_content_gap, select_links
from app.knowledge.loader import get_knowledge_base
from app.knowledge.retriever import get_retriever
from app.schemas import TripState


@pytest.fixture(scope="module")
def retriever():
    return get_retriever()


@pytest.fixture(scope="module")
def kb():
    return get_knowledge_base()


def answer_for(retriever, question: str):
    """Run the deterministic stages and return what would be rendered."""
    classification = classify_rules(question)
    candidates = retriever.retrieve(question, classification)
    links = select_links(candidates, classification)
    affiliates = select_affiliates(
        question, classification, TripState(), retriever.kb.programs, retriever.kb.activities
    )
    return classification, candidates, links, affiliates


# ---------------------------------------------------------------- knowledge
class TestKnowledgeBase:
    def test_loads_expected_volumes(self, kb):
        assert len(kb.items) == 240
        assert len(kb.programs) == 27
        assert len(kb.activities) == 77
        assert len(kb.golden_questions) == 213

    def test_every_item_has_a_usable_url(self, kb):
        for item in kb.items:
            assert item["url"].startswith("http"), item["id"]

    def test_unusable_affiliates_are_marked(self, kb):
        """Kiwi.com has no affiliate link in the source — only a widget.

        The source is explicit that a link must not be invented for it, so it
        must never be selectable.
        """
        kiwi = next(p for p in kb.programs if p["name"] == "Kiwi.com")
        assert kiwi["usable"] is False
        assert kiwi["url"] is None

    def test_thin_pages_are_not_linkable(self, kb):
        linkable_ids = {item["id"] for item in kb.linkable_items()}
        contact = next((i for i in kb.items if "contact" in i["url"]), None)
        if contact:
            assert contact["id"] not in linkable_ids


# --------------------------------------------------------------- language
class TestLanguage:
    @pytest.mark.parametrize(
        "text,expected",
        [
            ("What's the best time to visit Marrakech?", "en"),
            ("Quel est le meilleur moment pour visiter Marrakech ?", "fr"),
            ("Combien de jours faut-il prévoir pour le désert ?", "fr"),
            ("¿Cuántos días necesito en Marrakech?", "es"),
            ("شنو أحسن وقت نزور فيه مراكش؟", "ary"),
            ("ما هو أفضل وقت لزيارة المغرب؟", "ar"),
        ],
    )
    def test_detects_language(self, text, expected):
        assert detect_language(text) == expected

    def test_english_with_a_french_loanword_stays_english(self):
        # "des" and "une" appear in English travel writing often enough that a
        # single hit must not flip the language.
        assert detect_language("We booked a riad in the medina des Fes area") == "en"


# ------------------------------------------------------------ classification
class TestClassification:
    def test_detects_impossible_actions(self):
        for question in ("Book me a flight to Marrakech",
                         "Can you cancel my hotel reservation?",
                         "Check my booking for next week"):
            assert "IMPOSSIBLE_ACTION" in classify_rules(question).intents, question

    def test_detects_live_data_questions(self):
        for question in ("Is the train running tomorrow?",
                         "What's the weather in Marrakech today?",
                         "How much should I tip a guide?"):
            assert classify_rules(question).needs_live_data is True, question

    def test_stable_questions_are_not_live(self):
        for question in ("Is Fes worth visiting?",
                         "What is a riad?",
                         "How many days do I need in Marrakech?"):
            assert classify_rules(question).needs_live_data is False, question

    def test_off_topic(self):
        assert "OFF_TOPIC" in classify_rules("Who won yesterday's football match?").intents
        assert "OFF_TOPIC" in classify_rules("Write me some Python code").intents

    def test_morocco_questions_are_never_off_topic(self):
        for question in ("Is Chefchaouen worth it?", "Tell me about Merzouga", "hammam?"):
            assert "OFF_TOPIC" not in classify_rules(question).intents, question

    def test_greeting_is_not_a_travel_question(self):
        assert classify_rules("hi").intents == ["GREETING"]
        assert classify_rules("Bonjour").intents == ["GREETING"]

    def test_itinerary_questions_are_complex(self):
        result = classify_rules(
            "We have 15 days and want Marrakech, Fes, Chefchaouen and the Sahara. Can you plan it?"
        )
        assert result.complexity == "complex"
        assert "ITINERARY" in result.intents

    def test_extracts_destinations(self):
        found = extract_destinations("Flying into Casablanca then Marrakesh and the desert")
        assert "Casablanca" in found
        assert "Marrakech" in found
        assert "Sahara Desert" in found


# -------------------------------------------------------------- trip state
class TestTripState:
    def test_captures_duration_and_party(self):
        state = extract_rules("We have 10 days, 2 adults and 2 children aged 4 and 7", TripState())
        assert state.trip_duration_days == 10
        assert state.party_adults == 2
        assert state.party_children == 2
        assert state.children_ages == ["4", "7"]
        assert state.traveler_type == "family"

    def test_a_leg_length_is_not_the_trip_length(self):
        state = extract_rules("Should I spend 2 nights in Merzouga?", TripState())
        assert state.trip_duration_days is None

    def test_carries_context_across_turns(self):
        state = extract_rules("I'm going to Morocco for 12 days", TripState())
        state = extract_rules("I'm travelling with my wife", state)
        state = extract_rules("Would you add Fes?", state)
        assert state.trip_duration_days == 12
        assert state.traveler_type == "couple"
        assert "Fes" in state.destinations

    def test_rejections_are_remembered(self):
        """MT-001: a rejected assumption must not come back."""
        state = extract_rules("10 days in Morocco, I'd like the desert", TripState())
        state = extract_rules("Actually we want to skip Casablanca", state)
        assert "Casablanca" in state.excluded_destinations
        assert "Casablanca" not in state.destinations

    def test_already_visited_is_tracked(self):
        """MT-010: do not propose somewhere they have already been."""
        state = extract_rules("I've already been to Essaouira", TripState())
        assert "Essaouira" in state.already_visited

    def test_hard_constraints_are_captured(self):
        """MT-004: an eSIM is not an answer for a network-locked phone."""
        state = extract_rules("My phone is locked so I can't use an eSIM", TripState())
        assert any("locked" in c for c in state.constraints)

        state = extract_rules("No climbing please, we just want the views", TripState())
        assert any("climbing" in c for c in state.constraints)

    def test_relaxed_pace_is_detected(self):
        state = extract_rules("We don't want to spend half the trip driving", TripState())
        assert state.travel_pace == "relaxed"


# ------------------------------------------------------------------ safety
class TestSafety:
    def test_refuses_drug_sourcing(self):
        verdict = check_input("Where can I buy hash in Marrakech?", classify_rules("x"))
        assert verdict.allow is False
        assert "illegal" in (verdict.refusal or "").lower()

    def test_allows_ordinary_questions(self):
        verdict = check_input("Is Marrakech safe at night?", classify_rules("x"))
        assert verdict.allow is True

    def test_defers_on_visas(self):
        verdict = check_input("Do I need a visa for Morocco?", classify_rules("x"))
        assert verdict.allow is True
        assert "consulate" in (verdict.guidance or "").lower()

    def test_catches_fabricated_experience(self):
        issues = scan_output("I went to Merzouga last year and the camp was lovely.")
        assert any(i["code"] == "fabricated_experience" for i in issues)

    def test_catches_claimed_actions(self):
        issues = scan_output("I've booked your riad for the 4th.")
        assert any(i["code"] == "claimed_action" for i in issues)

    def test_catches_sales_pressure(self):
        issues = scan_output("Book now before it's too late — these sell out fast!")
        assert any(i["code"] == "sales_pressure" for i in issues)

    def test_allows_legitimate_opinions(self):
        """The voice the specs actually want must not trip the scanner."""
        text = (
            "I'd give Merzouga two nights rather than one. The drive from Marrakech is long, "
            "and one night means you arrive, do the camel trek and leave again."
        )
        assert [i for i in scan_output(text) if i["severity"] == "major"] == []


# --------------------------------------------------------------- retrieval
class TestRetrieval:
    def test_strong_and_weak_matches_are_separable(self, retriever):
        """The link thresholds depend on this separation holding."""
        strong = classify_rules("How many days do I need in Marrakech?")
        strong_results = retriever.retrieve("How many days do I need in Marrakech?", strong)

        nonsense = classify_rules("Are there dinosaurs in Morocco?")
        nonsense_results = retriever.retrieve("Are there dinosaurs in Morocco?", nonsense)

        assert strong_results[0].score > 1.5
        assert nonsense_results[0].score < 0.8

    def test_finds_the_obvious_page(self, retriever):
        classification = classify_rules("How many days do I need in Marrakech?")
        results = retriever.retrieve("How many days do I need in Marrakech?", classification)
        assert "marrakech" in results[0].item["title"].lower()

    def test_wrong_destination_is_penalised(self, retriever):
        classification = classify_rules("What should I do in Chefchaouen?")
        results = retriever.retrieve("What should I do in Chefchaouen?", classification)
        top = results[0].item
        destinations = {(top.get("primary_destination") or "").lower(),
                        *[d.lower() for d in top.get("related_destinations", [])]}
        assert "chefchaouen" in destinations or "morocco" in destinations


# --------------------------------------------------------------------- links
class TestLinks:
    def test_respects_the_link_budget(self, retriever):
        for question in ("Is Fes worth visiting?",
                         "I have 15 days, Marrakech, Fes, Chefchaouen and the Sahara. Plan it."):
            _, _, links, _ = answer_for(retriever, question)
            assert len(links.resources) <= 4, question

    def test_no_links_on_off_topic(self, retriever):
        _, _, links, _ = answer_for(retriever, "Who won yesterday's football match?")
        assert links.resources == []

    def test_does_not_repeat_a_link(self, retriever):
        question = "How many days do I need in Marrakech?"
        classification = classify_rules(question)
        candidates = retriever.retrieve(question, classification)
        first = select_links(candidates, classification)
        assert first.resources

        already = {first.resources[0].content_id}
        second = select_links(candidates, classification, already_linked=already)
        assert all(r.content_id not in already for r in second.resources)

    def test_anchor_text_comes_from_the_content_map(self, retriever):
        _, _, links, _ = answer_for(retriever, "Where should I stay in Fes?")
        for resource in links.resources:
            assert resource.anchor_text
            assert "click here" not in resource.anchor_text.lower()

    @pytest.mark.parametrize("question", [
        # Both appear in the dataset README's list of known gaps, and a search
        # of the content map confirms no page covers them.
        "Is Morocco wheelchair accessible? Which cities are easiest with a wheelchair?",
        "What are the private driver day rates in Morocco?",
    ])
    def test_flags_a_genuine_content_gap(self, retriever, question):
        # This used "tipping etiquette in Tafraout", on the assumption that
        # tipping is a gap. It is not quite: the etiquette guide covers
        # tipping, and once titles were weighted the retriever found it.
        classification = classify_rules(question)
        candidates = retriever.retrieve(question, classification)
        assert detect_content_gap(question, candidates, classification) is not None

    def test_does_not_flag_covered_topics(self, retriever):
        question = "How many days do I need in Marrakech?"
        classification = classify_rules(question)
        candidates = retriever.retrieve(question, classification)
        assert detect_content_gap(question, candidates, classification) is None


# ---------------------------------------------------------------- affiliates
class TestAffiliates:
    """The rules in 07_AFFILIATE_MAP that exist to stop this becoming a sales bot."""

    def test_sightseeing_never_carries_an_affiliate(self, retriever):
        """The affiliate map's deliberate 'no affiliate, by design' row."""
        for question in ("What should I see in Marrakech?",
                         "I'm visiting Marrakech for 3 days — what should I do?",
                         "What is Fes known for?"):
            _, _, _, affiliates = answer_for(retriever, question)
            assert affiliates.cards == [], question

    def test_explicit_booking_does(self, retriever):
        _, _, _, affiliates = answer_for(retriever, "Where can I book a Sahara desert tour from Marrakech?")
        assert affiliates.cards
        assert all(c.category for c in affiliates.cards)

    def test_advisory_questions_get_advice_first(self, retriever):
        """'Should I rent a car?' is a question, not a purchase intent."""
        for question in ("Should I rent a car in Morocco?",
                         "Do I need an eSIM for Morocco?",
                         "Is it worth booking a desert tour in advance?"):
            _, _, _, affiliates = answer_for(retriever, question)
            assert affiliates.cards == [], question
            assert "advisory" in (affiliates.reason_blocked or "")

    def test_activity_matches_the_destination(self, retriever):
        """A Fes question must never return an Agadir surf lesson."""
        _, _, _, affiliates = answer_for(retriever, "Where can I book a cooking class in Fes?")
        for card in affiliates.cards:
            assert "agadir" not in card.name.lower()

    def test_desert_request_returns_desert_tours(self, retriever):
        _, _, _, affiliates = answer_for(retriever, "Where can I book a Sahara desert tour from Marrakech?")
        assert any("Desert" in c.category for c in affiliates.cards)

    def test_safety_and_problem_questions_carry_nothing(self, retriever):
        for question in ("Is Morocco safe for solo female travellers?",
                         "Do I need a visa for Morocco?",
                         "Are the roads flooded in the Atlas Mountains right now?"):
            _, _, _, affiliates = answer_for(retriever, question)
            assert affiliates.cards == [], question

    def test_never_shows_an_unusable_program(self, retriever, kb):
        unusable = {p["id"] for p in kb.programs if not p["usable"]}
        for row in kb.golden_questions[:60]:
            _, _, _, affiliates = answer_for(retriever, row["question"])
            assert all(c.affiliate_id not in unusable for c in affiliates.cards)

    def test_every_card_carries_a_disclosure(self, retriever):
        _, _, _, affiliates = answer_for(retriever, "Where can I rent a car in Marrakech?")
        assert affiliates.cards
        for card in affiliates.cards:
            assert "commission" in card.disclosure.lower()

    def test_no_duplicate_urls(self, retriever):
        """The affiliate map flags 12 short links shared across 25 activities."""
        _, _, _, affiliates = answer_for(retriever, "Where can I book a desert tour from Marrakech?")
        urls = [c.url for c in affiliates.cards]
        assert len(urls) == len(set(urls))


# ------------------------------------------------------------ whole pipeline
class TestGoldenSetRegression:
    """Guards over the whole dataset, not a sample."""

    def test_no_affiliate_on_non_commercial_questions(self, retriever, kb):
        non_commercial = [r for r in kb.golden_questions
                          if (r.get("affiliate_relevant") or "No").lower() == "no"]
        leaks = []
        for row in non_commercial:
            _, _, _, affiliates = answer_for(retriever, row["question"])
            if affiliates.cards:
                leaks.append((row["id"], [c.name for c in affiliates.cards]))
        # The dataset is conservative about what counts as commercial, so a
        # small margin is allowed — but not a systematic leak.
        assert len(leaks) / max(len(non_commercial), 1) < 0.07, leaks[:10]

    def test_link_budget_never_exceeded(self, retriever, kb):
        for row in kb.golden_questions:
            _, _, links, _ = answer_for(retriever, row["question"])
            assert len(links.resources) <= 4, row["id"]

    def test_classification_never_crashes(self, retriever, kb):
        for row in kb.golden_questions:
            classification = classify_rules(row["question"])
            assert classification.intents
            assert classification.language
