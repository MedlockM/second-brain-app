"""
Media completed events consumer -- content ledger close, watcher fan-out, indexing.

- Consumes events from EPISODE_COMPLETED_EVENTS_QUEUE (episode-completed-events-<env>)
- Canonical event_type: episode_completion_status (with status: success/failure)
- Closes the global content ledger (media_idempotence): every ingestion path
  publishes here when it finishes, so this is the one place that knows a
  media_key is no longer in flight and can move it to processed/failed. Without
  that write the ledger stays at ``reserved`` and every later save of the same
  URL is parked in ``pending`` for ever (task-390).
- For each media key, fetches watchers and marks their processing state
- In V1, all user notifications are via mobile app polling; email notifications disabled

Search indexing (Algolia) is decoupled from the watcher loop:
- The submitting user (resolved from the event's canonical_job_id) is ALWAYS indexed,
  regardless of whether watchers exist.
- Each watcher is also indexed (for cross-user dedup scenarios).
- Deduplication: a user_id is only indexed once per event, even if they appear both as
  the canonical submitter and as a watcher.
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
from typing import Any, Dict, Optional

from media_summarizer.core.services.search_index_dispatch import (
    enqueue_transcript_indexing,
)
from media_summarizer.utils import media_idempotence, media_watchers, s3, sqs
from media_summarizer.utils.env import required_env
from media_summarizer.utils.logging_config import log_event

logger = logging.getLogger(__name__)

# The MEDIA_COMPLETED_EVENTS_QUEUE alias this consumer used to accept was never
# injected by Terraform, so it only ever resolved through its own fallback.
# task-143 settled EPISODE_COMPLETED_EVENTS_QUEUE as the canonical name shared by
# every producer, and pr.yml guards against the other spelling coming back.
MEDIA_COMPLETED_EVENTS_QUEUE = required_env("EPISODE_COMPLETED_EVENTS_QUEUE")
SUMMARY_BUCKET = required_env("SUMMARY_BUCKET")

# Backoff
TEST_MODE = os.environ.get("TEST_MODE", "false").lower() == "true"
RETRY_DELAY = 0.01 if TEST_MODE else 2


async def _record_content_outcome(
    *,
    media_key: str,
    canonical_job_id: Optional[str],
    processed: bool,
) -> None:
    """Close the global content ledger for this media (task-390).

    This consumer is the single join point every ingestion path publishes to, so
    it is where ``media_idempotence`` learns that the content is done. Nothing
    called this before: the ledger stayed at ``reserved`` for ever, and because
    the submission orchestrator reads it before anything else, every later save
    of the same URL was persisted as ``pending`` and waited on a job that had
    already finished. ``reserved`` now means what it says -- in flight.

    Deliberately not swallowed: a ledger that cannot be closed is the bug this
    call exists to fix, so the event stays on the queue and is redelivered. The
    work below it is idempotent (the same Algolia objectIDs, an already-marked
    watcher, an already-provisioned blurb), so a redelivery costs a repeat, not a
    corruption. A ledger row that simply is not there -- a direct upload, or a
    purged entry -- is not a failure and returns quietly.
    """
    try:
        if processed:
            await media_idempotence.mark_processed(
                media_key=media_key, job_id=canonical_job_id
            )
        else:
            await media_idempotence.mark_failed(
                media_key=media_key, job_id=canonical_job_id
            )
    except Exception as exc:
        log_event(
            logger,
            logging.ERROR,
            "media_idempotence.close_failed",
            "Could not close the content ledger; the event will be redelivered",
            media_key=media_key,
            job_id=canonical_job_id,
            target_status="processed" if processed else "failed",
            error=str(exc),
        )
        raise


async def _trigger_review_blurb(
    *,
    media_item_id: Optional[str],
    user_id: Optional[str],
) -> None:
    """Best-effort queueing of the internal ``review_blurb`` artifact (task-323).

    Called at the same two points as search indexing, for the same reason: this is
    where a media item is known to be readable, and both the submitting user and
    each watcher own a distinct library row that needs its own blurb.

    Swallows everything. The blurb is a convenience on the triage screen; a failure
    here must not stop the SQS message from being deleted and replay the whole
    completion event. The backfill CLI picks up whatever this missed.
    """
    if not media_item_id or not user_id:
        return
    try:
        from media_summarizer.core.services.review_blurb_service import (
            trigger_review_blurb_generation,
        )

        await trigger_review_blurb_generation(user_id, media_item_id)
    except Exception as exc:
        log_event(
            logger,
            logging.WARNING,
            "review_blurb.trigger_failed",
            "Failed to trigger review_blurb generation (non-fatal)",
            media_item_id=media_item_id,
            user_id=user_id,
            error=str(exc),
        )


async def _resume_waiting_artifacts(media_key: str) -> None:
    """Start the generations that were waiting for this media's text (task-360).

    The end of an ingestion is one of the two join points a deferred artifact
    request resumes from. It is keyed on ``media_key``, not on a watcher, because
    that is what a waiting entry names — one call covers every user who saved this
    content and every folder that contains it.

    Swallows everything by contract: the resume service already logs per entry, and
    a completion event must not be replayed because a generation could not start.
    """
    try:
        from media_summarizer.core.services.artifact_wait_service import (
            resume_artifacts_awaiting_media,
        )

        await resume_artifacts_awaiting_media(media_key)
    except Exception as exc:
        log_event(
            logger,
            logging.WARNING,
            "artifact.resume_hook_failed",
            "Failed to resume artifacts waiting for this media (non-fatal)",
            media_key=media_key,
            error=str(exc),
        )


async def _fail_waiting_artifacts(media_key: str, *, reason: str) -> None:
    """End the waits this ingestion will never satisfy (task-360).

    The counterpart of :func:`_resume_waiting_artifacts`, and the reason a wait is
    not a slow failure: an ingestion that failed produces no text ever, so the
    entries expecting it become ``failed`` now instead of spinning until their
    deadline.
    """
    try:
        from media_summarizer.core.services.artifact_service import (
            ERROR_CODE_PREPARATION_FAILED,
        )
        from media_summarizer.core.services.artifact_wait_service import (
            fail_artifacts_awaiting_media,
        )

        await fail_artifacts_awaiting_media(
            media_key,
            error_code=ERROR_CODE_PREPARATION_FAILED,
            error_message=f"The source could not be processed: {reason}",
        )
    except Exception as exc:
        log_event(
            logger,
            logging.WARNING,
            "artifact.fail_hook_failed",
            "Failed to end the artifact waits of a failed ingestion (non-fatal)",
            media_key=media_key,
            error=str(exc),
        )


async def _load_summary_content(summary_s3_key: Optional[str]) -> Optional[Dict[str, Any]]:
    if not summary_s3_key:
        return None
    try:
        raw = await s3.download_file_to_memory(SUMMARY_BUCKET, summary_s3_key)
        try:
            data = json.loads(raw.decode("utf-8"))
        except Exception:
            # Non-JSON fallback
            data = {"summary": raw.decode("utf-8", errors="ignore")}
        # Prefer the inner "summary" field if present
        return data.get("summary", data)
    except Exception as e:
        logger.warning(f"Failed to load summary content {summary_s3_key}: {e}")
        return None


async def process_event(message: Dict[str, Any]) -> None:
    body = json.loads(message.get("Body", "{}"))
    # Accept canonical and legacy event types
    event_type = body.get("event_type")
    if event_type not in ("episode_completion_status", "media_completed", "episode_completed"):
        logger.warning(f"Ignoring unknown event type: {event_type}")
        return

    # Accept both new and legacy field names
    media_key = body.get("media_key") or body.get("episode_guid")
    status = body.get("status", "success")  # legacy events have no status field; treat as success
    media_title = body.get("media_title") or body.get("episode_title")
    summary_s3_key = body.get("summary_s3_key")
    transcription_s3_key = body.get("transcription_s3_key")
    canonical_job_id = body.get("canonical_job_id")

    if not media_key:
        logger.error(f"Missing media_key in event: {body}")
        return

    # Fetch watchers
    watchers = await media_watchers.list_watchers(media_key)
    if not watchers:
        logger.info(f"No watchers for media key {media_key}")

    # Handle failure events: mark all watchers as failed and return early
    if status == "failure":
        # `reason` is what every producer of a failure event publishes: the
        # `CODE:reason_token` pair from `IngestionFailure.reason`. Reading
        # anything else here is how this branch silently logged
        # "upstream_pipeline_failure" for every single failure.
        failure_reason = body.get("reason") or "upstream_pipeline_failure"
        logger.warning(f"Processing failure event for media_key={media_key}: {failure_reason}")
        await _record_content_outcome(
            media_key=media_key,
            canonical_job_id=canonical_job_id,
            processed=False,
        )
        for w in (watchers or []):
            try:
                await media_watchers.mark_watcher_failed(media_key, w.get("user_id"), reason=failure_reason)
            except Exception as e:
                logger.error(f"Failed to mark watcher {w.get('user_id')} as failed: {e}")
        await _fail_waiting_artifacts(media_key, reason=failure_reason)
        return

    # The content is processed. Recording it before anything else is deliberate:
    # a save landing while this event is being handled reads the ledger first,
    # and it must find "processed" rather than a reservation it would wait on.
    await _record_content_outcome(
        media_key=media_key,
        canonical_job_id=canonical_job_id,
        processed=True,
    )

    # -------------------------------------------------------------------------
    # Primary-user search indexing (decoupled from watcher loop)
    # -------------------------------------------------------------------------
    # The canonical_job_id identifies the processing job that produced this
    # completion event. Its user_id is the submitting user who must always be
    # indexed, regardless of whether watchers exist.
    indexed_user_ids: set = set()

    from media_summarizer.utils import database_async

    canonical_job = None
    if canonical_job_id:
        try:
            canonical_job = await database_async.get_processing_job_by_id(canonical_job_id)
        except Exception as e:
            logger.error(f"Failed to load canonical job {canonical_job_id}: {e}")

    if canonical_job and canonical_job.user_id:
        await enqueue_transcript_indexing(
            media_item_id=canonical_job.media_item_id or canonical_job_id,
            job_id=canonical_job_id,
            user_id=canonical_job.user_id,
            transcription_s3_key=transcription_s3_key,
            title=canonical_job.title or media_title,
            creator_name=canonical_job.creator_name,
            source_platform=canonical_job.source_platform,
        )
        # Only the durable library id will do here: the blurb is written onto the
        # user_media row, and the job id fallback used for Algolia is not a library
        # key.
        await _trigger_review_blurb(
            media_item_id=canonical_job.media_item_id,
            user_id=canonical_job.user_id,
        )
        indexed_user_ids.add(canonical_job.user_id)
    elif not canonical_job_id:
        log_event(
            logger,
            logging.WARNING,
            "search_indexing.no_canonical_job_id",
            "Event has no canonical_job_id; cannot resolve primary user for indexing",
            media_key=media_key,
        )

    # -------------------------------------------------------------------------
    # Watcher fan-out
    # -------------------------------------------------------------------------
    if not watchers:
        # No watcher does not mean no waiting artifact: the entry hangs off the
        # library row, not off the watcher table.
        await _resume_waiting_artifacts(media_key)
        return

    # Fan-out
    for w in watchers:
        try:
            job_id = w.get("job_id")
            job = None

            # Update processing job with S3 keys and status BEFORE sending email
            try:
                job = await database_async.get_processing_job_by_id(job_id)
                if job:
                    if summary_s3_key:
                        job.set_summary_location(summary_s3_key)


                    job.mark_completed()
                    await database_async.update_processing_job(job)
                    logger.info(f"Updated processing job {job_id} with S3 keys")
            except Exception as e:
                logger.error(f"Failed to update processing job {job_id}: {e}")

            # Mark watcher as processed (for deduplication; notifications via mobile polling in V1)
            try:
                await media_watchers.mark_watcher_processed(media_key, w.get("user_id"))
                logger.info(f"Marked watcher {w.get('user_id')} as processed for media key {media_key}")
            except Exception as mark_error:
                logger.error(f"Failed to mark watcher processed for {w.get('user_id')} on {media_key}: {mark_error}")
                await media_watchers.mark_watcher_failed(
                    media_key,
                    w.get("user_id"),
                    reason=f"mark_processed_failed: {str(mark_error)}"
                )
                continue

            logger.info(f"Successfully processed watcher {w.get('user_id')} for media key {media_key}")

            # Per-watcher Algolia indexing (cross-user dedup). Deduplicate
            # against the primary user who was already indexed above.
            watcher_user_id = (getattr(job, "user_id", None) if job else None) or w.get("user_id")
            if watcher_user_id and watcher_user_id not in indexed_user_ids:
                await enqueue_transcript_indexing(
                    media_item_id=(
                        getattr(job, "media_item_id", None) if job else None
                    )
                    or job_id,
                    job_id=job_id,
                    user_id=watcher_user_id,
                    transcription_s3_key=transcription_s3_key,
                    title=(getattr(job, "title", None) if job else None) or media_title,
                    creator_name=(
                        getattr(job, "creator_name", None) if job else None
                    ),
                    source_platform=(getattr(job, "source_platform", None) if job else None),
                )
                # Not a retry of the call above: this is the fan-out over the other
                # users watching the same content, and each of them owns a separate
                # library row with its own blurb to write.
                await _trigger_review_blurb(
                    media_item_id=(
                        getattr(job, "media_item_id", None) if job else None
                    ),
                    user_id=watcher_user_id,
                )
                indexed_user_ids.add(watcher_user_id)

        except Exception as e:
            logger.error(f"Error processing watcher {w.get('user_id')} for {media_key}: {e}")
            try:
                await media_watchers.mark_watcher_failed(media_key, w.get("user_id"), reason=str(e))
            except Exception:
                pass

    # Last, and after the loop on purpose: the resume re-resolves the scope, which
    # reads the jobs this loop has just marked completed.
    await _resume_waiting_artifacts(media_key)


async def poll_queue() -> None:
    log_event(
        logger,
        logging.INFO,
        "worker.started",
        "Starting media-completed-events consumer",
        queue=MEDIA_COMPLETED_EVENTS_QUEUE,
    )
    while True:
        try:
            messages = await sqs.receive_messages(
                queue_name=MEDIA_COMPLETED_EVENTS_QUEUE,
                max_messages=10,
                wait_time_seconds=20,
            )
            if messages:
                for m in messages:
                    try:
                        await process_event(m)
                        rh = m.get("ReceiptHandle")
                        if rh:
                            await sqs.delete_message(queue_name=MEDIA_COMPLETED_EVENTS_QUEUE, receipt_handle=rh)
                    except Exception as e:
                        logger.error(f"Failed to process event: {e}")
            await asyncio.sleep(1)
        except Exception as e:
            logger.error(f"Polling error: {e}")
            await asyncio.sleep(RETRY_DELAY)


async def main() -> None:
    await poll_queue()


if __name__ == "__main__":
    from media_summarizer.utils.logging_config import setup_logging as _setup_logging
    _setup_logging("worker-episode-completed")
    asyncio.run(main())
