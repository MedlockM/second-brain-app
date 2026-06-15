"""
Transcript translation worker -- translates transcripts asynchronously via SQS.

Consumes messages from TRANSCRIPT_TRANSLATION_QUEUE containing:
- transcript_s3_key: S3 key of the original transcript to translate
- target_language: ISO 639-1 language code to translate into
- source_language_hint: (optional) reliable source-provided language tag
- source: (optional) source platform name for logging
- job_id: (optional) processing job ID for logging context

This worker is the async safety net for /raw-content cache misses (task-200).
The prewarm from task-192 keeps S3 warm in the majority of cases; this worker
handles the rare case where the prewarm did not finish in time or was skipped.

The worker calls ensure_translated_transcript which is fully idempotent:
duplicate messages for the same (transcript_s3_key, target_language) couple
will short-circuit on the S3 object_exists check and not re-translate.

Unlike the /raw-content endpoint (constrained by API Gateway's 30s timeout),
this Lambda is triggered by SQS with no Gateway timeout, allowing translations
of any length to complete.
"""

from __future__ import annotations

import json
import logging
import os
import time
from typing import Any, Dict, Optional

from media_summarizer.core.services.transcript_translation import (
    ensure_translated_transcript,
    TRANSCRIPT_BUCKET,
)
from media_summarizer.utils import s3
from media_summarizer.utils.logging_config import (
    bind_log_context,
    log_event,
    reset_log_context,
)

logger = logging.getLogger(__name__)

TRANSCRIPT_TRANSLATION_QUEUE = os.environ.get(
    "TRANSCRIPT_TRANSLATION_QUEUE", "transcript-translation-queue"
)


async def process_message(message: Dict[str, Any]) -> None:
    """
    Process a single transcript translation message.

    Downloads the original transcript from S3 and translates it to the
    target language using ensure_translated_transcript (idempotent).
    """
    body = json.loads(message.get("Body", "{}"))

    transcript_s3_key = body.get("transcript_s3_key")
    target_language = body.get("target_language")
    source_language_hint = body.get("source_language_hint")
    source = body.get("source")
    job_id = body.get("job_id")

    token = bind_log_context(
        job_id=job_id,
        worker="transcript_translation",
    )

    try:
        if not transcript_s3_key or not target_language:
            log_event(
                logger,
                logging.ERROR,
                "worker.invalid_message",
                "Missing required fields in transcript translation message",
                transcript_s3_key=transcript_s3_key,
                target_language=target_language,
            )
            # Don't retry invalid messages -- let them fall through
            return

        started = time.monotonic()

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
            raise

        if not raw_bytes or not raw_bytes.strip():
            log_event(
                logger,
                logging.WARNING,
                "worker.empty_transcript",
                "Transcript is empty; skipping translation",
                transcript_s3_key=transcript_s3_key,
            )
            return

        transcript_text = raw_bytes.decode("utf-8")

        # Run the idempotent detect+translate step.
        # If the translation already exists in S3, this is a no-op (cache hit).
        outcome = await ensure_translated_transcript(
            transcript_s3_key=transcript_s3_key,
            transcript_text=transcript_text,
            target_language=target_language,
            source=source,
            source_language_hint=source_language_hint,
            transcript_bucket=TRANSCRIPT_BUCKET,
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
