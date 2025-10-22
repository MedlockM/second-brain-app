"""
Episode completed events consumer — fan-out notifications to episode watchers.

- Consumes events from EPISODE_COMPLETED_EVENTS_QUEUE (episode-completed-events)
- For each episode GUID, fetches watchers, finalizes their minute usage, and sends completion emails with from_cache=True
- Handles insufficient minutes per policy: spotify → email error; manual → no email, mark failed
"""
from __future__ import annotations

import os
import json
import asyncio
import logging
from typing import Any, Dict, List, Optional

from media_summarizer.utils import sqs, s3
from media_summarizer.utils import episode_watchers
from media_summarizer.core.services.minute_pool import finalize_usage

logger = logging.getLogger(__name__)

EPISODE_COMPLETED_EVENTS_QUEUE = os.environ.get("EPISODE_COMPLETED_EVENTS_QUEUE", "episode-completed-events")
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
        logger.warning(f"Failed to load summary content {summary_s3_key}: {e}
")
        return None


async def _notify_watcher_completion(*, watcher: Dict[str, Any], podcast_title: Optional[str], episode_title: Optional[str], summary_content: Optional[Dict[str, Any]]) -> None:
    await sqs.send_message(
        queue_name=NOTIFICATION_QUEUE,
        message_body={
            "notification_type": "completion",
            "job_id": watcher.get("job_id"),
            "email": watcher.get("email"),
            "podcast_title": podcast_title,
            "episode_title": episode_title,
            "summary_content": summary_content,
            "from_cache": True,
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
            "error": "Insufficient minutes to finalize usage for this episode.",
            "step": "billing",
            "from_cache": True,
        },
    )


async def process_event(message: Dict[str, Any]) -> None:
    body = json.loads(message.get("Body", "{}"))
    if body.get("event_type") != "episode_completed":
        logger.warning(f"Ignoring unknown event type: {body.get('event_type')}")
        return

    episode_guid = body.get("episode_guid")
    minutes_used = int(body.get("minutes_used") or 0)
    podcast_title = body.get("podcast_title")
    episode_title = body.get("episode_title")
    summary_s3_key = body.get("summary_s3_key")

    if not episode_guid:
        logger.error(f"Missing episode_guid in event: {body}")
        return

    # Load summary content once for all watchers
    summary_content = await _load_summary_content(summary_s3_key)

    # Fetch watchers
    watchers = await episode_watchers.list_watchers(episode_guid)
    if not watchers:
        logger.info(f"No watchers for episode {episode_guid}")
        return

    # Fan-out
    for w in watchers:
        try:
            ok = await finalize_usage(w.get("job_id"), minutes_used)
            if not ok:
                # Policy: spotify → email; manual → no email
                if (w.get("source") or "").lower() == "spotify":
                    await _notify_watcher_insufficient_minutes(watcher=w)
                await episode_watchers.mark_watcher_failed(episode_guid, w.get("user_id"), reason="insufficient_minutes")
                continue

            await _notify_watcher_completion(
                watcher=w,
                podcast_title=podcast_title,
                episode_title=episode_title,
                summary_content=summary_content,
            )
            await episode_watchers.mark_watcher_emailed(episode_guid, w.get("user_id"))

        except Exception as e:
            logger.error(f"Error processing watcher {w.get('user_id')} for {episode_guid}: {e}")
            try:
                await episode_watchers.mark_watcher_failed(episode_guid, w.get("user_id"), reason=str(e))
            except Exception:
                pass


async def poll_queue() -> None:
    logger.info("Starting episode-completed-events consumer")
    while True:
        try:
            messages = await sqs.receive_messages(
                queue_name=EPISODE_COMPLETED_EVENTS_QUEUE,
                max_messages=10,
                wait_time_seconds=20,
            )
            if messages:
                for m in messages:
                    try:
                        await process_event(m)
                        rh = m.get("ReceiptHandle")
                        if rh:
                            await sqs.delete_message(queue_name=EPISODE_COMPLETED_EVENTS_QUEUE, receipt_handle=rh)
                    except Exception as e:
                        logger.error(f"Failed to process event: {e}")
            await asyncio.sleep(1)
        except Exception as e:
            logger.error(f"Polling error: {e}")
            await asyncio.sleep(RETRY_DELAY)


async def main() -> None:
    await poll_queue()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(main())
