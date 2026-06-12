"""
Media completed events consumer -- fan-out to media watchers.

- Consumes events from MEDIA_COMPLETED_EVENTS_QUEUE (episode-completed-events)
- Canonical event_type: episode_completion_status (with status: success/failure)
- For each media key, fetches watchers, marks processing state, and finalizes their minute usage
- In V1, all user notifications are via mobile app polling; email notifications disabled
"""
from __future__ import annotations

import os
import json
import asyncio
import logging
from typing import Any, Dict, List, Optional

from media_summarizer.utils import sqs, s3
from media_summarizer.utils import media_watchers
from media_summarizer.core.services.minute_pool import finalize_usage
from media_summarizer.utils.logging_config import bind_log_context, log_event, reset_log_context

logger = logging.getLogger(__name__)

MEDIA_COMPLETED_EVENTS_QUEUE = os.environ.get(
    "MEDIA_COMPLETED_EVENTS_QUEUE",
    os.environ.get("EPISODE_COMPLETED_EVENTS_QUEUE", "episode-completed-events"),
)
SUMMARY_BUCKET = os.environ.get("SUMMARY_BUCKET", "media-summarizer-summaries")

# Backoff
TEST_MODE = os.environ.get("TEST_MODE", "false").lower() == "true"
RETRY_DELAY = 0.01 if TEST_MODE else 2


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
    minutes_used = int(body.get("minutes_used") or 0)
    source_title = body.get("source_title") or body.get("podcast_title")
    media_title = body.get("media_title") or body.get("episode_title")
    summary_s3_key = body.get("summary_s3_key")

    if not media_key:
        logger.error(f"Missing media_key in event: {body}")
        return

    # Fetch watchers
    watchers = await media_watchers.list_watchers(media_key)
    if not watchers:
        logger.info(f"No watchers for media key {media_key}")
        return

    # Handle failure events: mark all watchers as failed and return early
    if status == "failure":
        failure_reason = body.get("error_message", "upstream_pipeline_failure")
        logger.warning(f"Processing failure event for media_key={media_key}: {failure_reason}")
        for w in watchers:
            try:
                await media_watchers.mark_watcher_failed(media_key, w.get("user_id"), reason=failure_reason)
            except Exception as e:
                logger.error(f"Failed to mark watcher {w.get('user_id')} as failed: {e}")
        return

    # Load summary content once for all watchers
    summary_content = await _load_summary_content(summary_s3_key)

    # Fan-out
    for w in watchers:
        try:
            job_id = w.get("job_id")

            # Update processing job with S3 keys and status BEFORE sending email
            try:
                from media_summarizer.utils import database_async

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

            # Finalize usage (charge minutes)
            ok = await finalize_usage(job_id, minutes_used)
            if not ok:
                # Insufficient minutes
                logger.error(f"Failed to finalize usage for job {job_id}: insufficient minutes")
                await media_watchers.mark_watcher_failed(
                    media_key,
                    w.get("user_id"),
                    reason="insufficient_minutes"
                )
                continue

            logger.info(f"Successfully processed watcher {w.get('user_id')} for media key {media_key}: {minutes_used} minutes charged")

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
