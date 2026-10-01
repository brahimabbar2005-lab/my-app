"""Unsplash photos for 'show me pictures' requests (no network: MockTransport)."""

import httpx
import pytest

from app.config import get_settings
from app.core import orchestrator
from app.infra import unsplash
from app.schemas import PhotoOut, TripState


@pytest.mark.parametrize(
    "message",
    [
        "Give me some images about the place",
        "Show me pictures of Chefchaouen",
        "what does Merzouga look like?",
        "Montre-moi des photos de Fès",
        "¿Tienes fotos de Essaouira?",
        "أرني صور مراكش",
    ],
)
def test_detects_photo_requests(message):
    assert unsplash.wants_photos(message)


@pytest.mark.parametrize(
    "message", ["Is Fes safe at night?", "How much is a taxi from the airport?", "imagine a slow trip"]
)
def test_ordinary_questions_get_no_photos(message):
    assert not unsplash.wants_photos(message)


def test_query_uses_places_and_subject():
    assert (
        unsplash.photo_query("Show me pictures of the blue streets", ["chefchaouen"])
        == "chefchaouen blue streets Morocco"
    )
    assert unsplash.photo_query("Give me some images about the place", ["agafay"]) == "agafay Morocco"
    assert unsplash.photo_query("Give me some images about the place", []) == ""
    assert unsplash.photo_query("photos of Morocco hammam", []) == "Morocco hammam"


def unsplash_result(n=2):
    return {
        "results": [
            {
                "urls": {
                    "regular": f"https://images.unsplash.com/photo-{i}?w=1080",
                    "small": f"https://images.unsplash.com/photo-{i}?w=400",
                },
                "alt_description": "desert dunes at sunset",
                "links": {"html": f"https://unsplash.com/photos/p{i}"},
                "user": {"name": f"Photographer {i}", "links": {"html": f"https://unsplash.com/@p{i}"}},
            }
            for i in range(n)
        ]
    }


@pytest.fixture
def mock_unsplash(monkeypatch):
    calls = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        return httpx.Response(200, json=unsplash_result())

    monkeypatch.setenv("UNSPLASH_ACCESS_KEY", "test-access-key")
    get_settings.cache_clear()
    monkeypatch.setattr(unsplash, "_transport", httpx.MockTransport(handler))
    unsplash._cache.clear()
    yield calls
    unsplash._cache.clear()
    get_settings.cache_clear()


async def test_search_returns_credited_photos_and_caches(mock_unsplash):
    photos = await unsplash.search_photos("agafay Morocco")
    assert [p.photographer for p in photos] == ["Photographer 0", "Photographer 1"]
    assert photos[0].photographer_url.endswith("?utm_source=comemorocco&utm_medium=referral")
    assert photos[0].source_url.startswith("https://unsplash.com/photos/")
    request = mock_unsplash[0]
    assert request.headers["Authorization"] == "Client-ID test-access-key"
    assert request.url.params["query"] == "agafay Morocco"
    await unsplash.search_photos("agafay Morocco")
    assert len(mock_unsplash) == 1, "the second identical search is served from the cache"


async def test_no_key_or_errors_mean_no_photos(monkeypatch):
    get_settings.cache_clear()
    assert await unsplash.search_photos("agafay Morocco") == []

    monkeypatch.setenv("UNSPLASH_ACCESS_KEY", "k")
    get_settings.cache_clear()
    monkeypatch.setattr(
        unsplash, "_transport", httpx.MockTransport(lambda r: httpx.Response(403, text="Rate Limit Exceeded"))
    )
    unsplash._cache.clear()
    assert await unsplash.search_photos("agafay Morocco") == []
    get_settings.cache_clear()


async def test_follow_up_without_a_place_uses_the_previous_question(monkeypatch):
    seen = []

    async def fake_search(query, count=4):
        seen.append(query)
        return [
            PhotoOut(
                url="https://images.unsplash.com/a",
                thumb_url="https://images.unsplash.com/a",
                photographer="A",
                photographer_url="https://unsplash.com/@a",
                source_url="https://unsplash.com/photos/a",
            )
        ]

    monkeypatch.setattr(unsplash, "search_photos", fake_search)
    history = [
        {"role": "user", "content": "What do you think about Agafay?"},
        {"role": "assistant", "content": "..."},
    ]
    photos = await orchestrator.photos_for("Give me some images about the place", TripState(), history)
    assert len(photos) == 1
    assert seen == ["Agafay Morocco"]
    assert "Do not say you cannot show images" in orchestrator.photo_note(photos)
    assert await orchestrator.photos_for("Is Agafay worth it?", TripState(), history) == []
