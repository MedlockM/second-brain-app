"""
DynamoDB operations for the digest feature.

Tables:
- user_digests: PK=user_id, SK=digest_key (format: "{type}#{period_key}")
- user_digest_settings: PK=user_id
"""

from __future__ import annotations

import logging
import os
from datetime import datetime, timezone
from typing import List, Optional

from boto3.dynamodb.conditions import Key
from botocore.exceptions import ClientError

from media_summarizer.core.models.digest import (
    DigestRecord,
    DigestStatus,
    DigestType,
    UserDigestSettings,
)
from media_summarizer.utils.database_async import (
    get_session,
    _dynamodb_client_kwargs,
    _log_dynamodb_success,
    _log_dynamodb_error,
)

logger = logging.getLogger(__name__)

USER_DIGESTS_TABLE = os.environ.get("USER_DIGESTS_TABLE", "user_digests")
USER_DIGEST_SETTINGS_TABLE = os.environ.get(
    "USER_DIGEST_SETTINGS_TABLE", "user_digest_settings"
)


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


async def list_all_users_with_digest_enabled() -> List[str]:
    """
    List all user IDs that have digests enabled (or have no settings row, which means enabled by default).
    For production scale, this would need pagination. Fine for V1.
    """
    try:
        session = get_session()
        async with session.resource("dynamodb", **_dynamodb_client_kwargs()) as dynamodb:
            table = await dynamodb.Table(USER_DIGEST_SETTINGS_TABLE)
            # Scan for users who explicitly disabled (we need to exclude them)
            disabled_users = set()
            scan_kwargs = {}
            while True:
                resp = await table.scan(**scan_kwargs)
                for item in resp.get("Items", []):
                    if not item.get("digest_enabled", True):
                        disabled_users.add(item["user_id"])
                last_key = resp.get("LastEvaluatedKey")
                if not last_key:
                    break
                scan_kwargs["ExclusiveStartKey"] = last_key
            return list(disabled_users)
    except ClientError as e:
        _log_dynamodb_error(
            "list_all_users_with_digest_enabled",
            e,
            table=USER_DIGEST_SETTINGS_TABLE,
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
