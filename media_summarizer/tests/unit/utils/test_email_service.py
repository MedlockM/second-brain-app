"""
Unit tests for email service (email verification + welcome emails).
"""
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from botocore.exceptions import ClientError
from media_summarizer.utils.email_service import EmailService, email_service


class TestEmailService:
    """Test EmailService class."""

    def test_init(self):
        """Test EmailService initialization."""
        service = EmailService()

        assert service.from_email is not None
        assert service.frontend_url is not None
        assert isinstance(service.from_email, str)
        assert isinstance(service.frontend_url, str)

    @patch.dict('os.environ', {
        'FROM_EMAIL': 'test@example.com',
        'FRONTEND_URL': 'https://test.com',
        'EMAIL_VERIFICATION_EXPIRE_HOURS': '48'
    })
    def test_init_with_environment_vars(self):
        """Test EmailService initialization with environment variables."""
        service = EmailService()

        assert service.from_email == 'test@example.com'
        assert service.frontend_url == 'https://test.com'
        assert service.email_verification_expire_hours == 48

    @pytest.mark.asyncio
    async def test_send_email_verification_success(self):
        """Test successful email verification email sending."""
        service = EmailService()
        email = "test@example.com"
        verification_token = "test-verification-token-123"

        # Mock SES client
        mock_ses_client = AsyncMock()
        mock_ses_client.send_email.return_value = {'MessageId': 'test-message-id'}

        with patch('media_summarizer.utils.email_service.get_session') as mock_get_session:
            mock_session = MagicMock()
            mock_get_session.return_value = mock_session
            mock_session.client.return_value.__aenter__.return_value = mock_ses_client

            result = await service.send_email_verification(email, verification_token)

            assert result is True
            mock_ses_client.send_email.assert_called_once()

            # Verify email content
            call_args = mock_ses_client.send_email.call_args
            assert call_args[1]['Source'] == service.from_email
            assert call_args[1]['Destination']['ToAddresses'] == [email]

            message = call_args[1]['Message']
            assert 'Verify your email' in message['Subject']['Data']
            assert verification_token in message['Body']['Html']['Data']
            assert verification_token in message['Body']['Text']['Data']

    @pytest.mark.asyncio
    async def test_send_email_verification_with_custom_frontend_url(self):
        """Test email verification with custom frontend URL."""
        service = EmailService()
        service.frontend_url = "https://custom.example.com"
        email = "test@example.com"
        verification_token = "test-verification-token-123"

        mock_ses_client = AsyncMock()
        mock_ses_client.send_email.return_value = {'MessageId': 'test-message-id'}

        with patch('media_summarizer.utils.email_service.get_session') as mock_get_session:
            mock_session = MagicMock()
            mock_get_session.return_value = mock_session
            mock_session.client.return_value.__aenter__.return_value = mock_ses_client

            result = await service.send_email_verification(email, verification_token)

            assert result is True

            # Check that custom frontend URL is used
            call_args = mock_ses_client.send_email.call_args
            html_body = call_args[1]['Message']['Body']['Html']['Data']
            text_body = call_args[1]['Message']['Body']['Text']['Data']

            expected_link = f"https://custom.example.com/verify-email?token={verification_token}&email={email}"
            assert expected_link in html_body
            assert expected_link in text_body

    @pytest.mark.asyncio
    async def test_send_email_verification_ses_error(self):
        """Test email verification sending with SES error."""
        service = EmailService()
        email = "test@example.com"
        verification_token = "test-verification-token-123"

        # Mock SES client error
        mock_ses_client = AsyncMock()
        mock_ses_client.send_email.side_effect = ClientError(
            {'Error': {'Code': 'MessageRejected', 'Message': 'Email rejected'}},
            'SendEmail'
        )

        with patch('media_summarizer.utils.email_service.get_session') as mock_get_session:
            mock_session = MagicMock()
            mock_get_session.return_value = mock_session
            mock_session.client.return_value.__aenter__.return_value = mock_ses_client

            result = await service.send_email_verification(email, verification_token)

            assert result is False
            mock_ses_client.send_email.assert_called_once()

    @pytest.mark.asyncio
    async def test_send_email_verification_unexpected_error(self):
        """Test email verification sending with unexpected error."""
        service = EmailService()
        email = "test@example.com"
        verification_token = "test-verification-token-123"

        # Mock unexpected error
        mock_ses_client = AsyncMock()
        mock_ses_client.send_email.side_effect = Exception("Unexpected error")

        with patch('media_summarizer.utils.email_service.get_session') as mock_get_session:
            mock_session = MagicMock()
            mock_get_session.return_value = mock_session
            mock_session.client.return_value.__aenter__.return_value = mock_ses_client

            result = await service.send_email_verification(email, verification_token)

            assert result is False

    @pytest.mark.asyncio
    async def test_send_welcome_email_success(self):
        """Test successful welcome email sending."""
        service = EmailService()
        email = "newuser@example.com"
        credits = 150

        mock_ses_client = AsyncMock()
        mock_ses_client.send_email.return_value = {'MessageId': 'welcome-message-id'}

        with patch('media_summarizer.utils.email_service.get_session') as mock_get_session:
            mock_session = MagicMock()
            mock_get_session.return_value = mock_session
            mock_session.client.return_value.__aenter__.return_value = mock_ses_client

            result = await service.send_welcome_email(email, credits)

            assert result is True
            mock_ses_client.send_email.assert_called_once()

            # Verify email content
            call_args = mock_ses_client.send_email.call_args
            assert call_args[1]['Source'] == service.from_email
            assert call_args[1]['Destination']['ToAddresses'] == [email]

            message = call_args[1]['Message']
            assert 'Welcome to Media Summarizer!' in message['Subject']['Data']

            html_body = message['Body']['Html']['Data']
            text_body = message['Body']['Text']['Data']
            assert str(credits) in html_body
            assert str(credits) in text_body

    @pytest.mark.asyncio
    async def test_send_welcome_email_default_credits(self):
        """Test welcome email with default credits."""
        service = EmailService()
        email = "newuser@example.com"

        mock_ses_client = AsyncMock()
        mock_ses_client.send_email.return_value = {'MessageId': 'welcome-message-id'}

        with patch('media_summarizer.utils.email_service.get_session') as mock_get_session:
            mock_session = MagicMock()
            mock_get_session.return_value = mock_session
            mock_session.client.return_value.__aenter__.return_value = mock_ses_client

            result = await service.send_welcome_email(email)

            assert result is True

            # Check default credits (100) are mentioned
            call_args = mock_ses_client.send_email.call_args
            html_body = call_args[1]['Message']['Body']['Html']['Data']
            assert '100' in html_body

    @pytest.mark.asyncio
    async def test_send_welcome_email_ses_error(self):
        """Test welcome email sending with SES error."""
        service = EmailService()
        email = "newuser@example.com"

        mock_ses_client = AsyncMock()
        mock_ses_client.send_email.side_effect = ClientError(
            {'Error': {'Code': 'SendingPausedException', 'Message': 'Sending paused'}},
            'SendEmail'
        )

        with patch('media_summarizer.utils.email_service.get_session') as mock_get_session:
            mock_session = MagicMock()
            mock_get_session.return_value = mock_session
            mock_session.client.return_value.__aenter__.return_value = mock_ses_client

            result = await service.send_welcome_email(email)

            assert result is False

    @pytest.mark.asyncio
    async def test_send_email_private_method(self):
        """Test the private _send_email method."""
        service = EmailService()
        to_email = "test@example.com"
        subject = "Test Subject"
        html_body = "<h1>Test HTML</h1>"
        text_body = "Test Text"

        mock_ses_client = AsyncMock()
        mock_ses_client.send_email.return_value = {'MessageId': 'test-message-id'}

        with patch('media_summarizer.utils.email_service.get_session') as mock_get_session:
            mock_session = MagicMock()
            mock_get_session.return_value = mock_session
            mock_session.client.return_value.__aenter__.return_value = mock_ses_client

            result = await service._send_email(to_email, subject, html_body, text_body)

            assert result is True
            mock_ses_client.send_email.assert_called_once()

            call_args = mock_ses_client.send_email.call_args
            assert call_args[1]['Source'] == service.from_email
            assert call_args[1]['Destination']['ToAddresses'] == [to_email]
            assert call_args[1]['Message']['Subject']['Data'] == subject
            assert call_args[1]['Message']['Body']['Html']['Data'] == html_body
            assert call_args[1]['Message']['Body']['Text']['Data'] == text_body
            assert call_args[1]['ReplyToAddresses'] == []

    @pytest.mark.asyncio
    async def test_send_email_with_reply_to(self):
        """Test _send_email method with reply-to address."""
        service = EmailService()
        to_email = "test@example.com"
        subject = "Test Subject"
        html_body = "<h1>Test HTML</h1>"
        text_body = "Test Text"
        reply_to = "support@example.com"

        mock_ses_client = AsyncMock()
        mock_ses_client.send_email.return_value = {'MessageId': 'test-message-id'}

        with patch('media_summarizer.utils.email_service.get_session') as mock_get_session:
            mock_session = MagicMock()
            mock_get_session.return_value = mock_session
            mock_session.client.return_value.__aenter__.return_value = mock_ses_client

            result = await service._send_email(to_email, subject, html_body, text_body, reply_to)

            assert result is True

            call_args = mock_ses_client.send_email.call_args
            assert call_args[1]['ReplyToAddresses'] == [reply_to]

    @pytest.mark.asyncio
    async def test_verify_email_address_success(self):
        """Test successful email verification."""
        service = EmailService()
        email = "test@example.com"

        mock_ses_client = AsyncMock()
        mock_ses_client.verify_email_identity.return_value = {}

        with patch('media_summarizer.utils.email_service.get_session') as mock_get_session:
            mock_session = MagicMock()
            mock_get_session.return_value = mock_session
            mock_session.client.return_value.__aenter__.return_value = mock_ses_client

            result = await service.verify_email_address(email)

            assert result is True
            mock_ses_client.verify_email_identity.assert_called_once_with(EmailAddress=email)

    @pytest.mark.asyncio
    async def test_verify_email_address_error(self):
        """Test email verification with error."""
        service = EmailService()
        email = "test@example.com"

        mock_ses_client = AsyncMock()
        mock_ses_client.verify_email_identity.side_effect = ClientError(
            {'Error': {'Code': 'InvalidParameterValue', 'Message': 'Invalid email'}},
            'VerifyEmailIdentity'
        )

        with patch('media_summarizer.utils.email_service.get_session') as mock_get_session:
            mock_session = MagicMock()
            mock_get_session.return_value = mock_session
            mock_session.client.return_value.__aenter__.return_value = mock_ses_client

            result = await service.verify_email_address(email)

            assert result is False

    @pytest.mark.asyncio
    async def test_check_sending_quota_success(self):
        """Test successful quota checking."""
        service = EmailService()

        mock_quota_response = {
            'Max24HourSend': 1000.0,
            'MaxSendRate': 5.0,
            'SentLast24Hours': 50.0
        }
        mock_stats_response = {
            'SendDataPoints': [
                {
                    'Timestamp': '2024-01-01T00:00:00Z',
                    'DeliveryAttempts': 10,
                    'Bounces': 0,
                    'Complaints': 0,
                    'Rejects': 0
                }
            ]
        }

        mock_ses_client = AsyncMock()
        mock_ses_client.get_send_quota.return_value = mock_quota_response
        mock_ses_client.get_send_statistics.return_value = mock_stats_response

        with patch('media_summarizer.utils.email_service.get_session') as mock_get_session:
            mock_session = MagicMock()
            mock_get_session.return_value = mock_session
            mock_session.client.return_value.__aenter__.return_value = mock_ses_client

            result = await service.check_sending_quota()

            assert result['max_24_hour_send'] == 1000.0
            assert result['max_send_rate'] == 5.0
            assert result['sent_last_24_hours'] == 50.0
            assert len(result['send_data_points']) == 1

    @pytest.mark.asyncio
    async def test_check_sending_quota_error(self):
        """Test quota checking with error."""
        service = EmailService()

        mock_ses_client = AsyncMock()
        mock_ses_client.get_send_quota.side_effect = ClientError(
            {'Error': {'Code': 'AccessDenied', 'Message': 'Access denied'}},
            'GetSendQuota'
        )

        with patch('media_summarizer.utils.email_service.get_session') as mock_get_session:
            mock_session = MagicMock()
            mock_get_session.return_value = mock_session
            mock_session.client.return_value.__aenter__.return_value = mock_ses_client

            result = await service.check_sending_quota()

            assert result == {}

    @pytest.mark.asyncio
    async def test_check_sending_quota_unexpected_error(self):
        """Test quota checking with unexpected error."""
        service = EmailService()

        mock_ses_client = AsyncMock()
        mock_ses_client.get_send_quota.side_effect = Exception("Unexpected error")

        with patch('media_summarizer.utils.email_service.get_session') as mock_get_session:
            mock_session = MagicMock()
            mock_get_session.return_value = mock_session
            mock_session.client.return_value.__aenter__.return_value = mock_ses_client

            result = await service.check_sending_quota()

            assert result == {}


