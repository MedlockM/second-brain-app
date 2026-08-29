"""Purge the v1 ``review_blurb`` artifacts so v2 can be generated in their place.

Bumping ``REVIEW_BLURB_ARTIFACT_GENERATOR_VERSION`` regenerates **nothing**:
``artifact_service.build_artifact_id`` deliberately keeps the generator version out
of the hash, precisely so that a prompt bump does not hand out a fresh generation
per media. The corollary is that a change of *shape* — v1's prose paragraph to v2's
triage card — has to be undone by hand before the backfill can do anything.

Two deletions, and both are required:

  1. **The attribute on the library row.** A row that still carries a blurb is
     skipped by the trigger, so leaving it would make the backfill a no-op.
  2. **The artifact records.** Without this, ``plan_artifact_generation`` finds the
     existing entry, answers ``REUSED``, and the repair path re-reads the old S3
     object and puts the old paragraph straight back on the row.

The S3 objects are deliberately left alone: their key derives from the artifact id,
which is a function of the request and not of the prompt, so the new generation
writes over them.

Usage:
  uv run python -m media_summarizer.scripts.purge_review_blurbs
  # then, once this reports 0 remaining:
  uv run python -m media_summarizer.scripts.backfill_review_blurbs

Guard rails (env), mirroring those of the backfill:

  - ``REVIEW_BLURB_PURGE_LIMIT`` (int, default 200)
        Hard ceiling on the number of rows purged in one run. Set it to ``0`` for a
        dry run — every row is inspected and counted, nothing is deleted.
"""

from __future__ import annotations

import asyncio
import logging
import os
from typing import List

from media_summarizer.core.models.media_artifact import (
    ArtifactScope,
    MediaArtifactType,
    build_scope_key,
)
from media_summarizer.utils import media_artifacts
from media_summarizer.utils import user_media as user_media_store

logger = logging.getLogger(__name__)

MAX_PURGED = int(os.environ.get("REVIEW_BLURB_PURGE_LIMIT", "200"))


async def _all_user_ids() -> List[str]:
    """Scan the users table. Fine for V1 scale, same as the backfill."""
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


async def _remove_blurb_attribute(*, user_id: str, media_item_id: str) -> None:
    """``REMOVE review_blurb`` on one row.

    Written here rather than through ``user_media.update_attributes``: that helper
    only ever emits ``SET`` and drops ``None`` values from its payload, so it is
    structurally unable to erase an attribute.
    """
    from media_summarizer.utils import database_async

    session = database_async.get_session()
    async with session.resource(
        "dynamodb",
        region_name=database_async.AWS_REGION,
    ) as dynamodb:
        table = await dynamodb.Table(user_media_store.user_media_table_name())
        await table.update_item(
            Key={"user_id": user_id, "media_item_id": media_item_id},
            UpdateExpression="REMOVE review_blurb",
        )


async def _delete_blurb_artifacts(*, user_id: str, media_item_id: str) -> int:
    """Delete every ``review_blurb`` artifact recorded for one media scope."""
    records, _ = await media_artifacts.list_artifacts_by_scope(
        scope_key=build_scope_key(
            user_id=user_id,
            scope=ArtifactScope.MEDIA,
            scope_id=media_item_id,
        )
    )
    deleted = 0
    for record in records:
        if record.artifact_type != MediaArtifactType.REVIEW_BLURB:
            continue
        await media_artifacts.delete_media_artifact(record.artifact_id)
        deleted += 1
    return deleted


async def purge() -> tuple[int, int, int]:
    """Purge the blurbs. Returns ``(rows_purged, artifacts_deleted, rows_left)``."""
    rows_purged = 0
    artifacts_deleted = 0
    rows_left = 0

    for user_id in await _all_user_ids():
        for record in await user_media_store.list_library_for_user(user_id):
            if record.review_blurb is None:
                continue
            if rows_purged >= MAX_PURGED:
                rows_left += 1
                continue

            await _remove_blurb_attribute(
                user_id=user_id, media_item_id=record.media_item_id
            )
            deleted = await _delete_blurb_artifacts(
                user_id=user_id, media_item_id=record.media_item_id
            )
            rows_purged += 1
            artifacts_deleted += deleted
            print(
                f"purged {rows_purged}/{MAX_PURGED}: "
                f"{record.media_item_id} ({deleted} artifact(s))"
            )

    return rows_purged, artifacts_deleted, rows_left


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    rows_purged, artifacts_deleted, rows_left = asyncio.run(purge())
    if MAX_PURGED == 0:
        print(f"dry run: {rows_left} row(s) carry a blurb and would be purged")
        return
    print(
        f"done: {rows_purged} row(s) purged, {artifacts_deleted} artifact(s) "
        f"deleted, {rows_left} row(s) left for a next run"
    )


if __name__ == "__main__":
    main()
