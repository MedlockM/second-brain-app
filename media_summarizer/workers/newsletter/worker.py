"""
Newsletter ingestion worker.

Consumes messages from the newsletter-ingestion-queue (fed by SES via SNS).
Each message contains a raw email that is:
1. Parsed to extract newsletter text content
2. Associated with the user via the recipient ingestion address
3. Stored as a transcription-equivalent in S3
4. Enqueued for summarization

This worker follows the same pattern as other platform workers:
- Creates a ProcessingJob
- Allocates a minute hold
- Feeds downstream into the summarization pipeline

The newsletter content is stored in the transcription bucket as plain text,
allowing the summarization worker to consume it identically to an audio transcript.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import os
import time
from io import BytesIO
from typing import Any, Dict, Optional

from media_summarizer.core.models import ProcessingJob
from media_summarizer.core.services.minute_pool import allocate_hold_for_job
from media_summarizer.core.services.newsletter_errors import (
    NewsletterIngestionError,
    USER_FACING_MESSAGES,
)
from media_summarizer.core.services.newsletter_parser import (
    NewsletterParseResult,
    parse_raw_email,
)
from media_summarizer.utils import database_async, s3, sqs
from media_summarizer.utils.logging_config import (
    bind_log_context,
    log_event,
    reset_log_context,
    setup_logging,
)
from media_summarizer.workers.base_worker import (
    get_sqs_receive_params,
    process_message_with_retry,
)

logger = logging.getLogger(__name__)

# Configuration
NEWSLETTER_INGESTION_QUEUE = os.environ.get(
    "NEWSLETTER_INGESTION_QUEUE", "newsletter-ingestion-queue"
)
TRANSCRIPT_BUCKET = os.environ.get(
    "TRANSCRIPT_BUCKET", "media-summarizer-transcripts"
)
SUMMARIZATION_QUEUE = os.environ.get("SUMMARIZATION_QUEUE", "summarization-queue")

# Estimated minutes for a newsletter (text-based, no audio duration)
# Newsletters are charged as 1 minute since there is no audio duration concept
NEWSLETTER_MINUTES_COST = 1


def _generate_media_key(sender: str, subject: str, date: str) -> str:
    """Generate a deterministic media key for idempotence.

    Combines sender + subject + date to produce a stable hash that prevents
    the same newsletter from being processed multiple times.
    """
    raw = f"{sender}|{subject}|{date}"
    return f"newsletter:{hashlib.sha256(raw.encode()).hexdigest()[:32]}"


def _resolve_user_from_recipient(recipient: str) -> Optional[str]:
    """Resolve the user ID from the recipient email address.

    The convention is: {user_hash}@ingest.{domain}
    where user_hash is a unique identifier mapped to the user in DynamoDB.

    For now this returns the local part of the address as the lookup key.
    The actual resolution happens via database lookup in the async processing.
    """
    if not recipient or "@" not in recipient:
        return None
    local_part = recipient.split("@")[0]
    return local_part if local_part else None


async def _lookup_user_by_ingest_address(recipient: str):
    """Look up the user associated with a newsletter ingest address.

    Searches the users table for the user whose ingest_email_address matches
    the given recipient.

    Returns the user object or None.
    """
    ingest_key = _resolve_user_from_recipient(recipient)
    if not ingest_key:
        return None

    # Look up user by their unique ingest address hash
    try:
        user = await database_async.get_user_by_ingest_address(ingest_key)
        return user
    except Exception:
        # If the lookup method doesn't exist yet, fall back to None
        # This is expected during initial development
        return None


async def process_newsletter_message(message_body: Dict[str, Any]) -> None:
    """Process a single newsletter ingestion message.

    Expected message_body keys:
        - raw_email: str - The raw MIME email content (or S3 reference)
        - recipient: str - The ingest email address that received the email
        - source: str - How this email arrived (ses, forwarded, etc.)
        - s3_bucket: str (optional) - If email stored in S3 by SES
        - s3_key: str (optional) - S3 object key for the raw email
    """
    recipient = message_body.get("recipient", "")
    source = message_body.get("source", "ses")

    token = bind_log_context(
        source_platform="newsletter",
        recipient=recipient,
    )

    try:
        # Step 1: Get raw email content
        raw_email: Optional[str] = message_body.get("raw_email")

        if not raw_email:
            # Email stored in S3 by SES (common for large emails)
            s3_bucket = message_body.get("s3_bucket")
            s3_key = message_body.get("s3_key")
            if s3_bucket and s3_key:
                try:
                    content_bytes = await s3.download_file_to_memory(
                        bucket=s3_bucket, key=s3_key
                    )
                    raw_email = content_bytes.decode("utf-8", errors="replace")
                except Exception as e:
                    logger.error(f"Failed to download email from S3: {e}")
                    raise ValueError(
                        USER_FACING_MESSAGES[NewsletterIngestionError.MISSING_MAIL_CONTENT]
                    )
            else:
                raise ValueError(
                    USER_FACING_MESSAGES[NewsletterIngestionError.MISSING_MAIL_CONTENT]
                )

        # Step 2: Identify the user from the recipient address
        user = await _lookup_user_by_ingest_address(recipient)
        if not user:
            log_event(
                logger,
                logging.WARNING,
                "newsletter.user_not_found",
                "Could not identify user from ingest address",
                recipient=recipient,
                error_code=NewsletterIngestionError.USER_NOT_FOUND,
            )
            raise ValueError(
                USER_FACING_MESSAGES[NewsletterIngestionError.USER_NOT_FOUND]
            )

        # Step 3: Parse the email
        parse_result: NewsletterParseResult = parse_raw_email(raw_email)

        if not parse_result.success:
            log_event(
                logger,
                logging.WARNING,
                "newsletter.parse_failed",
                f"Newsletter parsing failed: {parse_result.error}",
                recipient=recipient,
                error_code=parse_result.error,
            )
            raise ValueError(
                USER_FACING_MESSAGES.get(
                    parse_result.error,
                    "Failed to parse newsletter email.",
                )
            )

        # Step 4: Generate media key for idempotence
        media_key = _generate_media_key(
            parse_result.sender, parse_result.subject, parse_result.date
        )

        log_event(
            logger,
            logging.INFO,
            "newsletter.parsed",
            "Newsletter parsed successfully",
            subject=parse_result.subject,
            sender=parse_result.sender_name or parse_result.sender,
            word_count=parse_result.word_count,
            media_key=media_key,
        )

        # Step 5: Create processing job
        job = ProcessingJob(
            user_id=user.id,
            user_email=user.email,
            source_url="",
            media_url="",
            media_key=media_key,
            title=parse_result.subject or "Newsletter",
            source_platform="newsletter",
            media_type="article",
        )
        created_job = await database_async.create_processing_job(job)

        # Step 6: Allocate minutes hold
        try:
            await allocate_hold_for_job(
                user_id=user.id,
                job_id=created_job.id,
                minutes_estimated=NEWSLETTER_MINUTES_COST,
            )
        except Exception as e:
            logger.warning(f"Failed to allocate minutes for newsletter job: {e}")

        # Step 7: Store extracted text as a "transcription" in S3
        transcript_key = f"{created_job.id}.txt"
        transcript_content = (
            f"Newsletter: {parse_result.subject}\n"
            f"From: {parse_result.sender_name or parse_result.sender}\n"
            f"Date: {parse_result.date}\n"
            f"---\n\n"
            f"{parse_result.text}"
        )

        transcript_bytes = transcript_content.encode("utf-8")
        await s3.upload_file_object(
            bucket=TRANSCRIPT_BUCKET,
            key=transcript_key,
            file_obj=BytesIO(transcript_bytes),
            content_type="text/plain",
            metadata={
                "content-type": "text/plain",
                "source": "newsletter",
                "media-key": media_key,
            },
        )

        # Update job with transcription location
        created_job.set_transcription_location(transcript_key)
        created_job.mark_summarizing()
        await database_async.update_processing_job(created_job)

        # Step 8: Enqueue for summarization
        summarization_payload = {
            "job_id": created_job.id,
            "transcript_s3_key": transcript_key,
            "transcript_bucket": TRANSCRIPT_BUCKET,
            "email": user.email,
            "podcast_title": parse_result.sender_name or "Newsletter",
            "episode_title": parse_result.subject or "Newsletter Issue",
            "episode_guid": media_key,
            "audio_duration_seconds": 0,  # Text content, no audio
        }

        await sqs.send_message(
            queue_name=SUMMARIZATION_QUEUE,
            message_body=summarization_payload,
        )

        log_event(
            logger,
            logging.INFO,
            "newsletter.enqueued",
            "Newsletter enqueued for summarization",
            job_id=created_job.id,
            media_key=media_key,
            subject=parse_result.subject,
        )

    finally:
        reset_log_context(token)


async def process_message(message: Dict[str, Any]) -> None:
    """Process an SQS message for newsletter ingestion.

    Args:
        message: SQS message containing the newsletter email data.
    """
    try:
        body = json.loads(message.get("Body", "{}"))
        await process_newsletter_message(body)
    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse newsletter message body: {e}")
        raise
    except Exception as e:
        logger.error(f"Error processing newsletter message: {e}")
        raise


async def poll_queue() -> None:
    """Poll the newsletter ingestion SQS queue for incoming emails."""
    logger.info("Starting newsletter ingestion worker - polling queue")

    while True:
        try:
            messages = await sqs.receive_messages(
                queue_name=NEWSLETTER_INGESTION_QUEUE,
                max_messages=1,
                wait_time_seconds=20,
                visibility_timeout=120,
            )

            if messages:
                logger.info(f"Received {len(messages)} newsletter message(s)")
                for message in messages:
                    await process_message_with_retry(
                        message=message,
                        processor=process_message,
                        queue_name=NEWSLETTER_INGESTION_QUEUE,
                        max_retries=3,
                        worker_name="newsletter",
                    )

            await asyncio.sleep(1)

        except Exception as e:
            logger.error(f"Error polling newsletter ingestion queue: {e}")
            await asyncio.sleep(5)


async def main() -> None:
    """Main entry point for the newsletter ingestion worker."""
    logger.info("Starting newsletter ingestion worker")
    await poll_queue()


if __name__ == "__main__":
    setup_logging("worker-newsletter")
    asyncio.run(main())
