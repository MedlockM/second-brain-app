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
      Exactly two functions in the codebase touch them, both here (task-243, §6.2),
      which is what ``scripts/check_purge_at_writers.py`` enforces in CI:
      :func:`mark_deleted` sets them, reachable only from the user-initiated
      deletion use case (``core/services/media_deletion_service.py``), and the
      private ``_clear_deletion`` removes them when :func:`create_if_absent` finds
      the user re-saving content they had deleted. Account deletion (task-224) is a
      different use case and uses ``delete_all_for_user``, which removes the rows
      outright instead of scheduling them -- an erasure request is not a soft
      delete.

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
    NO_FOLDER_SEGMENT,
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

    Saving content the user had deleted **revives** the row instead of returning a
    soft-deleted one: the id is deterministic in ``(user_id, media_key)``, so the
    "new" save collides with the row still waiting for its ``purge_at``. Returning
    it untouched would give the user an item that is invisible everywhere and gets
    destroyed 30 days later — a save silently swallowed by an old deletion, which
    is the incident class this table exists to prevent.

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
            stored = UserMediaRecord.from_dynamodb_item(item)
            if not stored.is_deleted:
                return stored, False
            revived = await _clear_deletion(
                table, record.user_id, record.media_item_id
            )
            if revived is None:
                # Someone else revived it first, or the TTL swept it between the
                # read and the update. Either way the caller wants the current row.
                return stored, False
            return revived, False


async def _clear_deletion(
    table: Any,
    user_id: str,
    media_item_id: str,
) -> Optional[UserMediaRecord]:
    """Cancel a pending purge because the user saved the same content again.

    The second half of invariant I2: this module owns ``deleted_at``/``purge_at``,
    so cancelling a deletion lives here too and stays reachable only from
    :func:`create_if_absent`. Deliberately *not* exposed as a helper — an
    "un-delete this row" function callable from anywhere is how a TTL attribute
    acquires a second writer.

    Returns ``None`` when the row is no longer soft-deleted (a concurrent revive,
    or the TTL got there first).
    """
    try:
        resp = await table.update_item(
            Key={"user_id": user_id, "media_item_id": media_item_id},
            UpdateExpression="SET updated_at = :updated_at REMOVE deleted_at, purge_at",
            ExpressionAttributeValues={":updated_at": _now_iso()},
            ConditionExpression="attribute_exists(deleted_at)",
            ReturnValues="ALL_NEW",
        )
    except ClientError as exc:
        if exc.response.get("Error", {}).get("Code") == "ConditionalCheckFailedException":
            return None
        raise

    logger.info(
        "user_media: revived soft-deleted %s for user %s (re-saved before purge)",
        media_item_id,
        user_id,
    )
    return UserMediaRecord.from_dynamodb_item(resp["Attributes"])


async def get_user_media(
    user_id: str,
    media_item_id: str,
    *,
    include_deleted: bool = False,
) -> Optional[UserMediaRecord]:
    """Read one library row. Strongly consistent for read-after-save.

    A soft-deleted row reads as absent by default: §6.2 requires an item the user
    deleted to leave every read path *immediately*, while the row itself lingers
    until its ``purge_at`` sweeps it 30 days later. Only the deletion use case
    (which must see its own soft delete to be idempotent) and the purge cascade
    pass ``include_deleted=True``.
    """
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
        if not item:
            return None
        record = UserMediaRecord.from_dynamodb_item(item)
        if record.is_deleted and not include_deleted:
            return None
        return record


async def list_all_for_user(user_id: str) -> List[UserMediaRecord]:
    """Every library row of one user, fully paginated.

    Queries the base table rather than an LSI: the caller is the account purge,
    which needs *all* rows including any whose ``saved_at`` or ``folder_sort_key``
    a future writer might leave unset. A projection would be cheaper but the rows
    are needed whole to reach the artifacts keyed by ``media_item_id``.

    Soft-deleted rows are **included**, deliberately: an erasure request must take
    the rows a user deleted last week with it instead of waiting 30 days for their
    ``purge_at``. Library read paths must not use this function.
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


async def list_library_for_user(user_id: str) -> List[UserMediaRecord]:
    """Every *visible* library row of one user, fully paginated.

    THE read path behind ``GET /api/media``, Search, the folder views and the
    folder counts (task-220). It queries the base table and never touches
    ``processing_jobs``: invariant I3 says a library read must not require an
    operational row, so the list keeps working after a job expires.

    Strongly consistent, so a save is immediately visible in the list the app
    fetches right after it.
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
            "ConsistentRead": True,
        }
        while True:
            resp = await table.query(**kwargs)
            for item in resp.get("Items", []):
                record = UserMediaRecord.from_dynamodb_item(item)
                if record.is_deleted:
                    continue
                records.append(record)
            last_key = resp.get("LastEvaluatedKey")
            if not last_key:
                break
            kwargs["ExclusiveStartKey"] = last_key
    return records


