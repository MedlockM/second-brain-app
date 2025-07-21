"""
Tests for the Podcast domain model.
"""
import pytest
from datetime import datetime
from pydantic import ValidationError, HttpUrl

from media_summarizer.core.models.podcast import Podcast


class TestPodcastModel:
    """Test cases for the Podcast domain model."""
    
    def test_podcast_creation_with_valid_data(self):
        """Test creating a podcast with valid data."""
        # Arrange
        podcast_data = {
            "id": "podcast-123",
            "title": "Test Podcast",
            "description": "A test podcast",
            "feed_url": "https://example.com/feed.xml",
            "website": "https://example.com"
        }
        
        # Act
        podcast = Podcast(**podcast_data)
        
        # Assert
        assert podcast.id == "podcast-123"
        assert podcast.title == "Test Podcast"
        assert podcast.description == "A test podcast"
        assert str(podcast.feed_url) == "https://example.com/feed.xml"
        assert str(podcast.website).startswith("https://example.com")
        assert isinstance(podcast.created_at, datetime)
        assert isinstance(podcast.updated_at, datetime)
    
    def test_podcast_creation_with_minimal_data(self):
        """Test creating a podcast with minimal required data."""
        # Arrange
        podcast_data = {
            "id": "podcast-123",
            "title": "Test Podcast",
            "feed_url": "https://example.com/feed.xml"
        }
        
        # Act
        podcast = Podcast(**podcast_data)
        
        # Assert
        assert podcast.id == "podcast-123"
        assert podcast.title == "Test Podcast"
        assert podcast.description is None
        assert str(podcast.feed_url) == "https://example.com/feed.xml"
        assert podcast.website is None
    
    def test_podcast_creation_with_invalid_title(self):
        """Test creating a podcast with an invalid title."""
        # Arrange
        podcast_data = {
            "id": "podcast-123",
            "title": "",  # Empty title
            "feed_url": "https://example.com/feed.xml"
        }
        
        # Act & Assert
        with pytest.raises(ValidationError) as excinfo:
            Podcast(**podcast_data)
        
        assert "String should have at least 1 character" in str(excinfo.value)
    
    def test_podcast_creation_with_invalid_feed_url(self):
        """Test creating a podcast with an invalid feed URL."""
        # Arrange
        podcast_data = {
            "id": "podcast-123",
            "title": "Test Podcast",
            "feed_url": "invalid-url"  # Invalid URL
        }
        
        # Act & Assert
        with pytest.raises(ValidationError) as excinfo:
            Podcast(**podcast_data)
        
        assert "URL" in str(excinfo.value)
    
    def test_podcast_update_method(self):
        """Test the update method of the Podcast model."""
        # Arrange
        podcast = Podcast(
            id="podcast-123",
            title="Test Podcast",
            feed_url="https://example.com/feed.xml"
        )
        original_created_at = podcast.created_at
        original_updated_at = podcast.updated_at
        
        # Act
        updated_podcast = podcast.update(
            title="Updated Podcast",
            description="Updated description"
        )
        
        # Assert
        assert updated_podcast.title == "Updated Podcast"
        assert updated_podcast.description == "Updated description"
        assert updated_podcast.created_at == original_created_at
        assert updated_podcast.updated_at > original_updated_at
    
    def test_podcast_update_with_invalid_attribute(self):
        """Test the update method with an invalid attribute."""
        # Arrange
        podcast = Podcast(
            id="podcast-123",
            title="Test Podcast",
            feed_url="https://example.com/feed.xml"
        )
        
        # Act
        updated_podcast = podcast.update(
            invalid_attribute="This should be ignored"
        )
        
        # Assert
        assert not hasattr(updated_podcast, "invalid_attribute")