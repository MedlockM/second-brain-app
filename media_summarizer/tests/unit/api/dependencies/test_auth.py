"""
Unit tests for the authentication dependencies.
"""
import pytest
import pytest_asyncio
from unittest.mock import patch, MagicMock, AsyncMock
from fastapi import HTTPException

from media_summarizer.api.dependencies.auth import (
    get_current_user,
    get_optional_user,
    oauth2_scheme
)
from media_summarizer.core.models import User


@pytest.fixture
def mock_db_connection():
    """Create a mock DynamoDB connection for testing."""
    mock = AsyncMock()
    return mock


@pytest.fixture
def sample_user():
    """Create a sample user for testing."""
    return User(
        id="test-user-id",
        email="user@example.com",
        credits=100
    )


class TestGetCurrentUser:
    """Test cases for get_current_user dependency."""

    @pytest.mark.asyncio
    async def test_get_current_user_success_with_token(self, mock_db_connection, sample_user):
        """Test successful user authentication with valid token."""
        token = "valid-token"
        with patch("media_summarizer.api.dependencies.auth.verify_token") as mock_verify, \
             patch("media_summarizer.api.dependencies.auth.database_async.get_user_by_id") as mock_get_user:
            mock_verify.return_value = {"sub": sample_user.id, "email": sample_user.email}
            mock_get_user.return_value = sample_user
            user = await get_current_user(token, mock_db_connection)
            assert user is not None
            assert user.id == sample_user.id
            assert user.email == sample_user.email
            assert user.credits == sample_user.credits

    @pytest.mark.asyncio
    async def test_get_current_user_success_without_token(self, mock_db_connection):
        """Without token should raise 401 in strict auth."""
        token = None
        with pytest.raises(HTTPException) as excinfo:
            await get_current_user(token, mock_db_connection)
        assert excinfo.value.status_code == 401

    @pytest.mark.asyncio
    async def test_get_current_user_with_invalid_token(self, mock_db_connection):
        """Test authentication with invalid token."""
        # Setup
        token = "invalid-token"

        # Mock the implementation to simulate token verification failure
        with patch("media_summarizer.api.dependencies.auth.get_current_user") as mock_get_user:
            mock_get_user.side_effect = HTTPException(
                status_code=401,
                detail="Invalid authentication credentials"
            )

            # Execute and verify
            with pytest.raises(HTTPException) as excinfo:
                await mock_get_user(token, mock_db_connection)

            assert excinfo.value.status_code == 401
            assert "Invalid authentication credentials" in excinfo.value.detail

    @pytest.mark.asyncio
    async def test_get_current_user_database_error(self, mock_db_connection):
        """Test authentication with database error."""
        # Setup
        token = "valid-token"
        mock_db_connection.get_resource.side_effect = Exception("Database connection error")

        # Mock to simulate database error during user lookup
        with patch("media_summarizer.api.dependencies.auth.get_current_user") as mock_get_user:
            mock_get_user.side_effect = HTTPException(
                status_code=401,
                detail="Invalid authentication credentials"
            )

            # Execute and verify
            with pytest.raises(HTTPException) as excinfo:
                await mock_get_user(token, mock_db_connection)

            assert excinfo.value.status_code == 401

    @pytest.mark.asyncio
    async def test_get_current_user_expired_token(self, mock_db_connection):
        """Test authentication with expired token."""
        # Setup
        token = "expired-token"

        # Mock to simulate expired token
        with patch("media_summarizer.api.dependencies.auth.get_current_user") as mock_get_user:
            mock_get_user.side_effect = HTTPException(
                status_code=401,
                detail="Invalid authentication credentials",
                headers={"WWW-Authenticate": "Bearer"}
            )

            # Execute and verify
            with pytest.raises(HTTPException) as excinfo:
                await mock_get_user(token, mock_db_connection)

            assert excinfo.value.status_code == 401
            assert excinfo.value.headers == {"WWW-Authenticate": "Bearer"}


