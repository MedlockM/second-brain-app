"""
Unit tests for database authentication operations.
"""
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from datetime import datetime, timezone, timedelta
from botocore.exceptions import ClientError

from media_summarizer.utils.database_async import (
    create_auth_token,
    get_auth_token_by_token,
    get_auth_token_by_id,
    get_auth_tokens_by_user_id,
    update_auth_token,
    delete_auth_token,
    revoke_user_tokens,
    cleanup_expired_tokens,
    DynamoDBConnection
)
from media_summarizer.core.models.auth import AuthToken, TokenType
from media_summarizer.core.models import User


class TestCreateAuthToken:
    """Test create_auth_token function."""

    @pytest.mark.asyncio
    async def test_create_auth_token_success(self):
        """Test successful auth token creation."""
        user_id = "test-user-123"
        email = "test@example.com"
        token = AuthToken.create_email_verification_token(user_id, email, 15)

        # Mock DynamoDB table
        mock_table = AsyncMock()
        mock_table.put_item = AsyncMock()

        with patch('media_summarizer.utils.database_async.get_session') as mock_get_session:
            mock_session = MagicMock()
            mock_get_session.return_value = mock_session
            mock_session.resource.return_value.__aenter__.return_value = AsyncMock()
            mock_session.resource.return_value.__aenter__.return_value.Table = AsyncMock(return_value=mock_table)

            result = await create_auth_token(token)

            assert result == token
            mock_table.put_item.assert_called_once()
            call_args = mock_table.put_item.call_args
            assert call_args[1]['Item'] == token.to_dynamodb_item()
            assert call_args[1]['ConditionExpression'] == 'attribute_not_exists(id)'

    @pytest.mark.asyncio
    async def test_create_auth_token_already_exists(self):
        """Test creating auth token that already exists."""
        user_id = "test-user-123"
        email = "test@example.com"
        token = AuthToken.create_email_verification_token(user_id, email, 15)

        # Mock conditional check failure
        mock_table = AsyncMock()
        mock_table.put_item.side_effect = ClientError(
            {'Error': {'Code': 'ConditionalCheckFailedException'}},
            'PutItem'
        )

        with patch('media_summarizer.utils.database_async.get_session') as mock_get_session:
            mock_session = MagicMock()
            mock_get_session.return_value = mock_session
            mock_session.resource.return_value.__aenter__.return_value = AsyncMock()
            mock_session.resource.return_value.__aenter__.return_value.Table = AsyncMock(return_value=mock_table)

            with pytest.raises(ValueError, match="already exists"):
                await create_auth_token(token)

    @pytest.mark.asyncio
    async def test_create_auth_token_client_error(self):
        """Test creating auth token with DynamoDB client error."""
        user_id = "test-user-123"
        email = "test@example.com"
        token = AuthToken.create_email_verification_token(user_id, email, 15)

        # Mock other client error
        mock_table = AsyncMock()
        mock_table.put_item.side_effect = ClientError(
            {'Error': {'Code': 'ValidationException', 'Message': 'Invalid input'}},
            'PutItem'
        )

        with patch('media_summarizer.utils.database_async.get_session') as mock_get_session:
            mock_session = MagicMock()
            mock_get_session.return_value = mock_session
            mock_session.resource.return_value.__aenter__.return_value = AsyncMock()
            mock_session.resource.return_value.__aenter__.return_value.Table = AsyncMock(return_value=mock_table)

            with pytest.raises(ClientError):
                await create_auth_token(token)


