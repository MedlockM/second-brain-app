"""
Integration tests for Spotify link-account flow.

Validates that an authenticated user can link Spotify using Authorization Code
flow (no PKCE), storing tokens/metadata on the user, and that state protection
and error cases work.
"""
import json
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from unittest.mock import AsyncMock

import media_summarizer.api.endpoints.auth_social as auth_social
from media_summarizer.core.models import User
from media_summarizer.core.models.auth import AuthUser
from media_summarizer.api.dependencies.auth import get_current_user


class _FakeResponse:
    def __init__(self, json_body: dict, status_code: int = 200):
        self._json = json_body
        self.status_code = status_code
        self.text = json.dumps(json_body)

    def json(self):
        return self._json

    def raise_for_status(self):
        if not (200 <= self.status_code < 300):
            raise Exception(f"HTTP {self.status_code}")


class _FakeAsyncClient:
    def __init__(self, *, get_map=None, post_map=None, timeout=None):
        self._get_map = get_map or {}
        self._post_map = post_map or {}

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    async def get(self, url, *args, **kwargs):
        maker = self._get_map.get(url)
        if callable(maker):
            return maker(url, *args, **kwargs)
        if isinstance(maker, _FakeResponse):
            return maker
        raise AssertionError(f"Unexpected GET {url}")

    async def post(self, url, *args, **kwargs):
        maker = self._post_map.get(url)
        if callable(maker):
            return maker(url, *args, **kwargs)
        if isinstance(maker, _FakeResponse):
            return maker
        raise AssertionError(f"Unexpected POST {url}")


@pytest.fixture(autouse=True)
def _setup_env(monkeypatch):
    # Configure Spotify env and frontend
    auth_social.SPOTIFY_CLIENT_ID = "spotify-client"
    auth_social.SPOTIFY_CLIENT_SECRET = "spotify-secret"
    auth_social.SPOTIFY_REDIRECT_URI = "http://localhost:8000/api/v1/auth/spotify/callback"
    auth_social.FRONTEND_URL = "http://localhost:3000"
    # Relax cookies in test
    auth_social.COOKIE_SECURE = False
    auth_social.COOKIE_SAMESITE = "lax"
    yield


def _build_app_with_auth_override(fake_user: User):
    app = FastAPI()
    app.include_router(auth_social.router, prefix="/api/v1/auth")

    # Override dependency to simulate authenticated user
    def _override_get_current_user():
        return AuthUser(id=fake_user.id, email=fake_user.email)

    app.dependency_overrides[get_current_user] = _override_get_current_user
    return app


@pytest.mark.asyncio
async def test_spotify_link_success(monkeypatch):
    # Fake DB helpers
    saved_user = User(email="tester@example.com")

    async def fake_get_user_by_id(user_id: str):
        return saved_user

    async def fake_update_user(user: User):
        return user

    monkeypatch.setattr(
        "media_summarizer.utils.database_async.get_user_by_id", fake_get_user_by_id
    )
    monkeypatch.setattr(
        "media_summarizer.utils.database_async.update_user", fake_update_user
    )

    # Fake Spotify endpoints
    token_url = "https://accounts.spotify.com/api/token"
    me_url = "https://api.spotify.com/v1/me"

    fake_client = _FakeAsyncClient(
        post_map={
            token_url: _FakeResponse(
                {
                    "access_token": "at_123",
                    "refresh_token": "rt_123",
                    "expires_in": 3600,
                    "scope": "user-read-playback-position playlist-read-private",
                    "token_type": "Bearer",
                }
            )
        },
        get_map={me_url: _FakeResponse({"id": "spotify-user-1"})},
    )

    monkeypatch.setattr(auth_social.httpx, "AsyncClient", lambda *a, **k: fake_client)

    app = _build_app_with_auth_override(saved_user)
    client = TestClient(app, follow_redirects=False)

    # Step 1: login to set state cookie (requires auth)
    resp_login = client.get("/api/v1/auth/spotify/login")
    assert resp_login.status_code in (302, 307)
    state_cookie = client.cookies.get("oauth_state_spotify")
    assert state_cookie

    # Step 2: callback
    resp_cb = client.get(
        f"/api/v1/auth/spotify/callback?code=abc&state={state_cookie}"
    )
    assert resp_cb.status_code in (302, 303)
    # Should redirect to frontend success
    assert "auth/callback-success?provider=spotify" in resp_cb.headers.get(
        "location", ""
    )

    # User updated with spotify fields
    assert saved_user.spotify_user_id == "spotify-user-1"
    assert saved_user.spotify_access_token == "at_123"
    assert saved_user.spotify_refresh_token == "rt_123"
    assert saved_user.spotify_scope.startswith("user-read-playback-position")


@pytest.mark.asyncio
async def test_spotify_state_mismatch(monkeypatch):
    saved_user = User(email="tester@example.com")

    async def fake_get_user_by_id(user_id: str):
        return saved_user

    monkeypatch.setattr(
        "media_summarizer.utils.database_async.get_user_by_id", fake_get_user_by_id
    )

    app = _build_app_with_auth_override(saved_user)
    client = TestClient(app, follow_redirects=False)

    # Step 1: login
    resp_login = client.get("/api/v1/auth/spotify/login")
    assert resp_login.status_code in (302, 307)

    # Step 2: callback with mismatched state
    resp_cb = client.get(
        "/api/v1/auth/spotify/callback?code=abc&state=DIFFERENT_STATE"
    )
    assert resp_cb.status_code in (302, 303)
    assert "auth/callback-error?provider=spotify" in resp_cb.headers.get(
        "location", ""
    )