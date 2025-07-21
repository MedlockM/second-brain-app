"""
Unit tests for the podcast service.
"""
import pytest
import pytest_asyncio
from datetime import datetime, timedelta
from unittest.mock import patch, MagicMock, AsyncMock

from media_summarizer.core.services.podcast_service import PodcastService
from media_summarizer.core.models.podcast import Podcast
from media_summarizer.core.models.episode import Episode
from media_summarizer.core.models.podcast_episode_relationship import PodcastWithEpisodes


@pytest.fixture
def podcast_service():
    """Create a PodcastService instance for testing."""
    return PodcastService()


@pytest.fixture
def sample_podcast():
    """Create a sample podcast for testing."""
    return Podcast(
        id="podcast-123",
        title="Test Podcast",
        feed_url="https://example.com/feed.xml"
    )


@pytest.fixture
def sample_episodes():
    """Create sample episodes for testing."""
    now = datetime.utcnow()
    return [
        Episode(
            id="episode-1",
            podcast_id="podcast-123",
            title="Episode 1: Introduction",
            audio_url="https://example.com/episode1.mp3",
            published_at=now - timedelta(days=7),
            duration=1800  # 30 minutes
        ),
        Episode(
            id="episode-2",
            podcast_id="podcast-123",
            title="Episode 2: Deep Dive",
            audio_url="https://example.com/episode2.mp3",
            published_at=now - timedelta(days=3),
            duration=2700  # 45 minutes
        ),
        Episode(
            id="episode-3",
            podcast_id="podcast-123",
            title="Episode 3: Advanced Topics",
            audio_url="https://example.com/episode3.mp3",
            published_at=now - timedelta(days=1),
            duration=3600  # 60 minutes
        )
    ]