class TestGetAuthTokenByToken:
    """Test get_auth_token_by_token function."""

    @pytest.mark.asyncio
    async def test_get_auth_token_by_token_found(self):
        """Test getting auth token by token string when found."""
        user_id = "test-user-123"
        email = "test@example.com"
        token = AuthToken.create_email_verification_token(user_id, email, 15)
        token_string = token.token

        # Mock DynamoDB response
        mock_table = AsyncMock()
        mock_table.query.return_value = {
            'Items': [token.to_dynamodb_item()]
        }

        with patch('media_summarizer.utils.database_async.get_session') as mock_get_session:
            mock_session = MagicMock()
            mock_get_session.return_value = mock_session
            mock_session.resource.return_value.__aenter__.return_value = AsyncMock()
            mock_session.resource.return_value.__aenter__.return_value.Table = AsyncMock(return_value=mock_table)

            result = await get_auth_token_by_token(token_string)

            assert result is not None
            assert result.token == token_string
            assert result.user_id == user_id
            assert result.email == email
            assert result.token_type == TokenType.EMAIL_VERIFICATION

            # Verify query parameters
            mock_table.query.assert_called_once()
            call_args = mock_table.query.call_args
            assert call_args[1]['IndexName'] == 'token-index'

    @pytest.mark.asyncio
    async def test_get_auth_token_by_token_not_found(self):
        """Test getting auth token by token string when not found."""
        token_string = "nonexistent-token"

        # Mock empty DynamoDB response
        mock_table = AsyncMock()
        mock_table.query.return_value = {'Items': []}

        with patch('media_summarizer.utils.database_async.get_session') as mock_get_session:
            mock_session = MagicMock()
            mock_get_session.return_value = mock_session
            mock_session.resource.return_value.__aenter__.return_value = AsyncMock()
            mock_session.resource.return_value.__aenter__.return_value.Table = AsyncMock(return_value=mock_table)

            result = await get_auth_token_by_token(token_string)

            assert result is None

    @pytest.mark.asyncio
    async def test_get_auth_token_by_token_client_error(self):
        """Test getting auth token with client error."""
        token_string = "test-token"

        mock_table = AsyncMock()
        mock_table.query.side_effect = ClientError(
            {'Error': {'Code': 'ResourceNotFoundException'}},
            'Query'
        )

        with patch('media_summarizer.utils.database_async.get_session') as mock_get_session:
            mock_session = MagicMock()
            mock_get_session.return_value = mock_session
            mock_session.resource.return_value.__aenter__.return_value = AsyncMock()
            mock_session.resource.return_value.__aenter__.return_value.Table = AsyncMock(return_value=mock_table)

            with pytest.raises(ClientError):
                await get_auth_token_by_token(token_string)


class TestGetAuthTokenById:
    """Test get_auth_token_by_id function."""

    @pytest.mark.asyncio
    async def test_get_auth_token_by_id_found(self):
        """Test getting auth token by ID when found."""
        user_id = "test-user-123"
        email = "test@example.com"
        token = AuthToken.create_email_verification_token(user_id, email, 15)
        token_id = token.id

        # Mock DynamoDB response
        mock_table = AsyncMock()
        mock_table.get_item.return_value = {
            'Item': token.to_dynamodb_item()
        }

        with patch('media_summarizer.utils.database_async.get_session') as mock_get_session:
            mock_session = MagicMock()
            mock_get_session.return_value = mock_session
            mock_session.resource.return_value.__aenter__.return_value = AsyncMock()
            mock_session.resource.return_value.__aenter__.return_value.Table = AsyncMock(return_value=mock_table)

            result = await get_auth_token_by_id(token_id)

            assert result is not None
            assert result.id == token_id
            assert result.user_id == user_id
            assert result.email == email

            # Verify get_item parameters
            mock_table.get_item.assert_called_once_with(Key={'id': token_id})

    @pytest.mark.asyncio
    async def test_get_auth_token_by_id_not_found(self):
        """Test getting auth token by ID when not found."""
        token_id = "nonexistent-token-id"

        # Mock empty DynamoDB response
        mock_table = AsyncMock()
        mock_table.get_item.return_value = {}

        with patch('media_summarizer.utils.database_async.get_session') as mock_get_session:
            mock_session = MagicMock()
            mock_get_session.return_value = mock_session
            mock_session.resource.return_value.__aenter__.return_value = AsyncMock()
            mock_session.resource.return_value.__aenter__.return_value.Table = AsyncMock(return_value=mock_table)

            result = await get_auth_token_by_id(token_id)

            assert result is None


