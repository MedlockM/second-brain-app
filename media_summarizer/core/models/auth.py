"""
Authentication models for application sessions (local auth + refresh tokens).

A refresh token is one link of a *lineage*: login mints the first token with a
fresh ``lineage_id``, and every rotation carries that same id over to its
successor. The lineage is the server-side identity of one device session — it is
generated here, never supplied by the client — and it is what logout revokes so
that signing out of a tablet leaves the phone signed in (task-294).
"""

import secrets
import uuid
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any, Dict, Optional, Tuple

from pydantic import BaseModel, Field, field_validator

# Margin between a token's own expiry and the epoch it is handed to DynamoDB TTL.
# The invariant is one-directional: the TTL timestamp must sit strictly *after*
# expires_at, so a sweep can never delete a row that could still authenticate a
# request. Seven days is comfortably past the ~48 h DynamoDB takes to honour a
# TTL, and leaves a short window where an expired session is still readable for
# debugging before it disappears.
TOKEN_TTL_MARGIN = timedelta(days=7)


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
    lineage_id: str = Field(
        default_factory=lambda: str(uuid.uuid4()),
        description="Device-session lineage: constant across every rotation of a session",
    )
    replaced_by_refresh_token: Optional[str] = Field(
        default=None,
        description="Refresh token minted in exchange for this one, replayed inside the rotation grace window",
    )
    replaced_by_access_token: Optional[str] = Field(
        default=None,
        description="Access token minted in exchange for this one, replayed inside the rotation grace window",
    )

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
        expires_at: datetime,
        lineage_id: Optional[str] = None,
    ) -> "AuthToken":
        """Create a refresh token expiring at ``expires_at``.

        The caller owns the expiry because the policy is sliding: every rotation
        recomputes ``now + REFRESH_TOKEN_EXPIRE_DAYS`` instead of inheriting the
        expiry of the token it replaces. There is no absolute session cap — a user
        who opens the app once a year never signs in again, and an abandoned
        device still falls out of the system on its own.

        ``lineage_id`` is omitted at login (a new device session opens its own
        lineage) and passed at rotation to keep the successor in the same lineage.
        """
        return cls(
            user_id=user_id,
            email=email,
            token_type=TokenType.REFRESH_TOKEN,
            expires_at=expires_at,
            lineage_id=lineage_id or str(uuid.uuid4()),
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

    def mark_as_rotated(self, refresh_token: str, access_token: str) -> None:
        """Consume the token and remember the pair minted in exchange for it.

        Storing the successor pair is what makes the rotation grace window
        possible: two requests racing on the same refresh token (an app resumed
        while a request was already in flight, or a restored backup leaving two
        devices holding the same token) both get a working session instead of the
        loser being signed out.
        """
        self.used_at = datetime.now(timezone.utc)
        self.is_active = False
        self.replaced_by_refresh_token = refresh_token
        self.replaced_by_access_token = access_token

    def rotation_replay(self, grace_seconds: int) -> Optional[Tuple[str, str]]:
        """The ``(access_token, refresh_token)`` pair to replay, if still allowed.

        Returns ``None`` once the window has closed, so a late reuse of a consumed
        token stays a rejection, and ``None`` for a token that was revoked rather
        than rotated — a logout must never be replayable.
        """
        if (
            self.used_at is None
            or not self.replaced_by_refresh_token
            or not self.replaced_by_access_token
        ):
            return None
        if self.rotated_seconds_ago() > grace_seconds:
            return None
        return self.replaced_by_access_token, self.replaced_by_refresh_token

    def rotated_seconds_ago(self) -> float:
        """Seconds since this token was consumed (0.0 if it never was)."""
        if self.used_at is None:
            return 0.0
        return max(
            0.0, (datetime.now(timezone.utc) - self.used_at).total_seconds()
        )

    def revoke(self) -> None:
        """Revoke the token."""
        self.is_active = False

    def ttl_epoch(self) -> int:
        """Epoch seconds handed to DynamoDB TTL, strictly after ``expires_at``."""
        return int((self.expires_at + TOKEN_TTL_MARGIN).timestamp())

    def to_dynamodb_item(self) -> Dict[str, Any]:
        """Convert the model to a DynamoDB item."""
        item: Dict[str, Any] = {
            "id": self.id,
            "user_id": self.user_id,
            "email": self.email,
            "token": self.token,
            "token_type": self.token_type.value,
            "expires_at": self.expires_at.isoformat(),
            "created_at": self.created_at.isoformat(),
            "is_active": self.is_active,
            "lineage_id": self.lineage_id,
            # TTL attribute — see TOKEN_TTL_MARGIN. Writing it on every put is what
            # keeps a rotated row's sweep date aligned with its own expiry.
            "expire_at": self.ttl_epoch(),
        }
        if self.used_at:
            item["used_at"] = self.used_at.isoformat()
        if self.replaced_by_refresh_token:
            item["replaced_by_refresh_token"] = self.replaced_by_refresh_token
        if self.replaced_by_access_token:
            item["replaced_by_access_token"] = self.replaced_by_access_token
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
            # A row written before lineages existed gets one of its own, which is
            # the right answer: it belongs to exactly one device session.
            lineage_id=item.get("lineage_id") or str(uuid.uuid4()),
            replaced_by_refresh_token=item.get("replaced_by_refresh_token"),
            replaced_by_access_token=item.get("replaced_by_access_token"),
        )

    def __repr__(self):
        return f"<AuthToken(id='{self.id}', user_id='{self.user_id}', token_type='{self.token_type}')>"


class TokenVerificationResponse(BaseModel):
    """Session payload returned by register, login and refresh.

    The refresh token travels in the JSON body: the only client is the mobile
    app, which stores it in the secure store and sends it back to /refresh.
    """

    access_token: str = Field(..., description="JWT access token")
    refresh_token: str = Field(
        ...,
        description="Opaque refresh token, rotated at /refresh with a sliding one-year expiry",
    )
    token_type: str = Field(default="bearer", description="Token type")
    expires_in: int = Field(..., description="Access token lifetime in seconds")
    user: Dict[str, Any] = Field(..., description="User information")


class RefreshRequest(BaseModel):
    """Request model for /refresh: the refresh token is sent in the body."""

    refresh_token: str = Field(..., description="Refresh token issued at login")


class LogoutRequest(BaseModel):
    """Request model for /logout.

    The refresh token identifies which device session to close: the access token
    in the Authorization header says *who* is calling, not *from where*. Without
    it the server could only revoke every session of the account.
    """

    refresh_token: str = Field(
        ..., description="Refresh token of the device being signed out"
    )


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