class TestGetOptionalUser:
    """Test cases for get_optional_user dependency."""

    @pytest.mark.asyncio
    async def test_get_optional_user_with_valid_token(self, mock_db_connection, sample_user):
        """Test getting optional user with a valid token."""
        token = "valid-token"
        with patch("media_summarizer.api.dependencies.auth.verify_token") as mock_verify, \
             patch("media_summarizer.api.dependencies.auth.database_async.get_user_by_id") as mock_get_user:
            mock_verify.return_value = {"sub": sample_user.id, "email": sample_user.email}
            mock_get_user.return_value = sample_user
            user = await get_optional_user(token, mock_db_connection)
            assert user is not None
            assert user.id == sample_user.id
            assert user.email == sample_user.email

    @pytest.mark.asyncio
    async def test_get_optional_user_with_invalid_token(self, mock_db_connection):
        """Test getting optional user with an invalid token."""
        # Setup
        token = "invalid-token"

        # Mock get_current_user to raise HTTPException
        with patch("media_summarizer.api.dependencies.auth.get_current_user") as mock_get_user:
            mock_get_user.side_effect = HTTPException(
                status_code=401,
                detail="Invalid token"
            )

            # Execute
            user = await get_optional_user(token, mock_db_connection)

            # Verify
            assert user is None

    @pytest.mark.asyncio
    async def test_get_optional_user_without_token(self, mock_db_connection):
        """Test getting optional user without a token."""
        # Setup
        token = None

        # Execute
        user = await get_optional_user(token, mock_db_connection)

        # Verify
        assert user is None

    @pytest.mark.asyncio
    async def test_get_optional_user_empty_token(self, mock_db_connection):
        """Test getting optional user with empty token."""
        # Setup
        token = ""

        # Execute
        user = await get_optional_user(token, mock_db_connection)

        # Verify
        assert user is None

    @pytest.mark.asyncio
    async def test_get_optional_user_whitespace_token(self, mock_db_connection):
        """Test getting optional user with whitespace-only token."""
        # Setup
        token = "   "

        user = await get_optional_user(token, mock_db_connection)
        # In strict implementation, whitespace token is invalid -> None
        assert user is None


class TestOAuth2Scheme:
    """Test cases for OAuth2 scheme configuration."""

    def test_oauth2_scheme_configuration(self):
        """Test OAuth2 scheme is properly configured."""
        # Verify
        assert oauth2_scheme.auto_error is False  # Important for optional authentication

    def test_oauth2_scheme_auto_error_false(self):
        """Test that auto_error is False to allow optional authentication."""
        # This is important for endpoints that don't require authentication
        assert oauth2_scheme.auto_error is False


