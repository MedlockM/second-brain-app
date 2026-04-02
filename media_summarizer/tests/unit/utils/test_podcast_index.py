"""
Unit tests for Podcast Index utilities.

This module contains unit tests for all Podcast Index utility functions,
using mocked HTTP operations to test the logic without requiring
actual API calls.
"""
import pytest
import asyncio
import time
from unittest.mock import Mock, patch, AsyncMock, MagicMock
import httpx

from media_summarizer.utils import podcast_index


@pytest.fixture
def mock_http_client():
    """Create a mock HTTP client."""
    mock_client = AsyncMock()
    return mock_client


@pytest.fixture
def mock_httpx_response():
    """Create a mock httpx response."""
    mock_response = Mock()
    mock_response.raise_for_status = Mock()
    mock_response.json = Mock()
    return mock_response


class TestGenerateHeaders:
    """Test authentication header generation."""

    def test_generate_headers_with_valid_credentials(self):
        """Test header generation with valid API credentials."""
        with patch.dict('os.environ', {
            'PODCASTINDEXORG_API_KEY': 'test_key',
            'PODCASTINDEXORG_API_SECRET': 'test_secret'
        }):
            with patch('media_summarizer.utils.podcast_index.API_KEY', 'test_key'):
                with patch('media_summarizer.utils.podcast_index.API_SECRET', 'test_secret'):
                    with patch('media_summarizer.utils.podcast_index.time.time', return_value=1640995200):
                        headers = podcast_index._generate_headers()

                        assert 'X-Auth-Date' in headers
                        assert 'X-Auth-Key' in headers
                        assert 'Authorization' in headers
                        assert 'User-Agent' in headers
                        assert headers['X-Auth-Date'] == '1640995200'
                        assert headers['X-Auth-Key'] == 'test_key'
                        assert headers['User-Agent'] == 'MediaSummarizer/1.0'

    def test_generate_headers_with_real_credentials(self):
        """Test header generation with real credentials produces auth headers."""
        with patch('media_summarizer.utils.podcast_index.API_KEY', 'real_key'):
            with patch('media_summarizer.utils.podcast_index.API_SECRET', 'real_secret'):
                with patch('media_summarizer.utils.podcast_index.time.time', return_value=1640995200):
                    headers = podcast_index._generate_headers()

                    assert 'X-Auth-Date' in headers
                    assert 'X-Auth-Key' in headers
                    assert 'Authorization' in headers
                    assert 'User-Agent' in headers
                    assert headers['X-Auth-Date'] == '1640995200'
                    assert headers['X-Auth-Key'] == 'real_key'
                    assert headers['User-Agent'] == 'MediaSummarizer/1.0'

    def test_generate_headers_missing_credentials(self):
        """Test header generation with missing credentials."""
        with patch('media_summarizer.utils.podcast_index.API_KEY', None):
            with patch('media_summarizer.utils.podcast_index.API_SECRET', None):
                with pytest.raises(ValueError, match="PODCASTINDEXORG_API_KEY and PODCASTINDEXORG_API_SECRET must be set"):
                    podcast_index._generate_headers()


