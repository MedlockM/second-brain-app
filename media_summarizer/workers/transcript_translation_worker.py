"""
Transcript translation worker -- translates transcripts asynchronously via SQS.

Consumes messages from TRANSCRIPT_TRANSLATION_QUEUE containing:
- transcript_s3_key: S3 key of the original transcript to translate
- target_language: ISO 639-1 language code to translate into
- source_language_hint: (optional) reliable source-provided language tag
- source: (optional) source platform name for logging
- job_id: (optional) processing job ID for logging context

State machine integration (task-203):
- On start: marks status queued -> in_progress
- On success: marks status -> done
- On terminal failure: marks status -> failed (re-authorizes future attempts)

The worker atomically claims a translation using the SQS message ID. Duplicate
messages are rejected, retries of the same message may resume, and the S3 cache
still prevents re-translating an already completed transcript.

Unlike the /raw-content endpoint (constrained by API Gateway's 30s timeout),
this Lambda is triggered by SQS with no Gateway timeout, allowing translations
of any length to complete.
"""

from __future__ import annotations

import json
import logging
import time
from typing import Any, Dict

from media_summarizer.core.services.transcript_translation import (
    TRANSCRIPT_BUCKET,
    TranscriptTranslationError,
    ensure_translated_transcript,
    persist_detected_language,
)
from media_summarizer.utils import database_async, s3
from media_summarizer.utils.env import required_env
from media_summarizer.utils.llm_failures import log_llm_generation_failure
from media_summarizer.utils.logging_config import (
    bind_log_context,
    log_event,
    reset_log_context,
)
from media_summarizer.utils.translation_idempotence import (
    mark_translation_done,
    mark_translation_failed,
    mark_translation_in_progress,
)

logger = logging.getLogger(__name__)

TRANSCRIPT_TRANSLATION_QUEUE = required_env("TRANSCRIPT_TRANSLATION_QUEUE")


