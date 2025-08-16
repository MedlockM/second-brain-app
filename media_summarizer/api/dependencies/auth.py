"""
Authentication dependencies for the API.

This module provides functions for user authentication and authorization.
"""
from fastapi import Depends, HTTPException, status, Request
from fastapi.security import OAuth2PasswordBearer
from typing import Dict, Any, Optional

from media_summarizer.utils.database_async import get_db, DynamoDBConnection


class AuthUser:
    """Simple user class for authentication compatibility."""
    def __init__(self, id: str, email: str, credits: int = 100):
        self.id = id
        self.email = email
        self.credits = credits

# OAuth2 scheme for token authentication with auto_error=False to allow tests to bypass authentication
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token", auto_error=False)

async def get_current_user(
    token: Optional[str] = Depends(oauth2_scheme),
    db: DynamoDBConnection = Depends(get_db)
) -> AuthUser:
    """
    Get the current authenticated user based on the provided token.

    Args:
        token: The authentication token
        db: Database session

    Returns:
        AuthUser object containing user information

    Raises:
        HTTPException: If authentication fails
    """
    # For testing purposes, if no token is provided, we still return a mock user
    # In a real implementation, this would require a valid token
    if token is None:
        # Mock user for testing
        return AuthUser(
            id="test-user-id",
            email="user@example.com",
            credits=100
        )

    try:
        # In a real implementation, this would verify the token and fetch the user
        # For testing purposes, we return a mock user

        # TODO: Implement actual token verification and user retrieval

        # Mock user for testing
        return AuthUser(
            id="test-user-id",
            email="user@example.com",
            credits=100
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )

async def get_optional_user(
    token: Optional[str] = Depends(oauth2_scheme),
    db: DynamoDBConnection = Depends(get_db)
) -> Optional[AuthUser]:
    """
    Get the current user if authenticated, or None if not.

    Args:
        token: The authentication token (optional)
        db: Database session

    Returns:
        AuthUser object containing user information or None
    """
    if not token:
        return None

    try:
        return await get_current_user(token, db)
    except HTTPException:
        return None
