"""
Tests for the Episode domain model.
"""
import pytest
from datetime import datetime
from pydantic import ValidationError

from media_summarizer.core.models.episode import Episode


class TestEpisodeModel:
    """Test cases for the Episode domain model."""
    
    def test_episode_creation_with_valid_data(self):
        """Test creating an episode with valid data."""
        # Arrange
        episode_data = {
            "id": "episode-123",
            "podcast_id": "podcast-123",
            "title": "Test Episode",
            "description": "A test episode",
            "audio_url": "https://example.com/episode.mp3",
            "published_at": datetime(2023, 1, 1),
            "duration": 1800  # 30 minutes
        }
        
        # Act
        episode = Episode(**episode_data)
        
        # Assert
        assert episode.id == "episode-123"
        assert episode.podcast_id == "podcast-123"
        assert episode.title == "Test Episode"
        assert episode.description == "A test episode"
        assert str(episode.audio_url) == "https://example.com/episode.mp3"
        assert episode.published_at == datetime(2023, 1, 1)
        assert episode.duration == 1800
        assert isinstance(episode.created_at, datetime)
        assert isinstance(episode.updated_at, datetime)
    
    def test_episode_creation_with_minimal_data(self):
        """Test creating an episode with minimal required data."""
        # Arrange
        episode_data = {
            "id": "episode-123",
            "podcast_id": "podcast-123",
            "title": "Test Episode",
            "audio_url": "https://example.com/episode.mp3",
            "published_at": datetime(2023, 1, 1)
        }
        
        # Act
        episode = Episode(**episode_data)
        
        # Assert
        assert episode.id == "episode-123"
        assert episode.podcast_id == "podcast-123"
        assert episode.title == "Test Episode"
        assert episode.description is None
        assert str(episode.audio_url) == "https://example.com/episode.mp3"
        assert episode.published_at == datetime(2023, 1, 1)
        assert episode.duration is None
    
    def test_episode_creation_with_invalid_title(self):
        """Test creating an episode with an invalid title."""
        # Arrange
        episode_data = {
            "id": "episode-123",
            "podcast_id": "podcast-123",
            "title": "",  # Empty title
            "audio_url": "https://example.com/episode.mp3",
            "published_at": datetime(2023, 1, 1)
        }
        
        # Act & Assert
        with pytest.raises(ValidationError) as excinfo:
            Episode(**episode_data)
        
        assert "String should have at least 1 character" in str(excinfo.value)
    
    def test_episode_creation_with_invalid_audio_url(self):
        """Test creating an episode with an invalid audio URL."""
        # Arrange
        episode_data = {
            "id": "episode-123",
            "podcast_id": "podcast-123",
            "title": "Test Episode",
            "audio_url": "invalid-url",  # Invalid URL
            "published_at": datetime(2023, 1, 1)
        }
        
        # Act & Assert
        with pytest.raises(ValidationError) as excinfo:
            Episode(**episode_data)
        
        assert "URL" in str(excinfo.value)
    
    def test_episode_creation_with_invalid_duration(self):
        """Test creating an episode with an invalid duration."""
        # Arrange
        episode_data = {
            "id": "episode-123",
            "podcast_id": "podcast-123",
            "title": "Test Episode",
            "audio_url": "https://example.com/episode.mp3",
            "published_at": datetime(2023, 1, 1),
            "duration": -10  # Negative duration
        }
        
        # Act & Assert
        with pytest.raises(ValidationError) as excinfo:
            Episode(**episode_data)
        
        assert "Duration must be positive" in str(excinfo.value)
    
    def test_episode_update_method(self):
        """Test the update method of the Episode model."""
        # Arrange
        episode = Episode(
            id="episode-123",
            podcast_id="podcast-123",
            title="Test Episode",
            audio_url="https://example.com/episode.mp3",
            published_at=datetime(2023, 1, 1)
        )
        original_created_at = episode.created_at
        original_updated_at = episode.updated_at
        
        # Act
        updated_episode = episode.update(
            title="Updated Episode",
            description="Updated description",
            duration=2400  # 40 minutes
        )
        
        # Assert
        assert updated_episode.title == "Updated Episode"
        assert updated_episode.description == "Updated description"
        assert updated_episode.duration == 2400
        assert updated_episode.created_at == original_created_at
        assert updated_episode.updated_at > original_updated_at
    
    def test_episode_update_with_invalid_attribute(self):
        """Test the update method with an invalid attribute."""
        # Arrange
        episode = Episode(
            id="episode-123",
            podcast_id="podcast-123",
            title="Test Episode",
            audio_url="https://example.com/episode.mp3",
            published_at=datetime(2023, 1, 1)
        )
        
        # Act
        updated_episode = episode.update(
            invalid_attribute="This should be ignored"
        )
        
        # Assert
        assert not hasattr(updated_episode, "invalid_attribute")