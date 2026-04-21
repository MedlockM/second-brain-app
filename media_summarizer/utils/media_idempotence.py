"""
Media idempotence utilities using DynamoDB.

Canonical schema (MEDIA_IDEMPOTENCE_TABLE, default "media_idempotence"):
- PK: media_key (S)
- Attributes: status (reserved|processed|failed), job_id, created_at, updated_at
"""
from __future__ import annotations

import logging
import os
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from botocore.exceptions import ClientError

from media_summarizer.utils import database_async

logger = logging.getLogger(__name__)

MEDIA_IDEMPOTENCE_TABLE = os.environ.get("MEDIA_IDEMPOTENCE_TABLE", "media_idempotence")


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _resolve_identity_key(media_key: Optional[str]) -> str:
    key = (media_key or "").strip()
    if not key:
        raise ValueError("media_key is required")
    return key


async def _get_item(*, table_name: str, key_attr: str, key_value: str) -> Optional[Dict[str, Any]]:
    session = database_async.get_session()
    async with session.resource(
        "dynamodb",
        endpoint_url=database_async.AWS_ENDPOINT_URL,
        region_name=database_async.AWS_REGION,
    ) as dynamodb:
        table = await dynamodb.Table(table_name)
        resp = await table.get_item(
            Key={key_attr: key_value},
            ConsistentRead=True,
        )
        return resp.get("Item")


async def reserve_or_skip(
    media_key: Optional[str] = None,
    job_id: Optional[str] = None,
) -> bool:
    """
    Reserve media identity key globally.

    Returns True if reserved, False if duplicate.
    """
    identity_key = _resolve_identity_key(media_key)

    item: Dict[str, Any] = {
        "media_key": identity_key,
        "status": "reserved",
        "job_id": job_id or "",
        "created_at": _now_iso(),
        "updated_at": _now_iso(),
    }

    try:
        session = database_async.get_session()
        async with session.resource(
            "dynamodb",
            endpoint_url=database_async.AWS_ENDPOINT_URL,
            region_name=database_async.AWS_REGION,
        ) as dynamodb:
            table = await dynamodb.Table(MEDIA_IDEMPOTENCE_TABLE)
            await table.put_item(
                Item=item,
                ConditionExpression="attribute_not_exists(media_key)",
            )
        logger.info("Reserved media key %s (job_id=%s)", identity_key, job_id)
        return True
    except ClientError as e:
        if e.response.get("Error", {}).get("Code") == "ConditionalCheckFailedException":
            logger.info("Duplicate submission detected for media_key=%s", identity_key)
            return False
        logger.error("Error reserving media idempotence row: %s", e)
        raise


async def already_processed(
    media_key: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    """Return existing idempotence row from canonical media table."""
    identity_key = _resolve_identity_key(media_key)
    try:
        item = await _get_item(
            table_name=MEDIA_IDEMPOTENCE_TABLE,
            key_attr="media_key",
            key_value=identity_key,
        )
        return item
    except ClientError as e:
        logger.error("Error checking media idempotence row: %s", e)
        raise


async def mark_processed(
    media_key: Optional[str] = None,
    job_id: Optional[str] = None,
) -> None:
    identity_key = _resolve_identity_key(media_key)
    try:
        session = database_async.get_session()
        async with session.resource(
            "dynamodb",
            endpoint_url=database_async.AWS_ENDPOINT_URL,
            region_name=database_async.AWS_REGION,
        ) as dynamodb:
            table = await dynamodb.Table(MEDIA_IDEMPOTENCE_TABLE)
            expr_values: Dict[str, Any] = {
                ":s": "processed",
                ":u": _now_iso(),
                ":j": job_id or "",
            }
            await table.update_item(
                Key={"media_key": identity_key},
                UpdateExpression=(
                    "SET #st = :s, updated_at = :u, "
                    "job_id = if_not_exists(job_id, :j)"
                ),
                ExpressionAttributeNames={"#st": "status"},
                ExpressionAttributeValues=expr_values,
                ConditionExpression="attribute_exists(media_key)",
            )
        logger.info("Marked processed for media_key=%s (job=%s)", identity_key, job_id)
    except ClientError as e:
        logger.error("Error marking media idempotence processed: %s", e)
        raise


async def mark_failed(
    media_key: Optional[str] = None,
    job_id: Optional[str] = None,
) -> None:
    identity_key = _resolve_identity_key(media_key)
    try:
        session = database_async.get_session()
        async with session.resource(
            "dynamodb",
            endpoint_url=database_async.AWS_ENDPOINT_URL,
            region_name=database_async.AWS_REGION,
        ) as dynamodb:
            table = await dynamodb.Table(MEDIA_IDEMPOTENCE_TABLE)
            await table.update_item(
                Key={"media_key": identity_key},
                UpdateExpression=(
                    "SET #st = :s, updated_at = :u, "
                    "job_id = if_not_exists(job_id, :j)"
                ),
                ExpressionAttributeNames={"#st": "status"},
                ExpressionAttributeValues={
                    ":s": "failed",
                    ":u": _now_iso(),
                    ":j": job_id or "",
                },
                ConditionExpression="attribute_exists(media_key)",
            )
        logger.info("Marked failed for media_key=%s (job=%s)", identity_key, job_id)
    except ClientError as e:
        logger.error("Error marking media idempotence failed: %s", e)
        raise


async def release_reservation(
    media_key: Optional[str] = None,
    job_id: Optional[str] = None,
) -> None:
    """
    Release a reservation if the canonical processing fails before orchestration.
    """
    identity_key = _resolve_identity_key(media_key)
    try:
        session = database_async.get_session()
        async with session.resource(
            "dynamodb",
            endpoint_url=database_async.AWS_ENDPOINT_URL,
            region_name=database_async.AWS_REGION,
        ) as dynamodb:
            table = await dynamodb.Table(MEDIA_IDEMPOTENCE_TABLE)
            condition = "#st = :reserved"
            expr_names = {"#st": "status"}
            expr_values = {":reserved": "reserved"}
            if job_id:
                condition += " AND job_id = :j"
                expr_values[":j"] = job_id

            await table.delete_item(
                Key={"media_key": identity_key},
                ConditionExpression=condition,
                ExpressionAttributeNames=expr_names,
                ExpressionAttributeValues=expr_values,
            )
        logger.info("Released reservation for media_key=%s (job=%s)", identity_key, job_id)
    except ClientError as e:
        if e.response.get("Error", {}).get("Code") == "ConditionalCheckFailedException":
            logger.info(
                "No reservation to release or state changed for media_key=%s",
                identity_key,
            )
            return
        logger.error("Error releasing media idempotence reservation: %s", e)
        raise
