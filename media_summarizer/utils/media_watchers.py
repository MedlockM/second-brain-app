"""
Utilities to manage media watchers for pending processing fan-out.

Canonical schema (MEDIA_WATCHERS_TABLE, default "media_watchers"):
- PK: media_key (S)
- SK: user_id (S)
- Attributes: job_id, email, status (pending|completed|failed), minutes_estimated, source
"""
from __future__ import annotations

import logging
import os
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from botocore.exceptions import ClientError

from media_summarizer.utils import database_async

logger = logging.getLogger(__name__)

MEDIA_WATCHERS_TABLE = os.environ.get("MEDIA_WATCHERS_TABLE", "media_watchers")


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _resolve_identity_key(media_key: Optional[str]) -> str:
    key = (media_key or "").strip()
    if not key:
        raise ValueError("media_key is required")
    return key


async def _query_watchers(table_name: str, key_attr: str, key_value: str) -> List[Dict[str, Any]]:
    session = database_async.get_session()
    async with session.resource(
        "dynamodb",
        endpoint_url=database_async.AWS_ENDPOINT_URL,
        region_name=database_async.AWS_REGION,
    ) as dynamodb:
        table = await dynamodb.Table(table_name)
        resp = await table.query(
            KeyConditionExpression=database_async.Key(key_attr).eq(key_value)
        )
        return resp.get("Items", [])


async def add_watcher(
    *,
    media_key: Optional[str] = None,
    user_id: str,
    email: str,
    job_id: str,
    minutes_estimated: int,
    source: str,
) -> bool:
    identity_key = _resolve_identity_key(media_key)
    session = database_async.get_session()
    async with session.resource(
        "dynamodb",
        endpoint_url=database_async.AWS_ENDPOINT_URL,
        region_name=database_async.AWS_REGION,
    ) as dynamodb:
        table = await dynamodb.Table(MEDIA_WATCHERS_TABLE)
        try:
            item: Dict[str, Any] = {
                "media_key": identity_key,
                "user_id": user_id,
                "email": email,
                "job_id": job_id,
                "status": "pending",
                "minutes_estimated": int(minutes_estimated or 0),
                "source": source,
                "created_at": _now_iso(),
            }

            await table.put_item(
                Item=item,
                ConditionExpression="attribute_not_exists(media_key) AND attribute_not_exists(user_id)",
            )
            return True
        except ClientError as e:
            if e.response.get("Error", {}).get("Code") == "ConditionalCheckFailedException":
                return False
            raise


async def list_watchers(
    media_key: Optional[str] = None,
) -> List[Dict[str, Any]]:
    identity_key = _resolve_identity_key(media_key)
    try:
        return await _query_watchers(MEDIA_WATCHERS_TABLE, "media_key", identity_key)
    except ClientError as e:
        logger.warning("Failed to read media watchers for %s: %s", identity_key, e)
        return []


async def _update_status(
    *,
    status: str,
    media_key: Optional[str],
    user_id: str,
    reason: Optional[str] = None,
) -> None:
    identity_key = _resolve_identity_key(media_key)
    session = database_async.get_session()
    async with session.resource(
        "dynamodb",
        endpoint_url=database_async.AWS_ENDPOINT_URL,
        region_name=database_async.AWS_REGION,
    ) as dynamodb:
        table = await dynamodb.Table(MEDIA_WATCHERS_TABLE)
        update = "SET #st = :s, updated_at = :u"
        expr_names = {"#st": "status"}
        expr_vals: Dict[str, Any] = {":s": status, ":u": _now_iso()}
        if reason:
            update += ", failure_reason = :r"
            expr_vals[":r"] = reason

        try:
            await table.update_item(
                Key={"media_key": identity_key, "user_id": user_id},
                UpdateExpression=update,
                ExpressionAttributeNames=expr_names,
                ExpressionAttributeValues=expr_vals,
                ConditionExpression="attribute_exists(media_key) AND attribute_exists(user_id)",
            )
            return
        except ClientError as e:
            if e.response.get("Error", {}).get("Code") == "ConditionalCheckFailedException":
                logger.info(
                    "Watcher row not found for key=%s user=%s",
                    identity_key,
                    user_id,
                )
                return
            raise


async def mark_watcher_completed(
    media_key: Optional[str] = None,
    user_id: str = "",
) -> None:
    await _update_status(
        status="completed",
        media_key=media_key,
        user_id=user_id,
    )


async def mark_watcher_emailed(
    media_key: Optional[str] = None,
    user_id: str = "",
) -> None:
    # Legacy alias kept during migration; completion is no longer email-driven.
    await mark_watcher_completed(
        media_key=media_key,
        user_id=user_id,
    )


async def mark_watcher_processed(
    media_key: Optional[str] = None,
    user_id: str = "",
) -> None:
    # Mark watcher as processed (V1: no email, just state tracking for deduplication).
    # Notification delivery now via mobile app polling, not email.
    await mark_watcher_completed(
        media_key=media_key,
        user_id=user_id,
    )


async def mark_watcher_failed(
    media_key: Optional[str] = None,
    user_id: str = "",
    reason: Optional[str] = None,
) -> None:
    await _update_status(
        status="failed",
        media_key=media_key,
        user_id=user_id,
        reason=reason,
    )
