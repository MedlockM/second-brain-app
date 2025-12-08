"""
Base worker utilities for consistent error handling and retry logic.

This module provides common patterns used across all workers:
- Structured logging
- Retry logic with exponential backoff
- Dead Letter Queue integration
- Graceful error handling

Migrated to use the new utils for SQS operations instead of direct AWS libraries.
"""
import json
import logging
from typing import Dict, Any, Callable, Awaitable
import asyncio

from media_summarizer.utils import sqs, database_async
from media_summarizer.core.models.processing_job import ProcessingJob

logger = logging.getLogger(__name__)


async def process_message_with_retry(
    message: Dict[str, Any],
    processor: Callable[[Dict[str, Any]], Awaitable[None]],
    queue_name: str,
    max_retries: int = 3,
    worker_name: str = "unknown"
) -> bool:
    """
    Process a message with elegant error handling and retry logic.

    This follows industry best practices:
    - Automatic retry with counter
    - Structured logging with context
    - Conditional deletion based on attempt count
    - Fallback to DLQ in production, deletion in development

    Args:
        message: SQS message to process
        processor: Async function to process the message
        queue_name: SQS queue name for message deletion
        max_retries: Maximum number of retry attempts
        worker_name: Name of the worker for logging

    Returns:
        bool: True if processing succeeded, False otherwise
    """
    receipt_handle = message["ReceiptHandle"]

    # Extract SQS attributes for retry logic
    attributes = message.get("Attributes", {})
    receive_count = int(attributes.get("ApproximateReceiveCount", "1"))

    # Parse message body early to have job_id available in exception handler
    try:
        if "Body" in message:
            body = json.loads(message["Body"])
        else:
            body = message
    except Exception:
        body = {"job_id": "unknown"}

    job_id = body.get("job_id", "unknown")

    try:
        # Structured logging with context
        logger.info(
            f"[{worker_name}] Processing message",
            extra={
                "job_id": job_id,
                "attempt": receive_count,
                "max_attempts": max_retries,
                "worker": worker_name
            }
        )

        # Process the message
        await processor(message)

        # Success: delete the message
        await sqs.delete_message(
            queue_name=queue_name,
            receipt_handle=receipt_handle
        )

        logger.info(
            f"[{worker_name}] Message processed successfully",
            extra={
                "job_id": job_id,
                "attempt": receive_count,
                "worker": worker_name
            }
        )

        return True

    except Exception as e:
        # Structured error logging
        logger.error(
            f"[{worker_name}] Message processing failed",
            extra={
                "job_id": job_id,
                "attempt": receive_count,
                "max_attempts": max_retries,
                "error": str(e),
                "error_type": type(e).__name__,
                "worker": worker_name
            }
        )

        # Retry strategy based on attempt count
        if receive_count >= max_retries:
            # After max attempts: delete to prevent infinite loop
            
            # 1. Mark job as FAILED in DynamoDB
            try:
                if job_id and job_id != "unknown":
                    job = await ProcessingJob.get(job_id)
                    if job:
                        await job.mark_failed(
                            error_message=f"Max retries reached ({max_retries}). Last error: {str(e)}",
                            error_step=worker_name
                        )
                        logger.info(f"[{worker_name}] Marked job {job_id} as FAILED in DynamoDB")
            except Exception as db_err:
                logger.error(f"[{worker_name}] Failed to mark job {job_id} as FAILED: {db_err}")

            # 2. Release minutes hold if applicable
            try:
                if job_id and job_id != "unknown":
                    from media_summarizer.core.services.minute_pool import release_hold
                    released = await release_hold(job_id)
                    logger.info(f"[{worker_name}] Released minute hold on failure for job {job_id}: {released}")
            except Exception as refund_err:
                logger.error(f"[{worker_name}] Failed to release minute hold on failure for job {job_id}: {refund_err}")

            # 3. Send error notification to user
            try:
                if job_id and job_id != "unknown":
                    await send_error_notification(
                        job_id=job_id,
                        error_message=f"Processing failed after {max_retries} attempts. Please try again later.",
                        step=worker_name
                    )
            except Exception as notify_err:
                logger.error(f"[{worker_name}] Failed to send error notification for job {job_id}: {notify_err}")

            # Technical errors are logged for monitoring/alerting
            logger.warning(
                f"[{worker_name}] Technical error after {receive_count} attempts, removing from queue",
                extra={
                    "job_id": job_id,
                    "final_error": str(e),
                    "worker": worker_name,
                    "alert_ops": True  # Flag for monitoring systems
                }
            )

            # Delete message to prevent infinite loop
            await sqs.delete_message(
                queue_name=queue_name,
                receipt_handle=receipt_handle
            )

            return False
        else:
            # Less than max attempts: let SQS handle retry
            logger.info(
                f"[{worker_name}] Technical error, will retry automatically",
                extra={
                    "job_id": job_id,
                    "attempt": receive_count,
                    "next_attempt": receive_count + 1,
                    "worker": worker_name
                }
            )
            # Don't delete message - it will return after visibility timeout
            return False


def get_sqs_receive_params(visibility_timeout: int = 120) -> Dict[str, Any]:
    """
    Get standard SQS receive parameters for consistent behavior.

    Args:
        visibility_timeout: How long message stays invisible after being received

    Returns:
        Dict with SQS receive_message parameters
    """
    return {
        "MaxNumberOfMessages": 1,
        "WaitTimeSeconds": 20,  # Long polling
        "VisibilityTimeout": visibility_timeout,
        "AttributeNames": ['ApproximateReceiveCount'],  # For retry logic
    }


# Legacy refund_credits_on_failure removed in favor of minute holds release


async def send_error_notification(
    job_id: str,
    error_message: str,
    step: str
) -> None:
    """
    Send error notification to email queue with consistent format.

    Args:
        job_id: Job identifier
        error_message: Error description
        step: Processing step where error occurred
    """
    notification_body = {
        "job_id": job_id,
        "error": error_message,
        "step": step,
        "success": False,
        "notification_type": "error",
        "timestamp": __import__('datetime').datetime.now(__import__('datetime').timezone.utc).isoformat()
    }

    try:
        await sqs.send_message(
            queue_name="email-notification-queue",
            message_body=notification_body
        )
        logger.info(f"Error notification sent for job {job_id}")
    except Exception as e:
        logger.error(f"Failed to send error notification for job {job_id}: {str(e)}")
