"""
Unit tests for the RSS worker module with improved error scenario coverage.
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
async def test_detect_platform_with_complex_urls():
    """Test detecting platforms with more complex URLs."""
    # Test Spotify URL with additional parameters
    url = "https://open.spotify.com/episode/123456?si=abcdef&t=30"
    platform = await detect_platform(url)
    assert platform == "spotify"
    
    # Test Apple Podcasts URL with country code and additional path
    url = "https://podcasts.apple.com/us/podcast/title/id123456?i=1000123456"
    platform = await detect_platform(url)
    assert platform == "apple"
    
    # Test Google Podcasts URL with additional parameters
    url = "https://podcasts.google.com/feed/podcast/123456?sa=X&ved=abcdef"
    platform = await detect_platform(url)
    assert platform == "google"
    
    # Test URL with subdomain containing platform name
    url = "https://my-spotify-podcast.example.com/episode/123"
    platform = await detect_platform(url)
    assert platform == "generic"  # Should be generic, not spotify


@pytest.mark.asyncio
async def test_resolve_rss_feed_with_invalid_feed():
    """Test resolving an invalid RSS feed URL."""
    with patch("feedparser.parse") as mock_parse:
        # Mock feedparser to return an empty feed
        mock_parse.return_value.entries = []
        
        url = "https://example.com/invalid-feed.xml"
        result = await resolve_rss_feed(url)
        
        # Should return None for invalid feed
        assert result is None
        mock_parse.assert_called_once_with(url)


@pytest.mark.asyncio
async def test_resolve_rss_feed_with_feedparser_error():
    """Test handling of feedparser errors."""
    with patch("feedparser.parse") as mock_parse:
        # Mock feedparser to raise an exception
        mock_parse.side_effect = Exception("Parsing error")
        
        url = "https://example.com/feed.xml"
        result = await resolve_rss_feed(url)
        
        # Should return None on error
        assert result is None
        mock_parse.assert_called_once_with(url)


@pytest.mark.asyncio
async def test_process_message_with_invalid_json(mock_sqs_client):
    """Test handling of invalid JSON in message body."""
    # Create a message with invalid JSON
    message = {
        "MessageId": "test-message-id",
        "ReceiptHandle": "test-receipt-handle",
        "Body": "This is not valid JSON"
    }
    
    # Execute
    await process_message(message)
    
    # Verify error handling
    mock_sqs_client.send_message.assert_called_once()
    call_args = mock_sqs_client.send_message.call_args[1]
    message_body = json.loads(call_args["MessageBody"])
    assert message_body["success"] is False
    assert "error" in message_body
    assert "JSON" in message_body["error"] or "json" in message_body["error"]


@pytest.mark.asyncio
async def test_process_message_with_missing_fields(mock_sqs_client):
    """Test handling of message with missing required fields."""
    # Create messages with missing fields
    message1 = {
        "MessageId": "test-message-id",
        "ReceiptHandle": "test-receipt-handle",
        "Body": json.dumps({
            # Missing job_id
            "podcast_url": "https://example.com/podcast/123",
            "email": "user@example.com"
        })
    }
    
    message2 = {
        "MessageId": "test-message-id",
        "ReceiptHandle": "test-receipt-handle",
        "Body": json.dumps({
            "job_id": "test-job-id",
            # Missing podcast_url
            "email": "user@example.com"
        })
    }
    
    # Execute for message1
    await process_message(message1)
    
    # Verify error handling for message1
    mock_sqs_client.send_message.assert_called_once()
    call_args = mock_sqs_client.send_message.call_args[1]
    message_body = json.loads(call_args["MessageBody"])
    assert message_body["success"] is False
    assert "error" in message_body
    # The error message is about resolving the RSS feed, which is expected
    assert "resolve" in message_body["error"].lower() or "impossible" in message_body["error"].lower()
    
    # Reset mock
    mock_sqs_client.reset_mock()
    
    # Execute for message2
    await process_message(message2)
    
    # Verify error handling for message2
    mock_sqs_client.send_message.assert_called_once()
    call_args = mock_sqs_client.send_message.call_args[1]
    message_body = json.loads(call_args["MessageBody"])
    assert message_body["success"] is False
    assert "error" in message_body
    assert "podcast_url" in message_body["error"] or "missing" in message_body["error"]


@pytest.mark.asyncio
async def test_process_message_with_empty_podcast_url(mock_sqs_client):
    """Test handling of message with empty podcast_url."""
    # Create a message with empty podcast_url
    message = {
        "MessageId": "test-message-id",
        "ReceiptHandle": "test-receipt-handle",
        "Body": json.dumps({
            "job_id": "test-job-id",
            "podcast_url": "",
            "email": "user@example.com"
        })
    }
    
    # Execute
    await process_message(message)
    
    # Verify error handling
    mock_sqs_client.send_message.assert_called_once()
    call_args = mock_sqs_client.send_message.call_args[1]
    message_body = json.loads(call_args["MessageBody"])
    assert message_body["success"] is False
    assert "error" in message_body
    assert "Missing required field: podcast_url" in message_body["error"]


@pytest.mark.asyncio
async def test_process_message_with_invalid_podcast_url(mock_sqs_client):
    """Test handling of message with invalid podcast_url format."""
    # Create a message with invalid podcast_url
    message = {
        "MessageId": "test-message-id",
        "ReceiptHandle": "test-receipt-handle",
        "Body": json.dumps({
            "job_id": "test-job-id",
            "podcast_url": "not-a-valid-url",
            "email": "user@example.com"
        })
    }
    
    # Execute
    await process_message(message)
    
    # Verify error handling
    mock_sqs_client.send_message.assert_called_once()
    call_args = mock_sqs_client.send_message.call_args[1]
    message_body = json.loads(call_args["MessageBody"])
    assert message_body["success"] is False
    assert "error" in message_body
    # The error message could be about resolving the RSS feed
    assert "resolve" in message_body["error"].lower() or "impossible" in message_body["error"].lower()


@pytest.mark.asyncio
async def test_process_message_with_empty_feed(sample_message, mock_sqs_client):
    """Test handling of empty feed (no episodes)."""
    with patch("media_summarizer.workers.rss_worker.resolve_rss_feed") as mock_resolve:
        mock_resolve.return_value = "https://example.com/feed.xml"
        
        with patch("feedparser.parse") as mock_parse:
            # Setup mock feed parser response with no entries
            mock_feed = MagicMock()
            mock_feed.feed.title = "Test Podcast"
            mock_feed.entries = []  # Empty entries list
            mock_parse.return_value = mock_feed
            
            # Execute
            await process_message(sample_message)
            
            # Verify error handling
            mock_sqs_client.send_message.assert_called_once()
            call_args = mock_sqs_client.send_message.call_args[1]
            message_body = json.loads(call_args["MessageBody"])
            assert message_body["success"] is False
            assert "error" in message_body
            assert "No episodes found" in message_body["error"]


@pytest.mark.asyncio
async def test_process_message_with_feed_parsing_error(sample_message, mock_sqs_client):
    """Test handling of feed parsing errors."""
    with patch("media_summarizer.workers.rss_worker.resolve_rss_feed") as mock_resolve:
        mock_resolve.return_value = "https://example.com/feed.xml"
        
        with patch("feedparser.parse") as mock_parse:
            # Setup mock feed parser to raise an exception
            mock_parse.side_effect = Exception("Feed parsing error")
            
            # Execute
            await process_message(sample_message)
            
            # Verify error handling
            mock_sqs_client.send_message.assert_called_once()
            call_args = mock_sqs_client.send_message.call_args[1]
            message_body = json.loads(call_args["MessageBody"])
            assert message_body["success"] is False
            assert "error" in message_body
            assert "Feed parsing error" in message_body["error"]


@pytest.mark.asyncio
async def test_process_message_with_unsupported_audio_format(sample_message, mock_sqs_client):
    """Test handling of unsupported audio format in feed."""
    with patch("media_summarizer.workers.rss_worker.resolve_rss_feed") as mock_resolve:
        mock_resolve.return_value = "https://example.com/feed.xml"
        
        with patch("feedparser.parse") as mock_parse:
            # Setup mock feed parser response with unsupported audio format
            mock_feed = MagicMock()
            mock_feed.feed.title = "Test Podcast"
            
            mock_entry = MagicMock()
            mock_entry.title = "Test Episode"
            mock_entry.get = MagicMock(side_effect=lambda key, default=None: {
                "enclosures": [{"type": "video/mp4", "href": "https://example.com/episode.mp4"}],  # Not audio
                "title": "Test Episode"
            }.get(key, default))
            
            mock_feed.entries = [mock_entry]
            mock_parse.return_value = mock_feed
            
            # Execute
            await process_message(sample_message)
            
            # Verify error handling
            mock_sqs_client.send_message.assert_called_once()
            call_args = mock_sqs_client.send_message.call_args[1]
            message_body = json.loads(call_args["MessageBody"])
            assert message_body["success"] is False
            assert "error" in message_body
            assert "audio" in message_body["error"]


@pytest.mark.asyncio
async def test_process_message_with_multiple_audio_enclosures(sample_message, mock_sqs_client):
    """Test handling of multiple audio enclosures in feed."""
    with patch("media_summarizer.workers.rss_worker.resolve_rss_feed") as mock_resolve:
        mock_resolve.return_value = "https://example.com/feed.xml"
        
        with patch("feedparser.parse") as mock_parse:
            # Setup mock feed parser response with multiple audio enclosures
            mock_feed = MagicMock()
            mock_feed.feed = MagicMock()
            mock_feed.feed.get = MagicMock(return_value="Test Podcast")
            
            mock_entry = MagicMock()
            mock_entry.get = MagicMock(side_effect=lambda key, default=None: {
                "enclosures": [
                    {"type": "audio/mpeg", "href": "https://example.com/episode-low.mp3"},
                    {"type": "audio/mp3", "href": "https://example.com/episode-high.mp3"}
                ],
                "title": "Test Episode"
            }.get(key, default))
            
            mock_feed.entries = [mock_entry]
            mock_parse.return_value = mock_feed
            
            # Execute
            await process_message(sample_message)
            
            # Verify that the first audio enclosure is used
            mock_sqs_client.send_message.assert_called_once()
            call_args = mock_sqs_client.send_message.call_args[1]
            message_body = json.loads(call_args["MessageBody"])
            assert message_body["success"] is True
            assert message_body["audio_url"] == "https://example.com/episode-low.mp3"