"""
Unit tests for SES utilities.

This module contains unit tests for all SES utility functions,
using mocked aiobotocore operations to test the logic without requiring
actual AWS services.
"""
import pytest
import asyncio
from unittest.mock import Mock, patch, AsyncMock, MagicMock

from media_summarizer.utils import ses


@pytest.fixture
def mock_ses_client():
    """Create a mock SES client."""
    mock_client = AsyncMock()
    return mock_client


@pytest.fixture
def mock_session():
    """Create a mock aiobotocore session."""
    with patch('media_summarizer.utils.ses.session') as mock_session:
        mock_client = AsyncMock()
        mock_session.create_client.return_value.__aenter__.return_value = mock_client
        yield mock_session, mock_client


class TestSendEmail:
    """Test email sending functionality."""

    @pytest.mark.asyncio
    async def test_send_email_text_only(self, mock_session):
        """Test sending text-only email."""
        mock_session_obj, mock_client = mock_session
        mock_client.send_email.return_value = {'MessageId': 'test-message-id'}

        result = await ses.send_email(
            recipient="test@example.com",
            subject="Test Subject",
            body_text="Test body content"
        )

        mock_client.send_email.assert_called_once()
        call_args = mock_client.send_email.call_args[1]

        assert call_args["Destination"]["ToAddresses"] == ["test@example.com"]
        assert call_args["Message"]["Subject"]["Data"] == "Test Subject"
        assert call_args["Message"]["Body"]["Text"]["Data"] == "Test body content"
        assert call_args["Source"] == ses.DEFAULT_SENDER
        assert call_args["ReplyToAddresses"] == [ses.DEFAULT_SENDER]
        assert result == {'MessageId': 'test-message-id'}

    @pytest.mark.asyncio
    async def test_send_email_with_html(self, mock_session):
        """Test sending email with HTML body."""
        mock_session_obj, mock_client = mock_session
        mock_client.send_email.return_value = {'MessageId': 'test-message-id'}

        await ses.send_email(
            recipient="test@example.com",
            subject="Test Subject",
            body_text="Test body content",
            body_html="<h1>Test HTML</h1>"
        )

        call_args = mock_client.send_email.call_args[1]
        assert call_args["Message"]["Body"]["Html"]["Data"] == "<h1>Test HTML</h1>"

    @pytest.mark.asyncio
    async def test_send_email_custom_sender(self, mock_session):
        """Test sending email with custom sender."""
        mock_session_obj, mock_client = mock_session
        mock_client.send_email.return_value = {'MessageId': 'test-message-id'}

        await ses.send_email(
            recipient="test@example.com",
            subject="Test Subject",
            body_text="Test body content",
            sender="custom@example.com",
            reply_to=["reply@example.com"]
        )

        call_args = mock_client.send_email.call_args[1]
        assert call_args["Source"] == "custom@example.com"
        assert call_args["ReplyToAddresses"] == ["reply@example.com"]

    @pytest.mark.asyncio
    async def test_send_email_error(self, mock_session):
        """Test send email with SES error."""
        mock_session_obj, mock_client = mock_session
        mock_client.send_email.side_effect = Exception("SES error")

        with pytest.raises(Exception, match="SES error"):
            await ses.send_email(
                recipient="test@example.com",
                subject="Test Subject",
                body_text="Test body content"
            )


class TestSendBulkEmail:
    """Test bulk email sending functionality."""

    @pytest.mark.asyncio
    async def test_send_bulk_email_success(self, mock_session):
        """Test successful bulk email sending."""
        mock_session_obj, mock_client = mock_session
        mock_client.send_email.return_value = {'MessageId': 'test-message-id'}

        recipients = ["test1@example.com", "test2@example.com", "test3@example.com"]
        result = await ses.send_bulk_email(
            recipients=recipients,
            subject="Bulk Test Subject",
            body_text="Bulk test body"
        )

        mock_client.send_email.assert_called_once()
        call_args = mock_client.send_email.call_args[1]

        assert call_args["Destination"]["ToAddresses"] == recipients
        assert call_args["Message"]["Subject"]["Data"] == "Bulk Test Subject"
        assert call_args["Message"]["Body"]["Text"]["Data"] == "Bulk test body"
        assert result == {'MessageId': 'test-message-id'}

    @pytest.mark.asyncio
    async def test_send_bulk_email_with_html(self, mock_session):
        """Test bulk email with HTML body."""
        mock_session_obj, mock_client = mock_session
        mock_client.send_email.return_value = {'MessageId': 'test-message-id'}

        recipients = ["test1@example.com", "test2@example.com"]
        await ses.send_bulk_email(
            recipients=recipients,
            subject="Bulk Test Subject",
            body_text="Bulk test body",
            body_html="<h1>Bulk Test HTML</h1>"
        )

        call_args = mock_client.send_email.call_args[1]
        assert call_args["Message"]["Body"]["Html"]["Data"] == "<h1>Bulk Test HTML</h1>"

    @pytest.mark.asyncio
    async def test_send_bulk_email_error(self, mock_session):
        """Test bulk email with SES error."""
        mock_session_obj, mock_client = mock_session
        mock_client.send_email.side_effect = Exception("SES error")

        with pytest.raises(Exception, match="SES error"):
            await ses.send_bulk_email(
                recipients=["test@example.com"],
                subject="Test Subject",
                body_text="Test body"
            )


