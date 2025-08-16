"""
Unit tests for the email notification worker.
Tests the actual functions that exist in the worker.
"""
import json
import os
import pytest
import pytest_asyncio
import asyncio
from unittest.mock import patch, MagicMock, AsyncMock
from botocore.exceptions import ClientError

# Set AWS credentials for testing
os.environ["AWS_ACCESS_KEY_ID"] = "test"
os.environ["AWS_SECRET_ACCESS_KEY"] = "test"
os.environ["AWS_DEFAULT_REGION"] = "us-east-1"
os.environ["AWS_ENDPOINT_URL"] = "http://localhost:4566"

from media_summarizer.workers.notification.email_worker import (
    send_error_notification,
    send_completion_notification,
    process_message,
)




class TestSendErrorNotification:
    """Test cases for send_error_notification function."""

    @pytest.mark.asyncio
    async def test_send_error_notification_success(self):
        """Test successful error notification sending."""
        # Setup
        recipient = "user@example.com"
        job_id = "test-job-123"
        error_message = "Transcription failed: Invalid audio format"
        step = "transcription"

        with patch('media_summarizer.utils.ses.send_email') as mock_send:
            mock_send.return_value = {"MessageId": "test-message-id"}

            # Execute
            result = await send_error_notification(recipient, job_id, error_message, step)

            # Verify
            mock_send.assert_called_once()
            call_args = mock_send.call_args

            assert call_args[1]['recipient'] == recipient
            assert "error" in call_args[1]['subject'].lower()
            assert job_id in call_args[1]['body_text']
            assert error_message in call_args[1]['body_text']
            assert step in call_args[1]['body_text']
            assert result["MessageId"] == "test-message-id"

    @pytest.mark.asyncio
    async def test_send_error_notification_without_step(self):
        """Test error notification without step parameter."""
        # Setup
        recipient = "user@example.com"
        job_id = "test-job-123"
        error_message = "Unknown error occurred"

        with patch('media_summarizer.utils.ses.send_email') as mock_send:
            mock_send.return_value = {"MessageId": "test-message-id"}

            # Execute
            result = await send_error_notification(recipient, job_id, error_message)

            # Verify
            mock_send.assert_called_once()
            call_args = mock_send.call_args

            assert call_args[1]['recipient'] == recipient
            assert error_message in call_args[1]['body_text']
            assert result["MessageId"] == "test-message-id"

    @pytest.mark.asyncio
    async def test_send_error_notification_long_error(self):
        """Test error notification with very long error message."""
        # Setup
        recipient = "user@example.com"
        job_id = "test-job-123"
        long_error = "Very long error message with stack trace: " + "Error details\n" * 50
        step = "summarization"

        with patch('media_summarizer.utils.ses.send_email') as mock_send:
            mock_send.return_value = {"MessageId": "test-message-id"}

            # Execute
            result = await send_error_notification(recipient, job_id, long_error, step)

            # Verify
            mock_send.assert_called_once()
            call_args = mock_send.call_args
            assert long_error in call_args[1]['body_text']


class TestSendCompletionNotification:
    """Test cases for send_completion_notification function."""

    @pytest.mark.asyncio
    async def test_send_completion_notification_success(self):
        """Test successful completion notification sending."""
        # Setup
        recipient = "user@example.com"
        job_id = "test-job-123"
        podcast_title = "Test Podcast"
        episode_title = "Test Episode"
        summary_content = {
            "main_topics": ["Topic 1", "Topic 2"],
            "key_points": ["Point 1", "Point 2"],
            "notable_quotes": ["Quote 1"],
            "conclusion": "Test conclusion"
        }

        with patch('media_summarizer.utils.ses.send_email') as mock_send:
            mock_send.return_value = {"MessageId": "test-message-id"}

            # Execute
            result = await send_completion_notification(recipient, job_id, podcast_title, episode_title, summary_content)

            # Verify
            mock_send.assert_called_once()
            call_args = mock_send.call_args

            assert call_args[1]['recipient'] == recipient
            assert "ready" in call_args[1]['subject'].lower() or "summary" in call_args[1]['subject'].lower()
            assert job_id in call_args[1]['body_text']
            assert podcast_title in call_args[1]['body_text']
            assert episode_title in call_args[1]['body_text']
            assert "Topic 1" in call_args[1]['body_text']
            assert "Point 1" in call_args[1]['body_text']
            assert result["MessageId"] == "test-message-id"

    @pytest.mark.asyncio
    async def test_send_completion_notification_minimal(self):
        """Test completion notification with minimal parameters."""
        # Setup
        recipient = "user@example.com"
        job_id = "test-job-123"

        with patch('media_summarizer.utils.ses.send_email') as mock_send:
            mock_send.return_value = {"MessageId": "test-message-id"}

            # Execute
            result = await send_completion_notification(recipient, job_id)

            # Verify
            mock_send.assert_called_once()
            call_args = mock_send.call_args

            assert call_args[1]['recipient'] == recipient
            assert job_id in call_args[1]['body_text']
            assert result["MessageId"] == "test-message-id"

    @pytest.mark.asyncio
    async def test_send_completion_notification_with_string_summary(self):
        """Test completion notification with string summary content."""
        # Setup
        recipient = "user@example.com"
        job_id = "test-job-123"
        podcast_title = "Test Podcast"
        episode_title = "Test Episode"
        summary_content = "This is a plain text summary of the podcast episode."

        with patch('media_summarizer.utils.ses.send_email') as mock_send:
            mock_send.return_value = {"MessageId": "test-message-id"}

            # Execute
            result = await send_completion_notification(recipient, job_id, podcast_title, episode_title, summary_content)

            # Verify - should still work with string summary
            mock_send.assert_called_once()
            call_args = mock_send.call_args
            assert summary_content in call_args[1]['body_text']
            assert result["MessageId"] == "test-message-id"


