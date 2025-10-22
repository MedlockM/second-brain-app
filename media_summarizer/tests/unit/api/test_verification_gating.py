from unittest.mock import AsyncMock
from fastapi.testclient import TestClient

from media_summarizer.api.main import app
from media_summarizer.core.models.auth import AuthUser
from media_summarizer.core.models.user import User

client = TestClient(app)


def override_get_current_user():
    # Return a minimal authenticated user
    return AuthUser(id="test-user-1", email="u@example.com")


def test_unverified_user_blocked_on_billing_checkout(monkeypatch):
    # Override auth to return a user
    from media_summarizer.api.dependencies.auth import get_current_user

    app.dependency_overrides[get_current_user] = override_get_current_user

    # Patch DB to return an unverified local user
    from media_summarizer.utils import database_async

    unverified_user = User(
        id="test-user-1", email="u@example.com", auth_provider="local"
    )
    monkeypatch.setattr(
        database_async, "get_user_by_id", AsyncMock(return_value=unverified_user)
    )

    # Call billing packs checkout (requires verified email)
    resp = client.post(
        "/api/v1/billing/packs/checkout", json={"minutes": 300}
    )
    assert resp.status_code == 403
    assert "Email not verified" in resp.json()["detail"]

    # Cleanup overrides
    app.dependency_overrides.clear()


def test_unverified_user_blocked_on_submit_episode(monkeypatch):
    # Override auth to return a user
    from media_summarizer.api.dependencies.auth import get_current_user

    app.dependency_overrides[get_current_user] = override_get_current_user

    # Patch DB to return an unverified local user
    from media_summarizer.utils import database_async

    unverified_user = User(
        id="test-user-1", email="u@example.com", credits=100, auth_provider="local"
    )
    monkeypatch.setattr(
        database_async, "get_user_by_id", AsyncMock(return_value=unverified_user)
    )

    # This endpoint requires a body but should fail on dependency before processing
    body = {"feed_id": "feed_123", "episode_guid": "guid_123"}
    resp = client.post("/api/v1/podcast-search/submit-episode", json=body)
    assert resp.status_code == 403
    assert "Email not verified" in resp.json()["detail"]

    # Cleanup overrides
    app.dependency_overrides.clear()
