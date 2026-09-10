"""
Media idempotence utilities using DynamoDB.

Canonical schema (MEDIA_IDEMPOTENCE_TABLE, default "media_idempotence"):
- PK: media_key (S)
- Attributes: status (reserved|processed|failed), job_id, created_at, updated_at
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from botocore.exceptions import ClientError

from media_summarizer.utils import database_async
from media_summarizer.utils.env import required_env

logger = logging.getLogger(__name__)

MEDIA_IDEMPOTENCE_TABLE = required_env("MEDIA_IDEMPOTENCE_TABLE")


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


async def _record_terminal_status(
    *,
    media_key: Optional[str],
    job_id: Optional[str],
    status: str,
) -> bool:
    """Move an existing ledger row to a terminal status. ``True`` if it moved.

    The write is conditional on the row still pointing at the job that reports
    the outcome (or at no job at all, which is how a reservation made before its
    job id was known looks). A completion event redelivered after the content was
    purged and re-reserved therefore cannot stamp a dead job's outcome onto the
    new reservation, and cannot make a fresh in-flight job read as processed.

    ``False`` is a normal outcome, not an error: it means there is no ledger row
    for this content (nothing ever reserved it -- a direct upload, or a purged
    entry) or the ledger has legitimately moved on to another job. The caller
    keeps going; nothing about the media it just handled is invalidated by it.
    """
    identity_key = _resolve_identity_key(media_key)
    update = "SET #st = :s, updated_at = :u"
    condition = "attribute_exists(media_key)"
    expr_values: Dict[str, Any] = {":s": status, ":u": _now_iso()}
    if job_id:
        update += ", job_id = :j"
        condition += (
            " AND (attribute_not_exists(job_id)"
            " OR job_id = :j OR job_id = :no_job)"
        )
        expr_values[":j"] = job_id
        expr_values[":no_job"] = ""

    try:
        session = database_async.get_session()
        async with session.resource(
            "dynamodb",
            region_name=database_async.AWS_REGION,
        ) as dynamodb:
            table = await dynamodb.Table(MEDIA_IDEMPOTENCE_TABLE)
            await table.update_item(
                Key={"media_key": identity_key},
                UpdateExpression=update,
                ExpressionAttributeNames={"#st": "status"},
                ExpressionAttributeValues=expr_values,
                ConditionExpression=condition,
            )
    except ClientError as e:
        if e.response.get("Error", {}).get("Code") == "ConditionalCheckFailedException":
            logger.info(
                "No ledger row of job %s to mark %s for media_key=%s",
                job_id,
                status,
                identity_key,
            )
            return False
        logger.error("Error marking media idempotence %s: %s", status, e)
        raise

    logger.info(
        "Marked %s for media_key=%s (job=%s)", status, identity_key, job_id
    )
    return True


async def mark_processed(
    media_key: Optional[str] = None,
    job_id: Optional[str] = None,
) -> bool:
    """Record that this content has been processed and needs no further job.

    Called by the single path that completes a media
    (``workers/events/media_completed_worker``) and by the submission
    orchestrator when it finds a stranded reservation whose job in fact finished.
    Until task-390 nothing called it at all, so ``reserved`` was permanent and
    every re-save of an already-processed URL was parked in ``pending`` waiting
    for a job that had finished days earlier.
    """
    return await _record_terminal_status(
        media_key=media_key, job_id=job_id, status="processed"
    )


async def mark_failed(
    media_key: Optional[str] = None,
    job_id: Optional[str] = None,
) -> bool:
    """Record that the job that owned this content ended without a transcript."""
    return await _record_terminal_status(
        media_key=media_key, job_id=job_id, status="failed"
    )


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


async def delete_content_entry(
    *,
    media_key: str,
    job_id: str,
) -> bool:
    """Remove the ledger pointer after the final saved reference is purged.

    The condition prevents a late purge from deleting a newer reservation for
    the same content. Returning ``False`` means the ledger already moved on.
    """
    identity_key = _resolve_identity_key(media_key)
    try:
        session = database_async.get_session()
        async with session.resource(
            "dynamodb",
            region_name=database_async.AWS_REGION,
        ) as dynamodb:
            table = await dynamodb.Table(MEDIA_IDEMPOTENCE_TABLE)
            await table.delete_item(
                Key={"media_key": identity_key},
                ConditionExpression="job_id = :job_id",
                ExpressionAttributeValues={":job_id": job_id},
            )
        return True
    except ClientError as exc:
        if exc.response.get("Error", {}).get("Code") == "ConditionalCheckFailedException":
            return False
        raise
