"""
Base test classes for Media Summarizer tests.

This module provides base classes for different types of tests,
helping to standardize test patterns and reduce code duplication.
"""
import os
import pytest
import pytest_asyncio
from unittest.mock import patch, MagicMock, AsyncMock
from typing import Dict, Any, Optional
from dotenv import load_dotenv

from media_summarizer.tests.utils.helpers import (
    create_sqs_message,
    create_api_auth_headers,
    assert_sqs_message_sent,
    assert_s3_file_uploaded,
    assert_email_sent
)
from media_summarizer.tests.utils.docker_service_utils import (
    ensure_docker_services,
    DockerServiceError
)
from media_summarizer.tests.utils.real_whisper_client import (
    create_real_whisper_client,
    create_async_whisper_client,
    check_whisper_connection
)
from media_summarizer.tests.utils.real_worker_clients import (
    create_workflow_client,
    create_rss_worker_client,
    create_download_worker_client,
    create_transcription_worker_client,
    create_summarization_worker_client,
    create_email_worker_client
)
from media_summarizer.tests.utils.real_whisper_client import (
    create_async_whisper_client,
    check_whisper_connection
)
from media_summarizer.tests.utils.httpx_test_server import (
    httpx_test_server,
    HTTPXTestClient,
    load_test_rss_feed
)


class BaseTestCase:
    """Base class for all test cases."""

    def create_sqs_message(self, body, message_id="msg-123", receipt_handle="receipt-123"):
        """Create a mock SQS message for testing."""
        return create_sqs_message(body, message_id, receipt_handle)

    def create_api_auth_headers(self, user_id="test-user"):
        """Create mock authentication headers for API tests."""
        return create_api_auth_headers(user_id)

    def assert_sqs_message_sent(self, mock_sqs_client, expected_queue_url=None, expected_body_contains=None):
        """Assert that a message was sent to SQS with the expected content."""
        return assert_sqs_message_sent(mock_sqs_client, expected_queue_url, expected_body_contains)

    def assert_s3_file_uploaded(self, mock_s3_client, expected_bucket=None, expected_key_prefix=None):
        """Assert that a file was uploaded to S3."""
        return assert_s3_file_uploaded(mock_s3_client, expected_bucket, expected_key_prefix)

    def assert_email_sent(self, mock_ses_client, expected_recipient=None, expected_subject_contains=None, expected_body_contains=None):
        """Assert that an email was sent with the expected content."""
        return assert_email_sent(mock_ses_client, expected_recipient, expected_subject_contains, expected_body_contains)


class BaseUnitTestCase(BaseTestCase):
    """Base class for unit tests."""

    @pytest.fixture
    def mock_sqs_client(self):
        """Mock SQS client for testing."""
        mock_client = AsyncMock()
        mock_client.send_message = AsyncMock(
            return_value={"MessageId": "test-message-id"})
        mock_client.receive_message = AsyncMock(return_value={"Messages": [
            {
                "MessageId": "test-message-id",
                "ReceiptHandle": "test-receipt-handle",
                "Body": '{"key": "value"}',
                "Attributes": {"SentTimestamp": "1234567890"}
            }
        ]})
        mock_client.delete_message = AsyncMock(return_value={})
        return mock_client

    @pytest.fixture
    def mock_s3_client(self):
        """Mock S3 client for testing."""
        mock_client = AsyncMock()
        mock_client.upload_file = AsyncMock(return_value={})
        mock_client.download_file = AsyncMock(return_value={})
        mock_client.generate_presigned_url = AsyncMock(
            return_value="https://example.com/presigned-url")
        return mock_client

    @pytest.fixture
    def mock_ses_client(self):
        """Mock SES client for testing."""
        mock_client = AsyncMock()
        mock_client.send_email = AsyncMock(
            return_value={"MessageId": "test-message-id"})
        return mock_client

    @pytest.fixture
    def mock_db_session(self):
        """Mock database session for testing."""
        mock_session = AsyncMock()
        mock_session.execute = AsyncMock()
        mock_session.commit = AsyncMock()
        mock_session.rollback = AsyncMock()
        mock_session.close = AsyncMock()
        return mock_session


