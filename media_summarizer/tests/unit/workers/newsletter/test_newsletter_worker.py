"""
Unit tests for the newsletter ingestion worker.

Tests cover:
- Media key generation (idempotence)
- User resolution from ingest address
- Message processing flow (happy path and error cases)
- Integration with the summarization queue

The worker module is imported directly from its file path to bypass
missing infrastructure modules in this isolated test environment.
"""

import importlib.util
import json
import os
import sys
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Direct module import with mocked external dependencies
# ---------------------------------------------------------------------------

_WORKER_PATH = os.path.join(
    os.path.dirname(__file__),
    "..", "..", "..", "..",
    "workers", "newsletter", "worker.py",
)
_WORKER_PATH = os.path.abspath(_WORKER_PATH)


@pytest.fixture
def worker_module():
    """Load the newsletter worker module with all external deps mocked."""
    mock_sqs = MagicMock()
    mock_sqs.send_message = AsyncMock()
    mock_sqs.receive_messages = AsyncMock(return_value=[])

    mock_s3 = MagicMock()
    mock_s3.upload_file_object = AsyncMock()
    mock_s3.download_file_to_memory = AsyncMock(return_value=b"")

    mock_db = MagicMock()
    mock_db.create_processing_job = AsyncMock(side_effect=lambda job: job)
    mock_db.update_processing_job = AsyncMock()
    mock_db.get_user_by_ingest_address = AsyncMock(return_value=None)

    mock_minute_pool = MagicMock()
    mock_minute_pool.allocate_hold_for_job = AsyncMock()

    mock_logging = MagicMock()
    mock_logging.bind_log_context = lambda **kw: "token"
    mock_logging.log_event = lambda *a, **kw: None
    mock_logging.reset_log_context = lambda t: None
    mock_logging.setup_logging = lambda *a, **kw: None

    mock_base_worker = MagicMock()
    mock_base_worker.get_sqs_receive_params = MagicMock(return_value={})
    mock_base_worker.process_message_with_retry = AsyncMock()

    # Mock ProcessingJob as a simple class
    class MockProcessingJob:
        def __init__(self, **kwargs):
            self.id = kwargs.get("id", "test-job-id")
            for k, v in kwargs.items():
                setattr(self, k, v)

        def set_transcription_location(self, key):
            self.transcription_s3_key = key

        def mark_summarizing(self):
            self.status = "summarizing"

    mock_models = MagicMock()
    mock_models.ProcessingJob = MockProcessingJob

    mocked_modules = {
        "media_summarizer.utils": MagicMock(
            database_async=mock_db, s3=mock_s3, sqs=mock_sqs
        ),
        "media_summarizer.utils.database_async": mock_db,
        "media_summarizer.utils.s3": mock_s3,
        "media_summarizer.utils.sqs": mock_sqs,
        "media_summarizer.utils.logging_config": mock_logging,
        "media_summarizer.utils.podcastindex_limiter": MagicMock(),
        "media_summarizer.core.models": mock_models,
        "media_summarizer.core.services.minute_pool": mock_minute_pool,
        "media_summarizer.workers.base_worker": mock_base_worker,
    }

    with patch.dict(sys.modules, mocked_modules):
        spec = importlib.util.spec_from_file_location(
            "newsletter_worker_test_module", _WORKER_PATH
        )
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)

        # Attach mocks to the module for test access
        module._mock_sqs = mock_sqs
        module._mock_s3 = mock_s3
        module._mock_db = mock_db
        module._mock_minute_pool = mock_minute_pool

        yield module


# ---------------------------------------------------------------------------
# _generate_media_key tests
# ---------------------------------------------------------------------------


class TestGenerateMediaKey:
    def test_deterministic(self, worker_module):
        """Same inputs always produce the same key."""
        key1 = worker_module._generate_media_key("sender@test.com", "Subject", "2026-04-29")
        key2 = worker_module._generate_media_key("sender@test.com", "Subject", "2026-04-29")
        assert key1 == key2

    def test_different_inputs_different_keys(self, worker_module):
        key1 = worker_module._generate_media_key("sender@test.com", "Subject A", "2026-04-29")
        key2 = worker_module._generate_media_key("sender@test.com", "Subject B", "2026-04-29")
        assert key1 != key2

    def test_prefix(self, worker_module):
        key = worker_module._generate_media_key("sender@test.com", "Subject", "2026-04-29")
        assert key.startswith("newsletter:")

    def test_consistent_length(self, worker_module):
        key = worker_module._generate_media_key("sender@test.com", "Subject", "2026-04-29")
        # "newsletter:" (11) + 32 hex chars = 43
        assert len(key) == 43


# ---------------------------------------------------------------------------
# _resolve_user_from_recipient tests
# ---------------------------------------------------------------------------