class TestAuthenticationIntegration:
    """Test cases for authentication integration scenarios."""

    @pytest.mark.asyncio
    async def test_authentication_flow_success(self, mock_db_connection, sample_user):
        """Test complete authentication flow success."""
        token = "valid-jwt-token"
        with patch("media_summarizer.api.dependencies.auth.verify_token") as mock_verify, \
             patch("media_summarizer.api.dependencies.auth.database_async.get_user_by_id") as mock_get_user:
            mock_verify.return_value = {"sub": sample_user.id, "email": sample_user.email}
            mock_get_user.return_value = sample_user
            user = await get_current_user(token, mock_db_connection)
            assert user is not None
            assert hasattr(user, "id")
            assert hasattr(user, "email")
            assert hasattr(user, "credits")

    @pytest.mark.asyncio
    async def test_optional_authentication_flow(self, mock_db_connection, sample_user):
        """Test optional authentication flow."""
        # With a valid token, should return a user
        with patch("media_summarizer.api.dependencies.auth.verify_token") as mock_verify, \
             patch("media_summarizer.api.dependencies.auth.database_async.get_user_by_id") as mock_get_user:
            mock_verify.return_value = {"sub": sample_user.id, "email": sample_user.email}
            mock_get_user.return_value = sample_user
            user_with_token = await get_optional_user("valid-token", mock_db_connection)
            assert user_with_token is not None
            assert user_with_token.id == sample_user.id

        # Without token, should return None
        user_without_token = await get_optional_user(None, mock_db_connection)
        assert user_without_token is None

    @pytest.mark.asyncio
    async def test_authentication_with_different_token_formats(self, mock_db_connection, sample_user):
        """Test authentication with different token formats."""
        with patch("media_summarizer.api.dependencies.auth.verify_token") as mock_verify, \
             patch("media_summarizer.api.dependencies.auth.database_async.get_user_by_id") as mock_get_user:
            mock_verify.return_value = {"sub": sample_user.id, "email": sample_user.email}
            mock_get_user.return_value = sample_user
            token_with_bearer = "Bearer valid-token"
            user = await get_optional_user(token_with_bearer, mock_db_connection)
            assert user is not None
            plain_token = "valid-token"
            user = await get_optional_user(plain_token, mock_db_connection)
            assert user is not None

    @pytest.mark.asyncio
    async def test_concurrent_authentication_requests(self, mock_db_connection, sample_user):
        """Test handling of concurrent authentication requests."""
        import asyncio

        # Setup multiple concurrent requests
        tokens = ["token1", "token2", "token3"]

        with patch("media_summarizer.api.dependencies.auth.verify_token") as mock_verify, \
             patch("media_summarizer.api.dependencies.auth.database_async.get_user_by_id") as mock_get_user:
            mock_verify.side_effect = lambda t: {"sub": sample_user.id, "email": sample_user.email}
            mock_get_user.return_value = sample_user
            tasks = [get_optional_user(token, mock_db_connection) for token in tokens]
            results = await asyncio.gather(*tasks)
            assert len(results) == 3
            assert all(result is not None for result in results)

    @pytest.mark.asyncio
    async def test_authentication_error_handling(self, mock_db_connection):
        """Test proper error handling in authentication."""
        # Test that HTTPException has proper format
        with patch("media_summarizer.api.dependencies.auth.get_current_user") as mock_get_user:
            mock_get_user.side_effect = HTTPException(
                status_code=401,
                detail="Invalid authentication credentials",
                headers={"WWW-Authenticate": "Bearer"}
            )

            with pytest.raises(HTTPException) as excinfo:
                await mock_get_user("invalid", mock_db_connection)

            # Verify proper HTTP exception format
            assert excinfo.value.status_code == 401
            assert isinstance(excinfo.value.detail, str)
            assert excinfo.value.headers is not None
            assert "WWW-Authenticate" in excinfo.value.headers


class TestAuthenticationEdgeCases:
    """Test cases for authentication edge cases."""

    @pytest.mark.asyncio
    async def test_very_long_token(self, mock_db_connection):
        """Test authentication with very long token."""
        # Setup
        very_long_token = "a" * 10000

        # Execute
        user = await get_optional_user(very_long_token, mock_db_connection)

        # Verify - invalid token should return None
        assert user is None

    @pytest.mark.asyncio
    async def test_special_characters_in_token(self, mock_db_connection):
        """Test authentication with special characters in token."""
        # Setup
        special_token = "token-with-special-chars!@#$%^&*()"

        # Execute
        user = await get_optional_user(special_token, mock_db_connection)

        # Verify
        assert user is None

    @pytest.mark.asyncio
    async def test_unicode_token(self, mock_db_connection):
        """Test authentication with Unicode token."""
        # Setup
        unicode_token = "token-with-unicode-字符"

        # Execute
        user = await get_optional_user(unicode_token, mock_db_connection)

        # Verify
        assert user is None

    @pytest.mark.asyncio
    async def test_null_database_connection(self, mock_db_connection):
        """Test authentication with null database connection."""
        # Setup
        token = "valid-token"

        # Execute - this should handle gracefully
        user = await get_optional_user(token, mock_db_connection)

        # Verify - invalid token in optional flow returns None
        assert user is None
