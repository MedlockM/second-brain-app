"""Shared job/SQS orchestration around the non-blocking Apify adapter."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from media_summarizer.core.models.processing_job import ProcessingJob
from media_summarizer.infrastructure import apify_adapter
from media_summarizer.infrastructure.apify_adapter import ApifyActorKind, ApifyRun
from media_summarizer.utils import database_async, sqs

ACTIVE_APIFY_STATES = frozenset({"waiting", "processing"})


async def _schedule_backstop(
    *,
    job: ProcessingJob,
    queue_name: str,
) -> None:
    context = dict(job.apify_context or {})
    await sqs.send_message(
        queue_name=queue_name,
        message_body={
            **context,
            "message_type": "apify_backstop",
            "job_id": job.id,
            "apify_run_id": job.apify_run_id,
        },
        delay_seconds=apify_adapter.APIFY_BACKSTOP_DELAY_SECONDS,
    )
    updated = await database_async.mark_apify_backstop_scheduled(job.id, job.apify_run_id or "")
    if updated:
        job.apify_backstop_scheduled = True


async def start_run_for_job(
    *,
    job: ProcessingJob,
    kind: ApifyActorKind,
    source_platform: str,
    input_data: dict[str, Any],
    queue_name: str,
    context: dict[str, Any],
    replace_active_run: bool = False,
) -> ApifyRun:
    """Start, persist, and arm one run before the worker invocation returns."""
    if not replace_active_run and job.apify_run_id and job.apify_dataset_id and job.apify_state in ACTIVE_APIFY_STATES:
        if not job.apify_backstop_scheduled:
            await _schedule_backstop(job=job, queue_name=queue_name)
        return ApifyRun(
            run_id=job.apify_run_id,
            dataset_id=job.apify_dataset_id,
            actor_id=job.apify_actor_id or "",
        )

    run = await apify_adapter.start_actor_run(
        kind=kind,
        input_data=input_data,
        job_id=job.id,
        source_platform=source_platform,
    )
    now = datetime.now(timezone.utc)
    job.apify_run_id = run.run_id
    job.apify_dataset_id = run.dataset_id
    job.apify_actor_id = run.actor_id
    job.apify_actor_kind = kind.value
    job.apify_source_platform = source_platform
    job.apify_state = "waiting"
    job.apify_context = dict(context)
    job.apify_backstop_scheduled = False
    job.apify_started_at = now
    job.apify_claimed_at = None
    job.apify_completed_at = None
    job.touch()
    await database_async.persist_apify_run(job)
    await _schedule_backstop(job=job, queue_name=queue_name)
    return run


async def claim_callback(job_id: str, run_id: str) -> ProcessingJob | None:
    return await database_async.claim_apify_callback(job_id, run_id)


async def complete_callback(job: ProcessingJob) -> bool:
    return await database_async.complete_apify_callback(job)


async def expire_backstop(
    *,
    job_id: str,
    run_id: str,
    source_platform: str,
) -> ProcessingJob | None:
    return await database_async.expire_apify_run(
        job_id,
        run_id,
        error_message=(f"{source_platform.title()} extraction timed out waiting for Apify."),
        error_step=f"{source_platform}_ingestion",
    )
