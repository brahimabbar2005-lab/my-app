"""API tests.

These run without an API key, which is the useful case: they prove the service
degrades into a helpful fallback rather than an error page when the model is
unreachable (02_MVP_SCOPE §36), and that auth and rate limiting behave.

The `client` fixture uses TestClient as a context manager so the lifespan hook
runs — that is what creates the schema and builds the index.
"""
from __future__ import annotations

import os
import tempfile

import pytest
from fastapi.testclient import TestClient


@pytest.fixture(scope="module")
def client():
    # Isolated database per run so tests never touch a real one.
    handle, path = tempfile.mkstemp(suffix=".db")
    os.close(handle)
    os.environ["DATABASE_URL"] = f"sqlite:///{path}"
    os.environ.pop("WIDGET_KEY", None)
    os.environ.pop("ADMIN_KEY", None)

    from app.config import get_settings

    get_settings.cache_clear()
    import app.db.models as models

    models._engine = None
    models._SessionLocal = None

    from app.main import app

    # raise_server_exceptions=False so the registered handler's response is
    # returned, the way it would be in production.
    with TestClient(app, raise_server_exceptions=False) as test_client:
        yield test_client

    os.unlink(path)


class TestHealth:
    def test_health_reports_the_knowledge_base(self, client):
        payload = client.get("/health").json()
        assert payload["status"] == "ok"
        assert payload["knowledge"]["content_items"] == 240

    def test_starters_are_language_aware(self, client):
        english = client.get("/api/starters?lang=en").json()["starters"]
        french = client.get("/api/starters?lang=fr").json()["starters"]
        assert english and french
        assert english != french


class TestChat:
    def test_answers_without_a_model_key(self, client):
        """No key configured: the traveller gets a fallback, never a stack trace."""
        response = client.post("/api/chat", json={"message": "How many days do I need in Marrakech?"})
        assert response.status_code == 200

        payload = response.json()
        assert payload["answer"]
        assert "Error" not in payload["answer"]
        assert "500" not in payload["answer"]
        assert payload["conversation_id"]
        assert payload["message_id"]
        # Retrieval and link selection do not depend on the model, so the
        # resource card is still correct.
        assert payload["resources"]
        assert "marrakech" in payload["resources"][0]["title"].lower()

    def test_conversation_is_continued(self, client):
        """The client must send back both ids, as the widget does."""
        first = client.post("/api/chat", json={"message": "I have 10 days in Morocco"}).json()
        second = client.post(
            "/api/chat",
            json={
                "message": "Would you add Fes?",
                "session_id": first["session_id"],
                "conversation_id": first["conversation_id"],
            },
        ).json()
        assert second["conversation_id"] == first["conversation_id"]
        # The trip is still 10 days without the traveller repeating it.
        assert second["trip_state"].get("trip_duration_days") == 10

    def test_a_returned_session_id_is_honoured(self, client):
        """Regression: the server used to mint a new session every request,
        which silently dropped conversation context."""
        first = client.post("/api/chat", json={"message": "Hello"}).json()
        second = client.post(
            "/api/chat", json={"message": "Is Fes worth visiting?", "session_id": first["session_id"]}
        ).json()
        assert second["session_id"] == first["session_id"]

    def test_a_junk_session_id_is_not_stored(self, client):
        """Only ids shaped like ones we would issue are adopted."""
        payload = client.post(
            "/api/chat", json={"message": "Hello", "session_id": "../../etc/passwd"}
        ).json()
        assert payload["session_id"] != "../../etc/passwd"

    def test_rejects_an_empty_message(self, client):
        assert client.post("/api/chat", json={"message": "   "}).status_code == 422

    def test_rejects_an_oversized_message(self, client):
        response = client.post("/api/chat", json={"message": "x" * 5000})
        assert response.status_code == 400
        assert response.json()["answer"]

    def test_notices_flag_missing_live_data(self, client):
        payload = client.post("/api/chat", json={"message": "Is the train running tomorrow?"}).json()
        assert any("live" in notice.lower() or "change" in notice.lower()
                   for notice in payload["notices"])

    def test_off_topic_gets_no_links(self, client):
        payload = client.post("/api/chat", json={"message": "Who won yesterday's football match?"}).json()
        assert payload["resources"] == []
        assert payload["affiliates"] == []


class TestFeedback:
    def test_records_feedback(self, client):
        chat = client.post("/api/chat", json={"message": "Is Fes worth visiting?"}).json()
        response = client.post(
            "/api/feedback", json={"message_id": chat["message_id"], "helpful": True}
        )
        assert response.status_code == 200

    def test_negative_feedback_opens_a_review_item(self, client):
        chat = client.post("/api/chat", json={"message": "What is a riad?"}).json()
        client.post(
            "/api/feedback",
            json={"message_id": chat["message_id"], "helpful": False, "reason": "too_long"},
        )
        from app.db.models import Message
        from app.db.repo import session_scope

        with session_scope() as db:
            message = db.get(Message, chat["message_id"])
            assert message.review_status == "open"

    def test_unknown_message_is_rejected(self, client):
        response = client.post("/api/feedback", json={"message_id": "nope", "helpful": True})
        assert response.status_code == 404

    def test_only_known_event_names_are_accepted(self, client):
        assert client.post("/api/events", json={"name": "chat_opened"}).status_code == 200
        assert client.post("/api/events", json={"name": "drop_tables"}).status_code == 422


class TestAdminAuth:
    def test_admin_is_closed_when_no_key_is_set(self, client):
        """Fails closed: an unset ADMIN_KEY must not mean an open endpoint."""
        for path in ("/api/admin/stats", "/api/admin/flagged", "/api/admin/content-gaps"):
            assert client.get(path).status_code == 503, path

    def test_sync_endpoint_is_closed_too(self, client):
        assert client.post("/api/admin/content-changed").status_code == 503


class TestRateLimiting:
    def setup_method(self):
        from app.infra.ratelimit import _limiter

        _limiter._minute.clear()
        _limiter._day.clear()

    def test_limits_a_burst_from_one_session(self, client):
        session = "a1b2c3d4" * 4  # hex, the shape the widget generates
        codes = [
            client.post("/api/chat", json={"message": f"question {i}", "session_id": session}).status_code
            for i in range(12)
        ]
        assert 429 in codes

        blocked = client.post("/api/chat", json={"message": "again", "session_id": session})
        assert blocked.status_code == 429
        assert "Retry-After" in blocked.headers
        # Even when refused, the traveller gets a human sentence, not a code.
        assert blocked.json()["answer"]
        assert "429" not in blocked.json()["answer"]

    def test_rotating_session_ids_still_hits_the_ip_ceiling(self, client):
        """Regression: session ids are client-asserted, so rotating them used
        to produce a fresh rate-limit bucket on every request."""
        codes = []
        for i in range(60):
            codes.append(
                client.post(
                    "/api/chat",
                    json={"message": f"q{i}", "session_id": f"{i:032x}"},
                ).status_code
            )
            if 429 in codes:
                break
        assert 429 in codes
