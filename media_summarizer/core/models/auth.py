"""
Authentication models for application sessions (local auth + refresh tokens).
"""

from datetime import datetime, timezone, timedelta
from typing import Optional, Dict, Any
from pydantic import BaseModel, Field, field_validator
import uuid
import secrets
from enum import Enum


class TokenType(str, Enum):
    """Types of authentication tokens."""

    ACCESS_TOKEN = "access_token"
    REFRESH_TOKEN = "refresh_token"
    EMAIL_VERIFICATION = "email_verification"


class AuthToken(BaseModel):
    """Authentication token model (access, refresh, email verification)."""

    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    user_id: str = Field(..., description="ID of the user this token belongs to")
    email: str = Field(..., description="Email address associated with this token")
    token: str = Field(default_factory=lambda: secrets.token_urlsafe(32))
    token_type: TokenType = Field(..., description="Type of token")
    expires_at: datetime = Field(..., description="When the token expires")
    used_at: Optional[datetime] = Field(
        default=None, description="When the token was used"
    )
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    is_active: bool = Field(default=True, description="Whether the token is active")

    @field_validator("email")
    @classmethod
    def email_must_be_valid(cls, v):
        """Validate that the email is not empty and has basic format."""
        if not v.strip():
            raise ValueError("Email must not be empty")
        if "@" not in v:
            raise ValueError("Email must contain @ symbol")
        return v.lower().strip()

    @classmethod
    def create_access_token(
        cls, user_id: str, email: str, expires_in_hours: int = 24
    ) -> "AuthToken":
        """Create a new access token."""
        expires_at = datetime.now(timezone.utc) + timedelta(hours=expires_in_hours)
        return cls(
            user_id=user_id,
            email=email,
            token_type=TokenType.ACCESS_TOKEN,
            expires_at=expires_at,
        )

    @classmethod
    def create_refresh_token(
        cls,
        user_id: str,
        email: str,
        expires_in_days: int = 30,
        absolute_expires_at: Optional[datetime] = None,
    ) -> "AuthToken":
        """Create a new refresh token.

        If absolute_expires_at is provided, it will be used as the expires_at to enforce
        absolute session lifetime. Otherwise, expires_at is now + expires_in_days.
        """
        expires_at = absolute_expires_at or (
            datetime.now(timezone.utc) + timedelta(days=expires_in_days)
        )
        return cls(
            user_id=user_id,
            email=email,
            token_type=TokenType.REFRESH_TOKEN,
            expires_at=expires_at,
        )

    @classmethod
    def create_email_verification_token(
        cls,
        user_id: str,
        email: str,
        expires_in_hours: int = 24,
    ) -> "AuthToken":
        """Create a new email verification token (single-use)."""
        expires_at = datetime.now(timezone.utc) + timedelta(hours=expires_in_hours)
        return cls(
            user_id=user_id,
            email=email,
            token_type=TokenType.EMAIL_VERIFICATION,
            expires_at=expires_at,
        )

    def is_expired(self) -> bool:
        """Check if the token is expired."""
        return datetime.now(timezone.utc) > self.expires_at

    def is_valid(self) -> bool:
        """Check if the token is valid (not expired, not used, and active)."""
        return self.is_active and not self.is_expired() and self.used_at is None

    def mark_as_used(self) -> None:
        """Mark the token as used."""
        self.used_at = datetime.now(timezone.utc)
        self.is_active = False

    def revoke(self) -> None:
        """Revoke the token."""
        self.is_active = False

    def to_dynamodb_item(self) -> Dict[str, Any]:
        """Convert the model to a DynamoDB item."""
        item = {
            "id": self.id,
            "user_id": self.user_id,
            "email": self.email,
            "token": self.token,
            "token_type": self.token_type.value,
            "expires_at": self.expires_at.isoformat(),
            "created_at": self.created_at.isoformat(),
            "is_active": self.is_active,
        }
        if self.used_at:
            item["used_at"] = self.used_at.isoformat()
        return item

    @classmethod
    def from_dynamodb_item(cls, item: Dict[str, Any]) -> "AuthToken":
        """Create an AuthToken instance from a DynamoDB item."""
        used_at = None
        if "used_at" in item and item["used_at"]:
            used_at = datetime.fromisoformat(item["used_at"])

        return cls(
            id=item["id"],
            user_id=item["user_id"],
            email=item["email"],
            token=item["token"],
            token_type=TokenType(item["token_type"]),
            expires_at=datetime.fromisoformat(item["expires_at"]),
            used_at=used_at,
            created_at=datetime.fromisoformat(item["created_at"]),
            is_active=item.get("is_active", True),
        )

    def __repr__(self):
        return f"<AuthToken(id='{self.id}', user_id='{self.user_id}', token_type='{self.token_type}')>"


class TokenVerificationResponse(BaseModel):
    """Response model for token verification."""

    access_token: str = Field(..., description="JWT access token")
    token_type: str = Field(default="bearer", description="Token type")
    expires_in: int = Field(..., description="Token expiration time in seconds")
    user: Dict[str, Any] = Field(..., description="User information")


class RegisterRequest(BaseModel):
    """Request model for local registration (email/password)."""

    email: str = Field(..., description="User email")
    password: str = Field(..., description="User password (hashed at server)")

    @field_validator("email")
    @classmethod
    def email_must_be_valid(cls, v):
        if not v.strip():
            raise ValueError("Email must not be empty")
        if "@" not in v:
            raise ValueError("Email must contain @ symbol")
        return v.lower().strip()


class LoginRequest(BaseModel):
    """Request model for local login (email/password)."""

    email: str = Field(..., description="User email")
    password: str = Field(..., description="User password")

    @field_validator("email")
    @classmethod
    def email_must_be_valid(cls, v):
        if not v.strip():
            raise ValueError("Email must not be empty")
        if "@" not in v:
            raise ValueError("Email must contain @ symbol")
        return v.lower().strip()


class AuthUser(BaseModel):
    """Simplified user model for authentication responses (post-credits removal)."""

    id: str = Field(..., description="User ID")
    email: str = Field(..., description="User email")
    reading_language: Optional[str] = Field(
        default=None, description="Preferred reading language (ISO 639-1)"
    )


class EmailVerificationRequest(BaseModel):
    """Request model for email verification."""

    token: str = Field(..., description="Verification token")
    email: str = Field(..., description="Email to verify")

    @field_validator("email")
    @classmethod
    def email_must_be_valid(cls, v):
        if not v.strip():
            raise ValueError("Email must not be empty")
        if "@" not in v:
            raise ValueError("Email must contain @ symbol")
        return v.lower().strip()
