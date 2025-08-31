"""
Unit tests for the transcription worker.
Tests the actual functions that exist in the worker.
"""
import json
import os
import pytest
import pytest_asyncio
import asyncio
from unittest.mock import patch, MagicMock, AsyncMock, mock_open
from botocore.exceptions import ClientError
from io import BytesIO

# Set AWS credentials for testing
os.environ["AWS_ACCESS_KEY_ID"] = "test"
os.environ["AWS_SECRET_ACCESS_KEY"] = "test"
os.environ["AWS_DEFAULT_REGION"] = "us-east-1"
os.environ["AWS_ENDPOINT_URL"] = "http://localhost:4566"

from media_summarizer.workers.transcription.worker import (
    download_audio_file,
    upload_transcription,
    send_notification,
    send_to_summarization_queue,
    process_transcription_message,
    process_message,
)


class TestDownloadAudioFile:
    """Test cases for download_audio_file function."""

    @pytest.mark.asyncio
    async def test_download_audio_file_success(self):
        """Test successful audio file download."""
        # Setup
        audio_s3_key = "audio/test-episode.mp3"
        local_path = "/tmp/test_audio.mp3"

        with patch('media_summarizer.utils.s3.download_file') as mock_download:
            mock_download.return_value = None

            # Execute
            await download_audio_file(audio_s3_key, local_path)

            # Verify
            from os import getenv
            expected_bucket = getenv("AUDIO_BUCKET", "media-summarizer-audio")
            mock_download.assert_called_once_with(
                bucket=expected_bucket,
                key=audio_s3_key,
                file_path=local_path
            )

    @pytest.mark.asyncio
    async def test_download_audio_file_s3_error(self):
        """Test download with S3 error."""
        # Setup
        audio_s3_key = "audio/nonexistent.mp3"
        local_path = "/tmp/test_audio.mp3"

        with patch('media_summarizer.utils.s3.download_file') as mock_download:
            mock_download.side_effect = ClientError(
                {'Error': {'Code': 'NoSuchKey', 'Message': 'Key not found'}},
                'GetObject'
            )

            # Execute and verify
            with pytest.raises(ClientError) as exc_info:
                await download_audio_file(audio_s3_key, local_path)

            assert 'NoSuchKey' in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_download_audio_file_permission_error(self):
        """Test download with permission error."""
        # Setup
        audio_s3_key = "audio/restricted.mp3"
        local_path = "/tmp/test_audio.mp3"

        with patch('media_summarizer.utils.s3.download_file') as mock_download:
            mock_download.side_effect = ClientError(
                {'Error': {'Code': 'AccessDenied', 'Message': 'Access denied'}},
                'GetObject'
            )

            # Execute and verify
            with pytest.raises(ClientError) as exc_info:
                await download_audio_file(audio_s3_key, local_path)

            assert 'AccessDenied' in str(exc_info.value)