class TestEmailTemplates:
    """Test email template content and formatting."""

    @pytest.mark.asyncio
    async def test_email_verification_content(self):
        """Test email verification email contains required elements."""
        service = EmailService()
        email = "test@example.com"
        verification_token = "test-token-123"

        mock_ses_client = AsyncMock()
        mock_ses_client.send_email.return_value = {'MessageId': 'test-id'}

        with patch('media_summarizer.utils.email_service.get_session') as mock_get_session:
            mock_session = MagicMock()
            mock_get_session.return_value = mock_session
            mock_session.client.return_value.__aenter__.return_value = mock_ses_client

            await service.send_email_verification(email, verification_token)

            call_args = mock_ses_client.send_email.call_args
            html_body = call_args[1]['Message']['Body']['Html']['Data']
            text_body = call_args[1]['Message']['Body']['Text']['Data']

            # Check required elements in HTML
            assert 'Verify your email' in html_body
            assert verification_token in html_body
            assert email in html_body
            assert 'This link will expire in' in html_body
            assert 'href=' in html_body  # Should have clickable link

            # Check required elements in text
            assert 'Verify your email' in text_body
            assert verification_token in text_body
            assert 'This link will expire in' in text_body

    @pytest.mark.asyncio
    async def test_welcome_email_content(self):
        """Test welcome email contains required elements."""
        service = EmailService()
        email = "newuser@example.com"
        credits = 100

        mock_ses_client = AsyncMock()
        mock_ses_client.send_email.return_value = {'MessageId': 'test-id'}

        with patch('media_summarizer.utils.email_service.get_session') as mock_get_session:
            mock_session = MagicMock()
            mock_get_session.return_value = mock_session
            mock_session.client.return_value.__aenter__.return_value = mock_ses_client

            await service.send_welcome_email(email, credits)

            call_args = mock_ses_client.send_email.call_args
            html_body = call_args[1]['Message']['Body']['Html']['Data']
            text_body = call_args[1]['Message']['Body']['Text']['Data']

            # Check required elements in HTML
            assert 'Welcome to Media Summarizer' in html_body
            assert str(credits) in html_body
            assert 'credits' in html_body.lower()
            assert service.frontend_url in html_body

            # Check required elements in text
            assert 'Welcome to Media Summarizer' in text_body
            assert str(credits) in text_body
            assert 'credits' in text_body.lower()
            assert service.frontend_url in text_body

    @pytest.mark.asyncio
    async def test_email_html_structure(self):
        """Test that HTML emails have proper structure."""
        service = EmailService()
        email = "test@example.com"
        verification_token = "test-token-123"

        mock_ses_client = AsyncMock()
        mock_ses_client.send_email.return_value = {'MessageId': 'test-id'}

        with patch('media_summarizer.utils.email_service.get_session') as mock_get_session:
            mock_session = MagicMock()
            mock_get_session.return_value = mock_session
            mock_session.client.return_value.__aenter__.return_value = mock_ses_client

            await service.send_email_verification(email, verification_token)

            call_args = mock_ses_client.send_email.call_args
            html_body = call_args[1]['Message']['Body']['Html']['Data']

            # Check HTML structure
            assert '<!DOCTYPE html>' in html_body
            assert '<html>' in html_body
            assert '<head>' in html_body
            assert '<body>' in html_body
            assert '</html>' in html_body
            assert ('charset="utf-8"' in html_body) or ('charset=utf-8' in html_body)
            assert '<style>' in html_body  # Should have CSS styles


