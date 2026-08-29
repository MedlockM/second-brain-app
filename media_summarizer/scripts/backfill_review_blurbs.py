"""Backfill the ``review_blurb`` artifact for library rows that predate it (task-323).

Every media saved before this type existed has no blurb, and nothing will ever
generate one for it: the trigger runs at the end of ingestion, and those ingestions
are long finished. This walks the library and triggers the missing ones.

Usage:
  uv run python -m media_summarizer.scripts.backfill_review_blurbs

Guard rails (env), because this spends real money on a real provider and the only
thing standing between a typo and the whole library is this script:

  - ``REVIEW_BLURB_BACKFILL_DELAY_SECONDS`` (float, default 2.0)
        Pause after each *triggered* generation. Same role as
        ``DIGEST_STAGGER_DELAY_SECONDS`` in the digest scheduler: the artifact queue
        and the provider see a trickle instead of a burst, so a backfill cannot
        starve the interactive generations a user is waiting on.
  - ``REVIEW_BLURB_BACKFILL_LIMIT`` (int, default 25)
        Hard ceiling on the number of generations triggered in one run. Deliberately
        small: the intended use is to run it, read the count, and run it again. Rows
        already provisioned are skipped, so re-running walks forward instead of
        redoing work. Set it to ``0`` for a dry run — every row is inspected and
        counted, nothing is generated.

Rows skipped without spending anything: soft-deleted rows, rows that already carry
a blurb, and rows with no transcript (the skip lives in
``review_blurb_service.trigger_review_blurb_generation``, so the CLI and the
ingestion hook cannot disagree about what is worth generating).
"""

from __future__ import annotations

import asyncio
import logging
import os
from typing import List

from media_summarizer.core.services.review_blurb_service import (
    trigger_review_blurb_generation,
)
from media_summarizer.utils import user_media as user_media_store

logger = logging.getLogger(__name__)

STAGGER_DELAY_SECONDS = float(
    os.environ.get("REVIEW_BLURB_BACKFILL_DELAY_SECONDS", "2.0")
)
MAX_TRIGGERED = int(os.environ.get("REVIEW_BLURB_BACKFILL_LIMIT", "25"))


async def _all_user_ids() -> List[str]:
    """Scan the users table. Fine for V1 scale, same as the digest scheduler."""
    from media_summarizer.utils.database_async import (
        USERS_TABLE,
        _dynamodb_client_kwargs,
        get_session,
    )

    session = get_session()
    user_ids: List[str] = []
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


async def backfill() -> tuple[int, int]:
    """Trigger the missing blurbs. Returns ``(triggered, skipped)``."""
    triggered = 0
    skipped = 0

    for user_id in await _all_user_ids():
        for record in await user_media_store.list_library_for_user(user_id):
            if record.review_blurb is not None and record.review_blurb.hook.strip():
                skipped += 1
                continue
            if triggered >= MAX_TRIGGERED:
                skipped += 1
                continue

            artifact_id = await trigger_review_blurb_generation(
                user_id, record.media_item_id
            )
            if artifact_id is None:
                skipped += 1
                continue

            triggered += 1
            print(
                f"triggered {triggered}/{MAX_TRIGGERED}: "
                f"{record.media_item_id} -> {artifact_id}"
            )
            await asyncio.sleep(STAGGER_DELAY_SECONDS)

    return triggered, skipped


async def _run() -> None:
    triggered, skipped = await backfill()
    print(
        f"review_blurb backfill done: {triggered} triggered "
        f"(limit {MAX_TRIGGERED}), {skipped} skipped"
    )
    if triggered >= MAX_TRIGGERED:
        print(
            "The limit was reached, so rows are still missing a blurb. "
            "Run again to continue where this run stopped."
        )


def main() -> None:
    from media_summarizer.utils.logging_config import setup_logging

    setup_logging("backfill-review-blurbs")
    asyncio.run(_run())


if __name__ == "__main__":
    main()