async def list_for_folder(user_id: str, folder_id: Optional[str]) -> List[UserMediaRecord]:
    """One folder's direct contents, via the folder LSI.

    Direct contents only: sub-folder inclusion is a folder-tree concern and is
    resolved by the caller, which then unions several calls or filters the full
    library. ``folder_id=None`` returns the rows that sit outside any folder.
    """
    table_name = user_media_table_name()
    prefix = f"{folder_id or NO_FOLDER_SEGMENT}#"
    session = database_async.get_session()
    records: List[UserMediaRecord] = []
    async with session.resource(
        "dynamodb",
        region_name=database_async.AWS_REGION,
    ) as dynamodb:
        table = await dynamodb.Table(table_name)
        kwargs: Dict[str, Any] = {
            "IndexName": "folder-index",
            "KeyConditionExpression": (
                Key("user_id").eq(user_id) & Key("folder_sort_key").begins_with(prefix)
            ),
            "ConsistentRead": True,
        }
        while True:
            resp = await table.query(**kwargs)
            for item in resp.get("Items", []):
                record = UserMediaRecord.from_dynamodb_item(item)
                if record.is_deleted:
                    continue
                records.append(record)
            last_key = resp.get("LastEvaluatedKey")
            if not last_key:
                break
            kwargs["ExclusiveStartKey"] = last_key
    return records


async def count_media_per_folder(user_id: str) -> Dict[str, int]:
    """Number of visible library rows per folder id.

    One Query for the whole user rather than one per folder: a user has a handful
    of folders and a bounded library, so scanning the partition once is cheaper
    than N LSI queries. Rows with no folder are counted under
    ``NO_FOLDER_SEGMENT``.
    """
    counts: Dict[str, int] = {}
    for record in await list_library_for_user(user_id):
        key = record.folder_id or NO_FOLDER_SEGMENT
        counts[key] = counts.get(key, 0) + 1
    return counts


async def delete_all_for_user(user_id: str) -> int:
    """Hard-delete every library row of one user. Account deletion only.

    Deliberately does *not* go through ``purge_at``, unlike :func:`mark_deleted`:
    an erasure request under GDPR art. 17 removes the row now, it does not
    schedule it for later. Soft-deleted rows still awaiting their TTL are taken
    too, since the query covers the whole partition.

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


async def mark_deleted(
    *,
    user_id: str,
    media_item_id: str,
    grace_days: int,
) -> Optional[UserMediaRecord]:
    """Soft-delete one library row and schedule its purge. THE only ``purge_at`` writer.

    Invariant I2 in one function: ``deleted_at`` and ``purge_at`` are written here
    and nowhere else in the codebase, and every other write helper in this module
    refuses them. ``scripts/check_purge_at_writers.py`` fails CI if a second writer
    appears, because the whole point of ``user_media`` is that no clock except the
    user's own can expire a library row.

    The condition is ``attribute_exists(media_item_id) AND
    attribute_not_exists(deleted_at)``: deleting twice must not push the purge date
    30 more days into the future, which would let a client that retries keep an
    item alive indefinitely.

    Returns:
        The soft-deleted record, or ``None`` when the row does not exist or was
        already soft-deleted. The caller distinguishes the two by reading the row.
    """
    if grace_days < 0:
        raise ValueError("grace_days must be >= 0")

    now = datetime.now(timezone.utc)
    # Epoch seconds: DynamoDB TTL only ever reads a Number attribute, and the
    # sweep happens within 48h of that instant (best effort, not a guarantee).
    purge_at = int(now.timestamp()) + grace_days * 86400

    table_name = user_media_table_name()
    session = database_async.get_session()
    async with session.resource(
        "dynamodb",
        region_name=database_async.AWS_REGION,
    ) as dynamodb:
        table = await dynamodb.Table(table_name)
        try:
            resp = await table.update_item(
                Key={"user_id": user_id, "media_item_id": media_item_id},
                UpdateExpression=(
                    "SET deleted_at = :deleted_at, purge_at = :purge_at, "
                    "updated_at = :updated_at"
                ),
                ExpressionAttributeValues={
                    ":deleted_at": now.isoformat(),
                    ":purge_at": purge_at,
                    ":updated_at": now.isoformat(),
                },
                ConditionExpression=(
                    "attribute_exists(media_item_id) AND attribute_not_exists(deleted_at)"
                ),
                ReturnValues="ALL_NEW",
            )
        except ClientError as exc:
            if exc.response.get("Error", {}).get("Code") == "ConditionalCheckFailedException":
                return None
            raise

    logger.info(
        "user_media: soft-deleted %s for user %s, purge_at=%d",
        media_item_id,
        user_id,
        purge_at,
    )
    return UserMediaRecord.from_dynamodb_item(resp["Attributes"])


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
