"""
The back half of the library lifecycle: purge cascade + daily reconciliation.

One Lambda, two triggers, because both answer the same question ("did the
deletion actually delete everything?") and neither is worth its own function:

1. **``user_media`` DynamoDB stream, REMOVE events.** When the TTL sweeps a row a
   user soft-deleted 30 days earlier (see
   ``core/services/media_deletion_service.py``), the cascade in
   ``core/services/media_purge_service.py`` destroys the artifacts, the S3
   objects and the search records that row owned. The cascade *must* be complete:
   ``media_item_id`` is a hash of ``(user_id, media_key)``, so re-saving the same
   URL later lands on the same id and would inherit whatever was left behind.

2. **A daily schedule.** The reconciliation of §6.5: artifacts whose library row
   is gone, rows whose ``purge_at`` passed without the cascade running, dangling
   ``last_job_id`` pointers, per-user library size. This is the outcome metric the
   task-218 incident was missing — the archiver Lambda reported zero errors for
   two months while the data it was supposed to protect disappeared.

Which REMOVEs are cascaded, and which are deliberately not:

    TTL sweep, ``deleted_at`` present    -> cascade. The expected path.
    TTL sweep, no ``deleted_at``         -> ALARM, no cascade. Nothing but the
                                            deletion use case may write
                                            ``purge_at`` (invariant I2), so this
                                            means an illegal writer exists. The
                                            row is already gone; refusing to
                                            cascade keeps the artifacts and the
                                            objects recoverable while the
                                            regression is fixed.
    Deletion by a caller                 -> no cascade. Account deletion
                                            (task-224) cascades inline, over the
                                            whole account at once, which is the
                                            correct scope for shared objects. A
                                            second cascade here would be a
                                            duplicate at best.

Reference: ``docs/research/task-218-durable-media-library-persistence/README.md``
§6.2 (deletion), §6.5 (observability). Runbook:
``infrastructure/observability/runbooks/durable-media.md``.
"""

from __future__ import annotations

import asyncio
import logging
import random
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Iterable, List, Optional, Tuple

from boto3.dynamodb.types import TypeDeserializer

from media_summarizer.core.services import media_purge_service, search_indexing
from media_summarizer.utils import database_async
from media_summarizer.utils.env import required_env
from media_summarizer.utils.logging_config import log_event

logger = logging.getLogger(__name__)

_deserializer = TypeDeserializer()

EVENT_PURGE_COMPLETED = "user_media.purge_cascade_completed"
EVENT_PURGE_FAILED = "user_media.purge_cascade_failed"
EVENT_UNEXPLAINED_PURGE = "user_media.unexplained_purge"
EVENT_REMOVED_BY_CALLER = "user_media.removed_by_caller"
EVENT_RECONCILED = "user_media.reconciliation_completed"
EVENT_RECONCILE_FAILED = "user_media.reconciliation_failed"

# An artifact row whose library row is gone is only actionable when it is *new*:
# dev carries a permanent standing drift from the task-241 backfill (139
# quarantined rows), so alarming on total drift would be permanently breaching
# and therefore ignored. A recent orphan, by contrast, means a live write path is
# creating artifacts for a library row that does not exist.
ORPHAN_RECENT_WINDOW_HOURS = 48

# DynamoDB TTL is best-effort within 48h of purge_at. Past that, a row still
# present is a sweeper that stopped or a table whose TTL setting was lost (which
# is exactly what a PITR restore does -- see the runbook).
PURGE_OVERDUE_GRACE_HOURS = 48

# last_job_id is a nullable pointer that is *allowed* to dangle (invariant I3):
# jobs expire, library rows do not. The gauge exists to show the ratio is sane,
# not to alarm, so a bounded random sample is enough and keeps the daily run from
# issuing one GetItem per library row forever.
DANGLING_POINTER_SAMPLE = 500


# ---------------------------------------------------------------------------
# Stream: the purge cascade
# ---------------------------------------------------------------------------


def _deserialize(image: Dict[str, Any]) -> Dict[str, Any]:
    return {key: _deserializer.deserialize(value) for key, value in image.items()}


def _is_ttl_deletion(record: Dict[str, Any]) -> bool:
    """DynamoDB stamps TTL deletions with a service principal on the record."""
    identity = record.get("userIdentity") or {}
    return identity.get("principalId") == "dynamodb.amazonaws.com"


async def purge_media_item(
    *,
    user_id: str,
    media_item_id: str,
    last_job_id: Optional[str] = None,
) -> Dict[str, int]:
    """Destroy everything one library item owned. Idempotent by construction.

    Every step is a delete, so replaying the cascade after a partial failure is
    safe — which is what makes it correct to let the stream retry.
    """
    counts: Dict[str, int] = {}
    counts.update(
        await media_purge_service.purge_artifacts_for_scopes(
            user_id=user_id, media_item_ids=[media_item_id]
        )
    )

    if last_job_id:
        # No job row to read keys off: it may have expired years ago. The prefix
        # sweeps are the whole cleanup, which is why purge_job_objects accepts
        # being called with the id alone.
        for key, value in (await media_purge_service.purge_job_objects(last_job_id)).items():
            counts[key] = counts.get(key, 0) + value

    await asyncio.to_thread(search_indexing.delete_document, user_id, media_item_id)
    counts["search_documents_deleted"] = 1
    return counts


