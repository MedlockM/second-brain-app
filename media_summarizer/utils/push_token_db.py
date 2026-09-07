"""
DynamoDB operations for ``user_push_tokens``.

Table: PK=``user_id``, SK=``push_token``. See
``core/models/push_token.py`` for why there is no TTL attribute on it.

No function here ever passes a token value to a log call. ``_log_dynamodb_error``
and ``_log_dynamodb_success`` are given the table and the ``user_id`` only, which
is enough to locate a failing write without publishing the credential that would
let anyone push to that device.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List

from boto3.dynamodb.conditions import Key
from botocore.exceptions import ClientError

from media_summarizer.core.models.push_token import PushToken, PushTokenPlatform
from media_summarizer.utils.database_async import (
    _dynamodb_client_kwargs,
    _log_dynamodb_error,
    _log_dynamodb_success,
    get_session,
)
from media_summarizer.utils.env import required_env

logger = logging.getLogger(__name__)

USER_PUSH_TOKENS_TABLE = required_env("USER_PUSH_TOKENS_TABLE")

#: How long a token survives without being seen again.
#:
#: An app that is uninstalled stops refreshing ``last_seen_at`` and nothing else
#: ever says so — neither Apple, nor Google, nor reliably Expo. 90 days is long
#: enough that a phone left in a drawer over a summer keeps its registration, and
#: short enough that a device the user got rid of stops being addressable within
#: a quarter. The sweep is driven by the daily rule in
#: ``lambda_digest_scheduler.tf``.
STALE_TOKEN_DAYS = 90


async def save_token(
    user_id: str, push_token: str, platform: PushTokenPlatform
) -> None:
    """Register a device, or refresh the registration it already had.

    An ``update_item`` rather than a ``put_item``: the app re-registers on every
    launch to keep ``last_seen_at`` current (which is what the stale sweep reads),
    and a put would reset ``created_at`` each time, erasing when the device first
    appeared.
    """
    now = datetime.now(timezone.utc).isoformat()
    try:
        session = get_session()
        async with session.resource("dynamodb", **_dynamodb_client_kwargs()) as dynamodb:
            table = await dynamodb.Table(USER_PUSH_TOKENS_TABLE)
            await table.update_item(
                Key={"user_id": user_id, "push_token": push_token},
                UpdateExpression=(
                    "SET created_at = if_not_exists(created_at, :now), "
                    "last_seen_at = :now, platform = :platform"
                ),
                ExpressionAttributeValues={":now": now, ":platform": platform.value},
            )
            _log_dynamodb_success(
                "save_push_token",
                table=USER_PUSH_TOKENS_TABLE,
                user_id=user_id,
            )
    except ClientError as e:
        _log_dynamodb_error(
            "save_push_token", e, table=USER_PUSH_TOKENS_TABLE, user_id=user_id
        )
        raise


async def list_tokens_for_user(user_id: str) -> List[PushToken]:
    """Every device registered for this account.

    One query per notification, and the only read the send path makes.
    """
    try:
        session = get_session()
        async with session.resource("dynamodb", **_dynamodb_client_kwargs()) as dynamodb:
            table = await dynamodb.Table(USER_PUSH_TOKENS_TABLE)
            tokens: List[PushToken] = []
            query_kwargs: Dict[str, Any] = {
                "KeyConditionExpression": Key("user_id").eq(user_id)
            }
            while True:
                response = await table.query(**query_kwargs)
                tokens.extend(
                    PushToken.from_dynamodb_item(item)
                    for item in response.get("Items", [])
                )
                last_key = response.get("LastEvaluatedKey")
                if not last_key:
                    break
                query_kwargs["ExclusiveStartKey"] = last_key
            return tokens
    except ClientError as e:
        _log_dynamodb_error(
            "list_push_tokens", e, table=USER_PUSH_TOKENS_TABLE, user_id=user_id
        )
        raise


async def delete_token(user_id: str, push_token: str) -> None:
    """Drop one registration.

    Called from three places: the sign-out of a device, and — the important one —
    the consumer, on an Expo ``DeviceNotRegistered`` verdict. A dead token kept
    around is device data held with no purpose left.
    """
    try:
        session = get_session()
        async with session.resource("dynamodb", **_dynamodb_client_kwargs()) as dynamodb:
            table = await dynamodb.Table(USER_PUSH_TOKENS_TABLE)
            await table.delete_item(
                Key={"user_id": user_id, "push_token": push_token}
            )
            _log_dynamodb_success(
                "delete_push_token",
                table=USER_PUSH_TOKENS_TABLE,
                user_id=user_id,
            )
    except ClientError as e:
        _log_dynamodb_error(
            "delete_push_token", e, table=USER_PUSH_TOKENS_TABLE, user_id=user_id
        )
        raise


async def delete_stale_tokens(older_than_days: int = STALE_TOKEN_DAYS) -> int:
    """Delete every registration not seen for ``older_than_days``. Returns the count.

    A ``Scan``, and that is the right shape here: the table holds one row per
    device of the whole install base, the sweep runs once a day, and there is no
    access pattern that would justify an index built solely for it.
    """
    cutoff = (
        datetime.now(timezone.utc) - timedelta(days=older_than_days)
    ).isoformat()
    removed = 0
    try:
        session = get_session()
        async with session.resource("dynamodb", **_dynamodb_client_kwargs()) as dynamodb:
            table = await dynamodb.Table(USER_PUSH_TOKENS_TABLE)
            scan_kwargs: Dict[str, Any] = {
                "ProjectionExpression": "user_id, push_token, last_seen_at"
            }
            while True:
                response = await table.scan(**scan_kwargs)
                for item in response.get("Items", []):
                    # Lexicographic comparison of two ISO-8601 UTC strings is a
                    # chronological one, and every row is written by
                    # `save_token` above with `datetime.now(timezone.utc)`.
                    if str(item.get("last_seen_at", "")) >= cutoff:
                        continue
                    await table.delete_item(
                        Key={
                            "user_id": item["user_id"],
                            "push_token": item["push_token"],
                        }
                    )
                    removed += 1
                last_key = response.get("LastEvaluatedKey")
                if not last_key:
                    break
                scan_kwargs["ExclusiveStartKey"] = last_key
            return removed
    except ClientError as e:
        _log_dynamodb_error(
            "delete_stale_push_tokens", e, table=USER_PUSH_TOKENS_TABLE
        )
        raise
