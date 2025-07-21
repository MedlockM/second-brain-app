"""
Unit tests for the RSS worker module.
"""
import json
import pytest
import pytest_asyncio
import os
from unittest.mock import patch, MagicMock, AsyncMock

# Set AWS credentials for testing
os.environ["AWS_ACCESS_KEY_ID"] = "test"
os.environ["AWS_SECRET_ACCESS_KEY"] = "test"
os.environ["AWS_DEFAULT_REGION"] = "us-east-1"
os.environ["AWS_ENDPOINT_URL"] = "http://localhost:4566"

from media_summarizer.workers.rss_worker import (
    detect_platform,
    resolve_rss_feed,
    process_message,
)


@pytest.fixture
def mock_sqs_client():
    """Mock SQS client for testing."""
    with patch("media_summarizer.workers.rss_worker.sqs_client") as mock_client:
        yield mock_client


@pytest.fixture
def sample_message():
    """Create a sample SQS message for testing."""
    return {
        "MessageId": "test-message-id",
        "ReceiptHandle": "test-receipt-handle",
        "Body": json.dumps({
            "job_id": "test-job-id",
            "podcast_url": "https://example.com/podcast/123",
            "email": "user@example.com"
        })
    }


@pytest.mark.asyncio
async def test_detect_platform_spotify():
    """Test detecting Spotify platform."""
    url = "https://open.spotify.com/episode/123456"
    platform = await detect_platform(url)
    assert platform == "spotify"


@pytest.mark.asyncio
async def test_detect_platform_apple():
    """Test detecting Apple Podcasts platform."""
    url = "https://podcasts.apple.com/us/podcast/episode/123456"
    platform = await detect_platform(url)
    assert platform == "apple"


@pytest.mark.asyncio
async def test_detect_platform_google():
    """Test detecting Google Podcasts platform."""
    url = "https://podcasts.google.com/feed/podcast/123456"
    platform = await detect_platform(url)
    assert platform == "google"


@pytest.mark.asyncio
async def test_detect_platform_generic():
    """Test detecting generic platform."""
    url = "https://example.com/podcast/123456"
    platform = await detect_platform(url)
    assert platform == "generic"


@pytest.mark.asyncio
async def test_resolve_rss_feed_direct_rss():
    """Test resolving a direct RSS feed URL."""
    with patch("feedparser.parse") as mock_parse:
        mock_parse.return_value.entries = ["entry1", "entry2"]
        
        url = "https://example.com/feed.xml"
        result = await resolve_rss_feed(url)
        
        assert result == url
        mock_parse.assert_called_once_with(url)


@pytest.mark.asyncio
async def test_resolve_rss_feed_platform_specific():
    """Test resolving platform-specific URLs."""
    # This is a placeholder test since the actual implementation
    # of platform-specific resolvers is not complete in the code
    with patch("media_summarizer.workers.rss_worker.detect_platform") as mock_detect:
        mock_detect.return_value = "spotify"
        
        url = "https://open.spotify.com/episode/123456"
        result = await resolve_rss_feed(url)
        
        # Current implementation returns None for unimplemented platforms
        assert result is None
        mock_detect.assert_called_once_with(url)


@pytest.mark.asyncio
async def test_process_message_success(sample_message, mock_sqs_client):
    """Test successful processing of a message."""
    with patch("media_summarizer.workers.rss_worker.resolve_rss_feed") as mock_resolve:
        mock_resolve.return_value = "https://example.com/feed.xml"
        
        with patch("feedparser.parse") as mock_parse:
            # Setup mock feed parser response with a proper dictionary structure
            mock_feed = MagicMock()
            mock_feed.feed.title = "Test Podcast"
            mock_feed.feed.get = MagicMock(return_value="Test Podcast")
            
            mock_entry = MagicMock()
            mock_entry.title = "Test Episode"
            mock_entry.get = MagicMock(side_effect=lambda key, default=None: {
                "enclosures": [{"type": "audio/mp3", "href": "https://example.com/episode.mp3"}],
                "title": "Test Episode"
            }.get(key, default))
            
            mock_feed.entries = [mock_entry]
            mock_parse.return_value = mock_feed
            
            # Execute
            await process_message(sample_message)
            
            # Verify
            mock_resolve.assert_called_once()
            mock_parse.assert_called_once()
            mock_sqs_client.send_message.assert_called_once()
            
            # Check the message sent to the next queue
            call_args = mock_sqs_client.send_message.call_args[1]
            message_body = json.loads(call_args["MessageBody"])
            assert message_body["job_id"] == "test-job-id"
            assert message_body["audio_url"] == "https://example.com/episode.mp3"
            assert message_body["success"] is True


@pytest.mark.asyncio
async def test_process_message_rss_resolution_failure(sample_message, mock_sqs_client):
    """Test handling of RSS resolution failure."""
    with patch("media_summarizer.workers.rss_worker.resolve_rss_feed") as mock_resolve:
        mock_resolve.return_value = None
        
        # Execute
        await process_message(sample_message)
        
        # Verify
        mock_resolve.assert_called_once()
        mock_sqs_client.send_message.assert_called_once()
        
        # Check the error message sent
        call_args = mock_sqs_client.send_message.call_args[1]
        message_body = json.loads(call_args["MessageBody"])
        assert message_body["job_id"] == "test-job-id"
        assert message_body["success"] is False
        assert "error" in message_body
        assert "step" in message_body and message_body["step"] == "rss_resolution"


@pytest.mark.asyncio
async def test_process_message_no_audio_url(sample_message, mock_sqs_client):
    """Test handling of missing audio URL in feed."""
    with patch("media_summarizer.workers.rss_worker.resolve_rss_feed") as mock_resolve:
        mock_resolve.return_value = "https://example.com/feed.xml"
        
        with patch("feedparser.parse") as mock_parse:
            # Setup mock feed parser response with no audio enclosure
            class MockFeed:
                class Feed:
                    def __init__(self):
                        self.title = "Test Podcast"
                
                class Entry:
                    def __init__(self):
                        self.title = "Test Episode"
                        self.enclosures = []  # No enclosures
                
                def __init__(self):
                    self.feed = self.Feed()
                    self.entries = [self.Entry()]
            
            mock_parse.return_value = MockFeed()
            
            # Execute
            await process_message(sample_message)
            
            # Verify
            mock_sqs_client.send_message.assert_called_once()
            
            # Check the error message sent
            call_args = mock_sqs_client.send_message.call_args[1]
            message_body = json.loads(call_args["MessageBody"])
            assert message_body["success"] is False
            assert "error" in message_body