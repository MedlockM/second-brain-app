"""
RSS adapter for Media Summarizer.

This adapter provides an interface for resolving and parsing RSS feeds.
It handles feed resolution, parsing, and extraction of podcast episodes.
"""
import logging
import re
from typing import Dict, Any, Optional, List, Tuple
import feedparser
import httpx
from urllib.parse import urlparse

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class RSSAdapter:
    """
    Adapter for resolving and parsing RSS feeds.
    """
    
    def __init__(self):
        """
        Initialize the RSS adapter.
        """
        self.platform_patterns = {
            "spotify": r"(open\.spotify\.com|spotify\.com)",
            "apple": r"(podcasts\.apple\.com|apple\.com\/podcast)",
            "google": r"(podcasts\.google\.com)",
            "overcast": r"(overcast\.fm)",
            "pocketcasts": r"(pca\.st|pocketcasts\.com)",
            "castbox": r"(castbox\.fm)",
            "stitcher": r"(stitcher\.com)",
        }
    
    async def detect_platform(self, url: str) -> str:
        """
        Detect the podcast platform from the URL.
        
        Args:
            url: The podcast URL
            
        Returns:
            The platform name or "generic" if not recognized
        """
        parsed_url = urlparse(url)
        domain = parsed_url.netloc.lower()
        
        for platform, pattern in self.platform_patterns.items():
            if re.search(pattern, domain):
                return platform
        
        return "generic"
    
    async def resolve_feed_url(self, podcast_url: str) -> Optional[str]:
        """
        Resolve the RSS feed URL from a podcast URL.
        
        Args:
            podcast_url: The podcast URL from any platform
            
        Returns:
            The RSS feed URL or None if not found
            
        Raises:
            Exception: If there's an error resolving the feed URL
        """
        platform = await self.detect_platform(podcast_url)
        
        try:
            if platform == "spotify":
                return await self._resolve_spotify_feed(podcast_url)
            elif platform == "apple":
                return await self._resolve_apple_feed(podcast_url)
            elif platform == "google":
                return await self._resolve_google_feed(podcast_url)
            else:
                # For generic URLs, try to find RSS link in the page
                return await self._resolve_generic_feed(podcast_url)
        except Exception as e:
            logger.error(f"Error resolving feed URL for {podcast_url}: {str(e)}")
            raise
    
    async def _resolve_spotify_feed(self, url: str) -> Optional[str]:
        """
        Resolve the RSS feed URL from a Spotify podcast URL.
        
        Args:
            url: The Spotify podcast URL
            
        Returns:
            The RSS feed URL or None if not found
        """
        # Extract the Spotify show ID
        match = re.search(r"show\/([a-zA-Z0-9]+)", url)
        if not match:
            return None
        
        show_id = match.group(1)
        
        # Use Spotify API to get podcast details
        # Note: In a real implementation, this would use the Spotify API
        # For now, we'll just return None
        return None
    
    async def _resolve_apple_feed(self, url: str) -> Optional[str]:
        """
        Resolve the RSS feed URL from an Apple Podcasts URL.
        
        Args:
            url: The Apple Podcasts URL
            
        Returns:
            The RSS feed URL or None if not found
        """
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(url)
                response.raise_for_status()
                
                # Look for the RSS feed URL in the page
                match = re.search(r'feedUrl":"([^"]+)"', response.text)
                if match:
                    feed_url = match.group(1).replace("\\/", "/")
                    return feed_url
                
                return None
        except Exception as e:
            logger.error(f"Error resolving Apple Podcasts feed: {str(e)}")
            return None
    
    async def _resolve_google_feed(self, url: str) -> Optional[str]:
        """
        Resolve the RSS feed URL from a Google Podcasts URL.
        
        Args:
            url: The Google Podcasts URL
            
        Returns:
            The RSS feed URL or None if not found
        """
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(url)
                response.raise_for_status()
                
                # Look for the RSS feed URL in the page
                match = re.search(r'feedUrl":"([^"]+)"', response.text)
                if match:
                    feed_url = match.group(1).replace("\\/", "/")
                    return feed_url
                
                return None
        except Exception as e:
            logger.error(f"Error resolving Google Podcasts feed: {str(e)}")
            return None
    
    async def _resolve_generic_feed(self, url: str) -> Optional[str]:
        """
        Resolve the RSS feed URL from a generic podcast URL.
        
        Args:
            url: The podcast URL
            
        Returns:
            The RSS feed URL or None if not found
        """
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(url)
                response.raise_for_status()
                
                # Look for RSS link in the page
                match = re.search(r'<link[^>]+type="application/rss\+xml"[^>]+href="([^"]+)"', response.text)
                if match:
                    feed_url = match.group(1)
                    
                    # Handle relative URLs
                    if not feed_url.startswith(('http://', 'https://')):
                        parsed_url = urlparse(url)
                        base_url = f"{parsed_url.scheme}://{parsed_url.netloc}"
                        feed_url = f"{base_url}{feed_url if feed_url.startswith('/') else '/' + feed_url}"
                    
                    return feed_url
                
                # If no RSS link found, the URL might already be a feed
                if "xml" in response.headers.get("content-type", ""):
                    return url
                
                return None
        except Exception as e:
            logger.error(f"Error resolving generic feed: {str(e)}")
            return None
    
    async def parse_feed(self, feed_url: str) -> Dict[str, Any]:
        """
        Parse an RSS feed and extract podcast information.
        
        Args:
            feed_url: The RSS feed URL
            
        Returns:
            Dict containing podcast information and episodes
            
        Raises:
            Exception: If there's an error parsing the feed
        """
        try:
            # Parse the feed
            feed = feedparser.parse(feed_url)
            
            if not feed.entries:
                logger.warning(f"No entries found in feed: {feed_url}")
                return {
                    "success": False,
                    "error": "No episodes found in feed"
                }
            
            # Extract podcast information
            podcast_info = {
                "title": feed.feed.get("title", "Unknown Podcast"),
                "description": feed.feed.get("description", ""),
                "link": feed.feed.get("link", feed_url),
                "image": feed.feed.get("image", {}).get("href", ""),
                "episodes": []
            }
            
            # Extract episodes
            for entry in feed.entries:
                episode = {
                    "title": entry.get("title", "Unknown Episode"),
                    "description": entry.get("description", ""),
                    "published": entry.get("published", ""),
                    "link": entry.get("link", ""),
                    "audio_url": None,
                    "duration": entry.get("itunes_duration", "")
                }
                
                # Find the audio URL
                if "enclosures" in entry:
                    for enclosure in entry.enclosures:
                        if enclosure.get("type", "").startswith("audio/"):
                            episode["audio_url"] = enclosure.get("href", "")
                            break
                
                podcast_info["episodes"].append(episode)
            
            return {
                "success": True,
                "podcast": podcast_info
            }
        except Exception as e:
            logger.error(f"Error parsing feed {feed_url}: {str(e)}")
            return {
                "success": False,
                "error": f"Error parsing feed: {str(e)}"
            }
    
    async def get_latest_episode(self, feed_url: str) -> Optional[Dict[str, Any]]:
        """
        Get the latest episode from an RSS feed.
        
        Args:
            feed_url: The RSS feed URL
            
        Returns:
            Dict containing the latest episode information or None if not found
        """
        result = await self.parse_feed(feed_url)
        
        if not result["success"] or not result["podcast"]["episodes"]:
            return None
        
        return result["podcast"]["episodes"][0]
    
    async def find_episode_by_title(self, feed_url: str, title_pattern: str) -> Optional[Dict[str, Any]]:
        """
        Find an episode by title pattern.
        
        Args:
            feed_url: The RSS feed URL
            title_pattern: Regex pattern to match episode title
            
        Returns:
            Dict containing the episode information or None if not found
        """
        result = await self.parse_feed(feed_url)
        
        if not result["success"]:
            return None
        
        for episode in result["podcast"]["episodes"]:
            if re.search(title_pattern, episode["title"], re.IGNORECASE):
                return episode
        
        return None