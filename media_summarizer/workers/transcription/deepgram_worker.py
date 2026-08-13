"""
Deepgram transcription worker.

Active transcription path:
- Consumes messages from DEEPGRAM_TRANSCRIPTION_QUEUE
- Reads audio_url from message payload
- Sends Deepgram a pre-recorded URL payload
- Uploads transcript to S3
- Publishes episode completion status events
"""

from __future__ import annotations

import asyncio
import json
import logging
import mimetypes
import os
import time
from io import BytesIO
from math import ceil
from typing import Any, Dict, Optional
from urllib.parse import urlsplit

import httpx
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from media_summarizer.core.services import quota_enforcer
from media_summarizer.core.services.transcript_formatting import (
    count_paragraphs,
    deepgram_transcript_text,
)
from media_summarizer.utils import s3, sqs
from media_summarizer.utils.env import required_env
from media_summarizer.utils.logging_config import (
    bind_log_context,
    log_event,
    reset_log_context,
    setup_logging,
)
from media_summarizer.workers.base_worker import process_message_with_retry

logger = logging.getLogger(__name__)


class NonRetryableDeepgramError(Exception):
    """Raised for non-retryable Deepgram request failures."""


class RemoteContentError(NonRetryableDeepgramError):
    """Raised when Deepgram cannot fetch audio from a remote URL (e.g. CDN 403).

    This is a subclass of NonRetryableDeepgramError so existing handlers still
    catch it, but the process_deepgram_message function intercepts it to attempt
    a push-mode fallback (download audio locally, then POST bytes to Deepgram).
    """


class RetryableDeepgramError(Exception):
    """Raised for transient/retryable Deepgram request failures."""


TRANSCRIPT_BUCKET = required_env("TRANSCRIPT_BUCKET")
AUDIO_BUCKET = required_env("AUDIO_BUCKET")
EPISODE_COMPLETED_EVENTS_QUEUE = required_env("EPISODE_COMPLETED_EVENTS_QUEUE")
EPISODE_COMPLETED_EVENTS_QUEUE = required_env("EPISODE_COMPLETED_EVENTS_QUEUE")
DEEPGRAM_TRANSCRIPTION_QUEUE = required_env("DEEPGRAM_TRANSCRIPTION_QUEUE")

# Worker retry handling (SQS-level via base worker)
WORKER_MAX_RETRIES = int(os.environ.get("DEEPGRAM_WORKER_MAX_RETRIES", "3"))

# Deepgram API configuration
DEEPGRAM_API_KEY = os.environ.get("DEEPGRAM_API_KEY", "")
DEEPGRAM_API_URL = os.environ.get(
    "DEEPGRAM_API_URL", "https://api.deepgram.com/v1/listen"
)
DEEPGRAM_MODEL = os.environ.get("DEEPGRAM_MODEL", "nova-3")
DEEPGRAM_TIMEOUT_SECONDS = float(os.environ.get("DEEPGRAM_TIMEOUT_SECONDS", "300"))
DEEPGRAM_API_RETRIES = int(os.environ.get("DEEPGRAM_API_RETRIES", "3"))

DEEPGRAM_DETECT_LANGUAGE = os.environ.get("DEEPGRAM_DETECT_LANGUAGE", "true").lower() == "true"
DEEPGRAM_SMART_FORMAT = os.environ.get("DEEPGRAM_SMART_FORMAT", "true").lower() == "true"
DEEPGRAM_PUNCTUATE = os.environ.get("DEEPGRAM_PUNCTUATE", "true").lower() == "true"
DEEPGRAM_PARAGRAPHS = os.environ.get("DEEPGRAM_PARAGRAPHS", "true").lower() == "true"
DEEPGRAM_UTTERANCES = os.environ.get("DEEPGRAM_UTTERANCES", "true").lower() == "true"
# Speaker diarization is a paid Deepgram add-on ($0.0020/min, i.e. +41.7% over the
# Nova-3 promotional rate), so it stays OFF by default (task-231 benchmark, owner
# decision "option B"). The transcript rendering path already handles the in-band
# "Speaker N:" labels, so enabling this flag is the only change required to ship
# speaker attribution.
DEEPGRAM_DIARIZE = os.environ.get("DEEPGRAM_DIARIZE", "false").lower() == "true"
# `diarize=true` is deprecated by Deepgram in favour of `diarize_model`, and
# sending both is rejected. Never send `diarize`.
DEEPGRAM_DIARIZE_MODEL = os.environ.get("DEEPGRAM_DIARIZE_MODEL", "v2")

