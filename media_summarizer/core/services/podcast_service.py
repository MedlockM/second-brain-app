"""
Domain service for podcast operations.

This service handles business logic related to podcasts and episodes.
"""
from typing import Dict, Any, Optional, List
from datetime import datetime

from media_summarizer.core.models.podcast import Podcast
from media_summarizer.core.models.episode import Episode
from media_summarizer.core.models.podcast_episode_relationship import PodcastWithEpisodes


class PodcastService:
    """Service for podcast operations."""
    
    async def create_podcast(
        self,
        title: str,
        feed_url: str,
        description: Optional[str] = None,
        website: Optional[str] = None
    ) -> Podcast:
        """
        Create a new podcast.
        
        Args:
            title: Podcast title
            feed_url: Podcast feed URL
            description: Podcast description (optional)
            website: Podcast website URL (optional)
            
        Returns:
            The created podcast
        """
        podcast = Podcast(
            title=title,
            feed_url=feed_url,
            description=description,
            website=website
        )
        
        return podcast
    
    async def create_episode(
        self,
        podcast_id: str,
        title: str,
        audio_url: str,
        published_at: datetime,
        description: Optional[str] = None,
        duration: Optional[int] = None
    ) -> Episode:
        """
        Create a new episode.
        
        Args:
            podcast_id: ID of the podcast this episode belongs to
            title: Episode title
            audio_url: Episode audio URL
            published_at: Episode publication timestamp
            description: Episode description (optional)
            duration: Episode duration in seconds (optional)
            
        Returns:
            The created episode
        """
        episode = Episode(
            podcast_id=podcast_id,
            title=title,
            audio_url=audio_url,
            published_at=published_at,
            description=description,
            duration=duration
        )
        
        return episode
    
    async def add_episode_to_podcast(
        self,
        podcast: Podcast,
        episode: Episode
    ) -> PodcastWithEpisodes:
        """
        Add an episode to a podcast.
        
        Args:
            podcast: The podcast
            episode: The episode to add
            
        Returns:
            PodcastWithEpisodes containing the podcast and its episodes
            
        Raises:
            ValueError: If the episode does not belong to the podcast
        """
        if episode.podcast_id != podcast.id:
            raise ValueError(f"Episode {episode.id} does not belong to podcast {podcast.id}")
        
        podcast_with_episodes = PodcastWithEpisodes(
            podcast=podcast,
            episodes=[episode]
        )
        
        return podcast_with_episodes
    
    async def calculate_total_duration(self, episodes: List[Episode]) -> int:
        """
        Calculate the total duration of episodes.
        
        Args:
            episodes: List of episodes
            
        Returns:
            Total duration in seconds
        """
        total_duration = 0
        
        for episode in episodes:
            if episode.duration:
                total_duration += episode.duration
        
        return total_duration
    
    async def find_episodes_by_title_pattern(
        self,
        episodes: List[Episode],
        pattern: str
    ) -> List[Episode]:
        """
        Find episodes by title pattern.
        
        Args:
            episodes: List of episodes to search
            pattern: Pattern to match in episode titles
            
        Returns:
            List of matching episodes
        """
        pattern = pattern.lower()
        matching_episodes = []
        
        for episode in episodes:
            if pattern in episode.title.lower():
                matching_episodes.append(episode)
        
        return matching_episodes
    
    async def sort_episodes_by_date(
        self,
        episodes: List[Episode],
        ascending: bool = False
    ) -> List[Episode]:
        """
        Sort episodes by publication date.
        
        Args:
            episodes: List of episodes to sort
            ascending: Sort in ascending order (default: False, newest first)
            
        Returns:
            Sorted list of episodes
        """
        return sorted(
            episodes,
            key=lambda e: e.published_at,
            reverse=not ascending
        )