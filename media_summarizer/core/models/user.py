"""
User model for the Media Summarizer application (minutes-based billing era).

All legacy 'credits' fields and credit-manipulation methods have been REMOVED.
Le système de facturation repose sur les minute buckets (voir core.models.billing + utils.minute_db).

Structure DynamoDB:
- Partition key: id
- GSI: email-index (présumé) pour requêtes par email

Notes:
- Aucun champ nul n'est écrit dans DynamoDB (DynamoDB n'accepte pas les nulls).
- Les horodatages sont stockés en ISO8601 UTC.
"""

from datetime import datetime, timezone
from typing import Optional, Dict, Any
from pydantic import BaseModel, Field, field_validator
import uuid


class User(BaseModel):
    """
    Minimal user domain model (post-credits).
    """

    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    email: str = Field(..., min_length=1)

    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    # Optional auth-related / profile fields
    password_hash: Optional[str] = None
    auth_provider: Optional[str] = None  # e.g., "local", "google", "apple"
    provider_id: Optional[str] = None  # External provider subject / ID
    email_verified_at: Optional[datetime] = None
    name: Optional[str] = None
    avatar_url: Optional[str] = None

    # Linked accounts: Spotify (link-account flow)
    spotify_user_id: Optional[str] = None
    spotify_access_token: Optional[str] = None
    spotify_refresh_token: Optional[str] = None
    spotify_token_expires_at: Optional[datetime] = None
    spotify_scope: Optional[str] = None

    @field_validator("email")
    @classmethod
    def email_must_be_valid(cls, v: str) -> str:
        """Basic email sanity checks."""
        if not v or not v.strip():
            raise ValueError("Email must not be empty")
        v = v.strip().lower()
        if "@" not in v:
            raise ValueError("Email must contain '@'")
        return v

    def touch(self) -> None:
        """Update the updated_at timestamp."""
        self.updated_at = datetime.now(timezone.utc)

    def update(self, **kwargs):
        """
        Update mutable attributes (excluding id) then refresh updated_at.
        Silent ignore of unknown attributes.
        """
        for key, value in kwargs.items():
            if key == "id":
                continue
            if hasattr(self, key):
                setattr(self, key, value)
        self.touch()
        return self

    # ---------- DynamoDB Serialization ----------

    def to_dynamodb_item(self) -> Dict[str, Any]:
        """
        Convert model to a DynamoDB-compatible item (no nulls).
        """
        item: Dict[str, Any] = {
            "id": self.id,
            "email": self.email,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }
        if self.password_hash is not None:
            item["password_hash"] = self.password_hash
        if self.auth_provider is not None:
            item["auth_provider"] = self.auth_provider
        if self.provider_id is not None:
            item["provider_id"] = self.provider_id
        if self.email_verified_at is not None:
            item["email_verified_at"] = self.email_verified_at.isoformat()
        if self.name is not None:
            item["name"] = self.name
        if self.avatar_url is not None:
            item["avatar_url"] = self.avatar_url
        # Spotify linked account fields (only if present)
        if self.spotify_user_id is not None:
            item["spotify_user_id"] = self.spotify_user_id
        if self.spotify_access_token is not None:
            item["spotify_access_token"] = self.spotify_access_token
        if self.spotify_refresh_token is not None:
            item["spotify_refresh_token"] = self.spotify_refresh_token
        if self.spotify_token_expires_at is not None:
            item["spotify_token_expires_at"] = self.spotify_token_expires_at.isoformat()
        if self.spotify_scope is not None:
            item["spotify_scope"] = self.spotify_scope
        return item

    @classmethod
    def from_dynamodb_item(cls, item: Dict[str, Any]) -> "User":
        """
        Rehydrate a User from a DynamoDB item.
        Ignores any legacy 'credits' key if still present in table rows (transitional safety).
        """
        return cls(
            id=item["id"],
            email=item["email"],
            created_at=datetime.fromisoformat(item["created_at"]),
            updated_at=datetime.fromisoformat(item["updated_at"]),
            password_hash=item.get("password_hash"),
            auth_provider=item.get("auth_provider"),
            provider_id=item.get("provider_id"),
            email_verified_at=(
                datetime.fromisoformat(item["email_verified_at"])
                if item.get("email_verified_at")
                else None
            ),
            name=item.get("name"),
            avatar_url=item.get("avatar_url"),
            spotify_user_id=item.get("spotify_user_id"),
            spotify_access_token=item.get("spotify_access_token"),
            spotify_refresh_token=item.get("spotify_refresh_token"),
            spotify_token_expires_at=(
                datetime.fromisoformat(item["spotify_token_expires_at"])
                if item.get("spotify_token_expires_at")
                else None
            ),
            spotify_scope=item.get("spotify_scope"),
        )

    def __repr__(self) -> str:  # pragma: no cover (representation)
        return f"<User(id='{self.id}', email='{self.email}')>"
