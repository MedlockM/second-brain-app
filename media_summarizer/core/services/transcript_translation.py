"""
Source-agnostic transcript language detection and translation.

This module implements the common pipeline step (task-192) that runs for EVERY
source after a transcript is available and BEFORE artifact generation:

1. Detect the transcript language (ISO 639-1).
   - Prefer a reliable language tag exposed by the source (e.g. Deepgram
     ``detected_language``, YouTube subtitle language, ``<podcast:transcript
     language>``) when present.
   - Otherwise detect locally with ``langdetect``. Local detection is FREE and
     avoids an LLM round-trip on the common path where the transcript is already
     in the user's reading language (no translation needed).

2. Decide whether to translate: only when ``detected_language`` differs from the
   user's ``reading_language`` (task-190) AND the target is one of the 11 V1
   languages validated in the task-189 benchmark.

3. Translate with GPT-5-nano (task-189 owner decision) using a system prompt that
   preserves oral register, paragraphs, timestamps and speaker labels. No
   chunking for V1.

4. Persist the translated transcript in the same S3 bucket/structure as the
   originals, under a deterministic, idempotent key keyed on
   ``(transcript_s3_key, target_language)`` so a couple is never re-translated.

The detection method choice (local ``langdetect`` first, LLM only for the actual
translation) is justified by the task-189 benchmark: it keeps the no-translation
path zero-cost and reserves the paid LLM call for transcripts that genuinely need
to be translated.
"""

from __future__ import annotations

import asyncio
import logging
import os
import time
from io import BytesIO
from typing import Any, Dict, Optional, Tuple

import aiohttp

from media_summarizer.utils import s3
from media_summarizer.utils.logging_config import log_event

logger = logging.getLogger(__name__)

# --- Configuration -----------------------------------------------------------

TRANSCRIPT_BUCKET = os.environ.get(
    "TRANSCRIPT_BUCKET", "media-summarizer-transcripts"
)
LLM_API_URL = os.environ.get(
    "LLM_API_URL", "https://api.openai.com/v1/chat/completions"
)
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")

# task-189 owner decision: GPT-5-nano via the existing OpenAI stack.
TRANSLATION_MODEL = os.environ.get(
    "TRANSLATION_LLM_MODEL", "gpt-5-nano-2025-08-07"
)
TRANSLATION_TIMEOUT_SECONDS = int(
    os.environ.get("TRANSLATION_TIMEOUT_SECONDS", "180")
)
TRANSLATION_MAX_RETRIES = int(os.environ.get("TRANSLATION_MAX_RETRIES", "3"))
TRANSLATION_BACKOFF_BASE_SECONDS = float(
    os.environ.get("TRANSLATION_BACKOFF_BASE_SECONDS", "1.0")
)
PREWARM_TRANSLATION_TIMEOUT_SECONDS = int(
    os.environ.get("PREWARM_TRANSLATION_TIMEOUT_SECONDS", "45")
)

# Rough token estimate for observability / cost (4 chars per token, EU avg).
_CHARS_PER_TOKEN = 4
# GPT-5-nano pricing per task-189 benchmark (USD per 1M tokens).
_INPUT_USD_PER_1M = 0.05
_OUTPUT_USD_PER_1M = 0.40

# 11 V1 languages validated by the task-189 benchmark (ISO 639-1 -> English name).
V1_LANGUAGE_NAMES: Dict[str, str] = {
    "fr": "French",
    "en": "English",
    "es": "Spanish",
    "de": "German",
    "it": "Italian",
    "pt": "Portuguese",
    "nl": "Dutch",
    "ja": "Japanese",
    "zh": "Chinese",
    "ar": "Arabic",
    "hi": "Hindi",
}
V1_LANGUAGES = frozenset(V1_LANGUAGE_NAMES.keys())


class TranscriptTranslationError(Exception):
    """Raised when translation fails after exhausting retries."""


