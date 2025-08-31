"""
Unit tests for authentication dependencies and endpoints.
"""
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from datetime import datetime, timezone, timedelta
from fastapi import HTTPException
from fastapi.testclient import TestClient
from fastapi import FastAPI

from media_summarizer.api.dependencies.auth import (
    get_current_user,
    get_optional_user,
    require_user_access,
    require_sufficient_credits,
    get_user_id_from_request,
    validate_token_fresh
)
from media_summarizer.api.endpoints.auth import router
from media_summarizer.core.models.auth import (
    AuthUser,
    AuthToken,
    TokenType,
)
from media_summarizer.core.models import User
from media_summarizer.utils.auth_utils import create_access_token, create_token_payload


class TestGetCurrentUser:
    """Test get_current_user dependency."""

    @pytest.mark.asyncio
    async def test_get_current_user_valid_token(self):
        """Test get_current_user with valid token."""
        user_id = "test-user-123"
        email = "test@example.com"
        credits = 100

        # Create valid JWT token
        payload = create_token_payload(user_id, email, {"credits": credits})
        token = create_access_token(payload, timedelta(hours=1))

        # Mock user from database
        mock_user = User(id=user_id, email=email, credits=credits)
        mock_db = AsyncMock()

        with patch('media_summarizer.utils.database_async.get_user_by_id', return_value=mock_user):
            auth_user = await get_current_user(token, mock_db)

            assert isinstance(auth_user, AuthUser)
            assert auth_user.id == user_id
            assert auth_user.email == email
            assert auth_user.credits == credits

    @pytest.mark.asyncio
    async def test_get_current_user_no_token(self):
        """Test get_current_user with no token."""
        mock_db = AsyncMock()

        with pytest.raises(HTTPException) as exc_info:
            await get_current_user(None, mock_db)

        assert exc_info.value.status_code == 401
        assert "Authentication token required" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_get_current_user_invalid_token(self):
        """Test get_current_user with invalid token."""
        invalid_token = "invalid.token.string"
        mock_db = AsyncMock()

        with pytest.raises(HTTPException) as exc_info:
            await get_current_user(invalid_token, mock_db)

        assert exc_info.value.status_code == 401
        assert "Invalid authentication token" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_get_current_user_expired_token(self):
        """Test get_current_user with expired token."""
        user_id = "test-user-123"
        email = "test@example.com"

        # Create expired token
        payload = create_token_payload(user_id, email)
        expired_token = create_access_token(payload, timedelta(seconds=-1))

        mock_db = AsyncMock()

        with pytest.raises(HTTPException) as exc_info:
            await get_current_user(expired_token, mock_db)

        assert exc_info.value.status_code == 401
        assert "Invalid authentication token" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_get_current_user_user_not_found(self):
        """Test get_current_user when user doesn't exist in database."""
        user_id = "nonexistent-user"
        email = "test@example.com"

        # Create valid token for nonexistent user
        payload = create_token_payload(user_id, email)
        token = create_access_token(payload, timedelta(hours=1))

        mock_db = AsyncMock()

        with patch('media_summarizer.utils.database_async.get_user_by_id', return_value=None):
            with pytest.raises(HTTPException) as exc_info:
                await get_current_user(token, mock_db)

            assert exc_info.value.status_code == 401
            assert "User not found" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_get_current_user_email_mismatch(self):
        """Test get_current_user when token email doesn't match user email."""
        user_id = "test-user-123"
        token_email = "token@example.com"
        user_email = "user@example.com"

        # Create token with one email
        payload = create_token_payload(user_id, token_email)
        token = create_access_token(payload, timedelta(hours=1))

        # Mock user with different email
        mock_user = User(id=user_id, email=user_email, credits=100)
        mock_db = AsyncMock()

        with patch('media_summarizer.utils.database_async.get_user_by_id', return_value=mock_user):
            with pytest.raises(HTTPException) as exc_info:
                await get_current_user(token, mock_db)

            assert exc_info.value.status_code == 401
            assert "Invalid token" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_get_current_user_token_missing_sub(self):
        """Test get_current_user with token missing 'sub' field."""
        # Create token without 'sub' field
        payload = {"email": "test@example.com", "type": "access_token"}
        token = create_access_token(payload, timedelta(hours=1))

        mock_db = AsyncMock()

        with pytest.raises(HTTPException) as exc_info:
            await get_current_user(token, mock_db)

        assert exc_info.value.status_code == 401
        assert "Invalid authentication token" in exc_info.value.detail


