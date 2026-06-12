"""
Queue-first YouTube ingestion worker.

Pipeline (yt-dlp primary, Apify fallback for IP blocks):
- Consumes messages from YOUTUBE_INGESTION_QUEUE
- Runs yt-dlp extract_info with subtitle options first
  - If native/auto subtitles found: upload transcript, complete
  - If no subtitles but media URL available: enqueue Deepgram (push mode)
  - If IP-blocked: fall back to Apify YouTube Transcript actor
- Apify fallback requests the configured transcript language and returns
  transcript text or fails terminally
"""

from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime, timezone
from io import BytesIO
import os
from typing import Any, Dict, Optional
from urllib.parse import parse_qs, urlsplit

import httpx
import yt_dlp

from media_summarizer.utils import database_async, s3, sqs
from media_summarizer.utils.logging_config import (
    bind_log_context,
    log_event,
    reset_log_context,
    setup_logging,
)
from media_summarizer.utils.ytdlp_helpers import (
    MediaStreamUnavailableError,
    SubtitleFetchError,
    SubtitleUnavailableError,
    collect_subtitle_candidates,
    fetch_subtitle_candidate,
    resolve_direct_media_url,
)
from media_summarizer.workers.base_worker import (
    get_sqs_receive_params,
    process_message_with_retry,
)

logger = logging.getLogger(__name__)

TRANSCRIPT_BUCKET = os.environ.get(
    "TRANSCRIPT_BUCKET", "media-summarizer-transcriptions"
)
YOUTUBE_INGESTION_QUEUE = os.environ.get(
    "YOUTUBE_INGESTION_QUEUE", "youtube-ingestion-queue"
)
DEEPGRAM_TRANSCRIPTION_QUEUE = os.environ.get(
    "DEEPGRAM_TRANSCRIPTION_QUEUE", "deepgram-transcription-queue"
)
EPISODE_COMPLETED_EVENTS_QUEUE = os.environ.get(
    "EPISODE_COMPLETED_EVENTS_QUEUE", "episode-completed-events"
)
YTDLP_TIMEOUT_SECONDS = float(os.environ.get("YTDLP_TIMEOUT_SECONDS", "30"))
YOUTUBE_SUBTITLE_FETCH_TIMEOUT_SECONDS = float(
    os.environ.get("YOUTUBE_SUBTITLE_FETCH_TIMEOUT_SECONDS", "20")
)
YOUTUBE_WORKER_MAX_RETRIES = 3

# Apify configuration
APIFY_YOUTUBE_API_TOKEN = os.environ.get("APIFY_YOUTUBE_API_TOKEN", "")
APIFY_YOUTUBE_TRANSCRIPT_ACTOR_ID = os.environ.get(
    "APIFY_YOUTUBE_TRANSCRIPT_ACTOR_ID", ""
)
DEFAULT_YOUTUBE_TRANSCRIPT_LANGUAGE = os.environ.get(
    "YOUTUBE_TRANSCRIPT_LANGUAGE", "fr"
)
APIFY_API_BASE = "https://api.apify.com/v2"
APIFY_TIMEOUT_SECONDS = float(os.environ.get("APIFY_TIMEOUT_SECONDS", "60"))

_YTDLP_EXTRACTOR_VERSION = "v1"

_UNAVAILABLE_MESSAGE = "This YouTube video is unavailable or cannot be processed."
_TEMPORARY_MESSAGE = (
    "YouTube extraction is temporarily unavailable. Please retry."
)
_GEO_RESTRICTED_MESSAGE = (
    "This YouTube video is geo-restricted and cannot be accessed."
)
_AGE_RESTRICTED_MESSAGE = (
    "This YouTube video is age-restricted and cannot be processed."
)


# ---------------------------------------------------------------------------
# Error classes
# ---------------------------------------------------------------------------


class NativeSubtitlesUnavailable(Exception):
    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