def _normalize_lang(value: Optional[str]) -> Optional[str]:
    """Normalize a language tag to a bare ISO 639-1 code (lowercase, no region).

    Examples: ``"EN-US"`` -> ``"en"``, ``"pt_BR"`` -> ``"pt"``, ``"zh-Hans"`` ->
    ``"zh"``. Returns ``None`` for empty / unknown values.
    """
    if not value:
        return None
    code = str(value).strip().lower()
    if not code or code in {"unknown", "und", "auto", "mul", "zxx"}:
        return None
    # Split on region/script separators and keep the primary subtag.
    primary = code.replace("_", "-").split("-", 1)[0]
    return primary or None


def detect_language(
    transcript: str,
    *,
    source_hint: Optional[str] = None,
) -> Tuple[Optional[str], str]:
    """Detect the transcript language.

    Returns ``(iso_639_1_or_None, method)`` where ``method`` is one of
    ``"source_tag"``, ``"langdetect"`` or ``"unknown"``.

    A reliable source-provided tag wins when present; otherwise the text is
    classified locally with ``langdetect`` (free, no LLM call).
    """
    hint = _normalize_lang(source_hint)
    if hint:
        return hint, "source_tag"

    text = (transcript or "").strip()
    if not text:
        return None, "unknown"

    try:
        from langdetect import DetectorFactory, detect

        # Make detection deterministic across runs (idempotence).
        DetectorFactory.seed = 0
        detected = _normalize_lang(detect(text))
        if detected:
            return detected, "langdetect"
    except Exception as exc:  # pragma: no cover - defensive
        log_event(
            logger,
            logging.WARNING,
            "translation.detect_failed",
            "Local language detection failed",
            error_type=type(exc).__name__,
            detail=str(exc)[:200],
        )
    return None, "unknown"


def should_translate(
    detected_language: Optional[str],
    target_language: Optional[str],
) -> bool:
    """Return True when a translation should be performed.

    Translate only when the detected language is known, differs from the target,
    and the target is one of the 11 V1 languages.
    """
    detected = _normalize_lang(detected_language)
    target = _normalize_lang(target_language)
    if not detected or not target:
        return False
    if detected == target:
        return False
    return target in V1_LANGUAGES


def build_translated_transcript_key(
    *,
    transcript_s3_key: str,
    target_language: str,
) -> str:
    """Deterministic, idempotent S3 key for a translated transcript.

    Keyed on ``(transcript_s3_key, target_language)`` so the same couple always
    resolves to the same object — the cache key required by AC#7.
    """
    target = _normalize_lang(target_language) or "xx"
    base = transcript_s3_key.rsplit(".", 1)
    if len(base) == 2:
        stem, ext = base
        return f"{stem}.translated.{target}.{ext}"
    return f"{transcript_s3_key}.translated.{target}"


def _build_system_prompt(*, source_language: str, target_language: str) -> str:
    """Translation system prompt from the task-189 README ("System Prompt")."""
    source_name = V1_LANGUAGE_NAMES.get(source_language, source_language)
    target_name = V1_LANGUAGE_NAMES.get(target_language, target_language)
    return (
        "You are a translation assistant specialized in translating transcripts.\n"
        "\n"
        "Rules:\n"
        f"- Translate the following transcript from {source_name} to {target_name}.\n"
        "- Preserve ALL formatting: paragraph breaks, line breaks, timestamps "
        "(e.g., [00:05:32]), speaker labels.\n"
        "- Maintain the oral/conversational register. Do NOT formalize the language.\n"
        "- Keep proper nouns, brand names, and technical terms in their original "
        "form when appropriate.\n"
        "- If timestamps or speaker labels are present, keep them exactly as-is "
        "(do not translate them).\n"
        "- Output ONLY the translated text. No commentary, no notes, no explanations."
    )