class TestResolveUserFromRecipient:
    def test_valid_address(self, worker_module):
        result = worker_module._resolve_user_from_recipient("abc123@ingest.example.com")
        assert result == "abc123"

    def test_empty_address(self, worker_module):
        assert worker_module._resolve_user_from_recipient("") is None

    def test_no_at_sign(self, worker_module):
        assert worker_module._resolve_user_from_recipient("noemail") is None

    def test_empty_local_part(self, worker_module):
        assert worker_module._resolve_user_from_recipient("@ingest.example.com") is None


# ---------------------------------------------------------------------------
# process_newsletter_message tests
# ---------------------------------------------------------------------------


class TestProcessNewsletterMessage:
    @pytest.fixture
    def mock_user(self):
        user = MagicMock()
        user.id = "user-123"
        user.email = "user@example.com"
        return user

    def _make_valid_email(self):
        """A valid newsletter email body (plain text, long enough)."""
        body = "This is newsletter content about AI and technology. " * 20
        return (
            "From: TLDR <newsletter@tldr.tech>\r\n"
            "To: abc123@ingest.example.com\r\n"
            "Subject: TLDR AI #100\r\n"
            "Date: Mon, 29 Apr 2026 08:00:00 +0000\r\n"
            "Content-Type: text/plain; charset=utf-8\r\n"
            "\r\n"
            f"{body}"
        )

    @pytest.mark.asyncio
    async def test_happy_path(self, worker_module, mock_user):
        """Test successful newsletter processing end-to-end."""
        worker_module._lookup_user_by_ingest_address = AsyncMock(return_value=mock_user)

        message = {
            "raw_email": self._make_valid_email(),
            "recipient": "abc123@ingest.example.com",
            "source": "ses",
        }

        await worker_module.process_newsletter_message(message)

        # Verify S3 upload was called (transcript storage)
        worker_module._mock_s3.upload_file_object.assert_called_once()
        call_kwargs = worker_module._mock_s3.upload_file_object.call_args[1]
        assert call_kwargs["content_type"] == "text/plain"

        # Verify summarization queue message was sent
        worker_module._mock_sqs.send_message.assert_called_once()
        sqs_kwargs = worker_module._mock_sqs.send_message.call_args[1]
        assert sqs_kwargs["queue_name"] == "summarization-queue"
        body = sqs_kwargs["message_body"]
        assert body["email"] == "user@example.com"
        assert "TLDR" in body["podcast_title"]
        assert "TLDR AI #100" in body["episode_title"]

    @pytest.mark.asyncio
    async def test_user_not_found_raises(self, worker_module):
        """Test that unknown recipient raises ValueError."""
        worker_module._lookup_user_by_ingest_address = AsyncMock(return_value=None)

        message = {
            "raw_email": "From: test@test.com\r\nSubject: Test\r\n\r\nBody content here",
            "recipient": "unknown@ingest.example.com",
            "source": "ses",
        }

        with pytest.raises(ValueError, match="Could not identify"):
            await worker_module.process_newsletter_message(message)

    @pytest.mark.asyncio
    async def test_missing_content_raises(self, worker_module):
        """Test that missing raw_email and no S3 reference raises."""
        message = {
            "recipient": "abc123@ingest.example.com",
            "source": "ses",
        }

        with pytest.raises(ValueError, match="did not contain"):
            await worker_module.process_newsletter_message(message)

    @pytest.mark.asyncio
    async def test_s3_email_retrieval(self, worker_module, mock_user):
        """Test fetching email from S3 when not inline."""
        body = "Newsletter from S3 storage content here. " * 20
        raw_email = (
            "From: Test <test@test.com>\r\n"
            "To: abc123@ingest.example.com\r\n"
            "Subject: S3 Newsletter\r\n"
            "Date: Tue, 30 Apr 2026 10:00:00 +0000\r\n"
            "Content-Type: text/plain; charset=utf-8\r\n"
            "\r\n"
            f"{body}"
        )

        worker_module._lookup_user_by_ingest_address = AsyncMock(return_value=mock_user)
        worker_module._mock_s3.download_file_to_memory = AsyncMock(
            return_value=raw_email.encode("utf-8")
        )

        # Patch the module-level s3 reference
        worker_module.s3 = worker_module._mock_s3

        message = {
            "s3_bucket": "ses-emails-bucket",
            "s3_key": "incoming/email-123.eml",
            "recipient": "abc123@ingest.example.com",
            "source": "ses",
        }

        await worker_module.process_newsletter_message(message)

        # Verify S3 download was called for the email
        worker_module._mock_s3.download_file_to_memory.assert_called_once_with(
            bucket="ses-emails-bucket", key="incoming/email-123.eml"
        )
        # Verify summarization was enqueued
        worker_module._mock_sqs.send_message.assert_called_once()