class YouTubeIngestionError(Exception):
    def __init__(
        self,
        code: str,
        *,
        details: Optional[str] = None,
        retryable: bool = False,
        user_message: Optional[str] = None,
    ) -> None:
        super().__init__(details or code)
        self.code = code
        self.details = (details or "").strip()
        self.retryable = retryable
        self.user_message = user_message or "Unable to process this YouTube URL."


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _now_iso_utc() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _normalize_language_code(value: Any) -> Optional[str]:
    if not isinstance(value, str):
        return None
    normalized = value.strip().replace("_", "-").lower()
    if not normalized:
        return None
    return normalized.split("-", 1)[0].strip() or None


def _requested_transcript_language(message_body: Dict[str, Any]) -> str:
    for key in ("transcript_language", "language", "locale"):
        language = _normalize_language_code(message_body.get(key))
        if language:
            return language
    return _normalize_language_code(DEFAULT_YOUTUBE_TRANSCRIPT_LANGUAGE) or "fr"


def _apify_actor_id_for_api(actor_id: str) -> str:
    return actor_id.strip().replace("/", "~")


def _extract_video_id(normalized_url: str) -> str:
    split = urlsplit((normalized_url or "").strip())
    host = (split.hostname or "").lower()
    path = split.path or ""
    parts = [segment for segment in path.split("/") if segment]
    query = parse_qs(split.query)

    if host in {"youtube.com", "www.youtube.com", "m.youtube.com", "music.youtube.com"}:
        if path == "/watch":
            video_id = (query.get("v") or [""])[0].strip()
            if video_id:
                return video_id
        if len(parts) >= 2 and parts[0] in {"shorts", "embed", "live"}:
            return parts[1].strip()
    if host in {"youtu.be", "www.youtu.be"} and parts:
        return parts[0].strip()
    raise YouTubeIngestionError(
        "youtube_unavailable",
        details="missing_video_id",
        retryable=False,
        user_message=_UNAVAILABLE_MESSAGE,
    )


def _is_ip_blocked_youtube_error(exc: Exception) -> bool:
    """Detect YouTube IP-block / login-wall errors from yt-dlp.

    yt-dlp may emit the message with a Unicode right single quotation mark
    (U+2019, e.g. "Sign in to confirm you’re not a bot") instead of an ASCII
    apostrophe. Normalize both before substring matching.
    """
    msg = str(exc).lower().replace("’", "'")
    return any(
        token in msg
        for token in (
            "sign in to confirm you're not a bot",
            "confirm you're not a bot",
            "failed to extract any player response",
        )
    )


def _is_geo_restricted_error(exc: Exception) -> bool:
    """Detect geo-restriction errors."""
    msg = str(exc).lower()
    return any(
        token in msg
        for token in (
            "geo restricted",
            "geo-restricted",
            "not available in your country",
            "blocked in your country",
            "video is not available in your region",
        )
    )


def _is_age_restricted_error(exc: Exception) -> bool:
    """Detect age-restriction errors."""
    msg = str(exc).lower()
    return any(
        token in msg
        for token in (
            "age-restricted",
            "age restricted",
            "sign in to confirm your age",
            "confirm your age",
            "age gate",
            "age_gate",
        )
    )


def _is_unavailable_error(exc: Exception) -> bool:
    """Detect video unavailable/deleted/private errors."""
    msg = str(exc).lower()
    return any(
        token in msg
        for token in (
            "unavailable",
            "private video",
            "private",
            "deleted",
            "removed",
            "members-only",
            "members only",
            "video is no longer available",
        )
    )


# ---------------------------------------------------------------------------
# yt-dlp primary extraction
# ---------------------------------------------------------------------------