class TestRevokeUserTokens:
    """Test revoke_user_tokens function."""

    @pytest.mark.asyncio
    async def test_revoke_user_tokens_success(self):
        """Test successful user token revocation."""
        user_id = "test-user-123"
        email = "test@example.com"

        # Create mock tokens
        token1 = AuthToken.create_email_verification_token(user_id, email, 15)
        token2 = AuthToken.create_access_token(user_id, email, 24)

        with patch('media_summarizer.utils.database_async.get_auth_tokens_by_user_id') as mock_get_tokens, \
             patch('media_summarizer.utils.database_async.update_auth_token') as mock_update:

            mock_get_tokens.return_value = [token1, token2]
            mock_update.return_value = AsyncMock()

            result = await revoke_user_tokens(user_id)

            assert result == 2  # Both tokens should be revoked
            assert mock_update.call_count == 2

            # Verify tokens were revoked
            assert not token1.is_active
            assert not token2.is_active

    @pytest.mark.asyncio
    async def test_revoke_user_tokens_with_type_filter(self):
        """Test revoking user tokens with type filter."""
        user_id = "test-user-123"
        email = "test@example.com"

        # Create mock tokens
        magic_token = AuthToken.create_email_verification_token(user_id, email, 15)
        access_token = AuthToken.create_access_token(user_id, email, 24)

        with patch('media_summarizer.utils.database_async.get_auth_tokens_by_user_id') as mock_get_tokens, \
             patch('media_summarizer.utils.database_async.update_auth_token') as mock_update:

            # Only return email verification tokens
            mock_get_tokens.return_value = [magic_token]
            mock_update.return_value = AsyncMock()

            result = await revoke_user_tokens(user_id, TokenType.EMAIL_VERIFICATION)

            assert result == 1
            mock_get_tokens.assert_called_once_with(user_id, TokenType.EMAIL_VERIFICATION)

    @pytest.mark.asyncio
    async def test_revoke_user_tokens_no_active_tokens(self):
        """Test revoking tokens when no active tokens exist."""
        user_id = "test-user-123"
        email = "test@example.com"

        # Create already revoked token
        revoked_token = AuthToken.create_email_verification_token(user_id, email, 15)
        revoked_token.revoke()

        with patch('media_summarizer.utils.database_async.get_auth_tokens_by_user_id') as mock_get_tokens, \
             patch('media_summarizer.utils.database_async.update_auth_token') as mock_update:

            mock_get_tokens.return_value = [revoked_token]

            result = await revoke_user_tokens(user_id)

            assert result == 0  # No tokens were revoked
            mock_update.assert_not_called()


class TestCleanupExpiredTokens:
    """Test cleanup_expired_tokens function."""

    @pytest.mark.asyncio
    async def test_cleanup_expired_tokens_success(self):
        """Test successful cleanup of expired tokens."""
        user_id = "test-user-123"
        email = "test@example.com"

        # Create expired and valid tokens
        expired_token = AuthToken(
            user_id=user_id,
            email=email,
            token_type=TokenType.EMAIL_VERIFICATION,
            expires_at=datetime.now(timezone.utc) - timedelta(minutes=1)
        )
        valid_token = AuthToken.create_email_verification_token(user_id, email, 15)

        mock_table = AsyncMock()
        mock_table.scan.return_value = {
            'Items': [expired_token.to_dynamodb_item(), valid_token.to_dynamodb_item()]
        }

        with patch('media_summarizer.utils.database_async.get_session') as mock_get_session, \
             patch('media_summarizer.utils.database_async.delete_auth_token') as mock_delete:

            mock_session = MagicMock()
            mock_get_session.return_value = mock_session
            mock_session.resource.return_value.__aenter__.return_value = AsyncMock()
            mock_session.resource.return_value.__aenter__.return_value.Table = AsyncMock(return_value=mock_table)

            result = await cleanup_expired_tokens()

            assert result == 1  # Only expired token should be deleted
            mock_delete.assert_called_once_with(expired_token.id)

    @pytest.mark.asyncio
    async def test_cleanup_expired_tokens_no_expired(self):
        """Test cleanup when no tokens are expired."""
        user_id = "test-user-123"
        email = "test@example.com"

        # Create only valid tokens
        valid_token1 = AuthToken.create_email_verification_token(user_id, email, 15)
        valid_token2 = AuthToken.create_access_token(user_id, email, 24)

        mock_table = AsyncMock()
        mock_table.scan.return_value = {
            'Items': [valid_token1.to_dynamodb_item(), valid_token2.to_dynamodb_item()]
        }

        with patch('media_summarizer.utils.database_async.get_session') as mock_get_session, \
             patch('media_summarizer.utils.database_async.delete_auth_token') as mock_delete:

            mock_session = MagicMock()
            mock_get_session.return_value = mock_session
            mock_session.resource.return_value.__aenter__.return_value = AsyncMock()
            mock_session.resource.return_value.__aenter__.return_value.Table = AsyncMock(return_value=mock_table)

            result = await cleanup_expired_tokens()

            assert result == 0  # No tokens should be deleted
            mock_delete.assert_not_called()