class TestSendRawEmail:
    """Test raw email sending functionality."""

    @pytest.mark.asyncio
    async def test_send_raw_email_success(self, mock_session):
        """Test successful raw email sending."""
        mock_session_obj, mock_client = mock_session
        mock_client.send_raw_email.return_value = {'MessageId': 'test-message-id'}

        raw_message = "From: test@example.com\nTo: recipient@example.com\nSubject: Test\n\nRaw message body"
        result = await ses.send_raw_email(raw_message=raw_message)

        mock_client.send_raw_email.assert_called_once()
        call_args = mock_client.send_raw_email.call_args[1]

        assert call_args["Source"] == ses.DEFAULT_SENDER
        assert call_args["RawMessage"]["Data"] == raw_message
        assert result == {'MessageId': 'test-message-id'}

    @pytest.mark.asyncio
    async def test_send_raw_email_with_destinations(self, mock_session):
        """Test raw email with destinations."""
        mock_session_obj, mock_client = mock_session
        mock_client.send_raw_email.return_value = {'MessageId': 'test-message-id'}

        destinations = ["test1@example.com", "test2@example.com"]
        await ses.send_raw_email(
            raw_message="Raw message",
            sender="custom@example.com",
            destinations=destinations
        )

        call_args = mock_client.send_raw_email.call_args[1]
        assert call_args["Source"] == "custom@example.com"
        assert call_args["Destinations"] == destinations

    @pytest.mark.asyncio
    async def test_send_raw_email_error(self, mock_session):
        """Test raw email with SES error."""
        mock_session_obj, mock_client = mock_session
        mock_client.send_raw_email.side_effect = Exception("SES error")

        with pytest.raises(Exception, match="SES error"):
            await ses.send_raw_email(raw_message="Raw message")


class TestSendTemplatedEmail:
    """Test templated email sending functionality."""

    @pytest.mark.asyncio
    async def test_send_templated_email_success(self, mock_session):
        """Test successful templated email sending."""
        mock_session_obj, mock_client = mock_session
        mock_client.send_templated_email.return_value = {'MessageId': 'test-message-id'}

        template_data = {"name": "John", "amount": "100"}
        result = await ses.send_templated_email(
            recipient="test@example.com",
            template_name="WelcomeTemplate",
            template_data=template_data
        )

        mock_client.send_templated_email.assert_called_once()
        call_args = mock_client.send_templated_email.call_args[1]

        assert call_args["Source"] == ses.DEFAULT_SENDER
        assert call_args["Destination"]["ToAddresses"] == ["test@example.com"]
        assert call_args["Template"] == "WelcomeTemplate"
        assert call_args["TemplateData"] == str(template_data)
        assert call_args["ReplyToAddresses"] == [ses.DEFAULT_SENDER]
        assert result == {'MessageId': 'test-message-id'}

    @pytest.mark.asyncio
    async def test_send_templated_email_custom_params(self, mock_session):
        """Test templated email with custom parameters."""
        mock_session_obj, mock_client = mock_session
        mock_client.send_templated_email.return_value = {'MessageId': 'test-message-id'}

        await ses.send_templated_email(
            recipient="test@example.com",
            template_name="CustomTemplate",
            template_data="string data",
            sender="custom@example.com",
            reply_to=["reply@example.com", "support@example.com"]
        )

        call_args = mock_client.send_templated_email.call_args[1]
        assert call_args["Source"] == "custom@example.com"
        assert call_args["TemplateData"] == "string data"
        assert call_args["ReplyToAddresses"] == ["reply@example.com", "support@example.com"]

    @pytest.mark.asyncio
    async def test_send_templated_email_error(self, mock_session):
        """Test templated email with SES error."""
        mock_session_obj, mock_client = mock_session
        mock_client.send_templated_email.side_effect = Exception("SES error")

        with pytest.raises(Exception, match="SES error"):
            await ses.send_templated_email(
                recipient="test@example.com",
                template_name="TestTemplate",
                template_data={}
            )