class TestUploadTranscription:
    """Test cases for upload_transcription function."""

    @pytest.mark.asyncio
    async def test_upload_transcription_success(self):
        """Test successful transcription upload."""
        # Setup
        transcript_s3_key = "transcripts/test-job-123.txt"
        transcription_text = "This is a test transcription."

        with patch('media_summarizer.utils.s3.upload_file_object') as mock_upload:
            mock_upload.return_value = None

            # Execute
            await upload_transcription(transcript_s3_key, transcription_text)

            # Verify
            mock_upload.assert_called_once()
            call_args = mock_upload.call_args

            from os import getenv
            expected_transcript_bucket = getenv("TRANSCRIPT_BUCKET", "media-summarizer-transcriptions")
            assert call_args[1]['bucket'] == expected_transcript_bucket
            assert call_args[1]['key'] == transcript_s3_key

            # Check that the file object contains the transcription
            uploaded_content = call_args[1]['file_obj'].read()
            if isinstance(uploaded_content, bytes):
                uploaded_content = uploaded_content.decode('utf-8')
            assert transcription_text in uploaded_content

    @pytest.mark.asyncio
    async def test_upload_transcription_unicode(self):
        """Test transcription upload with Unicode content."""
        # Setup
        transcript_s3_key = "transcripts/unicode-test.txt"
        transcription_text = "Test with Unicode: こんにちは世界 🚀"

        with patch('media_summarizer.utils.s3.upload_file_object') as mock_upload:
            mock_upload.return_value = None

            # Execute
            await upload_transcription(transcript_s3_key, transcription_text)

            # Verify
            mock_upload.assert_called_once()
            call_args = mock_upload.call_args

            # Check Unicode handling
            uploaded_content = call_args[1]['file_obj'].read()
            if isinstance(uploaded_content, bytes):
                uploaded_content = uploaded_content.decode('utf-8')
            assert "こんにちは世界" in uploaded_content
            assert "🚀" in uploaded_content

    @pytest.mark.asyncio
    async def test_upload_transcription_s3_error(self):
        """Test transcription upload with S3 error."""
        # Setup
        transcript_s3_key = "transcripts/test.txt"
        transcription_text = "Test transcription"

        with patch('media_summarizer.utils.s3.upload_file_object') as mock_upload:
            mock_upload.side_effect = ClientError(
                {'Error': {'Code': 'AccessDenied', 'Message': 'Access denied'}},
                'PutObject'
            )

            # Execute and verify
            with pytest.raises(ClientError) as exc_info:
                await upload_transcription(transcript_s3_key, transcription_text)

            assert 'AccessDenied' in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_upload_transcription_empty_content(self):
        """Test transcription upload with empty content."""
        # Setup
        transcript_s3_key = "transcripts/empty.txt"
        transcription_text = ""

        with patch('media_summarizer.utils.s3.upload_file_object') as mock_upload:
            mock_upload.return_value = None

            # Execute
            await upload_transcription(transcript_s3_key, transcription_text)

            # Verify
            mock_upload.assert_called_once()


class TestSendNotification:
    """Test cases for send_notification function."""

    @pytest.mark.asyncio
    async def test_send_notification_success(self):
        """Test successful notification sending."""
        # Setup
        notification_type = "completion"
        job_id = "test-job-123"
        email = "user@example.com"
        kwargs = {"podcast_title": "Test Podcast"}

        with patch('media_summarizer.utils.sqs.send_message') as mock_send:
            mock_send.return_value = {"MessageId": "test-message-id"}

            # Execute
            await send_notification(notification_type, job_id, email, **kwargs)

            # Verify
            mock_send.assert_called_once()
            call_args = mock_send.call_args

            assert call_args[1]['queue_name'] == "email-notification-queue"

            message_body = call_args[1]['message_body']
            assert message_body['notification_type'] == notification_type
            assert message_body['job_id'] == job_id
            assert message_body['email'] == email
            assert message_body['podcast_title'] == "Test Podcast"

    @pytest.mark.asyncio
    async def test_send_notification_error_type(self):
        """Test sending error notification."""
        # Setup
        notification_type = "error"
        job_id = "test-job-123"
        email = "user@example.com"
        kwargs = {"error_message": "Processing failed", "step": "transcription"}

        with patch('media_summarizer.utils.sqs.send_message') as mock_send:
            mock_send.return_value = {"MessageId": "test-message-id"}

            # Execute
            await send_notification(notification_type, job_id, email, **kwargs)

            # Verify
            mock_send.assert_called_once()
            call_args = mock_send.call_args

            message_body = call_args[1]['message_body']
            assert message_body['notification_type'] == "error"
            assert message_body['error_message'] == "Processing failed"
            assert message_body['step'] == "transcription"

    @pytest.mark.asyncio
    async def test_send_notification_sqs_error(self):
        """Test notification sending with SQS error."""
        # Setup
        notification_type = "completion"
        job_id = "test-job-123"
        email = "user@example.com"

        with patch('media_summarizer.utils.sqs.send_message') as mock_send:
            mock_send.side_effect = ClientError(
                {'Error': {'Code': 'AWS.SimpleQueueService.NonExistentQueue'}},
                'SendMessage'
            )

            # Execute and verify
            with pytest.raises(ClientError) as exc_info:
                await send_notification(notification_type, job_id, email)

            assert 'NonExistentQueue' in str(exc_info.value)