class TestSearchPodcasts:
    """Test podcast search functionality."""

    @pytest.mark.asyncio
    async def test_search_podcasts_success(self, mock_http_client, mock_httpx_response):
        """Test successful podcast search."""
        expected_data = {
            'status': 'true',
            'count': 2,
            'feeds': [
                {'id': 1, 'title': 'Test Podcast 1'},
                {'id': 2, 'title': 'Test Podcast 2'}
            ]
        }
        mock_httpx_response.json.return_value = expected_data
        mock_http_client.get.return_value = mock_httpx_response

        with patch('media_summarizer.utils.podcast_index._generate_headers', return_value={'auth': 'test'}):
            result = await podcast_index.search_podcasts(
                query="test podcast",
                max_results=5,
                clean=True,
                http_client=mock_http_client
            )

        mock_http_client.get.assert_called_once()
        call_args = mock_http_client.get.call_args
        assert call_args[0][0] == f"{podcast_index.PODCAST_INDEX_BASE_URL}/search/byterm"
        assert call_args[1]['headers'] == {'auth': 'test'}
        assert call_args[1]['params']['q'] == 'test podcast'
        assert call_args[1]['params']['max'] == 5
        assert call_args[1]['params']['clean'] == 'true'
        assert result == expected_data

    @pytest.mark.asyncio
    async def test_search_podcasts_with_similar(self, mock_http_client, mock_httpx_response):
        """Test podcast search with similar (fuzzy) flag."""
        expected_data = {'status': 'true', 'count': 0, 'feeds': []}
        mock_httpx_response.json.return_value = expected_data
        mock_http_client.get.return_value = mock_httpx_response

        with patch('media_summarizer.utils.podcast_index._generate_headers', return_value={'auth': 'test'}):
            result = await podcast_index.search_podcasts(
                query="test podcast",
                max_results=5,
                clean=True,
                similar=True,
                http_client=mock_http_client
            )

        mock_http_client.get.assert_called_once()
        call_params = mock_http_client.get.call_args[1]['params']
        assert call_params['similar'] == 'true'
        assert result == expected_data

    @pytest.mark.asyncio
    async def test_search_podcasts_without_client(self, mock_httpx_response):
        """Test podcast search without provided HTTP client."""
        expected_data = {'status': 'true', 'count': 0, 'feeds': []}
        mock_httpx_response.json.return_value = expected_data

        with patch('media_summarizer.utils.podcast_index._generate_headers', return_value={'auth': 'test'}):
            with patch('httpx.AsyncClient') as mock_client_class:
                mock_client = AsyncMock()
                mock_client.get.return_value = mock_httpx_response
                mock_client_class.return_value.__aenter__.return_value = mock_client

                result = await podcast_index.search_podcasts(
                    query="test",
                    max_results=10,
                    clean=False
                )

                mock_client.get.assert_called_once()
                call_params = mock_client.get.call_args[1]['params']
                assert call_params['q'] == 'test'
                assert call_params['max'] == 10
                assert 'clean' not in call_params

    @pytest.mark.asyncio
    async def test_search_podcasts_max_limit(self, mock_http_client, mock_httpx_response):
        """Test podcast search with max limit enforcement."""
        mock_httpx_response.json.return_value = {'status': 'true', 'count': 0}
        mock_http_client.get.return_value = mock_httpx_response

        with patch('media_summarizer.utils.podcast_index._generate_headers', return_value={}):
            await podcast_index.search_podcasts(
                query="test",
                max_results=1500,  # Above limit
                http_client=mock_http_client
            )

        call_params = mock_http_client.get.call_args[1]['params']
        assert call_params['max'] == 1000  # Should be capped at 1000

    @pytest.mark.asyncio
    async def test_search_podcasts_http_error(self, mock_http_client):
        """Test podcast search with HTTP error."""
        mock_response = Mock()
        mock_response.status_code = 404
        mock_response.text = "Not Found"
        mock_http_client.get.side_effect = httpx.HTTPStatusError(
            "404 Not Found", request=Mock(), response=mock_response
        )

        with patch('media_summarizer.utils.podcast_index._generate_headers', return_value={}):
            with pytest.raises(Exception, match="Failed to search podcasts: 404"):
                await podcast_index.search_podcasts(
                    query="test",
                    http_client=mock_http_client
                )

    @pytest.mark.asyncio
    async def test_search_podcasts_generic_error(self, mock_http_client):
        """Test podcast search with generic error."""
        mock_http_client.get.side_effect = Exception("Network error")

        with patch('media_summarizer.utils.podcast_index._generate_headers', return_value={}):
            with pytest.raises(Exception, match="Network error"):
                await podcast_index.search_podcasts(
                    query="test",
                    http_client=mock_http_client
                )


class TestGetPodcastByFeedUrl:
    """Test get podcast by feed URL functionality."""

    @pytest.mark.asyncio
    async def test_get_podcast_by_feed_url_success(self, mock_http_client, mock_httpx_response):
        """Test successful podcast retrieval by feed URL."""
        expected_data = {
            'status': 'true',
            'feed': {'id': 123, 'title': 'Test Podcast', 'url': 'https://example.com/feed.xml'}
        }
        mock_httpx_response.json.return_value = expected_data
        mock_http_client.get.return_value = mock_httpx_response

        with patch('media_summarizer.utils.podcast_index._generate_headers', return_value={'auth': 'test'}):
            result = await podcast_index.get_podcast_by_feed_url(
                feed_url="https://example.com/feed.xml",
                http_client=mock_http_client
            )

        mock_http_client.get.assert_called_once()
        call_args = mock_http_client.get.call_args
        assert call_args[0][0] == f"{podcast_index.PODCAST_INDEX_BASE_URL}/podcasts/byfeedurl"
        assert call_args[1]['params']['url'] == 'https://example.com/feed.xml'
        assert result == expected_data

    @pytest.mark.asyncio
    async def test_get_podcast_by_feed_url_error(self, mock_http_client):
        """Test get podcast by feed URL with error."""
        mock_response = Mock()
        mock_response.status_code = 500
        mock_response.text = "Server Error"
        mock_http_client.get.side_effect = httpx.HTTPStatusError(
            "500 Server Error", request=Mock(), response=mock_response
        )

        with patch('media_summarizer.utils.podcast_index._generate_headers', return_value={}):
            with pytest.raises(Exception, match="Failed to get podcast by feed URL: 500"):
                await podcast_index.get_podcast_by_feed_url(
                    feed_url="https://example.com/feed.xml",
                    http_client=mock_http_client
                )


