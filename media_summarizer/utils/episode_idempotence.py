"""
Episode idempotence utilities using DynamoDB.

Provides a global per-episode GUID reservation to ensure idempotent submissions
across sources (UI, Spotify sync, etc.), while still allowing per-user billing.

Table schema (EPISODE_IDEMPOTENCE_TABLE, default "episode_idempotence"):
- PK: episode_guid (S)
- Attributes: status (reserved|processed|failed), job_id (canonical first-processor), created_at, updated_at
"""
from __future__ import annotations

import os
import logging
from datetime import datetime, timezone
from typing import Optional, Dict, Any
from botocore.exceptions import ClientError

from media_summarizer.utils import database_async

logger = logging.getLogger(__name__)

EPISODE_IDEMPOTENCE_TABLE = os.environ.get("EPISODE_IDEMPOTENCE_TABLE", "episode_idempotence")


# NOTE: Do not return Table outside of the aioboto3 resource context.
# Always open a new resource context per operation to avoid closed-session errors.


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


async def reserve_or_skip(episode_guid: str, job_id: Optional[str] = None) -> bool:
    """Try to reserve an episode GUID globally. Returns True if reserved, False if duplicate.

    This uses a conditional put on (episode_guid) to prevent duplicates across all users.
    """
    item = {
        "episode_guid": episode_guid,
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
            table = await dynamodb.Table(EPISODE_IDEMPOTENCE_TABLE)
            await table.put_item(
                Item=item,
                ConditionExpression="attribute_not_exists(episode_guid)",
            )
        logger.info(f"Reserved episode GUID {episode_guid} (job_id={job_id})")
        return True
    except ClientError as e:
        if e.response.get("Error", {}).get("Code") == "ConditionalCheckFailedException":
            logger.info(f"Duplicate submission detected for guid {episode_guid}")
            return False
        logger.error(f"Error reserving idempotence row: {e}")
        raise


async def already_processed(episode_guid: str) -> Optional[Dict[str, Any]]:
    """Return existing idempotence row if present, else None."""
    try:
        session = database_async.get_session()
        async with session.resource(
            "dynamodb",
            endpoint_url=database_async.AWS_ENDPOINT_URL,
            region_name=database_async.AWS_REGION,
        ) as dynamodb:
            table = await dynamodb.Table(EPISODE_IDEMPOTENCE_TABLE)
            resp = await table.get_item(
                Key={"episode_guid": episode_guid},
                ConsistentRead=True,
            )
            return resp.get("Item")
    except ClientError as e:
        logger.error(f"Error checking idempotence row: {e}")
        raise


async def mark_processed(episode_guid: str, job_id: str) -> None:
    """Mark GUID as processed. Only sets job_id if not already set to preserve canonical first-processor."""
    try:
        session = database_async.get_session()
        async with session.resource(
            "dynamodb",
            endpoint_url=database_async.AWS_ENDPOINT_URL,
            region_name=database_async.AWS_REGION,
        ) as dynamodb:
            table = await dynamodb.Table(EPISODE_IDEMPOTENCE_TABLE)
            # Try to set job_id only if not set
            try:
                await table.update_item(
                    Key={"episode_guid": episode_guid},
                    UpdateExpression="SET #st = :s, job_id = if_not_exists(job_id, :j), updated_at = :u",
                    ExpressionAttributeNames={"#st": "status"},
                    ExpressionAttributeValues={
                        ":s": "processed",
                        ":j": job_id,
                        ":u": _now_iso(),
                    },
                    ConditionExpression="attribute_exists(episode_guid)",
                )
            except ClientError as e:
                # Fallback for environments not supporting if_not_exists in UpdateExpression
                if e.response.get("Error", {}).get("Code") == "ValidationException":
                    await table.update_item(
                        Key={"episode_guid": episode_guid},
                        UpdateExpression="SET #st = :s, updated_at = :u",
                        ExpressionAttributeNames={"#st": "status"},
                        ExpressionAttributeValues={
                            ":s": "processed",
                            ":u": _now_iso(),
                        },
                        ConditionExpression="attribute_exists(episode_guid)",
                    )
                else:
                    raise
        logger.info(f"Marked processed for guid {episode_guid} (job {job_id})")
    except ClientError as e:
        logger.error(f"Error marking processed: {e}")
        raise


async def mark_failed(episode_guid: str, job_id: Optional[str] = None) -> None:
    try:
        session = database_async.get_session()
        async with session.resource(
            "dynamodb",
            endpoint_url=database_async.AWS_ENDPOINT_URL,
            region_name=database_async.AWS_REGION,
        ) as dynamodb:
            table = await dynamodb.Table(EPISODE_IDEMPOTENCE_TABLE)
            await table.update_item(
                Key={"episode_guid": episode_guid},
                UpdateExpression="SET #st = :s, updated_at = :u" + (", job_id = if_not_exists(job_id, :j)" if job_id else ""),
                ExpressionAttributeNames={"#st": "status"},
                ExpressionAttributeValues={
                    ":s": "failed",
                    ":u": _now_iso(),
                    **({":j": job_id} if job_id else {}),
                },
                ConditionExpression="attribute_exists(episode_guid)",
            )
        logger.info(f"Marked failed for guid {episode_guid} (job {job_id})")
    except ClientError as e:
        logger.error(f"Error marking failed: {e}")
        raise


async def release_reservation(episode_guid: str, job_id: Optional[str] = None) -> None:
    """Release a reservation if we fail before the job is persisted or enqueued.

    We guard the delete with a condition on status='reserved' and optional job_id match.
    """
    try:
        session = database_async.get_session()
        async with session.resource(
            "dynamodb",
            endpoint_url=database_async.AWS_ENDPOINT_URL,
            region_name=database_async.AWS_REGION,
        ) as dynamodb:
            table = await dynamodb.Table(EPISODE_IDEMPOTENCE_TABLE)
            condition = "#st = :reserved"
            expr_names = {"#st": "status"}
            expr_values = {":reserved": "reserved"}
            if job_id:
                condition += " AND job_id = :j"
                expr_values[":j"] = job_id

            await table.delete_item(
                Key={"episode_guid": episode_guid},
                ConditionExpression=condition,
                ExpressionAttributeNames=expr_names,
                ExpressionAttributeValues=expr_values,
            )
        logger.info(f"Released reservation for guid {episode_guid} (job {job_id})")
    except ClientError as e:
        if e.response.get("Error", {}).get("Code") == "ConditionalCheckFailedException":
            # Nothing to release or not in reserved state; ignore
            logger.info(
                f"No reservation to release or state changed for guid {episode_guid}"
            )
            return
        logger.error(f"Error releasing reservation: {e}")
        raise