class TestEmailServiceSingleton:
    """Test the email service singleton instance."""

    def test_email_service_singleton_exists(self):
        """Test that email_service singleton is available."""
        assert email_service is not None
        assert isinstance(email_service, EmailService)

    def test_email_service_singleton_is_same_instance(self):
        """Test that multiple imports return the same instance."""
        from media_summarizer.utils.email_service import email_service as service1
        from media_summarizer.utils.email_service import email_service as service2

        assert service1 is service2


class TestGetSession:
    """Test session management."""

    @patch('media_summarizer.utils.email_service._session', None)
    def test_get_session_creates_new_session(self):
        """Test that get_session creates a new session when none exists."""
        from media_summarizer.utils.email_service import get_session

        with patch('media_summarizer.utils.email_service.aioboto3.Session') as mock_session_class:
            mock_session = MagicMock()
            mock_session_class.return_value = mock_session

            session = get_session()

            assert session is mock_session
            mock_session_class.assert_called_once()

    def test_get_session_returns_existing_session(self):
        """Test that get_session returns existing session."""
        from media_summarizer.utils.email_service import get_session

        # Mock existing session
        existing_session = MagicMock()

        with patch('media_summarizer.utils.email_service._session', existing_session):
            session = get_session()
            assert session is existing_session

    @patch.dict('os.environ', {
        'AWS_REGION': 'eu-west-1',
        'AWS_ACCESS_KEY_ID': 'test-key',
        'AWS_SECRET_ACCESS_KEY': 'test-secret'
    })
    def test_get_session_with_environment_vars(self):
        """Test session creation with environment variables."""
        from media_summarizer.utils.email_service import get_session

        with patch('media_summarizer.utils.email_service.aioboto3.Session') as mock_session_class:
            with patch('media_summarizer.utils.email_service._session', None):
                get_session()

                mock_session_class.assert_called_once_with(
                    region_name='eu-west-1',
                    aws_access_key_id='test-key',
                    aws_secret_access_key='test-secret'
                )


