"""
Search indexing worker -- indexes transcripts in Algolia after transcription completes.

Consumes messages from SEARCH_INDEXING_QUEUE containing:
- media_item_id: job/media identifier
- user_id: owner of the media
- transcription_s3_key: S3 key of the transcript to index
- title: (optional) media title
- source_platform: (optional) platform source

On receipt, downloads the transcript from S3 and indexes it in the shared
Algolia index with user_id attribute for multi-tenant isolation.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
from typing import Any, Dict

from media_summarizer.core.services import search_indexing
from media_summarizer.utils import s3, sqs
from media_summarizer.utils.env import required_env
from media_summarizer.utils.logging_config import (
    bind_log_context,
    log_event,
    reset_log_context,
)

logger = logging.getLogger(__name__)

SEARCH_INDEXING_QUEUE = required_env("SEARCH_INDEXING_QUEUE")
TRANSCRIPT_BUCKET = required_env("TRANSCRIPT_BUCKET")

# Backoff
TEST_MODE = os.environ.get("TEST_MODE", "false").lower() == "true"
RETRY_DELAY = 0.01 if TEST_MODE else 2


async def process_indexing_message(message: Dict[str, Any]) -> None:
    """
    Process a single search indexing message.

    Downloads the transcript from S3 and indexes it in Algolia.
    """
    body = json.loads(message.get("Body", "{}"))

    media_item_id = body.get("media_item_id")
    user_id = body.get("user_id")
    transcription_s3_key = body.get("transcription_s3_key")
    title = body.get("title")
    creator_name = body.get("creator_name")
    source_platform = body.get("source_platform")
    created_at = body.get("created_at")

    if not all([media_item_id, user_id, transcription_s3_key]):
        logger.error(
            f"Missing required fields in search indexing message: {body}"
        )
        return

    context_token = bind_log_context(
        media_item_id=media_item_id, user_id=user_id
    )
    try:
        log_event(
            logger,
            logging.INFO,
            "search_indexing.started",
            "Downloading transcript for search indexing",
            media_item_id=media_item_id,
        )

        # Download transcript from S3
        transcript_bytes = await s3.download_file_to_memory(
            bucket=TRANSCRIPT_BUCKET, key=transcription_s3_key
        )
        transcript_text = transcript_bytes.decode("utf-8", errors="replace")

        if not transcript_text.strip():
            logger.warning(
                f"Empty transcript for media_item_id={media_item_id}, skipping indexing"
            )
            return

        # Index in Algolia (synchronous call, acceptable for worker context)
        search_indexing.index_transcript(
            user_id=user_id,
            media_item_id=media_item_id,
            transcript_text=transcript_text,
            title=title,
            creator_name=creator_name,
            source_platform=source_platform,
            created_at=created_at,
        )

        log_event(
            logger,
            logging.INFO,
            "search_indexing.completed",
            "Transcript indexed successfully",
            media_item_id=media_item_id,
        )

    except Exception as e:
        logger.error(
            f"Failed to index transcript for media_item_id={media_item_id}: {e}",
            exc_info=True,
        )
        # Re-raise so the message stays in the queue for retry
        raise
    finally:
        reset_log_context(context_token)


async def poll_queue() -> None:
    """Poll the search indexing SQS queue."""
    log_event(
        logger,
        logging.INFO,
        "worker.started",
        "Starting search indexing worker",
        queue=SEARCH_INDEXING_QUEUE,
    )

    while True:
        try:
            messages = await sqs.receive_messages(
                queue_name=SEARCH_INDEXING_QUEUE,
                max_messages=10,
                wait_time_seconds=20,
            )
            if messages:
                for m in messages:
                    try:
                        await process_indexing_message(m)
                        receipt_handle = m.get("ReceiptHandle")
                        if receipt_handle:
                            await sqs.delete_message(
                                queue_name=SEARCH_INDEXING_QUEUE,
                                receipt_handle=receipt_handle,
                            )
                    except Exception as e:
                        logger.error(f"Failed to process search indexing message: {e}")
            await asyncio.sleep(1)
        except Exception as e:
            logger.error(f"Polling error in search indexing worker: {e}")
            await asyncio.sleep(RETRY_DELAY)


async def main() -> None:
    """Main entry point for the search indexing worker."""
    await poll_queue()


if __name__ == "__main__":
    from media_summarizer.utils.logging_config import setup_logging

    setup_logging("worker-search-indexing")
    asyncio.run(main())
