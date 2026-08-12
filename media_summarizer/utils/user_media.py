"""
DynamoDB access layer for the durable ``user_media`` library table (task-240).

Schema (USER_MEDIA_TABLE, ``user_media-<env>``):
- PK: user_id (S)
- SK: media_item_id (S)
- LSI saved-at-index: saved_at (S)
- LSI folder-index:   folder_sort_key (S) == "<folder_id>#<saved_at>"
- TTL: purge_at (N) -- user-initiated deletion ONLY

This module is the ONLY place allowed to write the table. Two invariants from
§2.2 of the task-218 benchmark are enforced here structurally rather than by
convention, because both were violated in the incident this table exists to fix:

  I1  ``create_if_absent`` holds the module's only ``put_item``. Every other
      mutation is an attribute-level ``update_item``, so a metadata refresh can
      never overwrite the folder or tags a user set from another device.

  I2  ``purge_at`` and ``deleted_at`` are rejected by the generic update helper.
      Writing them requires ``mark_deleted``, which still does not exist: no
      per-item deletion use case ships yet, so *nothing* can set a TTL on a
      library row. That is the point. Account deletion (task-224) is a different
      use case and uses ``delete_all_for_user``, which removes the rows outright
      instead of scheduling them -- an erasure request is not a soft delete.

Table name resolution is lazy on purpose. ``required_env`` raises when the
variable is missing, and this module is imported by the API save path; resolving
at import time would turn a flag-off environment (or a local script that never
touches the library) into an import crash instead of a no-op.
"""

from __future__ import annotations

import logging
import os
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from boto3.dynamodb.conditions import Key
from botocore.exceptions import ClientError

from media_summarizer.core.models.user_media import (
    UserMediaRecord,
    UserMediaStatus,
    build_folder_sort_key,
)
from media_summarizer.utils import database_async
from media_summarizer.utils.env import required_env

logger = logging.getLogger(__name__)

# Attributes only the user-deletion use case may write. The generic update path
# refuses them outright: a caller that could pass purge_at through a metadata
# update is a caller that can expire a user's library.
_FORBIDDEN_UPDATE_ATTRS = frozenset({"purge_at", "deleted_at"})

# Written once by the create path and never rewritten: rewriting saved_at would
# reorder the library, and rewriting the keys is meaningless.
_IMMUTABLE_ATTRS = frozenset({"user_id", "media_item_id", "media_key", "saved_at"})


def user_media_table_name() -> str:
    """Resolve the table name at call time (never at import time)."""
    return required_env("USER_MEDIA_TABLE")


def durable_media_enabled() -> bool:
    """Whether the durable dual-write is active.

    Read at call time, not cached, so flipping the Lambda environment variable
    is an immediate rollback with no redeploy and no cold-start wait.
    """
    raw = (os.environ.get("DURABLE_MEDIA_ENABLED") or "").strip().lower()
    return raw in ("1", "true", "yes", "on")


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


async def create_if_absent(record: UserMediaRecord) -> tuple[UserMediaRecord, bool]:
    """Create the library row if it does not exist yet.

    This is the whole of the idempotence story, and deliberately so: because
    ``media_item_id`` is derived from ``(user_id, media_key)``, a conditional
    ``put_item`` on ``attribute_not_exists(media_item_id)`` is atomic at the item
    level and needs no read-before-write, no transaction and no lock. Two
    concurrent saves of the same content by the same user race on a single
    DynamoDB item and exactly one wins; the loser reads back the winner's row.

    Returns:
        ``(record, created)`` where ``created`` is False when the row already
        existed. On a lost race the returned record is the *stored* one, so the
        caller never propagates metadata that was not persisted.
    """
    table_name = user_media_table_name()
    session = database_async.get_session()
    async with session.resource(
        "dynamodb",
        region_name=database_async.AWS_REGION,
    ) as dynamodb:
        table = await dynamodb.Table(table_name)
        try:
            await table.put_item(
                Item=record.to_dynamodb_item(),
                ConditionExpression="attribute_not_exists(media_item_id)",
            )
            return record, True
        except ClientError as exc:
            code = exc.response.get("Error", {}).get("Code")
            if code != "ConditionalCheckFailedException":
                raise
            # Lost the race, or a genuine re-save of the same content. Both are
            # success: the row the user cares about exists.
            resp = await table.get_item(
                Key={
                    "user_id": record.user_id,
                    "media_item_id": record.media_item_id,
                },
                ConsistentRead=True,
            )
            item = resp.get("Item")
            if not item:
                # The condition failed but the item is gone: only reachable if it
                # was deleted between the put and the read. Surfacing this rather
                # than inventing a row, because a library entry that vanishes is
                # exactly the class of bug being fixed.
                raise
            return UserMediaRecord.from_dynamodb_item(item), False


async def get_user_media(user_id: str, media_item_id: str) -> Optional[UserMediaRecord]:
    """Read one library row. Strongly consistent for read-after-save."""
    table_name = user_media_table_name()
    session = database_async.get_session()
    async with session.resource(
        "dynamodb",
        region_name=database_async.AWS_REGION,
    ) as dynamodb:
        table = await dynamodb.Table(table_name)
        resp = await table.get_item(
            Key={"user_id": user_id, "media_item_id": media_item_id},
            ConsistentRead=True,
        )
        item = resp.get("Item")
        return UserMediaRecord.from_dynamodb_item(item) if item else None