class BaseWorkerTestCase(BaseUnitTestCase):
    """Base class for worker tests."""

    @pytest.fixture
    def sample_message(self):
        """Create a sample SQS message for testing."""
        return self.create_sqs_message({"job_id": "test-job-id", "status": "pending"})

    @pytest.fixture
    def mock_worker_dependencies(self):
        """Mock common worker dependencies."""
        with patch("boto3.client") as mock_boto3:
            mock_sqs = AsyncMock()
            mock_s3 = AsyncMock()
            mock_ses = AsyncMock()

            def get_mock_client(service_name, *args, **kwargs):
                if service_name == "sqs":
                    return mock_sqs
                elif service_name == "s3":
                    return mock_s3
                elif service_name == "ses":
                    return mock_ses
                else:
                    return AsyncMock()

            mock_boto3.side_effect = get_mock_client

            yield {
                "sqs": mock_sqs,
                "s3": mock_s3,
                "ses": mock_ses
            }


class BaseAdapterTestCase(BaseUnitTestCase):
    """Base class for adapter tests."""

    @pytest.fixture
    def mock_aws_session(self):
        """Mock AWS session for testing."""
        with patch("aiobotocore.session.get_session") as mock_session:
            mock_client = AsyncMock()
            mock_session.create_client.return_value.__aenter__.return_value = mock_client
            yield mock_client


class BaseAPITestCase(BaseTestCase):
    """Base class for API tests."""

    @pytest.fixture
    def test_client(self):
        """Create a FastAPI test client."""
        from fastapi.testclient import TestClient
        from media_summarizer.api.main import app
        return TestClient(app)

    @pytest.fixture
    def mock_user_auth(self):
        """Create a mock user authentication middleware."""
        with patch("media_summarizer.api.dependencies.auth.get_current_user") as mock_auth:
            mock_auth.return_value = {
                "id": "test-user-id",
                "email": "user@example.com",
                "credits": 100
            }
            yield mock_auth


