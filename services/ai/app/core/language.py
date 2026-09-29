"""Answer in the language the traveller wrote in.

MVP ships English and French properly. Spanish, Arabic and Darija are detected
so the assistant can respond in them where the model is comfortable, rather
than replying in English to someone who wrote in Arabic — but they are not
claimed as supported languages, and the content it links to stays English
until the site is translated.
"""
from __future__ import annotations

import re

LANGUAGE_NAMES = {
    "en": "English",
    "fr": "French",
    "es": "Spanish",
    "ar": "Arabic",
    "ary": "Moroccan Darija",
    "de": "German",
    "it": "Italian",
    "pt": "Portuguese",
    "nl": "Dutch",
}

ARABIC_RANGE = re.compile(r"[\u0600-\u06FF]")

# Darija written in Arabic script uses markers that Modern Standard Arabic does
# not, plus the Latin-script "Arabizi" numerals.
DARIJA_MARKERS = ("شنو", "كيفاش", "بزاف", "دابا", "واش", "فين", "علاش", "مزيان", "غادي")
ARABIZI = re.compile(r"\b(chno|kifach|bzaf|daba|wach|fin|3lach|mezyan|ghadi|labas|wa5a)\b", re.IGNORECASE)

WORD_MARKERS: dict[str, tuple[str, ...]] = {
    "fr": (
        "bonjour", "salut", "merci", "je", "j'ai", "nous", "vous", "quel", "quelle",
        "quels", "est-ce", "combien", "pour", "avec", "dans", "sur", "voyage",
        "jours", "semaine", "meilleur", "meilleure", "où", "comment", "pourquoi",
        "faut-il", "peut-on", "d'un", "d'une", "des", "les", "une", "être", "aller",
        "partir", "séjour", "conseil", "conseils",
    ),
    "es": (
        "hola", "gracias", "cuánto", "cuantos", "cuántos", "dónde", "donde",
        "cómo", "como", "qué", "que tal", "viaje", "días", "dias", "semana",
        "mejor", "quiero", "puedo", "necesito", "para", "desde", "hasta",
        "recomiendas", "hay",
    ),
    "de": ("hallo", "danke", "wie", "wieviel", "wohin", "reise", "tage", "woche", "beste", "ich", "wir"),
    "it": ("ciao", "grazie", "quanto", "dove", "come", "viaggio", "giorni", "settimana", "migliore", "vorrei"),
    "pt": ("olá", "obrigado", "quanto", "onde", "como", "viagem", "dias", "semana", "melhor", "quero"),
    "nl": ("hallo", "bedankt", "hoeveel", "waar", "hoe", "reis", "dagen", "week", "beste", "ik wil"),
}

# Words that look French/Spanish but appear constantly in English travel talk.
AMBIGUOUS = {"des", "les", "une", "hay", "como", "que"}


def detect_language(text: str, hint: str | None = None) -> str:
    """Return a BCP-47-ish language code for the traveller's message."""
    stripped = text.strip()
    if not stripped:
        return hint or "en"

    if ARABIC_RANGE.search(stripped):
        if any(marker in stripped for marker in DARIJA_MARKERS):
            return "ary"
        return "ar"

    lowered = f" {stripped.lower()} "
    if ARABIZI.search(lowered):
        return "ary"

    scores: dict[str, int] = {}
    for code, markers in WORD_MARKERS.items():
        score = 0
        for marker in markers:
            if marker in AMBIGUOUS:
                continue
            if f" {marker} " in lowered or lowered.startswith(f" {marker}"):
                score += 2 if len(marker) > 3 else 1
        if score:
            scores[code] = score

    # French accents are a strong signal; English travel text rarely has them.
    if re.search(r"[àâçéèêëîïôûùüœ]", lowered):
        scores["fr"] = scores.get("fr", 0) + 3
    if re.search(r"[¿¡ñ]", lowered):
        scores["es"] = scores.get("es", 0) + 3

    if not scores:
        return hint if hint in LANGUAGE_NAMES else "en"

    best = max(scores.items(), key=lambda kv: kv[1])
    # A single weak marker in an otherwise English sentence is not enough.
    if best[1] < 3:
        return hint if hint in LANGUAGE_NAMES else "en"
    return best[0]


def language_name(code: str) -> str:
    return LANGUAGE_NAMES.get(code, "English")


def is_fully_supported(code: str, supported: list[str]) -> bool:
    return code in supported