class TestSendToSummarizationQueue:
    """Test cases for send_to_summarization_queue function."""

    @pytest.mark.asyncio
    async def test_send_to_summarization_queue_success(self):
        """Test successful message sending to summarization queue."""
        # Setup
        job_id = "test-job-123"
        transcript_s3_key = "transcripts/test-job-123.txt"
        email = "user@example.com"
        kwargs = {"podcast_title": "Test Podcast", "episode_title": "Test Episode"}

        with patch('media_summarizer.utils.sqs.send_message') as mock_send:
            mock_send.return_value = {"MessageId": "test-message-id"}

            # Execute
            await send_to_summarization_queue(job_id, transcript_s3_key, email, **kwargs)

            # Verify
            mock_send.assert_called_once()
            call_args = mock_send.call_args

            assert call_args[1]['queue_name'] == "summarization-queue"

            message_body = call_args[1]['message_body']
            assert message_body['job_id'] == job_id
            assert message_body['transcript_s3_key'] == transcript_s3_key
            assert message_body['email'] == email
            assert message_body['podcast_title'] == "Test Podcast"
            assert message_body['episode_title'] == "Test Episode"

    @pytest.mark.asyncio
    async def test_send_to_summarization_queue_minimal(self):
        """Test sending to summarization queue with minimal parameters."""
        # Setup
        job_id = "test-job-123"
        transcript_s3_key = "transcripts/test-job-123.txt"
        email = "user@example.com"

        with patch('media_summarizer.utils.sqs.send_message') as mock_send:
            mock_send.return_value = {"MessageId": "test-message-id"}

            # Execute
            await send_to_summarization_queue(job_id, transcript_s3_key, email)

            # Verify
            mock_send.assert_called_once()
            call_args = mock_send.call_args

            message_body = call_args[1]['message_body']
            assert message_body['job_id'] == job_id
            assert message_body['transcript_s3_key'] == transcript_s3_key
            assert message_body['email'] == email

    @pytest.mark.asyncio
    async def test_send_to_summarization_queue_error(self):
        """Test sending to summarization queue with error."""
        # Setup
        job_id = "test-job-123"
        transcript_s3_key = "transcripts/test-job-123.txt"
        email = "user@example.com"

        with patch('media_summarizer.utils.sqs.send_message') as mock_send:
            mock_send.side_effect = ClientError(
                {'Error': {'Code': 'AccessDenied'}},
                'SendMessage'
            )

            # Execute and verify
            with pytest.raises(ClientError):
                await send_to_summarization_queue(job_id, transcript_s3_key, email)


