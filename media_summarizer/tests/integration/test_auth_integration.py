import pytest
pytestmark = pytest.mark.skip("Legacy magic-link endpoints removed (request-magic-link no longer available)")

"""
Integration tests for authentication system.

These tests verify that the authentication flow works end-to-end,
including magic link generation, email sending, token verification,
and JWT access token creation.
"""
import pytest
import asyncio
from unittest.mock import AsyncMock, patch, MagicMock
from datetime import datetime, timezone, timedelta
from fastapi.testclient import TestClient
from fastapi import FastAPI

from media_summarizer.api.endpoints.auth import router
from media_summarizer.api.dependencies.auth import get_current_user
from media_summarizer.core.models.auth import AuthToken, TokenType, AuthUser
from media_summarizer.core.models import User
from media_summarizer.utils.auth_utils import create_access_token, create_token_payload, verify_token
from media_summarizer.utils.database_async import DynamoDBConnection


class TestAuthIntegration:
    """Integration tests for authentication flow."""

    def setup_method(self):
        """Set up test client and app."""
        self.app = FastAPI()
        self.app.include_router(router, prefix="/auth")
        self.client = TestClient(self.app)

    @pytest.mark.asyncio
    async def test_complete_magic_link_flow(self):
        """Test complete magic link authentication flow."""
        email = "integration@example.com"
        user_id = "integration-user-123"

        # Step 1: Request magic link
        with patch('media_summarizer.utils.database_async.get_user_by_email') as mock_get_user, \
             patch('media_summarizer.utils.database_async.create_user') as mock_create_user, \
             patch('media_summarizer.utils.database_async.revoke_user_tokens') as mock_revoke, \
             patch('media_summarizer.utils.database_async.create_auth_token') as mock_create_token, \
             patch('media_summarizer.utils.email_service.email_service.send_magic_link_email') as mock_send_email, \
             patch('media_summarizer.utils.email_service.email_service.send_welcome_email') as mock_send_welcome:

            # Mock new user creation
            mock_get_user.return_value = None
            new_user = User(id=user_id, email=email, credits=100)
            mock_create_user.return_value = new_user

            # Mock async operations
            mock_revoke.return_value = AsyncMock()
            mock_create_token.return_value = AsyncMock()
            mock_send_email.return_value = AsyncMock()
            mock_send_welcome.return_value = AsyncMock()

            # Request magic link
            response = self.client.post(
                "/auth/request-magic-link",
                json={"email": email}
            )

            assert response.status_code == 200
            data = response.json()
            assert "Magic link sent" in data["message"]
            assert data["email"] == email

            # Verify user was created
            mock_create_user.assert_called_once()
            created_user = mock_create_user.call_args[0][0]
            assert created_user.email == email
            assert created_user.credits == 100

            # Verify magic token was created
            mock_create_token.assert_called_once()
            created_token = mock_create_token.call_args[0][0]
            assert created_token.user_id == user_id
            assert created_token.email == email
            assert created_token.token_type == TokenType.MAGIC_LINK

            # Verify emails were queued
            mock_send_email.assert_called_once()
            mock_send_welcome.assert_called_once()

        # Step 2: Verify magic link token
        magic_token = AuthToken.create_magic_link_token(user_id, email, 15)

        with patch('media_summarizer.utils.database_async.get_auth_token_by_token') as mock_get_token, \
             patch('media_summarizer.utils.database_async.get_user_by_id') as mock_get_user_by_id, \
             patch('media_summarizer.utils.database_async.update_auth_token') as mock_update_token:

            # Mock token and user retrieval
            mock_get_token.return_value = magic_token
            mock_get_user_by_id.return_value = new_user
            mock_update_token.return_value = AsyncMock()

            # Verify magic link token
            response = self.client.post(
                "/auth/verify-token",
                json={
                    "token": magic_token.token,
                    "email": email
                }
            )

            assert response.status_code == 200
            data = response.json()

            # Verify JWT token was returned
            assert "access_token" in data
            assert data["token_type"] == "bearer"
            assert data["expires_in"] == 24 * 60 * 60
            assert data["user"]["id"] == user_id
            assert data["user"]["email"] == email
            assert data["user"]["credits"] == 100

            # Verify token was marked as used
            mock_update_token.assert_called_once()
            updated_token = mock_update_token.call_args[0][0]
            assert updated_token.used_at is not None
            assert updated_token.is_active is False

            # Store JWT for next step
            jwt_token = data["access_token"]

        # Step 3: Use JWT token to access protected endpoint
        with patch('media_summarizer.utils.database_async.get_user_by_id') as mock_get_user_by_id:
            mock_get_user_by_id.return_value = new_user

            # Test JWT authentication works
            headers = {"Authorization": f"Bearer {jwt_token}"}
            response = self.client.get("/auth/me", headers=headers)

            assert response.status_code == 200
            data = response.json()
            assert data["id"] == user_id
            assert data["email"] == email
            assert data["credits"] == 100

    @pytest.mark.asyncio
    async def test_existing_user_magic_link_flow(self):
        """Test magic link flow for existing user."""
        email = "existing@example.com"
        user_id = "existing-user-123"
        existing_user = User(id=user_id, email=email, credits=50)

        with patch('media_summarizer.utils.database_async.get_user_by_email') as mock_get_user, \
             patch('media_summarizer.utils.database_async.revoke_user_tokens') as mock_revoke, \
             patch('media_summarizer.utils.database_async.create_auth_token') as mock_create_token, \
             patch('media_summarizer.utils.email_service.email_service.send_magic_link_email') as mock_send_email:

            # Mock existing user
            mock_get_user.return_value = existing_user
            mock_revoke.return_value = AsyncMock()
            mock_create_token.return_value = AsyncMock()
            mock_send_email.return_value = AsyncMock()

            # Request magic link
            response = self.client.post(
                "/auth/request-magic-link",
                json={"email": email}
            )

            assert response.status_code == 200
            data = response.json()
            assert "Magic link sent" in data["message"]
            assert data["email"] == email

            # Verify no new user was created
            mock_get_user.assert_called_once_with(email)

            # Verify existing tokens were revoked
            mock_revoke.assert_called_once_with(user_id, TokenType.MAGIC_LINK)

            # Verify new magic token was created
            mock_create_token.assert_called_once()
            created_token = mock_create_token.call_args[0][0]
            assert created_token.user_id == user_id
            assert created_token.email == email

    @pytest.mark.asyncio
    async def test_invalid_magic_link_scenarios(self):
        """Test various invalid magic link scenarios."""

        # Test 1: Invalid token
        with patch('media_summarizer.utils.database_async.get_auth_token_by_token') as mock_get_token:
            mock_get_token.return_value = None

            response = self.client.post(
                "/auth/verify-token",
                json={
                    "token": "invalid-token",
                    "email": "test@example.com"
                }
            )

            assert response.status_code == 401
            assert "Invalid magic link token" in response.json()["detail"]

        # Test 2: Expired token
        user_id = "test-user"
        email = "test@example.com"
        expired_token = AuthToken(
            user_id=user_id,
            email=email,
            token_type=TokenType.MAGIC_LINK,
            expires_at=datetime.now(timezone.utc) - timedelta(minutes=1)
        )

        with patch('media_summarizer.utils.database_async.get_auth_token_by_token') as mock_get_token:
            mock_get_token.return_value = expired_token

            response = self.client.post(
                "/auth/verify-token",
                json={
                    "token": expired_token.token,
                    "email": email
                }
            )

            assert response.status_code == 401
            assert "expired" in response.json()["detail"].lower()

        # Test 3: Already used token
        used_token = AuthToken.create_magic_link_token(user_id, email, 15)
        used_token.mark_as_used()

        with patch('media_summarizer.utils.database_async.get_auth_token_by_token') as mock_get_token:
            mock_get_token.return_value = used_token

            response = self.client.post(
                "/auth/verify-token",
                json={
                    "token": used_token.token,
                    "email": email
                }
            )

            assert response.status_code == 401
            assert "already been used" in response.json()["detail"]

        # Test 4: Email mismatch
        token_for_different_email = AuthToken.create_magic_link_token(user_id, "other@example.com", 15)

        with patch('media_summarizer.utils.database_async.get_auth_token_by_token') as mock_get_token:
            mock_get_token.return_value = token_for_different_email

            response = self.client.post(
                "/auth/verify-token",
                json={
                    "token": token_for_different_email.token,
                    "email": email  # Different email than token
                }
            )

            assert response.status_code == 401
            assert "Invalid magic link token" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_jwt_authentication_dependency(self):
        """Test JWT authentication dependency integration."""
        user_id = "jwt-test-user"
        email = "jwt@example.com"
        credits = 75

        # Create valid JWT token
        payload = create_token_payload(user_id, email, {"credits": credits})
        jwt_token = create_access_token(payload, timedelta(hours=1))

        # Mock user in database
        user = User(id=user_id, email=email, credits=credits)
        mock_db = DynamoDBConnection()

        with patch('media_summarizer.utils.database_async.get_user_by_id') as mock_get_user:
            mock_get_user.return_value = user

            # Test get_current_user dependency
            auth_user = await get_current_user(jwt_token, mock_db)

            assert isinstance(auth_user, AuthUser)
            assert auth_user.id == user_id
            assert auth_user.email == email
            assert auth_user.credits == credits

    @pytest.mark.asyncio
    async def test_token_security_features(self):
        """Test security features of the authentication system."""

        # Test 1: Token uniqueness
        user_id = "security-test-user"
        email = "security@example.com"

        token1 = AuthToken.create_magic_link_token(user_id, email, 15)
        token2 = AuthToken.create_magic_link_token(user_id, email, 15)

        # Tokens should be different even for same user
        assert token1.token != token2.token
        assert token1.id != token2.id

        # Test 2: JWT token validation
        valid_payload = create_token_payload(user_id, email)
        valid_token = create_access_token(valid_payload, timedelta(hours=1))

        # Should decode successfully
        decoded = verify_token(valid_token)
        assert decoded is not None
        assert decoded["sub"] == user_id
        assert decoded["email"] == email

        # Tampered token should fail
        tampered_token = valid_token[:-5] + "XXXXX"
        decoded_tampered = verify_token(tampered_token)
        assert decoded_tampered is None

        # Test 3: Token expiration enforcement
        expired_payload = create_token_payload(user_id, email)
        expired_token = create_access_token(expired_payload, timedelta(seconds=-1))

        decoded_expired = verify_token(expired_token)
        assert decoded_expired is None

    @pytest.mark.asyncio
    async def test_email_validation_in_flow(self):
        """Test email validation throughout the authentication flow."""

        # Test invalid email formats
        invalid_emails = [
            "invalid-email",
            "",
            "   ",
            "@example.com",
            "user@",
            "user space@example.com"
        ]

        for invalid_email in invalid_emails[:3]:  # Test first few to avoid too many requests
            response = self.client.post(
                "/auth/request-magic-link",
                json={"email": invalid_email}
            )
            assert response.status_code == 422  # Validation error

        # Test valid email normalization
        test_cases = [
            ("TEST@EXAMPLE.COM", "test@example.com"),
            ("  user@example.com  ", "user@example.com"),
            ("User.Name@Example.Com", "user.name@example.com")
        ]

        for input_email, expected_email in test_cases:
            with patch('media_summarizer.utils.database_async.get_user_by_email') as mock_get_user, \
                 patch('media_summarizer.utils.database_async.create_user') as mock_create_user, \
                 patch('media_summarizer.utils.database_async.revoke_user_tokens') as mock_revoke, \
                 patch('media_summarizer.utils.database_async.create_auth_token') as mock_create_token, \
                 patch('media_summarizer.utils.email_service.email_service.send_magic_link_email') as mock_send_email, \
                 patch('media_summarizer.utils.email_service.email_service.send_welcome_email') as mock_send_welcome:

                # Mock new user creation
                mock_get_user.return_value = None
                new_user = User(id="test-user", email=expected_email, credits=100)
                mock_create_user.return_value = new_user

                # Mock async operations
                mock_revoke.return_value = AsyncMock()
                mock_create_token.return_value = AsyncMock()
                mock_send_email.return_value = AsyncMock()
                mock_send_welcome.return_value = AsyncMock()

                response = self.client.post(
                    "/auth/request-magic-link",
                    json={"email": input_email}
                )

                assert response.status_code == 200
                data = response.json()
                assert data["email"] == expected_email

                # Verify user was created with normalized email
                mock_create_user.assert_called_once()
                created_user = mock_create_user.call_args[0][0]
                assert created_user.email == expected_email

    @pytest.mark.asyncio
    async def test_concurrent_magic_link_requests(self):
        """Test handling of concurrent magic link requests for same user."""
        email = "concurrent@example.com"
        user_id = "concurrent-user"
        user = User(id=user_id, email=email, credits=100)

        with patch('media_summarizer.utils.database_async.get_user_by_email') as mock_get_user, \
             patch('media_summarizer.utils.database_async.revoke_user_tokens') as mock_revoke, \
             patch('media_summarizer.utils.database_async.create_auth_token') as mock_create_token, \
             patch('media_summarizer.utils.email_service.email_service.send_magic_link_email') as mock_send_email:

            mock_get_user.return_value = user
            mock_revoke.return_value = AsyncMock()
            mock_create_token.return_value = AsyncMock()
            mock_send_email.return_value = AsyncMock()

            # Simulate concurrent requests
            responses = []
            for i in range(3):
                response = self.client.post(
                    "/auth/request-magic-link",
                    json={"email": email}
                )
                responses.append(response)

            # All requests should succeed
            for response in responses:
                assert response.status_code == 200
                data = response.json()
                assert "Magic link sent" in data["message"]

            # Verify revoke was called for each request (previous tokens invalidated)
            assert mock_revoke.call_count == 3

            # Verify new token was created for each request
            assert mock_create_token.call_count == 3


