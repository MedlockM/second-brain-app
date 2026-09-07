"""
Digest scheduler worker.

Designed to be invoked by a cron/scheduler (e.g. EventBridge Scheduler, CloudWatch Events).

Responsibilities:
1. Capture daily/weekly digests for all users with digest enabled
2. Publish the weekly digest (stamp ``published_at`` + send push notification)

It generates nothing. There used to be a third responsibility here — pre-generating
a ``summary_short`` per upcoming digest item, staggered to spare the LLM — and it
went with the payload it fed (task-366): the digest shows the media page, whose AI
tab offers its tiles to generate on demand like anywhere else.

Usage:
  uv run python -m media_summarizer.workers.digest.scheduler [--mode daily|weekly]
"""

from __future__ import annotations

import asyncio
import logging
import os
import sys
from datetime import datetime, timezone
from typing import List

from media_summarizer.core.models.digest import DigestRecord
from media_summarizer.core.services import digest_service
from media_summarizer.utils import digest_db, sqs

logger = logging.getLogger(__name__)

# Push notification queue for the weekly digest.
#
# Deliberately OPTIONAL, unlike every other queue name in the codebase. Real push
# notifications are post-V1 (task-102 keeps this producer alive for then), so
# Terraform does not create the queue in any environment and the variable is
# unset everywhere. It used to default to the literal "push-notification-queue",
# which meant every weekly digest tried to publish to a queue that did not exist
# and logged an error. When the queue is provisioned, inject
# PUSH_NOTIFICATION_QUEUE and this producer starts working with no code change.
PUSH_NOTIFICATION_QUEUE = os.environ.get("PUSH_NOTIFICATION_QUEUE", "").strip()


async def _get_all_user_ids() -> List[str]:
    """Get all user IDs from the users table. Fine for V1 scale."""
    from media_summarizer.utils.database_async import (
        USERS_TABLE,
        _dynamodb_client_kwargs,
        get_session,
    )

    session = get_session()
    user_ids = []
    async with session.resource("dynamodb", **_dynamodb_client_kwargs()) as dynamodb:
        table = await dynamodb.Table(USERS_TABLE)
        scan_kwargs = {"ProjectionExpression": "id"}
        while True:
            resp = await table.scan(**scan_kwargs)
            for item in resp.get("Items", []):
                user_ids.append(item["id"])
            last_key = resp.get("LastEvaluatedKey")
            if not last_key:
                break
            scan_kwargs["ExclusiveStartKey"] = last_key
    return user_ids


async def _is_digest_enabled(user_id: str) -> bool:
    """Check if digest is enabled for a user (True by default)."""
    settings = await digest_db.get_user_digest_settings(user_id)
    if settings is None:
        return True  # Active by default
    return settings.digest_enabled


async def assemble_daily_digests() -> int:
    """
    Capture the daily digest of every user with the daily digest enabled.
    Returns the number of digests captured.

    The period is not a parameter: the service resolves the window the last 18:30
    send announced, so running this worker twice in the same evening captures the
    same list once and reads it back the second time.
    """
    logger.info("Starting daily digest assembly")

    user_ids = await _get_all_user_ids()
    assembled = 0

    for user_id in user_ids:
        if not await _is_digest_enabled(user_id):
            continue

        settings = await digest_service.get_user_digest_settings(user_id)
        if not settings.daily_digest_enabled:
            continue

        try:
            digest = await digest_service.get_or_assemble_daily_digest(user_id)
            assembled += 1
            logger.debug(
                "Daily digest assembled for user %s (%s): %d items",
                user_id,
                digest.period_key,
                len(digest.media_items),
            )
        except Exception as exc:
            logger.error(
                "Failed to assemble daily digest for user %s: %s", user_id, exc
            )

    logger.info("Daily digest assembly complete: %d digests assembled", assembled)
    return assembled


async def assemble_and_publish_weekly_digests() -> int:
    """
    Capture and publish the weekly digest of every user.
    Sends a push notification for each digest published by this run.
    Returns the number of digests published.
    """
    logger.info("Starting weekly digest assembly and publication")

    user_ids = await _get_all_user_ids()
    published = 0

    for user_id in user_ids:
        if not await _is_digest_enabled(user_id):
            continue

        settings = await digest_service.get_user_digest_settings(user_id)
        if not settings.weekly_digest_enabled:
            continue

        try:
            digest = await digest_service.get_or_assemble_weekly_digest(user_id)

            # Publish once, and only a period that holds something. `published_at`
            # is the whole record of that: set means the notification went out.
            if digest.published_at is None and digest.media_items:
                digest.published_at = datetime.now(timezone.utc).isoformat()
                await digest_db.save_digest(digest)

                # Send push notification for weekly digest
                await _send_weekly_digest_push_notification(user_id, digest)
                published += 1

                logger.info(
                    "Weekly digest published for user %s: %d items",
                    user_id,
                    len(digest.media_items),
                )
        except Exception as exc:
            logger.error(
                "Failed to publish weekly digest for user %s: %s", user_id, exc
            )

    logger.info("Weekly digest publication complete: %d digests published", published)
    return published


async def _send_weekly_digest_push_notification(
    user_id: str, digest: DigestRecord
) -> None:
    """Send a push notification to the user about their weekly digest.

    No-op while PUSH_NOTIFICATION_QUEUE is unset (the V1 default): the digest is
    still assembled and published, users just discover it by polling.
    """
    if not PUSH_NOTIFICATION_QUEUE:
        logger.debug(
            "PUSH_NOTIFICATION_QUEUE unset; skipping push for user %s (weekly digest %s)",
            user_id,
            digest.period_key,
        )
        return

    item_count = len(digest.media_items)
    message = {
        "user_id": user_id,
        "notification_type": "weekly_digest_published",
        "title": "Your weekly digest is ready",
        "body": f"You have {item_count} {'item' if item_count == 1 else 'items'} in your weekly digest.",
        "data": {
            "digest_type": "weekly",
            "period_key": digest.period_key,
            "item_count": item_count,
        },
    }

    try:
        await sqs.send_message(
            queue_name=PUSH_NOTIFICATION_QUEUE,
            message_body=message,
        )
        logger.info(
            "Push notification queued for user %s (weekly digest %s)",
            user_id,
            digest.period_key,
        )
    except Exception as exc:
        logger.error(
            "Failed to queue push notification for user %s: %s", user_id, exc
        )


async def run(mode: str = "all") -> None:
    """
    Main entry point for the digest scheduler.

    Modes:
    - daily: Capture daily digests
    - weekly: Capture and publish weekly digests (with push notification)
    - all: Run both, in order
    """
    logger.info("Digest scheduler starting in mode: %s", mode)

    if mode in ("daily", "all"):
        await assemble_daily_digests()

    if mode in ("weekly", "all"):
        await assemble_and_publish_weekly_digests()

    logger.info("Digest scheduler finished (mode: %s)", mode)


if __name__ == "__main__":
    from media_summarizer.utils.logging_config import setup_logging

    setup_logging("digest-scheduler")

    mode = "all"
    if len(sys.argv) > 1 and sys.argv[1] == "--mode" and len(sys.argv) > 2:
        mode = sys.argv[2]

    asyncio.run(run(mode))