class TestProcessTranscriptionMessage:
    """Test cases for process_transcription_message function."""

    @pytest.mark.asyncio
    async def test_process_transcription_message_success(self):
        """Test successful transcription message processing."""
        # Setup
        message_body = {
            "job_id": "test-job-123",
            "audio_s3_key": "audio/test.mp3",
            "email": "user@example.com",
            "podcast_title": "Test Podcast",
            "episode_title": "Test Episode"
        }

        with patch('media_summarizer.workers.transcription.worker.download_audio_file') as mock_download:
            with patch('media_summarizer.workers.transcription.worker.upload_transcription') as mock_upload:
                with patch('media_summarizer.workers.transcription.worker.send_to_summarization_queue') as mock_send_summ:
                    with patch('media_summarizer.workers.transcription.worker.send_notification') as mock_send_notif:
                        with patch('media_summarizer.workers.transcription.worker.transcribe_async') as mock_transcribe:
                            with patch('os.path.exists') as mock_exists:
                                with patch('pathlib.Path.stat') as mock_stat:
                                    with patch('media_summarizer.utils.database_async.get_processing_job_by_id') as mock_get_job:
                                        with patch('media_summarizer.utils.database_async.update_processing_job') as mock_update_job:

                                            # Setup mocks
                                            mock_exists.return_value = True
                                            mock_stat.return_value.st_size = 1000  # Non-zero file size
                                            mock_transcribe.return_value = {
                                                "text": "Test transcription",
                                                "segments": [],
                                                "language": "en"
                                            }
                                            mock_get_job.return_value = MagicMock()
                                            mock_update_job.return_value = None

                                            # Execute
                                            await process_transcription_message(message_body)

                                            # Verify
                                            mock_download.assert_called_once()
                                            mock_upload.assert_called_once()
                                            mock_send_summ.assert_called_once()
                                            mock_transcribe.assert_called_once()

    @pytest.mark.asyncio
    async def test_process_transcription_message_download_error(self):
        """Test transcription processing with download error."""
        # Setup
        message_body = {
            "job_id": "test-job-123",
            "audio_s3_key": "audio/nonexistent.mp3",
            "email": "user@example.com"
        }

        with patch('media_summarizer.workers.transcription.worker.download_audio_file') as mock_download:
            with patch('media_summarizer.workers.transcription.worker.send_notification') as mock_send_notif:
                with patch('media_summarizer.utils.database_async.get_processing_job_by_id') as mock_get_job:
                    with patch('media_summarizer.utils.database_async.update_processing_job') as mock_update_job:

                        # Setup mocks
                        mock_download.side_effect = ClientError(
                            {'Error': {'Code': 'NoSuchKey'}},
                            'GetObject'
                        )
                        mock_get_job.return_value = MagicMock()
                        mock_update_job.return_value = None

                        # Execute - should raise exception
                        with pytest.raises(ClientError):
                            await process_transcription_message(message_body)

                        # Verify error notification was sent
                        mock_send_notif.assert_called_once()
                        call_args = mock_send_notif.call_args
                        assert call_args.kwargs["notification_type"] == "error"

    @pytest.mark.asyncio
    async def test_process_transcription_message_whisper_error(self):
        """Test transcription processing with Whisper error."""
        # Setup
        message_body = {
            "job_id": "test-job-123",
            "audio_s3_key": "audio/test.mp3",
            "email": "user@example.com"
        }

        with patch('media_summarizer.workers.transcription.worker.download_audio_file') as mock_download:
            with patch('media_summarizer.workers.transcription.worker.send_notification') as mock_send_notif:
                with patch('media_summarizer.workers.transcription.worker.transcribe_async') as mock_transcribe:
                    with patch('os.path.exists') as mock_exists:
                        with patch('pathlib.Path.stat') as mock_stat:
                            with patch('media_summarizer.utils.database_async.get_processing_job_by_id') as mock_get_job:
                                with patch('media_summarizer.utils.database_async.update_processing_job') as mock_update_job:

                                    # Setup mocks
                                    mock_exists.return_value = True
                                    mock_stat.return_value.st_size = 1000  # Non-zero file size
                                    mock_transcribe.side_effect = Exception("Whisper processing failed")
                                    mock_get_job.return_value = MagicMock()
                                    mock_update_job.return_value = None

                                    # Execute - should raise exception
                                    with pytest.raises(Exception):
                                        await process_transcription_message(message_body)

                                    # Verify error notification was sent
                                    mock_send_notif.assert_called_once()
                                    call_args = mock_send_notif.call_args
                                    assert call_args.kwargs["notification_type"] == "error"

    @pytest.mark.asyncio
    async def test_process_transcription_message_missing_fields(self):
        """Test transcription processing with missing required fields."""
        # Setup
        message_body = {
            "job_id": "test-job-123"
            # Missing audio_s3_key and email
        }

        # Execute - should raise ValueError
        with pytest.raises(ValueError, match="Missing required fields"):
            await process_transcription_message(message_body)


