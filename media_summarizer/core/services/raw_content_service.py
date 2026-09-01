"""
Service for retrieving and formatting raw content from media items.

Raw content is the source material (transcript, extracted text, OCR result)
stored in S3 under the processing job's transcription_s3_key.
This service downloads that content and formats it into readable text.

Translation architecture (task-200):
- /raw-content NEVER calls LLM translation synchronously.
- If a cached translation exists in S3, it is returned immediately.
- If not, the original transcript is returned with translation_pending=true
  and an async job is dispatched via SQS to the transcript-translation-worker.
- The mobile client polls /raw-content until the translation is ready.

Formatting architecture (task-232, benchmark task-231 option B):
- Producers already store paragraph-delimited plain text.
- This service re-runs the same shared normalizer at read time. It is
  idempotent, so new content passes through untouched while transcripts ingested
  before the change get structured on the fly — no S3 migration needed.
"""

from __future__ import annotations

import logging
from typing import Optional

from media_summarizer.core.models import ProcessingJob
from media_summarizer.core.services.transcript_formatting import (
    normalize_transcript_text,
)
from media_summarizer.core.services.transcript_translation import (
    TRANSCRIPT_TRANSLATION_QUEUE,
    _normalize_lang,
    build_translated_transcript_key,
    detect_language,
    enqueue_translation_job,
    job_source_language_hint,
    should_translate,
)
from media_summarizer.utils import s3
from media_summarizer.utils.env import required_env
from media_summarizer.utils.logging_config import log_event
from media_summarizer.utils.translation_idempotence import (
    TranslationStatus,
    build_translation_fingerprint,
    get_translation_lock,
    is_terminally_failed,
    mark_translation_failed,
    reserve_translation,
)

logger = logging.getLogger(__name__)

TRANSCRIPT_BUCKET = required_env("TRANSCRIPT_BUCKET")

class RawContentNotAvailableError(Exception):
    """Raised when raw content is not yet available for a media item."""

    pass


class RawContentResponse:
    """Structured response for raw content retrieval."""

    def __init__(
        self,
        content: str,
        content_type: str,
        media_type: Optional[str] = None,
        source_format: Optional[str] = None,
        translation: Optional[dict] = None,
    ):
        self.content = content
        self.content_type = content_type
        self.media_type = media_type
        self.source_format = source_format
        self.translation = translation


async def get_raw_content(
    job: ProcessingJob,
    reading_language: Optional[str] = None,
) -> RawContentResponse:
    """
    Retrieve and format the raw content for a media item.

    Downloads the transcript/text from S3 and formats it into readable text.
    The source format depends on the media type:
    - Audio/Video/Podcast: transcript (paragraph-delimited plain text)
    - Articles: extracted text (plain text from trafilatura)
    - Social posts: raw text content
    - Images/PDFs: OCR result

    Translation behavior (task-200 — fully asynchronous):
    - If a cached translation exists in S3, it is served immediately.
    - If a translation is needed but not yet cached, the original transcript is
      returned with ``translation_pending=true`` and an async job is dispatched
      to the transcript-translation-worker via SQS.
    - No LLM call is ever made synchronously in this code path.

    Args:
        job: The ProcessingJob containing the S3 key reference.
        reading_language: The user's preferred reading language (ISO 639-1),
            if any.

    Returns:
        RawContentResponse with formatted content.

    Raises:
        RawContentNotAvailableError: If the content is not yet available.
    """
    transcript_s3_key = (getattr(job, "transcription_s3_key", None) or "").strip()
    if not transcript_s3_key:
        raise RawContentNotAvailableError(
            "Raw content is not yet available for this media item."
        )

    try:
        raw_bytes = await s3.download_file_to_memory(
            bucket=TRANSCRIPT_BUCKET,
            key=transcript_s3_key,
        )
    except Exception as exc:
        logger.error(
            "Failed to download raw content from S3 for key %s: %s",
            transcript_s3_key,
            exc,
        )
        raise RawContentNotAvailableError(
            "Raw content could not be retrieved."
        ) from exc

    if not raw_bytes or not raw_bytes.strip():
        raise RawContentNotAvailableError(
            "Raw content is empty for this media item."
        )

    raw_text = raw_bytes.decode("utf-8")
    media_type = getattr(job, "media_type", None) or ""
    source_platform = getattr(job, "source_platform", None) or ""

    effective_text = raw_text
    translation_metadata: Optional[dict] = None

    if reading_language:
        translation_metadata = await _resolve_translation(
            job=job,
            transcript_s3_key=transcript_s3_key,
            raw_text=raw_text,
            reading_language=reading_language,
            source_platform=source_platform,
        )
        # If a cached translation was found, use it
        if translation_metadata and translation_metadata.get("is_translated"):
            translated_key = translation_metadata.get("_translated_s3_key")
            if translated_key:
                try:
                    translated_bytes = await s3.download_file_to_memory(
                        bucket=TRANSCRIPT_BUCKET,
                        key=translated_key,
                    )
                    effective_text = translated_bytes.decode("utf-8")
                except Exception as exc:
                    log_event(
                        logger,
                        logging.WARNING,
                        "raw_content.translated_download_failed",
                        "Failed to download cached translation; falling back to original",
                        transcript_s3_key=transcript_s3_key,
                        translated_key=translated_key,
                        error_type=type(exc).__name__,
                    )
                    translation_metadata = {
                        "is_translated": False,
                        "translated_from": None,
                        "target_language": reading_language,
                        "detected_language": translation_metadata.get("detected_language"),
                        "detection_method": translation_metadata.get("detection_method"),
                        "translation_pending": True,
                        "translation_status": TranslationStatus.QUEUED,
                    }
        # Remove internal key from metadata before returning
        if translation_metadata and "_translated_s3_key" in translation_metadata:
            translation_metadata = {
                k: v for k, v in translation_metadata.items() if k != "_translated_s3_key"
            }

    # Determine source format and format accordingly.
    # Ordering matters: translation is resolved *before* formatting, so the
    # normalizer runs on the effective (possibly translated) text. If the
    # translation LLM ever collapses paragraph breaks despite the prompt, they
    # get re-derived here — the read path is self-healing (task-231 section 8.2).
    source_format = _detect_source_format(media_type, source_platform, transcript_s3_key)
    formatted_content = _format_content(effective_text, source_format)

    return RawContentResponse(
        content=formatted_content,
        content_type="text/plain",
        media_type=media_type or None,
        source_format=source_format,
        translation=translation_metadata,
    )


