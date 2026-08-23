"""
Shared gate for every producer that enqueues a transcription (task-250 Layer 1).

The producer that resolves the audio URL is the last place where a job can still
be refused *before* spending provider minutes, and — since the meter follows the
provider call rather than the URL — it is also the only place allowed to charge
them. Whatever the media came from (a podcast feed, a YouTube video with no
captions, a TikTok, an Instagram reel, an uploaded file), if it is about to be
transcribed it goes through here and it is charged its real length. This module
holds the sequence they all need — establish the duration, ask the enforcer, debit
once, fail the job cleanly on refusal — so no producer drifts from it.

The contract with the transcription worker is the `quota_debited_minutes` field
in the SQS payload: whatever this gate debited must be forwarded, so the
settlement in `deepgram_worker` only applies the difference with the duration
Deepgram actually billed.

Since task-281 the gate also answers a question that comes *before* the quota
engine: does this user already hold this content? A media already in their
library -- any folder, any collection -- costs them nothing to file again, so the
gate runs its check as usual and skips only the debit, saying so through
`AudioGateDecision.debit_skipped`. Producers forward that as
`quota_debit_skipped` in the SQS payload, which is the second half of the
contract: without it the settlement would see `quota_debited_minutes == 0` and
charge the whole real duration, undoing the exemption.
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from typing import Any, Optional

from media_summarizer.core.services import audio_duration_probe, quota_enforcer
from media_summarizer.core.services.durable_media_service import user_holds_media
from media_summarizer.utils import database_async, sqs
from media_summarizer.utils.logging_config import log_event

logger = logging.getLogger(__name__)


@dataclass
class AudioGateDecision:
    """What the gate decided, and what the producer must forward downstream."""

    allowed: bool
    debited_minutes: int = 0
    duration_seconds: int = 0
    error_code: Optional[str] = None
    # True when the submission was let through without touching the counters
    # because the user already holds this content (task-281). Distinct from
    # `debited_minutes == 0`, which a real debit of zero could also produce, and
    # the only thing that tells the settlement to stand down.
    debit_skipped: bool = False

    @property
    def failure_message(self) -> str:
        """What the user reads on the item that could not be processed.

        One fixed sentence, with no figures in it. The gate runs in a worker,
        long after the request that produced the item is over, and what it
        writes lands in `ProcessingJob.error_message` — a free-text column the
        app renders as-is, in whatever language it was written in. Since the
        refusal figures now travel typed on the synchronous path (see
        `QuotaCheckResult`), spelling them out here would be the one place left
        putting an English sentence with numbers in front of a reader who asked
        for another language.
        """
        return "This import could not be processed."


async def resolve_audio_duration_seconds(
    *,
    known_duration_seconds: int = 0,
    audio_bytes: Optional[bytes] = None,
    audio_url: Optional[str] = None,
    probe_budget_seconds: float = audio_duration_probe.DEFAULT_PROBE_BUDGET_SECONDS,
) -> int:
    """Best available duration for a submission, or 0 when unobtainable.

    Cheapest source first: a duration the platform already told us (feed
    metadata, extractor output), then the local bytes, then an HTTP Range probe
    on the remote URL. Returning 0 is a valid answer and means "accept anyway,
    debit provisionally, let the settlement fix it".
    """
    if known_duration_seconds and known_duration_seconds > 0:
        return int(known_duration_seconds)

    if audio_bytes:
        local = audio_duration_probe.probe_duration_seconds_from_bytes(audio_bytes)
        if local:
            return local

    if audio_url:
        remote = await audio_duration_probe.probe_duration_seconds_from_url(
            audio_url, budget_seconds=probe_budget_seconds
        )
        if remote:
            return remote

    return 0


async def _publish_quota_failure_event(
    *,
    job_id: str,
    media_key: Optional[str],
    reason: str,
) -> None:
    """Tell the completion pipeline the job is over, so clients stop waiting.

    Best effort: the auto-poll worker has no events queue configured and nobody
    is waiting on a screen for those items.
    """
    queue_name = os.environ.get("EPISODE_COMPLETED_EVENTS_QUEUE")
    if not queue_name:
        return
    try:
        await sqs.send_message(
            queue_name=queue_name,
            message_body={
                "event_type": "episode_completion_status",
                "status": "failure",
                "media_key": media_key,
                "canonical_job_id": job_id,
                "reason": reason,
            },
        )
    except Exception as exc:
        log_event(
            logger,
            logging.WARNING,
            "event.publish_failed",
            "Failed to publish quota failure event",
            job_id=job_id,
            media_key=media_key,
            exc_info=exc,
        )


async def gate_audio_transcription(
    *,
    job_id: str,
    user_id: Optional[str],
    job: Any = None,
    media_key: Optional[str] = None,
    audio_url: Optional[str] = None,
    audio_bytes: Optional[bytes] = None,
    known_duration_seconds: int = 0,
    media_item_id: Optional[str] = None,
    error_step: str = "quota_enforcement",
    probe_budget_seconds: float = audio_duration_probe.DEFAULT_PROBE_BUDGET_SECONDS,
    mark_job_failed: bool = True,
) -> AudioGateDecision:
    """Check the audio quota and debit it once, right before a Deepgram enqueue.

    On refusal the job is marked failed with the stable quota error code and a
    failure event is published, so the caller only has to return without
    enqueueing.

    Without a `user_id` there is nobody to charge and nobody to protect: the
    submission is let through and the anomaly is logged, rather than dropped.

    `media_item_id` identifies the library row of *this* save, which is written
    before the gate runs; it is excluded from the already-held lookup so a save
    cannot find itself and exempt itself. It defaults to the pointer the job
    already carries, so every existing producer gets the check for free.
    """
    source_platform = getattr(job, "source_platform", None)

    if not user_id:
        log_event(
            logger,
            logging.WARNING,
            "quota.gate_skipped_no_user",
            "No user_id available for the transcription gate; submission allowed",
            job_id=job_id,
            source_platform=source_platform,
        )
        return AudioGateDecision(allowed=True)

    # The question that decides whether this save costs the user anything
    # (task-281): a media already in their library -- any folder, any collection
    # -- is free to file again. Per user and per content, and deliberately
    # unrelated to the global idempotence reservation, which keeps answering the
    # other question, whether the pipeline still has work to do.
    current_media_item_id = media_item_id or getattr(job, "media_item_id", None)
    already_held = bool(media_key) and await user_holds_media(
        user_id=user_id,
        media_key=media_key or "",
        exclude_media_item_id=current_media_item_id,
    )

    duration_seconds = await resolve_audio_duration_seconds(
        known_duration_seconds=known_duration_seconds,
        audio_bytes=audio_bytes,
        audio_url=audio_url,
        probe_budget_seconds=probe_budget_seconds,
    )

    # The check still runs for a free save. Free means the user is not charged,
    # not that the pipeline below is free to spend an unbounded number of
    # provider minutes for someone already out of them: this gate is the last
    # point where that spend can still be refused.
    gate = await quota_enforcer.gate_transcription(
        user_id=user_id,
        job_id=job_id,
        duration_seconds=duration_seconds,
        debit=not already_held,
    )

    if gate.allowed:
        log_event(
            logger,
            logging.INFO,
            "quota.audio_gate_already_held" if already_held else "quota.audio_gate_passed",
            "User already holds this media; the save is free"
            if already_held
            else "Audio quota gate passed",
            job_id=job_id,
            user_id=user_id,
            media_key=media_key,
            media_item_id=current_media_item_id,
            source_platform=source_platform,
            duration_seconds=duration_seconds,
            debited_minutes=gate.debited_minutes,
            provisional=gate.provisional,
        )
        return AudioGateDecision(
            allowed=True,
            debited_minutes=gate.debited_minutes,
            duration_seconds=duration_seconds,
            debit_skipped=already_held,
        )

    decision = AudioGateDecision(
        allowed=False,
        duration_seconds=duration_seconds,
        error_code=gate.error_code,
    )

    log_event(
        logger,
        logging.INFO,
        "quota.audio_gate_refused",
        "Audio quota gate refused the submission before any provider spend",
        job_id=job_id,
        user_id=user_id,
        source_platform=source_platform,
        duration_seconds=duration_seconds,
        error_code=gate.error_code,
    )

    if mark_job_failed:
        try:
            target_job = job or await database_async.get_processing_job_by_id(job_id)
            if target_job:
                target_job.mark_failed(
                    error_message=decision.failure_message,
                    error_step=error_step,
                )
                await database_async.update_processing_job(target_job)
        except Exception as exc:
            log_event(
                logger,
                logging.WARNING,
                "quota.gate_job_update_failed",
                "Could not mark the job failed after a quota refusal",
                job_id=job_id,
                exc_info=exc,
            )
        await _publish_quota_failure_event(
            job_id=job_id,
            media_key=media_key,
            reason=gate.error_code or quota_enforcer.ERROR_OUT_OF_MINUTES,
        )

    return decision
