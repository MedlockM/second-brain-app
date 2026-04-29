"""
Stable error enums for the newsletter email ingestion domain.

These codes are used in ProcessingJob.error_message and worker logs
to provide deterministic, client-safe error semantics.
"""

from enum import Enum


class NewsletterIngestionError(str, Enum):
    """Stable error codes for the newsletter ingestion pipeline."""

    # Parsing errors
    EMPTY_EMAIL_BODY = "newsletter_empty_email_body"
    INVALID_MIME_FORMAT = "newsletter_invalid_mime_format"
    NO_TEXT_CONTENT = "newsletter_no_text_content"
    CONTENT_TOO_SHORT = "newsletter_content_too_short"

    # User identification errors
    UNKNOWN_RECIPIENT = "newsletter_unknown_recipient"
    USER_NOT_FOUND = "newsletter_user_not_found"
    INACTIVE_INGEST_ADDRESS = "newsletter_inactive_ingest_address"

    # Processing errors
    EXTRACTION_FAILED = "newsletter_extraction_failed"
    SUMMARIZATION_ENQUEUE_FAILED = "newsletter_summarization_enqueue_failed"

    # SNS/SES webhook errors
    INVALID_SNS_SIGNATURE = "newsletter_invalid_sns_signature"
    UNSUPPORTED_NOTIFICATION_TYPE = "newsletter_unsupported_notification_type"
    MISSING_MAIL_CONTENT = "newsletter_missing_mail_content"


# Minimum character count for extracted newsletter text to be considered valid
MIN_NEWSLETTER_CONTENT_LENGTH = 100

# User-facing messages mapped to error codes
USER_FACING_MESSAGES: dict[str, str] = {
    NewsletterIngestionError.EMPTY_EMAIL_BODY: (
        "The forwarded email appears to be empty. Please ensure the newsletter has content."
    ),
    NewsletterIngestionError.INVALID_MIME_FORMAT: (
        "The email format could not be parsed. Please try forwarding the email again."
    ),
    NewsletterIngestionError.NO_TEXT_CONTENT: (
        "No readable text was found in the email. The newsletter may use unsupported formatting."
    ),
    NewsletterIngestionError.CONTENT_TOO_SHORT: (
        "The extracted newsletter content is too short to generate a meaningful summary."
    ),
    NewsletterIngestionError.UNKNOWN_RECIPIENT: (
        "The email was sent to an unrecognized ingestion address."
    ),
    NewsletterIngestionError.USER_NOT_FOUND: (
        "Could not identify the user associated with this ingestion address."
    ),
    NewsletterIngestionError.INACTIVE_INGEST_ADDRESS: (
        "This ingestion address is no longer active."
    ),
    NewsletterIngestionError.EXTRACTION_FAILED: (
        "Failed to extract content from the newsletter email."
    ),
    NewsletterIngestionError.SUMMARIZATION_ENQUEUE_FAILED: (
        "Failed to queue the newsletter for processing. Please try again."
    ),
    NewsletterIngestionError.INVALID_SNS_SIGNATURE: (
        "The notification signature could not be verified."
    ),
    NewsletterIngestionError.UNSUPPORTED_NOTIFICATION_TYPE: (
        "Unsupported notification type received."
    ),
    NewsletterIngestionError.MISSING_MAIL_CONTENT: (
        "The notification did not contain email content."
    ),
}
