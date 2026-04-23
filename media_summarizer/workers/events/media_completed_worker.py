"""
Media completed events consumer -- fan-out notifications to media watchers.

- Consumes events from MEDIA_COMPLETED_EVENTS_QUEUE (episode-completed-events, legacy queue name)
- For each media key, fetches watchers, finalizes their minute usage, and sends completion emails with from_cache=True
- Handles insufficient minutes per policy: spotify -> email error; manual -> no email, mark failed
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
NOTIFICATION_QUEUE = os.environ.get("NOTIFICATION_QUEUE", "email-notification-queue")
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


async def _notify_watcher_completion(*, watcher: Dict[str, Any], source_title: Optional[str], media_title: Optional[str], summary_content: Optional[Dict[str, Any]]) -> None:
    await sqs.send_message(
        queue_name=NOTIFICATION_QUEUE,
        message_body={
            "notification_type": "completion",
            "job_id": watcher.get("job_id"),
            "email": watcher.get("email"),
            "source_title": source_title,
            "media_title": media_title,
            "summary_content": summary_content,
            "from_cache": True,
            # Deprecated aliases for downstream compatibility
            "podcast_title": source_title,
            "episode_title": media_title,
        },
    )


async def _notify_watcher_insufficient_minutes(*, watcher: Dict[str, Any]) -> None:
    # Only for spotify source per policy
    await sqs.send_message(
        queue_name=NOTIFICATION_QUEUE,
        message_body={
            "notification_type": "error",
            "job_id": watcher.get("job_id"),
            "email": watcher.get("email"),
            "error": "Insufficient minutes to finalize usage for this media item.",
            "step": "billing",
            "from_cache": True,
        },
    )


async def process_event(message: Dict[str, Any]) -> None:
    body = json.loads(message.get("Body", "{}"))
    # Accept both new and legacy event types
    event_type = body.get("event_type")
    if event_type not in ("media_completed", "episode_completed"):
        logger.warning(f"Ignoring unknown event type: {event_type}")
        return

    # Accept both new and legacy field names
    media_key = body.get("media_key") or body.get("episode_guid")
    minutes_used = int(body.get("minutes_used") or 0)
    source_title = body.get("source_title") or body.get("podcast_title")
    media_title = body.get("media_title") or body.get("episode_title")
    summary_s3_key = body.get("summary_s3_key")

    if not media_key:
        logger.error(f"Missing media_key in event: {body}")
        return

    # Load summary content once for all watchers
    summary_content = await _load_summary_content(summary_s3_key)

    # Fetch watchers
    watchers = await media_watchers.list_watchers(media_key)
    if not watchers:
        logger.info(f"No watchers for media key {media_key}")
        return

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

            # CRITICAL: Send email FIRST, before charging minutes
            try:
                await _notify_watcher_completion(
                    watcher=w,
                    source_title=source_title,
                    media_title=media_title,
                    summary_content=summary_content,
                )
                await media_watchers.mark_watcher_emailed(media_key, w.get("user_id"))
                logger.info(f"Successfully sent completion email to {w.get('email')} for media key {media_key}")
            except Exception as email_error:
                # If email sending fails, DO NOT charge minutes
                logger.error(f"Failed to send email to {w.get('email')} for media key {media_key}: {email_error}")
                await media_watchers.mark_watcher_failed(
                    media_key,
                    w.get("user_id"),
                    reason=f"email_failed: {str(email_error)}"
                )
                # Skip finalize_usage - user will not be charged
                continue

            # ONLY NOW: Finalize usage (charge minutes) AFTER successful email delivery
            ok = await finalize_usage(job_id, minutes_used)
            if not ok:
                # Edge case: Email sent but billing failed
                # Policy: spotify -> send error email; manual -> no email
                logger.error(f"Email sent successfully but failed to finalize usage for job {job_id}")
                if (w.get("source") or "").lower() == "spotify":
                    await _notify_watcher_insufficient_minutes(watcher=w)
                await media_watchers.mark_watcher_failed(
                    media_key,
                    w.get("user_id"),
                    reason="insufficient_minutes_after_email"
                )
                continue

            logger.info(f"Successfully processed watcher {w.get('user_id')} for media key {media_key}: email sent + {minutes_used} minutes charged")

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
