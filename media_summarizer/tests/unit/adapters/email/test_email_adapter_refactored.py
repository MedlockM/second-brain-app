"""
Refactored unit tests for the email adapter using standardized test utilities.
"""
import os
import json
import pytest
import pytest_asyncio
from unittest.mock import patch, MagicMock, AsyncMock
from botocore.exceptions import ClientError

from media_summarizer.adapters.email.email_adapter import EmailAdapter
from media_summarizer.tests.utils.base_test_classes import BaseAdapterTestCase
from media_summarizer.tests.utils.test_helpers import assert_email_sent, set_env_vars, restore_env_vars


class TestEmailAdapterRefactored(BaseAdapterTestCase):
    """Refactored test cases for the EmailAdapter class."""
    
    @pytest.fixture(autouse=True)
    def setup_environment(self):
        """Set up environment variables for testing."""
        original_values = set_env_vars({
            "AWS_ACCESS_KEY_ID": "test",
            "AWS_SECRET_ACCESS_KEY": "test",
            "AWS_DEFAULT_REGION": "us-east-1",
            "AWS_ENDPOINT_URL": "http://localhost:4566"
        })
        yield
        restore_env_vars(original_values)
        
    def create_client_error(self, code, message, operation_name):
        """Create a ClientError exception for testing."""
        error_response = {
            "Error": {
                "Code": code,
                "Message": message
            }
        }
        return ClientError(error_response, operation_name)
    
    @pytest.fixture
    def mock_ses_client(self):
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
    def email_adapter(self):
        """Create an EmailAdapter instance for testing."""
        return EmailAdapter(region_name="us-east-1", endpoint_url="http://localhost:4566")
    
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
        
        # Verify using the helper function
        message = assert_email_sent(
            mock_ses_client,
            expected_recipient=recipient,
            expected_subject_contains=subject,
            expected_body_contains=body_text
        )
        
        # Additional verification
        assert message["Body"]["Html"]["Data"] == body_html
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
        error = self.create_client_error(
            code="MessageRejected",
            message="Email address is not verified",
            operation_name="send_email"
        )
        mock_ses_client.send_email.side_effect = error
        
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
    async def test_send_template_email_with_client_error(self, email_adapter, mock_ses_client):
        """Test handling of ClientError during templated email sending."""
        # Setup
        recipient = "user@example.com"
        template_name = "TestTemplate"
        template_data = {"name": "Test User"}
        
        # Configure mock to raise ClientError
        error = self.create_client_error(
            code="TemplateDoesNotExist",
            message="Template does not exist",
            operation_name="send_templated_email"
        )
        mock_ses_client.send_templated_email.side_effect = error
        
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
        
        # Verify using the helper function
        message = assert_email_sent(
            mock_ses_client,
            expected_recipient=recipient,
            expected_subject_contains="Unicode",
            expected_body_contains="こんにちは世界"
        )
        
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