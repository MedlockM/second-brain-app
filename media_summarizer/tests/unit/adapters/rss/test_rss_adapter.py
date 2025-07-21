"""
Unit tests for the RSS adapter.
"""
import pytest
import pytest_asyncio
from unittest.mock import patch, MagicMock, AsyncMock
import feedparser
import httpx

from media_summarizer.adapters.rss.rss_adapter import RSSAdapter


@pytest.fixture
def rss_adapter():
    """Create an RSSAdapter instance for testing."""
    return RSSAdapter()


@pytest.fixture
def mock_httpx_response():
    """Create a mock httpx response."""
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.raise_for_status = MagicMock()
    return mock_response


@pytest.fixture
def sample_feed():
    """Create a sample feed for testing."""
    return {
        "feed": {
            "title": "Test Podcast",
            "description": "A test podcast",
            "link": "https://example.com/podcast",
            "image": {"href": "https://example.com/image.jpg"}
        },
        "entries": [
            {
                "title": "Episode 1",
                "description": "First episode",
                "published": "Mon, 01 Jan 2023 12:00:00 +0000",
                "link": "https://example.com/episode1",
                "itunes_duration": "30:00",
                "enclosures": [
                    {"type": "audio/mpeg", "href": "https://example.com/episode1.mp3"}
                ]
            },
            {
                "title": "Episode 2",
                "description": "Second episode",
                "published": "Mon, 08 Jan 2023 12:00:00 +0000",
                "link": "https://example.com/episode2",
                "itunes_duration": "45:00",
                "enclosures": [
                    {"type": "audio/mpeg", "href": "https://example.com/episode2.mp3"}
                ]
            }
        ]
    }


