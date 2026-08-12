"""
Translation idempotence: state machine + atomic reservation for transcript translations.

Follows the same pattern as artifact_idempotence.py (artifact generation locks),
adapted to the translation lifecycle:

    (none) -> queued -> in_progress -> done | failed

Key: deterministic fingerprint of (transcript_s3_key, target_language).

The reservation uses a DynamoDB ConditionExpression so that only the FIRST
caller to attempt a translation for a given (key, lang) pair wins the
reservation and enqueues the SQS job. All concurrent/subsequent callers read
the existing state and do NOT re-enqueue (anti-thundering-herd, AC#4/AC#5).

When the worker fails terminally (DLQ exhaustion), the status transitions to
``failed``, which re-authorizes a fresh reservation on the next access.
"""

from __future__ import annotations

import hashlib
import logging
from datetime import datetime, timezone
from typing import Optional

from botocore.exceptions import ClientError

from media_summarizer.utils import database_async
from media_summarizer.utils.env import required_env
from media_summarizer.utils.logging_config import log_event

logger = logging.getLogger(__name__)

TRANSLATION_IDEMPOTENCE_TABLE = required_env("TRANSLATION_IDEMPOTENCE_TABLE")


class TranslationStatus:
    """Translation state machine statuses."""

    QUEUED = "queued"
    IN_PROGRESS = "in_progress"
    DONE = "done"
    FAILED = "failed"


class TranslationLock:
    """State record for a single (transcript_s3_key, target_language) translation."""

    def __init__(
        self,
        *,
        translation_fingerprint: str,
        transcript_s3_key: str,
        target_language: str,
        status: str,
        created_at: Optional[str] = None,
        updated_at: Optional[str] = None,
        error_message: Optional[str] = None,
        worker_owner_id: Optional[str] = None,
    ) -> None:
        self.translation_fingerprint = translation_fingerprint
        self.transcript_s3_key = transcript_s3_key
        self.target_language = target_language
        self.status = status
        self.created_at = created_at or _now_iso()
        self.updated_at = updated_at or _now_iso()
        self.error_message = error_message
        self.worker_owner_id = worker_owner_id

    def to_dynamodb_item(self) -> dict:
        item = {
            "translation_fingerprint": self.translation_fingerprint,
            "transcript_s3_key": self.transcript_s3_key,
            "target_language": self.target_language,
            "status": self.status,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }
        if self.error_message:
            item["error_message"] = self.error_message
        if self.worker_owner_id:
            item["worker_owner_id"] = self.worker_owner_id
        return item

    @classmethod
    def from_dynamodb_item(cls, item: dict) -> "TranslationLock":
        return cls(
            translation_fingerprint=item["translation_fingerprint"],
            transcript_s3_key=item.get("transcript_s3_key", ""),
            target_language=item.get("target_language", ""),
            status=item.get("status", TranslationStatus.QUEUED),
            created_at=item.get("created_at"),
            updated_at=item.get("updated_at"),
            error_message=item.get("error_message"),
            worker_owner_id=item.get("worker_owner_id"),
        )


def build_translation_fingerprint(
    *,
    transcript_s3_key: str,
    target_language: str,
) -> str:
    """Deterministic fingerprint for a (transcript_s3_key, target_language) couple."""
    raw = f"{transcript_s3_key}::{target_language}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


async def get_translation_lock(
    translation_fingerprint: str,
) -> Optional[TranslationLock]:
    """Read the current translation state. Returns None if no record exists."""
    session = database_async.get_session()
    async with session.resource(
        "dynamodb",
        region_name=database_async.AWS_REGION,
    ) as dynamodb:
        table = await dynamodb.Table(TRANSLATION_IDEMPOTENCE_TABLE)
        resp = await table.get_item(
            Key={"translation_fingerprint": translation_fingerprint},
            ConsistentRead=True,
        )
        item = resp.get("Item")
        if not item:
            return None
        return TranslationLock.from_dynamodb_item(item)


async def reserve_translation(
    *,
    transcript_s3_key: str,
    target_language: str,
    allow_done_retry: bool = False,
) -> bool:
    """Atomically reserve a translation slot.

    Succeeds (returns True) only when:
    - No record exists for this fingerprint, OR
    - The existing record has status ``failed`` (allows retry after DLQ), OR
    - ``allow_done_retry`` is true and the record is ``done`` even though its
      translated S3 object is missing.

    All other callers get False and must NOT enqueue a translation job.
    This is the anti-thundering-herd gate (AC#4).
    """
    fingerprint = build_translation_fingerprint(
        transcript_s3_key=transcript_s3_key,
        target_language=target_language,
    )
    lock = TranslationLock(
        translation_fingerprint=fingerprint,
        transcript_s3_key=transcript_s3_key,
        target_language=target_language,
        status=TranslationStatus.QUEUED,
    )
    session = database_async.get_session()
    try:
        async with session.resource(
            "dynamodb",
            region_name=database_async.AWS_REGION,
        ) as dynamodb:
            table = await dynamodb.Table(TRANSLATION_IDEMPOTENCE_TABLE)
            condition_expression = (
                "attribute_not_exists(translation_fingerprint) OR #st = :failed"
            )
            expression_values = {":failed": TranslationStatus.FAILED}
            if allow_done_retry:
                condition_expression += " OR #st = :done"
                expression_values[":done"] = TranslationStatus.DONE

            await table.put_item(
                Item=lock.to_dynamodb_item(),
                ConditionExpression=condition_expression,
                ExpressionAttributeNames={"#st": "status"},
                ExpressionAttributeValues=expression_values,
            )
        log_event(
            logger,
            logging.INFO,
            "translation_idempotence.reserved",
            "Translation reservation acquired",
            translation_fingerprint=fingerprint,
            transcript_s3_key=transcript_s3_key,
            target_language=target_language,
        )
        return True
    except ClientError as exc:
        if exc.response.get("Error", {}).get("Code") == "ConditionalCheckFailedException":
            log_event(
                logger,
                logging.DEBUG,
                "translation_idempotence.already_reserved",
                "Translation already reserved by another caller",
                translation_fingerprint=fingerprint,
                transcript_s3_key=transcript_s3_key,
                target_language=target_language,
            )
            return False
        raise


