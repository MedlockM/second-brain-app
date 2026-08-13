"""
Shared audio quota gate for every producer that enqueues a Deepgram
transcription (task-250 Layer 1).

The producer that resolves the audio URL is the last place where a job can still
be refused *before* spending provider minutes. This module holds the sequence
they all need — establish the duration, ask the quota engine, debit once, fail
the job cleanly on refusal — so no producer drifts from it. Both the resolution
workers and the ingestion orchestrator use it.

The contract with the transcription worker is the `quota_debited_minutes` field
in the SQS payload: whatever this gate debited must be forwarded, so the
settlement in `deepgram_worker` only applies the difference with the duration
Deepgram actually billed.
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from typing import Any, Optional

from media_summarizer.core.services import audio_duration_probe, quota_enforcer
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
    message: Optional[str] = None

    @property
    def failure_message(self) -> str:
        """Job error message that `user_facing_errors` can map to a real string.

        The stable error code has to appear verbatim in the message: that is what
        the user-facing translation layer keys on.
        """
        return f"{self.error_code}: {self.message or 'Quota exceeded'}"


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
    source_platform: str = quota_enforcer.QUOTA_PLATFORM_AUDIO,
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
    """
    if not user_id:
        log_event(
            logger,
            logging.WARNING,
            "quota.gate_skipped_no_user",
            "No user_id available for the audio quota gate; submission allowed",
            job_id=job_id,
            source_platform=source_platform,
        )
        return AudioGateDecision(allowed=True)

    duration_seconds = await resolve_audio_duration_seconds(
        known_duration_seconds=known_duration_seconds,
        audio_bytes=audio_bytes,
        audio_url=audio_url,
        probe_budget_seconds=probe_budget_seconds,
    )

    gate = await quota_enforcer.gate_audio_submission(
        user_id=user_id,
        job_id=job_id,
        duration_seconds=duration_seconds,
        source_platform=source_platform,
    )

    if gate.allowed:
        log_event(
            logger,
            logging.INFO,
            "quota.audio_gate_passed",
            "Audio quota gate passed",
            job_id=job_id,
            user_id=user_id,
            source_platform=source_platform,
            duration_seconds=duration_seconds,
            debited_minutes=gate.debited_minutes,
            provisional=gate.provisional,
        )
        return AudioGateDecision(
            allowed=True,
            debited_minutes=gate.debited_minutes,
            duration_seconds=duration_seconds,
        )

    decision = AudioGateDecision(
        allowed=False,
        duration_seconds=duration_seconds,
        error_code=gate.error_code,
        message=gate.message,
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
            reason=gate.error_code or "tier_quota_exceeded",
        )

    return decision
