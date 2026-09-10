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

import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional

from pydantic import BaseModel, Field, field_validator

# How long an account waits between two reading-language changes.
#
# The reading language is not a display setting: moving it translates the full
# text of every media the reader opens next, then each of that media's
# artifacts, at a provider cost we pay. That cost is bounded *per media* — a
# translation is persisted and never redone — but nothing bounded how often an
# account could reopen the door on its whole library, so the interval between
# two changes is what this guard-rail holds: one change per month, per account.
#
# A rolling 30-day window rather than a calendar month: under a calendar rule a
# change on 31 January and another on 1 February are a day apart and both
# legal, which is exactly the burst the guard exists to prevent.
READING_LANGUAGE_CHANGE_INTERVAL = timedelta(days=30)


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

    # User preferences
    reading_language: Optional[str] = None  # ISO 639-1 code (e.g., "fr", "en")

    # When the reading language last *moved*, which is what the once-a-month
    # guard-rail above is measured from. Stays None until one language actually
    # replaces another: choosing a first language (at onboarding, or on a first
    # visit to the setting) is not a change, it is the initial setting, and it
    # must not start the clock — otherwise a reader who mis-picks during
    # onboarding is locked out of their own library's language for a month.
    reading_language_changed_at: Optional[datetime] = None

    # IANA zone name of the user's device (e.g. "Europe/Paris"), never a UTC
    # offset: a stored "+02:00" is wrong six months a year, while the name
    # carries its own DST rules. Written by the app on every return to the
    # foreground, so a user who travels sees their Digest follow. Stays None
    # until the app has reported one — an account whose zone is unknown is a
    # valid account, and "unknown" is deliberately not backfilled to UTC (that
    # would ring at 20:30 in Paris). Consumers must tolerate the absence.
    # Named `iana_timezone` rather than `timezone` on two counts: `timezone` is
    # a DynamoDB reserved word, so any projection over this table would need an
    # expression alias, and it would shadow `datetime.timezone` in this module.
    iana_timezone: Optional[str] = None

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

    def reading_language_change_available_at(
        self, now: Optional[datetime] = None
    ) -> Optional[datetime]:
        """When the next reading-language change becomes possible.

        ``None`` means "right now": an account that never changed its language
        and one whose last change is older than
        ``READING_LANGUAGE_CHANGE_INTERVAL`` give the same answer — there is
        nothing to wait for. A datetime is the instant the guard-rail lifts, and
        the only figure a refused caller needs to be told.
        """
        if self.reading_language_changed_at is None:
            return None
        available_at = self.reading_language_changed_at + READING_LANGUAGE_CHANGE_INTERVAL
        reference = now if now is not None else datetime.now(timezone.utc)
        return available_at if available_at > reference else None

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
        if self.reading_language is not None:
            item["reading_language"] = self.reading_language
        if self.reading_language_changed_at is not None:
            item["reading_language_changed_at"] = self.reading_language_changed_at.isoformat()
        if self.iana_timezone is not None:
            item["iana_timezone"] = self.iana_timezone
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
            reading_language=item.get("reading_language"),
            reading_language_changed_at=(
                datetime.fromisoformat(item["reading_language_changed_at"])
                if item.get("reading_language_changed_at")
                else None
            ),
            iana_timezone=item.get("iana_timezone"),
        )

    def __repr__(self) -> str:  # pragma: no cover (representation)
        return f"<User(id='{self.id}', email='{self.email}')>"
