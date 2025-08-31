import json
from fastapi.testclient import TestClient
from unittest.mock import AsyncMock, patch

from media_summarizer.api.main import app

client = TestClient(app)


def test_resend_verification_requires_auth():
    # No Authorization header -> should be 401
    resp = client.post("/api/v1/auth/resend-verification")
    assert resp.status_code == 401
    body = resp.json()
    assert "detail" in body


def test_verify_email_invalid_token():
    # Simulate invalid token without hitting DynamoDB/LocalStack
    with patch("media_summarizer.utils.database_async.get_auth_token_by_token", new_callable=AsyncMock) as mock_get_token:
        mock_get_token.return_value = None
        payload = {"token": "invalid-token", "email": "user@example.com"}
        resp = client.post("/api/v1/auth/verify-email", json=payload)
        assert resp.status_code == 401
        body = resp.json()
        assert "detail" in body

