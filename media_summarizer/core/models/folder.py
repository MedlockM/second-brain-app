"""
Folder model for hierarchical media organization using DynamoDB.

Each user has a private folder tree. Every media item belongs to exactly one folder.
A special "Uncategorized" folder is auto-created per user and cannot be deleted.
"""

from datetime import datetime, timezone
from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field, field_validator
import uuid


# Sentinel name for the default folder created per user
UNCATEGORIZED_FOLDER_NAME = "Uncategorized"

# Maximum nesting depth (root = depth 0, so depth 5 means 6 levels total)
MAX_FOLDER_DEPTH = 5


class Folder(BaseModel):
    """User folder for organizing media items."""

    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    user_id: str = Field(..., min_length=1)
    name: str = Field(..., min_length=1, max_length=255)
    parent_folder_id: Optional[str] = None  # None means root-level folder
    is_default: bool = Field(default=False)  # True only for the "Uncategorized" folder

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
            raise ValueError("Folder name must not be empty")
        return v.strip()

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
            "is_default": self.is_default,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }
        if self.parent_folder_id is not None:
            item["parent_folder_id"] = self.parent_folder_id
        return item

    @classmethod
    def from_dynamodb_item(cls, item: Dict[str, Any]) -> "Folder":
        """Rehydrate a Folder from a DynamoDB item."""
        return cls(
            id=item["id"],
            user_id=item["user_id"],
            name=item["name"],
            parent_folder_id=item.get("parent_folder_id"),
            is_default=item.get("is_default", False),
            created_at=datetime.fromisoformat(item["created_at"]),
            updated_at=datetime.fromisoformat(item["updated_at"]),
        )

    @classmethod
    def create_default(cls, user_id: str) -> "Folder":
        """Create the default 'Uncategorized' folder for a user."""
        return cls(
            user_id=user_id,
            name=UNCATEGORIZED_FOLDER_NAME,
            parent_folder_id=None,
            is_default=True,
        )

    def __repr__(self) -> str:
        return f"<Folder(id='{self.id}', user_id='{self.user_id}', name='{self.name}')>"