async def _handle_removed_row(record: Dict[str, Any]) -> str:
    """Process one stream REMOVE. Returns the outcome name, for the batch summary."""
    old_image = (record.get("dynamodb") or {}).get("OldImage")
    if not old_image:
        # OLD_IMAGE is guaranteed by the table's NEW_AND_OLD_IMAGES stream view,
        # so this is unreachable unless the view type was changed.
        logger.warning("user_media REMOVE without OldImage: %s", record.get("eventID"))
        return "skipped_no_old_image"

    item = _deserialize(old_image)
    user_id = str(item.get("user_id") or "")
    media_item_id = str(item.get("media_item_id") or "")
    if not user_id or not media_item_id:
        logger.warning("user_media REMOVE without keys: %s", record.get("eventID"))
        return "skipped_no_keys"

    if not _is_ttl_deletion(record):
        log_event(
            logger,
            logging.INFO,
            EVENT_REMOVED_BY_CALLER,
            "user_media row deleted by a caller, not by TTL: no cascade here",
            user_id=user_id,
            media_item_id=media_item_id,
        )
        return "skipped_not_ttl"

    if not item.get("deleted_at"):
        log_event(
            logger,
            logging.ERROR,
            EVENT_UNEXPLAINED_PURGE,
            "A user_media row was swept by TTL without ever being deleted by its "
            "owner: purge_at was written by something other than the deletion use "
            "case (invariant I2 violated). Cascade skipped so the content stays "
            "recoverable.",
            user_id=user_id,
            media_item_id=media_item_id,
            purge_at=item.get("purge_at"),
            last_job_id=item.get("last_job_id"),
        )
        return "unexplained_purge"

    last_job_id = item.get("last_job_id")
    try:
        counts = await purge_media_item(
            user_id=user_id,
            media_item_id=media_item_id,
            last_job_id=str(last_job_id) if last_job_id else None,
        )
    except Exception as exc:
        log_event(
            logger,
            logging.ERROR,
            EVENT_PURGE_FAILED,
            f"Purge cascade failed after a user_media TTL sweep: {exc}",
            user_id=user_id,
            media_item_id=media_item_id,
            last_job_id=last_job_id,
            error_type=type(exc).__name__,
            exc_info=True,
        )
        raise

    log_event(
        logger,
        logging.INFO,
        EVENT_PURGE_COMPLETED,
        "Purge cascade completed for a user-deleted media item",
        user_id=user_id,
        media_item_id=media_item_id,
        last_job_id=last_job_id,
        deleted_at=item.get("deleted_at"),
        **{f"count_{key}": value for key, value in counts.items()},
    )
    return "purged"


async def handle_stream_records(records: Iterable[Dict[str, Any]]) -> Dict[str, Any]:
    """Cascade every REMOVE in the batch, reporting per-record failures.

    Partial batch response rather than raising: one poisoned record must not
    block the shard, and every failure is already logged as
    ``user_media.purge_cascade_failed`` (alarmed). Records the retries never
    manage to process are caught by the daily reconciliation as orphans.
    """
    failures: List[Dict[str, str]] = []
    outcomes: Dict[str, int] = {}

    for record in records:
        if record.get("eventName") != "REMOVE":
            continue
        try:
            outcome = await _handle_removed_row(record)
        except Exception:
            outcome = "failed"
            identifier = (record.get("dynamodb") or {}).get("SequenceNumber")
            if identifier:
                failures.append({"itemIdentifier": str(identifier)})
        outcomes[outcome] = outcomes.get(outcome, 0) + 1

    logger.info("user_media stream batch outcomes: %s", outcomes)
    return {"batchItemFailures": failures}


# ---------------------------------------------------------------------------
# Schedule: the daily reconciliation
# ---------------------------------------------------------------------------


async def _scan_table(
    table_name: str,
    projection: str,
    *,
    expression_attribute_names: Optional[Dict[str, str]] = None,
) -> List[Dict[str, Any]]:
    session = database_async.get_session()
    items: List[Dict[str, Any]] = []
    async with session.resource(
        "dynamodb",
        region_name=database_async.AWS_REGION,
    ) as dynamodb:
        table = await dynamodb.Table(table_name)
        kwargs: Dict[str, Any] = {"ProjectionExpression": projection}
        if expression_attribute_names:
            # `scope` is a DynamoDB reserved word, so it can only be projected
            # through a name placeholder.
            kwargs["ExpressionAttributeNames"] = expression_attribute_names
        while True:
            resp = await table.scan(**kwargs)
            items.extend(resp.get("Items", []))
            last_key = resp.get("LastEvaluatedKey")
            if not last_key:
                return items
            kwargs["ExclusiveStartKey"] = last_key