async def _resolve_translation(
    *,
    job: ProcessingJob,
    transcript_s3_key: str,
    raw_text: str,
    reading_language: str,
    source_platform: str,
) -> dict:
    """Resolve translation status without any synchronous LLM call.

    State-machine aware (task-203):
    1. Detect the source language (local langdetect, zero-cost).
    2. Decide whether a translation is needed.
    3. Check the translation idempotence state machine in DynamoDB:
       - ``done``: S3 cache should contain the translation -- serve it.
       - ``queued`` / ``in_progress``: translation already in-flight, do NOT
         re-enqueue -- return translation_pending with the status.
       - ``failed`` (permanent): the provider refused for good -- report
         ``translation_status=failed`` and reserve nothing.
       - ``failed`` (transient): re-authorize a fresh translation attempt.
       - no record: first request -- attempt atomic reservation + enqueue.
    4. On S3 cache hit (even without a state record, for backward compat):
       serve the translation directly.
    5. On cache miss with no inflight state: reserve atomically + enqueue.
    """
    source_language_hint = job_source_language_hint(job)
    detected_language, detection_method = detect_language(
        raw_text,
        source_hint=source_language_hint,
    )
    normalized_target = _normalize_lang(reading_language)

    # No translation needed (same language or unsupported target)
    if not should_translate(detected_language, normalized_target):
        return {
            "is_translated": False,
            "translated_from": None,
            "target_language": normalized_target,
            "detected_language": detected_language,
            "detection_method": detection_method,
            "translation_pending": False,
            "translation_status": None,
        }

    assert detected_language is not None
    assert normalized_target is not None

    translated_key = build_translated_transcript_key(
        transcript_s3_key=transcript_s3_key,
        target_language=normalized_target,
    )

    # --- Check the translation state machine first (task-203 anti-thundering-herd) ---
    fingerprint = build_translation_fingerprint(
        transcript_s3_key=transcript_s3_key,
        target_language=normalized_target,
    )
    try:
        lock = await get_translation_lock(fingerprint)
    except Exception as exc:
        log_event(
            logger,
            logging.WARNING,
            "raw_content.translation_lock_read_failed",
            "Failed to read translation lock; falling back to S3 check",
            error_type=type(exc).__name__,
            detail=str(exc)[:200],
        )
        lock = None

    retry_missing_done_translation = False

    # If state machine says "done", translation should be in S3
    if lock and lock.status == TranslationStatus.DONE:
        # Verify S3 actually has it (defensive)
        try:
            cache_hit = await s3.object_exists(
                bucket=TRANSCRIPT_BUCKET,
                key=translated_key,
            )
        except Exception:
            cache_hit = False

        if cache_hit:
            log_event(
                logger,
                logging.INFO,
                "raw_content.translation_cache_hit",
                "Serving cached translated transcript (state=done)",
                transcript_s3_key=transcript_s3_key,
                target_language=normalized_target,
                detected_language=detected_language,
            )
            return {
                "is_translated": True,
                "translated_from": detected_language,
                "target_language": normalized_target,
                "detected_language": detected_language,
                "detection_method": detection_method,
                "translation_pending": False,
                "translation_status": TranslationStatus.DONE,
                "_translated_s3_key": translated_key,
            }
        # State says done but S3 object missing -- treat as failed for recovery
        retry_missing_done_translation = True
        lock = None

    # If state machine says "queued" or "in_progress", do NOT re-enqueue
    if lock and lock.status in (TranslationStatus.QUEUED, TranslationStatus.IN_PROGRESS):
        log_event(
            logger,
            logging.INFO,
            "raw_content.translation_in_flight",
            "Translation already in-flight; not re-enqueuing",
            transcript_s3_key=transcript_s3_key,
            target_language=normalized_target,
            detected_language=detected_language,
            translation_status=lock.status,
        )
        return {
            "is_translated": False,
            "translated_from": None,
            "target_language": normalized_target,
            "detected_language": detected_language,
            "detection_method": detection_method,
            "translation_pending": True,
            "translation_status": lock.status,
        }

    # If the state machine says "failed" with a *permanent* kind, the provider
    # refused for a reason no retry can change (no credit, rejected key, unknown
    # model). Report the failure and reserve nothing: this read path is polled
    # every 3 seconds by the mobile transcript view, and re-reserving here is how
    # one exhausted OpenAI balance turned into 25 worker invocations for a single
    # document (task-327). The client stops polling on `translation_status:
    # failed` and shows the original transcript with its "not translated" badge.
    if is_terminally_failed(lock):
        log_event(
            logger,
            logging.WARNING,
            "raw_content.translation_permanently_failed",
            "Translation failed permanently; serving the original transcript",
            transcript_s3_key=transcript_s3_key,
            target_language=normalized_target,
            detected_language=detected_language,
        )
        return {
            "is_translated": False,
            "translated_from": None,
            "target_language": normalized_target,
            "detected_language": detected_language,
            "detection_method": detection_method,
            "translation_pending": False,
            "translation_status": TranslationStatus.FAILED,
        }

    # A *transient* "failed" was attempted and failed for a reason that may pass
    # (a timeout, a 5xx, a momentary rate limit). We allow a fresh re-attempt by
    # falling through to the reservation logic below: the reserve_translation()
    # ConditionExpression explicitly allows overwriting a transiently failed lock.
    # The anti-infinite-loop is provided by TRANSLATION_POLL_MAX_ATTEMPTS on mobile
    # (max 20 polls = 60s) and by the SQS DLQ (maxReceiveCount=3 per reservation).

    # --- No inflight state (no record, state=failed, or state invalidated): check S3, then attempt reservation ---

    # Check S3 cache (covers legacy translations produced before state machine existed)
    try:
        cache_hit = await s3.object_exists(
            bucket=TRANSCRIPT_BUCKET,
            key=translated_key,
        )
    except Exception as exc:
        log_event(
            logger,
            logging.WARNING,
            "raw_content.translation_cache_check_failed",
            "S3 cache check failed; treating as cache miss",
            error_type=type(exc).__name__,
            detail=str(exc)[:200],
        )
        cache_hit = False

    if cache_hit:
        log_event(
            logger,
            logging.INFO,
            "raw_content.translation_cache_hit",
            "Serving cached translated transcript",
            transcript_s3_key=transcript_s3_key,
            target_language=normalized_target,
            detected_language=detected_language,
        )
        return {
            "is_translated": True,
            "translated_from": detected_language,
            "target_language": normalized_target,
            "detected_language": detected_language,
            "detection_method": detection_method,
            "translation_pending": False,
            "translation_status": TranslationStatus.DONE,
            "_translated_s3_key": translated_key,
        }

    # Attempt atomic reservation (only the first caller wins)
    try:
        reserved = await reserve_translation(
            transcript_s3_key=transcript_s3_key,
            target_language=normalized_target,
            allow_done_retry=retry_missing_done_translation,
        )
    except Exception as exc:
        log_event(
            logger,
            logging.WARNING,
            "raw_content.translation_reserve_failed",
            "Failed to reserve translation; treating as already in-flight",
            error_type=type(exc).__name__,
            detail=str(exc)[:200],
        )
        reserved = False

    if reserved:
        # We won the reservation -- enqueue the translation job
        dispatched = await _enqueue_translation_job(
            transcript_s3_key=transcript_s3_key,
            target_language=normalized_target,
            source_language_hint=source_language_hint,
            source=source_platform or None,
            job_id=getattr(job, "id", None),
        )
        if dispatched:
            log_event(
                logger,
                logging.INFO,
                "raw_content.translation_enqueued",
                "Translation reserved and async job dispatched",
                transcript_s3_key=transcript_s3_key,
                target_language=normalized_target,
                detected_language=detected_language,
            )
        else:
            return {
                "is_translated": False,
                "translated_from": None,
                "target_language": normalized_target,
                "detected_language": detected_language,
                "detection_method": detection_method,
                "translation_pending": False,
                "translation_status": TranslationStatus.FAILED,
            }
    else:
        log_event(
            logger,
            logging.INFO,
            "raw_content.translation_already_reserved",
            "Translation already reserved by another caller; not re-enqueuing",
            transcript_s3_key=transcript_s3_key,
            target_language=normalized_target,
            detected_language=detected_language,
        )

    return {
        "is_translated": False,
        "translated_from": None,
        "target_language": normalized_target,
        "detected_language": detected_language,
        "detection_method": detection_method,
        "translation_pending": True,
        "translation_status": TranslationStatus.QUEUED,
    }


