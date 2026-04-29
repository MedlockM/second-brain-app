"""
Newsletter email ingestion webhook endpoint.

Receives AWS SNS notifications triggered by SES when an email arrives at
the user's dedicated newsletter ingestion address. The endpoint validates
the SNS message, extracts the email content, and enqueues it for the
newsletter ingestion worker.

Route: POST /api/media/newsletter/ingest

This endpoint is called by AWS infrastructure (SNS), not by end users directly.
It must handle:
1. SNS SubscriptionConfirmation (auto-confirm the subscription)
2. SNS Notification with SES email data (enqueue for processing)
"""

from __future__ import annotations

import json
import logging
import os
from typing import Any, Dict, Optional

import httpx
from fastapi import APIRouter, Request, Response, status

from media_summarizer.core.services.newsletter_errors import (
    NewsletterIngestionError,
)
from media_summarizer.utils import sqs
from media_summarizer.utils.logging_config import (
    bind_log_context,
    log_event,
    reset_log_context,
)

router = APIRouter()
logger = logging.getLogger(__name__)

NEWSLETTER_INGESTION_QUEUE = os.environ.get(
    "NEWSLETTER_INGESTION_QUEUE", "newsletter-ingestion-queue"
)


def _extract_recipients_from_ses(ses_mail: Dict[str, Any]) -> list[str]:
    """Extract recipient email addresses from an SES notification."""
    destination = ses_mail.get("destination", [])
    if isinstance(destination, list):
        return destination
    return []


def _extract_email_content(sns_message: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Extract the email data from an SNS notification carrying SES content.

    SES can deliver email content in two ways:
    1. Inline in the notification (for small emails)
    2. Via S3 action (email stored in S3, notification contains reference)

    Returns a dict with:
        - raw_email: str (if inline)
        - s3_bucket + s3_key: str (if stored in S3)
        - recipient: str (the ingest address)
        - source: "ses"
    """
    mail = sns_message.get("mail", {})
    receipt = sns_message.get("receipt", {})

    recipients = _extract_recipients_from_ses(mail)
    recipient = recipients[0] if recipients else ""

    # Check if content was stored via S3 action
    action = receipt.get("action", {})
    if action.get("type") == "S3":
        return {
            "s3_bucket": action.get("bucketName", ""),
            "s3_key": action.get("objectKey", ""),
            "recipient": recipient,
            "source": "ses",
            "message_id": mail.get("messageId", ""),
        }

    # Check for inline content (rare for SES, but handle it)
    content = sns_message.get("content")
    if content:
        return {
            "raw_email": content,
            "recipient": recipient,
            "source": "ses",
            "message_id": mail.get("messageId", ""),
        }

    return None


@router.post("/newsletter/ingest")
async def newsletter_ingest_webhook(request: Request) -> Response:
    """Receive SNS notifications from SES for newsletter email ingestion.

    Handles two SNS message types:
    - SubscriptionConfirmation: Automatically confirms the SNS subscription
    - Notification: Extracts email data and enqueues for processing
    """
    token = bind_log_context(source_platform="newsletter", endpoint="webhook")

    try:
        # Parse the raw body
        body = await request.body()
        try:
            payload = json.loads(body)
        except json.JSONDecodeError:
            log_event(
                logger,
                logging.WARNING,
                "newsletter.webhook.invalid_json",
                "Received non-JSON body in newsletter webhook",
                error_code=NewsletterIngestionError.INVALID_SNS_SIGNATURE,
            )
            return Response(status_code=status.HTTP_400_BAD_REQUEST)

        message_type = payload.get("Type", "")

        # Handle SNS subscription confirmation
        if message_type == "SubscriptionConfirmation":
            subscribe_url = payload.get("SubscribeURL")
            if subscribe_url:
                try:
                    async with httpx.AsyncClient() as client:
                        await client.get(subscribe_url, timeout=10.0)
                    log_event(
                        logger,
                        logging.INFO,
                        "newsletter.webhook.subscription_confirmed",
                        "SNS subscription confirmed",
                    )
                except Exception as e:
                    logger.error(f"Failed to confirm SNS subscription: {e}")
            return Response(status_code=status.HTTP_200_OK)

        # Handle notification
        if message_type == "Notification":
            # Parse the inner Message (SES notification JSON)
            message_str = payload.get("Message", "")
            try:
                ses_notification = json.loads(message_str)
            except (json.JSONDecodeError, TypeError):
                log_event(
                    logger,
                    logging.WARNING,
                    "newsletter.webhook.invalid_message",
                    "Could not parse SES notification from SNS Message",
                    error_code=NewsletterIngestionError.MISSING_MAIL_CONTENT,
                )
                return Response(status_code=status.HTTP_400_BAD_REQUEST)

            # Extract email content reference
            email_data = _extract_email_content(ses_notification)
            if not email_data:
                log_event(
                    logger,
                    logging.WARNING,
                    "newsletter.webhook.no_content",
                    "SNS notification did not contain extractable email content",
                    error_code=NewsletterIngestionError.MISSING_MAIL_CONTENT,
                )
                return Response(status_code=status.HTTP_400_BAD_REQUEST)

            # Enqueue for the newsletter worker
            await sqs.send_message(
                queue_name=NEWSLETTER_INGESTION_QUEUE,
                message_body=email_data,
            )

            log_event(
                logger,
                logging.INFO,
                "newsletter.webhook.enqueued",
                "Newsletter email enqueued for processing",
                recipient=email_data.get("recipient", ""),
                message_id=email_data.get("message_id", ""),
            )

            return Response(status_code=status.HTTP_200_OK)

        # Unsupported message type
        log_event(
            logger,
            logging.WARNING,
            "newsletter.webhook.unsupported_type",
            f"Unsupported SNS message type: {message_type}",
            error_code=NewsletterIngestionError.UNSUPPORTED_NOTIFICATION_TYPE,
        )
        return Response(status_code=status.HTTP_400_BAD_REQUEST)

    except Exception as e:
        log_event(
            logger,
            logging.ERROR,
            "newsletter.webhook.error",
            "Unexpected error in newsletter webhook",
            error_type=type(e).__name__,
            exc_info=e,
        )
        return Response(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR)

    finally:
        reset_log_context(token)
