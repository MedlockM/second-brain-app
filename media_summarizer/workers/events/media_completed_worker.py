"""
Media completed events consumer -- fan-out to media watchers + primary-user indexing.

- Consumes events from EPISODE_COMPLETED_EVENTS_QUEUE (episode-completed-events-<env>)
- Canonical event_type: episode_completion_status (with status: success/failure)
- For each media key, fetches watchers and marks their processing state
- In V1, all user notifications are via mobile app polling; email notifications disabled

Search indexing (Algolia) is decoupled from the watcher loop:
- The submitting user (resolved from the event's canonical_job_id) is ALWAYS indexed,
  regardless of whether watchers exist.
- Each watcher is also indexed (for cross-user dedup scenarios).
- Deduplication: a user_id is only indexed once per event, even if they appear both as
  the canonical submitter and as a watcher.
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import time
from typing import Any, Dict, Optional

from media_summarizer.utils import media_watchers, s3, sqs
from media_summarizer.utils.env import required_env
from media_summarizer.utils.logging_config import log_event

logger = logging.getLogger(__name__)

# The MEDIA_COMPLETED_EVENTS_QUEUE alias this consumer used to accept was never
# injected by Terraform, so it only ever resolved through its own fallback.
# task-143 settled EPISODE_COMPLETED_EVENTS_QUEUE as the canonical name shared by
# every producer, and pr.yml guards against the other spelling coming back.
MEDIA_COMPLETED_EVENTS_QUEUE = required_env("EPISODE_COMPLETED_EVENTS_QUEUE")
SUMMARY_BUCKET = required_env("SUMMARY_BUCKET")
SEARCH_INDEXING_QUEUE = required_env("SEARCH_INDEXING_QUEUE")

# Backoff
TEST_MODE = os.environ.get("TEST_MODE", "false").lower() == "true"
RETRY_DELAY = 0.01 if TEST_MODE else 2


async def _enqueue_search_indexing(
    *,
    media_item_id: Optional[str],
    job_id: Optional[str],
    user_id: Optional[str],
    transcription_s3_key: Optional[str],
    title: Optional[str],
    creator_name: Optional[str],
    source_platform: Optional[str],
) -> None:
    """
    Best-effort enqueue of a search indexing message so the transcript becomes
    searchable in the shared Algolia index (with user_id attribute for isolation).

    This is the single canonical join point for Algolia indexing: every
    ingestion path that publishes ``episode_completion_status`` with a
    ``transcription_s3_key`` is indexed here, regardless of producer.

    ``media_item_id`` is the durable library id and becomes the Algolia objectID
    (task-220). It used to be the processing-job id, which meant a search hit
    pointed at a row that was allowed to expire; ``job_id`` is now kept for logs
    only.

    Failure is logged as a warning and never propagates -- it must not break
    the event handling nor the watcher fan-out. The enqueue is skipped (with a
    structured log) when ``transcription_s3_key``, ``media_item_id`` or
    ``user_id`` is missing.
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
        return

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
    except Exception as search_err:
        log_event(
            logger,
            logging.WARNING,
            "search_indexing.enqueue_failed",
            "Failed to enqueue search indexing message",
            job_id=job_id,
            user_id=user_id,
            error=str(search_err),
        )


async def _load_summary_content(summary_s3_key: Optional[str]) -> Optional[Dict[str, Any]]:
    if not summary_s3_key:
        return None
    try:
        raw = await s3.download_file_to_memory(SUMMARY_BUCKET, summary_s3_key)
        try:
            data = json.loads(raw.decode("utf-8"))
        except Exception:
            # Non-JSON fallback
            data = {"summary": raw.decode("utf-8", errors="ignore")}
        # Prefer the inner "summary" field if present
        return data.get("summary", data)
    except Exception as e:
        logger.warning(f"Failed to load summary content {summary_s3_key}: {e}")
        return None