class TestGetAuthTokensByUserId:
    """Test get_auth_tokens_by_user_id function."""

    @pytest.mark.asyncio
    async def test_get_auth_tokens_by_user_id_found(self):
        """Test getting auth tokens by user ID when found."""
        user_id = "test-user-123"
        email = "test@example.com"

        token1 = AuthToken.create_email_verification_token(user_id, email, 15)
        token2 = AuthToken.create_access_token(user_id, email, 24)

        mock_table = AsyncMock()
        mock_table.query.return_value = {
            'Items': [token1.to_dynamodb_item(), token2.to_dynamodb_item()]
        }

        with patch('media_summarizer.utils.database_async.get_session') as mock_get_session:
            mock_session = MagicMock()
            mock_get_session.return_value = mock_session
            mock_session.resource.return_value.__aenter__.return_value = AsyncMock()
            mock_session.resource.return_value.__aenter__.return_value.Table = AsyncMock(return_value=mock_table)

            result = await get_auth_tokens_by_user_id(user_id)

            assert len(result) == 2
            assert result[0].user_id == user_id
            assert result[1].user_id == user_id

            # Verify query uses user-index
            mock_table.query.assert_called_once()
            call_args = mock_table.query.call_args
            assert call_args[1]['IndexName'] == 'user-index'

    @pytest.mark.asyncio
    async def test_get_auth_tokens_by_user_id_with_type_filter(self):
        """Test getting auth tokens by user ID with type filter."""
        user_id = "test-user-123"
        email = "test@example.com"

        magic_token = AuthToken.create_email_verification_token(user_id, email, 15)

        mock_table = AsyncMock()
        mock_table.query.return_value = {
            'Items': [magic_token.to_dynamodb_item()]
        }

        with patch('media_summarizer.utils.database_async.get_session') as mock_get_session:
            mock_session = MagicMock()
            mock_get_session.return_value = mock_session
            mock_session.resource.return_value.__aenter__.return_value = AsyncMock()
            mock_session.resource.return_value.__aenter__.return_value.Table = AsyncMock(return_value=mock_table)

            result = await get_auth_tokens_by_user_id(user_id, TokenType.EMAIL_VERIFICATION)

            assert len(result) == 1
            assert result[0].token_type == TokenType.EMAIL_VERIFICATION

            # Verify query uses user-type-index
            mock_table.query.assert_called_once()
            call_args = mock_table.query.call_args
            assert call_args[1]['IndexName'] == 'user-type-index'


class TestUpdateAuthToken:
    """Test update_auth_token function."""

    @pytest.mark.asyncio
    async def test_update_auth_token_success(self):
        """Test successful auth token update."""
        user_id = "test-user-123"
        email = "test@example.com"
        token = AuthToken.create_email_verification_token(user_id, email, 15)

        # Modify token
        token.mark_as_used()

        mock_table = AsyncMock()
        mock_table.put_item = AsyncMock()

        with patch('media_summarizer.utils.database_async.get_session') as mock_get_session:
            mock_session = MagicMock()
            mock_get_session.return_value = mock_session
            mock_session.resource.return_value.__aenter__.return_value = AsyncMock()
            mock_session.resource.return_value.__aenter__.return_value.Table = AsyncMock(return_value=mock_table)

            result = await update_auth_token(token)

            assert result == token
            mock_table.put_item.assert_called_once_with(Item=token.to_dynamodb_item())


class TestDeleteAuthToken:
    """Test delete_auth_token function."""

    @pytest.mark.asyncio
    async def test_delete_auth_token_success(self):
        """Test successful auth token deletion."""
        token_id = "test-token-id"

        mock_table = AsyncMock()
        mock_table.delete_item = AsyncMock()

        with patch('media_summarizer.utils.database_async.get_session') as mock_get_session:
            mock_session = MagicMock()
            mock_get_session.return_value = mock_session
            mock_session.resource.return_value.__aenter__.return_value = AsyncMock()
            mock_session.resource.return_value.__aenter__.return_value.Table = AsyncMock(return_value=mock_table)

            result = await delete_auth_token(token_id)

            assert result is True
            mock_table.delete_item.assert_called_once_with(Key={'id': token_id})


if __name__ == "__main__":
    pytest.main([__file__])
