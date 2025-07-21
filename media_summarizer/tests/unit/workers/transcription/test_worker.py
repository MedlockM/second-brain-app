"""
Unit tests for the transcription worker module.
"""
import json
import os
import pytest
import pytest_asyncio
import asyncio
from unittest.mock import MagicMock, patch, AsyncMock

# Mock the whisper module before importing the worker
import sys
whisper_mock = MagicMock()
whisper_mock.load_model.return_value.transcribe.return_value = {"text": "This is a test transcription."}
sys.modules['whisper'] = whisper_mock

# Set AWS credentials for testing
os.environ["AWS_ACCESS_KEY_ID"] = "test"
os.environ["AWS_SECRET_ACCESS_KEY"] = "test"
os.environ["AWS_DEFAULT_REGION"] = "us-east-1"
os.environ["AWS_ENDPOINT_URL"] = "http://localhost:4566"

from media_summarizer.workers.transcription.worker import (
    download_audio_file,
    upload_transcript,
    send_sqs_message,
    process_message,
    get_queue_url,
)


@pytest.fixture
def mock_s3_client():
    """Mock S3 client for testing."""
    with patch("media_summarizer.workers.transcription.worker.session") as mock_session:
        mock_client = AsyncMock()
        mock_session.client.return_value.__aenter__.return_value = mock_client
        yield mock_client


@pytest.fixture
def mock_sqs_client():
    """Mock SQS client for testing."""
    with patch("media_summarizer.workers.transcription.worker.session") as mock_session:
        mock_client = AsyncMock()
        mock_session.client.return_value.__aenter__.return_value = mock_client
        yield mock_client


@pytest.fixture
def mock_whisper():
    """Mock Whisper model for testing."""
    with patch("whisper.load_model") as mock_load_model:
        mock_model = MagicMock()
        mock_model.transcribe.return_value = {"text": "This is a test transcription."}
        mock_load_model.return_value = mock_model
        yield mock_model


@pytest.fixture
def sample_message():
    """Create a sample SQS message for testing."""
    return {
        "MessageId": "test-message-id",
        "ReceiptHandle": "test-receipt-handle",
        "Body": json.dumps({
            "job_id": "test-job-id",
            "s3_audio_key": "audio/test-job-id.mp3",
            "bucket_name": "test-bucket",
            "success": True
        })
    }


@pytest.mark.asyncio
async def test_download_audio_file():
    """Test downloading an audio file from S3."""
    # Setup
    bucket = "test-bucket"
    key = "test-key.mp3"
    
    with patch("tempfile.NamedTemporaryFile") as mock_temp:
        mock_temp.return_value.__enter__.return_value.name = "/tmp/test_audio.mp3"
        
        with patch("media_summarizer.workers.transcription.worker.session") as mock_session:
            mock_client = AsyncMock()
            mock_session.client.return_value.__aenter__.return_value = mock_client
            
            # Execute
            result = await download_audio_file(bucket, key)
            
            # Verify
            mock_client.download_file.assert_called_once_with(bucket, key, "/tmp/test_audio.mp3")
            assert result == "/tmp/test_audio.mp3"


@pytest.mark.asyncio
async def test_upload_transcript():
    """Test uploading a transcript to S3."""
    # Setup
    bucket = "test-bucket"
    key = "test-key.txt"
    transcript = "This is a test transcript."
    
    with patch("media_summarizer.workers.transcription.worker.session") as mock_session:
        mock_client = AsyncMock()
        mock_session.client.return_value.__aenter__.return_value = mock_client
        
        # Execute
        await upload_transcript(bucket, key, transcript)
        
        # Verify
        mock_client.put_object.assert_called_once()
        call_args = mock_client.put_object.call_args[1]
        assert call_args["Bucket"] == bucket
        assert call_args["Key"] == key
        assert call_args["Body"] == transcript.encode("utf-8")


@pytest.mark.asyncio
async def test_send_sqs_message():
    """Test sending a message to SQS."""
    # Setup
    queue_name = "test-queue"
    message = {"job_id": "test-job-id", "status": "complete"}
    
    with patch("media_summarizer.workers.transcription.worker.session") as mock_session:
        mock_client = AsyncMock()
        mock_session.client.return_value.__aenter__.return_value = mock_client
        
        # Execute
        await send_sqs_message(queue_name, message)
        
        # Verify
        mock_client.send_message.assert_called_once()
        call_args = mock_client.send_message.call_args[1]
        assert json.loads(call_args["MessageBody"]) == message


@pytest.mark.asyncio
async def test_process_message_success(sample_message):
    """Test successful processing of a message."""
    # Setup
    with patch("media_summarizer.workers.transcription.worker.download_audio_file") as mock_download:
        # Mock the download to return a file path
        mock_download.return_value = "/tmp/test_audio.mp3"
        
        with patch("media_summarizer.workers.transcription.worker.model") as mock_model:
            # Mock the transcribe method
            mock_model.transcribe.return_value = {"text": "This is a test transcription."}
            
            with patch("media_summarizer.workers.transcription.worker.upload_transcript") as mock_upload:
                with patch("media_summarizer.workers.transcription.worker.send_sqs_message") as mock_send:
                    # Execute
                    await process_message(sample_message)
                    
                    # Verify
                    mock_model.transcribe.assert_called_once_with("/tmp/test_audio.mp3")
                    mock_upload.assert_called_once()
                    mock_send.assert_called_once()


@pytest.mark.asyncio
async def test_process_message_retry_on_failure(sample_message):
    """Test that process_message retries on failure."""
    # Setup
    with patch("media_summarizer.workers.transcription.worker.download_audio_file") as mock_download:
        mock_download.side_effect = [Exception("Test error"), "test_path"]
        with patch("media_summarizer.workers.transcription.worker.upload_transcript"):
            with patch("media_summarizer.workers.transcription.worker.send_sqs_message"):
                with patch("asyncio.sleep") as mock_sleep:
                    with patch("media_summarizer.workers.transcription.worker.model") as mock_model:
                        mock_model.transcribe.return_value = {"text": "This is a test transcription."}
                        
                        # Execute
                        await process_message(sample_message)
                        
                        # Verify
                        assert mock_download.call_count == 2
                        mock_sleep.assert_called_once()


@pytest.mark.asyncio
async def test_process_message_max_retries_exceeded(sample_message):
    """Test that process_message sends error notification after max retries."""
    # Setup
    with patch("media_summarizer.workers.transcription.worker.download_audio_file") as mock_download:
        mock_download.side_effect = Exception("Test error")
        with patch("media_summarizer.workers.transcription.worker.send_sqs_message") as mock_send:
            with patch("asyncio.sleep"):
                # Execute
                await process_message(sample_message)
                
                # Verify
                assert mock_download.call_count > 1
                mock_send.assert_called_once()
                call_args = mock_send.call_args[0]
                assert call_args[0] == "email-notification-queue"
                assert call_args[1]["error"] == "Test error"


def test_get_queue_url():
    """Test the get_queue_url function."""
    # Test with AWS_ENDPOINT_URL set
    with patch("media_summarizer.workers.transcription.worker.AWS_ENDPOINT_URL", "http://localhost:4566"):
        url = get_queue_url("test-queue")
        assert url == "http://localhost:4566/000000000000/test-queue"
    
    # Test without AWS_ENDPOINT_URL
    with patch("media_summarizer.workers.transcription.worker.AWS_ENDPOINT_URL", None):
        url = get_queue_url("test-queue")
        assert url == "test-queue"