async def process_event(message: Dict[str, Any]) -> None:
    body = json.loads(message.get("Body", "{}"))
    # Accept canonical and legacy event types
    event_type = body.get("event_type")
    if event_type not in ("episode_completion_status", "media_completed", "episode_completed"):
        logger.warning(f"Ignoring unknown event type: {event_type}")
        return

    # Accept both new and legacy field names
    media_key = body.get("media_key") or body.get("episode_guid")
    status = body.get("status", "success")  # legacy events have no status field; treat as success
    media_title = body.get("media_title") or body.get("episode_title")
    summary_s3_key = body.get("summary_s3_key")
    transcription_s3_key = body.get("transcription_s3_key")
    canonical_job_id = body.get("canonical_job_id")

    if not media_key:
        logger.error(f"Missing media_key in event: {body}")
        return

    # Fetch watchers
    watchers = await media_watchers.list_watchers(media_key)
    if not watchers:
        logger.info(f"No watchers for media key {media_key}")

    # Handle failure events: mark all watchers as failed and return early
    if status == "failure":
        failure_reason = body.get("error_message", "upstream_pipeline_failure")
        logger.warning(f"Processing failure event for media_key={media_key}: {failure_reason}")
        for w in (watchers or []):
            try:
                await media_watchers.mark_watcher_failed(media_key, w.get("user_id"), reason=failure_reason)
            except Exception as e:
                logger.error(f"Failed to mark watcher {w.get('user_id')} as failed: {e}")
        return

    # -------------------------------------------------------------------------
    # Primary-user search indexing (decoupled from watcher loop)
    # -------------------------------------------------------------------------
    # The canonical_job_id identifies the processing job that produced this
    # completion event. Its user_id is the submitting user who must always be
    # indexed, regardless of whether watchers exist.
    indexed_user_ids: set = set()

    from media_summarizer.utils import database_async

    canonical_job = None
    if canonical_job_id:
        try:
            canonical_job = await database_async.get_processing_job_by_id(canonical_job_id)
        except Exception as e:
            logger.error(f"Failed to load canonical job {canonical_job_id}: {e}")

    if canonical_job and canonical_job.user_id:
        await _enqueue_search_indexing(
            media_item_id=canonical_job.media_item_id or canonical_job_id,
            job_id=canonical_job_id,
            user_id=canonical_job.user_id,
            transcription_s3_key=transcription_s3_key,
            title=canonical_job.title or media_title,
            creator_name=canonical_job.creator_name,
            source_platform=canonical_job.source_platform,
        )
        indexed_user_ids.add(canonical_job.user_id)
    elif not canonical_job_id:
        log_event(
            logger,
            logging.WARNING,
            "search_indexing.no_canonical_job_id",
            "Event has no canonical_job_id; cannot resolve primary user for indexing",
            media_key=media_key,
        )

    # -------------------------------------------------------------------------
    # Watcher fan-out
    # -------------------------------------------------------------------------
    if not watchers:
        return

    # Fan-out
    for w in watchers:
        try:
            job_id = w.get("job_id")
            job = None

            # Update processing job with S3 keys and status BEFORE sending email
            try:
                job = await database_async.get_processing_job_by_id(job_id)
                if job:
                    if summary_s3_key:
                        job.set_summary_location(summary_s3_key)


                    job.mark_completed()
                    await database_async.update_processing_job(job)
                    logger.info(f"Updated processing job {job_id} with S3 keys")
            except Exception as e:
                logger.error(f"Failed to update processing job {job_id}: {e}")

            # Mark watcher as processed (for deduplication; notifications via mobile polling in V1)
            try:
                await media_watchers.mark_watcher_processed(media_key, w.get("user_id"))
                logger.info(f"Marked watcher {w.get('user_id')} as processed for media key {media_key}")
            except Exception as mark_error:
                logger.error(f"Failed to mark watcher processed for {w.get('user_id')} on {media_key}: {mark_error}")
                await media_watchers.mark_watcher_failed(
                    media_key,
                    w.get("user_id"),
                    reason=f"mark_processed_failed: {str(mark_error)}"
                )
                continue

            logger.info(f"Successfully processed watcher {w.get('user_id')} for media key {media_key}")

            # Per-watcher Algolia indexing (cross-user dedup). Deduplicate
            # against the primary user who was already indexed above.
            watcher_user_id = (getattr(job, "user_id", None) if job else None) or w.get("user_id")
            if watcher_user_id and watcher_user_id not in indexed_user_ids:
                await _enqueue_search_indexing(
                    media_item_id=(
                        getattr(job, "media_item_id", None) if job else None
                    )
                    or job_id,
                    job_id=job_id,
                    user_id=watcher_user_id,
                    transcription_s3_key=transcription_s3_key,
                    title=(getattr(job, "title", None) if job else None) or media_title,
                    creator_name=(
                        getattr(job, "creator_name", None) if job else None
                    ),
                    source_platform=(getattr(job, "source_platform", None) if job else None),
                )
                indexed_user_ids.add(watcher_user_id)

        except Exception as e:
            logger.error(f"Error processing watcher {w.get('user_id')} for {media_key}: {e}")
            try:
                await media_watchers.mark_watcher_failed(media_key, w.get("user_id"), reason=str(e))
            except Exception:
                pass


async def poll_queue() -> None:
    log_event(
        logger,
        logging.INFO,
        "worker.started",
        "Starting media-completed-events consumer",
        queue=MEDIA_COMPLETED_EVENTS_QUEUE,
    )
    while True:
        try:
            messages = await sqs.receive_messages(
                queue_name=MEDIA_COMPLETED_EVENTS_QUEUE,
                max_messages=10,
                wait_time_seconds=20,
            )
            if messages:
                for m in messages:
                    try:
                        await process_event(m)
                        rh = m.get("ReceiptHandle")
                        if rh:
                            await sqs.delete_message(queue_name=MEDIA_COMPLETED_EVENTS_QUEUE, receipt_handle=rh)
                    except Exception as e:
                        logger.error(f"Failed to process event: {e}")
            await asyncio.sleep(1)
        except Exception as e:
            logger.error(f"Polling error: {e}")
            await asyncio.sleep(RETRY_DELAY)


async def main() -> None:
    await poll_queue()


if __name__ == "__main__":
    from media_summarizer.utils.logging_config import setup_logging as _setup_logging
    _setup_logging("worker-episode-completed")
    asyncio.run(main())
