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

Rows are read **raw**, with a table scan, and never through ``UserMediaRecord``: that
model degrades a blurb in an unknown shape to ``None`` so a stale row stays readable,
which is exactly the value this script exists to find. Reading through it made the
first run report zero rows to purge while 22 carried the v1 prose.

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
from typing import Any, Dict, List, Tuple

from media_summarizer.core.models.media_artifact import MediaArtifactType
from media_summarizer.utils import media_artifacts
from media_summarizer.utils import user_media as user_media_store

logger = logging.getLogger(__name__)

MAX_PURGED = int(os.environ.get("REVIEW_BLURB_PURGE_LIMIT", "200"))


async def _rows_carrying_a_blurb() -> List[Tuple[str, str]]:
    """``(user_id, media_item_id)`` of every row that still holds a blurb.

    One scan with ``attribute_exists``, on the raw item: whatever shape the value
    is in — the v1 prose string, a v2 map — the row needs purging, and only the
    table itself can say so.
    """
    from media_summarizer.utils import database_async

    session = database_async.get_session()
    rows: List[Tuple[str, str]] = []
    async with session.resource(
        "dynamodb",
        region_name=database_async.AWS_REGION,
    ) as dynamodb:
        table = await dynamodb.Table(user_media_store.user_media_table_name())
        scan_kwargs: Dict[str, Any] = {
            "ProjectionExpression": "user_id, media_item_id",
            "FilterExpression": "attribute_exists(review_blurb)",
        }
        while True:
            resp = await table.scan(**scan_kwargs)
            for item in resp.get("Items", []):
                rows.append((item["user_id"], item["media_item_id"]))
            last_key = resp.get("LastEvaluatedKey")
            if not last_key:
                break
            scan_kwargs["ExclusiveStartKey"] = last_key
    return rows


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


async def _delete_blurb_artifacts() -> int:
    """Delete every ``review_blurb`` artifact record, whoever owns it.

    A scan filtered on the type, rather than one scope query per row. The scope of
    this artifact is keyed by the **content** — ``<user>#media#mkey_v1_…`` — not by
    the library row, so there is no scope key to rebuild from a ``media_item_id``;
    trying deleted nothing on the first run while all 22 records sat there. The
    table is small and this is a one-shot maintenance tool, so the scan is the
    honest way to say "every record of this type".
    """
    from media_summarizer.utils import database_async

    session = database_async.get_session()
    artifact_ids: List[str] = []
    async with session.resource(
        "dynamodb",
        region_name=database_async.AWS_REGION,
    ) as dynamodb:
        table = await dynamodb.Table(media_artifacts.MEDIA_ARTIFACTS_TABLE)
        scan_kwargs: Dict[str, Any] = {
            "ProjectionExpression": "artifact_id",
            "FilterExpression": "artifact_type = :t",
            "ExpressionAttributeValues": {
                ":t": MediaArtifactType.REVIEW_BLURB.value
            },
        }
        while True:
            resp = await table.scan(**scan_kwargs)
            artifact_ids.extend(item["artifact_id"] for item in resp.get("Items", []))
            last_key = resp.get("LastEvaluatedKey")
            if not last_key:
                break
            scan_kwargs["ExclusiveStartKey"] = last_key

    for artifact_id in artifact_ids:
        await media_artifacts.delete_media_artifact(artifact_id)
    return len(artifact_ids)


async def purge() -> tuple[int, int, int]:
    """Purge the blurbs. Returns ``(rows_purged, artifacts_deleted, rows_left)``."""
    rows_purged = 0
    artifacts_deleted = 0
    rows_left = 0

    for user_id, media_item_id in await _rows_carrying_a_blurb():
        if rows_purged >= MAX_PURGED:
            rows_left += 1
            continue

        await _remove_blurb_attribute(user_id=user_id, media_item_id=media_item_id)
        rows_purged += 1
        print(f"purged row {rows_purged}/{MAX_PURGED}: {media_item_id}")

    # Only once every row is clear: an artifact deleted while its row still points
    # at it would be regenerated by the next completion event and mirrored back.
    if MAX_PURGED > 0:
        artifacts_deleted = await _delete_blurb_artifacts()
        print(f"deleted {artifacts_deleted} review_blurb artifact record(s)")

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