class TestAuthIntegrationErrorHandling:
    """Test error handling in authentication integration scenarios."""

    def setup_method(self):
        """Set up test client and app."""
        self.app = FastAPI()
        self.app.include_router(router, prefix="/auth")
        self.client = TestClient(self.app)

    @pytest.mark.asyncio
    async def test_database_errors_during_magic_link_flow(self):
        """Test handling of database errors during magic link flow."""
        email = "db-error@example.com"

        # Test database error during user lookup
        with patch('media_summarizer.utils.database_async.get_user_by_email') as mock_get_user:
            mock_get_user.side_effect = Exception("Database connection failed")

            response = self.client.post(
                "/auth/request-magic-link",
                json={"email": email}
            )

            assert response.status_code == 500
            assert "Failed to send magic link" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_email_service_errors(self):
        """Test handling of email service errors."""
        email = "email-error@example.com"
        user_id = "email-error-user"

        with patch('media_summarizer.utils.database_async.get_user_by_email') as mock_get_user, \
             patch('media_summarizer.utils.database_async.create_user') as mock_create_user, \
             patch('media_summarizer.utils.database_async.revoke_user_tokens') as mock_revoke, \
             patch('media_summarizer.utils.database_async.create_auth_token') as mock_create_token, \
             patch('media_summarizer.utils.email_service.email_service.send_magic_link_email') as mock_send_email:

            # Mock successful database operations
            mock_get_user.return_value = None
            new_user = User(id=user_id, email=email, credits=100)
            mock_create_user.return_value = new_user
            mock_revoke.return_value = AsyncMock()
            mock_create_token.return_value = AsyncMock()

            # Mock email service failure
            mock_send_email.side_effect = Exception("Email service unavailable")

            response = self.client.post(
                "/auth/request-magic-link",
                json={"email": email}
            )

            # Should still return success (email is background task)
            assert response.status_code == 200

            # But the background task would fail (logged but not exposed to user)
            # This is the expected behavior for background email sending

    @pytest.mark.asyncio
    async def test_malformed_requests(self):
        """Test handling of malformed authentication requests."""

        # Test missing email field
        response = self.client.post(
            "/auth/request-magic-link",
            json={}
        )
        assert response.status_code == 422

        # Test missing token field
        response = self.client.post(
            "/auth/verify-token",
            json={"email": "test@example.com"}
        )
        assert response.status_code == 422

        # Test missing email field in verification
        response = self.client.post(
            "/auth/verify-token",
            json={"token": "some-token"}
        )
        assert response.status_code == 422

        # Test invalid JSON
        response = self.client.post(
            "/auth/request-magic-link",
            data="invalid-json",
            headers={"Content-Type": "application/json"}
        )
        assert response.status_code == 422


if __name__ == "__main__":
    pytest.main([__file__])
