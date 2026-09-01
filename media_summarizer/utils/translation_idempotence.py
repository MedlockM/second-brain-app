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

A ``failed`` lock re-authorizes a fresh reservation on the next access -- but
only when the failure was **transient**. A ``failed`` lock carrying
``failure_kind=permanent`` (no credit left, rejected key, unknown model) refuses
re-reservation for :data:`PERMANENT_FAILURE_RETRY_AFTER_SECONDS`, because
re-reserving it is how one exhausted OpenAI balance turned into 75 provider calls
for a single document (task-327). A cooldown rather than a flat refusal is what
keeps the couple recoverable once the provider works again: nothing else in the
system ever clears a lock.
"""

from __future__ import annotations

import hashlib
import logging
from datetime import datetime, timedelta, timezone
from typing import Optional, TypeGuard

from botocore.exceptions import ClientError

from media_summarizer.utils import database_async
from media_summarizer.utils.env import required_env
from media_summarizer.utils.llm_failure import LLMFailureKind
from media_summarizer.utils.logging_config import log_event

logger = logging.getLogger(__name__)

TRANSLATION_IDEMPOTENCE_TABLE = required_env("TRANSLATION_IDEMPOTENCE_TABLE")

# How long a permanently failed translation stays terminal before one attempt is
# allowed again. One hour bounds the waste at one provider call per hour per
# couple (against 75 in six minutes during the task-327 incident) while keeping
# the recovery automatic: the owner tops the credit up and the next request an
# hour later translates, with no lock to purge by hand.
PERMANENT_FAILURE_RETRY_AFTER_SECONDS = 3600


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
        failure_kind: Optional[str] = None,
    ) -> None:
        self.translation_fingerprint = translation_fingerprint
        self.transcript_s3_key = transcript_s3_key
        self.target_language = target_language
        self.status = status
        self.created_at = created_at or _now_iso()
        self.updated_at = updated_at or _now_iso()
        self.error_message = error_message
        self.worker_owner_id = worker_owner_id
        #: Set with ``status=failed`` only. ``permanent`` means the provider
        #: refused for a reason a retry cannot change, so readers must treat this
        #: translation as never coming rather than as pending.
        self.failure_kind = failure_kind

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
        if self.failure_kind:
            item["failure_kind"] = self.failure_kind
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
            failure_kind=item.get("failure_kind"),
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


def _permanent_retry_cutoff_iso() -> str:
    """Timestamp before which a permanent failure stops being terminal.

    ISO-8601 UTC strings produced by :func:`_now_iso` sort lexicographically, so
    this same value drives both the Python predicate below and the DynamoDB
    ConditionExpression of :func:`reserve_translation` -- the reader and the
    writer can never disagree about whether a lock is still terminal.
    """
    cutoff = datetime.now(timezone.utc) - timedelta(
        seconds=PERMANENT_FAILURE_RETRY_AFTER_SECONDS
    )
    return cutoff.isoformat()


def is_terminally_failed(
    lock: Optional["TranslationLock"],
) -> TypeGuard["TranslationLock"]:
    """True when this translation will not be attempted again.

    The one state where a caller must stop waiting: the provider refused for a
    reason a retry cannot change, and the cooldown has not elapsed. Everything
    else -- no lock, queued, in_progress, done, or a transient failure -- means
    the translation is either coming or re-reservable.

    Typed as a ``TypeGuard`` so a caller that reads ``error_message`` off the lock
    right after the check needs no redundant ``is not None``.
    """
    if lock is None or lock.status != TranslationStatus.FAILED:
        return False
    if lock.failure_kind != LLMFailureKind.PERMANENT:
        return False
    updated_at = lock.updated_at or ""
    # A lock with no timestamp stays terminal: the ConditionExpression refuses it
    # too (a comparison against a missing attribute is false in DynamoDB), and
    # the two must answer the same thing.
    return not (updated_at and updated_at < _permanent_retry_cutoff_iso())


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


async def delete_translation_lock(translation_fingerprint: str) -> None:
    """Delete one translation lock. Idempotent.

    Safe to call per user, unlike the artifact generation lock: the fingerprint
    hashes the transcript S3 key, and transcript keys are per job, so a lock is
    never shared between two accounts.
    """
    session = database_async.get_session()
    async with session.resource(
        "dynamodb",
        region_name=database_async.AWS_REGION,
    ) as dynamodb:
        table = await dynamodb.Table(TRANSLATION_IDEMPOTENCE_TABLE)
        await table.delete_item(
            Key={"translation_fingerprint": translation_fingerprint}
        )


async def reserve_translation(
    *,
    transcript_s3_key: str,
    target_language: str,
    allow_done_retry: bool = False,
) -> bool:
    """Atomically reserve a translation slot.

    Succeeds (returns True) only when:
    - No record exists for this fingerprint, OR
    - The existing record has status ``failed`` **and** that failure is not a
      fresh permanent one (allows retry after DLQ), OR
    - ``allow_done_retry`` is true and the record is ``done`` even though its
      translated S3 object is missing.

    All other callers get False and must NOT enqueue a translation job.
    This is the anti-thundering-herd gate (AC#4).

    The ``failure_kind`` clause is the task-327 gate: a translation the provider
    refused permanently is not re-reserved, so the client polling loop above it
    stops feeding provider calls. It expires after
    :data:`PERMANENT_FAILURE_RETRY_AFTER_SECONDS` so a topped-up account heals on
    its own.
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
            # ``attribute_not_exists(failure_kind)`` is not a legacy shim: in
            # DynamoDB a comparison against a missing attribute is false, so
            # without it a lock whose kind was never written would be
            # unreservable forever -- the exact dead end this gate exists to
            # prevent.
            condition_expression = (
                "attribute_not_exists(translation_fingerprint) OR "
                "(#st = :failed AND ("
                "attribute_not_exists(failure_kind) OR "
                "failure_kind <> :permanent OR "
                "updated_at < :permanent_retry_cutoff"
                "))"
            )
            expression_values = {
                ":failed": TranslationStatus.FAILED,
                ":permanent": LLMFailureKind.PERMANENT,
                ":permanent_retry_cutoff": _permanent_retry_cutoff_iso(),
            }
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

    A permanently failed lock stays claimable here, unlike in
    :func:`reserve_translation`. That is deliberate: the only way a message
    reaches this function without a reservation is an owner redriving the DLQ,
    which is precisely the manual "try it again now" the cooldown otherwise makes
    the owner wait for.
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
                "REMOVE error_message, worker_owner_id, failure_kind"
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
    failure_kind: str = LLMFailureKind.TRANSIENT,
) -> None:
    """Transition to failed, recording *why* the failure is or is not final.

    ``failure_kind`` is what separates a translation worth attempting again from
    one that will get the same refusal forever (task-327 AC#3). It is written
    next to the status, so every reader -- the reservation gate, ``/raw-content``,
    artifact scope resolution -- decides from the lock alone, with no need to
    re-parse a provider message.

    Callers must pass ``PERMANENT`` only for a failure classified as such by
    :func:`media_summarizer.utils.llm_failure.classify_llm_failure`. The default
    is deliberately the conservative one: an infrastructure hiccup (S3, SQS, an
    unexpected exception) leaves the couple re-reservable.
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
        update_expr = "SET #st = :failed, updated_at = :now, failure_kind = :kind"
        attr_values: dict = {
            ":failed": TranslationStatus.FAILED,
            ":now": _now_iso(),
            ":kind": failure_kind,
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
        failure_kind=failure_kind,
        error_message=(error_message or "")[:200],
    )
