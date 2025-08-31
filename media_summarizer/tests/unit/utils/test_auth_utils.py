"""
Unit tests for authentication utilities.
"""
import pytest
from unittest.mock import patch, MagicMock
from datetime import datetime, timezone, timedelta
from jose import jwt, JWTError
from media_summarizer.utils.auth_utils import (
    create_access_token,
    verify_token,
    get_user_id_from_token,
    create_token_payload,
    hash_password,
    verify_password,
    is_token_expired,
    SECRET_KEY,
    ALGORITHM
)


class TestCreateAccessToken:
    """Test create_access_token function."""

    def test_create_token_with_default_expiry(self):
        """Test creating token with default expiry."""
        data = {"sub": "user-123", "email": "test@example.com"}

        token = create_access_token(data)

        assert isinstance(token, str)
        assert len(token) > 50  # JWT tokens are long

        # Decode to verify content
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        assert payload["sub"] == "user-123"
        assert payload["email"] == "test@example.com"
        assert "exp" in payload
        assert "iat" in payload

    def test_create_token_with_custom_expiry(self):
        """Test creating token with custom expiry."""
        data = {"sub": "user-123", "email": "test@example.com"}
        expires_delta = timedelta(hours=2)

        token = create_access_token(data, expires_delta)

        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])

        # Check expiry is approximately 2 hours from now
        exp_time = datetime.fromtimestamp(payload["exp"], tz=timezone.utc)
        expected_exp = datetime.now(timezone.utc) + expires_delta
        time_diff = abs((exp_time - expected_exp).total_seconds())
        assert time_diff < 60  # Within 1 minute tolerance

    def test_create_token_preserves_data(self):
        """Test that all data is preserved in the token."""
        data = {
            "sub": "user-123",
            "email": "test@example.com",
            "credits": 100,
            "custom_field": "custom_value"
        }

        token = create_access_token(data)
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])

        assert payload["sub"] == "user-123"
        assert payload["email"] == "test@example.com"
        assert payload["credits"] == 100
        assert payload["custom_field"] == "custom_value"

    def test_create_token_adds_timestamps(self):
        """Test that exp and iat timestamps are added."""
        data = {"sub": "user-123"}

        before_creation = datetime.now(timezone.utc)
        token = create_access_token(data)
        after_creation = datetime.now(timezone.utc)

        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])

        # Check issued at time (allow 1 second tolerance)
        iat_time = datetime.fromtimestamp(payload["iat"], tz=timezone.utc)
        assert (before_creation - timedelta(seconds=1)) <= iat_time <= (after_creation + timedelta(seconds=1))

        # Check expiry time is in the future
        exp_time = datetime.fromtimestamp(payload["exp"], tz=timezone.utc)
        assert exp_time > after_creation

    @patch('media_summarizer.utils.auth_utils.jwt.encode')
    def test_create_token_handles_encoding_error(self, mock_encode):
        """Test error handling during token encoding."""
        mock_encode.side_effect = Exception("Encoding failed")

        data = {"sub": "user-123"}

        with pytest.raises(Exception, match="Encoding failed"):
            create_access_token(data)


