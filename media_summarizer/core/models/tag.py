"""
Tag model for user-created media labels using DynamoDB.

Each user has private tags that can be associated with any of their media items.
Tags are manually created (no auto-generation) and support an optional color.
"""

from datetime import datetime, timezone
from typing import Optional, Dict, Any
from pydantic import BaseModel, Field, field_validator
import uuid


class Tag(BaseModel):
    """User-created tag for labeling media items."""

    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    user_id: str = Field(..., min_length=1)
    name: str = Field(..., min_length=1, max_length=100)
    color: Optional[str] = None  # Hex color e.g. "#FF5733"

    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    @field_validator("user_id")
    @classmethod
    def user_id_must_not_be_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("User ID must not be empty")
        return v.strip()

    @field_validator("name")
    @classmethod
    def name_must_not_be_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("Tag name must not be empty")
        return v.strip()

    @field_validator("color")
    @classmethod
    def color_must_be_valid_hex(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        v = v.strip()
        if not v:
            return None
        if not v.startswith("#") or len(v) not in (4, 7):
            raise ValueError("Color must be a valid hex color (e.g. #FFF or #FF5733)")
        # Validate hex characters
        hex_chars = v[1:]
        if not all(c in "0123456789abcdefABCDEF" for c in hex_chars):
            raise ValueError("Color must contain valid hex characters")
        return v

    def touch(self) -> None:
        """Update the updated_at timestamp."""
        self.updated_at = datetime.now(timezone.utc)

    # ---------- DynamoDB Serialization ----------

    def to_dynamodb_item(self) -> Dict[str, Any]:
        """Convert model to a DynamoDB-compatible item (no nulls)."""
        item: Dict[str, Any] = {
            "id": self.id,
            "user_id": self.user_id,
            "name": self.name,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }
        if self.color is not None:
            item["color"] = self.color
        return item

    @classmethod
    def from_dynamodb_item(cls, item: Dict[str, Any]) -> "Tag":
        """Rehydrate a Tag from a DynamoDB item."""
        return cls(
            id=item["id"],
            user_id=item["user_id"],
            name=item["name"],
            color=item.get("color"),
            created_at=datetime.fromisoformat(item["created_at"]),
            updated_at=datetime.fromisoformat(item["updated_at"]),
        )

    def __repr__(self) -> str:
        return f"<Tag(id='{self.id}', user_id='{self.user_id}', name='{self.name}')>"
