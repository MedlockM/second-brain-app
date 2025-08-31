"""
Integration tests for social authentication (Google/Apple).

These tests mock provider responses and validate the account linking flow
for an existing user, ensuring a refresh cookie is set and the frontend
redirection occurs.
"""
import os
import json
import types
import pytest
from unittest.mock import AsyncMock, patch
from fastapi import FastAPI
from fastapi.testclient import TestClient

import media_summarizer.api.endpoints.auth_social as auth_social
from media_summarizer.core.models import User


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
    # Frontend and cookie settings for tests
    monkeypatch.setenv("FRONTEND_URL", "http://localhost:3000")
    auth_social.FRONTEND_URL = "http://localhost:3000"
    # Relax cookies in test
    auth_social.COOKIE_SECURE = False
    auth_social.COOKIE_SAMESITE = "lax"
    yield


def _build_app():
    app = FastAPI()
    app.include_router(auth_social.router, prefix="/api/v1/auth")
    return app


@pytest.mark.asyncio
async def test_google_links_existing_user(monkeypatch):
    # Configure provider creds
    auth_social.GOOGLE_CLIENT_ID = "client-id"
    auth_social.GOOGLE_CLIENT_SECRET = "client-secret"
    auth_social.GOOGLE_REDIRECT_URI = "http://localhost:8000/api/v1/auth/google/callback"

    # Fake user existing in DB
    existing = User(email="existing@example.com", credits=50)

    async def fake_get_user_by_email(email: str):
        return existing

    async def fake_update_user(user: User):
        return user

    async def fake_create_auth_token(token):
        return token

    # Mock DB helpers
    monkeypatch.setattr("media_summarizer.utils.database_async.get_user_by_email", fake_get_user_by_email)
    monkeypatch.setattr("media_summarizer.utils.database_async.update_user", fake_update_user)
    monkeypatch.setattr("media_summarizer.utils.database_async.create_auth_token", fake_create_auth_token)

    # Fake Google endpoints
    token_url = "https://oauth2.googleapis.com/token"
    info_url = "https://oauth2.googleapis.com/tokeninfo"

    fake_client = _FakeAsyncClient(
        post_map={token_url: _FakeResponse({"id_token": "dummy"})},
        get_map={
            info_url: _FakeResponse({
                "aud": auth_social.GOOGLE_CLIENT_ID,
                "iss": "https://accounts.google.com",
                "email": "existing@example.com",
                "email_verified": "true",
                "sub": "sub-123",
            })
        },
    )

    monkeypatch.setattr(auth_social.httpx, "AsyncClient", lambda *a, **k: fake_client)

    # App and client
    app = _build_app()
    client = TestClient(app, follow_redirects=False)

    # Step 1: login to set state cookie
    resp_login = client.get("/api/v1/auth/google/login")
    assert resp_login.status_code in (302, 307)
    state_cookie = client.cookies.get("oauth_state_google")
    assert state_cookie

    # Step 2: callback
    resp_cb = client.get(f"/api/v1/auth/google/callback?code=abc&state={state_cookie}")
    assert resp_cb.status_code in (302, 303)
    # Should redirect to frontend success
    assert "auth/callback-success?provider=google" in resp_cb.headers.get("location", "")
    # Refresh cookie set
    set_cookie = resp_cb.headers.get("set-cookie", "")
    assert "refresh_token=" in set_cookie


@pytest.mark.asyncio
async def test_apple_links_existing_user(monkeypatch):
    # Configure provider
    auth_social.APPLE_CLIENT_ID = "apple-client"
    auth_social.APPLE_TEAM_ID = "apple-team"
    auth_social.APPLE_KEY_ID = "apple-key"
    auth_social.APPLE_PRIVATE_KEY = "-----BEGIN PRIVATE KEY-----\n...\n-----END PRIVATE KEY-----"
    auth_social.APPLE_REDIRECT_URI = "http://localhost:8000/api/v1/auth/apple/callback"

    # Existing user
    existing = User(email="existing@example.com", credits=10)

    async def fake_get_user_by_email(email: str):
        return existing

    async def fake_update_user(user: User):
        return user

    async def fake_create_auth_token(token):
        return token

    monkeypatch.setattr("media_summarizer.utils.database_async.get_user_by_email", fake_get_user_by_email)
    monkeypatch.setattr("media_summarizer.utils.database_async.update_user", fake_update_user)
    monkeypatch.setattr("media_summarizer.utils.database_async.create_auth_token", fake_create_auth_token)

    # Patch token exchange and id_token verification
    token_url = "https://appleid.apple.com/auth/token"
    fake_client = _FakeAsyncClient(post_map={token_url: _FakeResponse({"id_token": "dummy"})})
    monkeypatch.setattr(auth_social.httpx, "AsyncClient", lambda *a, **k: fake_client)

    async def fake_verify(id_token: str):
        return {"sub": "apple-sub", "email": "existing@example.com", "email_verified": "true"}

    # Avoid building a real ES256 client_secret from a PEM during tests
    monkeypatch.setattr(auth_social, "_apple_build_client_secret", lambda: "dummy_client_secret")
    monkeypatch.setattr(auth_social, "_apple_verify_id_token", fake_verify)

    app = _build_app()
    client = TestClient(app, follow_redirects=False)

    # Step 1: login
    resp_login = client.get("/api/v1/auth/apple/login")
    assert resp_login.status_code in (302, 307)
    state_cookie = client.cookies.get("oauth_state_apple")
    assert state_cookie

    # Step 2: callback
    resp_cb = client.get(f"/api/v1/auth/apple/callback?code=abc&state={state_cookie}")
    assert resp_cb.status_code in (302, 303)
    assert "auth/callback-success?provider=apple" in resp_cb.headers.get("location", "")
    set_cookie = resp_cb.headers.get("set-cookie", "")
    assert "refresh_token=" in set_cookie