async def _extract_youtube_info(normalized_url: str) -> Dict[str, Any]:
    """
    Run yt-dlp extract_info with subtitle retrieval options.

    Returns the info dict on success.
    Raises YouTubeIngestionError with specific codes on failure.
    Sets a flag on the raised error if it's an IP-block (caller should fallback to Apify).
    """
    ydl_opts = {
        "quiet": True,
        "no_warnings": True,
        "skip_download": True,
        "writesubtitles": True,
        "writeautomaticsub": True,
        "subtitleslangs": ["all"],
        "socket_timeout": YTDLP_TIMEOUT_SECONDS,
    }

    def _extract() -> Dict[str, Any]:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            return ydl.extract_info(normalized_url, download=False)

    try:
        return await asyncio.wait_for(
            asyncio.to_thread(_extract),
            timeout=YTDLP_TIMEOUT_SECONDS,
        )
    except asyncio.TimeoutError as exc:
        raise YouTubeIngestionError(
            "youtube_ytdlp_timeout",
            details="yt_dlp_timeout",
            retryable=True,
            user_message=_TEMPORARY_MESSAGE,
        ) from exc
    except (yt_dlp.utils.DownloadError, Exception) as exc:
        if _is_ip_blocked_youtube_error(exc):
            raise YouTubeIPBlockedError(str(exc)) from exc
        if _is_geo_restricted_error(exc):
            raise YouTubeIngestionError(
                "youtube_geo_restricted",
                details=f"yt_dlp:{type(exc).__name__}",
                retryable=False,
                user_message=_GEO_RESTRICTED_MESSAGE,
            ) from exc
        if _is_age_restricted_error(exc):
            raise YouTubeIngestionError(
                "youtube_age_restricted",
                details=f"yt_dlp:{type(exc).__name__}",
                retryable=False,
                user_message=_AGE_RESTRICTED_MESSAGE,
            ) from exc
        if _is_unavailable_error(exc):
            raise YouTubeIngestionError(
                "youtube_unavailable",
                details=f"yt_dlp:{type(exc).__name__}",
                retryable=False,
                user_message=_UNAVAILABLE_MESSAGE,
            ) from exc
        # Other yt-dlp errors: fail terminally
        raise YouTubeIngestionError(
            "youtube_ytdlp_failed",
            details=f"yt_dlp:{type(exc).__name__}",
            retryable=False,
            user_message=_UNAVAILABLE_MESSAGE,
        ) from exc


class YouTubeIPBlockedError(Exception):
    """Raised when yt-dlp detects a YouTube IP block / login wall."""

    pass


# ---------------------------------------------------------------------------
# Subtitle fetching from yt-dlp info
# ---------------------------------------------------------------------------


def _language_preference_key(
    candidate: Dict[str, Any],
    preferred_language: Optional[str],
) -> int:
    if not preferred_language:
        return 1
    candidate_language = _normalize_language_code(candidate.get("language"))
    return 0 if candidate_language == preferred_language else 1