async def _call_translation_llm(
    *,
    transcript: str,
    source_language: str,
    target_language: str,
) -> Tuple[str, Dict[str, Any]]:
    """Call GPT-5-nano once. Returns ``(translated_text, usage)``.

    No chunking for V1 (the 400k-token window covers any realistic transcript).
    """
    if not OPENAI_API_KEY:
        raise TranscriptTranslationError(
            "OPENAI_API_KEY environment variable is required for translation"
        )

    system_prompt = _build_system_prompt(
        source_language=source_language,
        target_language=target_language,
    )
    payload: Dict[str, Any] = {
        "model": TRANSLATION_MODEL,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": transcript},
        ],
    }
    timeout = aiohttp.ClientTimeout(total=TRANSLATION_TIMEOUT_SECONDS)
    async with aiohttp.ClientSession(timeout=timeout) as session:
        async with session.post(
            LLM_API_URL,
            headers={
                "Authorization": f"Bearer {OPENAI_API_KEY}",
                "Content-Type": "application/json",
            },
            json=payload,
        ) as response:
            if response.status >= 400:
                body = await response.text()
                raise TranscriptTranslationError(
                    f"translation_llm_http_{response.status}: {body[:300]}"
                )
            result = await response.json()
            content = result["choices"][0]["message"]["content"]
            usage = result.get("usage") or {}
            return content, usage


async def _translate_with_retry(
    *,
    transcript: str,
    source_language: str,
    target_language: str,
) -> Tuple[str, Dict[str, Any]]:
    """Translate with exponential backoff. Raises on terminal failure."""
    last_exc: Optional[Exception] = None
    for attempt in range(1, TRANSLATION_MAX_RETRIES + 1):
        try:
            return await _call_translation_llm(
                transcript=transcript,
                source_language=source_language,
                target_language=target_language,
            )
        except Exception as exc:  # noqa: BLE001 - retried below
            last_exc = exc
            if attempt >= TRANSLATION_MAX_RETRIES:
                break
            backoff = TRANSLATION_BACKOFF_BASE_SECONDS * (2 ** (attempt - 1))
            log_event(
                logger,
                logging.WARNING,
                "translation.retry",
                "Translation attempt failed, retrying with backoff",
                attempt=attempt,
                max_retries=TRANSLATION_MAX_RETRIES,
                backoff_seconds=backoff,
                error_type=type(exc).__name__,
                detail=str(exc)[:200],
            )
            await asyncio.sleep(backoff)
    raise TranscriptTranslationError(
        f"translation_failed_after_{TRANSLATION_MAX_RETRIES}_attempts: {last_exc}"
    )


