"""French/Spanish → English bridge for the deterministic stages.

The knowledge base, the intent rules and the affiliate gates are written in
English. A French or Spanish question therefore reached none of them: asked
"Où réserver une excursion dans le désert depuis Marrakech ?", the service
linked a hammam guide and opened no booking options (docs/ai-audit.md,
finding 7).

`bridge()` keeps the traveller's words and appends English equivalents of the
travel phrases it recognises, so every rule, keyword and BM25 term sees both.
It is:
  * applied only when the message is detected as French or Spanish, so English
    behaviour — and the English eval — cannot change;
  * a phrase table, not a model call: deterministic, free, and testable;
  * additive: nothing the traveller wrote is removed.

The model still answers in the traveller's language; this only affects which
pages and partner options the code selects.
"""

from __future__ import annotations

import re
import unicodedata

BRIDGED_LANGUAGES = {"fr", "es"}


def fold(text: str) -> str:
    """Lowercase and strip accents: "Désert à Fès" -> "desert a fes"."""
    decomposed = unicodedata.normalize("NFKD", text.lower())
    return "".join(ch for ch in decomposed if not unicodedata.combining(ch))


# (folded phrase, English equivalent). Longer phrases first; matching is on
# word boundaries against the folded text. Advisory framings map to the
# English advisory phrases on purpose, so "faut-il réserver…" stays advice.
_FR: list[tuple[str, str]] = [
    ("excursion dans le desert", "desert tour"),
    ("circuit dans le desert", "desert tour"),
    ("excursion au desert", "desert tour"),
    ("circuit desert", "desert tour"),
    ("ou puis-je reserver", "where can i book"),
    ("ou peut-on reserver", "where can i book"),
    ("ou reserver", "where can i book"),
    ("je veux reserver", "i want to book"),
    ("je voudrais reserver", "i want to book"),
    ("comment reserver", "how do i book"),
    ("est-ce que ca vaut la peine", "is it worth"),
    ("ca vaut la peine", "is it worth"),
    ("vaut-il mieux", "better to"),
    ("faut-il reserver", "do i need to book"),
    ("faut-il", "should i"),
    ("dois-je", "should i"),
    ("combien de jours", "how many days"),
    ("combien de nuits", "how many nights"),
    ("combien ca coute", "how much does it cost"),
    ("louer une voiture", "rent a car"),
    ("location de voiture", "car rental"),
    ("premier voyage", "first trip"),
    ("visite guidee", "guided tour"),
    ("au depart de", "from"),
    ("a l'avance", "in advance"),
    ("reserver", "book"),
    ("reservation", "booking"),
    ("excursion", "tour"),
    ("excursions", "tours"),
    ("circuit", "tour"),
    ("depuis", "from"),
    ("jours", "days"),
    ("nuits", "nights"),
    ("semaine", "week"),
    ("voiture", "car"),
    ("gare", "train station"),
    ("autocar", "bus"),
    ("plage", "beach"),
    ("randonnee", "hiking"),
    ("montagne", "mountains"),
    ("hebergement", "accommodation"),
    ("nourriture", "food"),
    ("cuisine", "food"),
    ("securite", "safety"),
    ("meteo", "weather"),
    ("prix", "price"),
    ("maroc", "morocco"),
    ("enfants", "kids"),
    ("famille", "family"),
    ("aeroport", "airport"),
    ("vol", "flight"),
]

_ES: list[tuple[str, str]] = [
    ("excursion al desierto", "desert tour"),
    ("excursion por el desierto", "desert tour"),
    ("tour por el desierto", "desert tour"),
    ("donde puedo reservar", "where can i book"),
    ("donde reservar", "where can i book"),
    ("quiero reservar", "i want to book"),
    ("como reservar", "how do i book"),
    ("vale la pena", "is it worth"),
    ("es mejor", "better to"),
    ("deberia", "should i"),
    ("necesito reservar", "do i need to book"),
    ("cuantos dias", "how many days"),
    ("cuantas noches", "how many nights"),
    ("alquilar un coche", "rent a car"),
    ("alquiler de coches", "car rental"),
    ("primer viaje", "first trip"),
    ("reservar", "book"),
    ("reserva", "booking"),
    ("excursion", "tour"),
    ("excursiones", "tours"),
    ("desierto", "desert"),
    ("desde", "from"),
    ("dias", "days"),
    ("noches", "nights"),
    ("semana", "week"),
    ("coche", "car"),
    ("tren", "train"),
    ("autobus", "bus"),
    ("playa", "beach"),
    ("senderismo", "hiking"),
    ("montana", "mountains"),
    ("alojamiento", "accommodation"),
    ("comida", "food"),
    ("seguridad", "safety"),
    ("clima", "weather"),
    ("precio", "price"),
    ("ninos", "kids"),
    ("familia", "family"),
    ("aeropuerto", "airport"),
    ("vuelo", "flight"),
    ("visado", "visa"),
    ("marruecos", "morocco"),
]

_TABLES = {
    "fr": [(re.compile(rf"(?<![\w-]){re.escape(p)}(?![\w-])"), e) for p, e in _FR],
    "es": [(re.compile(rf"(?<![\w-]){re.escape(p)}(?![\w-])"), e) for p, e in _ES],
}


def english_hints(text: str, language: str | None) -> list[str]:
    """English equivalents of the travel phrases found in a fr/es message."""
    if language not in BRIDGED_LANGUAGES:
        return []
    folded = fold(text)
    hints: list[str] = _routes(folded)
    for pattern, english in _TABLES[language]:
        if pattern.search(folded):
            # Consume the phrase so "ou reserver" does not also add "book".
            folded = pattern.sub(" ", folded)
            if english not in hints:
                hints.append(english)
    return hints


# "de Marrakech à Fès" / "de Marrakech a Fez" -> "from marrakech to fes".
_ROUTE = re.compile(
    r"(?<![\w-])(?:de|desde|depuis) ([a-z]+(?: [a-z]+)?) (?:a|au|hasta|vers) ([a-z]+)(?![\w-])"
)


def _routes(folded: str) -> list[str]:
    return [f"from {a} to {b}" for a, b in _ROUTE.findall(folded)]


def bridge(text: str, language: str | None) -> str:
    """The message plus its English hints (and accent-folded form) for the rule stages."""
    hints = english_hints(text, language)
    if not hints:
        return text
    return f"{text} {fold(text)} {' '.join(hints)}"


def retrieval_query(text: str, language: str | None, known: set[str]) -> str:
    """The query BM25 should see for a fr/es message: its English hints plus
    only the traveller's words that exist in the (English) corpus.

    Untranslated words ("aller", "pour") are absent from the corpus, so BM25
    ranks them as the most distinctive terms and page coverage collapses.
    Place names and shared words ("visa", "riad", "marrakech") are kept.
    """
    hints = english_hints(text, language)
    if not hints:
        return text
    kept = [w for w in re.findall(r"[a-z0-9]+", fold(text)) if w in known]
    return " ".join(kept + hints)