class TestProcessMessage:
    """Test cases for process_message function."""

    @pytest.mark.asyncio
    async def test_process_message_starts_heartbeat_and_extends_visibility(self, monkeypatch):
        # Prepare message
        message = {
            "Body": json.dumps({
                "job_id": "test-job-123",
                "audio_s3_key": "audio/test.mp3",
                "email": "user@example.com"
            }),
            "ReceiptHandle": "test-receipt-handle"
        }

        # Speed up heartbeat for test
        import media_summarizer.workers.transcription.worker as worker_mod
        monkeypatch.setattr(worker_mod, "HEARTBEAT_INTERVAL", 0.01, raising=False)
        monkeypatch.setattr(worker_mod, "TRANSCRIPTION_VISIBILITY_TIMEOUT", 10, raising=False)

        # Mock visibility change and processing
        calls = {"count": 0}

        async def fake_change_visibility(queue_name, receipt_handle, timeout_seconds):
            calls["count"] += 1
            assert queue_name == worker_mod.TRANSCRIPTION_QUEUE
            assert receipt_handle == message["ReceiptHandle"]
            assert timeout_seconds == worker_mod.TRANSCRIPTION_VISIBILITY_TIMEOUT
            return {}

        async def fake_process(body):
            # simulate short processing with small sleep to allow at least one heartbeat tick
            await asyncio.sleep(0.03)

        monkeypatch.setattr('media_summarizer.utils.sqs.change_message_visibility', fake_change_visibility)
        monkeypatch.setattr('media_summarizer.workers.transcription.worker.process_transcription_message', fake_process)

        # Execute
        await worker_mod.process_message(message)

        # Verify at least one change call (immediate) occurred
        assert calls["count"] >= 1

    @pytest.mark.asyncio
    async def test_process_message_heartbeat_handles_errors(self, monkeypatch):
        message = {
            "Body": json.dumps({
                "job_id": "test-job-123",
                "audio_s3_key": "audio/test.mp3",
                "email": "user@example.com"
            }),
            "ReceiptHandle": "test-receipt-handle"
        }

        import media_summarizer.workers.transcription.worker as worker_mod
        monkeypatch.setattr(worker_mod, "HEARTBEAT_INTERVAL", 0.01, raising=False)
        monkeypatch.setattr(worker_mod, "TRANSCRIPTION_VISIBILITY_TIMEOUT", 10, raising=False)

        # First call succeeds, then raise once, then succeed
        seq = iter([None, Exception("temp error"), None])

        async def flaky_change_visibility(queue_name, receipt_handle, timeout_seconds):
            v = next(seq, None)
            if isinstance(v, Exception):
                raise v
            return {}

        async def fake_process(body):
            await asyncio.sleep(0.04)

        monkeypatch.setattr('media_summarizer.utils.sqs.change_message_visibility', flaky_change_visibility)
        monkeypatch.setattr('media_summarizer.workers.transcription.worker.process_transcription_message', fake_process)

        # Should not raise despite heartbeat transient error
        await worker_mod.process_message(message)

    @pytest.mark.asyncio
    async def test_process_message_success(self):
        """Test successful message processing."""
        # Setup
        message = {
            "Body": json.dumps({
                "job_id": "test-job-123",
                "audio_s3_key": "audio/test.mp3",
                "email": "user@example.com"
            }),
            "ReceiptHandle": "test-receipt-handle"
        }

        with patch('media_summarizer.workers.transcription.worker.process_transcription_message') as mock_process:

            # Execute
            await process_message(message)

            # Verify
            mock_process.assert_called_once()

    @pytest.mark.asyncio
    async def test_process_message_invalid_json(self):
        """Test message processing with invalid JSON."""
        # Setup
        message = {
            "Body": "invalid json content",
            "ReceiptHandle": "test-receipt-handle"
        }

        # Execute - should raise JSONDecodeError
        with pytest.raises(json.JSONDecodeError):
            await process_message(message)

    @pytest.mark.asyncio
    async def test_process_message_processing_error(self):
        """Test message processing when transcription processing fails."""
        # Setup
        message = {
            "Body": json.dumps({
                "job_id": "test-job-123",
                "audio_s3_key": "audio/test.mp3",
                "email": "user@example.com"
            }),
            "ReceiptHandle": "test-receipt-handle"
        }

        with patch('media_summarizer.workers.transcription.worker.process_transcription_message') as mock_process:

            # Setup processing to fail
            mock_process.side_effect = Exception("Processing failed")

            # Execute - should raise exception
            with pytest.raises(Exception, match="Processing failed"):
                await process_message(message)

    @pytest.mark.asyncio
    async def test_process_message_delete_error(self):
        """Test message processing when delete fails."""
        # Setup
        message = {
            "Body": json.dumps({
                "job_id": "test-job-123",
                "audio_s3_key": "audio/test.mp3",
                "email": "user@example.com"
            }),
            "ReceiptHandle": "test-receipt-handle"
        }

        with patch('media_summarizer.workers.transcription.worker.process_transcription_message') as mock_process:
            with patch('media_summarizer.utils.sqs.delete_message') as mock_delete:

                # Setup delete to fail
                mock_delete.side_effect = ClientError(
                    {'Error': {'Code': 'ReceiptHandleIsInvalid'}},
                    'DeleteMessage'
                )

                # Execute - should not raise exception
                await process_message(message)

                # Verify processing still happened
                mock_process.assert_called_once()

    @pytest.mark.asyncio
    async def test_process_message_empty_body(self):
        """Test message processing with empty body."""
        # Setup
        message = {
            "Body": "",
            "ReceiptHandle": "test-receipt-handle"
        }

        # Execute - should raise JSONDecodeError
        with pytest.raises(json.JSONDecodeError):
            await process_message(message)
