"""
Unit tests for the email adapter.
"""
import os
import json
import pytest
import pytest_asyncio
from unittest.mock import patch, MagicMock, AsyncMock
from botocore.exceptions import ClientError

# Set AWS credentials for testing
os.environ["AWS_ACCESS_KEY_ID"] = "test"
os.environ["AWS_SECRET_ACCESS_KEY"] = "test"
os.environ["AWS_DEFAULT_REGION"] = "us-east-1"
os.environ["AWS_ENDPOINT_URL"] = "http://localhost:4566"

from media_summarizer.adapters.email.email_adapter import EmailAdapter


@pytest.fixture
def mock_ses_client():
    """Mock SES client for testing."""
    mock_client = AsyncMock()
    mock_client.send_email = AsyncMock(return_value={"MessageId": "test-message-id"})
    mock_client.send_templated_email = AsyncMock(return_value={"MessageId": "test-template-message-id"})
    mock_client.verify_email_identity = AsyncMock(return_value={"VerificationAttributes": {}})
    mock_client.get_send_quota = AsyncMock(return_value={
        "Max24HourSend": 200.0,
        "MaxSendRate": 1.0,
        "SentLast24Hours": 0.0
    })
    mock_client.get_send_statistics = AsyncMock(return_value={
        "SendDataPoints": [
            {
                "Timestamp": "2023-01-01T00:00:00Z",
                "DeliveryAttempts": 10,
                "Bounces": 0,
                "Complaints": 0,
                "Rejects": 0
            }
        ]
    })
    return mock_client


@pytest.fixture
def email_adapter():
    """Create an EmailAdapter instance for testing."""
    return EmailAdapter(region_name="us-east-1", endpoint_url="http://localhost:4566")


