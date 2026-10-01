"""Photos from Unsplash when a traveller asks to see a place.

Only when they ask for pictures (in any supported language); the search runs
on the server, so the access key never reaches the app. Unsplash guidelines:
images are hotlinked from images.unsplash.com and every photo is credited to
its photographer with links back to Unsplash (the app renders the credit).

Without UNSPLASH_ACCESS_KEY, or on any error or timeout, no photos are
returned and the answer is unaffected.
"""

from __future__ import annotations

import logging
import re
import time
from typing import Any

import httpx

from app.config import get_settings
from app.schemas import PhotoOut

log = logging.getLogger(__name__)

API = "https://api.unsplash.com/search/photos"
UTM = "utm_source=comemorocco&utm_medium=referral"
TIMEOUT_SECONDS = 4.0
CACHE_SECONDS = 24 * 3600
_cache: dict[str, tuple[float, list[PhotoOut]]] = {}
_transport: httpx.AsyncBaseTransport | None = None  # tests swap in a MockTransport

ASKS_FOR_PHOTOS = re.compile(
    r"\b(images?|photos?|pictures?|pics?|picture of|show me|what does .{1,40} look like"
    r"|photographies?|à quoi ressemble|montre[- ]moi"
    r"|im[aá]gen(?:es)?|fotos?|fotograf[ií]as?|mu[eé]strame)\b"
    r"|صور|صورة|أرني",
    re.IGNORECASE,
)
# Words that ask for pictures, not what to picture.
PHOTO_WORDS = re.compile(
    r"\b(give|send|show|share|me|some|any|a few|few|please|can|could|you|i|want|to|see|of|the|about|for"
    r"|images?|photos?|pictures?|pics?|place|this|that|it|there"
    r"|what|do|does|think|is|are|how|worth|visit|visiting|should|we|our|my|your|tell|know|like|look|looks"
    r"|donne|moi|des|les|du|de|la|le|voir|montre|photographies?"
    r"|dame|unas|unos|las|los|del|ver|muestra|mu[eé]strame|im[aá]genes|fotos?)\b",
    re.IGNORECASE,
)


def wants_photos(message: str) -> bool:
    return bool(ASKS_FOR_PHOTOS.search(message))


def photo_query(message: str, destinations: list[str]) -> str:
    """What to search for: the places the conversation is about, plus whatever
    subject is left in the message once the 'show me pictures' words go."""
    subject = PHOTO_WORDS.sub(" ", message)
    subject = re.sub(r"[^\w\s'-]", " ", subject)
    subject = " ".join(subject.split())[:60]
    parts = [d.replace("_", " ") for d in destinations[:2]]
    if subject and subject.lower() not in " ".join(parts).lower():
        parts.append(subject)
    if not parts:
        return ""
    query = " ".join(parts)
    return query if "morocco" in query.lower() else f"{query} Morocco"


def _photo(item: dict[str, Any]) -> PhotoOut | None:
    try:
        user = item["user"]
        return PhotoOut(
            url=item["urls"]["regular"],
            thumb_url=item["urls"]["small"],
            alt=(item.get("alt_description") or item.get("description") or "")[:200],
            photographer=user["name"],
            photographer_url=f"{user['links']['html']}?{UTM}",
            source_url=f"{item['links']['html']}?{UTM}",
        )
    except (KeyError, TypeError):
        return None


async def search_photos(query: str, count: int = 4) -> list[PhotoOut]:
    key = get_settings().unsplash_access_key
    if not key or not query:
        return []
    cache_key = f"{query.lower()}|{count}"
    cached = _cache.get(cache_key)
    if cached and time.monotonic() - cached[0] < CACHE_SECONDS:
        return cached[1]
    try:
        async with httpx.AsyncClient(timeout=TIMEOUT_SECONDS, transport=_transport) as client:
            response = await client.get(
                API,
                params={
                    "query": query,
                    "per_page": count,
                    "orientation": "landscape",
                    "content_filter": "high",
                },
                headers={"Authorization": f"Client-ID {key}", "Accept-Version": "v1"},
            )
        response.raise_for_status()
        results = response.json().get("results", [])
    except (httpx.HTTPError, ValueError) as exc:
        log.warning("unsplash search failed for %r: %s", query, exc)
        return []
    photos = [p for p in (_photo(item) for item in results) if p][:count]
    _cache[cache_key] = (time.monotonic(), photos)
    return photos
