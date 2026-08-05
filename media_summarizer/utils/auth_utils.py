"""
JWT token utilities for authentication.
"""
import logging
import os
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional

from jose import JWTError, jwt
from passlib.context import CryptContext

# Configure logging
logger = logging.getLogger(__name__)

# JWT configuration (standardized)
# Prefer JWT_* variables with backward-compatible fallbacks
JWT_SECRET_KEY = os.environ.get("JWT_SECRET_KEY") or os.environ.get("SECRET_KEY", "your-secret-key-change-this-in-production")
JWT_ALGORITHM = os.environ.get("JWT_ALGORITHM", "HS256")
# Prefer minutes; fallback to 30 minutes if unset (security-first default)
JWT_ACCESS_TOKEN_EXPIRE_MINUTES = int(os.environ.get("JWT_ACCESS_TOKEN_EXPIRE_MINUTES", "30"))
# Optional seconds override (useful for short-lived dev tokens)
JWT_ACCESS_TOKEN_EXPIRE_SECONDS = int(os.environ.get("JWT_ACCESS_TOKEN_EXPIRE_SECONDS", "0"))

# Backward-compat constants (for existing imports in tests)
SECRET_KEY = JWT_SECRET_KEY
ALGORITHM = JWT_ALGORITHM
# Derive hours from minutes if not explicitly provided
try:
    if os.environ.get("ACCESS_TOKEN_EXPIRE_HOURS"):
        ACCESS_TOKEN_EXPIRE_HOURS = int(os.environ.get("ACCESS_TOKEN_EXPIRE_HOURS"))
    else:
        ACCESS_TOKEN_EXPIRE_HOURS = max(1, (JWT_ACCESS_TOKEN_EXPIRE_MINUTES + 59) // 60)
except Exception:
    ACCESS_TOKEN_EXPIRE_HOURS = 24

# Refresh token lifetime (defaults to days, but can be overridden in minutes/seconds for dev)
REFRESH_TOKEN_EXPIRE_DAYS = int(os.environ.get("REFRESH_TOKEN_EXPIRE_DAYS", "30"))
REFRESH_TOKEN_EXPIRE_MINUTES = int(os.environ.get("REFRESH_TOKEN_EXPIRE_MINUTES", "0"))
REFRESH_TOKEN_EXPIRE_SECONDS = int(os.environ.get("REFRESH_TOKEN_EXPIRE_SECONDS", "0"))


def get_access_token_expires_seconds() -> int:
    if JWT_ACCESS_TOKEN_EXPIRE_SECONDS > 0:
        return JWT_ACCESS_TOKEN_EXPIRE_SECONDS
    return max(1, JWT_ACCESS_TOKEN_EXPIRE_MINUTES * 60)


def get_access_token_expires_timedelta() -> timedelta:
    if JWT_ACCESS_TOKEN_EXPIRE_SECONDS > 0:
        return timedelta(seconds=JWT_ACCESS_TOKEN_EXPIRE_SECONDS)
    return timedelta(minutes=JWT_ACCESS_TOKEN_EXPIRE_MINUTES)


def get_refresh_token_expires_at(now: Optional[datetime] = None) -> datetime:
    now = now or datetime.now(timezone.utc)
    if REFRESH_TOKEN_EXPIRE_SECONDS > 0:
        return now + timedelta(seconds=REFRESH_TOKEN_EXPIRE_SECONDS)
    if REFRESH_TOKEN_EXPIRE_MINUTES > 0:
        return now + timedelta(minutes=REFRESH_TOKEN_EXPIRE_MINUTES)
    return now + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)

# Password hashing context (for future use if needed)
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def create_access_token(data: Dict[str, Any], expires_delta: Optional[timedelta] = None) -> str:
    """
    Create a JWT access token.

    Args:
        data: The data to encode in the token
        expires_delta: Optional custom expiration time

    Returns:
        Encoded JWT token string
    """
    to_encode = data.copy()

    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + get_access_token_expires_timedelta()

    to_encode.update({"exp": expire, "iat": datetime.now(timezone.utc)})

    try:
        encoded_jwt = jwt.encode(to_encode, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)
        logger.info(f"Access token created for user: {data.get('sub', 'unknown')}")
        return encoded_jwt
    except Exception as e:
        logger.error(f"Error creating access token: {str(e)}")
        raise


def verify_token(token: str) -> Optional[Dict[str, Any]]:
    """
    Verify and decode a JWT token.

    Args:
        token: The JWT token to verify

    Returns:
        Decoded token payload or None if invalid
    """
    try:
        payload = jwt.decode(token, JWT_SECRET_KEY, algorithms=[JWT_ALGORITHM])

        # Check if token is expired
        exp = payload.get("exp")
        if exp:
            exp_datetime = datetime.fromtimestamp(exp, tz=timezone.utc)
            if datetime.now(timezone.utc) > exp_datetime:
                logger.warning("Token has expired")
                return None

        # Validate required fields
        user_id = payload.get("sub")
        if not user_id:
            logger.warning("Token missing 'sub' (user_id) field")
            return None

        logger.debug(f"Token verified for user: {user_id}")
        return payload

    except JWTError as e:
        logger.warning(f"JWT verification failed: {str(e)}")
        return None
    except Exception as e:
        logger.error(f"Unexpected error verifying token: {str(e)}")
        return None


def get_user_id_from_token(token: str) -> Optional[str]:
    """
    Extract user ID from a JWT token.

    Args:
        token: The JWT token

    Returns:
        User ID or None if token is invalid
    """
    payload = verify_token(token)
    if payload:
        return payload.get("sub")
    return None


def create_token_payload(user_id: str, email: str, additional_data: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    Create a standardized token payload.

    Args:
        user_id: The user ID
        email: The user email
        additional_data: Optional additional data to include

    Returns:
        Token payload dictionary
    """
    payload = {
        "sub": user_id,  # Subject (user ID)
        "email": email,
        "type": "access_token"
    }

    if additional_data:
        payload.update(additional_data)

    return payload


def hash_password(password: str) -> str:
    """
    Hash a password using bcrypt.

    Args:
        password: Plain text password

    Returns:
        Hashed password
    """
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    Verify a password against its hash.

    Args:
        plain_password: Plain text password
        hashed_password: Hashed password to verify against

    Returns:
        True if password matches, False otherwise
    """
    try:
        return pwd_context.verify(plain_password, hashed_password)
    except Exception:
        return False


def is_token_expired(token: str) -> bool:
    """
    Check if a token is expired without fully validating it.

    Args:
        token: The JWT token to check

    Returns:
        True if expired, False if valid or if cannot determine
    """
    try:
        # Decode without verification to check expiration
        payload = jwt.decode(token, key="", options={"verify_signature": False, "verify_exp": False})
        exp = payload.get("exp")
        if exp:
            exp_datetime = datetime.fromtimestamp(exp, tz=timezone.utc)
            return datetime.now(timezone.utc) >= exp_datetime
        return False
    except Exception:
        return True  # Assume expired if we can't decode