async def mark_translation_in_progress(
    *,
    transcript_s3_key: str,
    target_language: str,
    worker_owner_id: str,
) -> bool:
    """Claim a translation for one SQS message.

    A queued or failed translation may be claimed by the first worker. Retries
    of that same SQS message may resume an ``in_progress`` translation, while a
    different duplicate message is rejected so it cannot issue a second LLM
    request for the same transcript.
    """
    fingerprint = build_translation_fingerprint(
        transcript_s3_key=transcript_s3_key,
        target_language=target_language,
    )
    session = database_async.get_session()
    async with session.resource(
        "dynamodb",
        region_name=database_async.AWS_REGION,
    ) as dynamodb:
        table = await dynamodb.Table(TRANSLATION_IDEMPOTENCE_TABLE)
        try:
            await table.update_item(
                Key={"translation_fingerprint": fingerprint},
                UpdateExpression=(
                    "SET #st = :in_progress, updated_at = :now, "
                    "worker_owner_id = :owner"
                ),
                ConditionExpression=(
                    "#st = :queued OR #st = :failed OR "
                    "(#st = :in_progress AND worker_owner_id = :owner)"
                ),
                ExpressionAttributeNames={"#st": "status"},
                ExpressionAttributeValues={
                    ":in_progress": TranslationStatus.IN_PROGRESS,
                    ":queued": TranslationStatus.QUEUED,
                    ":failed": TranslationStatus.FAILED,
                    ":owner": worker_owner_id,
                    ":now": _now_iso(),
                },
            )
            return True
        except ClientError as exc:
            if exc.response.get("Error", {}).get("Code") != "ConditionalCheckFailedException":
                raise
            log_event(
                logger,
                logging.DEBUG,
                "translation_idempotence.claim_rejected",
                "Translation is owned by another worker message",
                translation_fingerprint=fingerprint,
                worker_owner_id=worker_owner_id,
            )
            return False


async def mark_translation_done(
    *,
    transcript_s3_key: str,
    target_language: str,
) -> None:
    """Transition to done when translation completes successfully."""
    fingerprint = build_translation_fingerprint(
        transcript_s3_key=transcript_s3_key,
        target_language=target_language,
    )
    session = database_async.get_session()
    async with session.resource(
        "dynamodb",
        region_name=database_async.AWS_REGION,
    ) as dynamodb:
        table = await dynamodb.Table(TRANSLATION_IDEMPOTENCE_TABLE)
        await table.update_item(
            Key={"translation_fingerprint": fingerprint},
            UpdateExpression=(
                "SET #st = :done, updated_at = :now "
                "REMOVE error_message, worker_owner_id"
            ),
            ExpressionAttributeNames={"#st": "status"},
            ExpressionAttributeValues={
                ":done": TranslationStatus.DONE,
                ":now": _now_iso(),
            },
        )


async def mark_translation_failed(
    *,
    transcript_s3_key: str,
    target_language: str,
    error_message: Optional[str] = None,
) -> None:
    """Transition to failed (terminal). Re-authorizes a future reserve_translation.

    Called when the worker exhausts retries or the message ends up on DLQ.
    """
    fingerprint = build_translation_fingerprint(
        transcript_s3_key=transcript_s3_key,
        target_language=target_language,
    )
    session = database_async.get_session()
    async with session.resource(
        "dynamodb",
        region_name=database_async.AWS_REGION,
    ) as dynamodb:
        table = await dynamodb.Table(TRANSLATION_IDEMPOTENCE_TABLE)
        update_expr = "SET #st = :failed, updated_at = :now"
        attr_values: dict = {
            ":failed": TranslationStatus.FAILED,
            ":now": _now_iso(),
        }
        if error_message:
            update_expr += ", error_message = :err"
            attr_values[":err"] = error_message[:500]
        update_expr += " REMOVE worker_owner_id"

        await table.update_item(
            Key={"translation_fingerprint": fingerprint},
            UpdateExpression=update_expr,
            ExpressionAttributeNames={"#st": "status"},
            ExpressionAttributeValues=attr_values,
        )
    log_event(
        logger,
        logging.WARNING,
        "translation_idempotence.failed",
        "Translation marked as failed",
        translation_fingerprint=fingerprint,
        transcript_s3_key=transcript_s3_key,
        target_language=target_language,
        error_message=(error_message or "")[:200],
    )
