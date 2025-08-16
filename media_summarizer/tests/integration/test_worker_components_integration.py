"""
Component integration tests for individual podcast workflow workers.

These tests focus on testing individual worker components in isolation with real LocalStack
services but WITHOUT background workers running. They test component interactions
with infrastructure services only.

Environment Requirements:
- LocalStack (SQS, S3, DynamoDB)
- No background workers (isolated testing)
- HTTPx async server for mock endpoints

Test Markers:
- @pytest.mark.component: Component integration test
- @pytest.mark.requires_localstack: Needs LocalStack services
"""
import os
# Set WHISPER_MODEL_SIZE before any worker imports
os.environ.setdefault("WHISPER_MODEL_SIZE", "tiny")
os.environ.setdefault("AWS_ACCESS_KEY_ID", "test")
os.environ.setdefault("AWS_SECRET_ACCESS_KEY", "test")
os.environ.setdefault("AWS_DEFAULT_REGION", "us-east-1")
os.environ.setdefault("AWS_ENDPOINT_URL", "http://localhost:4566")

import json
import pytest
import pytest_asyncio
from unittest.mock import patch, MagicMock, AsyncMock
import uuid
import tempfile
import time
from contextlib import contextmanager

from media_summarizer.tests.utils.base_test_classes import BaseIntegrationTestCase
from media_summarizer.tests.utils.helpers import (
    create_sqs_message,
    set_env_vars,
    restore_env_vars,
    verify_s3_file_exists,
    verify_sqs_message_sent,
    load_fixture_file
)
from media_summarizer.tests.utils.httpx_test_server import (
    httpx_test_server,
    HTTPXTestClient,
    load_test_rss_feed
)

# Worker imports
from media_summarizer.workers.rss_worker import process_message as rss_process_message


# Component test markers
pytestmark = [
    pytest.mark.component,
    pytest.mark.requires_localstack,
    pytest.mark.integration
]


class TestWorkerComponentsIntegration(BaseIntegrationTestCase):
    """Component integration tests for individual podcast workflow workers.

    These tests verify individual worker components in isolation using real LocalStack
    services but no background workers. Each test focuses on a single component's
    interaction with infrastructure services.
    """

    @pytest.fixture(autouse=True)
    def setup_environment(self):
        """Set up environment variables for testing."""
        # Environment variables are already set at module level
        original_values = {}
        yield
        restore_env_vars(original_values)

    @pytest.fixture
    async def httpx_server(self):
        """Create httpx async test server for HTTP requests."""
        async with httpx_test_server(host="127.0.0.1", port=8003) as server:
            # Add test RSS feed
            rss_content = load_test_rss_feed()
            server.add_rss_feed("/podcast.xml", rss_content)

            # Add test audio file
            audio_content = b"fake audio content for testing"
            server.add_audio_file("/episode.mp3", audio_content)

            yield server

    @pytest.mark.asyncio
    @pytest.mark.component
    @pytest.mark.fast
    async def test_rss_worker_component(self, localstack_sqs_client, httpx_server, no_workers):
        """
        Test RSS worker component in isolation with real LocalStack.

        Component Test Scope:
        1. RSS worker processes SQS message correctly
        2. Fetches RSS feed from httpx async server
        3. Sends message to LocalStack SQS queue
        4. No background workers interfering
        """
        job_id = str(uuid.uuid4())

        # Set up RSS feed content on the httpx server
        from media_summarizer.tests.utils.httpx_test_server import load_test_rss_feed
        rss_content = load_test_rss_feed()
        httpx_server.add_rss_feed("/feed.xml", rss_content)

        # Create RSS resolution message pointing to our test HTTP server
        rss_message = create_sqs_message({
            "job_id": job_id,
            "podcast_url": f"{httpx_server.base_url}/feed.xml",
            "email": "user@example.com",
            "user_id": "test-user"
        })

        # Use real LocalStack SQS client
        with patch("media_summarizer.workers.rss_worker.get_sqs_client", return_value=localstack_sqs_client):
            await rss_process_message(rss_message)

        # Verify message was sent to download queue using real LocalStack
        download_queue_url = localstack_sqs_client.queue_urls["audio-download-queue"]
        download_message_body = verify_sqs_message_sent(
            localstack_sqs_client,
            download_queue_url,
            {"job_id": job_id}
        )

        assert download_message_body is not None, "No message sent to download queue"
        assert download_message_body["job_id"] == job_id
        assert download_message_body.get("audio_url") is not None
        assert download_message_body.get("podcast_title") is not None

    # Tous les autres tests de composants workers déplacés depuis unit/