# Heartbeat/visibility settings
HEARTBEAT_INTERVAL = float(os.environ.get("HEARTBEAT_INTERVAL", "60"))
DEEPGRAM_VISIBILITY_TIMEOUT = int(
    os.environ.get("DEEPGRAM_VISIBILITY_TIMEOUT", "1800")
)

# Valid deepgram_mode values declared by producer workers in the message body.
# "pull" = Deepgram fetches the URL (fail loudly on 403 -- producer misrouted)
# "push" = Lambda downloads audio and POSTs bytes to Deepgram (for CDNs that block Deepgram)
# "pull_with_push_fallback" = Try pull first, fall back to push on RemoteContentError
VALID_DEEPGRAM_MODES = ("pull", "push", "pull_with_push_fallback")

# Testing flag: when set to "1", forces the push-mode fallback path on
# pull_with_push_fallback messages by simulating a RemoteContentError on pull-mode.
# Used by E2E tests to deterministically exercise the push-mode fallback
# without depending on external CDN IP-blocking behavior.
FORCE_DEEPGRAM_PUSH_MODE = os.environ.get("FORCE_DEEPGRAM_PUSH_MODE", "").strip() == "1"


def _build_deepgram_query_params() -> Dict[str, str]:
    params = {
        "model": DEEPGRAM_MODEL,
        "detect_language": str(DEEPGRAM_DETECT_LANGUAGE).lower(),
        "smart_format": str(DEEPGRAM_SMART_FORMAT).lower(),
        "punctuate": str(DEEPGRAM_PUNCTUATE).lower(),
        "paragraphs": str(DEEPGRAM_PARAGRAPHS).lower(),
        "utterances": str(DEEPGRAM_UTTERANCES).lower(),
    }
    if DEEPGRAM_DIARIZE:
        params["diarize_model"] = DEEPGRAM_DIARIZE_MODEL
    return params


def _is_valid_http_url(value: str) -> bool:
    v = (value or "").strip().lower()
    return v.startswith("http://") or v.startswith("https://")


def _looks_like_feed_url(value: str) -> bool:
    raw = (value or "").strip().lower()
    if not raw:
        return False
    try:
        path = (urlsplit(raw).path or "").lower()
    except ValueError:
        path = raw
    return path.endswith(".rss") or path.endswith(".xml")


async def upload_transcription(transcript_s3_key: str, transcription_text: str) -> None:
    transcript_file = BytesIO(transcription_text.encode("utf-8"))
    await s3.upload_file_object(
        bucket=TRANSCRIPT_BUCKET,
        key=transcript_s3_key,
        file_obj=transcript_file,
        content_type="text/plain",
        metadata={
            "content-type": "text/plain",
            "job-type": "podcast-transcription",
            "provider": "deepgram",
            "model": DEEPGRAM_MODEL,
        },
    )
    log_event(
        logger,
        logging.DEBUG,
        "external_call.succeeded",
        "Uploaded Deepgram transcription",
        provider="s3",
        transcript_source="deepgram",
    )