class TestPodcastService:
    """Test cases for the PodcastService class."""
    
    @pytest.mark.asyncio
    async def test_create_podcast(self, podcast_service):
        """Test creating a podcast."""
        # Setup
        title = "Test Podcast"
        feed_url = "https://example.com/feed.xml"
        description = "A test podcast"
        website = "https://example.com"
        
        # Execute
        podcast = await podcast_service.create_podcast(
            title=title,
            feed_url=feed_url,
            description=description,
            website=website
        )
        
        # Verify
        assert podcast.title == title
        assert str(podcast.feed_url) == feed_url
        assert podcast.description == description
        assert str(podcast.website) == website
    
    @pytest.mark.asyncio
    async def test_create_podcast_minimal(self, podcast_service):
        """Test creating a podcast with minimal data."""
        # Setup
        title = "Test Podcast"
        feed_url = "https://example.com/feed.xml"
        
        # Execute
        podcast = await podcast_service.create_podcast(
            title=title,
            feed_url=feed_url
        )
        
        # Verify
        assert podcast.title == title
        assert str(podcast.feed_url) == feed_url
        assert podcast.description is None
        assert podcast.website is None
    
    @pytest.mark.asyncio
    async def test_create_episode(self, podcast_service):
        """Test creating an episode."""
        # Setup
        podcast_id = "podcast-123"
        title = "Test Episode"
        audio_url = "https://example.com/episode.mp3"
        published_at = datetime.utcnow()
        description = "A test episode"
        duration = 1800  # 30 minutes
        
        # Execute
        episode = await podcast_service.create_episode(
            podcast_id=podcast_id,
            title=title,
            audio_url=audio_url,
            published_at=published_at,
            description=description,
            duration=duration
        )
        
        # Verify
        assert episode.podcast_id == podcast_id
        assert episode.title == title
        assert str(episode.audio_url) == audio_url
        assert episode.published_at == published_at
        assert episode.description == description
        assert episode.duration == duration
    
    @pytest.mark.asyncio
    async def test_create_episode_minimal(self, podcast_service):
        """Test creating an episode with minimal data."""
        # Setup
        podcast_id = "podcast-123"
        title = "Test Episode"
        audio_url = "https://example.com/episode.mp3"
        published_at = datetime.utcnow()
        
        # Execute
        episode = await podcast_service.create_episode(
            podcast_id=podcast_id,
            title=title,
            audio_url=audio_url,
            published_at=published_at
        )
        
        # Verify
        assert episode.podcast_id == podcast_id
        assert episode.title == title
        assert str(episode.audio_url) == audio_url
        assert episode.published_at == published_at
        assert episode.description is None
        assert episode.duration is None
    
    @pytest.mark.asyncio
    async def test_add_episode_to_podcast(self, podcast_service, sample_podcast, sample_episodes):
        """Test adding an episode to a podcast."""
        # Setup
        episode = sample_episodes[0]
        
        # Execute
        podcast_with_episodes = await podcast_service.add_episode_to_podcast(
            podcast=sample_podcast,
            episode=episode
        )
        
        # Verify
        assert podcast_with_episodes.podcast == sample_podcast
        assert len(podcast_with_episodes.episodes) == 1
        assert podcast_with_episodes.episodes[0] == episode
    
    @pytest.mark.asyncio
    async def test_add_episode_to_podcast_invalid(self, podcast_service, sample_podcast):
        """Test adding an invalid episode to a podcast."""
        # Setup
        invalid_episode = Episode(
            id="episode-invalid",
            podcast_id="different-podcast-id",  # Different podcast ID
            title="Invalid Episode",
            audio_url="https://example.com/invalid-episode.mp3",
            published_at=datetime.utcnow()
        )
        
        # Execute and verify
        with pytest.raises(ValueError) as excinfo:
            await podcast_service.add_episode_to_podcast(
                podcast=sample_podcast,
                episode=invalid_episode
            )
        
        assert "does not belong to podcast" in str(excinfo.value)
    
    @pytest.mark.asyncio
    async def test_calculate_total_duration(self, podcast_service, sample_episodes):
        """Test calculating the total duration of episodes."""
        # Execute
        total_duration = await podcast_service.calculate_total_duration(sample_episodes)
        
        # Verify
        expected_duration = 1800 + 2700 + 3600  # 30 + 45 + 60 minutes in seconds
        assert total_duration == expected_duration
    
    @pytest.mark.asyncio
    async def test_calculate_total_duration_empty(self, podcast_service):
        """Test calculating the total duration of an empty episode list."""
        # Execute
        total_duration = await podcast_service.calculate_total_duration([])
        
        # Verify
        assert total_duration == 0
    
    @pytest.mark.asyncio
    async def test_calculate_total_duration_missing_durations(self, podcast_service, sample_episodes):
        """Test calculating the total duration with missing durations."""
        # Setup
        episodes = [
            sample_episodes[0],  # Has duration
            Episode(
                id="episode-no-duration",
                podcast_id="podcast-123",
                title="Episode Without Duration",
                audio_url="https://example.com/episode-no-duration.mp3",
                published_at=datetime.utcnow()
                # No duration
            ),
            sample_episodes[2]  # Has duration
        ]
        
        # Execute
        total_duration = await podcast_service.calculate_total_duration(episodes)
        
        # Verify
        expected_duration = 1800 + 3600  # Only episodes with duration
        assert total_duration == expected_duration
    
    @pytest.mark.asyncio
    async def test_find_episodes_by_title_pattern(self, podcast_service, sample_episodes):
        """Test finding episodes by title pattern."""
        # Execute
        matching_episodes = await podcast_service.find_episodes_by_title_pattern(
            episodes=sample_episodes,
            pattern="deep dive"
        )
        
        # Verify
        assert len(matching_episodes) == 1
        assert matching_episodes[0].id == "episode-2"
        assert "Deep Dive" in matching_episodes[0].title
    
    @pytest.mark.asyncio
    async def test_find_episodes_by_title_pattern_case_insensitive(self, podcast_service, sample_episodes):
        """Test finding episodes by title pattern (case insensitive)."""
        # Execute
        matching_episodes = await podcast_service.find_episodes_by_title_pattern(
            episodes=sample_episodes,
            pattern="EPISODE"  # Uppercase
        )
        
        # Verify
        assert len(matching_episodes) == 3  # All episodes have "Episode" in the title
    
    @pytest.mark.asyncio
    async def test_find_episodes_by_title_pattern_no_matches(self, podcast_service, sample_episodes):
        """Test finding episodes by title pattern with no matches."""
        # Execute
        matching_episodes = await podcast_service.find_episodes_by_title_pattern(
            episodes=sample_episodes,
            pattern="nonexistent"
        )
        
        # Verify
        assert len(matching_episodes) == 0
    
    @pytest.mark.asyncio
    async def test_sort_episodes_by_date_descending(self, podcast_service, sample_episodes):
        """Test sorting episodes by date (descending, newest first)."""
        # Execute
        sorted_episodes = await podcast_service.sort_episodes_by_date(
            episodes=sample_episodes,
            ascending=False
        )
        
        # Verify
        assert len(sorted_episodes) == 3
        assert sorted_episodes[0].id == "episode-3"  # Newest
        assert sorted_episodes[1].id == "episode-2"
        assert sorted_episodes[2].id == "episode-1"  # Oldest
    
    @pytest.mark.asyncio
    async def test_sort_episodes_by_date_ascending(self, podcast_service, sample_episodes):
        """Test sorting episodes by date (ascending, oldest first)."""
        # Execute
        sorted_episodes = await podcast_service.sort_episodes_by_date(
            episodes=sample_episodes,
            ascending=True
        )
        
        # Verify
        assert len(sorted_episodes) == 3
        assert sorted_episodes[0].id == "episode-1"  # Oldest
        assert sorted_episodes[1].id == "episode-2"
        assert sorted_episodes[2].id == "episode-3"  # Newest
    
    @pytest.mark.asyncio
    async def test_sort_episodes_by_date_empty(self, podcast_service):
        """Test sorting an empty episode list by date."""
        # Execute
        sorted_episodes = await podcast_service.sort_episodes_by_date([])
        
        # Verify
        assert len(sorted_episodes) == 0