class TestEmailAdapter:
    """Test cases for the EmailAdapter class."""
    
    @pytest.mark.asyncio
    async def test_init(self):
        """Test EmailAdapter initialization."""
        # Test with default values
        adapter = EmailAdapter()
        assert adapter.region_name == "us-east-1"
        assert adapter.endpoint_url == "http://localhost:4566"
        
        # Test with custom values
        adapter = EmailAdapter(region_name="eu-west-1", endpoint_url="http://custom-endpoint")
        assert adapter.region_name == "eu-west-1"
        assert adapter.endpoint_url == "http://custom-endpoint"
    
    @pytest.mark.asyncio
    async def test_send_email(self, email_adapter, mock_ses_client):
        """Test sending an email."""
        # Setup
        recipient = "user@example.com"
        subject = "Test Subject"
        body_text = "Test body text"
        body_html = "<p>Test body HTML</p>"
        
        # Execute - Test with provided ses_client
        result = await email_adapter.send_email(
            recipient, subject, body_text, body_html, ses_client=mock_ses_client
        )
        
        # Verify
        mock_ses_client.send_email.assert_called_once()
        call_args = mock_ses_client.send_email.call_args[1]
        
        assert call_args["Destination"]["ToAddresses"] == [recipient]
        assert call_args["Message"]["Subject"]["Data"] == subject
        assert call_args["Message"]["Body"]["Text"]["Data"] == body_text
        assert call_args["Message"]["Body"]["Html"]["Data"] == body_html
        assert result == {"MessageId": "test-message-id"}
        
        # Reset mock
        mock_ses_client.reset_mock()
        
        # Execute - Test with provided ses_client
        result = await email_adapter.send_email(
            recipient, subject, body_text, body_html, ses_client=mock_ses_client
        )
        
        # Verify
        mock_ses_client.send_email.assert_called_once()
        call_args = mock_ses_client.send_email.call_args[1]
        
        assert call_args["Destination"]["ToAddresses"] == [recipient]
        assert call_args["Message"]["Subject"]["Data"] == subject
        assert call_args["Message"]["Body"]["Text"]["Data"] == body_text
        assert call_args["Message"]["Body"]["Html"]["Data"] == body_html
        assert result == {"MessageId": "test-message-id"}
    
    @pytest.mark.asyncio
    async def test_send_email_with_custom_sender(self, email_adapter, mock_ses_client):
        """Test sending an email with a custom sender."""
        # Setup
        recipient = "user@example.com"
        subject = "Test Subject"
        body_text = "Test body text"
        sender = "custom@example.com"
        reply_to = ["reply@example.com"]
        
        # Execute
        result = await email_adapter.send_email(
            recipient, subject, body_text, sender=sender, reply_to=reply_to, ses_client=mock_ses_client
        )
        
        # Verify
        mock_ses_client.send_email.assert_called_once()
        call_args = mock_ses_client.send_email.call_args[1]
        
        assert call_args["Destination"]["ToAddresses"] == [recipient]
        assert call_args["Source"] == sender
        assert call_args["ReplyToAddresses"] == reply_to
        assert result == {"MessageId": "test-message-id"}
    
    @pytest.mark.asyncio
    async def test_send_email_without_html(self, email_adapter, mock_ses_client):
        """Test sending an email without HTML body."""
        # Setup
        recipient = "user@example.com"
        subject = "Test Subject"
        body_text = "Test body text"
        
        # Execute
        result = await email_adapter.send_email(
            recipient, subject, body_text, ses_client=mock_ses_client
        )
        
        # Verify
        mock_ses_client.send_email.assert_called_once()
        call_args = mock_ses_client.send_email.call_args[1]
        
        assert call_args["Destination"]["ToAddresses"] == [recipient]
        assert "Html" not in call_args["Message"]["Body"]
        assert result == {"MessageId": "test-message-id"}
    
    @pytest.mark.asyncio
    async def test_send_email_with_client_error(self, email_adapter, mock_ses_client):
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
            await email_adapter.send_email(recipient, subject, body_text, ses_client=mock_ses_client)
        
        assert "MessageRejected" in str(excinfo.value)
        assert "Email address is not verified" in str(excinfo.value)
    
    @pytest.mark.asyncio
    async def test_send_template_email(self, email_adapter, mock_ses_client):
        """Test sending a templated email."""
        # Setup
        recipient = "user@example.com"
        template_name = "TestTemplate"
        template_data = {
            "name": "Test User",
            "message": "This is a test message"
        }
        
        # Execute
        result = await email_adapter.send_template_email(
            recipient, template_name, template_data, ses_client=mock_ses_client
        )
        
        # Verify
        mock_ses_client.send_templated_email.assert_called_once()
        call_args = mock_ses_client.send_templated_email.call_args[1]
        
        assert call_args["Destination"]["ToAddresses"] == [recipient]
        assert call_args["Template"] == template_name
        assert call_args["TemplateData"] == template_data
        assert result == {"MessageId": "test-template-message-id"}
    
    @pytest.mark.asyncio
    async def test_send_template_email_with_custom_sender(self, email_adapter, mock_ses_client):
        """Test sending a templated email with a custom sender."""
        # Setup
        recipient = "user@example.com"
        template_name = "TestTemplate"
        template_data = {"name": "Test User"}
        sender = "custom@example.com"
        reply_to = ["reply@example.com"]
        
        # Execute
        result = await email_adapter.send_template_email(
            recipient, template_name, template_data, sender=sender, reply_to=reply_to, ses_client=mock_ses_client
        )
        
        # Verify
        mock_ses_client.send_templated_email.assert_called_once()
        call_args = mock_ses_client.send_templated_email.call_args[1]
        
        assert call_args["Destination"]["ToAddresses"] == [recipient]
        assert call_args["Source"] == sender
        assert call_args["ReplyToAddresses"] == reply_to
        assert result == {"MessageId": "test-template-message-id"}
    
    @pytest.mark.asyncio
    async def test_send_template_email_with_client_error(self, email_adapter, mock_ses_client):
        """Test handling of ClientError during templated email sending."""
        # Setup
        recipient = "user@example.com"
        template_name = "TestTemplate"
        template_data = {"name": "Test User"}
        
        # Configure mock to raise ClientError
        error_response = {"Error": {"Code": "TemplateDoesNotExist", "Message": "Template does not exist"}}
        mock_ses_client.send_templated_email.side_effect = ClientError(error_response, "send_templated_email")
        
        # Execute and verify
        with pytest.raises(ClientError) as excinfo:
            await email_adapter.send_template_email(recipient, template_name, template_data, ses_client=mock_ses_client)
        
        assert "TemplateDoesNotExist" in str(excinfo.value)
        assert "Template does not exist" in str(excinfo.value)
    
    @pytest.mark.asyncio
    async def test_verify_email_identity(self, email_adapter, mock_ses_client):
        """Test verifying an email identity."""
        # Setup
        email_address = "user@example.com"
        
        # Execute
        result = await email_adapter.verify_email_identity(email_address, ses_client=mock_ses_client)
        
        # Verify
        mock_ses_client.verify_email_identity.assert_called_once_with(EmailAddress=email_address)
        assert result == {"VerificationAttributes": {}}
    
    @pytest.mark.asyncio
    async def test_verify_email_identity_with_client_error(self, email_adapter, mock_ses_client):
        """Test handling of ClientError during email identity verification."""
        # Setup
        email_address = "user@example.com"
        
        # Configure mock to raise ClientError
        error_response = {"Error": {"Code": "ValidationError", "Message": "Invalid email address"}}
        mock_ses_client.verify_email_identity.side_effect = ClientError(error_response, "verify_email_identity")
        
        # Execute and verify
        with pytest.raises(ClientError) as excinfo:
            await email_adapter.verify_email_identity(email_address, ses_client=mock_ses_client)
        
        assert "ValidationError" in str(excinfo.value)
        assert "Invalid email address" in str(excinfo.value)
    
    @pytest.mark.asyncio
    async def test_get_send_quota(self, email_adapter, mock_ses_client):
        """Test getting the SES sending quota."""
        # Execute
        result = await email_adapter.get_send_quota(ses_client=mock_ses_client)
        
        # Verify
        mock_ses_client.get_send_quota.assert_called_once()
        assert result["Max24HourSend"] == 200.0
        assert result["MaxSendRate"] == 1.0
        assert result["SentLast24Hours"] == 0.0
    
    @pytest.mark.asyncio
    async def test_get_send_quota_with_client_error(self, email_adapter, mock_ses_client):
        """Test handling of ClientError during getting the sending quota."""
        # Configure mock to raise ClientError
        error_response = {"Error": {"Code": "AccessDenied", "Message": "Access denied"}}
        mock_ses_client.get_send_quota.side_effect = ClientError(error_response, "get_send_quota")
        
        # Execute and verify
        with pytest.raises(ClientError) as excinfo:
            await email_adapter.get_send_quota(ses_client=mock_ses_client)
        
        assert "AccessDenied" in str(excinfo.value)
        assert "Access denied" in str(excinfo.value)
    
    @pytest.mark.asyncio
    async def test_get_send_statistics(self, email_adapter, mock_ses_client):
        """Test getting the SES sending statistics."""
        # Execute
        result = await email_adapter.get_send_statistics(ses_client=mock_ses_client)
        
        # Verify
        mock_ses_client.get_send_statistics.assert_called_once()
        assert len(result["SendDataPoints"]) == 1
        assert result["SendDataPoints"][0]["DeliveryAttempts"] == 10
        assert result["SendDataPoints"][0]["Bounces"] == 0
    
    @pytest.mark.asyncio
    async def test_get_send_statistics_with_client_error(self, email_adapter, mock_ses_client):
        """Test handling of ClientError during getting the sending statistics."""
        # Configure mock to raise ClientError
        error_response = {"Error": {"Code": "AccessDenied", "Message": "Access denied"}}
        mock_ses_client.get_send_statistics.side_effect = ClientError(error_response, "get_send_statistics")
        
        # Execute and verify
        with pytest.raises(ClientError) as excinfo:
            await email_adapter.get_send_statistics(ses_client=mock_ses_client)
        
        assert "AccessDenied" in str(excinfo.value)
        assert "Access denied" in str(excinfo.value)
    
    @pytest.mark.asyncio
    async def test_send_email_with_unicode_characters(self, email_adapter, mock_ses_client):
        """Test sending an email with unicode characters."""
        # Setup
        recipient = "user@example.com"
        subject = "Test Subject with Unicode: こんにちは世界"
        body_text = "Test body text with Unicode: こんにちは世界"
        body_html = "<p>Test body HTML with Unicode: こんにちは世界</p>"
        
        # Execute
        result = await email_adapter.send_email(
            recipient, subject, body_text, body_html, ses_client=mock_ses_client
        )
        
        # Verify
        mock_ses_client.send_email.assert_called_once()
        call_args = mock_ses_client.send_email.call_args[1]
        
        assert call_args["Destination"]["ToAddresses"] == [recipient]
        assert call_args["Message"]["Subject"]["Data"] == subject
        assert call_args["Message"]["Body"]["Text"]["Data"] == body_text
        assert call_args["Message"]["Body"]["Html"]["Data"] == body_html
        assert result == {"MessageId": "test-message-id"}
    
    @pytest.mark.asyncio
    async def test_send_email_with_special_characters(self, email_adapter, mock_ses_client):
        """Test sending an email with special characters."""
        # Setup
        recipient = "user@example.com"
        subject = "Test Subject with Special Characters: !@#$%^&*()"
        body_text = "Test body text with special characters: !@#$%^&*()"
        body_html = "<p>Test body HTML with special characters: !@#$%^&*()</p>"
        
        # Execute
        result = await email_adapter.send_email(
            recipient, subject, body_text, body_html, ses_client=mock_ses_client
        )
        
        # Verify
        mock_ses_client.send_email.assert_called_once()
        call_args = mock_ses_client.send_email.call_args[1]
        
        assert call_args["Destination"]["ToAddresses"] == [recipient]
        assert call_args["Message"]["Subject"]["Data"] == subject
        assert call_args["Message"]["Body"]["Text"]["Data"] == body_text
        assert call_args["Message"]["Body"]["Html"]["Data"] == body_html
        assert result == {"MessageId": "test-message-id"}
    
    @pytest.mark.asyncio
    async def test_send_email_with_empty_body(self, email_adapter, mock_ses_client):
        """Test sending an email with empty body."""
        # Setup
        recipient = "user@example.com"
        subject = "Test Subject"
        body_text = ""  # Empty body
        
        # Execute
        result = await email_adapter.send_email(
            recipient, subject, body_text, ses_client=mock_ses_client
        )
        
        # Verify
        mock_ses_client.send_email.assert_called_once()
        call_args = mock_ses_client.send_email.call_args[1]
        
        assert call_args["Destination"]["ToAddresses"] == [recipient]
        assert call_args["Message"]["Subject"]["Data"] == subject
        assert call_args["Message"]["Body"]["Text"]["Data"] == ""  # Empty body
        assert result == {"MessageId": "test-message-id"}
    
    @pytest.mark.asyncio
    async def test_send_template_email_with_complex_data(self, email_adapter, mock_ses_client):
        """Test sending a templated email with complex template data."""
        # Setup
        recipient = "user@example.com"
        template_name = "TestTemplate"
        template_data = {
            "user": {
                "name": "Test User",
                "email": "user@example.com",
                "preferences": {
                    "language": "en",
                    "notifications": True
                }
            },
            "items": [
                {"id": 1, "name": "Item 1"},
                {"id": 2, "name": "Item 2"},
                {"id": 3, "name": "Item 3"}
            ],
            "message": "This is a test message with special characters: !@#$%^&*()"
        }
        
        # Execute
        result = await email_adapter.send_template_email(
            recipient, template_name, template_data, ses_client=mock_ses_client
        )
        
        # Verify
        mock_ses_client.send_templated_email.assert_called_once()
        call_args = mock_ses_client.send_templated_email.call_args[1]
        
        assert call_args["Destination"]["ToAddresses"] == [recipient]
        assert call_args["Template"] == template_name
        assert call_args["TemplateData"] == template_data
        assert result == {"MessageId": "test-template-message-id"}