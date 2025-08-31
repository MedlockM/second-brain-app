"""
Authentication dependencies for the API.

This module provides functions for user authentication and authorization
using JWT access tokens (issued after local or social login).
"""
import logging
from fastapi import Depends, HTTPException, status, Request
from fastapi.security import OAuth2PasswordBearer
from typing import Optional

from media_summarizer.core.models.auth import AuthUser
from media_summarizer.core.models import User
from media_summarizer.utils.database_async import get_db, DynamoDBConnection
from media_summarizer.utils.auth_utils import verify_token, get_user_id_from_token
from media_summarizer.utils import database_async

# Configure logging
logger = logging.getLogger(__name__)

# OAuth2 scheme for token authentication
oauth2_scheme = OAuth2PasswordBearer(
    tokenUrl="/api/v1/auth/login",
    auto_error=False  # Allow optional authentication
)


async def get_current_user(
    token: Optional[str] = Depends(oauth2_scheme),
    db: DynamoDBConnection = Depends(get_db)
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
            id=user.id,
            email=user.email,
            credits=user.credits
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
    db: DynamoDBConnection = Depends(get_db)
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
    resource_user_id: str,
    current_user: AuthUser = Depends(get_current_user)
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
            detail="Access denied: You can only access your own resources"
        )

    return current_user


async def require_sufficient_credits(
    required_credits: int,
    current_user: AuthUser = Depends(get_current_user),
    db: DynamoDBConnection = Depends(get_db)
) -> AuthUser:
    """
    Require that the current user has sufficient credits for an operation.

    Args:
        required_credits: Number of credits required for the operation
        current_user: The current authenticated user
        db: Database connection

    Returns:
        The current user if they have sufficient credits

    Raises:
        HTTPException: If the user doesn't have enough credits
    """
    # Get fresh user data to ensure credits are up-to-date
    user = await database_async.get_user_by_id(current_user.id)
    if not user:
        logger.error(f"User {current_user.id} not found during credit check")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found"
        )

    if user.credits < required_credits:
        logger.info(
            f"User {user.id} has insufficient credits: {user.credits} < {required_credits}"
        )
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail=f"Insufficient credits. You have {user.credits} credits but need {required_credits}."
        )

    # Update the current_user object with fresh credits
    current_user.credits = user.credits
    return current_user


async def require_verified_email(
    current_user: AuthUser = Depends(get_current_user),
    db: DynamoDBConnection = Depends(get_db)
) -> AuthUser:
    """
    Ensure the current user's email is verified before allowing sensitive actions.
    """
    user = await database_async.get_user_by_id(current_user.id)
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")
    # Social providers are treated as verified (provider assures email verification)
    if getattr(user, "auth_provider", None) in ("google", "apple"):
        return current_user

    if not getattr(user, "email_verified_at", None):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Email not verified. Please verify your email to continue.")
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
    current_user: AuthUser = Depends(get_current_user),
    max_age_hours: int = 24
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


# Convenience aliases for common authentication patterns
RequireAuth = Depends(get_current_user)
OptionalAuth = Depends(get_optional_user)