class BaseIntegrationTestCase(BaseTestCase):
    """Base class for integration tests."""

    @pytest.fixture(autouse=True)
    def setup_env(self):
        """Set up environment variables for testing."""
        # Load environment variables from .env file
        load_dotenv()
        yield

    @pytest.fixture(autouse=True)
    def setup_localstack_env(self):
        """Set up environment variables for LocalStack."""
        original_env = {}
        env_vars = {
            "AWS_ACCESS_KEY_ID": "test",
            "AWS_SECRET_ACCESS_KEY": "test",
            "AWS_DEFAULT_REGION": "us-east-1",
            "AWS_ENDPOINT_URL": "http://localhost:4566"
        }

        # Save original values and set test values
        for key, value in env_vars.items():
            original_env[key] = os.environ.get(key)
            os.environ[key] = value

        yield

        # Restore original values
        for key, value in original_env.items():
            if value is None:
                if key in os.environ:
                    del os.environ[key]
            else:
                os.environ[key] = value

    @pytest.fixture
    def test_client(self):
        """Create a FastAPI test client."""
        from fastapi.testclient import TestClient
        from media_summarizer.api.main import app
        return TestClient(app)

    @pytest.fixture(autouse=True)
    def setup_localstack_resources(self):
        """Set up LocalStack resources for testing."""
        from media_summarizer.tests.utils.localstack_helpers import setup_localstack_resources
        setup_localstack_resources()
        yield

    @pytest.fixture
    def localstack_sqs_client(self):
        """Create a real SQS client connected to LocalStack."""
        import boto3
        client = boto3.client(
            "sqs",
            endpoint_url=os.environ["AWS_ENDPOINT_URL"],
            region_name=os.environ["AWS_DEFAULT_REGION"],
            aws_access_key_id=os.environ["AWS_ACCESS_KEY_ID"],
            aws_secret_access_key=os.environ["AWS_SECRET_ACCESS_KEY"]
        )

        # Standard queue names used in the application
        queues = [
            "audio-download-queue",
            "transcription-queue",
            "summarization-queue",
            "email-notification-queue"
        ]

        # Get actual queue URLs from SQS
        client.queue_urls = {}
        for queue_name in queues:
            try:
                # Try to get the queue URL
                response = client.get_queue_url(QueueName=queue_name)
                queue_url = response['QueueUrl']
                client.queue_urls[queue_name] = queue_url
                print(f"Found queue {queue_name} at URL: {queue_url}")
            except client.exceptions.QueueDoesNotExist:
                # If queue doesn't exist, create it and get the URL
                response = client.create_queue(QueueName=queue_name)
                queue_url = response['QueueUrl']
                client.queue_urls[queue_name] = queue_url
                print(f"Created queue {queue_name} at URL: {queue_url}")
            except Exception as e:
                print(f"Error with queue {queue_name}: {e}")
                # Fallback to old format
                queue_url = f"{os.environ['AWS_ENDPOINT_URL']}/000000000000/{queue_name}"
                client.queue_urls[queue_name] = queue_url

        yield client

        # Clean up queues after tests by purging them
        for queue_name in queues:
            try:
                queue_url = client.queue_urls[queue_name]
                client.purge_queue(QueueUrl=queue_url)
            except Exception as e:
                print(f"Failed to purge queue {queue_name}: {e}")

    @pytest.fixture
    def localstack_s3_client(self):
        """Create a real S3 client connected to LocalStack."""
        import boto3
        client = boto3.client(
            "s3",
            endpoint_url=os.environ["AWS_ENDPOINT_URL"],
            region_name=os.environ["AWS_DEFAULT_REGION"],
            aws_access_key_id=os.environ["AWS_ACCESS_KEY_ID"],
            aws_secret_access_key=os.environ["AWS_SECRET_ACCESS_KEY"]
        )

        # Create test buckets
        buckets = [
            "media-summarizer-audio",
            "media-summarizer-transcriptions",
            "media-summarizer-summaries"
        ]

        created_buckets = []
        for bucket in buckets:
            try:
                client.create_bucket(Bucket=bucket)
                created_buckets.append(bucket)
            except Exception as e:
                print(f"Bucket {bucket} might already exist: {e}")
                created_buckets.append(bucket)

        # Add bucket names to the client for easy access
        client.buckets = created_buckets

        yield client

    @pytest.fixture
    async def real_whisper_client(self):
        """Create a real Whisper client connected to Docker service."""
        if not check_whisper_connection():
            pytest.skip("Whisper Docker service not available")

        return create_async_whisper_client()

    @pytest.fixture
    async def httpx_server(self):
        """Create httpx async test server for HTTP requests."""
        async with httpx_test_server(host="127.0.0.1", port=8001) as server:
            # Add test RSS feed
            rss_content = load_test_rss_feed()
            server.add_rss_feed("/podcast.xml", rss_content)

            # Add test audio file
            audio_content = b"fake audio content for testing"
            server.add_audio_file("/episode.mp3", audio_content)

            yield server

    @pytest.fixture
    def httpx_test_client(self):
        """Create httpx test client for making HTTP requests."""
        return HTTPXTestClient

        # Clean up test objects after tests
        for bucket in created_buckets:
            try:
                # List and delete all objects in the bucket
                response = client.list_objects_v2(Bucket=bucket)
                if "Contents" in response:
                    for obj in response["Contents"]:
                        client.delete_object(Bucket=bucket, Key=obj["Key"])
            except Exception as e:
                print(f"Failed to clean up bucket {bucket}: {e}")

    @pytest.fixture
    def localstack_ses_client(self):
        """Create a real SES client connected to LocalStack."""
        import boto3
        client = boto3.client(
            "ses",
            endpoint_url=os.environ["AWS_ENDPOINT_URL"],
            region_name=os.environ["AWS_DEFAULT_REGION"],
            aws_access_key_id=os.environ["AWS_ACCESS_KEY_ID"],
            aws_secret_access_key=os.environ["AWS_SECRET_ACCESS_KEY"]
        )

        # Verify email identities for testing
        test_emails = [
            "sender@example.com",
            "user@example.com",
            "admin@example.com"
        ]

        for email in test_emails:
            try:
                client.verify_email_identity(EmailAddress=email)
            except Exception as e:
                print(f"Failed to verify email {email}: {e}")

        yield client

    @pytest.fixture
    def localstack_dynamodb_client(self):
        """Create a real DynamoDB client connected to LocalStack."""
        from media_summarizer.tests.utils.dynamodb_localstack import create_dynamodb_localstack_client

        client = create_dynamodb_localstack_client()

        # Skip test if LocalStack is not available
        if not client.is_available():
            pytest.skip("DynamoDB LocalStack service not available")

        # Set up tables
        client.setup_tables()

        yield client

        # Clean up
        client.clear_tables()

    @pytest.fixture
    def openai_mock(self):
        """Create OpenAI mock for LLM API calls."""
        from media_summarizer.tests.utils.openai_mock import create_openai_mock_client
        from unittest.mock import patch

        mock_client = create_openai_mock_client()

        # Set default summarization response
        mock_client.set_chat_completion_response(
            "This is a mock summary of the podcast episode. "
            "Key topics: technology, innovation, future trends. "
            "Main insights: The discussion covers emerging technologies and their impact on society."
        )

        # Patch OpenAI API calls
        with patch("openai.ChatCompletion.create", mock_client.create_chat_completion):
            with patch("openai.ChatCompletion.acreate", mock_client.acreate_chat_completion):
                yield mock_client

        mock_client.reset()

    @pytest.fixture
    def mock_db_session(self):
        """Mock database session for testing."""
        mock_session = AsyncMock()
        mock_session.execute = AsyncMock()
        mock_session.commit = AsyncMock()
        mock_session.rollback = AsyncMock()
        mock_session.close = AsyncMock()

        with patch("media_summarizer.adapters.database.connection.get_db", return_value=mock_session):
            yield mock_session

    # For backward compatibility, provide the mock clients as well
    @pytest.fixture
    def mock_sqs_client(self, localstack_sqs_client):
        """For backward compatibility - returns the LocalStack SQS client."""
        return localstack_sqs_client

    @pytest.fixture
    def mock_s3_client(self, localstack_s3_client):
        """For backward compatibility - returns the LocalStack S3 client."""
        return localstack_s3_client

    @pytest.fixture
    def mock_ses_client(self, localstack_ses_client):
        """For backward compatibility - returns the LocalStack SES client."""
        return localstack_ses_client

    @pytest.fixture
    def stripe_client(self):
        """Create a real Stripe client using the test API key from .env."""
        import stripe
        # Get the Stripe API key from environment variables
        stripe_api_key = os.environ.get("STRIPE_API_KEY")
        if not stripe_api_key:
            pytest.skip(
                "STRIPE_API_KEY not found in environment variables")

        # Configure the Stripe library with the test API key
        stripe.api_key = stripe_api_key

        # Return the stripe module itself as the client
        return stripe

    # Real service fixtures for integration tests
    @pytest.fixture(autouse=True)
    def ensure_docker_services_running(self):
        """Ensure all required Docker services are running before tests."""
        try:
            # Do a simple synchronous check instead of async
            from media_summarizer.tests.utils.docker_service_utils import DockerClient
            docker_client = DockerClient()
            containers = docker_client.get_running_containers()

            # Check if we have some basic containers running
            if len(containers) == 0:
                pytest.skip("No Docker containers running")

            # Check for LocalStack specifically
            localstack_running = any("localstack" in name.lower() for name in containers)
            if not localstack_running:
                pytest.skip("LocalStack container not running")

        except Exception as e:
            pytest.skip(f"Docker service check failed: {e}")

    @pytest.fixture
    def real_whisper_client(self):
        """Create a real Whisper client that connects to the Docker service."""
        if not check_whisper_connection():
            pytest.skip("Whisper service is not available")
        return create_real_whisper_client()

    @pytest.fixture
    def async_whisper_client(self):
        """Create an async real Whisper client."""
        if not check_whisper_connection():
            pytest.skip("Whisper service is not available")
        return create_async_whisper_client()

    @pytest.fixture
    def real_rss_worker_client(self):
        """Create a real RSS worker client."""
        client = create_rss_worker_client()
        if not client.is_available():
            pytest.skip("RSS worker service is not available")
        return client

    @pytest.fixture
    def real_download_worker_client(self):
        """Create a real download worker client."""
        client = create_download_worker_client()
        if not client.is_available():
            pytest.skip("Download worker service is not available")
        return client

    @pytest.fixture
    def real_transcription_worker_client(self):
        """Create a real transcription worker client."""
        client = create_transcription_worker_client()
        if not client.is_available():
            pytest.skip("Transcription worker service is not available")
        return client

    @pytest.fixture
    def real_summarization_worker_client(self):
        """Create a real summarization worker client."""
        client = create_summarization_worker_client()
        if not client.is_available():
            pytest.skip("Summarization worker service is not available")
        return client

    @pytest.fixture
    def real_email_worker_client(self):
        """Create a real email worker client."""
        client = create_email_worker_client()
        if not client.is_available():
            pytest.skip("Email worker service is not available")
        return client

    @pytest.fixture
    def real_workflow_client(self):
        """Create a complete workflow client for end-to-end testing."""
        client = create_workflow_client()
        unavailable_workers = client.get_unavailable_workers()
        if unavailable_workers:
            pytest.skip(f"Required workers not available: {unavailable_workers}")
        return client

    @pytest.fixture
    def sample_audio_file(self):
        """Create a sample audio file for testing."""
        from media_summarizer.tests.utils.audio_helpers import create_test_audio_file, cleanup_test_audio_file

        # Create a proper test audio file
        audio_path = create_test_audio_file(duration_seconds=5)  # Short file for faster tests
        yield audio_path

        # Clean up the temporary file
        cleanup_test_audio_file(audio_path)

    @pytest.fixture
    def http_server(self):
        """Create a real HTTP server for testing RSS feeds and audio downloads."""
        from media_summarizer.tests.utils.http_server_helpers import TestHTTPServer

        server = TestHTTPServer(port=8001)
        server.start()
        yield server
        server.stop()
