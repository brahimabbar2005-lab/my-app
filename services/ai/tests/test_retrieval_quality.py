"""Retrieval quality, judged by hand.

The golden dataset's "content opportunity" column describes the article
ComeMorocco *should* have, not the page it *does* have, so word-overlap
scoring against it is too noisy to tune retrieval by. It rated a switch from
"no link" to a perfect bargaining guide as a failure, and a switch from the
Merzouga page to a Marrakech city guide — for a Sahara question — as a win.

These cases are annotated by reading the question and the candidate pages.
Each lists titles that are acceptable as the first link and titles that must
never be linked. Several come straight from regressions found while tuning,
so the same mistake cannot return unnoticed.
"""
from __future__ import annotations

import pytest

from app.core.intent import classify_rules
from app.knowledge.links import select_links
from app.knowledge.loader import get_knowledge_base
from app.knowledge.retriever import get_retriever


def golden(question_id: str) -> str:
    return next(q["question"] for q in get_knowledge_base().golden_questions if q["id"] == question_id)


def links_for(question: str) -> list[str]:
    retriever = get_retriever()
    classification = classify_rules(question)
    decision = select_links(retriever.retrieve(question, classification), classification)
    return [resource.title for resource in decision.resources]


# (label, question, acceptable first link, forbidden anywhere)
CASES = [
    (
        "days in a city",
        "How many days do I need in Marrakech?",
        ["How Many Days in Marrakech"],
        [],
    ),
    (
        "choosing between two cities",
        "Marrakech or Fes for a first trip?",
        ["First Timers", "First-Timers", "Beginner", "Where to Go"],
        # Both were linked before title matching existed.
        ["Flights to Marrakech", "Markets Guide"],
    ),
    (
        "route between two cities",
        "Train or bus from Marrakech to Fes?",
        ["Morocco Trains", "Morocco Transportation"],
        # A different route is not half an answer.
        ["Casablanca to Marrakech"],
    ),
    (
        "route that has its own page",
        "How do I get from Casablanca to Marrakech?",
        ["Casablanca to Marrakech"],
        [],
    ),
    (
        "accommodation comparison",
        "Riad or hotel in Marrakech?",
        ["Riad vs Hotel"],
        [],
    ),
    (
        "first-timer destination choice",
        "It's my first time in Morocco, where should I go?",
        ["First Timers", "First-Timers", "Beginner"],
        [],
    ),
    (
        "bargaining in the souks",
        "Any tips for bargaining in the souks?",
        ["Bargaining"],
        [],
    ),
    (
        "a dish, not the word restaurant",
        "Best steak place in Marrakech?",
        ["Restaurants"],
        # Linked in turn by two earlier versions: one on "place", one on the
        # city name alone.
        ["Flights to Marrakech", "Places to Visit"],
    ),
    (
        "a bare place name",
        "Chefchaouen?",
        ["Chefchaouen"],
        ["Private Transfer"],
    ),
    (
        "forum phrasing around a real subject",
        "Is anyone able to recommend a good hammam?",
        ["Hammam"],
        [],
    ),
    (
        # Country-wide questions can't earn a city match; this went unlinked
        # until country-wide pages could, and before that linked the blog
        # index, which the content map mislabels as a Core weather guide.
        "GQ-141: country-wide weather",
        golden("GQ-141"),
        ["Weather", "Best Time", "Month-by-Month"],
        ["Blog"],
    ),
    (
        "visa, a country-wide question with its own page",
        "Do I need a visa for Morocco?",
        ["Visa"],
        [],
    ),
    # --- regressions found while adding title matching ------------------
    (
        "GQ-190: car rental with a pick-up city",
        golden("GQ-190"),
        ["Car Rental"],
        [],
    ),
    (
        "GQ-065: Sahara over Christmas",
        golden("GQ-065"),
        ["Merzouga", "Sahara", "Desert"],
        ["How Many Days in Marrakech"],
    ),
    (
        "GQ-205: already at a resort, wants family day trips",
        golden("GQ-205"),
        ["Kids", "Kid-Friendly Activities", "Day Trip", "Family Holiday"],
        # They have somewhere to stay; a hotel list misreads the question.
        ["Family Hotels"],
    ),
]


@pytest.mark.parametrize("label,question,acceptable,forbidden", CASES, ids=[c[0] for c in CASES])
def test_retrieval_quality(label, question, acceptable, forbidden):
    titles = links_for(question)

    for title in titles:
        for bad in forbidden:
            assert bad.lower() not in title.lower(), f"linked a forbidden page: {title!r}"

    assert titles, "no page linked, but the site has a good one"
    first = titles[0].lower()
    assert any(ok.lower() in first for ok in acceptable), (
        f"first link was {titles[0]!r}; expected one of {acceptable}"
    )


def test_a_genuine_gap_links_nothing_misleading():
    """Nothing on the site is about wheelchair access. The assistant may still
    answer, but must not pretend a page covers it."""
    question = "Is Morocco wheelchair accessible? Which cities are easiest with a wheelchair?"
    for title in links_for(question):
        assert "wheelchair" in title.lower() or "accessib" in title.lower(), (
            f"linked {title!r} to an accessibility question the site does not cover"
        )


def test_long_train_booking_question_never_gets_an_off_topic_page():
    """GQ-051: a long forum post about the ONCF website failing, Rabat to Tangier.

    Before title-topic scoring this linked an AFCON *hotels* guide. It now ranks
    two train pages first. Neither is linked: the top one is about a different
    route (Casablanca–Rabat), and the general trains guide falls just under the
    link threshold, because long posts score lower in absolute terms.

    That is a defensible outcome — no link beats a wrong one — so the test pins
    what matters: nothing off-topic is ever linked, and anything that is linked
    is about trains. The threshold question is recorded in the README's known
    limitations rather than tuned away for one case.
    """
    question = golden("GQ-051")
    retriever = get_retriever()
    classification = classify_rules(question)
    ranked = retriever.retrieve(question, classification)

    assert "train" in ranked[0].item["title"].lower()
    for title in links_for(question):
        assert "train" in title.lower(), f"linked an off-topic page: {title!r}"
        assert "hotel" not in title.lower()


# Questions the site has no page for. The right behaviour is two things at
# once: link nothing (every earlier version linked something wrong here), and
# record the question as a gap so it reaches the editorial brief list.
GAPS = [
    # Linked a Casablanca hotels page while place-only questions were
    # over-detected.
    ("GQ-185", "Casablanca airport terminals"),
    # Linked a Tangier *beach* guide, then linked nothing without logging it.
    ("GQ-113", "restaurants in Tetouan"),
    # Linked "Marrakech vs Agadir: 7 Key Differences" — a page for choosing
    # between the two cities, not for travelling between them.
    ("GQ-045", "getting from Marrakech to Agadir"),
]


@pytest.mark.parametrize("question_id,label", GAPS, ids=[g[1] for g in GAPS])
def test_uncovered_question_links_nothing_and_is_logged(question_id, label):
    from app.knowledge.links import detect_content_gap

    question = golden(question_id)
    retriever = get_retriever()
    classification = classify_rules(question)
    candidates = retriever.retrieve(question, classification)

    assert links_for(question) == [], "linked a page to a question the site does not cover"
    assert detect_content_gap(question, candidates, classification) is not None, (
        "no link was shown but the question was not logged as a content gap"
    )
