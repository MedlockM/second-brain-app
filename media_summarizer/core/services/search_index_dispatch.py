"""The one way a transcript is submitted for search indexing (task-390).

Two paths reach this queue, and they need the same message for the same reason:

- the end of an ingestion, where the transcript has just been written;
- a **deduplicated save**, which reuses a transcript another save of the same
  content already produced.

An Algolia record is keyed by the save, not by the content
(``objectID = {media_item_id}_chunk_{i}``), and every save gets a fresh
``media_item_id``. So a save that skipped the pipeline has no records at all
until one is indexed under its own id, and the media is absent from search while
sitting in the library with its text one click away. Reusing the previous save's
records is not an option: the search endpoint resolves a hit against the library
row, so records pointing at a deleted save come back as dead hits with no title,
no cover and no possible action.

Indexing a deduplicated save costs one ``save_objects`` over a transcript that
already exists in S3: no re-extraction, no provider call, no LLM, no quota.
"""

from __future__ import annotations

import logging
import time
from typing import Optional

from media_summarizer.utils import sqs
from media_summarizer.utils.env import required_env
from media_summarizer.utils.logging_config import log_event

logger = logging.getLogger(__name__)

SEARCH_INDEXING_QUEUE = required_env("SEARCH_INDEXING_QUEUE")


async def enqueue_transcript_indexing(
    *,
    media_item_id: Optional[str],
    user_id: Optional[str],
    transcription_s3_key: Optional[str],
    title: Optional[str] = None,
    creator_name: Optional[str] = None,
    source_platform: Optional[str] = None,
    job_id: Optional[str] = None,
) -> bool:
    """Ask the indexing worker to index one save's transcript. Never raises.

    ``media_item_id`` is the durable library id and becomes the Algolia objectID
    prefix (task-220). It used to be the processing-job id, which meant a search
    hit pointed at a row that was allowed to expire; ``job_id`` is carried for
    logs only.

    Returns whether a message was sent. Failure is logged and swallowed: neither
    a completion event nor a user's save may be lost because a search record
    could not be scheduled. The enqueue is skipped, with a structured log, when
    the transcript key, the library id or the owner is missing -- the worker
    needs all three and would only log the same thing later.
    """
    if not transcription_s3_key or not user_id or not media_item_id:
        log_event(
            logger,
            logging.WARNING,
            "search_indexing.skipped",
            "Skipped search indexing enqueue: missing transcription_s3_key, media_item_id or user_id",
            job_id=job_id,
            has_transcription_s3_key=bool(transcription_s3_key),
            has_media_item_id=bool(media_item_id),
            has_user_id=bool(user_id),
        )
        return False

    try:
        await sqs.send_message(
            queue_name=SEARCH_INDEXING_QUEUE,
            message_body={
                "media_item_id": media_item_id,
                "user_id": user_id,
                "transcription_s3_key": transcription_s3_key,
                "title": title,
                "creator_name": creator_name,
                "source_platform": source_platform,
                "created_at": int(time.time()),
            },
        )
    except Exception as exc:  # noqa: BLE001 - indexing never fails its caller
        log_event(
            logger,
            logging.WARNING,
            "search_indexing.enqueue_failed",
            "Failed to enqueue search indexing message",
            job_id=job_id,
            user_id=user_id,
            media_item_id=media_item_id,
            error=str(exc),
        )
        return False

    return True