async def list_all_for_user(user_id: str) -> List[UserMediaRecord]:
    """Every library row of one user, fully paginated.

    Queries the base table rather than an LSI: the caller is the account purge,
    which needs *all* rows including any whose ``saved_at`` or ``folder_sort_key``
    a future writer might leave unset. A projection would be cheaper but the rows
    are needed whole to reach the artifacts keyed by ``media_item_id``.
    """
    table_name = user_media_table_name()
    session = database_async.get_session()
    records: List[UserMediaRecord] = []
    async with session.resource(
        "dynamodb",
        region_name=database_async.AWS_REGION,
    ) as dynamodb:
        table = await dynamodb.Table(table_name)
        kwargs: Dict[str, Any] = {
            "KeyConditionExpression": Key("user_id").eq(user_id),
        }
        while True:
            resp = await table.query(**kwargs)
            for item in resp.get("Items", []):
                records.append(UserMediaRecord.from_dynamodb_item(item))
            last_key = resp.get("LastEvaluatedKey")
            if not last_key:
                break
            kwargs["ExclusiveStartKey"] = last_key
    return records


async def delete_all_for_user(user_id: str) -> int:
    """Hard-delete every library row of one user. Account deletion only.

    This is the "user-initiated deletion use case" invariant I2 was holding the
    door open for, and it deliberately does *not* go through ``purge_at``: an
    erasure request under GDPR art. 17 removes the row now, it does not schedule
    it for later. The TTL therefore stays unused, and ``mark_deleted`` (per-item
    soft deletion) still does not exist.

    Idempotent: deleting an already-deleted partition is a no-op that returns 0.
    """
    table_name = user_media_table_name()
    session = database_async.get_session()
    deleted = 0
    async with session.resource(
        "dynamodb",
        region_name=database_async.AWS_REGION,
    ) as dynamodb:
        table = await dynamodb.Table(table_name)
        kwargs: Dict[str, Any] = {
            "KeyConditionExpression": Key("user_id").eq(user_id),
            "ProjectionExpression": "user_id, media_item_id",
        }
        while True:
            resp = await table.query(**kwargs)
            for item in resp.get("Items", []):
                await table.delete_item(
                    Key={
                        "user_id": item["user_id"],
                        "media_item_id": item["media_item_id"],
                    }
                )
                deleted += 1
            last_key = resp.get("LastEvaluatedKey")
            if not last_key:
                break
            kwargs["ExclusiveStartKey"] = last_key
    logger.info("user_media: deleted %d library rows for user %s", deleted, user_id)
    return deleted


async def update_attributes(
    *,
    user_id: str,
    media_item_id: str,
    attributes: Dict[str, Any],
) -> bool:
    """Patch individual attributes of an existing row.

    Attribute-level ``SET`` rather than a full item rewrite: the pipeline updating
    a title must not clobber a folder move the user made a second earlier.

    Refuses ``purge_at`` / ``deleted_at`` (invariant I2) and the immutable
    identity attributes. Returns False when the row does not exist -- a missing
    row is never created here, because only the save path may bring a library
    entry into existence.
    """
    forbidden = _FORBIDDEN_UPDATE_ATTRS.intersection(attributes)
    if forbidden:
        raise ValueError(
            f"{sorted(forbidden)} may only be written by the user-initiated "
            "deletion use case, never by a metadata update (task-218 invariant I2)"
        )
    immutable = _IMMUTABLE_ATTRS.intersection(attributes)
    if immutable:
        raise ValueError(f"{sorted(immutable)} are write-once and set at creation")

    payload = {k: v for k, v in attributes.items() if v is not None}
    if not payload:
        return True

    set_parts: List[str] = ["updated_at = :updated_at"]
    expr_names: Dict[str, str] = {}
    expr_values: Dict[str, Any] = {":updated_at": _now_iso()}

    for index, (key, value) in enumerate(payload.items()):
        name_ref = f"#a{index}"
        value_ref = f":v{index}"
        expr_names[name_ref] = key
        if isinstance(value, UserMediaStatus):
            value = value.value
        elif isinstance(value, datetime):
            value = value.isoformat()
        expr_values[value_ref] = value
        set_parts.append(f"{name_ref} = {value_ref}")

    table_name = user_media_table_name()
    session = database_async.get_session()
    async with session.resource(
        "dynamodb",
        region_name=database_async.AWS_REGION,
    ) as dynamodb:
        table = await dynamodb.Table(table_name)
        try:
            await table.update_item(
                Key={"user_id": user_id, "media_item_id": media_item_id},
                UpdateExpression="SET " + ", ".join(set_parts),
                ExpressionAttributeNames=expr_names or None,
                ExpressionAttributeValues=expr_values,
                ConditionExpression="attribute_exists(media_item_id)",
            )
            return True
        except ClientError as exc:
            if exc.response.get("Error", {}).get("Code") == "ConditionalCheckFailedException":
                return False
            raise


async def update_organization(
    *,
    user_id: str,
    media_item_id: str,
    folder_id: Optional[str] = None,
    tag_ids: Optional[List[str]] = None,
    saved_at: Optional[datetime] = None,
) -> bool:
    """Update the user-authored organization of a row.

    Separate from ``update_attributes`` because moving an item between folders
    also has to rewrite ``folder_sort_key`` (the folder LSI range key), and
    forgetting that leaves the item queryable under its old folder. ``saved_at``
    is read, never written: it is the second half of the composite key.
    """
    attributes: Dict[str, Any] = {}
    if tag_ids is not None:
        attributes["tag_ids"] = list(tag_ids)
    if folder_id is not None:
        attributes["folder_id"] = folder_id
        if saved_at is None:
            current = await get_user_media(user_id, media_item_id)
            if current is None:
                return False
            saved_at = current.saved_at
        attributes["folder_sort_key"] = build_folder_sort_key(folder_id, saved_at)

    if not attributes:
        return True
    return await update_attributes(
        user_id=user_id,
        media_item_id=media_item_id,
        attributes=attributes,
    )