class TestVerifyToken:
    """Test verify_token function."""

    def test_verify_valid_token(self):
        """Test verifying a valid token."""
        data = {"sub": "user-123", "email": "test@example.com"}
        token = create_access_token(data, timedelta(hours=1))

        payload = verify_token(token)

        assert payload is not None
        assert payload["sub"] == "user-123"
        assert payload["email"] == "test@example.com"

    def test_verify_expired_token(self):
        """Test verifying an expired token."""
        data = {"sub": "user-123", "email": "test@example.com"}
        token = create_access_token(data, timedelta(seconds=-1))  # Already expired

        payload = verify_token(token)

        assert payload is None

    def test_verify_invalid_token(self):
        """Test verifying an invalid token."""
        invalid_token = "invalid.token.string"

        payload = verify_token(invalid_token)

        assert payload is None

    def test_verify_token_with_wrong_secret(self):
        """Test verifying token with wrong secret."""
        # Create token with different secret
        wrong_secret = "wrong-secret"
        data = {"sub": "user-123"}
        wrong_token = jwt.encode(data, wrong_secret, algorithm=ALGORITHM)

        payload = verify_token(wrong_token)

        assert payload is None

    def test_verify_token_missing_sub(self):
        """Test verifying token without required 'sub' field."""
        data = {"email": "test@example.com"}  # Missing 'sub'
        token = create_access_token(data)

        payload = verify_token(token)

        assert payload is None

    def test_verify_none_token(self):
        """Test verifying None token."""
        payload = verify_token(None)
        assert payload is None

    def test_verify_empty_token(self):
        """Test verifying empty token."""
        payload = verify_token("")
        assert payload is None

    @patch('media_summarizer.utils.auth_utils.jwt.decode')
    def test_verify_token_jwt_error(self, mock_decode):
        """Test handling JWT errors during verification."""
        mock_decode.side_effect = JWTError("JWT error")

        token = "some.token.string"
        payload = verify_token(token)

        assert payload is None

    @patch('media_summarizer.utils.auth_utils.jwt.decode')
    def test_verify_token_unexpected_error(self, mock_decode):
        """Test handling unexpected errors during verification."""
        mock_decode.side_effect = Exception("Unexpected error")

        token = "some.token.string"
        payload = verify_token(token)

        assert payload is None


class TestGetUserIdFromToken:
    """Test get_user_id_from_token function."""

    def test_get_user_id_valid_token(self):
        """Test extracting user ID from valid token."""
        user_id = "user-123"
        data = {"sub": user_id, "email": "test@example.com"}
        token = create_access_token(data)

        extracted_user_id = get_user_id_from_token(token)

        assert extracted_user_id == user_id

    def test_get_user_id_invalid_token(self):
        """Test extracting user ID from invalid token."""
        invalid_token = "invalid.token.string"

        extracted_user_id = get_user_id_from_token(invalid_token)

        assert extracted_user_id is None

    def test_get_user_id_expired_token(self):
        """Test extracting user ID from expired token."""
        data = {"sub": "user-123", "email": "test@example.com"}
        token = create_access_token(data, timedelta(seconds=-1))

        extracted_user_id = get_user_id_from_token(token)

        assert extracted_user_id is None

    def test_get_user_id_missing_sub(self):
        """Test extracting user ID when sub is missing."""
        data = {"email": "test@example.com"}  # No 'sub' field
        token = create_access_token(data)

        extracted_user_id = get_user_id_from_token(token)

        assert extracted_user_id is None


class TestCreateTokenPayload:
    """Test create_token_payload function."""

    def test_create_basic_payload(self):
        """Test creating basic token payload."""
        user_id = "user-123"
        email = "test@example.com"

        payload = create_token_payload(user_id, email)

        assert payload["sub"] == user_id
        assert payload["email"] == email
        assert payload["type"] == "access_token"

    def test_create_payload_with_additional_data(self):
        """Test creating payload with additional data."""
        user_id = "user-123"
        email = "test@example.com"
        additional_data = {"credits": 100, "role": "user"}

        payload = create_token_payload(user_id, email, additional_data)

        assert payload["sub"] == user_id
        assert payload["email"] == email
        assert payload["type"] == "access_token"
        assert payload["credits"] == 100
        assert payload["role"] == "user"

    def test_create_payload_additional_data_overwrites(self):
        """Test that additional data can overwrite defaults."""
        user_id = "user-123"
        email = "test@example.com"
        additional_data = {"type": "refresh_token"}

        payload = create_token_payload(user_id, email, additional_data)

        assert payload["type"] == "refresh_token"  # Overwritten

    def test_create_payload_none_additional_data(self):
        """Test creating payload with None additional data."""
        user_id = "user-123"
        email = "test@example.com"

        payload = create_token_payload(user_id, email, None)

        assert payload["sub"] == user_id
        assert payload["email"] == email
        assert payload["type"] == "access_token"