class TestProcessMessage:
    """Test cases for process_message function."""

    @pytest.mark.asyncio
    async def test_process_message_error(self):
        """Test processing error message."""
        # Setup
        message = {
            "Body": json.dumps({
                "notification_type": "error",
                "job_id": "test-job-123",
                "email": "user@example.com",
                "error": "Processing failed",
                "step": "transcription"
            })
        }

        with patch('media_summarizer.workers.notification.email_worker.send_error_notification') as mock_send:
            with patch('media_summarizer.utils.sqs.delete_message') as mock_delete:
                mock_send.return_value = {"MessageId": "test-message-id"}

                # Execute
                await process_message(message)

                # Verify
                mock_send.assert_called_once_with(
                    "user@example.com", "test-job-123", "Processing failed", "transcription"
                )
                mock_delete.assert_called_once()

    @pytest.mark.asyncio
    async def test_process_message_completion(self):
        """Test processing completion message."""
        # Setup
        message = {
            "Body": json.dumps({
                "notification_type": "completion",
                "job_id": "test-job-123",
                "email": "user@example.com",
                "podcast_title": "Test Podcast",
                "episode_title": "Test Episode",
                "summary_content": {
                    "main_topics": ["Topic 1"],
                    "key_points": ["Point 1"],
                    "conclusion": "Test conclusion"
                }
            })
        }

        with patch('media_summarizer.workers.notification.email_worker.send_completion_notification') as mock_send:
            with patch('media_summarizer.utils.sqs.delete_message') as mock_delete:
                mock_send.return_value = {"MessageId": "test-message-id"}

                # Execute
                await process_message(message)

                # Verify
                mock_send.assert_called_once_with(
                    "user@example.com", "test-job-123", "Test Podcast", "Test Episode", {
                        "main_topics": ["Topic 1"],
                        "key_points": ["Point 1"],
                        "conclusion": "Test conclusion"
                    }
                )
                mock_delete.assert_called_once()

    @pytest.mark.asyncio
    async def test_process_message_invalid_json(self):
        """Test processing message with invalid JSON."""
        # Setup
        message = {
            "Body": "invalid json"
        }

        with patch('media_summarizer.utils.sqs.delete_message') as mock_delete:
            # Execute
            await process_message(message)

            # Verify - message should NOT be deleted for invalid JSON
            mock_delete.assert_not_called()

    @pytest.mark.asyncio
    async def test_process_message_unknown_notification_type(self):
        """Test processing message with unknown notification type."""
        # Setup
        message = {
            "Body": json.dumps({
                "notification_type": "unknown_type",
                "job_id": "test-job-123",
                "email": "user@example.com"
            })
        }

        with patch('media_summarizer.utils.sqs.delete_message') as mock_delete:
            # Execute
            await process_message(message)

            # Verify - message should NOT be deleted for unknown type
            mock_delete.assert_not_called()

    @pytest.mark.asyncio
    async def test_process_message_missing_fields(self):
        """Test processing message with missing required fields."""
        # Setup
        message = {
            "Body": json.dumps({
                "notification_type": "error"
                # Missing job_id and email
            })
        }

        with patch('media_summarizer.utils.sqs.delete_message') as mock_delete:
            # Execute
            await process_message(message)

            # Verify - message should NOT be deleted for missing fields
            mock_delete.assert_not_called()

    @pytest.mark.asyncio
    async def test_process_message_send_error_with_retry(self):
        """Test processing message when sending fails."""
        # Setup
        message = {
            "Body": json.dumps({
                "notification_type": "error",
                "job_id": "test-job-123",
                "email": "user@example.com",
                "error": "Test error"
            }),
            "ReceiptHandle": "test-receipt-handle"
        }

        with patch('media_summarizer.workers.notification.email_worker.send_error_notification') as mock_send:
            with patch('media_summarizer.utils.sqs.delete_message') as mock_delete:
                with patch('asyncio.sleep') as mock_sleep:
                    # First call fails, second succeeds
                    mock_send.side_effect = [
                        ClientError({'Error': {'Code': 'Throttling'}}, 'SendEmail'),
                        {"MessageId": "test-message-id"}
                    ]

                    # Execute
                    await process_message(message)

                    # Verify retry behavior
                    assert mock_send.call_count == 2
                    assert mock_sleep.call_count == 1
                    mock_delete.assert_called_once()