@retry(
    reraise=True,
    stop=stop_after_attempt(DEEPGRAM_API_RETRIES),
    wait=wait_exponential(multiplier=1, min=1, max=10),
    retry=retry_if_exception_type(
        (RetryableDeepgramError, httpx.TimeoutException, httpx.TransportError)
    ),
)
async def call_deepgram_api(*, audio_url: str, job_id: str) -> Dict[str, Any]:
    if not DEEPGRAM_API_KEY:
        raise NonRetryableDeepgramError("DEEPGRAM_API_KEY is required")

    if not _is_valid_http_url(audio_url):
        raise NonRetryableDeepgramError("audio_url must be a valid http(s) URL")
    if _looks_like_feed_url(audio_url):
        raise NonRetryableDeepgramError(
            "audio_url points to an RSS/feed URL; resolve enclosure URL before Deepgram"
        )

    query_params = _build_deepgram_query_params()
    headers = {
        "Authorization": f"Token {DEEPGRAM_API_KEY}",
        "Content-Type": "application/json",
    }

    started = time.time()
    try:
        async with httpx.AsyncClient(timeout=DEEPGRAM_TIMEOUT_SECONDS) as client:
            response = await client.post(
                DEEPGRAM_API_URL,
                params=query_params,
                headers=headers,
                json={"url": audio_url},
            )
    except (httpx.TimeoutException, httpx.TransportError):
        raise

    latency_seconds = time.time() - started
    status = response.status_code

    if status in (401, 403, 400, 404, 415, 422):
        # Detect REMOTE_CONTENT_ERROR: Deepgram could not fetch the audio URL
        # (e.g. source CDN blocks cloud SaaS IPs with HTTP 403).
        # Raise RemoteContentError so callers can fall back to push-mode.
        response_text = response.text[:500]
        if "REMOTE_CONTENT_ERROR" in response_text or (
            status == 400 and "403" in response_text
        ):
            raise RemoteContentError(
                f"Deepgram remote content fetch blocked "
                f"(HTTP {status}): {response_text}"
            )
        raise NonRetryableDeepgramError(
            f"Deepgram non-retryable HTTP {status}: {response_text}"
        )
    if status == 429 or status >= 500:
        raise RetryableDeepgramError(
            f"Deepgram transient HTTP {status}: {response.text[:500]}"
        )
    if status >= 300:
        raise NonRetryableDeepgramError(
            f"Deepgram unexpected HTTP {status}: {response.text[:500]}"
        )

    try:
        payload = response.json()
    except json.JSONDecodeError as exc:
        raise NonRetryableDeepgramError(
            "Deepgram response is not valid JSON"
        ) from exc

    request_id = (payload.get("metadata") or {}).get("request_id")
    log_event(
        logger,
        logging.INFO,
        "external_call.succeeded",
        "Deepgram request succeeded",
        provider="deepgram",
        transcript_source="deepgram",
        job_id=job_id,
        status=status,
        duration_ms=int(latency_seconds * 1000),
        provider_request_id=request_id,
        audio_url=audio_url,
    )
    return payload


# Maximum audio file size for push-mode fallback (250 MB).
# Larger files should not be held in Lambda memory.
_PUSH_MODE_MAX_BYTES = 250 * 1024 * 1024

# Timeout for downloading audio from source CDN (seconds).
_AUDIO_DOWNLOAD_TIMEOUT = 120


async def _download_audio_for_push_fallback(
    audio_url: str,
    job_id: str,
) -> tuple[bytes, str]:
    """Download audio from a URL for push-mode Deepgram fallback.

    This is invoked when Deepgram's pull-mode fails because the source CDN
    blocks cloud SaaS IP ranges. Lambda downloads the audio itself, then we
    POST the bytes directly to Deepgram.

    Returns:
        Tuple of (audio_bytes, content_type).

    Raises:
        NonRetryableDeepgramError: If the download fails (expired URL, blocked, etc.).

    Cost note: This adds Lambda execution time for the download (~1-30s depending
    on file size and network) plus memory usage to hold the full audio in RAM.
    For typical social media audio (<50 MB) this is well within Lambda 512 MB limits.
    """
    log_event(
        logger,
        logging.INFO,
        "transcription.push_fallback.download_start",
        "Downloading audio for push-mode fallback (source CDN blocked Deepgram)",
        provider="deepgram",
        job_id=job_id,
        audio_url=audio_url,
    )

    try:
        async with httpx.AsyncClient(
            timeout=_AUDIO_DOWNLOAD_TIMEOUT,
            follow_redirects=True,
        ) as client:
            response = await client.get(audio_url)

        if response.status_code == 403:
            raise NonRetryableDeepgramError(
                "Lambda also blocked by source CDN (HTTP 403) "
                f"for audio URL: {audio_url[:200]}"
            )
        if response.status_code == 404:
            raise NonRetryableDeepgramError(
                "Audio URL expired or not found (HTTP 404): "
                f"{audio_url[:200]}"
            )
        if response.status_code >= 400:
            raise NonRetryableDeepgramError(
                f"Failed to download audio "
                f"(HTTP {response.status_code}): {audio_url[:200]}"
            )

        audio_bytes = response.content
        if not audio_bytes:
            raise NonRetryableDeepgramError(
                f"Downloaded audio is empty (0 bytes) from: {audio_url[:200]}"
            )
        if len(audio_bytes) > _PUSH_MODE_MAX_BYTES:
            raise NonRetryableDeepgramError(
                f"Audio too large for push-mode fallback "
                f"({len(audio_bytes)} bytes > {_PUSH_MODE_MAX_BYTES} limit)"
            )

        # Determine content type from response headers or URL
        raw_ct = response.headers.get("content-type") or ""
        content_type = raw_ct.split(";")[0].strip()
        if not content_type or content_type == "application/octet-stream":
            # Try to guess from URL path
            guessed, _ = mimetypes.guess_type(audio_url.split("?")[0])
            content_type = guessed or "audio/mpeg"

        log_event(
            logger,
            logging.INFO,
            "transcription.push_fallback.download_complete",
            "Audio downloaded for push-mode fallback",
            provider="deepgram",
            job_id=job_id,
            audio_size_bytes=len(audio_bytes),
            content_type=content_type,
        )
        return audio_bytes, content_type

    except NonRetryableDeepgramError:
        raise
    except httpx.TimeoutException:
        raise NonRetryableDeepgramError(
            "Timeout downloading audio for push-mode fallback "
            f"after {_AUDIO_DOWNLOAD_TIMEOUT}s: {audio_url[:200]}"
        )
    except Exception as exc:
        raise NonRetryableDeepgramError(
            f"Unexpected error downloading audio for push-mode fallback: "
            f"{type(exc).__name__}: {str(exc)[:200]}"
        ) from exc