class TestPasswordHashing:
    """Test password hashing functions."""

    def test_hash_password(self):
        """Test password hashing."""
        password = "test-password-123"

        hashed = hash_password(password)

        assert isinstance(hashed, str)
        assert len(hashed) > 50  # Bcrypt hashes are long
        assert hashed != password  # Should be different from original
        assert hashed.startswith("$2b$")  # Bcrypt format

    def test_hash_different_passwords_different_hashes(self):
        """Test that different passwords produce different hashes."""
        password1 = "password1"
        password2 = "password2"

        hash1 = hash_password(password1)
        hash2 = hash_password(password2)

        assert hash1 != hash2

    def test_hash_same_password_different_hashes(self):
        """Test that same password produces different hashes (salt)."""
        password = "test-password"

        hash1 = hash_password(password)
        hash2 = hash_password(password)

        assert hash1 != hash2  # Different due to salt

    def test_verify_correct_password(self):
        """Test verifying correct password."""
        password = "test-password-123"
        hashed = hash_password(password)

        result = verify_password(password, hashed)

        assert result is True

    def test_verify_incorrect_password(self):
        """Test verifying incorrect password."""
        password = "test-password-123"
        wrong_password = "wrong-password"
        hashed = hash_password(password)

        result = verify_password(wrong_password, hashed)

        assert result is False

    def test_verify_password_with_invalid_hash(self):
        """Test verifying password with invalid hash."""
        password = "test-password"
        invalid_hash = "invalid-hash"

        # Should not raise exception, just return False
        result = verify_password(password, invalid_hash)

        assert result is False

    def test_password_hash_roundtrip(self):
        """Test complete password hash and verification roundtrip."""
        passwords = [
            "simple",
            "complex-P@ssw0rd!",
            "with spaces and symbols #$%",
            "unicode-ëñçödéd",
            "very-long-password-with-many-characters-1234567890"
        ]

        for password in passwords:
            hashed = hash_password(password)
            assert verify_password(password, hashed) is True
            assert verify_password(password + "wrong", hashed) is False


class TestIsTokenExpired:
    """Test is_token_expired function."""

    def test_valid_token_not_expired(self):
        """Test that valid token is not considered expired."""
        data = {"sub": "user-123"}
        token = create_access_token(data, timedelta(minutes=5))

        result = is_token_expired(token)

        assert result is False

    def test_expired_token_is_expired(self):
        """Test that expired token is considered expired."""
        data = {"sub": "user-123"}
        token = create_access_token(data, timedelta(seconds=-1))

        result = is_token_expired(token)

        assert result is True

    def test_invalid_token_is_expired(self):
        """Test that invalid token is considered expired."""
        invalid_token = "invalid.token.string"

        result = is_token_expired(invalid_token)

        assert result is True

    def test_token_without_exp_not_expired(self):
        """Test token without expiry claim."""
        # Manually create token without exp claim
        data = {"sub": "user-123"}
        token_without_exp = jwt.encode(data, SECRET_KEY, algorithm=ALGORITHM)

        result = is_token_expired(token_without_exp)

        assert result is False

    def test_malformed_token_is_expired(self):
        """Test that malformed token is considered expired."""
        malformed_tokens = [
            "",
            "not.a.token",
            "header.only",
            "too.many.parts.here.extra",
            None
        ]

        for token in malformed_tokens:
            result = is_token_expired(token)
            assert result is True

    @patch('media_summarizer.utils.auth_utils.jwt.decode')
    def test_decode_exception_is_expired(self, mock_decode):
        """Test that decode exceptions result in expired status."""
        mock_decode.side_effect = Exception("Decode error")

        token = "some.token.string"
        result = is_token_expired(token)

        assert result is True


