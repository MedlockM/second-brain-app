"""
Unit tests for the download worker module with improved edge case coverage.
"""
import json
import os
import pytest
import pytest_asyncio
import tempfile
from unittest.mock import patch, MagicMock, AsyncMock

# Set AWS credentials for testing
os.environ["AWS_ACCESS_KEY_ID"] = "test"
os.environ["AWS_SECRET_ACCESS_KEY"] = "test"
os.environ["AWS_DEFAULT_REGION"] = "us-east-1"
os.environ["AWS_ENDPOINT_URL"] = "http://localhost:4566"

from media_summarizer.workers.download_worker import (
    download_audio,
    process_message,
)


@pytest.fixture
def mock_s3_client():
    """Mock S3 client for testing."""
    with patch("media_summarizer.workers.download_worker.s3_client") as mock_client:
        yield mock_client


@pytest.fixture
def mock_sqs_client():
    """Mock SQS client for testing."""
    with patch("media_summarizer.workers.download_worker.sqs_client") as mock_client:
        yield mock_client


@pytest.fixture
def sample_message():
    """Create a sample SQS message for testing."""
    return {
        "MessageId": "test-message-id",
        "ReceiptHandle": "test-receipt-handle",
        "Body": json.dumps({
            "job_id": "test-job-id",
            "audio_url": "https://example.com/podcast.mp3",
        })
    }


@pytest.mark.asyncio
async def test_download_audio_http_error():
    """Test handling of HTTP errors during audio download."""
    with patch("httpx.AsyncClient") as mock_client:
        # Create a real exception to raise
        http_error = Exception("HTTP 404 Not Found")
        
        # Setup mock client to raise the exception
        mock_client_instance = AsyncMock()
        mock_client_instance.stream.side_effect = http_error
        mock_client_instance.__aenter__.return_value = mock_client_instance
        
        mock_client.return_value = mock_client_instance
        
        # Execute and verify
        with pytest.raises(Exception) as excinfo:
            await download_audio("https://example.com/not-found.mp3", "/tmp/test.mp3")
        
        assert "HTTP 404 Not Found" in str(excinfo.value)
        mock_client_instance.stream.assert_called_once()


@pytest.mark.asyncio
async def test_download_audio_timeout():
    """Test handling of timeout during audio download."""
    with patch("httpx.AsyncClient") as mock_client:
        # Setup mock with timeout error
        mock_client_instance = AsyncMock()
        mock_client_instance.stream.side_effect = TimeoutError("Connection timed out")
        mock_client_instance.__aenter__.return_value = mock_client_instance
        
        mock_client.return_value = mock_client_instance
        
        # Execute and verify
        with pytest.raises(TimeoutError) as excinfo:
            await download_audio("https://example.com/podcast.mp3", "/tmp/test.mp3")
        
        assert "Connection timed out" in str(excinfo.value)
        mock_client_instance.stream.assert_called_once()


@pytest.mark.asyncio
async def test_download_audio_file_write_error():
    """Test handling of file write errors during audio download."""
    with patch("httpx.AsyncClient") as mock_client:
        # Setup mock response
        mock_response = AsyncMock()
        mock_response.raise_for_status.return_value = None
        
        # Setup mock for aiter_bytes to return some data
        mock_response.aiter_bytes.return_value = [b"chunk1", b"chunk2"]
        mock_response.__aenter__.return_value = mock_response
        
        mock_client_instance = AsyncMock()
        mock_client_instance.stream.return_value = mock_response
        mock_client_instance.__aenter__.return_value = mock_client_instance
        
        mock_client.return_value = mock_client_instance
        
        # Mock open to raise an error
        with patch("builtins.open") as mock_open:
            mock_open.side_effect = PermissionError("Permission denied")
            
            # Execute and verify
            with pytest.raises(PermissionError) as excinfo:
                await download_audio("https://example.com/podcast.mp3", "/tmp/test.mp3")
            
            assert "Permission denied" in str(excinfo.value)
            mock_client_instance.stream.assert_called_once()


