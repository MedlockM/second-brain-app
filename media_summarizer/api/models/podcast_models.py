"""
Pydantic models for podcast search and episode selection.
"""

from pydantic import BaseModel, Field
from typing import Dict, Any, List, Optional
from datetime import datetime


class PodcastSearchRequest(BaseModel):
    """Request model for podcast search."""
    query: str = Field(..., description="Search query for podcasts", min_length=1, max_length=500)
    max_results: int = Field(default=10, description="Maximum number of results", ge=1, le=100)
    clean: bool = Field(default=True, description="Filter out explicit content")
    similar: bool = Field(default=False, description="Include similar matches (fuzzy search)")


class PodcastInfo(BaseModel):
    """Podcast information model."""
    id: int = Field(..., description="Podcast Index feed ID")
    title: str = Field(..., description="Podcast title")
    description: str = Field(default="", description="Podcast description")
    author: str = Field(default="", description="Podcast author")
    image: str = Field(default="", description="Podcast image URL")
    language: str = Field(default="", description="Podcast language")
    categories: Optional[Dict[str, str]] = Field(default=None, description="Podcast categories")
    episode_count: int = Field(default=0, description="Number of episodes")
    feed_url: str = Field(..., description="RSS feed URL")
    link: str = Field(default="", description="Podcast website link")
    last_update_time: int = Field(default=0, description="Last update timestamp")
    explicit: bool = Field(default=False, description="Is explicit content")
    itunes_id: Optional[int] = Field(default=None, description="iTunes ID")
    podcast_guid: Optional[str] = Field(default=None, description="Podcast GUID")


class PodcastSearchResponse(BaseModel):
    """Response model for podcast search."""
    status: str = Field(..., description="Response status")
    podcasts: List[PodcastInfo] = Field(..., description="List of found podcasts")
    count: int = Field(..., description="Number of results")
    query: str = Field(..., description="Original search query")


class EpisodeInfo(BaseModel):
    """Episode information model."""
    id: int = Field(..., description="Episode ID")
    title: str = Field(..., description="Episode title")
    description: str = Field(default="", description="Episode description")
    guid: str = Field(..., description="Episode GUID")
    date_published: int = Field(..., description="Publication timestamp")
    enclosure_url: str = Field(..., description="Audio file URL")
    enclosure_type: str = Field(default="", description="Audio file type")
    enclosure_length: int = Field(default=0, description="Audio file size in bytes")
    duration: Optional[int] = Field(default=None, description="Duration in seconds")
    explicit: int = Field(default=0, description="Explicit content flag")
    episode_number: Optional[int] = Field(default=None, description="Episode number")
    season: Optional[int] = Field(default=None, description="Season number")
    image: str = Field(default="", description="Episode image URL")
    link: str = Field(default="", description="Episode web link")
    feed_id: Optional[int] = Field(default=None, description="Feed ID")
    feed_title: str = Field(default="", description="Podcast title")
    feed_image: str = Field(default="", description="Podcast image URL")
    podcast_guid: Optional[str] = Field(default=None, description="Podcast GUID")


class EpisodesListRequest(BaseModel):
    """Request model for listing episodes."""
    feed_id: int = Field(..., description="Podcast Index feed ID", gt=0)
    max_results: int = Field(default=50, description="Maximum number of episodes", ge=1, le=1000)
    since: Optional[int] = Field(default=None, description="Return episodes since timestamp")


class EpisodesListResponse(BaseModel):
    """Response model for episodes list."""
    status: str = Field(..., description="Response status")
    episodes: List[EpisodeInfo] = Field(..., description="List of episodes")
    count: int = Field(..., description="Number of episodes returned")
    feed_id: int = Field(..., description="Feed ID")
    podcast_title: str = Field(default="", description="Podcast title")


class EpisodeSelectionRequest(BaseModel):
    """Request model for episode selection."""
    feed_id: int = Field(..., description="Podcast Index feed ID", gt=0)
    episode_guid: str = Field(..., description="Episode GUID", min_length=1)
    user_email: Optional[str] = Field(default=None, description="User email address (deprecated, will be ignored if auth is provided)")


class EpisodeSelectionResponse(BaseModel):
    """Response model for episode selection."""
    job_id: str = Field(..., description="Processing job ID")
    status: str = Field(..., description="Job status")
    message: str = Field(..., description="Response message")
    minutes_hold_estimated: int = Field(..., description="Estimated minutes placed on hold for this job")
    estimated_processing_time: str = Field(..., description="Estimated processing time")
    episode_title: str = Field(..., description="Selected episode title")
    podcast_title: str = Field(..., description="Podcast title")


class TrendingPodcastsRequest(BaseModel):
    """Request model for trending podcasts."""
    max_results: int = Field(default=20, description="Maximum number of results", ge=1, le=100)
    language: Optional[str] = Field(default=None, description="Language filter (e.g., 'en', 'fr')")
    category: Optional[str] = Field(default=None, description="Category filter")


class TrendingPodcastsResponse(BaseModel):
    """Response model for trending podcasts."""
    status: str = Field(..., description="Response status")
    podcasts: List[PodcastInfo] = Field(..., description="List of trending podcasts")
    count: int = Field(..., description="Number of results")
