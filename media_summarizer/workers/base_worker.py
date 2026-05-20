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
from media_summarizer.utils.logging_config import (
    bind_log_context,
    log_event,
    reset_log_context,
)
from media_summarizer.utils.user_facing_errors import get_user_facing_error_message

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
    - Let SQS redrive to DLQ after max attempts

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
    context_token = bind_log_context(
        job_id=job_id if job_id != "unknown" else None,
        queue=queue_name,
        attempt=receive_count,
    )

    try:
        # Process the message
        await processor(message)

        # Success: delete the message
        await sqs.delete_message(
            queue_name=queue_name,
            receipt_handle=receipt_handle
        )
        log_event(
            logger,
            logging.DEBUG,
            "worker.message_completed",
            "Worker message processed successfully",
            worker=worker_name,
        )

        return True

    except Exception as e:
        # Retry strategy based on attempt count
        if receive_count >= max_retries:
            # After max attempts: let SQS redrive to DLQ (do not delete)

            user_error_message = get_user_facing_error_message(str(e))

            # 1. Mark job as FAILED in DynamoDB
            try:
                if job_id and job_id != "unknown":
                    job = await ProcessingJob.get(job_id)
                    if job:
                        await job.mark_failed(
                            error_message=user_error_message,
                            error_step=worker_name
                        )
                        log_event(
                            logger,
                            logging.DEBUG,
                            "external_call.succeeded",
                            "Marked processing job as failed",
                            worker=worker_name,
                            provider="dynamodb",
                        )
            except Exception as db_err:
                log_event(
                    logger,
                    logging.ERROR,
                    "external_call.failed",
                    "Failed to mark job as failed",
                    worker=worker_name,
                    provider="dynamodb",
                    error_type=type(db_err).__name__,
                    exc_info=db_err,
                )

            # 2. Release minutes hold if applicable
            try:
                if job_id and job_id != "unknown":
                    from media_summarizer.core.services.minute_pool import release_hold
                    released = await release_hold(job_id)
                    log_event(
                        logger,
                        logging.DEBUG,
                        "external_call.succeeded",
                        "Released minute hold after worker failure",
                        worker=worker_name,
                        released=released,
                    )
            except Exception as refund_err:
                log_event(
                    logger,
                    logging.ERROR,
                    "external_call.failed",
                    "Failed to release minute hold after worker failure",
                    worker=worker_name,
                    error_type=type(refund_err).__name__,
                    exc_info=refund_err,
                )

            # 3. User notifications via email are disabled in V1 (replaced by mobile polling)

            # Technical errors are logged for monitoring/alerting
            log_event(
                logger,
                logging.ERROR,
                "worker.failed",
                "Worker message failed after max retries",
                worker=worker_name,
                error_type=type(e).__name__,
                exc_info=e,
            )

            return False
        else:
            # Less than max attempts: let SQS handle retry
            log_event(
                logger,
                logging.WARNING,
                "worker.retry_scheduled",
                "Worker message failed and will be retried by SQS",
                worker=worker_name,
                error_type=type(e).__name__,
                next_attempt=receive_count + 1,
                exc_info=e,
            )
            # Don't delete message - it will return after visibility timeout
            return False
    finally:
        reset_log_context(context_token)


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


