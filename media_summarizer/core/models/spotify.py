"""Spotify integration models."""
from datetime import datetime, timezone
from typing import Optional, Dict, Any
from pydantic import BaseModel, Field


class SpotifyPlaylistFollow(BaseModel):
    """Represents a user's follow/tracking of a Spotify playlist."""
    user_id: str
    playlist_id: str
    enabled: bool = True
    last_synced_at: Optional[datetime] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    
    def to_dynamodb_item(self) -> Dict[str, Any]:
        """Convert to DynamoDB item (no nulls)."""
        item = {
            "user_id": self.user_id,
            "playlist_id": self.playlist_id,
            "enabled": self.enabled,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }
        if self.last_synced_at:
            item["last_synced_at"] = self.last_synced_at.isoformat()
        return item
    
    @classmethod
    def from_dynamodb_item(cls, item: Dict[str, Any]) -> "SpotifyPlaylistFollow":
        """Rehydrate from DynamoDB item."""
        return cls(
            user_id=item["user_id"],
            playlist_id=item["playlist_id"],
            enabled=item.get("enabled", True),
            last_synced_at=datetime.fromisoformat(item["last_synced_at"]) if item.get("last_synced_at") else None,
            created_at=datetime.fromisoformat(item["created_at"]),
            updated_at=datetime.fromisoformat(item["updated_at"]),
        )
