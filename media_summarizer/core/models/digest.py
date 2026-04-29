"""
Digest models for daily/weekly in-app digests.

DynamoDB table: user_digests
- PK: user_id (S)
- SK: digest_key (S) - format: "{digest_type}#{period_key}" e.g. "daily#2026-04-29" or "weekly#2026-W18"

DynamoDB table: user_digest_settings
- PK: user_id (S)
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


class DigestType(str, Enum):
    DAILY = "daily"
    WEEKLY = "weekly"


class DigestStatus(str, Enum):
    PENDING = "pending"  # Digest is being assembled (summary_short generation in progress)
    READY = "ready"  # All summary_shorts are generated, digest is consultable
    PUBLISHED = "published"  # Digest has been published (push notification sent for weekly)


class DigestMediaItem(BaseModel):
    """A media item included in a digest with its summary_short status."""

    media_item_id: str
    title: Optional[str] = None
    media_type: Optional[str] = None
    source_platform: Optional[str] = None
    summary_short_artifact_id: Optional[str] = None
    summary_short_status: str = "pending"  # pending, ready, failed
    added_at: str = Field(default_factory=lambda: _now_utc().isoformat())


class DigestRecord(BaseModel):
    """A single digest (daily or weekly) for a user."""

    user_id: str
    digest_type: DigestType
    period_key: str  # e.g. "2026-04-29" for daily, "2026-W18" for weekly
    media_items: List[DigestMediaItem] = Field(default_factory=list)
    status: DigestStatus = DigestStatus.PENDING
    created_at: str = Field(default_factory=lambda: _now_utc().isoformat())
    updated_at: str = Field(default_factory=lambda: _now_utc().isoformat())
    published_at: Optional[str] = None

    @property
    def digest_key(self) -> str:
        """Sort key for DynamoDB: {digest_type}#{period_key}."""
        return f"{self.digest_type.value}#{self.period_key}"

    def to_dynamodb_item(self) -> Dict[str, Any]:
        item: Dict[str, Any] = {
            "user_id": self.user_id,
            "digest_key": self.digest_key,
            "digest_type": self.digest_type.value,
            "period_key": self.period_key,
            "media_items": [mi.model_dump() for mi in self.media_items],
            "status": self.status.value,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }
        if self.published_at:
            item["published_at"] = self.published_at
        return item

    @classmethod
    def from_dynamodb_item(cls, item: Dict[str, Any]) -> "DigestRecord":
        media_items_raw = item.get("media_items", [])
        media_items = [DigestMediaItem(**mi) for mi in media_items_raw]
        return cls(
            user_id=item["user_id"],
            digest_type=DigestType(item["digest_type"]),
            period_key=item["period_key"],
            media_items=media_items,
            status=DigestStatus(item.get("status", "pending")),
            created_at=item.get("created_at", _now_utc().isoformat()),
            updated_at=item.get("updated_at", _now_utc().isoformat()),
            published_at=item.get("published_at"),
        )


class UserDigestSettings(BaseModel):
    """User-level digest settings."""

    user_id: str
    digest_enabled: bool = True  # Active by default for all users
    daily_digest_enabled: bool = True
    weekly_digest_enabled: bool = True
    updated_at: str = Field(default_factory=lambda: _now_utc().isoformat())

    def to_dynamodb_item(self) -> Dict[str, Any]:
        return {
            "user_id": self.user_id,
            "digest_enabled": self.digest_enabled,
            "daily_digest_enabled": self.daily_digest_enabled,
            "weekly_digest_enabled": self.weekly_digest_enabled,
            "updated_at": self.updated_at,
        }

    @classmethod
    def from_dynamodb_item(cls, item: Dict[str, Any]) -> "UserDigestSettings":
        return cls(
            user_id=item["user_id"],
            digest_enabled=item.get("digest_enabled", True),
            daily_digest_enabled=item.get("daily_digest_enabled", True),
            weekly_digest_enabled=item.get("weekly_digest_enabled", True),
            updated_at=item.get("updated_at", _now_utc().isoformat()),
        )
