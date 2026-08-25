"""
Persistence helpers for AI artifacts.

One table, one index. ``scope-index`` (hash ``scope_key``, range ``created_at``)
is what makes the append-only history readable: DynamoDB returns the entries
newest-first with ``ScanIndexForward=False``, so nothing is sorted in Python and
pagination stays correct. The index projects only the attributes the listing
renders, so a page costs one query with no read of the base table and no S3
access — ``sources`` (up to ~5 kB) is deliberately left out of it and fetched
only when a single entry is opened.
"""

from __future__ import annotations

import logging
import os
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from boto3.dynamodb.conditions import Key
from botocore.exceptions import ClientError

from media_summarizer.core.models.media_artifact import MediaArtifactRecord
from media_summarizer.utils import database_async
from media_summarizer.utils.env import required_env

logger = logging.getLogger(__name__)

MEDIA_ARTIFACTS_TABLE = required_env("MEDIA_ARTIFACTS_TABLE")
SCOPE_INDEX = os.environ.get("MEDIA_ARTIFACTS_SCOPE_INDEX", "scope-index")


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class ArtifactAlreadyExistsError(Exception):
    """A record with this deterministic ``artifact_id`` is already stored."""


async def create_media_artifact(record: MediaArtifactRecord) -> MediaArtifactRecord:
    """Write a new history entry, refusing to overwrite an existing one.

    The conditional write is what makes two concurrent taps one generation: they
    compute the same ``artifact_id``, so the loser raises
    :class:`ArtifactAlreadyExistsError` and the caller hands back the winner. It is
    also the guard behind permanent reuse — an id that already exists is never
    written a second time from this path.
    """
    session = database_async.get_session()
    try:
        async with session.resource(
            "dynamodb",
            region_name=database_async.AWS_REGION,
        ) as dynamodb:
            table = await dynamodb.Table(MEDIA_ARTIFACTS_TABLE)
            await table.put_item(
                Item=record.to_dynamodb_item(),
                ConditionExpression="attribute_not_exists(artifact_id)",
            )
            return record
    except ClientError as exc:
        if exc.response.get("Error", {}).get("Code") == "ConditionalCheckFailedException":
            raise ArtifactAlreadyExistsError(record.artifact_id) from exc
        raise


async def reclaim_failed_artifact(record: MediaArtifactRecord) -> bool:
    """Rerun a failed entry in place, or refuse.

    The ``artifact_id`` no longer carries a time component, so a failed entry
    would otherwise bar its key forever: one transient provider error and that
    artifact type could never be generated again over those sources. Reclaiming
    replaces the row with a fresh ``queued`` one under the same id — the history
    keeps one entry per (sources, type) rather than a trail of failures.

    Returns ``False`` when the row is no longer ``failed``, which means a
    concurrent request already reclaimed it and owns the generation.
    """
    session = database_async.get_session()
    try:
        async with session.resource(
            "dynamodb",
            region_name=database_async.AWS_REGION,
        ) as dynamodb:
            table = await dynamodb.Table(MEDIA_ARTIFACTS_TABLE)
            await table.put_item(
                Item=record.to_dynamodb_item(),
                ConditionExpression="attribute_exists(artifact_id) AND #st = :failed",
                ExpressionAttributeNames={"#st": "status"},
                ExpressionAttributeValues={":failed": "failed"},
            )
            return True
    except ClientError as exc:
        if exc.response.get("Error", {}).get("Code") == "ConditionalCheckFailedException":
            return False
        raise


async def update_media_artifact(record: MediaArtifactRecord) -> MediaArtifactRecord:
    session = database_async.get_session()
    async with session.resource(
        "dynamodb",
        region_name=database_async.AWS_REGION,
    ) as dynamodb:
        table = await dynamodb.Table(MEDIA_ARTIFACTS_TABLE)
        await table.put_item(Item=record.to_dynamodb_item())
        return record