def _resolve_audio_content_type(
    *,
    content_mime_type: Optional[str],
    original_name: Optional[str],
) -> str:
    mime_type = (content_mime_type or "").strip().lower()
    if mime_type.startswith("audio/") or mime_type.startswith("video/"):
        return mime_type

    guessed, _ = mimetypes.guess_type((original_name or "").strip())
    guessed = (guessed or "").strip().lower()
    if guessed.startswith("audio/") or guessed.startswith("video/"):
        return guessed
    return "application/octet-stream"


@retry(
    reraise=True,
    stop=stop_after_attempt(DEEPGRAM_API_RETRIES),
    wait=wait_exponential(multiplier=1, min=1, max=10),
    retry=retry_if_exception_type(
        (RetryableDeepgramError, httpx.TimeoutException, httpx.TransportError)
    ),
)
async def call_deepgram_api_from_bytes(
    *,
    audio_bytes: bytes,
    content_type: str,
    job_id: str,
) -> Dict[str, Any]:
    if not DEEPGRAM_API_KEY:
        raise NonRetryableDeepgramError("DEEPGRAM_API_KEY is required")
    if not audio_bytes:
        raise NonRetryableDeepgramError("audio bytes must be non-empty")

    query_params = _build_deepgram_query_params()
    headers = {
        "Authorization": f"Token {DEEPGRAM_API_KEY}",
        "Content-Type": content_type,
    }

    started = time.time()
    try:
        async with httpx.AsyncClient(timeout=DEEPGRAM_TIMEOUT_SECONDS) as client:
            response = await client.post(
                DEEPGRAM_API_URL,
                params=query_params,
                headers=headers,
                content=audio_bytes,
            )
    except (httpx.TimeoutException, httpx.TransportError):
        raise

    latency_seconds = time.time() - started
    status = response.status_code

    if status in (401, 403, 400, 404, 415, 422):
        raise NonRetryableDeepgramError(
            f"Deepgram non-retryable HTTP {status}: {response.text[:500]}"
        )
    if status == 429 or status >= 500:
        raise RetryableDeepgramError(
            f"Deepgram transient HTTP {status}: {response.text[:500]}"
        )
    if status >= 300:
        raise NonRetryableDeepgramError(
            f"Deepgram unexpected HTTP {status}: {response.text[:500]}"
        )

    try:
        payload = response.json()
    except json.JSONDecodeError as exc:
        raise NonRetryableDeepgramError(
            "Deepgram response is not valid JSON"
        ) from exc

    request_id = (payload.get("metadata") or {}).get("request_id")
    log_event(
        logger,
        logging.INFO,
        "external_call.succeeded",
        "Deepgram file-bytes request succeeded",
        provider="deepgram",
        transcript_source="deepgram",
        job_id=job_id,
        status=status,
        duration_ms=int(latency_seconds * 1000),
        provider_request_id=request_id,
        content_type=content_type,
        audio_size_bytes=len(audio_bytes),
    )
    return payload