class TestRSSAdapter:
    """Test cases for the RSSAdapter class."""
    
    @pytest.mark.asyncio
    async def test_detect_platform_spotify(self, rss_adapter):
        """Test detecting Spotify platform."""
        url = "https://open.spotify.com/show/123456"
        platform = await rss_adapter.detect_platform(url)
        assert platform == "spotify"
        
        # Test with different Spotify URL format
        url = "https://spotify.com/show/123456"
        platform = await rss_adapter.detect_platform(url)
        assert platform == "spotify"
    
    @pytest.mark.asyncio
    async def test_detect_platform_apple(self, rss_adapter):
        """Test detecting Apple Podcasts platform."""
        url = "https://podcasts.apple.com/us/podcast/test-podcast/id123456"
        platform = await rss_adapter.detect_platform(url)
        assert platform == "apple"
        
        # Test with different Apple URL format
        url = "https://apple.com/podcast/test-podcast/id123456"
        platform = await rss_adapter.detect_platform(url)
        assert platform == "apple"
    
    @pytest.mark.asyncio
    async def test_detect_platform_google(self, rss_adapter):
        """Test detecting Google Podcasts platform."""
        url = "https://podcasts.google.com/feed/123456"
        platform = await rss_adapter.detect_platform(url)
        assert platform == "google"
    
    @pytest.mark.asyncio
    async def test_detect_platform_generic(self, rss_adapter):
        """Test detecting generic platform."""
        url = "https://example.com/podcast"
        platform = await rss_adapter.detect_platform(url)
        assert platform == "generic"
    
    @pytest.mark.asyncio
    async def test_resolve_feed_url_spotify(self, rss_adapter):
        """Test resolving feed URL from Spotify."""
        with patch.object(rss_adapter, "_resolve_spotify_feed") as mock_resolve:
            mock_resolve.return_value = "https://example.com/feed.xml"
            
            url = "https://open.spotify.com/show/123456"
            feed_url = await rss_adapter.resolve_feed_url(url)
            
            mock_resolve.assert_called_once_with(url)
            assert feed_url == "https://example.com/feed.xml"
    
    @pytest.mark.asyncio
    async def test_resolve_feed_url_apple(self, rss_adapter):
        """Test resolving feed URL from Apple Podcasts."""
        with patch.object(rss_adapter, "_resolve_apple_feed") as mock_resolve:
            mock_resolve.return_value = "https://example.com/feed.xml"
            
            url = "https://podcasts.apple.com/us/podcast/test-podcast/id123456"
            feed_url = await rss_adapter.resolve_feed_url(url)
            
            mock_resolve.assert_called_once_with(url)
            assert feed_url == "https://example.com/feed.xml"
    
    @pytest.mark.asyncio
    async def test_resolve_feed_url_google(self, rss_adapter):
        """Test resolving feed URL from Google Podcasts."""
        with patch.object(rss_adapter, "_resolve_google_feed") as mock_resolve:
            mock_resolve.return_value = "https://example.com/feed.xml"
            
            url = "https://podcasts.google.com/feed/123456"
            feed_url = await rss_adapter.resolve_feed_url(url)
            
            mock_resolve.assert_called_once_with(url)
            assert feed_url == "https://example.com/feed.xml"
    
    @pytest.mark.asyncio
    async def test_resolve_feed_url_generic(self, rss_adapter):
        """Test resolving feed URL from generic URL."""
        with patch.object(rss_adapter, "_resolve_generic_feed") as mock_resolve:
            mock_resolve.return_value = "https://example.com/feed.xml"
            
            url = "https://example.com/podcast"
            feed_url = await rss_adapter.resolve_feed_url(url)
            
            mock_resolve.assert_called_once_with(url)
            assert feed_url == "https://example.com/feed.xml"
    
    @pytest.mark.asyncio
    async def test_resolve_feed_url_error(self, rss_adapter):
        """Test error handling in resolve_feed_url."""
        with patch.object(rss_adapter, "_resolve_generic_feed") as mock_resolve:
            mock_resolve.side_effect = Exception("Test error")
            
            url = "https://example.com/podcast"
            with pytest.raises(Exception) as excinfo:
                await rss_adapter.resolve_feed_url(url)
            
            assert "Test error" in str(excinfo.value)
    
    @pytest.mark.asyncio
    async def test_resolve_spotify_feed(self, rss_adapter):
        """Test resolving Spotify feed."""
        url = "https://open.spotify.com/show/123456"
        feed_url = await rss_adapter._resolve_spotify_feed(url)
        
        # Currently, the implementation returns None for Spotify
        assert feed_url is None
    
    @pytest.mark.asyncio
    async def test_resolve_spotify_feed_invalid_url(self, rss_adapter):
        """Test resolving Spotify feed with invalid URL."""
        url = "https://open.spotify.com/invalid/123456"
        feed_url = await rss_adapter._resolve_spotify_feed(url)
        
        assert feed_url is None
    
    @pytest.mark.asyncio
    async def test_resolve_apple_feed(self, rss_adapter, mock_httpx_response):
        """Test resolving Apple Podcasts feed."""
        url = "https://podcasts.apple.com/us/podcast/test-podcast/id123456"
        mock_httpx_response.text = 'feedUrl":"https://example.com/feed.xml"'
        
        with patch("httpx.AsyncClient") as mock_client:
            mock_client_instance = AsyncMock()
            mock_client_instance.get.return_value = mock_httpx_response
            mock_client.return_value.__aenter__.return_value = mock_client_instance
            
            feed_url = await rss_adapter._resolve_apple_feed(url)
            
            mock_client_instance.get.assert_called_once_with(url)
            assert feed_url == "https://example.com/feed.xml"
    
    @pytest.mark.asyncio
    async def test_resolve_apple_feed_no_feed_url(self, rss_adapter, mock_httpx_response):
        """Test resolving Apple Podcasts feed with no feed URL in response."""
        url = "https://podcasts.apple.com/us/podcast/test-podcast/id123456"
        mock_httpx_response.text = "No feed URL here"
        
        with patch("httpx.AsyncClient") as mock_client:
            mock_client_instance = AsyncMock()
            mock_client_instance.get.return_value = mock_httpx_response
            mock_client.return_value.__aenter__.return_value = mock_client_instance
            
            feed_url = await rss_adapter._resolve_apple_feed(url)
            
            mock_client_instance.get.assert_called_once_with(url)
            assert feed_url is None
    
    @pytest.mark.asyncio
    async def test_resolve_apple_feed_error(self, rss_adapter):
        """Test error handling in resolve_apple_feed."""
        url = "https://podcasts.apple.com/us/podcast/test-podcast/id123456"
        
        with patch("httpx.AsyncClient") as mock_client:
            mock_client_instance = AsyncMock()
            mock_client_instance.get.side_effect = Exception("Test error")
            mock_client.return_value.__aenter__.return_value = mock_client_instance
            
            feed_url = await rss_adapter._resolve_apple_feed(url)
            
            mock_client_instance.get.assert_called_once_with(url)
            assert feed_url is None
    
    @pytest.mark.asyncio
    async def test_resolve_google_feed(self, rss_adapter, mock_httpx_response):
        """Test resolving Google Podcasts feed."""
        url = "https://podcasts.google.com/feed/123456"
        mock_httpx_response.text = 'feedUrl":"https://example.com/feed.xml"'
        
        with patch("httpx.AsyncClient") as mock_client:
            mock_client_instance = AsyncMock()
            mock_client_instance.get.return_value = mock_httpx_response
            mock_client.return_value.__aenter__.return_value = mock_client_instance
            
            feed_url = await rss_adapter._resolve_google_feed(url)
            
            mock_client_instance.get.assert_called_once_with(url)
            assert feed_url == "https://example.com/feed.xml"
    
    @pytest.mark.asyncio
    async def test_resolve_generic_feed(self, rss_adapter, mock_httpx_response):
        """Test resolving generic feed."""
        url = "https://example.com/podcast"
        mock_httpx_response.text = '<link rel="alternate" type="application/rss+xml" href="https://example.com/feed.xml">'
        
        with patch("httpx.AsyncClient") as mock_client:
            mock_client_instance = AsyncMock()
            mock_client_instance.get.return_value = mock_httpx_response
            mock_client.return_value.__aenter__.return_value = mock_client_instance
            
            feed_url = await rss_adapter._resolve_generic_feed(url)
            
            mock_client_instance.get.assert_called_once_with(url)
            assert feed_url == "https://example.com/feed.xml"
    
    @pytest.mark.asyncio
    async def test_resolve_generic_feed_relative_url(self, rss_adapter, mock_httpx_response):
        """Test resolving generic feed with relative URL."""
        url = "https://example.com/podcast"
        mock_httpx_response.text = '<link rel="alternate" type="application/rss+xml" href="/feed.xml">'
        
        with patch("httpx.AsyncClient") as mock_client:
            mock_client_instance = AsyncMock()
            mock_client_instance.get.return_value = mock_httpx_response
            mock_client.return_value.__aenter__.return_value = mock_client_instance
            
            feed_url = await rss_adapter._resolve_generic_feed(url)
            
            mock_client_instance.get.assert_called_once_with(url)
            assert feed_url == "https://example.com/feed.xml"
    
    @pytest.mark.asyncio
    async def test_resolve_generic_feed_is_feed(self, rss_adapter, mock_httpx_response):
        """Test resolving generic feed when URL is already a feed."""
        url = "https://example.com/feed.xml"
        mock_httpx_response.text = "<?xml version='1.0'?><rss version='2.0'></rss>"
        mock_httpx_response.headers = {"content-type": "application/xml"}
        
        with patch("httpx.AsyncClient") as mock_client:
            mock_client_instance = AsyncMock()
            mock_client_instance.get.return_value = mock_httpx_response
            mock_client.return_value.__aenter__.return_value = mock_client_instance
            
            feed_url = await rss_adapter._resolve_generic_feed(url)
            
            mock_client_instance.get.assert_called_once_with(url)
            assert feed_url == url
    
    @pytest.mark.asyncio
    async def test_parse_feed(self, rss_adapter, sample_feed):
        """Test parsing a feed."""
        feed_url = "https://example.com/feed.xml"
        
        with patch("feedparser.parse") as mock_parse:
            mock_parse.return_value = sample_feed
            
            result = await rss_adapter.parse_feed(feed_url)
            
            mock_parse.assert_called_once_with(feed_url)
            assert result["success"] is True
            assert result["podcast"]["title"] == "Test Podcast"
            assert len(result["podcast"]["episodes"]) == 2
            assert result["podcast"]["episodes"][0]["title"] == "Episode 1"
            assert result["podcast"]["episodes"][0]["audio_url"] == "https://example.com/episode1.mp3"
    
    @pytest.mark.asyncio
    async def test_parse_feed_empty(self, rss_adapter):
        """Test parsing an empty feed."""
        feed_url = "https://example.com/empty-feed.xml"
        empty_feed = {"feed": {}, "entries": []}
        
        with patch("feedparser.parse") as mock_parse:
            mock_parse.return_value = empty_feed
            
            result = await rss_adapter.parse_feed(feed_url)
            
            mock_parse.assert_called_once_with(feed_url)
            assert result["success"] is False
            assert "No episodes found" in result["error"]
    
    @pytest.mark.asyncio
    async def test_parse_feed_error(self, rss_adapter):
        """Test error handling in parse_feed."""
        feed_url = "https://example.com/feed.xml"
        
        with patch("feedparser.parse") as mock_parse:
            mock_parse.side_effect = Exception("Test error")
            
            result = await rss_adapter.parse_feed(feed_url)
            
            mock_parse.assert_called_once_with(feed_url)
            assert result["success"] is False
            assert "Test error" in result["error"]
    
    @pytest.mark.asyncio
    async def test_get_latest_episode(self, rss_adapter, sample_feed):
        """Test getting the latest episode."""
        feed_url = "https://example.com/feed.xml"
        
        with patch.object(rss_adapter, "parse_feed") as mock_parse:
            mock_parse.return_value = {
                "success": True,
                "podcast": {
                    "title": "Test Podcast",
                    "episodes": [
                        {"title": "Episode 1", "audio_url": "https://example.com/episode1.mp3"},
                        {"title": "Episode 2", "audio_url": "https://example.com/episode2.mp3"}
                    ]
                }
            }
            
            episode = await rss_adapter.get_latest_episode(feed_url)
            
            mock_parse.assert_called_once_with(feed_url)
            assert episode["title"] == "Episode 1"
            assert episode["audio_url"] == "https://example.com/episode1.mp3"
    
    @pytest.mark.asyncio
    async def test_get_latest_episode_no_episodes(self, rss_adapter):
        """Test getting the latest episode when there are no episodes."""
        feed_url = "https://example.com/feed.xml"
        
        with patch.object(rss_adapter, "parse_feed") as mock_parse:
            mock_parse.return_value = {
                "success": True,
                "podcast": {
                    "title": "Test Podcast",
                    "episodes": []
                }
            }
            
            episode = await rss_adapter.get_latest_episode(feed_url)
            
            mock_parse.assert_called_once_with(feed_url)
            assert episode is None
    
    @pytest.mark.asyncio
    async def test_get_latest_episode_parse_error(self, rss_adapter):
        """Test getting the latest episode when parsing fails."""
        feed_url = "https://example.com/feed.xml"
        
        with patch.object(rss_adapter, "parse_feed") as mock_parse:
            mock_parse.return_value = {
                "success": False,
                "error": "Parse error"
            }
            
            episode = await rss_adapter.get_latest_episode(feed_url)
            
            mock_parse.assert_called_once_with(feed_url)
            assert episode is None
    
    @pytest.mark.asyncio
    async def test_find_episode_by_title(self, rss_adapter):
        """Test finding an episode by title."""
        feed_url = "https://example.com/feed.xml"
        
        with patch.object(rss_adapter, "parse_feed") as mock_parse:
            mock_parse.return_value = {
                "success": True,
                "podcast": {
                    "title": "Test Podcast",
                    "episodes": [
                        {"title": "Episode 1", "audio_url": "https://example.com/episode1.mp3"},
                        {"title": "Special Episode", "audio_url": "https://example.com/special.mp3"},
                        {"title": "Episode 2", "audio_url": "https://example.com/episode2.mp3"}
                    ]
                }
            }
            
            episode = await rss_adapter.find_episode_by_title(feed_url, r"Special")
            
            mock_parse.assert_called_once_with(feed_url)
            assert episode["title"] == "Special Episode"
            assert episode["audio_url"] == "https://example.com/special.mp3"
    
    @pytest.mark.asyncio
    async def test_find_episode_by_title_not_found(self, rss_adapter):
        """Test finding an episode by title when not found."""
        feed_url = "https://example.com/feed.xml"
        
        with patch.object(rss_adapter, "parse_feed") as mock_parse:
            mock_parse.return_value = {
                "success": True,
                "podcast": {
                    "title": "Test Podcast",
                    "episodes": [
                        {"title": "Episode 1", "audio_url": "https://example.com/episode1.mp3"},
                        {"title": "Episode 2", "audio_url": "https://example.com/episode2.mp3"}
                    ]
                }
            }
            
            episode = await rss_adapter.find_episode_by_title(feed_url, r"Special")
            
            mock_parse.assert_called_once_with(feed_url)
            assert episode is None
    
    @pytest.mark.asyncio
    async def test_find_episode_by_title_parse_error(self, rss_adapter):
        """Test finding an episode by title when parsing fails."""
        feed_url = "https://example.com/feed.xml"
        
        with patch.object(rss_adapter, "parse_feed") as mock_parse:
            mock_parse.return_value = {
                "success": False,
                "error": "Parse error"
            }
            
            episode = await rss_adapter.find_episode_by_title(feed_url, r"Special")
            
            mock_parse.assert_called_once_with(feed_url)
            assert episode is None