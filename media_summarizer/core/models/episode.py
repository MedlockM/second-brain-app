"""
Domain model for podcast episodes.
"""
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, HttpUrl, Field, validator


class Episode(BaseModel):
    """Domain model for a podcast episode."""
    id: str
    podcast_id: str
    title: str = Field(..., min_length=1, max_length=200)
    description: Optional[str] = Field(None, max_length=5000)
    audio_url: HttpUrl
    published_at: datetime
    duration: Optional[int] = None  # Duration in seconds
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    
    @validator('title')
    def title_must_not_be_empty(cls, v):
        """Validate that the title is not empty."""
        if not v.strip():
            raise ValueError('Title must not be empty')
        return v
    
    @validator('duration')
    def duration_must_be_positive(cls, v):
        """Validate that the duration is positive."""
        if v is not None and v <= 0:
            raise ValueError('Duration must be positive')
        return v
    
    def update(self, **kwargs):
        """Update episode attributes."""
        for key, value in kwargs.items():
            if hasattr(self, key):
                setattr(self, key, value)
        self.updated_at = datetime.utcnow()
        return self