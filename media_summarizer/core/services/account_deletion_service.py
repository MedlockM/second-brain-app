"""
Full-account erasure: the one place that deletes everything an account owns.

Why this module exists
----------------------
App Store guideline 5.1.1(v) requires any app that lets a user create an account
to let them delete it from inside the app, and GDPR art. 17 requires that
deletion to actually erase the data instead of hiding it. The route this replaces
(``DELETE /api/v1/users/{user_id}``) did neither: it removed a single row from
``users`` and left the library, the artifacts, the S3 objects and the search
index behind -- an account that could no longer log in while its content stayed
fully indexed. That is the worst of both worlds and is exactly the state the
ordering below is designed to make impossible.

Ordering is a correctness property, not a style choice
------------------------------------------------------
Steps run from the most *discoverable* data to the least, and the identity rows
(``auth_tokens``, then the ``users`` row) go last:

    search index -> artifacts + their objects -> media objects -> media rows
    -> per-user tables -> identity

A failure therefore leaves an account that still authenticates and can retry the
deletion, never an account that is locked out while its transcripts are still
searchable. Every step is query-then-delete against DynamoDB, so a re-run after a
partial failure is a no-op on whatever already went (AC#6).

Content shared between accounts
-------------------------------
The per-media cascade — artifact rows, their S3 objects and
the objects a processing job wrote — lives in
``core/services/media_purge_service.py`` and is shared with the ``user_media`` TTL
purge (task-243). Both paths must remove exactly the same things: because
``media_item_id`` is deterministic in ``(user_id, media_key)``, an artifact that
outlives its media row would reattach to the next save of the same URL. See that
module for the shared-object rule that keeps one account's departure from
breaking another's copy of the same episode.

Deliberately out of scope
-------------------------
``media_idempotence`` (PK ``media_key``) and ``feed_forecasts`` (PK ``feed_id``)
describe content, not people: they carry no user id, are shared by every account
that submitted the same media, and cannot be queried per user in the first place.
Artifact rows are reached through the scope index, keyed on ``user_id``.
``pricing_config`` is global configuration.

The archive bucket is not swept either: its keys are partitioned by archive date,
not by user, so there is nothing to enumerate. Instead each job row is stamped
with ``purge_reason = account_deletion`` before it is deleted, which is the signal
the DynamoDB-stream archiver (task-242, a no-op placeholder today) needs to skip
the REMOVE events this purge generates. Without it, erasing an account would
*create* a copy of its data in the archive bucket.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Sequence, Set, Tuple

from boto3.dynamodb.conditions import Attr, Key

from media_summarizer.core.models.processing_job import ProcessingJob
from media_summarizer.core.services import media_purge_service, search_indexing
from media_summarizer.utils import database_async, s3, user_media
from media_summarizer.utils.env import required_env
from media_summarizer.utils.logging_config import log_event

logger = logging.getLogger(__name__)

USER_INDEX = "user-index"

# Stamped on a job row just before it is deleted, so the OLD_IMAGE carried by the
# DynamoDB stream tells the archiver this REMOVE is an erasure, not a retention
# expiry. Read by task-242's archiver.
PURGE_REASON_ACCOUNT_DELETION = "account_deletion"

# Per-job S3 work runs concurrently: the API Lambda has a 30s budget and a job
# costs three LIST round-trips plus its deletes. Sequential purging of a large
# library would time out, and a timeout mid-purge is a (retryable) partial purge.
_JOB_CONCURRENCY = 8

# DynamoDB tables whose partition key *is* the user id. Value is the sort key
# attribute, or None for one-row-per-user tables. This tuple is the auditable
# inventory required by AC#3: adding a user-scoped table without adding it here
# is the bug this shape exists to make obvious.
_USER_PARTITION_TABLES: Tuple[Tuple[str, Optional[str]], ...] = (
    ("USER_USAGE_MONTHLY_TABLE", "period"),
    ("USER_USAGE_DAILY_TABLE", "date"),
    ("REVIEW_SCHEDULE_TABLE", "card_id"),
    ("USER_REVIEW_SETTINGS_TABLE", None),
    ("USER_DIGESTS_TABLE", "digest_key"),
    ("USER_DIGEST_SETTINGS_TABLE", None),
    ("FOLLOWS_TABLE", "feed_id"),
)

# Tables that own the user's rows under their own primary key and expose them
# through a ``user-index`` GSI. Value is the table's partition key attribute.
_USER_INDEX_TABLES: Tuple[Tuple[str, str], ...] = (
    ("USER_FOLDERS_TABLE", "id"),
    ("USER_TAGS_TABLE", "id"),
    ("USER_RSS_FEEDS_TABLE", "id"),
    ("SUBSCRIPTIONS_TABLE", "id"),
    ("BUG_REPORTS_TABLE", "id"),
)


@dataclass
class PurgeReport:
    """What the purge actually removed, for the audit log and the API log line."""

    user_id: str
    counts: Dict[str, int] = field(default_factory=dict)

    def add(self, step: str, count: int = 1) -> None:
        self.counts[step] = self.counts.get(step, 0) + count

    def merge(self, other: Dict[str, int]) -> None:
        for step, count in other.items():
            self.add(step, count)

    def total(self) -> int:
        return sum(self.counts.values())


async def purge_account(user_id: str) -> PurgeReport:
    """Erase every trace of one account. Idempotent, ordered, fail-fast.

    Raises whatever the underlying store raises. The caller must surface that as
    an error rather than reporting success: a purge that half-ran is a purge the
    user has to be able to retry, and every step re-runs cleanly.
    """
    report = PurgeReport(user_id=user_id)

    await _purge_search_index(user_id, report)

    inventory = await _collect_inventory(user_id)
    await _purge_artifacts(user_id, inventory, report)
    await _purge_media_objects(user_id, inventory, report)
    await _purge_media_watchers(user_id, inventory, report)
    await _purge_processing_jobs(inventory, report)
    report.add("user_media_rows", await user_media.delete_all_for_user(user_id))

    for env_var, sort_key in _USER_PARTITION_TABLES:
        table_name = required_env(env_var)
        report.add(env_var, await _purge_partition(table_name, user_id, sort_key))
    for env_var, primary_key in _USER_INDEX_TABLES:
        table_name = required_env(env_var)
        report.add(env_var, await _purge_by_user_index(table_name, user_id, primary_key))

    await _purge_bug_report_attachments(inventory, report)
    await _purge_revenucat_events(user_id, report)
    await _purge_identity(user_id, report)

    log_event(
        logger,
        logging.INFO,
        "account_deletion.purged",
        "Account purged",
        user_id=user_id,
        records_removed=report.total(),
        **{f"count_{key}": value for key, value in report.counts.items()},
    )
    return report


# ---------------------------------------------------------------------------
# Inventory
# ---------------------------------------------------------------------------


@dataclass
class _Inventory:
    """Everything the purge has to know before it starts deleting.

    Collected up front because the deletion order destroys the very rows the
    later steps need to find their targets: artifacts are reachable only through
    ``media_item_id``, watchers only through ``media_key``, and both live on rows
    this purge removes.
    """

    jobs: List[ProcessingJob]
    media_item_ids: Set[str]
    media_keys: Set[str]
    bug_report_attachment_keys: Set[str]


async def _collect_inventory(user_id: str) -> _Inventory:
    jobs = await _list_processing_jobs(user_id)
    library = await user_media.list_all_for_user(user_id)

    media_item_ids: Set[str] = set()
    media_keys: Set[str] = set()
    for job in jobs:
        # Legacy jobs carry artifacts under their own id; jobs created through the
        # durable library carry a separate media_item_id. Both are looked up: an
        # extra query that returns nothing is free, a missed one leaks artifacts.
        media_item_ids.add(job.id)
        if job.media_item_id:
            media_item_ids.add(job.media_item_id)
        if job.media_key:
            media_keys.add(job.media_key)
    for record in library:
        media_item_ids.add(record.media_item_id)
        if record.media_key:
            media_keys.add(record.media_key)

    attachment_keys: Set[str] = set()
    for item in await _query_user_index(
        required_env("BUG_REPORTS_TABLE"), user_id, projection=("id", "attachment_key")
    ):
        key = item.get("attachment_key")
        if key:
            attachment_keys.add(str(key))

    return _Inventory(
        jobs=jobs,
        media_item_ids=media_item_ids,
        media_keys=media_keys,
        bug_report_attachment_keys=attachment_keys,
    )


async def _list_processing_jobs(user_id: str) -> List[ProcessingJob]:
    """Paginated read of the user's jobs.

    Deliberately not a single ``query`` on the ``user-index``: that stops at the
    first 1 MB page, and for an erasure the jobs it dropped are exactly the ones
    whose S3 objects would survive.
    """
    items = await _query_user_index(required_env("PROCESSING_JOBS_TABLE"), user_id)
    return [ProcessingJob.from_dynamodb_item(item) for item in items]


# ---------------------------------------------------------------------------
# Search index
# ---------------------------------------------------------------------------


async def _purge_search_index(user_id: str, report: PurgeReport) -> None:
    """Drop the user's records from the shared Algolia index (AC#4).

    First step on purpose: search is the most exposed surface, and the shared
    index means a leftover record is discoverable by other accounts' queries.
    A missing Algolia configuration is the one tolerated failure -- an
    environment with no credentials has nothing indexed to leak.
    """
    try:
        await asyncio.to_thread(search_indexing.delete_user_records, user_id)
    except RuntimeError as exc:
        log_event(
            logger,
            logging.WARNING,
            "account_deletion.search_index_unconfigured",
            "Skipping search index purge: Algolia is not configured",
            user_id=user_id,
            detail=str(exc)[:200],
        )
        return
    report.add("search_index_purges")


# ---------------------------------------------------------------------------
# Artifacts
# ---------------------------------------------------------------------------


async def _purge_artifacts(
    user_id: str, inventory: _Inventory, report: PurgeReport
) -> None:
    from media_summarizer.utils import database_async

    # Collection artifacts hang off the folder, not off any media item, so the
    # folders have to be walked explicitly or every one of them survives the
    # erasure (task-270).
    folders = await database_async.get_folders_by_user_id(user_id)
    report.merge(
        await media_purge_service.purge_artifacts_for_scopes(
            user_id=user_id,
            media_item_ids=inventory.media_item_ids,
            folder_ids=[folder.id for folder in folders],
        )
    )


# ---------------------------------------------------------------------------
# S3 objects
# ---------------------------------------------------------------------------


async def _purge_media_objects(
    user_id: str,
    inventory: _Inventory,
    report: PurgeReport,
) -> None:
    semaphore = asyncio.Semaphore(_JOB_CONCURRENCY)

    async def purge_one(job: ProcessingJob) -> Dict[str, int]:
        async with semaphore:
            return await media_purge_service.purge_job_objects(
                job.id,
                transcription_s3_key=job.transcription_s3_key,
                audio_s3_key=job.audio_s3_key,
                summary_s3_key=job.summary_s3_key,
                quiz_s3_key=job.quiz_s3_key,
            )

    for counts in await asyncio.gather(*(purge_one(job) for job in inventory.jobs)):
        report.merge(counts)

    # Share-extension audio is staged outside any job prefix and survives a job
    # that never completed, so it is swept per user rather than per job.
    report.add(
        "audio_objects_deleted",
        await media_purge_service.purge_prefix(
            required_env("AUDIO_BUCKET"), f"shared-audio/{user_id}/"
        ),
    )


async def _purge_bug_report_attachments(
    inventory: _Inventory, report: PurgeReport
) -> None:
    """Delete the screenshots attached to the user's bug reports.

    Requires ``s3:DeleteObject`` on the bug reports bucket, which this task adds
    to the API Lambda policy: apply the Terraform change before deploying, or a
    user who ever filed a report with a screenshot cannot delete their account.
    """
    if not inventory.bug_report_attachment_keys:
        return
    bucket = required_env("BUG_REPORTS_BUCKET")
    for key in sorted(inventory.bug_report_attachment_keys):
        await s3.delete_object(bucket, key)
        report.add("bug_report_attachments_deleted")


# ---------------------------------------------------------------------------
# DynamoDB
# ---------------------------------------------------------------------------


async def _purge_media_watchers(
    user_id: str,
    inventory: _Inventory,
    report: PurgeReport,
) -> None:
    """Remove the user from the watcher rows of every media they submitted.

    ``media_watchers`` is partitioned by ``media_key`` with the user id as sort
    key, so the user's rows are only reachable through the media keys collected
    before the jobs and library rows were deleted.
    """
    if not inventory.media_keys:
        return
    keys = [
        {"media_key": media_key, "user_id": user_id}
        for media_key in sorted(inventory.media_keys)
    ]
    report.add(
        "media_watcher_rows_deleted",
        await _delete_items(required_env("MEDIA_WATCHERS_TABLE"), keys),
    )


async def _purge_processing_jobs(inventory: _Inventory, report: PurgeReport) -> None:
    """Stamp then delete each job row.

    The stamp is not bookkeeping: deleting a job emits a REMOVE event on the
    table stream, and the archiver that consumes it would otherwise write the
    job's payload -- transcript key, title, user id -- into the archive bucket as
    part of erasing it. ``purge_reason`` rides along in the OLD_IMAGE so the
    archiver can tell an erasure from a retention expiry.
    """
    if not inventory.jobs:
        return
    table_name = required_env("PROCESSING_JOBS_TABLE")
    session = database_async.get_session()
    deleted = 0
    async with session.resource(
        "dynamodb",
        region_name=database_async.AWS_REGION,
    ) as dynamodb:
        table = await dynamodb.Table(table_name)
        for job in inventory.jobs:
            await table.update_item(
                Key={"id": job.id},
                UpdateExpression="SET #purge_reason = :reason",
                ExpressionAttributeNames={"#purge_reason": "purge_reason"},
                ExpressionAttributeValues={
                    ":reason": PURGE_REASON_ACCOUNT_DELETION,
                },
            )
            await table.delete_item(Key={"id": job.id})
            deleted += 1
    report.add("processing_job_rows_deleted", deleted)


async def _purge_revenucat_events(user_id: str, report: PurgeReport) -> None:
    """Delete the user's RevenueCat webhook events.

    Keyed by ``event_id`` with no user index, so this is the one filtered scan in
    the purge. The table holds a bounded number of events per environment; a GSI
    exists nowhere in the schema and adding one for a delete-only access pattern
    would be a worse trade.
    """
    table_name = required_env("REVENUCAT_EVENTS_TABLE")
    session = database_async.get_session()
    keys: List[Dict[str, Any]] = []
    async with session.resource(
        "dynamodb",
        region_name=database_async.AWS_REGION,
    ) as dynamodb:
        table = await dynamodb.Table(table_name)
        kwargs: Dict[str, Any] = {
            "FilterExpression": Attr("user_id").eq(user_id),
            "ProjectionExpression": "#pk",
            "ExpressionAttributeNames": {"#pk": "event_id"},
        }
        while True:
            resp = await table.scan(**kwargs)
            for item in resp.get("Items", []):
                keys.append({"event_id": item["event_id"]})
            last_key = resp.get("LastEvaluatedKey")
            if not last_key:
                break
            kwargs["ExclusiveStartKey"] = last_key
    report.add("revenucat_event_rows_deleted", await _delete_items(table_name, keys))


async def _purge_identity(user_id: str, report: PurgeReport) -> None:
    """Sessions, then the user row. Always last.

    Reversing this order produces the exact failure mode AC#6 forbids: an account
    that can no longer authenticate, and therefore can no longer retry its own
    deletion, while its content is still there.
    """
    tokens = await database_async.get_auth_tokens_by_user_id(user_id)
    for token in tokens:
        await database_async.delete_auth_token(token.id)
        report.add("auth_token_rows_deleted")
    # Read before delete only so the audit count stays truthful: DynamoDB reports
    # success for a delete on a key that never existed, so a purge retried after a
    # partial failure would otherwise log an erasure it did not perform. Every
    # other count comes from a query, so this is the only step that needs it.
    existed = (await database_async.get_user_by_id(user_id)) is not None
    await database_async.delete_user(user_id)
    if existed:
        report.add("user_rows_deleted")


async def _query_user_index(
    table_name: str,
    user_id: str,
    *,
    projection: Optional[Sequence[str]] = None,
) -> List[Dict[str, Any]]:
    """Every item of one user on a ``user-index`` GSI, fully paginated."""
    session = database_async.get_session()
    items: List[Dict[str, Any]] = []
    async with session.resource(
        "dynamodb",
        region_name=database_async.AWS_REGION,
    ) as dynamodb:
        table = await dynamodb.Table(table_name)
        kwargs: Dict[str, Any] = {
            "IndexName": USER_INDEX,
            "KeyConditionExpression": Key("user_id").eq(user_id),
        }
        kwargs.update(_projection_kwargs(projection))
        while True:
            resp = await table.query(**kwargs)
            items.extend(resp.get("Items", []))
            last_key = resp.get("LastEvaluatedKey")
            if not last_key:
                break
            kwargs["ExclusiveStartKey"] = last_key
    return items


async def _purge_by_user_index(
    table_name: str,
    user_id: str,
    primary_key: str,
) -> int:
    items = await _query_user_index(table_name, user_id, projection=(primary_key,))
    keys = [{primary_key: item[primary_key]} for item in items if primary_key in item]
    return await _delete_items(table_name, keys)


async def _purge_partition(
    table_name: str,
    user_id: str,
    sort_key: Optional[str],
) -> int:
    """Delete a whole ``user_id`` partition of a table keyed on the user."""
    projection = ("user_id", sort_key) if sort_key else ("user_id",)
    session = database_async.get_session()
    keys: List[Dict[str, Any]] = []
    async with session.resource(
        "dynamodb",
        region_name=database_async.AWS_REGION,
    ) as dynamodb:
        table = await dynamodb.Table(table_name)
        kwargs: Dict[str, Any] = {
            "KeyConditionExpression": Key("user_id").eq(user_id),
        }
        kwargs.update(_projection_kwargs(projection))
        while True:
            resp = await table.query(**kwargs)
            for item in resp.get("Items", []):
                key: Dict[str, Any] = {"user_id": item["user_id"]}
                if sort_key:
                    key[sort_key] = item[sort_key]
                keys.append(key)
            last_key = resp.get("LastEvaluatedKey")
            if not last_key:
                break
            kwargs["ExclusiveStartKey"] = last_key
    return await _delete_items(table_name, keys)


def _projection_kwargs(projection: Optional[Sequence[str]]) -> Dict[str, Any]:
    """Build a ProjectionExpression through name placeholders.

    Always aliased, never inlined: the sort keys in the inventory include
    ``date`` and ``period``, both DynamoDB reserved words, and a raw projection
    on them fails the request instead of the deletion.
    """
    if not projection:
        return {}
    names = {f"#p{index}": attribute for index, attribute in enumerate(projection)}
    return {
        "ProjectionExpression": ", ".join(names.keys()),
        "ExpressionAttributeNames": names,
    }


async def _delete_items(table_name: str, keys: Sequence[Dict[str, Any]]) -> int:
    """Delete a list of primary keys through a single client.

    Item-by-item rather than ``batch_writer``: the volumes here are small, and a
    plain ``delete_item`` is idempotent and gives an exact count, where a batch
    write hides per-item failures in ``UnprocessedItems``.
    """
    if not keys:
        return 0
    session = database_async.get_session()
    deleted = 0
    async with session.resource(
        "dynamodb",
        region_name=database_async.AWS_REGION,
    ) as dynamodb:
        table = await dynamodb.Table(table_name)
        for key in keys:
            await table.delete_item(Key=key)
            deleted += 1
    return deleted
