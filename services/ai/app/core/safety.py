"""Guardrails that run before and after the model.

Deliberately narrow. The model handles most of this well; what lives here are
the cases where a wrong answer has a real cost to a traveller or to
ComeMorocco, and the fallbacks for when the model is unavailable.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

from app.schemas import Classification

# Requests that should be refused outright rather than answered carefully.
REFUSE = [
    (
        re.compile(r"\b(buy|score|get|find|where.{0,20}(hash|weed|kif|cannabis|cocaine))\b.{0,30}"
                   r"\b(hash|weed|kif|cannabis|drugs?|cocaine)\b", re.I),
        "drugs",
    ),
    (
        re.compile(r"\b(smuggl\w+|bribe (the|a) (police|officer|cop)|fake (passport|visa|id)|"
                   r"forged? (document|passport|visa))\b", re.I),
        "illegal",
    ),
    (
        re.compile(r"\b(sex tourism|prostitut\w+|escort service)\b", re.I),
        "exploitation",
    ),
]

REFUSAL_MESSAGES = {
    "drugs": (
        "That's not something I'll help with — cannabis is illegal in Morocco and tourists do get "
        "caught up in it, sometimes as the target of a setup. If you want, I can help with the rest "
        "of your trip instead."
    ),
    "illegal": (
        "I can't help with that. If there's a legitimate travel problem behind the question — a "
        "document issue, a border question, a dispute with an operator — tell me what's actually "
        "going on and I'll help where I can."
    ),
    "exploitation": "I won't help with that. Happy to help with anything else about travelling in Morocco.",
}

# Questions where deferring to an authority is the correct answer.
DEFER = [
    (
        re.compile(r"\b(visa|entry requirement|do i need a visa|passport validity|border control|"
                   r"customs (rules|limit)|immigration)\b", re.I),
        "Entry and visa rules depend on nationality and change without notice — send them to the "
        "Moroccan consulate or embassy for their country, and to their own foreign ministry's "
        "travel advice. Explain what generally determines the answer, but do not state their "
        "specific requirement as fact.",
    ),
    (
        re.compile(r"\b(vaccin\w+|malaria|medication|prescription|insulin|allerg\w+|pregnan\w+|"
                   r"medical condition|chronic illness)\b", re.I),
        "Health questions go to a travel clinic or their doctor. Give practical travel logistics "
        "(pharmacies, keeping medication in hand luggage, heat) but never clinical advice.",
    ),
    (
        re.compile(r"\b(travel (advisory|warning)|is it safe to travel (now|right now|currently)|"
                   r"protest|unrest|earthquake|flood(ing)?|strike)\b", re.I),
        "Current conditions cannot be verified here. Point them at their government's travel "
        "advisory and local news, and be clear about what you do and do not know.",
    ),
]


@dataclass
class SafetyVerdict:
    allow: bool = True
    refusal: str | None = None
    guidance: str | None = None
    category: str | None = None


def check_input(text: str, classification: Classification) -> SafetyVerdict:
    for pattern, category in REFUSE:
        if pattern.search(text):
            return SafetyVerdict(
                allow=False,
                refusal=REFUSAL_MESSAGES[category],
                category=category,
            )

    notes: list[str] = []
    for pattern, guidance in DEFER:
        if pattern.search(text):
            notes.append(guidance)

    return SafetyVerdict(allow=True, guidance=" ".join(notes) if notes else None)


# --------------------------------------------------------------------------
# Post-generation checks that are cheap and mechanical
# --------------------------------------------------------------------------
FABRICATED_EXPERIENCE = re.compile(
    r"\b(i (went|stayed|visited|ate|travell?ed|booked|tried|used|drove|flew|took the train)\b"
    r"|when i (was|stayed|visited)\b"
    r"|i'?ve (been|stayed|visited|eaten) (there|in|at)\b"
    r"|we (stayed|used|booked) (them|it|there)\b"
    r"|last (year|month|summer|winter) i\b"
    r"|here in morocco\b)",
    re.IGNORECASE,
)

CLAIMED_ACTION = re.compile(
    r"\b(i'?ve (booked|reserved|cancelled|canceled|checked|contacted|emailed|called)"
    r"|i (just )?(booked|reserved|checked the (schedule|availability|price)|contacted)"
    r"|your (booking|reservation) (is|has been) (confirmed|made))\b",
    re.IGNORECASE,
)

SALES_PRESSURE = re.compile(
    r"\b(book now|don'?t miss out|limited time|hurry|selling out|act fast|before it'?s too late|"
    r"you must book|grab (it|yours))\b",
    re.IGNORECASE,
)

URL_IN_TEXT = re.compile(r"https?://\S+|\bwww\.\S+", re.IGNORECASE)

BROCHURE = re.compile(
    r"\b(magical|breathtaking|unforgettable|vibrant tapestry|rich tapestry|hidden gem|nestled|"
    r"immerse yourself|embark on|delve into|world-class|look no further|bustling)\b",
    re.IGNORECASE,
)


def scan_output(text: str) -> list[dict[str, str]]:
    """Mechanical scan of a draft answer. Cheap, runs on every response."""
    issues: list[dict[str, str]] = []
    if FABRICATED_EXPERIENCE.search(text):
        issues.append({"severity": "major", "code": "fabricated_experience",
                       "detail": "claims a first-hand experience"})
    if CLAIMED_ACTION.search(text):
        issues.append({"severity": "major", "code": "claimed_action",
                       "detail": "claims to have performed an action it cannot perform"})
    if SALES_PRESSURE.search(text):
        issues.append({"severity": "major", "code": "sales_pressure",
                       "detail": "manufactured urgency or sales pressure"})
    if URL_IN_TEXT.search(text):
        issues.append({"severity": "minor", "code": "inline_url",
                       "detail": "pasted a URL instead of letting the interface render the link"})
    if BROCHURE.search(text):
        issues.append({"severity": "minor", "code": "brochure_language",
                       "detail": "tourism-brochure wording"})
    return issues


# --------------------------------------------------------------------------
# Fallbacks
# --------------------------------------------------------------------------
FALLBACKS = {
    "model_unavailable": (
        "I couldn't get that answer together just now — try again in a moment. If it keeps "
        "happening, the Morocco guides on the site cover most of the common questions."
    ),
    "rate_limited": (
        "You've asked quite a few questions in a short window, so I need a short break. Try again "
        "in a minute."
    ),
    "message_too_long": (
        "That's a lot to take in at once. Could you send me the key parts — how long you have, "
        "who's travelling, and what you want out of the trip?"
    ),
    "empty": "What are you planning? Tell me roughly how long you have and I can help from there.",
}


def fallback(reason: str) -> str:
    return FALLBACKS.get(reason, FALLBACKS["model_unavailable"])