async def claim_artifact_generation(
    *,
    artifact_id: str,
    lease_expires_at: datetime,
) -> bool:
    """Move an entry to ``generating`` and take a lease on it, or refuse.

    Returns ``False`` when the entry is already terminal or another worker holds
    a live lease. That is how at-least-once SQS delivery and Lambda replays are
    absorbed: the loser acknowledges its message and never calls the LLM, with no
    auxiliary lock table involved.
    """
    session = database_async.get_session()
    now_iso = _now_iso()
    try:
        async with session.resource(
            "dynamodb",
            region_name=database_async.AWS_REGION,
        ) as dynamodb:
            table = await dynamodb.Table(MEDIA_ARTIFACTS_TABLE)
            await table.update_item(
                Key={"artifact_id": artifact_id},
                UpdateExpression=(
                    "SET #st = :generating, lease_expires_at = :lease, "
                    "updated_at = :now REMOVE error_code, error_message"
                ),
                ConditionExpression=(
                    "attribute_exists(artifact_id) AND ("
                    "#st = :queued OR ("
                    "#st = :generating AND ("
                    "attribute_not_exists(lease_expires_at) OR lease_expires_at < :now"
                    ")))"
                ),
                ExpressionAttributeNames={"#st": "status"},
                ExpressionAttributeValues={
                    ":generating": "generating",
                    ":queued": "queued",
                    ":lease": lease_expires_at.isoformat(),
                    ":now": now_iso,
                },
            )
            return True
    except ClientError as exc:
        if exc.response.get("Error", {}).get("Code") == "ConditionalCheckFailedException":
            return False
        raise


async def get_media_artifact_by_id(artifact_id: str) -> Optional[MediaArtifactRecord]:
    session = database_async.get_session()
    async with session.resource(
        "dynamodb",
        region_name=database_async.AWS_REGION,
    ) as dynamodb:
        table = await dynamodb.Table(MEDIA_ARTIFACTS_TABLE)
        resp = await table.get_item(
            Key={"artifact_id": artifact_id},
            ConsistentRead=True,
        )
        item = resp.get("Item")
        if not item:
            return None
        return MediaArtifactRecord.from_dynamodb_item(item)


async def delete_media_artifact(artifact_id: str) -> None:
    """Delete one artifact row. Idempotent: a missing row is a silent no-op."""
    session = database_async.get_session()
    async with session.resource(
        "dynamodb",
        region_name=database_async.AWS_REGION,
    ) as dynamodb:
        table = await dynamodb.Table(MEDIA_ARTIFACTS_TABLE)
        await table.delete_item(Key={"artifact_id": artifact_id})


async def list_artifacts_by_scope(
    *,
    scope_key: str,
    limit: Optional[int] = None,
    cursor: Optional[str] = None,
    forward: bool = False,
) -> Tuple[List[MediaArtifactRecord], Optional[str]]:
    """One page of a scope's history, newest first, plus the next cursor.

    The cursor is the ``created_at`` of the last entry returned, which is the
    index's range key: no opaque encoding to maintain, and a resumed listing
    lands exactly where the previous page stopped.
    """
    session = database_async.get_session()
    async with session.resource(
        "dynamodb",
        region_name=database_async.AWS_REGION,
    ) as dynamodb:
        table = await dynamodb.Table(MEDIA_ARTIFACTS_TABLE)
        kwargs: Dict[str, Any] = {
            "IndexName": SCOPE_INDEX,
            "KeyConditionExpression": Key("scope_key").eq(scope_key),
            "ScanIndexForward": forward,
        }
        if limit is not None:
            kwargs["Limit"] = limit
        if cursor:
            kwargs["ExclusiveStartKey"] = {
                "scope_key": scope_key,
                "created_at": cursor,
            }
        items: List[Dict[str, Any]] = []
        next_cursor: Optional[str] = None
        while True:
            resp = await table.query(**kwargs)
            items.extend(resp.get("Items", []))
            last_key = resp.get("LastEvaluatedKey")
            if limit is not None:
                next_cursor = (
                    str(last_key.get("created_at")) if last_key else None
                )
                break
            if not last_key:
                break
            kwargs["ExclusiveStartKey"] = last_key

    return [_projected_record(item) for item in items], next_cursor


def _projected_record(item: Dict[str, Any]) -> MediaArtifactRecord:
    """Rebuild a record from a GSI page, which projects only some attributes.

    The listing needs a typed object, but the index does not carry ``sources``,
    ``parameters`` or ``storage``. Filling the model's required fields from
    ``scope_key`` keeps one type across both reads rather than a second shape the
    API would have to branch on; a listed record therefore has an empty
    ``sources`` and that is expected — the detail route reads the base table.
    """
    payload = dict(item)
    payload.setdefault("parameters", {})
    payload.setdefault("sources", [])
    payload.setdefault("generator_version", "")
    payload.setdefault("updated_at", payload.get("created_at"))
    if "user_id" not in payload or "scope" not in payload or "scope_id" not in payload:
        user_id, _, remainder = str(payload.get("scope_key", "")).partition("#")
        scope, _, scope_id = remainder.partition("#")
        payload.setdefault("user_id", user_id)
        payload.setdefault("scope", scope)
        payload.setdefault("scope_id", scope_id)
    return MediaArtifactRecord.from_dynamodb_item(payload)