class TestGetEpisodesByFeedId:
    """Test get episodes by feed ID functionality."""

    @pytest.mark.asyncio
    async def test_get_episodes_by_feed_id_success(self, mock_http_client, mock_httpx_response):
        """Test successful episodes retrieval by feed ID."""
        expected_data = {
            'status': 'true',
            'count': 1,
            'items': [{'id': 456, 'title': 'Test Episode'}]
        }
        mock_httpx_response.json.return_value = expected_data
        mock_http_client.get.return_value = mock_httpx_response

        with patch('media_summarizer.utils.podcast_index._generate_headers', return_value={'auth': 'test'}):
            result = await podcast_index.get_episodes_by_feed_id(
                feed_id=123,
                max_results=5,
                since=1640995200,
                http_client=mock_http_client
            )

        mock_http_client.get.assert_called_once()
        call_args = mock_http_client.get.call_args
        assert call_args[0][0] == f"{podcast_index.PODCAST_INDEX_BASE_URL}/episodes/byfeedid"
        assert call_args[1]['params']['id'] == 123
        assert call_args[1]['params']['max'] == 5
        assert call_args[1]['params']['since'] == 1640995200
        assert result == expected_data

    @pytest.mark.asyncio
    async def test_get_episodes_by_feed_id_no_since(self, mock_http_client, mock_httpx_response):
        """Test episodes retrieval without since parameter."""
        mock_httpx_response.json.return_value = {'status': 'true', 'count': 0}
        mock_http_client.get.return_value = mock_httpx_response

        with patch('media_summarizer.utils.podcast_index._generate_headers', return_value={}):
            await podcast_index.get_episodes_by_feed_id(
                feed_id=123,
                http_client=mock_http_client
            )

        call_params = mock_http_client.get.call_args[1]['params']
        assert 'since' not in call_params
        assert call_params['max'] == 10


class TestGetEpisodesByFeedUrl:
    """Test get episodes by feed URL functionality."""

    @pytest.mark.asyncio
    async def test_get_episodes_by_feed_url_success(self, mock_http_client, mock_httpx_response):
        """Test successful episodes retrieval by feed URL."""
        expected_data = {
            'status': 'true',
            'count': 2,
            'items': [
                {'id': 456, 'title': 'Episode 1'},
                {'id': 457, 'title': 'Episode 2'}
            ]
        }
        mock_httpx_response.json.return_value = expected_data
        mock_http_client.get.return_value = mock_httpx_response

        with patch('media_summarizer.utils.podcast_index._generate_headers', return_value={'auth': 'test'}):
            result = await podcast_index.get_episodes_by_feed_url(
                feed_url="https://example.com/feed.xml",
                max_results=20,
                http_client=mock_http_client
            )

        mock_http_client.get.assert_called_once()
        call_args = mock_http_client.get.call_args
        assert call_args[0][0] == f"{podcast_index.PODCAST_INDEX_BASE_URL}/episodes/byfeedurl"
        assert call_args[1]['params']['url'] == 'https://example.com/feed.xml'
        assert call_args[1]['params']['max'] == 20
        assert result == expected_data


class TestGetEpisodeById:
    """Test get episode by ID functionality."""

    @pytest.mark.asyncio
    async def test_get_episode_by_id_success(self, mock_http_client, mock_httpx_response):
        """Test successful episode retrieval by ID."""
        expected_data = {
            'status': 'true',
            'episode': {'id': 456, 'title': 'Test Episode', 'url': 'https://example.com/episode.mp3'}
        }
        mock_httpx_response.json.return_value = expected_data
        mock_http_client.get.return_value = mock_httpx_response

        with patch('media_summarizer.utils.podcast_index._generate_headers', return_value={'auth': 'test'}):
            result = await podcast_index.get_episode_by_id(
                episode_id=456,
                http_client=mock_http_client
            )

        mock_http_client.get.assert_called_once()
        call_args = mock_http_client.get.call_args
        assert call_args[0][0] == f"{podcast_index.PODCAST_INDEX_BASE_URL}/episodes/byid"
        assert call_args[1]['params']['id'] == 456
        assert result == expected_data

    @pytest.mark.asyncio
    async def test_get_episode_by_id_error(self, mock_http_client):
        """Test get episode by ID with error."""
        mock_response = Mock()
        mock_response.status_code = 404
        mock_response.text = "Episode not found"
        mock_http_client.get.side_effect = httpx.HTTPStatusError(
            "404 Not Found", request=Mock(), response=mock_response
        )

        with patch('media_summarizer.utils.podcast_index._generate_headers', return_value={}):
            with pytest.raises(Exception, match="Failed to get episode by ID: 404"):
                await podcast_index.get_episode_by_id(
                    episode_id=999,
                    http_client=mock_http_client
                )