def extract_transcript(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Extract the readable transcript text from a Deepgram response.

    Deepgram already returns paragraph structure for free (we ask for
    ``paragraphs=true`` and ``utterances=true``, both included in Smart
    Formatting), so the shared normalizer picks the richest available shape
    instead of the flat ``alternatives[0].transcript`` string. The result is
    paragraph-delimited plain text, which is what every consumer of the S3
    transcript object expects (task-231 option B).
    """
    results = payload.get("results") or {}
    channels = results.get("channels") or []
    alternatives = (channels[0].get("alternatives") if channels else None) or []
    alt = alternatives[0] if alternatives else {}

    utterances = results.get("utterances") or []
    transcript_text = deepgram_transcript_text(alt, utterances)
    if not transcript_text:
        raise NonRetryableDeepgramError("Deepgram transcript is empty")

    metadata = payload.get("metadata") or {}

    language = (
        alt.get("detected_language")
        or metadata.get("language")
        or "unknown"
    )

    # `metadata.duration` is the length of audio Deepgram actually processed and
    # billed. It is the authoritative figure for the audio-minutes quota: every
    # other duration in this pipeline is either a producer hint or wall-clock
    # latency (task-250 Layer 2).
    try:
        audio_duration_seconds = float(metadata.get("duration") or 0.0)
    except (TypeError, ValueError):
        audio_duration_seconds = 0.0

    return {
        "text": transcript_text,
        "language": language,
        # Paragraph count, not utterance/word count: every producer now reports the
        # same unit so the value is comparable across sources (task-231 s13.1).
        "segments_count": count_paragraphs(transcript_text),
        "request_id": metadata.get("request_id"),
        "audio_duration_seconds": audio_duration_seconds,
    }


async def _settle_audio_quota(
    *,
    message_body: Dict[str, Any],
    job: Any,
    job_id: str,
    billed_audio_seconds: float,
) -> None:
    """Reconcile the monthly audio counter with the duration Deepgram billed.

    This is the only place in the pipeline that knows the real duration of every
    transcription, whatever the platform it came from, so it is where the quota
    is made accurate (task-250 Layer 2). It deliberately does *not* live in the
    media-completed events consumer: the completion event is published twice
    (`episode_completion_status` and `episode_completed`), so debiting there
    would charge every job twice.

    Never raises: the user has already been billed by Deepgram, so a counter
    problem must not fail a transcription that succeeded.
    """
    # Producers whose quota category is not `audio` opt out explicitly
    # (social video keeps its own category per the validated task-250 decision).
    # Everything else that reaches this worker is metered in audio minutes.
    quota_platform = (
        message_body.get("quota_source_platform")
        or quota_enforcer.QUOTA_PLATFORM_AUDIO
    )
    if quota_enforcer.classify_media_type(quota_platform) != quota_enforcer.QUOTA_CATEGORY_AUDIO:
        log_event(
            logger,
            logging.INFO,
            "quota.settlement_skipped_non_audio",
            "Transcription is not metered in audio minutes; nothing to settle",
            job_id=job_id,
            quota_source_platform=quota_platform,
        )
        return

    user_id = message_body.get("user_id") or getattr(job, "user_id", None)
    if not user_id:
        log_event(
            logger,
            logging.WARNING,
            "quota.settlement_skipped_no_user",
            "Cannot settle audio minutes: no user_id on the message or the job",
            job_id=job_id,
            source_platform=message_body.get("source_platform"),
        )
        return

    try:
        already_debited = int(float(message_body.get("quota_debited_minutes") or 0))
    except (TypeError, ValueError):
        already_debited = 0

    try:
        applied = await quota_enforcer.settle_audio_minutes(
            user_id=user_id,
            job_id=job_id,
            actual_duration_seconds=billed_audio_seconds,
            already_debited_minutes=already_debited,
        )
    except Exception as exc:
        log_event(
            logger,
            logging.ERROR,
            "quota.settlement_error",
            "Audio minutes settlement failed; the transcription is unaffected",
            job_id=job_id,
            user_id=user_id,
            billed_audio_seconds=billed_audio_seconds,
            exc_info=exc,
        )
        return

    log_event(
        logger,
        logging.INFO,
        "quota.settled",
        "Audio minutes settled from the provider-billed duration",
        job_id=job_id,
        user_id=user_id,
        source_platform=message_body.get("source_platform"),
        billed_audio_seconds=billed_audio_seconds,
        already_debited_minutes=already_debited,
        settled_delta_minutes=applied,
    )


async def publish_failure_event(
    *,
    job_id: Optional[str],
    media_key: Optional[str],
    reason: str,
) -> None:
    if not job_id:
        return
    await sqs.send_message(
        queue_name=EPISODE_COMPLETED_EVENTS_QUEUE,
        message_body={
            "event_type": "episode_completion_status",
            "status": "failure",
            "media_key": media_key,
            "canonical_job_id": job_id,
            "reason": reason,
        },
    )


async def process_deepgram_message(message_body: Dict[str, Any]) -> None:
    job_id = message_body.get("job_id")
    audio_url = message_body.get("audio_url")
    audio_s3_key = message_body.get("audio_s3_key")

    if not job_id:
        raise NonRetryableDeepgramError("Missing required fields in transcription message")
    if not isinstance(job_id, str):
        raise NonRetryableDeepgramError("Invalid field types in transcription message")

    # Read explicit deepgram_mode declared by the producer worker.
    # Default to "pull" for backward compatibility with messages already in-flight.
    requested_mode = message_body.get("deepgram_mode")
    if requested_mode is None:
        log_event(
            logger,
            logging.WARNING,
            "transcription.missing_deepgram_mode",
            "Received Deepgram message with no deepgram_mode field; "
            "defaulting to 'pull'. Update the producer to set deepgram_mode explicitly.",
            provider="deepgram",
            job_id=job_id,
            source_platform=message_body.get("source_platform"),
        )
        requested_mode = "pull"
    elif requested_mode not in VALID_DEEPGRAM_MODES:
        raise NonRetryableDeepgramError(
            f"Invalid deepgram_mode '{requested_mode}'; "
            f"must be one of {VALID_DEEPGRAM_MODES}"
        )

    from media_summarizer.utils import database_async

    job = await database_async.get_processing_job_by_id(job_id)
    if job:
        job.mark_transcribing()
        await database_async.update_processing_job(job)

    if not audio_url and job:
        audio_url = getattr(job, "media_url", None)
    if not audio_s3_key and job:
        audio_s3_key = getattr(job, "audio_s3_key", None)

    deepgram_payload: Dict[str, Any]
    deepgram_mode_used: str = requested_mode
    started = time.time()

    if isinstance(audio_s3_key, str) and audio_s3_key.strip():
        # S3-based audio always uses push-mode (bytes already available)
        audio_bytes = await s3.download_file_to_memory(AUDIO_BUCKET, audio_s3_key.strip())
        content_type = _resolve_audio_content_type(
            content_mime_type=message_body.get("content_mime_type"),
            original_name=message_body.get("original_name"),
        )
        deepgram_payload = await call_deepgram_api_from_bytes(
            audio_bytes=audio_bytes,
            content_type=content_type,
            job_id=job_id,
        )
        deepgram_mode_used = "push"
    elif isinstance(audio_url, str) and audio_url.strip():
        if requested_mode == "push":
            # Producer declared push-mode: skip pull entirely, download and push bytes.
            audio_bytes, content_type = await _download_audio_for_push_fallback(
                audio_url=audio_url.strip(),
                job_id=job_id,
            )
            deepgram_payload = await call_deepgram_api_from_bytes(
                audio_bytes=audio_bytes,
                content_type=content_type,
                job_id=job_id,
            )
            deepgram_mode_used = "push"
        elif requested_mode == "pull":
            # Producer declared pull-mode: fail loudly on RemoteContentError.
            try:
                deepgram_payload = await call_deepgram_api(
                    audio_url=audio_url.strip(),
                    job_id=job_id,
                )
            except RemoteContentError as remote_err:
                raise NonRetryableDeepgramError(
                    f"Deepgram pull-mode failed with REMOTE_CONTENT_ERROR "
                    f"(producer declared deepgram_mode='pull' but source CDN "
                    f"blocks Deepgram; update the producer to use 'push' mode). "
                    f"source_platform={message_body.get('source_platform')}, "
                    f"audio_url={audio_url.strip()[:200]}, "
                    f"original_error={str(remote_err)[:200]}"
                ) from remote_err
            deepgram_mode_used = "pull"
        else:
            # "pull_with_push_fallback": try pull, fall back to push on CDN block.
            try:
                if FORCE_DEEPGRAM_PUSH_MODE:
                    raise RemoteContentError(
                        "Forced push-mode via FORCE_DEEPGRAM_PUSH_MODE=1 (E2E testing)"
                    )
                deepgram_payload = await call_deepgram_api(
                    audio_url=audio_url.strip(),
                    job_id=job_id,
                )
                deepgram_mode_used = "pull"
            except RemoteContentError as remote_err:
                log_event(
                    logger,
                    logging.WARNING,
                    "transcription.push_fallback.triggered",
                    "Deepgram pull-mode failed with REMOTE_CONTENT_ERROR; "
                    "attempting push-mode fallback (mode=pull_with_push_fallback)",
                    provider="deepgram",
                    job_id=job_id,
                    audio_url=audio_url.strip(),
                    original_error=str(remote_err)[:300],
                )
                audio_bytes, content_type = await _download_audio_for_push_fallback(
                    audio_url=audio_url.strip(),
                    job_id=job_id,
                )
                deepgram_payload = await call_deepgram_api_from_bytes(
                    audio_bytes=audio_bytes,
                    content_type=content_type,
                    job_id=job_id,
                )
                deepgram_mode_used = "push"
                log_event(
                    logger,
                    logging.INFO,
                    "transcription.push_fallback.succeeded",
                    "Push-mode fallback transcription succeeded",
                    provider="deepgram",
                    job_id=job_id,
                    audio_size_bytes=len(audio_bytes),
                )
    else:
        raise NonRetryableDeepgramError(
            "Missing required field: audio_url or audio_s3_key"
        )
    transcription_duration = time.time() - started

    transcript = extract_transcript(deepgram_payload)
    transcript_text = transcript["text"]

    # --- Quota settlement (task-250 Layer 2) --------------------------------
    # Deepgram has now told us how much audio it billed. Reconcile the user's
    # monthly counter with that figure before anything else, so a later failure
    # (S3 upload, event publication) cannot lose the debit. The settlement only
    # applies the delta with what the producer already debited at its gate, and
    # is idempotent per job, so an SQS redelivery cannot debit twice.
    billed_audio_seconds = float(transcript.get("audio_duration_seconds") or 0.0)
    minutes_used = (
        max(1, ceil(billed_audio_seconds / 60)) if billed_audio_seconds > 0 else 1
    )
    await _settle_audio_quota(
        message_body=message_body,
        job=job,
        job_id=job_id,
        billed_audio_seconds=billed_audio_seconds,
    )

    transcript_s3_key = f"{job_id}.txt"
    await upload_transcription(transcript_s3_key, transcript_text)

    transcription_metadata = {
        "provider": "deepgram",
        "deepgram_mode": deepgram_mode_used,
        "request_id": transcript.get("request_id"),
        "model_used": DEEPGRAM_MODEL,
        "language": transcript.get("language"),
        "segments_count": transcript.get("segments_count", 0),
        "duration_seconds": transcription_duration,
        # Length of the audio itself, as billed by Deepgram — not to be confused
        # with `duration_seconds` above, which is how long the call took.
        "audio_duration_seconds": billed_audio_seconds,
        "audio_url": audio_url.strip() if isinstance(audio_url, str) and audio_url.strip() else None,
        "audio_s3_key": audio_s3_key.strip()
        if isinstance(audio_s3_key, str) and audio_s3_key.strip()
        else None,
        "content_mime_type": message_body.get("content_mime_type"),
        "transcribed_at": time.strftime(
            "%Y-%m-%dT%H:%M:%SZ", time.gmtime()
        ),
    }

    if job:
        job.set_transcription_location(transcript_s3_key)
        job.set_transcription_metadata(transcription_metadata)
        job.set_processing_duration("transcription", int(transcription_duration))
        await database_async.update_processing_job(job)

    await sqs.send_message(
        queue_name=EPISODE_COMPLETED_EVENTS_QUEUE,
        message_body={
            "event_type": "episode_completion_status",
            "status": "success",
            "media_key": message_body.get("media_key"),
            "canonical_job_id": job_id,
            "minutes_used": minutes_used,
            "transcription_s3_key": transcript_s3_key,
            "transcription_metadata": transcription_metadata,
        },
    )

    # Search indexing (Algolia) is enqueued centrally by the media-completed
    # events consumer once it receives this episode_completion_status event.

    # Mark the canonical job as completed now that transcription is done.
    if job:
        job.mark_completed()
        await database_async.update_processing_job(job)

    # Publish episode_completed event for watcher fan-out via media_completed_worker.
    # This enables watchers of shared media keys to get their jobs finalized.
    try:
        await sqs.send_message(
            queue_name=EPISODE_COMPLETED_EVENTS_QUEUE,
            message_body={
                "event_type": "episode_completed",
                "media_key": message_body.get("media_key"),
                "canonical_job_id": job_id,
                "minutes_used": minutes_used,
                "transcription_s3_key": transcript_s3_key,
            },
        )
    except Exception as e:
        log_event(
            logger,
            logging.WARNING,
            "event.publish_failed",
            "Failed to publish episode_completed event for watcher fan-out",
            job_id=job_id,
            media_key=message_body.get("media_key"),
            exc_info=e,
        )

    log_event(
        logger,
        logging.INFO,
        "transcription.completed",
        "Deepgram transcription completed",
        provider="deepgram",
        transcript_source="deepgram",
        job_id=job_id,
        media_item_id=job_id,
    )


async def process_message(message: Dict[str, Any]) -> None:
    receipt_handle = message.get("ReceiptHandle")
    heartbeat_task: Optional[asyncio.Task] = None
    body: Dict[str, Any] = {}

    async def _heartbeat_loop() -> None:
        try:
            await sqs.change_message_visibility(
                queue_name=DEEPGRAM_TRANSCRIPTION_QUEUE,
                receipt_handle=receipt_handle,
                timeout_seconds=DEEPGRAM_VISIBILITY_TIMEOUT,
            )
            while True:
                await asyncio.sleep(HEARTBEAT_INTERVAL)
                await sqs.change_message_visibility(
                    queue_name=DEEPGRAM_TRANSCRIPTION_QUEUE,
                    receipt_handle=receipt_handle,
                    timeout_seconds=DEEPGRAM_VISIBILITY_TIMEOUT,
                )
        except asyncio.CancelledError:
            pass
        except Exception as e:
            log_event(
                logger,
                logging.WARNING,
                "external_call.failed",
                "Deepgram heartbeat failed",
                provider="sqs",
                queue=DEEPGRAM_TRANSCRIPTION_QUEUE,
                exc_info=e,
            )

    try:
        body = json.loads(message.get("Body", "{}"))
        context_token = bind_log_context(
            job_id=body.get("job_id"),
            media_item_id=body.get("job_id"),
            queue=DEEPGRAM_TRANSCRIPTION_QUEUE,
            provider="deepgram",
            transcript_source="deepgram",
        )
        if receipt_handle:
            heartbeat_task = asyncio.create_task(_heartbeat_loop())

        await process_deepgram_message(body)
    except NonRetryableDeepgramError as e:
        await publish_failure_event(
            job_id=body.get("job_id"),
            media_key=body.get("media_key"),
            reason=f"deepgram_non_retryable: {e}",
        )
        log_event(
            logger,
            logging.ERROR,
            "transcription.failed",
            "Deepgram transcription failed with non-retryable error",
            job_id=body.get("job_id"),
            media_item_id=body.get("job_id"),
            provider="deepgram",
            transcript_source="deepgram",
            error_code="deepgram_non_retryable",
            detail=str(e),
        )
        return
    except Exception as e:
        receive_count = int(
            (message.get("Attributes") or {}).get("ApproximateReceiveCount", "1")
        )
        if receive_count >= WORKER_MAX_RETRIES:
            try:
                await publish_failure_event(
                    job_id=body.get("job_id"),
                    media_key=body.get("media_key"),
                    reason=f"deepgram_failed_after_retries: {e}",
                )
            except Exception as publish_error:
                log_event(
                    logger,
                    logging.WARNING,
                    "external_call.failed",
                    "Failed to publish final Deepgram failure event",
                    provider="sqs",
                    queue=EPISODE_COMPLETED_EVENTS_QUEUE,
                    job_id=body.get("job_id"),
                    exc_info=publish_error,
                )
        raise
    finally:
        if "context_token" in locals():
            reset_log_context(context_token)
        if heartbeat_task:
            heartbeat_task.cancel()
            try:
                await heartbeat_task
            except asyncio.CancelledError:
                pass
            except Exception:
                pass


async def poll_queue() -> None:
    log_event(
        logger,
        logging.INFO,
        "worker.started",
        "Starting Deepgram transcription worker",
        queue=DEEPGRAM_TRANSCRIPTION_QUEUE,
        provider="deepgram",
    )

    while True:
        try:
            messages = await sqs.receive_messages(
                queue_name=DEEPGRAM_TRANSCRIPTION_QUEUE,
                max_messages=1,
                wait_time_seconds=20,
                visibility_timeout=DEEPGRAM_VISIBILITY_TIMEOUT,
            )
            if messages:
                for message in messages:
                    await process_message_with_retry(
                        message=message,
                        processor=process_message,
                        queue_name=DEEPGRAM_TRANSCRIPTION_QUEUE,
                        max_retries=WORKER_MAX_RETRIES,
                        worker_name="deepgram_transcription",
                    )
            await asyncio.sleep(1)
        except Exception as e:
            log_event(
                logger,
                logging.ERROR,
                "worker.polling_error",
                "Deepgram queue polling failed",
                queue=DEEPGRAM_TRANSCRIPTION_QUEUE,
                provider="deepgram",
                exc_info=e,
            )
            await asyncio.sleep(5)


async def main() -> None:
    setup_logging("deepgram-worker")
    await poll_queue()


if __name__ == "__main__":
    asyncio.run(main())