async def process_message(message: Dict[str, Any]) -> None:
    """
    Process a single transcript translation message.

    Downloads the original transcript from S3 and translates it to the
    target language using ensure_translated_transcript (idempotent).

    State transitions (task-203):
    - queued -> in_progress (on worker start)
    - in_progress -> done (on successful translation or cache hit)
    - in_progress -> failed (on terminal error after retries exhausted)
    """
    body = json.loads(message.get("Body", "{}"))

    transcript_s3_key = body.get("transcript_s3_key")
    target_language = body.get("target_language")
    source_language_hint = body.get("source_language_hint")
    source = body.get("source")
    job_id = body.get("job_id")
    worker_owner_id = message.get("MessageId")

    token = bind_log_context(
        job_id=job_id,
        worker="transcript_translation",
    )

    try:
        if (
            not transcript_s3_key
            or not target_language
            or not isinstance(worker_owner_id, str)
            or not worker_owner_id
        ):
            log_event(
                logger,
                logging.ERROR,
                "worker.invalid_message",
                "Missing required fields in transcript translation message",
                transcript_s3_key=transcript_s3_key,
                target_language=target_language,
                has_message_id=bool(worker_owner_id),
            )
            # Don't retry invalid messages -- let them fall through
            return

        started = time.monotonic()

        # --- State transition: queued -> in_progress ---
        owns_translation = await mark_translation_in_progress(
            transcript_s3_key=transcript_s3_key,
            target_language=target_language,
            worker_owner_id=worker_owner_id,
        )
        if not owns_translation:
            log_event(
                logger,
                logging.INFO,
                "worker.translation_duplicate_skipped",
                "Translation is already owned by another worker message",
                transcript_s3_key=transcript_s3_key,
                target_language=target_language,
                worker_owner_id=worker_owner_id,
            )
            return

        log_event(
            logger,
            logging.INFO,
            "worker.translation_started",
            "Transcript translation worker processing message",
            transcript_s3_key=transcript_s3_key,
            target_language=target_language,
            source=source,
            source_language_hint=source_language_hint,
        )

        # Download the original transcript text from S3
        try:
            raw_bytes = await s3.download_file_to_memory(
                bucket=TRANSCRIPT_BUCKET,
                key=transcript_s3_key,
            )
        except Exception as exc:
            log_event(
                logger,
                logging.ERROR,
                "worker.s3_download_failed",
                "Failed to download transcript from S3",
                transcript_s3_key=transcript_s3_key,
                error_type=type(exc).__name__,
                detail=str(exc)[:300],
            )
            # Mark failed -- S3 download failure is terminal for this message
            await mark_translation_failed(
                transcript_s3_key=transcript_s3_key,
                target_language=target_language,
                error_message=f"s3_download_failed: {type(exc).__name__}: {str(exc)[:200]}",
            )
            raise

        if not raw_bytes or not raw_bytes.strip():
            log_event(
                logger,
                logging.WARNING,
                "worker.empty_transcript",
                "Transcript is empty; skipping translation",
                transcript_s3_key=transcript_s3_key,
            )
            # Mark as done -- there's nothing to translate
            await mark_translation_done(
                transcript_s3_key=transcript_s3_key,
                target_language=target_language,
            )
            return

        transcript_text = raw_bytes.decode("utf-8")

        # Run the idempotent detect+translate step.
        # If the translation already exists in S3, this is a no-op (cache hit).
        try:
            outcome = await ensure_translated_transcript(
                transcript_s3_key=transcript_s3_key,
                transcript_text=transcript_text,
                target_language=target_language,
                source=source,
                source_language_hint=source_language_hint,
                transcript_bucket=TRANSCRIPT_BUCKET,
                translation_owner_id=worker_owner_id,
            )
        except TranscriptTranslationError as exc:
            # Terminal translation failure after retries exhausted
            log_event(
                logger,
                logging.ERROR,
                "worker.translation_terminal_failure",
                "Translation failed terminally",
                transcript_s3_key=transcript_s3_key,
                target_language=target_language,
                error_type=type(exc).__name__,
                detail=str(exc)[:300],
            )
            log_llm_generation_failure(
                logger,
                worker="transcript_translation",
                exc=exc,
                transcript_s3_key=transcript_s3_key,
                target_language=target_language,
            )
            await mark_translation_failed(
                transcript_s3_key=transcript_s3_key,
                target_language=target_language,
                error_message=str(exc)[:300],
            )
            # Do NOT re-raise: the message should not be retried by SQS since
            # the internal retry logic already exhausted attempts.
            return
        except Exception as exc:
            # Unexpected error -- let SQS retry via visibility timeout
            log_event(
                logger,
                logging.ERROR,
                "worker.translation_unexpected_error",
                "Unexpected error during translation",
                transcript_s3_key=transcript_s3_key,
                target_language=target_language,
                error_type=type(exc).__name__,
                detail=str(exc)[:300],
            )
            log_llm_generation_failure(
                logger,
                worker="transcript_translation",
                exc=exc,
                transcript_s3_key=transcript_s3_key,
                target_language=target_language,
            )
            # Mark failed so the state machine knows this attempt is done
            await mark_translation_failed(
                transcript_s3_key=transcript_s3_key,
                target_language=target_language,
                error_message=f"unexpected: {type(exc).__name__}: {str(exc)[:200]}",
            )
            raise

        if outcome.translation_failed:
            await mark_translation_failed(
                transcript_s3_key=transcript_s3_key,
                target_language=target_language,
                error_message=outcome.translation_error or "translation_failed",
            )
            log_event(
                logger,
                logging.ERROR,
                "worker.translation_terminal_failure",
                "Translation failed after internal retries",
                transcript_s3_key=transcript_s3_key,
                target_language=target_language,
                detail=(outcome.translation_error or "translation_failed")[:300],
            )
            # The blind spot this event exists for: the service swallowed the
            # failure and returned normally, so this invocation is a success for
            # Lambda -- no Errors datapoint, no DLQ message, nothing for
            # lambda_error_rate to see (see utils/llm_failures.py).
            log_llm_generation_failure(
                logger,
                worker="transcript_translation",
                refusal_reason=outcome.translation_refusal_reason,
                detail=(outcome.translation_error or "translation_failed")[:300],
                transcript_s3_key=transcript_s3_key,
                target_language=target_language,
            )
            return

        # --- State transition: in_progress -> done ---
        await mark_translation_done(
            transcript_s3_key=transcript_s3_key,
            target_language=target_language,
        )

        # --- Persist detected language on the job (AC#2, moved from prewarm) ---
        if job_id and outcome.detected_language:
            try:
                job = await database_async.get_processing_job_by_id(job_id)
                if job:
                    await persist_detected_language(job, outcome.detected_language)
            except Exception as exc:
                # Non-fatal: language persistence is best-effort
                log_event(
                    logger,
                    logging.WARNING,
                    "worker.persist_language_failed",
                    "Failed to persist detected_language on job (non-fatal)",
                    job_id=job_id,
                    detected_language=outcome.detected_language,
                    error_type=type(exc).__name__,
                    detail=str(exc)[:200],
                )

        duration_ms = int((time.monotonic() - started) * 1000)

        log_event(
            logger,
            logging.INFO,
            "worker.translation_completed",
            "Transcript translation worker finished",
            transcript_s3_key=transcript_s3_key,
            target_language=target_language,
            source=source,
            detected_language=outcome.detected_language,
            detection_method=outcome.detection_method,
            is_translated=outcome.is_translated,
            translation_failed=outcome.translation_failed,
            duration_ms=duration_ms,
        )

    finally:
        reset_log_context(token)
