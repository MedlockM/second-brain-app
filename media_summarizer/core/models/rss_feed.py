"""
RSS Feed subscription model for DynamoDB.

Each user can subscribe to multiple RSS feeds. The system polls them
periodically and ingests new items via the existing media pipeline.
"""

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

import uuid
from pydantic import BaseModel, Field, field_validator


class FeedStatus(str, Enum):
    """Status of an RSS feed subscription."""

    ACTIVE = "active"
    PAUSED = "paused"


class UserRssFeed(BaseModel):
    """User RSS feed subscription for automatic media ingestion."""

    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    user_id: str = Field(..., min_length=1)
    feed_url: str = Field(..., min_length=1)
    feed_title: Optional[str] = None
    status: FeedStatus = Field(default=FeedStatus.ACTIVE)

    # Tracking state
    last_polled_at: Optional[datetime] = None
    last_error: Optional[str] = None
    item_guids_seen: List[str] = Field(default_factory=list)

    # Timestamps
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    @field_validator("user_id")
    @classmethod
    def user_id_must_not_be_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("User ID must not be empty")
        return v.strip()

    @field_validator("feed_url")
    @classmethod
    def feed_url_must_not_be_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("Feed URL must not be empty")
        return v.strip()

    def touch(self) -> None:
        """Update the updated_at timestamp."""
        self.updated_at = datetime.now(timezone.utc)

    def mark_polled(self) -> None:
        """Record that the feed was just polled."""
        self.last_polled_at = datetime.now(timezone.utc)
        self.last_error = None
        self.touch()

    def mark_poll_error(self, error: str) -> None:
        """Record a polling error."""
        self.last_polled_at = datetime.now(timezone.utc)
        self.last_error = error
        self.touch()

    def add_seen_guids(self, guids: List[str]) -> None:
        """Add GUIDs to the seen set (deduplication)."""
        existing = set(self.item_guids_seen)
        existing.update(guids)
        self.item_guids_seen = list(existing)
        self.touch()

    def is_guid_seen(self, guid: str) -> bool:
        """Check if a GUID has already been ingested."""
        return guid in self.item_guids_seen

    # ---------- DynamoDB Serialization ----------

    def to_dynamodb_item(self) -> Dict[str, Any]:
        """Convert model to a DynamoDB-compatible item (no nulls)."""
        item: Dict[str, Any] = {
            "id": self.id,
            "user_id": self.user_id,
            "feed_url": self.feed_url,
            "status": self.status.value,
            "item_guids_seen": self.item_guids_seen,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }
        if self.feed_title is not None:
            item["feed_title"] = self.feed_title
        if self.last_polled_at is not None:
            item["last_polled_at"] = self.last_polled_at.isoformat()
        if self.last_error is not None:
            item["last_error"] = self.last_error
        return item

    @classmethod
    def from_dynamodb_item(cls, item: Dict[str, Any]) -> "UserRssFeed":
        """Rehydrate a UserRssFeed from a DynamoDB item."""
        data: Dict[str, Any] = {
            "id": item["id"],
            "user_id": item["user_id"],
            "feed_url": item["feed_url"],
            "status": FeedStatus(item.get("status", "active")),
            "item_guids_seen": item.get("item_guids_seen", []),
            "created_at": datetime.fromisoformat(item["created_at"]),
            "updated_at": datetime.fromisoformat(item["updated_at"]),
        }
        if "feed_title" in item:
            data["feed_title"] = item["feed_title"]
        if "last_polled_at" in item and item["last_polled_at"]:
            data["last_polled_at"] = datetime.fromisoformat(item["last_polled_at"])
        if "last_error" in item:
            data["last_error"] = item["last_error"]
        return cls(**data)

    def __repr__(self) -> str:
        return (
            f"<UserRssFeed(id='{self.id}', user_id='{self.user_id}', "
            f"feed_url='{self.feed_url}', status='{self.status.value}')>"
        )