class TestGetOptionalUser:
    """Test get_optional_user dependency."""

    @pytest.mark.asyncio
    async def test_get_optional_user_valid_token(self):
        """Test get_optional_user with valid token."""
        user_id = "test-user-123"
        email = "test@example.com"
        credits = 100

        payload = create_token_payload(user_id, email, {"credits": credits})
        token = create_access_token(payload, timedelta(hours=1))

        mock_user = User(id=user_id, email=email, credits=credits)
        mock_db = AsyncMock()

        with patch('media_summarizer.utils.database_async.get_user_by_id', return_value=mock_user):
            auth_user = await get_optional_user(token, mock_db)

            assert isinstance(auth_user, AuthUser)
            assert auth_user.id == user_id

    @pytest.mark.asyncio
    async def test_get_optional_user_no_token(self):
        """Test get_optional_user with no token returns None."""
        mock_db = AsyncMock()

        result = await get_optional_user(None, mock_db)
        assert result is None

    @pytest.mark.asyncio
    async def test_get_optional_user_invalid_token(self):
        """Test get_optional_user with invalid token returns None."""
        invalid_token = "invalid.token.string"
        mock_db = AsyncMock()

        result = await get_optional_user(invalid_token, mock_db)
        assert result is None

    @pytest.mark.asyncio
    async def test_get_optional_user_expired_token(self):
        """Test get_optional_user with expired token returns None."""
        user_id = "test-user-123"
        email = "test@example.com"

        payload = create_token_payload(user_id, email)
        expired_token = create_access_token(payload, timedelta(seconds=-1))

        mock_db = AsyncMock()

        result = await get_optional_user(expired_token, mock_db)
        assert result is None


class TestRequireUserAccess:
    """Test require_user_access dependency."""

    @pytest.mark.asyncio
    async def test_require_user_access_allowed(self):
        """Test require_user_access when user accesses own resources."""
        user_id = "test-user-123"
        auth_user = AuthUser(id=user_id, email="test@example.com", credits=100)

        result = await require_user_access(user_id, auth_user)
        assert result == auth_user

    @pytest.mark.asyncio
    async def test_require_user_access_denied(self):
        """Test require_user_access when user tries to access other's resources."""
        user_id = "test-user-123"
        other_user_id = "other-user-456"
        auth_user = AuthUser(id=user_id, email="test@example.com", credits=100)

        with pytest.raises(HTTPException) as exc_info:
            await require_user_access(other_user_id, auth_user)

        assert exc_info.value.status_code == 403
        assert "Access denied" in exc_info.value.detail


class TestRequireSufficientCredits:
    """Test require_sufficient_credits dependency."""

    @pytest.mark.asyncio
    async def test_require_sufficient_credits_allowed(self):
        """Test require_sufficient_credits when user has enough credits."""
        user_id = "test-user-123"
        email = "test@example.com"
        credits = 100
        required_credits = 50

        auth_user = AuthUser(id=user_id, email=email, credits=credits)
        fresh_user = User(id=user_id, email=email, credits=credits)

        mock_db = AsyncMock()

        with patch('media_summarizer.utils.database_async.get_user_by_id', return_value=fresh_user):
            result = await require_sufficient_credits(required_credits, auth_user, mock_db)

            assert result.credits == credits  # Should be updated with fresh data

    @pytest.mark.asyncio
    async def test_require_sufficient_credits_insufficient(self):
        """Test require_sufficient_credits when user doesn't have enough credits."""
        user_id = "test-user-123"
        email = "test@example.com"
        credits = 30
        required_credits = 50

        auth_user = AuthUser(id=user_id, email=email, credits=credits)
        fresh_user = User(id=user_id, email=email, credits=credits)

        mock_db = AsyncMock()

        with patch('media_summarizer.utils.database_async.get_user_by_id', return_value=fresh_user):
            with pytest.raises(HTTPException) as exc_info:
                await require_sufficient_credits(required_credits, auth_user, mock_db)

            assert exc_info.value.status_code == 402
            assert "Insufficient credits" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_require_sufficient_credits_user_not_found(self):
        """Test require_sufficient_credits when user is not found in database."""
        user_id = "test-user-123"
        auth_user = AuthUser(id=user_id, email="test@example.com", credits=100)
        required_credits = 50

        mock_db = AsyncMock()

        with patch('media_summarizer.utils.database_async.get_user_by_id', return_value=None):
            with pytest.raises(HTTPException) as exc_info:
                await require_sufficient_credits(required_credits, auth_user, mock_db)

            assert exc_info.value.status_code == 401
            assert "User not found" in exc_info.value.detail


