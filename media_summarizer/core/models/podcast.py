"""
Domain model for podcasts.
"""
from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, HttpUrl, Field, validator


class Podcast(BaseModel):
    """Domain model for a podcast."""
    id: str
    title: str = Field(..., min_length=1, max_length=200)
    description: Optional[str] = Field(None, max_length=2000)
    feed_url: HttpUrl
    website: Optional[HttpUrl] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    
    @validator('title')
    def title_must_not_be_empty(cls, v):
        """Validate that the title is not empty."""
        if not v.strip():
            raise ValueError('Title must not be empty')
        return v
    
    def update(self, **kwargs):
        """Update podcast attributes."""
        for key, value in kwargs.items():
            if hasattr(self, key):
                setattr(self, key, value)
        self.updated_at = datetime.utcnow()
        return self