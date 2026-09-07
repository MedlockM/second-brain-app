"""
DynamoDB operations for the digest feature.

Tables:
- user_digests: PK=user_id, SK=digest_key (format: "{type}#{period_key}")
- user_digest_settings: PK=user_id
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import List, Optional

from boto3.dynamodb.conditions import Key
from botocore.exceptions import ClientError

from media_summarizer.core.models.digest import (
    DigestRecord,
    DigestType,
    UserDigestSettings,
)
from media_summarizer.utils.database_async import (
    _dynamodb_client_kwargs,
    _log_dynamodb_error,
    _log_dynamodb_success,
    get_session,
)
from media_summarizer.utils.env import required_env

logger = logging.getLogger(__name__)

USER_DIGESTS_TABLE = required_env("USER_DIGESTS_TABLE")
USER_DIGEST_SETTINGS_TABLE = required_env("USER_DIGEST_SETTINGS_TABLE")


# ---------- Digest CRUD ----------


async def get_digest(
    user_id: str, digest_type: DigestType, period_key: str
) -> Optional[DigestRecord]:
    """Get a specific digest by user_id + type + period."""
    digest_key = f"{digest_type.value}#{period_key}"
    try:
        session = get_session()
        async with session.resource("dynamodb", **_dynamodb_client_kwargs()) as dynamodb:
            table = await dynamodb.Table(USER_DIGESTS_TABLE)
            response = await table.get_item(
                Key={"user_id": user_id, "digest_key": digest_key}
            )
            if "Item" in response:
                return DigestRecord.from_dynamodb_item(response["Item"])
            return None
    except ClientError as e:
        _log_dynamodb_error(
            "get_digest", e, table=USER_DIGESTS_TABLE, user_id=user_id
        )
        raise


async def save_digest(record: DigestRecord) -> DigestRecord:
    """Create or update a digest record."""
    record.updated_at = datetime.now(timezone.utc).isoformat()
    try:
        session = get_session()
        async with session.resource("dynamodb", **_dynamodb_client_kwargs()) as dynamodb:
            table = await dynamodb.Table(USER_DIGESTS_TABLE)
            await table.put_item(Item=record.to_dynamodb_item())
            _log_dynamodb_success(
                "save_digest",
                table=USER_DIGESTS_TABLE,
                user_id=record.user_id,
                digest_key=record.digest_key,
            )
            return record
    except ClientError as e:
        _log_dynamodb_error(
            "save_digest", e, table=USER_DIGESTS_TABLE, user_id=record.user_id
        )
        raise


async def list_digests_for_user(
    user_id: str,
    digest_type: Optional[DigestType] = None,
    limit: int = 10,
) -> List[DigestRecord]:
    """List recent digests for a user, optionally filtered by type."""
    try:
        session = get_session()
        async with session.resource("dynamodb", **_dynamodb_client_kwargs()) as dynamodb:
            table = await dynamodb.Table(USER_DIGESTS_TABLE)
            query_kwargs = {
                "KeyConditionExpression": Key("user_id").eq(user_id),
                "ScanIndexForward": False,  # newest first
                "Limit": limit,
            }
            if digest_type is not None:
                # Filter SK to start with the digest type prefix
                query_kwargs["KeyConditionExpression"] = (
                    Key("user_id").eq(user_id)
                    & Key("digest_key").begins_with(f"{digest_type.value}#")
                )
            response = await table.query(**query_kwargs)
            items = response.get("Items", [])
            return [DigestRecord.from_dynamodb_item(item) for item in items]
    except ClientError as e:
        _log_dynamodb_error(
            "list_digests_for_user", e, table=USER_DIGESTS_TABLE, user_id=user_id
        )
        raise


async def mark_digest_published(
    user_id: str, digest_type: DigestType, period_key: str
) -> bool:
    """Claim the right to notify this period. ``True`` if this call won it.

    This is the whole of the send's idempotency, and it is a *conditional* write
    rather than a read followed by a write for a reason: the schedule fires 72
    times a day, and a retried Lambda invocation can put two ticks in flight over
    the same account at once. Read-then-write would let both see
    ``published_at is None`` and both enqueue a notification;
    ``attribute_not_exists(published_at)`` lets exactly one through and answers
    ``False`` to the other.

    ``attribute_exists(user_id)`` is the second half of the condition and guards a
    different invariant: an ``update_item`` on an absent key would *create* the
    row, and an empty period must never materialise one (see the module docstring
    of ``core/services/digest_service.py``).

    The caller enqueues only after this returns ``True``, so the marker is claimed
    before the message leaves. A crash in between costs that one notification —
    the digest itself is already stored and the app shows it on next launch —
    which is the right way round: a lost notification is a non-event, a duplicate
    one is a defect the user sees.
    """
    digest_key = f"{digest_type.value}#{period_key}"
    now = datetime.now(timezone.utc).isoformat()
    try:
        session = get_session()
        async with session.resource("dynamodb", **_dynamodb_client_kwargs()) as dynamodb:
            table = await dynamodb.Table(USER_DIGESTS_TABLE)
            await table.update_item(
                Key={"user_id": user_id, "digest_key": digest_key},
                UpdateExpression="SET published_at = :now, updated_at = :now",
                ConditionExpression=(
                    "attribute_exists(user_id) AND attribute_not_exists(published_at)"
                ),
                ExpressionAttributeValues={":now": now},
            )
            _log_dynamodb_success(
                "mark_digest_published",
                table=USER_DIGESTS_TABLE,
                user_id=user_id,
                digest_key=digest_key,
            )
            return True
    except ClientError as e:
        if e.response.get("Error", {}).get("Code") == "ConditionalCheckFailedException":
            # Already announced, or no row for this period. Both mean "not mine
            # to send", and neither is an error.
            return False
        _log_dynamodb_error(
            "mark_digest_published", e, table=USER_DIGESTS_TABLE, user_id=user_id
        )
        raise


# ---------- Digest Settings CRUD ----------


async def get_user_digest_settings(user_id: str) -> Optional[UserDigestSettings]:
    """Get digest settings for a user. Returns None if no settings exist (defaults apply)."""
    try:
        session = get_session()
        async with session.resource("dynamodb", **_dynamodb_client_kwargs()) as dynamodb:
            table = await dynamodb.Table(USER_DIGEST_SETTINGS_TABLE)
            response = await table.get_item(Key={"user_id": user_id})
            if "Item" in response:
                return UserDigestSettings.from_dynamodb_item(response["Item"])
            return None
    except ClientError as e:
        _log_dynamodb_error(
            "get_user_digest_settings",
            e,
            table=USER_DIGEST_SETTINGS_TABLE,
            user_id=user_id,
        )
        raise


async def save_user_digest_settings(
    settings: UserDigestSettings,
) -> UserDigestSettings:
    """Create or update user digest settings."""
    settings.updated_at = datetime.now(timezone.utc).isoformat()
    try:
        session = get_session()
        async with session.resource("dynamodb", **_dynamodb_client_kwargs()) as dynamodb:
            table = await dynamodb.Table(USER_DIGEST_SETTINGS_TABLE)
            await table.put_item(Item=settings.to_dynamodb_item())
            _log_dynamodb_success(
                "save_user_digest_settings",
                table=USER_DIGEST_SETTINGS_TABLE,
                user_id=settings.user_id,
            )
            return settings
    except ClientError as e:
        _log_dynamodb_error(
            "save_user_digest_settings",
            e,
            table=USER_DIGEST_SETTINGS_TABLE,
            user_id=settings.user_id,
        )
        raise
