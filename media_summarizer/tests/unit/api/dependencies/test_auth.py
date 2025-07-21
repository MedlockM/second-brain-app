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


@pytest.fixture
def mock_db_session():
    """Create a mock database session for testing."""
    mock = AsyncMock()
    mock.execute = AsyncMock()
    mock.commit = AsyncMock()
    mock.rollback = AsyncMock()
    mock.close = AsyncMock()
    return mock


@pytest.mark.asyncio
async def test_get_current_user_success(mock_db_session):
    """Test successful user authentication."""
    # Setup
    token = "valid-token"
    
    # Execute
    user = await get_current_user(token, mock_db_session)
    
    # Verify
    assert user is not None
    assert user["id"] == "test-user-id"
    assert user["email"] == "user@example.com"
    assert user["credits"] == 100


@pytest.mark.asyncio
async def test_get_current_user_exception():
    """Test authentication failure."""
    # Setup
    token = "invalid-token"
    mock_db_session = AsyncMock()
    
    # Mock the internal implementation to raise an exception
    with patch("media_summarizer.api.dependencies.auth.get_current_user.__wrapped__", 
               side_effect=Exception("Authentication failed")):
        
        # Execute and verify
        with pytest.raises(HTTPException) as excinfo:
            await get_current_user(token, mock_db_session)
        
        assert excinfo.value.status_code == 401
        assert "Invalid authentication credentials" in excinfo.value.detail


@pytest.mark.asyncio
async def test_get_optional_user_with_valid_token(mock_db_session):
    """Test getting optional user with a valid token."""
    # Setup
    token = "valid-token"
    
    # Execute
    user = await get_optional_user(token, mock_db_session)
    
    # Verify
    assert user is not None
    assert user["id"] == "test-user-id"
    assert user["email"] == "user@example.com"


@pytest.mark.asyncio
async def test_get_optional_user_with_invalid_token(mock_db_session):
    """Test getting optional user with an invalid token."""
    # Setup
    token = "invalid-token"
    
    # Mock get_current_user to raise HTTPException
    with patch("media_summarizer.api.dependencies.auth.get_current_user", 
               side_effect=HTTPException(status_code=401, detail="Invalid token")):
        
        # Execute
        user = await get_optional_user(token, mock_db_session)
        
        # Verify
        assert user is None


@pytest.mark.asyncio
async def test_get_optional_user_without_token():
    """Test getting optional user without a token."""
    # Setup
    token = None
    mock_db_session = AsyncMock()
    
    # Execute
    user = await get_optional_user(token, mock_db_session)
    
    # Verify
    assert user is None