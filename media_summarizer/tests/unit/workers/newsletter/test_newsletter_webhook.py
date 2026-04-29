"""
Unit tests for the newsletter webhook endpoint helpers.

Tests cover:
- SNS notification parsing helpers
- Email content extraction from SES notifications
- Recipient extraction logic

The webhook module is imported directly from its file path to avoid
triggering the full endpoints package __init__.py import chain.
"""

import importlib.util
import os
import sys
from unittest.mock import MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Direct module import bypassing package __init__.py
# ---------------------------------------------------------------------------

_WEBHOOK_PATH = os.path.join(
    os.path.dirname(__file__),
    "..", "..", "..", "..",
    "api", "endpoints", "newsletter_webhook.py",
)
_WEBHOOK_PATH = os.path.abspath(_WEBHOOK_PATH)


@pytest.fixture(autouse=True)
def webhook_module():
    """Load the webhook module directly from file, mocking external deps."""
    # Mock external modules that would be imported
    mock_sqs = MagicMock()
    mock_sqs.send_message = MagicMock()

    mock_logging_config = MagicMock()
    mock_logging_config.bind_log_context = lambda **kw: "token"
    mock_logging_config.log_event = lambda *a, **kw: None
    mock_logging_config.reset_log_context = lambda t: None

    mock_newsletter_errors = MagicMock()
    mock_newsletter_errors.NewsletterIngestionError = MagicMock()

    mocked_modules = {
        "media_summarizer.utils": MagicMock(sqs=mock_sqs),
        "media_summarizer.utils.sqs": mock_sqs,
        "media_summarizer.utils.logging_config": mock_logging_config,
        "media_summarizer.core.services.newsletter_errors": mock_newsletter_errors,
    }

    with patch.dict(sys.modules, mocked_modules):
        spec = importlib.util.spec_from_file_location(
            "newsletter_webhook_test_module", _WEBHOOK_PATH
        )
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        yield module


class TestExtractRecipientsFromSes:
    """Tests for _extract_recipients_from_ses helper."""

    def test_extracts_destinations(self, webhook_module):
        mail = {"destination": ["user@ingest.example.com", "other@test.com"]}
        result = webhook_module._extract_recipients_from_ses(mail)
        assert result == ["user@ingest.example.com", "other@test.com"]

    def test_empty_destination(self, webhook_module):
        assert webhook_module._extract_recipients_from_ses({}) == []
        assert webhook_module._extract_recipients_from_ses({"destination": []}) == []

    def test_non_list_destination(self, webhook_module):
        # If destination is not a list (edge case), return empty
        result = webhook_module._extract_recipients_from_ses({"destination": "single@test.com"})
        assert result == []


class TestExtractEmailContent:
    """Tests for _extract_email_content helper."""

    def test_s3_action(self, webhook_module):
        sns_message = {
            "mail": {
                "messageId": "msg-123",
                "destination": ["user456@ingest.example.com"],
            },
            "receipt": {
                "action": {
                    "type": "S3",
                    "bucketName": "ses-emails",
                    "objectKey": "incoming/msg-123",
                }
            },
        }

        result = webhook_module._extract_email_content(sns_message)
        assert result is not None
        assert result["s3_bucket"] == "ses-emails"
        assert result["s3_key"] == "incoming/msg-123"
        assert result["recipient"] == "user456@ingest.example.com"
        assert result["source"] == "ses"
        assert result["message_id"] == "msg-123"

    def test_inline_content(self, webhook_module):
        sns_message = {
            "mail": {
                "messageId": "msg-456",
                "destination": ["abc@ingest.example.com"],
            },
            "receipt": {"action": {"type": "Lambda"}},
            "content": "From: test@test.com\r\nSubject: Hello\r\n\r\nBody",
        }

        result = webhook_module._extract_email_content(sns_message)
        assert result is not None
        assert result["raw_email"] == "From: test@test.com\r\nSubject: Hello\r\n\r\nBody"
        assert result["recipient"] == "abc@ingest.example.com"

    def test_no_content_returns_none(self, webhook_module):
        sns_message = {
            "mail": {"messageId": "msg-789", "destination": []},
            "receipt": {"action": {"type": "Lambda"}},
        }

        result = webhook_module._extract_email_content(sns_message)
        assert result is None

    def test_empty_destination_gives_empty_recipient(self, webhook_module):
        sns_message = {
            "mail": {"messageId": "msg-999", "destination": []},
            "receipt": {
                "action": {
                    "type": "S3",
                    "bucketName": "bucket",
                    "objectKey": "key",
                }
            },
        }

        result = webhook_module._extract_email_content(sns_message)
        assert result is not None
        assert result["recipient"] == ""
