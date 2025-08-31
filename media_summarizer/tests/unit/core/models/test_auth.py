"""
Unit tests for authentication models (post-magic-link migration).
"""
import pytest
from pydantic import ValidationError
from datetime import datetime, timezone, timedelta
from media_summarizer.core.models.auth import (
    AuthToken,
    TokenType,
    TokenVerificationResponse,
    AuthUser
)


class TestTokenType:
    def test_token_type_values(self):
        assert TokenType.ACCESS_TOKEN == "access_token"
        assert TokenType.REFRESH_TOKEN == "refresh_token"
        assert TokenType.EMAIL_VERIFICATION == "email_verification"

    def test_token_type_creation(self):
        assert TokenType("access_token") == TokenType.ACCESS_TOKEN
        assert TokenType("refresh_token") == TokenType.REFRESH_TOKEN
        assert TokenType("email_verification") == TokenType.EMAIL_VERIFICATION


class TestAuthToken:
    def test_access_token_creation(self):
        user_id = "test-user-123"
        email = "test@example.com"
        token = AuthToken.create_access_token(user_id, email, expires_in_hours=12)
        assert token.user_id == user_id
        assert token.email == email
        assert token.token_type == TokenType.ACCESS_TOKEN
        assert token.is_active is True
        assert token.used_at is None
        assert token.expires_at > datetime.now(timezone.utc)

    def test_refresh_token_creation_and_absolute(self):
        user_id = "test-user-123"
        email = "test@example.com"
        absolute = datetime.now(timezone.utc) + timedelta(days=5)
        token = AuthToken.create_refresh_token(user_id, email, absolute_expires_at=absolute)
        assert token.token_type == TokenType.REFRESH_TOKEN
        assert token.expires_at == absolute

    def test_email_verification_token_creation(self):
        user_id = "test-user-123"
        email = "test@example.com"
        token = AuthToken.create_email_verification_token(user_id, email, expires_in_hours=24)
        assert token.token_type == TokenType.EMAIL_VERIFICATION
        # within tolerance
        assert abs((token.expires_at - (datetime.now(timezone.utc) + timedelta(hours=24))).total_seconds()) < 60

    def test_email_validation_and_normalization(self):
        user_id = "test-user-123"
        expires_at = datetime.now(timezone.utc) + timedelta(hours=1)
        # normalization
        t = AuthToken(user_id=user_id, email="  TEST@EXAMPLE.COM  ", token_type=TokenType.ACCESS_TOKEN, expires_at=expires_at)
        assert t.email == "test@example.com"
        # invalids
        with pytest.raises(ValidationError):
            AuthToken(user_id=user_id, email="", token_type=TokenType.ACCESS_TOKEN, expires_at=expires_at)
        with pytest.raises(ValidationError):
            AuthToken(user_id=user_id, email="   ", token_type=TokenType.ACCESS_TOKEN, expires_at=expires_at)
        with pytest.raises(ValidationError):
            AuthToken(user_id=user_id, email="invalid-email", token_type=TokenType.ACCESS_TOKEN, expires_at=expires_at)

    def test_is_expired_and_is_valid(self):
        user_id = "test-user-123"
        email = "test@example.com"
        # not expired
        t1 = AuthToken(user_id=user_id, email=email, token_type=TokenType.ACCESS_TOKEN, expires_at=datetime.now(timezone.utc) + timedelta(minutes=5))
        assert t1.is_expired() is False
        assert t1.is_valid() is True
        # expired
        t2 = AuthToken(user_id=user_id, email=email, token_type=TokenType.ACCESS_TOKEN, expires_at=datetime.now(timezone.utc) - timedelta(minutes=1))
        assert t2.is_expired() is True
        assert t2.is_valid() is False
        # used
        t3 = AuthToken.create_access_token(user_id, email, 1)
        t3.mark_as_used()
        assert t3.is_valid() is False
        # revoked
        t4 = AuthToken.create_access_token(user_id, email, 1)
        t4.revoke()
        assert t4.is_valid() is False

    def test_dynamodb_roundtrip(self):
        user_id = "test-user-123"
        email = "test@example.com"
        original = AuthToken.create_access_token(user_id, email, 2)
        item = original.to_dynamodb_item()
        restored = AuthToken.from_dynamodb_item(item)
        assert restored.id == original.id
        assert restored.user_id == original.user_id
        assert restored.email == original.email
        assert restored.token == original.token
        assert restored.token_type == original.token_type
        assert restored.expires_at == original.expires_at
        assert restored.created_at == original.created_at
        assert restored.is_active == original.is_active
        assert restored.used_at == original.used_at

    def test_repr_contains(self):
        user_id = "test-user-123"
        email = "test@example.com"
        tok = AuthToken.create_access_token(user_id, email, 1)
        s = repr(tok)
        assert "AuthToken" in s
        assert tok.id in s
        assert user_id in s
        # Ensure token_type representation is present
        assert "token_type='" in s


class TestTokenVerificationResponse:
    def test_creation(self):
        access_token = "jwt-token-string"
        expires_in = 86400
        user_data = {"id": "user-123", "email": "test@example.com", "credits": 100}
        resp = TokenVerificationResponse(access_token=access_token, expires_in=expires_in, user=user_data)
        assert resp.access_token == access_token
        assert resp.token_type == "bearer"
        assert resp.expires_in == expires_in
        assert resp.user == user_data

    def test_custom_token_type(self):
        resp = TokenVerificationResponse(access_token="t", expires_in=3600, user={}, token_type="custom")
        assert resp.token_type == "custom"


class TestAuthUser:
    def test_creation(self):
        au = AuthUser(id="u1", email="test@example.com", credits=100)
        assert au.id == "u1"
        assert au.email == "test@example.com"
        assert au.credits == 100

    def test_required(self):
        with pytest.raises(ValidationError):
            AuthUser(email="e", credits=1)
        with pytest.raises(ValidationError):
            AuthUser(id="u", credits=1)
        with pytest.raises(ValidationError):
            AuthUser(id="u", email="e")
