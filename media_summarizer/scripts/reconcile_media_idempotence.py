"""Close the ledger rows stranded at ``reserved`` before task-390.

Nothing ever called ``media_idempotence.mark_processed``, so every content ever
submitted kept a ``reserved`` row, and the submission orchestrator -- which reads
that ledger before anything else -- resolved every re-save of an already
processed URL as ``pending``: no job to wait for, no transcript, no search
result. The fix closes the ledger from the completion path, but it does not
retrofit rows written before it, and those rows are exactly the ones a user hits
by re-saving something they saved months ago.

This walks the ledger and, for each ``reserved`` row, asks the job it points at
what really happened:

- job ``completed``  -> the content is processed. The row is advanced.
- job ``failed`` / ``cancelled`` -> the row is marked failed; there is no
  transcript and no worker is going to produce one.
- job still in flight -> left alone. ``reserved`` is then telling the truth.
- job **gone** (the ``processing_jobs`` TTL swept it) -> left alone, and
  reported. Advancing it would claim a transcript that nothing can resolve any
  more: the S3 key lived on the job row that expired. Those contents need a
  fresh ingestion, which is a separate decision from this reconciliation.

Usage:
  uv run python -m media_summarizer.scripts.reconcile_media_idempotence

Dry run by default -- every row is inspected and counted, nothing is written.
Set ``MEDIA_IDEMPOTENCE_RECONCILE_APPLY=true`` to perform the writes. Re-running
is safe and cheap: rows already closed are no longer ``reserved`` and are
skipped.
"""

from __future__ import annotations

import asyncio
import logging
import os
from collections import Counter
from typing import Any, Dict, List

from media_summarizer.core.models.processing_job import JobStatus
from media_summarizer.utils import database_async, media_idempotence

logger = logging.getLogger(__name__)

APPLY = os.environ.get("MEDIA_IDEMPOTENCE_RECONCILE_APPLY", "false").lower() == "true"


async def _scan_ledger() -> List[Dict[str, Any]]:
    """Every ledger row. A global content ledger at V1 scale is a small table."""
    session = database_async.get_session()
    rows: List[Dict[str, Any]] = []
    async with session.resource(
        "dynamodb", region_name=database_async.AWS_REGION
    ) as dynamodb:
        table = await dynamodb.Table(media_idempotence.MEDIA_IDEMPOTENCE_TABLE)
        scan_kwargs: Dict[str, Any] = {}
        while True:
            resp = await table.scan(**scan_kwargs)
            rows.extend(resp.get("Items", []))
            last_key = resp.get("LastEvaluatedKey")
            if not last_key:
                break
            scan_kwargs["ExclusiveStartKey"] = last_key
    return rows


async def reconcile() -> Counter:
    outcomes: Counter = Counter()

    for row in await _scan_ledger():
        media_key = str(row.get("media_key") or "")
        status = str(row.get("status") or "").lower().strip()
        job_id = str(row.get("job_id") or "")

        if status != "reserved":
            outcomes[f"skipped_status_{status or 'unknown'}"] += 1
            continue
        if not job_id:
            outcomes["skipped_no_job_id"] += 1
            print(f"{media_key}: reserved with no job id, left alone")
            continue

        job = await database_async.get_processing_job_by_id(job_id)
        if job is None:
            outcomes["job_missing"] += 1
            print(f"{media_key}: job {job_id} no longer exists, left alone")
            continue

        if job.status == JobStatus.COMPLETED:
            target = "processed"
        elif job.status in (JobStatus.FAILED, JobStatus.CANCELLED):
            target = "failed"
        else:
            outcomes[f"in_flight_{job.status.value}"] += 1
            print(f"{media_key}: job {job_id} is {job.status.value}, left alone")
            continue

        if not APPLY:
            outcomes[f"would_mark_{target}"] += 1
            print(f"{media_key}: would mark {target} (job {job_id} {job.status.value})")
            continue

        if target == "processed":
            moved = await media_idempotence.mark_processed(
                media_key=media_key, job_id=job_id
            )
        else:
            moved = await media_idempotence.mark_failed(
                media_key=media_key, job_id=job_id
            )
        outcomes[f"marked_{target}" if moved else f"refused_{target}"] += 1
        print(f"{media_key}: {'marked' if moved else 'refused'} {target}")

    return outcomes


async def _run() -> None:
    outcomes = await reconcile()
    mode = "APPLY" if APPLY else "DRY RUN"
    print(f"\nmedia_idempotence reconciliation ({mode}):")
    for key in sorted(outcomes):
        print(f"  {key}: {outcomes[key]}")
    if not APPLY:
        print(
            "\nNothing was written. Re-run with "
            "MEDIA_IDEMPOTENCE_RECONCILE_APPLY=true to apply."
        )


def main() -> None:
    from media_summarizer.utils.logging_config import setup_logging

    setup_logging("reconcile-media-idempotence")
    asyncio.run(_run())


if __name__ == "__main__":
    main()