class TestEnvironmentConfiguration:
    """Test environment configuration and constants."""

    def test_secret_key_exists(self):
        """Test that SECRET_KEY is defined."""
        assert SECRET_KEY is not None
        assert isinstance(SECRET_KEY, str)
        assert len(SECRET_KEY) > 0

    def test_algorithm_is_hs256(self):
        """Test that algorithm is HS256."""
        assert ALGORITHM == "HS256"

    @patch.dict('os.environ', {'SECRET_KEY': 'test-secret', 'JWT_SECRET_KEY': 'test-secret'})
    def test_secret_key_from_environment(self):
        """Test that SECRET_KEY can be loaded from environment."""
        # Need to reload the module to pick up new environment
        import importlib
        import media_summarizer.utils.auth_utils
        importlib.reload(media_summarizer.utils.auth_utils)

        from media_summarizer.utils.auth_utils import SECRET_KEY as reloaded_secret
        assert reloaded_secret == 'test-secret'

    @patch.dict('os.environ', {'ACCESS_TOKEN_EXPIRE_HOURS': '48'})
    def test_token_expire_hours_from_environment(self):
        """Test that ACCESS_TOKEN_EXPIRE_HOURS can be loaded from environment."""
        import importlib
        import media_summarizer.utils.auth_utils
        importlib.reload(media_summarizer.utils.auth_utils)

        from media_summarizer.utils.auth_utils import ACCESS_TOKEN_EXPIRE_HOURS as reloaded_hours
        assert reloaded_hours == 48


class TestIntegration:
    """Integration tests for auth utilities."""

    def test_full_token_lifecycle(self):
        """Test complete token creation, verification, and expiry cycle."""
        user_id = "user-123"
        email = "test@example.com"

        # Create payload
        payload = create_token_payload(user_id, email, {"credits": 100})

        # Create token
        token = create_access_token(payload, timedelta(seconds=2))

        # Verify token immediately
        verified_payload = verify_token(token)
        assert verified_payload is not None
        assert verified_payload["sub"] == user_id
        assert verified_payload["email"] == email
        assert verified_payload["credits"] == 100

        # Extract user ID
        extracted_user_id = get_user_id_from_token(token)
        assert extracted_user_id == user_id

        # Check not expired
        assert is_token_expired(token) is False

        # Wait for expiry (in real test, you might mock time instead)
        import time
        time.sleep(2)

        # Check expired
        assert is_token_expired(token) is True

        # Verify returns None for expired token
        expired_payload = verify_token(token)
        assert expired_payload is None

        # Extract user ID returns None for expired token
        expired_user_id = get_user_id_from_token(token)
        assert expired_user_id is None

    def test_token_with_all_features(self):
        """Test token creation with all possible features."""
        user_id = "user-123"
        email = "test@example.com"
        additional_data = {
            "credits": 100,
            "role": "premium",
            "permissions": ["read", "write"],
            "metadata": {"last_login": "2024-01-01"}
        }

        # Create comprehensive payload
        payload = create_token_payload(user_id, email, additional_data)

        # Create token with custom expiry
        token = create_access_token(payload, timedelta(minutes=30))

        # Verify all data is preserved
        verified_payload = verify_token(token)
        assert verified_payload["sub"] == user_id
        assert verified_payload["email"] == email
        assert verified_payload["credits"] == 100
        assert verified_payload["role"] == "premium"
        assert verified_payload["permissions"] == ["read", "write"]
        assert verified_payload["metadata"]["last_login"] == "2024-01-01"
        assert verified_payload["type"] == "access_token"

        # Check timestamps
        assert "exp" in verified_payload
        assert "iat" in verified_payload

        # Verify expiry is approximately 30 minutes from now
        exp_time = datetime.fromtimestamp(verified_payload["exp"], tz=timezone.utc)
        expected_exp = datetime.now(timezone.utc) + timedelta(minutes=30)
        time_diff = abs((exp_time - expected_exp).total_seconds())
        assert time_diff < 60  # Within 1 minute tolerance


if __name__ == "__main__":
    pytest.main([__file__])