def _parse_iso(value: Any) -> Optional[datetime]:
    if not value or not isinstance(value, str):
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed


async def _count_dangling_pointers(
    pointers: List[Tuple[str, str]],
) -> Tuple[int, int]:
    """(checked, dangling) over a bounded random sample of ``last_job_id`` values."""
    if not pointers:
        return 0, 0
    sample = pointers
    if len(pointers) > DANGLING_POINTER_SAMPLE:
        sample = random.sample(pointers, DANGLING_POINTER_SAMPLE)

    dangling = 0
    for _media_item_id, job_id in sample:
        job = await database_async.get_processing_job_by_id(job_id)
        if job is None:
            dangling += 1
    return len(sample), dangling


async def run_reconciliation() -> Dict[str, Any]:
    """Compare the library against what it owns and publish the gauges of §6.5."""
    now = datetime.now(timezone.utc)
    recent_cutoff = now - timedelta(hours=ORPHAN_RECENT_WINDOW_HOURS)
    overdue_cutoff = int((now - timedelta(hours=PURGE_OVERDUE_GRACE_HOURS)).timestamp())

    library = await _scan_table(
        required_env("USER_MEDIA_TABLE"),
        "user_id, media_item_id, deleted_at, purge_at, last_job_id",
    )

    library_ids = set()
    per_user: Dict[str, int] = {}
    pointers: List[Tuple[str, str]] = []
    rows_deleted_pending_purge = 0
    rows_overdue_purge = 0

    for row in library:
        media_item_id = str(row.get("media_item_id") or "")
        library_ids.add(media_item_id)
        user_id = str(row.get("user_id") or "")
        per_user[user_id] = per_user.get(user_id, 0) + 1
        last_job_id = row.get("last_job_id")
        if last_job_id:
            pointers.append((media_item_id, str(last_job_id)))
        if row.get("deleted_at"):
            rows_deleted_pending_purge += 1
        purge_at = row.get("purge_at")
        if purge_at is not None and int(purge_at) < overdue_cutoff:
            rows_overdue_purge += 1

    artifacts = await _scan_table(
        required_env("MEDIA_ARTIFACTS_TABLE"),
        "artifact_id, #sc, scope_id, created_at",
        expression_attribute_names={"#sc": "scope"},
    )

    artifact_rows = 0
    orphaned = 0
    orphaned_recent = 0
    for row in artifacts:
        artifact_rows += 1
        # Only media-scoped entries can be orphaned by a library row leaving;
        # a collection artifact hangs off a folder, which this gauge does not
        # inventory (task-270).
        if str(row.get("scope") or "") != "media":
            continue
        scope_id = str(row.get("scope_id") or "")
        if scope_id and scope_id in library_ids:
            continue
        orphaned += 1
        created_at = _parse_iso(row.get("created_at"))
        if created_at and created_at >= recent_cutoff:
            orphaned_recent += 1

    pointers_checked, pointers_dangling = await _count_dangling_pointers(pointers)

    report = {
        "library_rows": len(library),
        "library_users": len(per_user),
        "library_rows_deleted_pending_purge": rows_deleted_pending_purge,
        "library_rows_overdue_purge": rows_overdue_purge,
        "library_max_rows_per_user": max(per_user.values()) if per_user else 0,
        "artifact_rows": artifact_rows,
        "artifact_rows_orphaned": orphaned,
        "artifact_rows_orphaned_recent": orphaned_recent,
        "pointers_checked": pointers_checked,
        "pointers_dangling": pointers_dangling,
    }

    log_event(
        logger,
        logging.INFO,
        EVENT_RECONCILED,
        "user_media reconciliation completed",
        **report,
    )
    return report


# ---------------------------------------------------------------------------
# Lambda entrypoint
# ---------------------------------------------------------------------------


def handle_event(event: Dict[str, Any]) -> Dict[str, Any]:
    """Route by event shape: a stream batch has Records, the schedule does not.

    Called from ``workers/lambda_handlers.py`` so the cold-start secret load
    (Algolia credentials, needed to delete search records) happens exactly once
    and in one place.
    """
    records = event.get("Records") if isinstance(event, dict) else None
    if records:
        return asyncio.run(handle_stream_records(records))

    try:
        return asyncio.run(run_reconciliation())
    except Exception as exc:
        log_event(
            logger,
            logging.ERROR,
            EVENT_RECONCILE_FAILED,
            f"user_media reconciliation failed: {exc}",
            error_type=type(exc).__name__,
            exc_info=True,
        )
        raise