def _estimate_cost_usd(usage: Dict[str, Any], char_count: int) -> float:
    """Best-effort cost estimate. Falls back to a char-based token estimate."""
    prompt_tokens = usage.get("prompt_tokens")
    completion_tokens = usage.get("completion_tokens")
    if prompt_tokens is None or completion_tokens is None:
        approx = max(1, char_count // _CHARS_PER_TOKEN)
        prompt_tokens = approx
        completion_tokens = approx
    input_cost = (prompt_tokens / 1_000_000) * _INPUT_USD_PER_1M
    output_cost = (completion_tokens / 1_000_000) * _OUTPUT_USD_PER_1M
    return round(input_cost + output_cost, 6)


class TranslationOutcome:
    """Result of :func:`ensure_translated_transcript`.

    ``transcript_s3_key`` is the key downstream artifact generation must read.
    When translation succeeds it points at the translated object; otherwise it
    falls back to the original transcript key.
    """

    def __init__(
        self,
        *,
        transcript_s3_key: str,
        detected_language: Optional[str],
        detection_method: str,
        target_language: Optional[str],
        is_translated: bool,
        translation_failed: bool = False,
        translation_error: Optional[str] = None,
    ) -> None:
        self.transcript_s3_key = transcript_s3_key
        self.detected_language = detected_language
        self.detection_method = detection_method
        self.target_language = target_language
        self.is_translated = is_translated
        self.translation_failed = translation_failed
        self.translation_error = translation_error

    def metadata(self) -> Dict[str, Any]:
        """Translation metadata block embedded in the artifact envelope."""
        return {
            "is_translated": self.is_translated,
            "translated_from": self.detected_language if self.is_translated else None,
            "target_language": self.target_language,
            "detected_language": self.detected_language,
            "detection_method": self.detection_method,
            "translation_failed": self.translation_failed,
        }


async def ensure_translated_transcript(
    *,
    transcript_s3_key: str,
    transcript_text: str,
    target_language: Optional[str],
    source: Optional[str] = None,
    source_language_hint: Optional[str] = None,
    transcript_bucket: str = TRANSCRIPT_BUCKET,
) -> TranslationOutcome:
    """Common detect+translate step. Source-agnostic.

    - Detects the transcript language (source tag first, then local langdetect).
    - Translates to ``target_language`` only when needed and supported.
    - Idempotent: a ``(transcript_s3_key, target_language)`` couple already
      present in S3 is reused, never re-translated.
    - On translation failure: retries with backoff, then falls back to the
      original transcript (``translation_failed=True``) so artifact generation
      still proceeds. The mobile UI surfaces the failure via the badge.
    """
    started = time.monotonic()
    detected_language, detection_method = detect_language(
        transcript_text,
        source_hint=source_language_hint,
    )
    normalized_target = _normalize_lang(target_language)

    if not should_translate(detected_language, normalized_target):
        log_event(
            logger,
            logging.INFO,
            "translation.skipped",
            "Transcript already in target language or target unsupported",
            source=source,
            detected_language=detected_language,
            target_language=normalized_target,
            detection_method=detection_method,
            translated=False,
        )
        return TranslationOutcome(
            transcript_s3_key=transcript_s3_key,
            detected_language=detected_language,
            detection_method=detection_method,
            target_language=normalized_target,
            is_translated=False,
        )

    assert detected_language is not None  # guaranteed by should_translate
    assert normalized_target is not None

    translated_key = build_translated_transcript_key(
        transcript_s3_key=transcript_s3_key,
        target_language=normalized_target,
    )

    # Idempotence: reuse an already-produced translation for this couple.
    try:
        if await s3.object_exists(bucket=transcript_bucket, key=translated_key):
            log_event(
                logger,
                logging.INFO,
                "translation.cache_hit",
                "Reusing previously translated transcript",
                source=source,
                detected_language=detected_language,
                target_language=normalized_target,
                detection_method=detection_method,
                translated=True,
            )
            return TranslationOutcome(
                transcript_s3_key=translated_key,
                detected_language=detected_language,
                detection_method=detection_method,
                target_language=normalized_target,
                is_translated=True,
            )
    except Exception as exc:  # pragma: no cover - defensive
        log_event(
            logger,
            logging.WARNING,
            "translation.cache_lookup_failed",
            "Translated transcript existence check failed; will translate",
            error_type=type(exc).__name__,
            detail=str(exc)[:200],
        )

    try:
        translated_text, usage = await _translate_with_retry(
            transcript=transcript_text,
            source_language=detected_language,
            target_language=normalized_target,
        )
    except TranscriptTranslationError as exc:
        # Documented fallback: pass the ORIGINAL transcript to artifacts and flag
        # the failure so the mobile UI can tell the user it wasn't translated.
        log_event(
            logger,
            logging.ERROR,
            "translation.failed",
            "Translation failed after retries; falling back to original transcript",
            source=source,
            detected_language=detected_language,
            target_language=normalized_target,
            detection_method=detection_method,
            model=TRANSLATION_MODEL,
            translated=False,
            detail=str(exc)[:300],
        )
        return TranslationOutcome(
            transcript_s3_key=transcript_s3_key,
            detected_language=detected_language,
            detection_method=detection_method,
            target_language=normalized_target,
            is_translated=False,
            translation_failed=True,
            translation_error=str(exc)[:300],
        )

    payload_bytes = (translated_text or "").encode("utf-8")
    await s3.upload_file_object(
        bucket=transcript_bucket,
        key=translated_key,
        file_obj=BytesIO(payload_bytes),
        content_type="text/plain; charset=utf-8",
        metadata={
            "is-translated": "true",
            "translated-from": detected_language,
            "target-language": normalized_target,
            "source-transcript-key": transcript_s3_key,
        },
    )

    duration_ms = int((time.monotonic() - started) * 1000)
    char_count = len(transcript_text or "")
    log_event(
        logger,
        logging.INFO,
        "translation.completed",
        "Transcript translated",
        source=source,
        detected_language=detected_language,
        target_language=normalized_target,
        detection_method=detection_method,
        model=TRANSLATION_MODEL,
        prompt_tokens=usage.get("prompt_tokens"),
        completion_tokens=usage.get("completion_tokens"),
        total_tokens=usage.get("total_tokens"),
        duration_ms=duration_ms,
        estimated_cost_usd=_estimate_cost_usd(usage, char_count),
        translated=True,
    )
    return TranslationOutcome(
        transcript_s3_key=translated_key,
        detected_language=detected_language,
        detection_method=detection_method,
        target_language=normalized_target,
        is_translated=True,
    )


def job_source_language_hint(job: Any) -> Optional[str]:
    """Reliable source-provided language tag from a job's transcription metadata.

    Deepgram persists the detected/forced language in ``transcription_metadata``;
    YouTube/TikTok subtitle workers and the Podcasting 2.0 short-circuit do the
    same. We treat that tag as a trustworthy detection hint.
    """
    metadata = getattr(job, "transcription_metadata", None)
    if isinstance(metadata, dict):
        for key in ("detected_language", "language"):
            value = metadata.get(key)
            if isinstance(value, str) and value.strip():
                return value
    return None


async def prewarm_translated_transcript(
    job: Any, transcript_s3_key: str, transcript_text: str
) -> None:
    """Pre-translate the transcript to the user's reading language (task-192).

    Call this synchronously, before ``job.mark_completed()``, from every worker
    that completes a job with a transcript -- so the S3-cached translation is
    warm by the time the mobile app calls ``/raw-content``, keeping that
    endpoint well within API Gateway's hard 30s integration timeout. Bounded by
    ``PREWARM_TRANSLATION_TIMEOUT_SECONDS`` so a slow translation cannot block
    job completion indefinitely; failures are logged and swallowed since the
    prewarm is a best-effort optimization, not a correctness requirement
    (``/raw-content`` falls back to translating on demand).
    """
    from media_summarizer.utils import database_async

    job_id = getattr(job, "id", None)
    user_id = getattr(job, "user_id", None)
    if not user_id:
        return
    try:
        user = await database_async.get_user_by_id(user_id)
    except Exception as exc:
        logger.warning(f"Failed to load user {user_id} for transcript prewarm: {exc}")
        return

    reading_language = getattr(user, "reading_language", None) if user else None
    if not reading_language:
        return

    async def _translate_and_persist() -> None:
        outcome = await ensure_translated_transcript(
            transcript_s3_key=transcript_s3_key,
            transcript_text=transcript_text,
            target_language=reading_language,
            source=getattr(job, "source_platform", None),
            source_language_hint=job_source_language_hint(job),
            transcript_bucket=TRANSCRIPT_BUCKET,
        )
        await persist_detected_language(job, outcome.detected_language)

    try:
        await asyncio.wait_for(
            _translate_and_persist(), timeout=PREWARM_TRANSLATION_TIMEOUT_SECONDS
        )
    except asyncio.TimeoutError:
        logger.warning(
            f"Transcript prewarm timed out after "
            f"{PREWARM_TRANSLATION_TIMEOUT_SECONDS}s for job {job_id}"
        )
    except Exception as exc:
        logger.warning(
            f"Failed to pre-warm translated transcript for job {job_id}: {exc}"
        )


async def persist_detected_language(job: Any, detected_language: Optional[str]) -> None:
    """Best-effort persistence of the detected language on the job (idempotent)."""
    if not detected_language:
        return
    metadata = dict(getattr(job, "transcription_metadata", None) or {})
    if metadata.get("detected_language") == detected_language:
        return
    metadata["detected_language"] = detected_language
    try:
        job.set_transcription_metadata(metadata)
        from media_summarizer.utils import database_async

        await database_async.update_processing_job(job)
    except Exception as exc:  # pragma: no cover - non-fatal
        log_event(
            logger,
            logging.WARNING,
            "translation.detected_language_persist_failed",
            "Failed to persist detected_language on job (non-fatal)",
            media_item_id=getattr(job, "id", None),
            error_type=type(exc).__name__,
            detail=str(exc)[:200],
        )