async def _fetch_native_subtitles(
    info: Dict[str, Any],
    *,
    preferred_language: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Try to extract subtitles from yt-dlp info dict.

    Prefers manual subtitles over auto-generated captions.
    Raises NativeSubtitlesUnavailable if no subtitles can be resolved.
    """
    candidates = collect_subtitle_candidates(info)
    if not candidates:
        raise NativeSubtitlesUnavailable("no_subtitles_in_info")
    candidates.sort(
        key=lambda candidate: _language_preference_key(
            candidate,
            preferred_language,
        )
    )

    last_unavailable_reason = "no_subtitles_in_info"
    for candidate in candidates:
        try:
            result = await fetch_subtitle_candidate(
                candidate,
                timeout_seconds=YOUTUBE_SUBTITLE_FETCH_TIMEOUT_SECONDS,
                platform_label="youtube",
            )
            result["fetched_at"] = _now_iso_utc()
            return result
        except SubtitleUnavailableError as exc:
            last_unavailable_reason = exc.reason
            continue
        except SubtitleFetchError as exc:
            raise YouTubeIngestionError(
                "youtube_subtitle_fetch_failed",
                details=exc.details,
                retryable=exc.retryable,
                user_message=_TEMPORARY_MESSAGE,
            ) from exc
    raise NativeSubtitlesUnavailable(last_unavailable_reason)


# ---------------------------------------------------------------------------
# Apify YouTube Transcript fallback
# ---------------------------------------------------------------------------


async def _fetch_apify_transcript(
    source_url: str,
    *,
    transcript_language: str,
) -> Dict[str, Any]:
    """
    Call the Apify YouTube Transcript actor to retrieve transcript text.

    Returns a dict with text, language, segments_count, source_detail, fetched_at.
    Raises YouTubeIngestionError if Apify fails or returns no transcript.
    """
    if not APIFY_YOUTUBE_API_TOKEN:
        raise YouTubeIngestionError(
            "youtube_unavailable",
            details="apify_token_missing",
            retryable=False,
            user_message=_UNAVAILABLE_MESSAGE,
        )

    actor_id = _apify_actor_id_for_api(APIFY_YOUTUBE_TRANSCRIPT_ACTOR_ID)
    if not actor_id:
        raise YouTubeIngestionError(
            "youtube_unavailable",
            details="apify_actor_missing",
            retryable=False,
            user_message=_UNAVAILABLE_MESSAGE,
        )

    run_url = (
        f"{APIFY_API_BASE}/acts/{actor_id}/run-sync-get-dataset-items"
    )
    params = {"token": APIFY_YOUTUBE_API_TOKEN}
    payload = {
        "include_transcript_text": True,
        "language": transcript_language,
        "youtube_url": source_url,
    }

    try:
        async with httpx.AsyncClient(timeout=APIFY_TIMEOUT_SECONDS) as client:
            response = await client.post(
                run_url,
                params=params,
                json=payload,
            )
    except (httpx.TimeoutException, httpx.TransportError) as exc:
        raise YouTubeIngestionError(
            "youtube_apify_failed",
            details=f"apify_network:{type(exc).__name__}",
            retryable=True,
            user_message=_TEMPORARY_MESSAGE,
        ) from exc

    if response.status_code == 402:
        raise YouTubeIngestionError(
            "youtube_apify_failed",
            details="apify_payment_required",
            retryable=False,
            user_message=_UNAVAILABLE_MESSAGE,
        )
    if response.status_code == 401 or response.status_code == 403:
        raise YouTubeIngestionError(
            "youtube_apify_failed",
            details=f"apify_auth_error:{response.status_code}",
            retryable=False,
            user_message=_UNAVAILABLE_MESSAGE,
        )
    if response.status_code >= 500:
        raise YouTubeIngestionError(
            "youtube_apify_failed",
            details=f"apify_server_error:{response.status_code}",
            retryable=True,
            user_message=_TEMPORARY_MESSAGE,
        )
    if response.status_code >= 400:
        raise YouTubeIngestionError(
            "youtube_apify_failed",
            details=f"apify_client_error:{response.status_code}",
            retryable=False,
            user_message=_UNAVAILABLE_MESSAGE,
        )

    try:
        items = response.json()
    except Exception:
        raise YouTubeIngestionError(
            "youtube_apify_failed",
            details="apify_invalid_json",
            retryable=False,
            user_message=_UNAVAILABLE_MESSAGE,
        )

    if not isinstance(items, list) or not items:
        raise YouTubeIngestionError(
            "youtube_unavailable",
            details="apify_no_results",
            retryable=False,
            user_message=_UNAVAILABLE_MESSAGE,
        )

    first_item = items[0]
    if not isinstance(first_item, dict):
        raise YouTubeIngestionError(
            "youtube_unavailable",
            details="apify_invalid_result",
            retryable=False,
            user_message=_UNAVAILABLE_MESSAGE,
        )

    transcript_text = (
        first_item["transcript_text"].strip()
        if isinstance(first_item.get("transcript_text"), str)
        else ""
    )

    if not transcript_text:
        raise YouTubeIngestionError(
            "youtube_unavailable",
            details="apify_empty_transcript",
            retryable=False,
            user_message=_UNAVAILABLE_MESSAGE,
        )

    return {
        "text": transcript_text,
        "language": _normalize_language_code(first_item.get("language"))
        or transcript_language,
        "requested_language": transcript_language,
        "segments_count": len(
            [line for line in transcript_text.splitlines() if line.strip()]
        ),
        "source_detail": "apify_youtube_transcript",
        "source_url": source_url,
        "fetched_at": _now_iso_utc(),
        "is_automatic": False,
    }


# ---------------------------------------------------------------------------
# S3 upload + event publishing
# ---------------------------------------------------------------------------


async def _upload_transcript(job_id: str, text: str) -> str:
    transcript_s3_key = f"{job_id}.txt"
    await s3.upload_file_object(
        bucket=TRANSCRIPT_BUCKET,
        key=transcript_s3_key,
        file_obj=BytesIO(text.encode("utf-8")),
        content_type="text/plain",
        metadata={
            "content-type": "text/plain",
            "job-type": "youtube-transcript",
            "provider": "native_transcript",
        },
    )
    return transcript_s3_key


async def _publish_success_event(
    *,
    job_id: str,
    media_key: Optional[str],
    transcript_s3_key: str,
    transcription_metadata: Dict[str, Any],
) -> None:
    await sqs.send_message(
        queue_name=EPISODE_COMPLETED_EVENTS_QUEUE,
        message_body={
            "event_type": "episode_completion_status",
            "status": "success",
            "media_key": media_key,
            "canonical_job_id": job_id,
            "minutes_used": 1,
            "transcription_s3_key": transcript_s3_key,
            "transcription_metadata": transcription_metadata,
        },
    )


async def _publish_failure_event(
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


# ---------------------------------------------------------------------------
# Metadata builders
# ---------------------------------------------------------------------------


def _build_native_subtitle_extraction_metadata(
    *,
    video_id: str,
    source_url: str,
    native_result: Dict[str, Any],
) -> Dict[str, Any]:
    return {
        "provider": "yt-dlp",
        "extractor": "yt_dlp",
        "extractor_version": _YTDLP_EXTRACTOR_VERSION,
        "strategy_used": "native_subtitles",
        "video_id": video_id,
        "source_url": source_url,
        "subtitle_language": native_result.get("language"),
        "subtitle_ext": native_result.get("ext"),
        "is_automatic_caption": native_result.get("is_automatic", False),
        "segments_count": native_result.get("segments_count"),
        "fetched_at": native_result["fetched_at"],
    }


def _build_native_subtitle_transcription_metadata(
    *,
    native_result: Dict[str, Any],
) -> Dict[str, Any]:
    return {
        "provider": "native_transcript",
        "model_used": "yt_dlp_youtube_subtitles",
        "language": native_result.get("language"),
        "segments_count": native_result.get("segments_count"),
        "duration_seconds": 0,
        "source_url": native_result.get("source_url"),
        "transcribed_at": native_result["fetched_at"],
        "source_detail": native_result["source_detail"],
    }


def _build_apify_extraction_metadata(
    *,
    video_id: str,
    source_url: str,
    apify_result: Dict[str, Any],
) -> Dict[str, Any]:
    return {
        "provider": "apify",
        "extractor": "apify_youtube_transcript",
        "extractor_version": "v1",
        "strategy_used": "apify_transcript",
        "video_id": video_id,
        "source_url": source_url,
        "requested_language": apify_result.get("requested_language"),
        "transcript_language": apify_result.get("language"),
        "segments_count": apify_result.get("segments_count"),
        "fetched_at": apify_result["fetched_at"],
    }


def _build_apify_transcription_metadata(
    *,
    apify_result: Dict[str, Any],
) -> Dict[str, Any]:
    return {
        "provider": "apify_transcript",
        "model_used": "apify_youtube_transcript_scraper",
        "language": apify_result.get("language"),
        "segments_count": apify_result.get("segments_count"),
        "duration_seconds": 0,
        "source_url": apify_result.get("source_url"),
        "transcribed_at": apify_result["fetched_at"],
        "source_detail": apify_result["source_detail"],
    }


def _build_deepgram_fallback_extraction_metadata(
    *,
    video_id: str,
    source_url: str,
    fallback_reason: str,
    audio_result: Dict[str, Any],
) -> Dict[str, Any]:
    return {
        "provider": "yt-dlp",
        "extractor": "yt_dlp",
        "extractor_version": _YTDLP_EXTRACTOR_VERSION,
        "strategy_used": "deepgram_via_ytdlp_url",
        "video_id": video_id,
        "source_url": source_url,
        "audio_url": audio_result["audio_url"],
        "audio_duration_seconds": audio_result["audio_duration_seconds"],
        "native_subtitle_fallback_reason": fallback_reason,
        "yt_dlp_format_id": audio_result.get("format_id"),
        "yt_dlp_format_note": audio_result.get("format_note"),
        "yt_dlp_ext": audio_result.get("ext"),
        "queued_at": _now_iso_utc(),
    }


# ---------------------------------------------------------------------------
# Job state management
# ---------------------------------------------------------------------------


async def _mark_job_failed(
    *,
    job_id: Optional[str],
    normalized_url: str,
    video_id: Optional[str],
    error: YouTubeIngestionError,
) -> None:
    if not job_id:
        return

    job = await database_async.get_processing_job_by_id(job_id)
    if not job:
        return

    job.extraction_metadata = {
        "provider": "youtube_ingestion_worker",
        "extractor": "youtube_ingestion_worker",
        "extractor_version": "v1",
        "strategy_used": "failed",
        "source_url": normalized_url,
        "video_id": video_id,
        "last_error_code": error.code,
        "failure_details": error.details or error.code,
        "failed_at": _now_iso_utc(),
    }
    job.mark_failed(
        error_message=error.user_message,
        error_step="youtube_ingestion",
    )
    await database_async.update_processing_job(job)


# ---------------------------------------------------------------------------
# Main message processor
# ---------------------------------------------------------------------------


async def process_youtube_message(message_body: Dict[str, Any]) -> Dict[str, Any]:
    job_id = (message_body.get("job_id") or "").strip()
    normalized_url = (message_body.get("normalized_url") or "").strip()

    if not job_id:
        raise YouTubeIngestionError(
            "youtube_unavailable",
            details="missing_job_id",
            retryable=False,
            user_message=_UNAVAILABLE_MESSAGE,
        )
    if not normalized_url:
        raise YouTubeIngestionError(
            "youtube_unavailable",
            details="missing_normalized_url",
            retryable=False,
            user_message=_UNAVAILABLE_MESSAGE,
        )

    job = await database_async.get_processing_job_by_id(job_id)
    if not job:
        raise YouTubeIngestionError(
            "youtube_unavailable",
            details=f"processing_job_not_found:{job_id}",
            retryable=False,
            user_message=_UNAVAILABLE_MESSAGE,
        )

    video_id = _extract_video_id(normalized_url)
    transcript_language = _requested_transcript_language(message_body)

    # -----------------------------------------------------------------------
    # PRIMARY PATH: yt-dlp extract_info
    # -----------------------------------------------------------------------
    ip_blocked = False
    info: Optional[Dict[str, Any]] = None

    try:
        info = await _extract_youtube_info(normalized_url)
    except YouTubeIPBlockedError:
        ip_blocked = True
    # Other YouTubeIngestionError (geo, age, unavailable, etc.) propagate up

    # -----------------------------------------------------------------------
    # IP-BLOCKED BRANCH: Apify fallback
    # -----------------------------------------------------------------------
    if ip_blocked:
        apify_result = await _fetch_apify_transcript(
            normalized_url,
            transcript_language=transcript_language,
        )

        transcript_s3_key = await _upload_transcript(job_id, apify_result["text"])
        transcription_metadata = _build_apify_transcription_metadata(
            apify_result=apify_result,
        )
        job.set_transcription_location(transcript_s3_key)
        job.set_transcription_metadata(transcription_metadata)
        job.extraction_metadata = _build_apify_extraction_metadata(
            video_id=video_id,
            source_url=normalized_url,
            apify_result=apify_result,
        )
        job.mark_completed()
        await database_async.update_processing_job(job)

        await _publish_success_event(
            job_id=job_id,
            media_key=message_body.get("media_key"),
            transcript_s3_key=transcript_s3_key,
            transcription_metadata=transcription_metadata,
        )

        return {
            "mode": "apify_transcript",
            "job_id": job_id,
            "media_key": message_body.get("media_key"),
            "video_id": video_id,
            "source_detail": "apify_youtube_transcript",
        }

    # -----------------------------------------------------------------------
    # YT-DLP SUCCEEDED: try native subtitles
    # -----------------------------------------------------------------------
    assert info is not None

    try:
        native_result = await _fetch_native_subtitles(
            info,
            preferred_language=transcript_language,
        )
    except NativeSubtitlesUnavailable as exc:
        # No subtitles available: resolve media URL and enqueue Deepgram
        try:
            audio_result = resolve_direct_media_url(info)
        except MediaStreamUnavailableError as media_exc:
            raise YouTubeIngestionError(
                "youtube_unavailable",
                details=f"no_media_url:{media_exc.reason}",
                retryable=False,
                user_message=_UNAVAILABLE_MESSAGE,
            ) from media_exc

        extraction_metadata = _build_deepgram_fallback_extraction_metadata(
            video_id=video_id,
            source_url=normalized_url,
            fallback_reason=exc.reason,
            audio_result=audio_result,
        )
        job.extraction_metadata = extraction_metadata
        job.episode_url = audio_result["audio_url"]
        await database_async.update_processing_job(job)

        await sqs.send_message(
            queue_name=DEEPGRAM_TRANSCRIPTION_QUEUE,
            message_body={
                "job_id": job.id,
                "user_id": message_body.get("user_id"),
                "user_email": message_body.get("user_email"),
                "audio_url": audio_result["audio_url"],
                "media_key": message_body.get("media_key"),
                "normalized_url": normalized_url,
                "episode_title": message_body.get("episode_title") or job.episode_title,
                "podcast_title": message_body.get("podcast_title") or job.podcast_title,
                "audio_duration_seconds": audio_result["audio_duration_seconds"],
                "deepgram_mode": "push",
            },
        )

        return {
            "mode": "deepgram_via_ytdlp_url",
            "job_id": job.id,
            "media_key": message_body.get("media_key"),
            "video_id": video_id,
            "fallback_reason": exc.reason,
        }

    # -----------------------------------------------------------------------
    # YT-DLP SUCCEEDED WITH SUBTITLES: upload and complete
    # -----------------------------------------------------------------------
    transcript_s3_key = await _upload_transcript(job_id, native_result["text"])
    transcription_metadata = _build_native_subtitle_transcription_metadata(
        native_result=native_result,
    )
    job.set_transcription_location(transcript_s3_key)
    job.set_transcription_metadata(transcription_metadata)
    job.extraction_metadata = _build_native_subtitle_extraction_metadata(
        video_id=video_id,
        source_url=normalized_url,
        native_result=native_result,
    )
    job.mark_completed()
    await database_async.update_processing_job(job)

    await _publish_success_event(
        job_id=job_id,
        media_key=message_body.get("media_key"),
        transcript_s3_key=transcript_s3_key,
        transcription_metadata=transcription_metadata,
    )

    return {
        "mode": "native_subtitles",
        "job_id": job_id,
        "media_key": message_body.get("media_key"),
        "video_id": video_id,
        "source_detail": native_result["source_detail"],
    }


# ---------------------------------------------------------------------------
# SQS message handler
# ---------------------------------------------------------------------------


async def process_message(message: Dict[str, Any]) -> None:
    body: Dict[str, Any] = {}

    try:
        body = json.loads(message.get("Body", "{}"))
    except Exception as exc:
        log_event(
            logger,
            logging.ERROR,
            "worker.invalid_message",
            "Invalid JSON in YouTube ingestion message",
            queue=YOUTUBE_INGESTION_QUEUE,
            exc_info=exc,
        )
        return

    context_token = bind_log_context(
        job_id=body.get("job_id"),
        media_item_id=body.get("job_id"),
        queue=YOUTUBE_INGESTION_QUEUE,
        resolver_key=body.get("resolver_key") or "youtube.default",
        source_platform="youtube",
    )

    receive_count = int(
        (message.get("Attributes") or {}).get("ApproximateReceiveCount", "1")
    )

    try:
        result = await process_youtube_message(body)
        mode = result["mode"]

        if mode == "native_subtitles":
            log_event(
                logger,
                logging.INFO,
                "transcription.completed",
                "YouTube native subtitles completed via yt-dlp",
                job_id=result["job_id"],
                media_item_id=result["job_id"],
                transcript_source="native_subtitles",
                fallback_strategy=result.get("source_detail"),
            )
        elif mode == "apify_transcript":
            log_event(
                logger,
                logging.INFO,
                "transcription.completed",
                "YouTube transcript completed via Apify fallback",
                job_id=result["job_id"],
                media_item_id=result["job_id"],
                transcript_source="apify_transcript",
                fallback_strategy="ip_blocked_apify_fallback",
            )
        elif mode == "deepgram_via_ytdlp_url":
            log_event(
                logger,
                logging.INFO,
                "transcription.enqueued",
                "YouTube queued Deepgram after no subtitles found in yt-dlp",
                job_id=result["job_id"],
                media_item_id=result["job_id"],
                queue=DEEPGRAM_TRANSCRIPTION_QUEUE,
                transcript_source="deepgram",
                fallback_strategy=result.get("fallback_reason"),
            )
    except YouTubeIngestionError as exc:
        should_retry = exc.retryable and receive_count < YOUTUBE_WORKER_MAX_RETRIES
        if should_retry:
            raise

        video_id = None
        normalized_url = (body.get("normalized_url") or "").strip()
        if normalized_url:
            try:
                video_id = _extract_video_id(normalized_url)
            except YouTubeIngestionError:
                video_id = None

        await _mark_job_failed(
            job_id=body.get("job_id"),
            normalized_url=normalized_url,
            video_id=video_id,
            error=exc,
        )
        reason = exc.code if not exc.details else f"{exc.code}:{exc.details}"
        await _publish_failure_event(
            job_id=body.get("job_id"),
            media_key=body.get("media_key"),
            reason=reason,
        )
        log_event(
            logger,
            logging.ERROR,
            "transcription.failed",
            "YouTube ingestion failed",
            job_id=body.get("job_id"),
            media_item_id=body.get("job_id"),
            error_code=exc.code,
            detail=exc.details,
        )
    except Exception as exc:
        if receive_count < YOUTUBE_WORKER_MAX_RETRIES:
            raise

        final_error = YouTubeIngestionError(
            "youtube_unavailable",
            details=f"unexpected:{type(exc).__name__}",
            retryable=False,
            user_message=_UNAVAILABLE_MESSAGE,
        )
        video_id = None
        normalized_url = (body.get("normalized_url") or "").strip()
        if normalized_url:
            try:
                video_id = _extract_video_id(normalized_url)
            except YouTubeIngestionError:
                video_id = None
        await _mark_job_failed(
            job_id=body.get("job_id"),
            normalized_url=normalized_url,
            video_id=video_id,
            error=final_error,
        )
        await _publish_failure_event(
            job_id=body.get("job_id"),
            media_key=body.get("media_key"),
            reason=f"{final_error.code}:{final_error.details}",
        )
        log_event(
            logger,
            logging.ERROR,
            "transcription.failed",
            "YouTube ingestion failed after retries",
            job_id=body.get("job_id"),
            media_item_id=body.get("job_id"),
            error_code=final_error.code,
            exc_info=exc,
        )
    finally:
        reset_log_context(context_token)


# ---------------------------------------------------------------------------
# Queue polling loop
# ---------------------------------------------------------------------------


async def poll_queue() -> None:
    log_event(
        logger,
        logging.INFO,
        "worker.started",
        "Starting YouTube ingestion worker",
        queue=YOUTUBE_INGESTION_QUEUE,
    )
    while True:
        try:
            receive_params = get_sqs_receive_params(visibility_timeout=300)
            messages = await sqs.receive_messages(
                queue_name=YOUTUBE_INGESTION_QUEUE,
                max_messages=receive_params["MaxNumberOfMessages"],
                wait_time_seconds=receive_params["WaitTimeSeconds"],
                visibility_timeout=receive_params["VisibilityTimeout"],
            )
            if messages:
                for message in messages:
                    await process_message_with_retry(
                        message=message,
                        processor=process_message,
                        queue_name=YOUTUBE_INGESTION_QUEUE,
                        max_retries=YOUTUBE_WORKER_MAX_RETRIES,
                        worker_name="youtube_ingestion",
                    )
            else:
                await asyncio.sleep(1)
        except Exception as exc:
            log_event(
                logger,
                logging.ERROR,
                "worker.polling_error",
                "YouTube ingestion polling failed",
                queue=YOUTUBE_INGESTION_QUEUE,
                exc_info=exc,
            )
            await asyncio.sleep(5)


async def main() -> None:
    setup_logging("youtube-ingestion-worker")
    await poll_queue()


if __name__ == "__main__":
    asyncio.run(main())
