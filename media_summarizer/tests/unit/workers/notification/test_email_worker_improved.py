"""
Improved unit tests for the email notification worker with better edge case coverage.
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
    send_email,
    send_confirmation_email,
    send_error_notification,
    send_completion_notification,
    process_message,
    get_queue_url,
)


@pytest.fixture
def mock_ses_client():
    """Mock SES client for testing."""
    mock_client = AsyncMock()
    mock_client.send_email = AsyncMock(return_value={"MessageId": "test-message-id"})
    return mock_client


@pytest.fixture
def mock_sqs_client():
    """Mock SQS client for testing."""
    mock_client = AsyncMock()
    mock_client.delete_message = AsyncMock()
    return mock_client


@pytest.fixture
def confirmation_message():
    """Create a sample confirmation message."""
    return {
        "MessageId": "test-message-id",
        "ReceiptHandle": "test-receipt-handle",
        "Body": json.dumps({
            "job_id": "test-job-id",
            "email": "user@example.com",
            "notification_type": "confirmation",
            "podcast_title": "Test Podcast"
        })
    }


@pytest.fixture
def error_message():
    """Create a sample error message."""
    return {
        "MessageId": "test-message-id",
        "ReceiptHandle": "test-receipt-handle",
        "Body": json.dumps({
            "job_id": "test-job-id",
            "email": "user@example.com",
            "notification_type": "error",
            "error": "Test error message",
            "step": "transcription"
        })
    }


@pytest.fixture
def completion_message():
    """Create a sample completion message."""
    return {
        "MessageId": "test-message-id",
        "ReceiptHandle": "test-receipt-handle",
        "Body": json.dumps({
            "job_id": "test-job-id",
            "email": "user@example.com",
            "notification_type": "completion",
            "podcast_title": "Test Podcast",
            "summary_url": "https://example.com/summary/test-job-id"
        })
    }


@pytest.mark.asyncio
async def test_send_email_with_client_error(mock_ses_client):
    """Test handling of ClientError during email sending."""
    # Setup
    recipient = "user@example.com"
    subject = "Test Subject"
    body_text = "Test body text"
    
    # Configure mock to raise ClientError
    error_response = {"Error": {"Code": "MessageRejected", "Message": "Email address is not verified"}}
    mock_ses_client.send_email.side_effect = ClientError(error_response, "send_email")
    
    # Execute and verify
    with pytest.raises(ClientError) as excinfo:
        await send_email(recipient, subject, body_text, ses_client=mock_ses_client)
    
    assert "MessageRejected" in str(excinfo.value)
    assert "Email address is not verified" in str(excinfo.value)


@pytest.mark.asyncio
async def test_send_email_with_throttling_error(mock_ses_client):
    """Test handling of throttling errors during email sending."""
    # Setup
    recipient = "user@example.com"
    subject = "Test Subject"
    body_text = "Test body text"
    
    # Configure mock to raise throttling error
    error_response = {"Error": {"Code": "Throttling", "Message": "Rate exceeded"}}
    mock_ses_client.send_email.side_effect = ClientError(error_response, "send_email")
    
    # Execute and verify
    with pytest.raises(ClientError) as excinfo:
        await send_email(recipient, subject, body_text, ses_client=mock_ses_client)
    
    assert "Throttling" in str(excinfo.value)
    assert "Rate exceeded" in str(excinfo.value)


@pytest.mark.asyncio
async def test_send_email_with_invalid_email(mock_ses_client):
    """Test handling of invalid email address."""
    # Setup
    recipient = "invalid-email"  # Invalid email format
    subject = "Test Subject"
    body_text = "Test body text"
    
    # Configure mock to raise validation error
    error_response = {"Error": {"Code": "ValidationError", "Message": "Invalid email address"}}
    mock_ses_client.send_email.side_effect = ClientError(error_response, "send_email")
    
    # Execute and verify
    with pytest.raises(ClientError) as excinfo:
        await send_email(recipient, subject, body_text, ses_client=mock_ses_client)
    
    assert "ValidationError" in str(excinfo.value)
    assert "Invalid email address" in str(excinfo.value)


@pytest.mark.asyncio
async def test_send_email_with_empty_body():
    """Test sending an email with empty body."""
    # Setup
    recipient = "user@example.com"
    subject = "Test Subject"
    body_text = ""  # Empty body
    
    # Execute - Test with session creation
    with patch("media_summarizer.workers.notification.email_worker.session") as mock_session:
        mock_client = AsyncMock()
        mock_client.send_email = AsyncMock(return_value={"MessageId": "test-message-id"})
        mock_session.create_client.return_value.__aenter__.return_value = mock_client
        
        # Execute
        result = await send_email(recipient, subject, body_text)
        
        # Verify
        mock_client.send_email.assert_called_once()
        call_args = mock_client.send_email.call_args[1]
        
        assert call_args["Destination"]["ToAddresses"] == [recipient]
        assert call_args["Message"]["Subject"]["Data"] == subject
        assert call_args["Message"]["Body"]["Text"]["Data"] == ""  # Empty body
        assert result == {"MessageId": "test-message-id"}


@pytest.mark.asyncio
async def test_send_email_with_special_characters(mock_ses_client):
    """Test sending an email with special characters."""
    # Setup
    recipient = "user@example.com"
    subject = "Test Subject with Special Characters: !@#$%^&*()"
    body_text = "Test body text with special characters: !@#$%^&*()"
    body_html = "<p>Test body HTML with special characters: !@#$%^&*()</p>"
    
    # Execute
    result = await send_email(recipient, subject, body_text, body_html, ses_client=mock_ses_client)
    
    # Verify
    mock_ses_client.send_email.assert_called_once()
    call_args = mock_ses_client.send_email.call_args[1]
    
    assert call_args["Destination"]["ToAddresses"] == [recipient]
    assert call_args["Message"]["Subject"]["Data"] == subject
    assert call_args["Message"]["Body"]["Text"]["Data"] == body_text
    assert call_args["Message"]["Body"]["Html"]["Data"] == body_html
    assert result == {"MessageId": "test-message-id"}


@pytest.mark.asyncio
async def test_send_email_with_unicode_characters(mock_ses_client):
    """Test sending an email with unicode characters."""
    # Setup
    recipient = "user@example.com"
    subject = "Test Subject with Unicode: こんにちは世界"
    body_text = "Test body text with Unicode: こんにちは世界"
    body_html = "<p>Test body HTML with Unicode: こんにちは世界</p>"
    
    # Execute
    result = await send_email(recipient, subject, body_text, body_html, ses_client=mock_ses_client)
    
    # Verify
    mock_ses_client.send_email.assert_called_once()
    call_args = mock_ses_client.send_email.call_args[1]
    
    assert call_args["Destination"]["ToAddresses"] == [recipient]
    assert call_args["Message"]["Subject"]["Data"] == subject
    assert call_args["Message"]["Body"]["Text"]["Data"] == body_text
    assert call_args["Message"]["Body"]["Html"]["Data"] == body_html
    assert result == {"MessageId": "test-message-id"}


@pytest.mark.asyncio
async def test_send_email_with_multiple_recipients(mock_ses_client):
    """Test sending an email to multiple recipients."""
    # Setup
    recipients = ["user1@example.com", "user2@example.com"]
    subject = "Test Subject"
    body_text = "Test body text"
    
    # Execute - Test with multiple recipients
    for recipient in recipients:
        result = await send_email(recipient, subject, body_text, ses_client=mock_ses_client)
        
        # Verify
        call_args = mock_ses_client.send_email.call_args[1]
        assert call_args["Destination"]["ToAddresses"] == [recipient]
        assert result == {"MessageId": "test-message-id"}
    
    # Verify total number of calls
    assert mock_ses_client.send_email.call_count == len(recipients)


@pytest.mark.asyncio
async def test_send_confirmation_email_with_very_long_title(mock_ses_client):
    """Test sending a confirmation email with a very long podcast title."""
    # Setup
    recipient = "user@example.com"
    job_id = "test-job-id"
    podcast_title = "This is a very long podcast title that exceeds the typical length " * 10  # Very long title
    
    # Execute
    result = await send_confirmation_email(recipient, job_id, podcast_title, ses_client=mock_ses_client)
    
    # Verify
    mock_ses_client.send_email.assert_called_once()
    call_args = mock_ses_client.send_email.call_args[1]
    
    assert call_args["Destination"]["ToAddresses"] == [recipient]
    assert "Your podcast is being processed" in call_args["Message"]["Subject"]["Data"]
    assert podcast_title in call_args["Message"]["Body"]["Text"]["Data"]
    assert podcast_title in call_args["Message"]["Body"]["Html"]["Data"]
    assert result == {"MessageId": "test-message-id"}


@pytest.mark.asyncio
async def test_send_error_notification_with_very_long_error(mock_ses_client):
    """Test sending an error notification with a very long error message."""
    # Setup
    recipient = "user@example.com"
    job_id = "test-job-id"
    error_message = "This is a very long error message with stack trace: " + "Error details\n" * 50  # Very long error
    step = "transcription"
    
    # Execute
    result = await send_error_notification(recipient, job_id, error_message, step, ses_client=mock_ses_client)
    
    # Verify
    mock_ses_client.send_email.assert_called_once()
    call_args = mock_ses_client.send_email.call_args[1]
    
    assert call_args["Destination"]["ToAddresses"] == [recipient]
    assert "Error processing your podcast" in call_args["Message"]["Subject"]["Data"]
    assert error_message in call_args["Message"]["Body"]["Text"]["Data"]
    assert error_message in call_args["Message"]["Body"]["Html"]["Data"]
    assert result == {"MessageId": "test-message-id"}


@pytest.mark.asyncio
async def test_send_completion_notification_with_invalid_url(mock_ses_client):
    """Test sending a completion notification with an invalid summary URL."""
    # Setup
    recipient = "user@example.com"
    job_id = "test-job-id"
    podcast_title = "Test Podcast"
    summary_url = "invalid-url"  # Invalid URL format
    
    # Execute
    result = await send_completion_notification(recipient, job_id, podcast_title, summary_url, ses_client=mock_ses_client)
    
    # Verify
    mock_ses_client.send_email.assert_called_once()
    call_args = mock_ses_client.send_email.call_args[1]
    
    assert call_args["Destination"]["ToAddresses"] == [recipient]
    assert "Your podcast summary is ready" in call_args["Message"]["Subject"]["Data"]
    assert summary_url in call_args["Message"]["Body"]["Text"]["Data"]
    assert summary_url in call_args["Message"]["Body"]["Html"]["Data"]
    assert result == {"MessageId": "test-message-id"}


@pytest.mark.asyncio
async def test_process_message_with_invalid_json():
    """Test handling of completely invalid JSON in message body."""
    # Setup
    message = {
        "MessageId": "test-message-id",
        "ReceiptHandle": "test-receipt-handle",
        "Body": "This is not valid JSON at all"
    }
    
    with patch("media_summarizer.workers.notification.email_worker.session") as mock_session:
        mock_sqs_client = AsyncMock()
        mock_session.create_client.return_value.__aenter__.return_value = mock_sqs_client
        
        # Execute
        await process_message(message)
        
        # Verify no email was sent and message was not deleted
        mock_sqs_client.delete_message.assert_not_called()


@pytest.mark.asyncio
async def test_process_message_with_malformed_json():
    """Test handling of malformed JSON in message body."""
    # Setup
    message = {
        "MessageId": "test-message-id",
        "ReceiptHandle": "test-receipt-handle",
        "Body": "{\"job_id\": \"test-job-id\", \"email\": \"user@example.com\", \"notification_type\": \"confirmation\""  # Missing closing brace
    }
    
    with patch("media_summarizer.workers.notification.email_worker.session") as mock_session:
        mock_sqs_client = AsyncMock()
        mock_session.create_client.return_value.__aenter__.return_value = mock_sqs_client
        
        # Execute
        await process_message(message)
        
        # Verify no email was sent and message was not deleted
        mock_sqs_client.delete_message.assert_not_called()


@pytest.mark.asyncio
async def test_process_message_with_invalid_email():
    """Test handling of message with invalid email address."""
    # Setup
    message = {
        "MessageId": "test-message-id",
        "ReceiptHandle": "test-receipt-handle",
        "Body": json.dumps({
            "job_id": "test-job-id",
            "email": "invalid-email",  # Invalid email format
            "notification_type": "confirmation"
        })
    }
    
    with patch("media_summarizer.workers.notification.email_worker.send_confirmation_email") as mock_send_confirmation:
        # Configure mock to raise ClientError for invalid email
        error_response = {"Error": {"Code": "ValidationError", "Message": "Invalid email address"}}
        mock_send_confirmation.side_effect = ClientError(error_response, "send_email")
        
        with patch("media_summarizer.workers.notification.email_worker.session") as mock_session:
            mock_sqs_client = AsyncMock()
            mock_session.create_client.return_value.__aenter__.return_value = mock_sqs_client
            
            with patch("asyncio.sleep", AsyncMock()) as mock_sleep:
                # Execute
                await process_message(message)
                
                # Verify retry behavior
                assert mock_send_confirmation.call_count > 1
                mock_sleep.assert_called()
                mock_sqs_client.delete_message.assert_not_called()


@pytest.mark.asyncio
async def test_process_message_with_custom_notification_type(mock_ses_client, mock_sqs_client):
    """Test handling of message with custom notification type."""
    # Setup
    message = {
        "MessageId": "test-message-id",
        "ReceiptHandle": "test-receipt-handle",
        "Body": json.dumps({
            "job_id": "test-job-id",
            "email": "user@example.com",
            "notification_type": "custom",  # Custom notification type
            "custom_subject": "Custom Subject",
            "custom_message": "Custom message body"
        })
    }
    
    # Execute
    await process_message(message, ses_client=mock_ses_client, sqs_client=mock_sqs_client)
    
    # Verify that message was not processed (unknown notification type)
    mock_ses_client.send_email.assert_not_called()
    mock_sqs_client.delete_message.assert_not_called()


@pytest.mark.asyncio
async def test_process_message_with_empty_email(mock_ses_client, mock_sqs_client):
    """Test handling of message with empty email address."""
    # Setup
    message = {
        "MessageId": "test-message-id",
        "ReceiptHandle": "test-receipt-handle",
        "Body": json.dumps({
            "job_id": "test-job-id",
            "email": "",  # Empty email
            "notification_type": "confirmation"
        })
    }
    
    # Execute
    await process_message(message, ses_client=mock_ses_client, sqs_client=mock_sqs_client)
    
    # Verify that message was not processed (missing required fields)
    mock_ses_client.send_email.assert_not_called()
    mock_sqs_client.delete_message.assert_not_called()


@pytest.mark.asyncio
async def test_process_message_with_empty_job_id(mock_ses_client, mock_sqs_client):
    """Test handling of message with empty job ID."""
    # Setup
    message = {
        "MessageId": "test-message-id",
        "ReceiptHandle": "test-receipt-handle",
        "Body": json.dumps({
            "job_id": "",  # Empty job ID
            "email": "user@example.com",
            "notification_type": "confirmation"
        })
    }
    
    # Execute
    await process_message(message, ses_client=mock_ses_client, sqs_client=mock_sqs_client)
    
    # Verify that message was not processed (missing required fields)
    mock_ses_client.send_email.assert_not_called()
    mock_sqs_client.delete_message.assert_not_called()


@pytest.mark.asyncio
async def test_process_message_with_very_long_job_id(mock_ses_client, mock_sqs_client):
    """Test handling of message with very long job ID."""
    # Setup
    message = {
        "MessageId": "test-message-id",
        "ReceiptHandle": "test-receipt-handle",
        "Body": json.dumps({
            "job_id": "very-long-job-id-" + "x" * 1000,  # Very long job ID
            "email": "user@example.com",
            "notification_type": "confirmation"
        })
    }
    
    # Execute
    with patch("media_summarizer.workers.notification.email_worker.send_confirmation_email") as mock_send_confirmation:
        mock_send_confirmation.return_value = {"MessageId": "test-message-id"}
        
        await process_message(message, ses_client=mock_ses_client, sqs_client=mock_sqs_client)
        
        # Verify that message was processed
        mock_send_confirmation.assert_called_once()
        mock_sqs_client.delete_message.assert_called_once()


@pytest.mark.asyncio
async def test_process_message_with_unicode_characters_in_fields(mock_ses_client, mock_sqs_client):
    """Test handling of message with unicode characters in fields."""
    # Setup
    message = {
        "MessageId": "test-message-id",
        "ReceiptHandle": "test-receipt-handle",
        "Body": json.dumps({
            "job_id": "test-job-id",
            "email": "user@example.com",
            "notification_type": "confirmation",
            "podcast_title": "Podcast with Unicode: こんにちは世界"  # Unicode characters
        })
    }
    
    # Execute
    with patch("media_summarizer.workers.notification.email_worker.send_confirmation_email") as mock_send_confirmation:
        mock_send_confirmation.return_value = {"MessageId": "test-message-id"}
        
        await process_message(message, ses_client=mock_ses_client, sqs_client=mock_sqs_client)
        
        # Verify that message was processed
        mock_send_confirmation.assert_called_once()
        call_args = mock_send_confirmation.call_args
        assert call_args[0][2] == "Podcast with Unicode: こんにちは世界"  # Unicode characters preserved
        mock_sqs_client.delete_message.assert_called_once()


@pytest.mark.asyncio
async def test_process_message_with_special_characters_in_fields(mock_ses_client, mock_sqs_client):
    """Test handling of message with special characters in fields."""
    # Setup
    message = {
        "MessageId": "test-message-id",
        "ReceiptHandle": "test-receipt-handle",
        "Body": json.dumps({
            "job_id": "test-job-id",
            "email": "user@example.com",
            "notification_type": "confirmation",
            "podcast_title": "Podcast with Special Characters: !@#$%^&*()"  # Special characters
        })
    }
    
    # Execute
    with patch("media_summarizer.workers.notification.email_worker.send_confirmation_email") as mock_send_confirmation:
        mock_send_confirmation.return_value = {"MessageId": "test-message-id"}
        
        await process_message(message, ses_client=mock_ses_client, sqs_client=mock_sqs_client)
        
        # Verify that message was processed
        mock_send_confirmation.assert_called_once()
        call_args = mock_send_confirmation.call_args
        assert call_args[0][2] == "Podcast with Special Characters: !@#$%^&*()"  # Special characters preserved
        mock_sqs_client.delete_message.assert_called_once()