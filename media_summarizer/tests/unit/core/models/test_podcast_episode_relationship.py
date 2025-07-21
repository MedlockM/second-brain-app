"""
Tests for the PodcastWithEpisodes domain model.
"""
import pytest
from datetime import datetime
from pydantic import ValidationError

from media_summarizer.core.models.podcast import Podcast
from media_summarizer.core.models.episode import Episode
from media_summarizer.core.models.podcast_episode_relationship import PodcastWithEpisodes


class TestPodcastWithEpisodesModel:
    """Test cases for the PodcastWithEpisodes domain model."""
    
    @pytest.fixture
    def sample_podcast(self):
        """Create a sample podcast for testing."""
        return Podcast(
            id="podcast-123",
            title="Test Podcast",
            feed_url="https://example.com/feed.xml"
        )
    
    @pytest.fixture
    def sample_episode(self, sample_podcast):
        """Create a sample episode for testing."""
        return Episode(
            id="episode-123",
            podcast_id=sample_podcast.id,
            title="Test Episode",
            audio_url="https://example.com/episode.mp3",
            published_at=datetime(2023, 1, 1)
        )
    
    def test_podcast_with_episodes_creation(self, sample_podcast, sample_episode):
        """Test creating a podcast with episodes."""
        # Arrange & Act
        podcast_with_episodes = PodcastWithEpisodes(
            podcast=sample_podcast,
            episodes=[sample_episode]
        )
        
        # Assert
        assert podcast_with_episodes.podcast.id == "podcast-123"
        assert len(podcast_with_episodes.episodes) == 1
        assert podcast_with_episodes.episodes[0].id == "episode-123"
    
    def test_podcast_with_episodes_validation(self, sample_podcast):
        """Test validation of episodes belonging to the podcast."""
        # Arrange
        invalid_episode = Episode(
            id="episode-456",
            podcast_id="different-podcast-id",  # Different podcast ID
            title="Invalid Episode",
            audio_url="https://example.com/invalid-episode.mp3",
            published_at=datetime(2023, 1, 1)
        )
        
        # Act & Assert
        with pytest.raises(ValidationError) as excinfo:
            PodcastWithEpisodes(
                podcast=sample_podcast,
                episodes=[invalid_episode]
            )
        
        assert "does not belong to podcast" in str(excinfo.value)
    
    def test_add_episode(self, sample_podcast, sample_episode):
        """Test adding an episode to a podcast."""
        # Arrange
        podcast_with_episodes = PodcastWithEpisodes(
            podcast=sample_podcast,
            episodes=[]
        )
        
        # Act
        podcast_with_episodes.add_episode(sample_episode)
        
        # Assert
        assert len(podcast_with_episodes.episodes) == 1
        assert podcast_with_episodes.episodes[0].id == "episode-123"
    
    def test_add_invalid_episode(self, sample_podcast):
        """Test adding an invalid episode to a podcast."""
        # Arrange
        podcast_with_episodes = PodcastWithEpisodes(
            podcast=sample_podcast,
            episodes=[]
        )
        
        invalid_episode = Episode(
            id="episode-456",
            podcast_id="different-podcast-id",  # Different podcast ID
            title="Invalid Episode",
            audio_url="https://example.com/invalid-episode.mp3",
            published_at=datetime(2023, 1, 1)
        )
        
        # Act & Assert
        with pytest.raises(ValueError) as excinfo:
            podcast_with_episodes.add_episode(invalid_episode)
        
        assert "does not belong to podcast" in str(excinfo.value)
        assert len(podcast_with_episodes.episodes) == 0
    
    def test_add_duplicate_episode(self, sample_podcast, sample_episode):
        """Test adding a duplicate episode to a podcast."""
        # Arrange
        podcast_with_episodes = PodcastWithEpisodes(
            podcast=sample_podcast,
            episodes=[sample_episode]
        )
        
        updated_episode = Episode(
            id="episode-123",  # Same ID
            podcast_id=sample_podcast.id,
            title="Updated Episode",  # Updated title
            audio_url="https://example.com/episode.mp3",
            published_at=datetime(2023, 1, 1)
        )
        
        # Act
        podcast_with_episodes.add_episode(updated_episode)
        
        # Assert
        assert len(podcast_with_episodes.episodes) == 1
        assert podcast_with_episodes.episodes[0].title == "Updated Episode"
    
    def test_remove_episode(self, sample_podcast, sample_episode):
        """Test removing an episode from a podcast."""
        # Arrange
        podcast_with_episodes = PodcastWithEpisodes(
            podcast=sample_podcast,
            episodes=[sample_episode]
        )
        
        # Act
        removed_episode = podcast_with_episodes.remove_episode("episode-123")
        
        # Assert
        assert len(podcast_with_episodes.episodes) == 0
        assert removed_episode.id == "episode-123"
    
    def test_remove_nonexistent_episode(self, sample_podcast, sample_episode):
        """Test removing a nonexistent episode from a podcast."""
        # Arrange
        podcast_with_episodes = PodcastWithEpisodes(
            podcast=sample_podcast,
            episodes=[sample_episode]
        )
        
        # Act
        removed_episode = podcast_with_episodes.remove_episode("nonexistent-id")
        
        # Assert
        assert len(podcast_with_episodes.episodes) == 1
        assert removed_episode is None
    
    def test_get_episode(self, sample_podcast, sample_episode):
        """Test getting an episode by ID."""
        # Arrange
        podcast_with_episodes = PodcastWithEpisodes(
            podcast=sample_podcast,
            episodes=[sample_episode]
        )
        
        # Act
        episode = podcast_with_episodes.get_episode("episode-123")
        
        # Assert
        assert episode is not None
        assert episode.id == "episode-123"
    
    def test_get_nonexistent_episode(self, sample_podcast, sample_episode):
        """Test getting a nonexistent episode by ID."""
        # Arrange
        podcast_with_episodes = PodcastWithEpisodes(
            podcast=sample_podcast,
            episodes=[sample_episode]
        )
        
        # Act
        episode = podcast_with_episodes.get_episode("nonexistent-id")
        
        # Assert
        assert episode is None
    
    def test_to_dict(self, sample_podcast, sample_episode):
        """Test converting the model to a dictionary."""
        # Arrange
        podcast_with_episodes = PodcastWithEpisodes(
            podcast=sample_podcast,
            episodes=[sample_episode]
        )
        
        # Act
        result = podcast_with_episodes.to_dict()
        
        # Assert
        assert isinstance(result, dict)
        assert "podcast" in result
        assert "episodes" in result
        assert result["podcast"]["id"] == "podcast-123"
        assert len(result["episodes"]) == 1
        assert result["episodes"][0]["id"] == "episode-123"