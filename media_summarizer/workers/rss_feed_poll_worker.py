"""
RSS Feed polling worker.

Periodically polls all active RSS feed subscriptions and routes new items
to the appropriate ingestion queues (article extraction or audio download).

Architecture:
- Triggered by an SQS delayed message (self-re-enqueuing) or external scheduler
- For each active feed, parse the RSS and detect new items
- Audio enclosures -> ingest-url pipeline (audio path)
- Article links -> ingest-url pipeline (web/article path)
- Deduplication via guid tracking in the UserRssFeed record
"""

import asyncio
import json
import logging
import os

from media_summarizer.core.services.rss_feed_service import poll_feed
from media_summarizer.utils import database_async, sqs
from media_summarizer.utils.logging_config import log_event, setup_logging
from media_summarizer.workers.base_worker import process_message_with_retry

logger = logging.getLogger(__name__)

RSS_FEED_POLL_QUEUE = os.environ.get("RSS_FEED_POLL_QUEUE", "rss-feed-poll-queue")
ARTICLE_EXTRACTION_QUEUE = os.environ.get("ARTICLE_EXTRACTION_QUEUE", "article-extraction-queue")
DEEPGRAM_TRANSCRIPTION_QUEUE = os.environ.get("DEEPGRAM_TRANSCRIPTION_QUEUE", "deepgram-transcription-queue")

# Polling interval: re-enqueue after this many seconds (default 1 hour)
POLL_INTERVAL_SECONDS = int(os.environ.get("RSS_POLL_INTERVAL_SECONDS", "3600"))


async def _route_item_to_pipeline(
    item: dict,
    user_id: str,
    feed_url: str,
) -> None:
    """Route a single feed item to the appropriate ingestion queue.

    - Audio items -> deepgram-transcription-queue (direct audio URL, no download worker)
    - Article items -> article-extraction-queue (web URL)
    """
    import uuid

    item_type = item.get("item_type", "article")
    link = item.get("link") or ""
    audio_url = item.get("audio_url") or ""
    title = item.get("title") or ""
    guid = item.get("guid") or ""

    # Create a pseudo job_id for tracking (the actual job will be created
    # when the downstream worker processes the message, or we create it here)
    from media_summarizer.core.models import ProcessingJob

    # Look up user for email
    user = await database_async.get_user_by_id(user_id)
    if not user:
        logger.warning("User %s not found, skipping feed item %s", user_id, guid)
        return

    job = ProcessingJob(
        user_id=user_id,
        user_email=user.email,
        source_url=feed_url,
        media_key=guid,
    )
    job = await database_async.create_processing_job(job)

    if item_type == "audio" and audio_url:
        # Route to deepgram transcription (direct path, no download worker needed)
        await sqs.send_message(
            queue_name=DEEPGRAM_TRANSCRIPTION_QUEUE,
            message_body={
                "job_id": job.id,
                "user_id": user_id,
                "audio_url": audio_url,
                "media_key": guid,
                "feed_url": feed_url,
                "episode_guid": guid,
                "episode_title": title,
                "normalized_url": audio_url,
                "source_platform": "rss_feed",
            },
        )
        log_event(
            logger,
            logging.INFO,
            "rss_poll.item_routed",
            "RSS item routed to deepgram transcription",
            job_id=job.id,
            item_type="audio",
            guid=guid,
        )
    else:
        # Route to article extraction
        target_url = link or ""
        if not target_url:
            logger.warning("Feed item %s has no link, skipping", guid)
            return

        await sqs.send_message(
            queue_name=ARTICLE_EXTRACTION_QUEUE,
            message_body={
                "job_id": job.id,
                "user_id": user_id,
                "normalized_url": target_url,
                "source_platform": "rss_feed",
                "media_key": guid,
            },
        )
        log_event(
            logger,
            logging.INFO,
            "rss_poll.item_routed",
            "RSS item routed to article extraction",
            job_id=job.id,
            item_type="article",
            guid=guid,
        )


async def poll_all_active_feeds() -> int:
    """Poll all active feeds and route new items.

    Returns:
        Total number of new items ingested across all feeds.
    """
    feeds = await database_async.get_active_rss_feeds()
    total_new_items = 0

    for feed in feeds:
        try:
            new_items = await poll_feed(feed)
            for item in new_items:
                try:
                    await _route_item_to_pipeline(
                        item=item,
                        user_id=feed.user_id,
                        feed_url=feed.feed_url,
                    )
                    total_new_items += 1
                except Exception as e:
                    logger.error(
                        "Failed to route item %s from feed %s: %s",
                        item.get("guid"),
                        feed.id,
                        str(e),
                    )
        except Exception as e:
            logger.error(
                "Failed to poll feed %s (%s): %s",
                feed.id,
                feed.feed_url,
                str(e),
            )

    log_event(
        logger,
        logging.INFO,
        "rss_poll.cycle_complete",
        "RSS polling cycle completed",
        feeds_polled=len(feeds),
        new_items=total_new_items,
    )
    return total_new_items


async def process_message(message: dict) -> None:
    """Process a poll trigger message from SQS.

    The message can be:
    - A general "poll_all" trigger (no specific feed)
    - A specific feed_id to poll only that feed
    """
    body = {}
    if "Body" in message:
        body = json.loads(message["Body"])
    else:
        body = message

    action = body.get("action", "poll_all")

    if action == "poll_all":
        await poll_all_active_feeds()
    elif action == "poll_single" and body.get("feed_id"):
        feed = await database_async.get_rss_feed_by_id(body["feed_id"])
        if feed and feed.status.value == "active":
            new_items = await poll_feed(feed)
            for item in new_items:
                await _route_item_to_pipeline(
                    item=item,
                    user_id=feed.user_id,
                    feed_url=feed.feed_url,
                )


async def _schedule_next_poll() -> None:
    """Re-enqueue a poll trigger with a delay (self-scheduling)."""
    await sqs.send_message(
        queue_name=RSS_FEED_POLL_QUEUE,
        message_body={"action": "poll_all"},
        delay_seconds=min(POLL_INTERVAL_SECONDS, 900),  # SQS max delay is 900s
    )


async def poll_queue() -> None:
    """Main polling loop: consume messages from the RSS feed poll queue."""
    while True:
        try:
            messages = await sqs.receive_messages(
                queue_name=RSS_FEED_POLL_QUEUE,
                max_messages=1,
                wait_time_seconds=20,
                visibility_timeout=600,  # 10 minutes for full poll cycle
            )

            if messages:
                for msg in messages:
                    await process_message_with_retry(
                        message=msg,
                        processor=process_message,
                        queue_name=RSS_FEED_POLL_QUEUE,
                        max_retries=2,
                        worker_name="rss_feed_poll",
                    )
                # Schedule next poll after completing
                await _schedule_next_poll()
            else:
                # No messages -- schedule a trigger if queue is empty
                await _schedule_next_poll()
                await asyncio.sleep(5)

        except Exception as e:
            log_event(
                logger,
                logging.ERROR,
                "worker.poll_error",
                "RSS feed poll queue error",
                queue=RSS_FEED_POLL_QUEUE,
                error_type=type(e).__name__,
                error_code="POLL_ERROR",
            )
            await asyncio.sleep(10)


async def main() -> None:
    setup_logging("worker-rss-feed-poll")
    log_event(
        logger,
        logging.INFO,
        "worker.started",
        "RSS feed poll worker started",
        queue=RSS_FEED_POLL_QUEUE,
    )

    # Seed the first poll trigger
    await _schedule_next_poll()
    await poll_queue()


if __name__ == "__main__":
    asyncio.run(main())
