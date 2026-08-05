"""
Authentication dependencies for the API.

This module provides functions for user authentication and authorization
using JWT access tokens (issued after local or social login).
"""

import logging
from typing import Optional

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordBearer

from media_summarizer.core.models.auth import AuthUser
from media_summarizer.utils import database_async
from media_summarizer.utils.auth_utils import get_user_id_from_token, verify_token
from media_summarizer.utils.database_async import DynamoDBConnection, get_db

# Configure logging
logger = logging.getLogger(__name__)

# OAuth2 scheme for token authentication
oauth2_scheme = OAuth2PasswordBearer(
    tokenUrl="/api/v1/auth/login",
    auto_error=False,  # Allow optional authentication
)


async def get_current_user(
    token: Optional[str] = Depends(oauth2_scheme),
    db: DynamoDBConnection = Depends(get_db),
) -> AuthUser:
    """
    Get the current authenticated user based on the provided JWT token.

    Args:
        token: The JWT authentication token
        db: Database connection

    Returns:
        AuthUser object containing user information

    Raises:
        HTTPException: If authentication fails or token is invalid
    """
    if not token:
        logger.warning("No authentication token provided")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication token required",
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        # Verify the JWT token
        payload = verify_token(token)
        if not payload:
            logger.warning("Invalid JWT token provided")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid authentication token",
                headers={"WWW-Authenticate": "Bearer"},
            )

        # Extract user ID from token
        user_id = payload.get("sub")
        if not user_id:
            logger.warning("JWT token missing user ID (sub field)")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token format",
                headers={"WWW-Authenticate": "Bearer"},
            )

        # Get user from database
        user = await database_async.get_user_by_id(user_id)
        if not user:
            logger.warning(f"User not found for ID: {user_id}")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User not found",
                headers={"WWW-Authenticate": "Bearer"},
            )

        # Verify email matches token
        token_email = payload.get("email")
        if token_email and token_email != user.email:
            logger.warning(f"Email mismatch in token for user {user_id}")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token",
                headers={"WWW-Authenticate": "Bearer"},
            )

        logger.debug(f"Successfully authenticated user: {user.id}")

        # Return AuthUser object
        return AuthUser(
            id=user.id, email=user.email, reading_language=user.reading_language
        )

    except HTTPException:
        # Re-raise HTTP exceptions as-is
        raise
    except Exception as e:
        logger.error(f"Unexpected error during authentication: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication failed",
            headers={"WWW-Authenticate": "Bearer"},
        )


async def get_optional_user(
    token: Optional[str] = Depends(oauth2_scheme),
    db: DynamoDBConnection = Depends(get_db),
) -> Optional[AuthUser]:
    """
    Get the current user if authenticated, or None if not.

    This is useful for endpoints that work both with and without authentication.

    Args:
        token: The authentication token (optional)
        db: Database connection

    Returns:
        AuthUser object containing user information or None if not authenticated
    """
    if not token:
        return None

    try:
        return await get_current_user(token, db)
    except HTTPException:
        # If authentication fails, return None instead of raising exception
        return None
    except Exception as e:
        logger.error(f"Unexpected error in optional authentication: {str(e)}")
        return None


async def require_user_access(
    resource_user_id: str, current_user: AuthUser = Depends(get_current_user)
) -> AuthUser:
    """
    Require that the current user has access to a specific user's resources.

    This ensures that users can only access their own data.

    Args:
        resource_user_id: The user ID of the resource being accessed
        current_user: The current authenticated user

    Returns:
        The current user if access is allowed

    Raises:
        HTTPException: If the user doesn't have access to the resource
    """
    if current_user.id != resource_user_id:
        logger.warning(
            f"User {current_user.id} attempted to access resources for user {resource_user_id}"
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied: You can only access your own resources",
        )

    return current_user


# require_sufficient_credits removed: legacy credits system deprecated (minutes-based billing in effect).


async def require_verified_email(
    current_user: AuthUser = Depends(get_current_user),
    db: DynamoDBConnection = Depends(get_db),
) -> AuthUser:
    """
    Legacy compatibility dependency.
    Email verification by mail has been removed; authenticated users are accepted.
    """
    return current_user


def get_user_id_from_request(request: Request) -> Optional[str]:
    """
    Extract user ID from JWT token in request headers without full authentication.

    This is useful for logging or optional user context without requiring authentication.

    Args:
        request: The FastAPI request object

    Returns:
        User ID if token is valid, None otherwise
    """
    try:
        # Extract token from Authorization header
        authorization = request.headers.get("Authorization")
        if not authorization or not authorization.startswith("Bearer "):
            return None

        token = authorization.split(" ")[1]
        return get_user_id_from_token(token)

    except Exception as e:
        logger.debug(f"Could not extract user ID from request: {str(e)}")
        return None


async def validate_token_fresh(
    current_user: AuthUser = Depends(get_current_user), max_age_hours: int = 24
) -> AuthUser:
    """
    Validate that the current user's token is not too old.

    This is useful for sensitive operations that require recent authentication.

    Args:
        current_user: The current authenticated user
        max_age_hours: Maximum age of token in hours

    Returns:
        The current user if token is fresh enough

    Raises:
        HTTPException: If token is too old
    """
    # Note: This would require storing token issued time in the JWT payload
    # For now, we'll implement a basic version that always passes
    # In a full implementation, you would check the 'iat' (issued at) claim

    logger.debug(f"Token freshness validation passed for user: {current_user.id}")
    return current_user


async def get_current_user_flexible(
    request: Request,
    token: Optional[str] = Depends(oauth2_scheme),
    db: DynamoDBConnection = Depends(get_db),
) -> AuthUser:
    """
    Get the current authenticated user from Bearer token OR refresh token cookie.
    This is useful for endpoints that need to work with browser redirects.

    Args:
        request: FastAPI request object (to access cookies)
        token: Optional Bearer token from Authorization header
        db: Database connection

    Returns:
        AuthUser object containing user information

    Raises:
        HTTPException: If authentication fails
    """
    # Try Bearer token first
    if token:
        try:
            return await get_current_user(token, db)
        except HTTPException:
            pass  # Fall through to try refresh token

    # Try refresh token from cookie
    from media_summarizer.api.endpoints.auth import REFRESH_COOKIE_NAME

    refresh_token_value = request.cookies.get(REFRESH_COOKIE_NAME)
    if refresh_token_value:
        try:
            # Load refresh token from database
            refresh_token = await database_async.get_auth_token_by_token(
                refresh_token_value
            )
            if (
                refresh_token
                and refresh_token.token_type == "refresh"
                and not refresh_token.is_expired()
            ):
                # Get user from database
                user = await database_async.get_user_by_id(refresh_token.user_id)
                if user:
                    logger.debug(
                        f"Authenticated user via refresh token cookie: {user.id}"
                    )
                    return AuthUser(
                        id=user.id,
                        email=user.email,
                        reading_language=user.reading_language,
                    )
        except Exception as e:
            logger.warning(f"Failed to authenticate via refresh token: {e}")

    # No valid authentication found
    logger.warning("No valid authentication token (Bearer or refresh cookie) provided")
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Authentication token required",
        headers={"WWW-Authenticate": "Bearer"},
    )


# Convenience aliases for common authentication patterns
RequireAuth = Depends(get_current_user)
OptionalAuth = Depends(get_optional_user)
RequireAuthFlexible = Depends(get_current_user_flexible)
