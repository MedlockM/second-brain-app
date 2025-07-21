"""
Domain model for the relationship between podcasts and episodes.
"""
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, validator

from media_summarizer.core.models.podcast import Podcast
from media_summarizer.core.models.episode import Episode


class PodcastWithEpisodes(BaseModel):
    """Domain model for a podcast with its episodes."""
    podcast: Podcast
    episodes: List[Episode] = []
    
    @validator('episodes')
    def episodes_must_belong_to_podcast(cls, v, values):
        """Validate that all episodes belong to the podcast."""
        if 'podcast' in values and v:
            for episode in v:
                if episode.podcast_id != values['podcast'].id:
                    raise ValueError(f"Episode {episode.id} does not belong to podcast {values['podcast'].id}")
        return v
    
    def add_episode(self, episode: Episode) -> None:
        """Add an episode to the podcast."""
        if episode.podcast_id != self.podcast.id:
            raise ValueError(f"Episode {episode.id} does not belong to podcast {self.podcast.id}")
        
        # Check if episode already exists
        for i, existing_episode in enumerate(self.episodes):
            if existing_episode.id == episode.id:
                # Replace existing episode
                self.episodes[i] = episode
                return
        
        # Add new episode
        self.episodes.append(episode)
    
    def remove_episode(self, episode_id: str) -> Optional[Episode]:
        """Remove an episode from the podcast."""
        for i, episode in enumerate(self.episodes):
            if episode.id == episode_id:
                return self.episodes.pop(i)
        return None
    
    def get_episode(self, episode_id: str) -> Optional[Episode]:
        """Get an episode by ID."""
        for episode in self.episodes:
            if episode.id == episode_id:
                return episode
        return None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert the model to a dictionary."""
        return {
            "podcast": self.podcast.dict(),
            "episodes": [episode.dict() for episode in self.episodes]
        }