async def _enqueue_translation_job(
    *,
    transcript_s3_key: str,
    target_language: str,
    source_language_hint: Optional[str],
    source: Optional[str],
    job_id: Optional[str],
) -> bool:
    """Enqueue a translation job to the transcript-translation-queue.

    Best-effort: failures are logged but do not break /raw-content.
    The next request will re-attempt the dispatch.
    """
    try:
        await enqueue_translation_job(
            transcript_s3_key=transcript_s3_key,
            target_language=target_language,
            source_language_hint=source_language_hint,
            source=source,
            job_id=job_id,
        )
        return True
    except Exception as exc:
        await mark_translation_failed(
            transcript_s3_key=transcript_s3_key,
            target_language=target_language,
            error_message=(
                f"translation_enqueue_failed: {type(exc).__name__}: {str(exc)[:200]}"
            ),
        )
        log_event(
            logger,
            logging.ERROR,
            "raw_content.translation_enqueue_failed",
            "Failed to enqueue translation job; next request will retry",
            queue=TRANSCRIPT_TRANSLATION_QUEUE,
            transcript_s3_key=transcript_s3_key,
            target_language=target_language,
            error_type=type(exc).__name__,
            detail=str(exc)[:200],
        )
        return False


def _detect_source_format(media_type: str, source_platform: str, transcript_s3_key: str) -> str:
    """
    Classify the raw content by media type, platform and stored extension.

    Returns one of: "markdown", "article_text", "social_post", "ocr", "plain_text".

    Note: this is a *classification* of the content family, not provider payload
    sniffing. Nothing ever writes a provider JSON payload to the transcript
    bucket — every producer stores plain text (or markdown for parsed
    documents), so the former ``deepgram_json`` / ``whisper_json`` /
    ``json_transcript`` branches were unreachable and have been removed
    (task-231 section 12).
    """
    if transcript_s3_key.lower().endswith(".md"):
        return "markdown"
    if media_type in ("article",) or source_platform in ("web",):
        return "article_text"
    if source_platform in ("twitter", "linkedin"):
        return "social_post"
    if media_type in ("image", "pdf") or source_platform in ("ocr",):
        return "ocr"
    return "plain_text"


def _format_content(raw_text: str, source_format: str) -> str:
    """Format raw content based on its source format.

    Everything but markdown goes through the shared transcript normalizer
    (task-231 option B). Because that normalizer is idempotent, content already
    structured at write time passes through untouched, while legacy flat
    transcripts get paragraphed on the fly — which is what makes an S3 backfill
    unnecessary.
    """
    if source_format == "markdown":
        # Parsed documents carry their own markdown structure (headings, lists).
        # Re-paragraphing them would damage it.
        return raw_text.strip()
    return normalize_transcript_text(raw_text, source=source_format)
