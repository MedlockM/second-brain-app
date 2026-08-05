"""
Security utilities for JWT token management.

This module provides helpers for:
- Creating and validating JWT access tokens
- Password hashing
"""
import logging
import os
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional

from jose import JWTError, jwt

logger = logging.getLogger(__name__)

# Configuration from environment
JWT_SECRET_KEY = os.environ.get("JWT_SECRET_KEY", "dev-secret-key-change-in-production")
JWT_ALGORITHM = os.environ.get("JWT_ALGORITHM", "HS256")
JWT_ACCESS_TOKEN_EXPIRE_MINUTES = int(os.environ.get("JWT_ACCESS_TOKEN_EXPIRE_MINUTES", "30"))


def create_access_token(data: Dict[str, Any], expires_minutes: Optional[int] = None) -> str:
    """
    Create a JWT access token.
    
    Args:
        data: The data to encode in the token (should include 'sub' for user ID)
        expires_minutes: Optional custom expiration time in minutes
        
    Returns:
        A signed JWT access token
    """
    to_encode = data.copy()
    
    if expires_minutes is None:
        expires_minutes = JWT_ACCESS_TOKEN_EXPIRE_MINUTES
        
    expire = datetime.now(timezone.utc) + timedelta(minutes=expires_minutes)
    to_encode.update({
        "exp": expire,
        "iat": datetime.now(timezone.utc),
        "type": "access"
    })
    
    encoded_jwt = jwt.encode(to_encode, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)
    
    user_id = data.get("sub", "unknown")
    logger.debug(f"Created access token for user {user_id}, expires at {expire}")
    
    return encoded_jwt


def verify_access_token(token: str) -> Dict[str, Any]:
    """
    Verify a JWT access token and return the payload.
    
    Args:
        token: The JWT access token
        
    Returns:
        The decoded token payload
        
    Raises:
        ValueError: If the token is invalid or expired
    """
    try:
        payload = jwt.decode(token, JWT_SECRET_KEY, algorithms=[JWT_ALGORITHM])
        
        # Verify token type
        if payload.get("type") != "access":
            raise ValueError("Invalid token type")
            
        return payload
        
    except JWTError as e:
        logger.warning(f"Access token verification failed: {str(e)}")
        raise ValueError(f"Invalid or expired access token: {str(e)}")


def create_refresh_token(user_id: str) -> str:
    """
    Create a refresh token (longer-lived than access token).
    
    TODO: Implement refresh token logic with separate storage
    """
    # For now, just create a longer-lived JWT
    # In production, store refresh tokens in database with ability to revoke
    expire = datetime.now(timezone.utc) + timedelta(days=30)
    to_encode = {
        "sub": user_id,
        "type": "refresh",
        "exp": expire,
        "iat": datetime.now(timezone.utc)
    }
    
    return jwt.encode(to_encode, JWT_SECRET_KEY + "-refresh", algorithm=JWT_ALGORITHM)


def hash_password(password: str) -> str:
    """
    Hash a password using bcrypt.
    
    TODO: Implement when password auth is needed
    """
    from passlib.context import CryptContext
    pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    Verify a password against its hash.
    
    TODO: Implement when password auth is needed
    """
    from passlib.context import CryptContext
    pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
    return pwd_context.verify(plain_password, hashed_password)