class TestGetUserIdFromRequest:
    """Test get_user_id_from_request function."""

    def test_get_user_id_from_request_valid_token(self):
        """Test extracting user ID from request with valid token."""
        user_id = "test-user-123"
        email = "test@example.com"

        payload = create_token_payload(user_id, email)
        token = create_access_token(payload, timedelta(hours=1))

        # Mock request object
        mock_request = MagicMock()
        mock_request.headers.get.return_value = f"Bearer {token}"

        result = get_user_id_from_request(mock_request)
        assert result == user_id

    def test_get_user_id_from_request_no_authorization_header(self):
        """Test extracting user ID when no Authorization header."""
        mock_request = MagicMock()
        mock_request.headers.get.return_value = None

        result = get_user_id_from_request(mock_request)
        assert result is None

    def test_get_user_id_from_request_invalid_header_format(self):
        """Test extracting user ID with invalid header format."""
        mock_request = MagicMock()
        mock_request.headers.get.return_value = "InvalidFormat token"

        result = get_user_id_from_request(mock_request)
        assert result is None

    def test_get_user_id_from_request_invalid_token(self):
        """Test extracting user ID with invalid token."""
        mock_request = MagicMock()
        mock_request.headers.get.return_value = "Bearer invalid.token.string"

        result = get_user_id_from_request(mock_request)
        assert result is None


class TestValidateTokenFresh:
    """Test validate_token_fresh dependency."""

    @pytest.mark.asyncio
    async def test_validate_token_fresh_passes(self):
        """Test validate_token_fresh passes for valid user."""
        user_id = "test-user-123"
        auth_user = AuthUser(id=user_id, email="test@example.com", credits=100)

        result = await validate_token_fresh(auth_user)
        assert result == auth_user


# Note: Magic link endpoint tests removed due to migration to email/password + refresh. Endpoints tested elsewhere.


class TestErrorHandling:
    """Test error handling in authentication."""

    @pytest.mark.asyncio
    async def test_get_current_user_database_error(self):
        """Test get_current_user with database error."""
        user_id = "test-user-123"
        email = "test@example.com"

        payload = create_token_payload(user_id, email)
        token = create_access_token(payload, timedelta(hours=1))

        mock_db = AsyncMock()

        with patch('media_summarizer.utils.database_async.get_user_by_id', side_effect=Exception("Database error")):
            with pytest.raises(HTTPException) as exc_info:
                await get_current_user(token, mock_db)

            assert exc_info.value.status_code == 401
            assert "Authentication failed" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_require_sufficient_credits_database_error(self):
        """Test require_sufficient_credits with database error."""
        user_id = "test-user-123"
        auth_user = AuthUser(id=user_id, email="test@example.com", credits=100)
        mock_db = AsyncMock()

        with patch('media_summarizer.utils.database_async.get_user_by_id', side_effect=Exception("Database error")):
            with pytest.raises(Exception, match="Database error"):
                await require_sufficient_credits(50, auth_user, mock_db)


if __name__ == "__main__":
    pytest.main([__file__])