@pytest.mark.asyncio
async def test_process_message_with_invalid_json(mock_s3_client, mock_sqs_client):
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
async def test_process_message_with_missing_fields(mock_s3_client, mock_sqs_client):
    """Test handling of message with missing required fields."""
    # Create a message with missing audio_url
    message = {
        "MessageId": "test-message-id",
        "ReceiptHandle": "test-receipt-handle",
        "Body": json.dumps({
            "job_id": "test-job-id",
            # Missing audio_url
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
    assert "audio_url" in message_body["error"]
    
    # Reset mock
    mock_sqs_client.reset_mock()
    
    # Create a message with missing job_id
    message = {
        "MessageId": "test-message-id",
        "ReceiptHandle": "test-receipt-handle",
        "Body": json.dumps({
            # Missing job_id
            "audio_url": "https://example.com/podcast.mp3"
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
    assert "job_id" in message_body["error"]


@pytest.mark.asyncio
async def test_process_message_with_empty_audio_url(mock_s3_client, mock_sqs_client):
    """Test handling of message with empty audio_url."""
    # Create a message with empty audio_url
    message = {
        "MessageId": "test-message-id",
        "ReceiptHandle": "test-receipt-handle",
        "Body": json.dumps({
            "job_id": "test-job-id",
            "audio_url": ""
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
    assert "empty" in message_body["error"] or "invalid" in message_body["error"]


@pytest.mark.asyncio
async def test_process_message_with_invalid_audio_url(mock_s3_client, mock_sqs_client):
    """Test handling of message with invalid audio_url format."""
    # Create a message with invalid audio_url
    message = {
        "MessageId": "test-message-id",
        "ReceiptHandle": "test-receipt-handle",
        "Body": json.dumps({
            "job_id": "test-job-id",
            "audio_url": "not-a-valid-url"
        })
    }
    
    # Setup download_audio to raise an error for invalid URL
    with patch("media_summarizer.workers.download_worker.download_audio") as mock_download:
        mock_download.side_effect = ValueError("Invalid URL format")
        
        # Execute
        await process_message(message)
        
        # Verify error handling
        mock_sqs_client.send_message.assert_called_once()
        call_args = mock_sqs_client.send_message.call_args[1]
        message_body = json.loads(call_args["MessageBody"])
        assert message_body["success"] is False
        assert "error" in message_body
        assert "Invalid URL format" in message_body["error"]


@pytest.mark.asyncio
async def test_process_message_with_temp_file_creation_error(sample_message, mock_sqs_client):
    """Test handling of temporary file creation errors."""
    with patch("tempfile.NamedTemporaryFile") as mock_temp:
        # Mock tempfile to raise an error
        mock_temp.side_effect = OSError("No space left on device")
        
        # Execute
        await process_message(sample_message)
        
        # Verify error handling
        mock_sqs_client.send_message.assert_called_once()
        call_args = mock_sqs_client.send_message.call_args[1]
        message_body = json.loads(call_args["MessageBody"])
        assert message_body["success"] is False
        assert "error" in message_body
        assert "No space left on device" in message_body["error"]


@pytest.mark.asyncio
async def test_process_message_with_large_file(sample_message, mock_s3_client, mock_sqs_client):
    """Test handling of large audio files."""
    # Setup
    with patch("media_summarizer.workers.download_worker.download_audio") as mock_download:
        mock_download.return_value = None  # Just mock the download function
        
        with patch("tempfile.NamedTemporaryFile") as mock_temp:
            mock_temp_file = MagicMock()
            mock_temp_file.name = "/tmp/test_audio.mp3"
            mock_temp.return_value.__enter__.return_value = mock_temp_file
            
            # Mock os.path.getsize to return a large file size
            with patch("os.path.getsize") as mock_getsize:
                mock_getsize.return_value = 1024 * 1024 * 1024  # 1 GB
                
                # Mock os.unlink to prevent file not found error
                with patch("os.unlink") as mock_unlink:
                    # Execute
                    await process_message(sample_message)
                    
                    # Verify
                    mock_s3_client.upload_file.assert_called_once()
                    mock_sqs_client.send_message.assert_called_once()
                    
                    # Check the message sent to the next queue
                    call_args = mock_sqs_client.send_message.call_args[1]
                    message_body = json.loads(call_args["MessageBody"])
                    assert message_body["job_id"] == "test-job-id"
                    assert message_body["s3_audio_key"] == "audio/test-job-id.mp3"
                    assert message_body["success"] is True
                    # Verify file size is included in metadata
                    assert "metadata" in message_body
                    assert "file_size_bytes" in message_body["metadata"]
                    assert message_body["metadata"]["file_size_bytes"] == 1024 * 1024 * 1024