class TestVerifyEmailIdentity:
    """Test email identity verification functionality."""

    @pytest.mark.asyncio
    async def test_verify_email_identity_success(self, mock_session):
        """Test successful email verification."""
        mock_session_obj, mock_client = mock_session
        mock_client.verify_email_identity.return_value = {}

        result = await ses.verify_email_identity("test@example.com")

        mock_client.verify_email_identity.assert_called_once_with(
            EmailAddress="test@example.com"
        )
        assert result == {}

    @pytest.mark.asyncio
    async def test_verify_email_identity_error(self, mock_session):
        """Test email verification with SES error."""
        mock_session_obj, mock_client = mock_session
        mock_client.verify_email_identity.side_effect = Exception("SES error")

        with pytest.raises(Exception, match="SES error"):
            await ses.verify_email_identity("test@example.com")


class TestGetSendQuota:
    """Test send quota functionality."""

    @pytest.mark.asyncio
    async def test_get_send_quota_success(self, mock_session):
        """Test successful send quota retrieval."""
        mock_session_obj, mock_client = mock_session
        expected_quota = {
            "Max24HourSend": 200,
            "MaxSendRate": 1,
            "SentLast24Hours": 15
        }
        mock_client.get_send_quota.return_value = expected_quota

        result = await ses.get_send_quota()

        mock_client.get_send_quota.assert_called_once()
        assert result == expected_quota

    @pytest.mark.asyncio
    async def test_get_send_quota_error(self, mock_session):
        """Test send quota with SES error."""
        mock_session_obj, mock_client = mock_session
        mock_client.get_send_quota.side_effect = Exception("SES error")

        with pytest.raises(Exception, match="SES error"):
            await ses.get_send_quota()


class TestGetSendStatistics:
    """Test send statistics functionality."""

    @pytest.mark.asyncio
    async def test_get_send_statistics_success(self, mock_session):
        """Test successful send statistics retrieval."""
        mock_session_obj, mock_client = mock_session
        expected_stats = {
            "SendDataPoints": [
                {
                    "Timestamp": "2023-01-01T00:00:00Z",
                    "DeliveryAttempts": 10,
                    "Bounces": 0,
                    "Complaints": 0,
                    "Rejects": 0
                }
            ]
        }
        mock_client.get_send_statistics.return_value = expected_stats

        result = await ses.get_send_statistics()

        mock_client.get_send_statistics.assert_called_once()
        assert result == expected_stats

    @pytest.mark.asyncio
    async def test_get_send_statistics_error(self, mock_session):
        """Test send statistics with SES error."""
        mock_session_obj, mock_client = mock_session
        mock_client.get_send_statistics.side_effect = Exception("SES error")

        with pytest.raises(Exception, match="SES error"):
            await ses.get_send_statistics()


class TestListVerifiedEmailAddresses:
    """Test verified email addresses listing functionality."""

    @pytest.mark.asyncio
    async def test_list_verified_email_addresses_success(self, mock_session):
        """Test successful verified emails listing."""
        mock_session_obj, mock_client = mock_session
        expected_emails = ["verified1@example.com", "verified2@example.com"]
        mock_client.list_verified_email_addresses.return_value = {
            'VerifiedEmailAddresses': expected_emails
        }

        result = await ses.list_verified_email_addresses()

        mock_client.list_verified_email_addresses.assert_called_once()
        assert result == expected_emails

    @pytest.mark.asyncio
    async def test_list_verified_email_addresses_empty(self, mock_session):
        """Test verified emails listing with empty result."""
        mock_session_obj, mock_client = mock_session
        mock_client.list_verified_email_addresses.return_value = {}

        result = await ses.list_verified_email_addresses()

        assert result == []

    @pytest.mark.asyncio
    async def test_list_verified_email_addresses_error(self, mock_session):
        """Test verified emails listing with SES error."""
        mock_session_obj, mock_client = mock_session
        mock_client.list_verified_email_addresses.side_effect = Exception("SES error")

        with pytest.raises(Exception, match="SES error"):
            await ses.list_verified_email_addresses()