class TestEnvironmentVariables:
    """Test environment variable handling."""

    @patch.dict('os.environ', {
        'FROM_EMAIL': 'custom@example.com',
        'FRONTEND_URL': 'https://custom.com',
        'EMAIL_VERIFICATION_EXPIRE_HOURS': '30'
    })
    def test_environment_variables_loaded(self):
        """Test that environment variables are properly loaded."""
        # Re-import to pick up new environment variables
        import importlib
        import media_summarizer.utils.email_service
        importlib.reload(media_summarizer.utils.email_service)

        from media_summarizer.utils.email_service import FROM_EMAIL, FRONTEND_URL, EmailService

        assert FROM_EMAIL == 'custom@example.com'
        assert FRONTEND_URL == 'https://custom.com'
        # Instance-level config for verification expiry
        service = EmailService()
        assert service.email_verification_expire_hours == 30

    @patch.dict('os.environ', {}, clear=True)
    def test_default_environment_variables(self):
        """Test default values when environment variables are not set."""
        import importlib
        import media_summarizer.utils.email_service
        importlib.reload(media_summarizer.utils.email_service)

        from media_summarizer.utils.email_service import FROM_EMAIL, FRONTEND_URL, EmailService

        assert FROM_EMAIL == "noreply@example.com"
        assert FRONTEND_URL == "http://localhost:3000"
        # Default email verification expiry hours is 24
        service = EmailService()
        assert service.email_verification_expire_hours == 24


if __name__ == "__main__":
    pytest.main([__file__])