class TestSearchEpisodes:
    """Test episode search functionality."""

    @pytest.mark.asyncio
    async def test_search_episodes_success(self, mock_http_client, mock_httpx_response):
        """Test successful episode search."""
        expected_data = {
            'status': 'true',
            'count': 1,
            'items': [{'id': 456, 'title': 'Test Episode'}]
        }
        mock_httpx_response.json.return_value = expected_data
        mock_http_client.get.return_value = mock_httpx_response

        with patch('media_summarizer.utils.podcast_index._generate_headers', return_value={'auth': 'test'}):
            result = await podcast_index.search_episodes(
                query="test episode",
                max_results=15,
                feed_id=123,
                http_client=mock_http_client
            )

        mock_http_client.get.assert_called_once()
        call_args = mock_http_client.get.call_args
        assert call_args[0][0] == f"{podcast_index.PODCAST_INDEX_BASE_URL}/search/byterm"
        assert call_args[1]['params']['q'] == 'test episode'
        assert call_args[1]['params']['max'] == 15
        assert call_args[1]['params']['feedid'] == 123
        assert result == expected_data

    @pytest.mark.asyncio
    async def test_search_episodes_no_feed_id(self, mock_http_client, mock_httpx_response):
        """Test episode search without feed ID."""
        mock_httpx_response.json.return_value = {'status': 'true', 'count': 0}
        mock_http_client.get.return_value = mock_httpx_response

        with patch('media_summarizer.utils.podcast_index._generate_headers', return_value={}):
            await podcast_index.search_episodes(
                query="test",
                http_client=mock_http_client
            )

        call_params = mock_http_client.get.call_args[1]['params']
        assert 'feedid' not in call_params
        assert call_params['q'] == 'test'
        assert call_params['max'] == 10

    @pytest.mark.asyncio
    async def test_search_episodes_max_limit(self, mock_http_client, mock_httpx_response):
        """Test episode search with max limit enforcement."""
        mock_httpx_response.json.return_value = {'status': 'true', 'count': 0}
        mock_http_client.get.return_value = mock_httpx_response

        with patch('media_summarizer.utils.podcast_index._generate_headers', return_value={}):
            await podcast_index.search_episodes(
                query="test",
                max_results=2000,  # Above limit
                http_client=mock_http_client
            )

        call_params = mock_http_client.get.call_args[1]['params']
        assert call_params['max'] == 1000  # Should be capped at 1000


class TestErrorHandling:
    """Test error handling scenarios."""

    @pytest.mark.asyncio
    async def test_http_status_error_handling(self, mock_http_client):
        """Test handling of HTTP status errors."""
        mock_response = Mock()
        mock_response.status_code = 403
        mock_response.text = "Forbidden"
        mock_http_client.get.side_effect = httpx.HTTPStatusError(
            "403 Forbidden", request=Mock(), response=mock_response
        )

        with patch('media_summarizer.utils.podcast_index._generate_headers', return_value={}):
            with pytest.raises(Exception, match="Failed to search podcasts: 403"):
                await podcast_index.search_podcasts(
                    query="test",
                    http_client=mock_http_client
                )

    @pytest.mark.asyncio
    async def test_generic_exception_handling(self, mock_http_client):
        """Test handling of generic exceptions."""
        mock_http_client.get.side_effect = Exception("Connection timeout")

        with patch('media_summarizer.utils.podcast_index._generate_headers', return_value={}):
            with pytest.raises(Exception, match="Connection timeout"):
                await podcast_index.search_podcasts(
                    query="test",
                    http_client=mock_http_client
                )

    @pytest.mark.asyncio
    async def test_session_management_without_client(self, mock_httpx_response):
        """Test proper session management when no client is provided."""
        mock_httpx_response.json.return_value = {'status': 'true', 'count': 0}

        with patch('media_summarizer.utils.podcast_index._generate_headers', return_value={}):
            with patch('httpx.AsyncClient') as mock_client_class:
                mock_client = AsyncMock()
                mock_client.get.return_value = mock_httpx_response
                mock_client_class.return_value.__aenter__.return_value = mock_client
                mock_client_class.return_value.__aexit__ = AsyncMock()

                await podcast_index.search_podcasts(query="test")

                # Verify async context manager was used
                mock_client_class.assert_called_once()
                mock_client_class.return_value.__aenter__.assert_called_once()