class TestCreateTemplate:
    """Test template creation functionality."""

    @pytest.mark.asyncio
    async def test_create_template_text_only(self, mock_session):
        """Test creating text-only template."""
        mock_session_obj, mock_client = mock_session
        mock_client.create_template.return_value = {}

        result = await ses.create_template(
            template_name="TestTemplate",
            subject="Welcome {{name}}",
            text_part="Hello {{name}}, welcome to our service!"
        )

        mock_client.create_template.assert_called_once()
        call_args = mock_client.create_template.call_args[1]
        template = call_args["Template"]

        assert template["TemplateName"] == "TestTemplate"
        assert template["Subject"] == "Welcome {{name}}"
        assert template["TextPart"] == "Hello {{name}}, welcome to our service!"
        assert "HtmlPart" not in template
        assert result == {}

    @pytest.mark.asyncio
    async def test_create_template_with_html(self, mock_session):
        """Test creating template with HTML part."""
        mock_session_obj, mock_client = mock_session
        mock_client.create_template.return_value = {}

        await ses.create_template(
            template_name="HtmlTemplate",
            subject="Welcome {{name}}",
            text_part="Hello {{name}}",
            html_part="<h1>Hello {{name}}</h1>"
        )

        call_args = mock_client.create_template.call_args[1]
        template = call_args["Template"]
        assert template["HtmlPart"] == "<h1>Hello {{name}}</h1>"

    @pytest.mark.asyncio
    async def test_create_template_error(self, mock_session):
        """Test template creation with SES error."""
        mock_session_obj, mock_client = mock_session
        mock_client.create_template.side_effect = Exception("SES error")

        with pytest.raises(Exception, match="SES error"):
            await ses.create_template(
                template_name="TestTemplate",
                subject="Test",
                text_part="Test body"
            )


class TestDeleteTemplate:
    """Test template deletion functionality."""

    @pytest.mark.asyncio
    async def test_delete_template_success(self, mock_session):
        """Test successful template deletion."""
        mock_session_obj, mock_client = mock_session
        mock_client.delete_template.return_value = {}

        result = await ses.delete_template("TestTemplate")

        mock_client.delete_template.assert_called_once_with(
            TemplateName="TestTemplate"
        )
        assert result == {}

    @pytest.mark.asyncio
    async def test_delete_template_error(self, mock_session):
        """Test template deletion with SES error."""
        mock_session_obj, mock_client = mock_session
        mock_client.delete_template.side_effect = Exception("SES error")

        with pytest.raises(Exception, match="SES error"):
            await ses.delete_template("TestTemplate")


class TestGetTemplate:
    """Test template retrieval functionality."""

    @pytest.mark.asyncio
    async def test_get_template_success(self, mock_session):
        """Test successful template retrieval."""
        mock_session_obj, mock_client = mock_session
        expected_template = {
            "Template": {
                "TemplateName": "TestTemplate",
                "Subject": "Test Subject",
                "TextPart": "Test body"
            }
        }
        mock_client.get_template.return_value = expected_template

        result = await ses.get_template("TestTemplate")

        mock_client.get_template.assert_called_once_with(
            TemplateName="TestTemplate"
        )
        assert result == expected_template

    @pytest.mark.asyncio
    async def test_get_template_error(self, mock_session):
        """Test template retrieval with SES error."""
        mock_session_obj, mock_client = mock_session
        mock_client.get_template.side_effect = Exception("SES error")

        with pytest.raises(Exception, match="SES error"):
            await ses.get_template("TestTemplate")


class TestErrorHandling:
    """Test error handling scenarios."""

    @pytest.mark.asyncio
    async def test_session_creation_error(self):
        """Test handling of session creation errors."""
        with patch('media_summarizer.utils.ses.session') as mock_session:
            mock_session.create_client.side_effect = Exception("Session error")

            with pytest.raises(Exception, match="Session error"):
                await ses.send_email("test@example.com", "Subject", "Body")

    @pytest.mark.asyncio
    async def test_generic_exception_handling(self, mock_session):
        """Test handling of generic exceptions."""
        mock_session_obj, mock_client = mock_session
        mock_client.send_email.side_effect = Exception("Network error")

        with pytest.raises(Exception, match="Network error"):
            await ses.send_email("test@example.com", "Subject", "Body")
