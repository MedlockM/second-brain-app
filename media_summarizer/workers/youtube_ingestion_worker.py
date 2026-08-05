"""
Queue-first YouTube ingestion worker.

Pipeline (yt-dlp primary, Apify fallback for IP blocks):
- Consumes messages from YOUTUBE_INGESTION_QUEUE
- Runs yt-dlp extract_info with subtitle options first
  - If native/auto subtitles found: upload transcript, complete
  - If no subtitles but media URL available: enqueue Deepgram (push mode)
  - If IP-blocked: fall back to Apify YouTube Transcript actor
- Apify fallback requests the transcript language carried by the SQS message and
  returns transcript text or fails terminally

Transcript language (task-216)
------------------------------
The target language is NOT decided here. It is resolved by the API from the
user's ``reading_language`` preference (task-190), overridable per submission via
``transcript_language`` in ``POST /api/media/ingest-url``, and travels
API -> orchestrator -> SQS -> this worker. The worker only consumes it:

- yt-dlp path: ranks subtitle candidates so the requested language wins.
- Apify path: sends ``language`` in the actor input when the configured actor
  supports it, so the actor returns that language's captions directly (saves a
  downstream translation LLM call).

When the requested language is unavailable for a video, a language-aware actor
answers ``error_category="language_not_available"``; the worker then retries once
without ``language`` to get the video's default captions, and the task-192
pipeline (detection + GPT-5-nano translation) brings the transcript to the user's
reading_language downstream.

Apify actor dialects
--------------------
``APIFY_YOUTUBE_TRANSCRIPT_ACTOR_ID`` comes from Secrets Manager at runtime, so
code cannot assume which actor is configured (the Lambda bootstrap uses
``os.environ.setdefault``: the secret always wins over the code default). Each
supported actor therefore declares its own input/output dialect in
``_APIFY_ACTOR_DIALECTS``:

- ``starvibe~youtube-video-transcript``: accepts ``language`` (ISO 639-1),
  returns ``transcript_text`` — the language-aware target of task-216.
- ``scrape-creators~best-youtube-transcripts-scraper``: accepts only
  ``videoUrls``, returns ``transcript_only_text`` and an English language name.
  No language control possible.

An unknown actor id fails fast with ``apify_actor_unsupported`` instead of being
sent a payload it will reject with a generic 400.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
from datetime import datetime, timezone
from enum import Enum
from io import BytesIO
from typing import Any, Dict, Optional
from urllib.parse import parse_qs, urlsplit

import httpx
import yt_dlp

from media_summarizer.utils import database_async, s3, sqs
from media_summarizer.utils.language_codes import (
    normalize_language_code,
    resolve_language_code,
)
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
# The runtime value always comes from Secrets Manager (the Lambda bootstrap uses
# `os.environ.setdefault`, so the secret wins over this default). It is set to
# the language-aware actor targeted by task-216, but switching a deployed
# environment REQUIRES updating `APIFY_YOUTUBE_TRANSCRIPT_ACTOR_ID` in the
# runtime secret — see docs/INGESTION_WORKERS_PROVIDERS.md, "Rollout
# prerequisite". Both actors below are supported, so a lagging secret degrades
# to "no language control" instead of failing.
APIFY_YOUTUBE_TRANSCRIPT_ACTOR_ID = os.environ.get(
    "APIFY_YOUTUBE_TRANSCRIPT_ACTOR_ID", "starvibe~youtube-video-transcript"
)
APIFY_API_BASE = "https://api.apify.com/v2"
APIFY_TIMEOUT_SECONDS = float(os.environ.get("APIFY_TIMEOUT_SECONDS", "60"))

_STARVIBE_ACTOR = "starvibe~youtube-video-transcript"
_SCRAPE_CREATORS_ACTOR = "scrape-creators~best-youtube-transcripts-scraper"

# Per-actor input/output dialects. Verified live against the Apify build schemas
# on 2026-08-05. `supports_language` drives whether task-216 can request the
# user's reading_language at all on the Apify path.
_APIFY_ACTOR_DIALECTS: Dict[str, Dict[str, Any]] = {
    _STARVIBE_ACTOR: {
        "supports_language": True,
        "url_field": "youtube_url",
        "url_is_list": False,
        "text_fields": ("transcript_text",),
        "extra_input": {"include_transcript_text": True},
    },
    _SCRAPE_CREATORS_ACTOR: {
        "supports_language": False,
        "url_field": "videoUrls",
        "url_is_list": True,
        "text_fields": ("transcript_only_text",),
        "extra_input": {},
    },
}

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


class ApifyTranscriptFailure(str, Enum):
    """Stable failure details for the Apify YouTube transcript branch.

    Surfaced in ``YouTubeIngestionError.details`` (and therefore in job
    ``extraction_metadata.failure_details`` and the failure event reason), so
    they are part of the observability contract: do not rename without updating
    dashboards/alarms.
    """

    TOKEN_MISSING = "apify_token_missing"
    ACTOR_MISSING = "apify_actor_missing"
    # Configured actor id has no known input/output dialect: raised before any
    # HTTP call so a misconfigured runtime secret is diagnosable instead of
    # surfacing as an opaque provider 400.
    ACTOR_UNSUPPORTED = "apify_actor_unsupported"
    NETWORK_ERROR = "apify_network"
    PAYMENT_REQUIRED = "apify_payment_required"
    AUTH_ERROR = "apify_auth_error"
    SERVER_ERROR = "apify_server_error"
    CLIENT_ERROR = "apify_client_error"
    INVALID_JSON = "apify_invalid_json"
    NO_RESULTS = "apify_no_results"
    INVALID_RESULT = "apify_invalid_result"
    ACTOR_ERROR = "apify_actor_error"
    EMPTY_TRANSCRIPT = "apify_empty_transcript"


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


def _requested_transcript_language(message_body: Dict[str, Any]) -> Optional[str]:
    """Target transcript language carried by the SQS message (task-216).

    ``transcript_language`` is the value the API resolved from the request
    override or the user's ``reading_language``. ``language``/``locale`` remain
    accepted as weaker hints for messages produced outside the API path.

    Returns ``None`` when the message carries no usable language: there is
    deliberately NO hard-coded default anymore, so we never silently ask a
    provider for a language the user never picked.
    """
    for key in ("transcript_language", "language", "locale"):
        language = normalize_language_code(message_body.get(key))
        if language:
            return language
    return None


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
    candidate_language = normalize_language_code(candidate.get("language"))
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


def _apify_actor_dialect(actor_id: str) -> Dict[str, Any]:
    """Return the input/output dialect for the configured actor.

    Raises ``apify_actor_unsupported`` when the runtime secret names an actor
    this worker does not know how to talk to, naming the offending id and the
    supported set so the misconfiguration is immediately actionable.
    """
    normalized = _apify_actor_id_for_api(actor_id)
    dialect = _APIFY_ACTOR_DIALECTS.get(normalized)
    if dialect is None:
        log_event(
            logger,
            logging.ERROR,
            "config.actor_unsupported",
            (
                "APIFY_YOUTUBE_TRANSCRIPT_ACTOR_ID names an actor this worker has "
                "no payload dialect for; update the runtime secret to a supported "
                "actor before relying on the Apify fallback"
            ),
            configured_actor_id=normalized,
            supported_actor_ids=sorted(_APIFY_ACTOR_DIALECTS),
            transcript_source="apify_transcript",
        )
        raise YouTubeIngestionError(
            "youtube_unavailable",
            details=(
                f"{ApifyTranscriptFailure.ACTOR_UNSUPPORTED.value}:{normalized}"
            ),
            retryable=False,
            user_message=_UNAVAILABLE_MESSAGE,
        )
    return dialect


def _build_apify_transcript_payload(
    source_url: str,
    *,
    transcript_language: Optional[str],
    dialect: Dict[str, Any],
) -> Dict[str, Any]:
    """Build the Apify actor input for one video, in the actor's own dialect.

    ``language`` (bare ISO 639-1) is only sent to actors that declare
    ``supports_language``; sending it to an actor that does not accept it would
    be rejected as ``invalid-input``. It is also omitted when the target
    language is unknown, in which case the actor picks the video's default
    caption track.
    """
    url_value = [source_url] if dialect["url_is_list"] else source_url
    payload: Dict[str, Any] = {dialect["url_field"]: url_value}
    payload.update(dialect["extra_input"])
    if transcript_language and dialect["supports_language"]:
        payload["language"] = transcript_language
    return payload


async def _run_apify_transcript_actor(
    payload: Dict[str, Any],
) -> Dict[str, Any]:
    """Run the Apify actor synchronously and return its first dataset item.

    Raises YouTubeIngestionError with a stable ``ApifyTranscriptFailure`` detail
    on transport, credential, or payload-shape problems. Actor-level errors
    (``status="error"`` in the item) are returned to the caller as-is so it can
    decide whether they are recoverable (e.g. language fallback).
    """
    if not APIFY_YOUTUBE_API_TOKEN:
        raise YouTubeIngestionError(
            "youtube_unavailable",
            details=ApifyTranscriptFailure.TOKEN_MISSING.value,
            retryable=False,
            user_message=_UNAVAILABLE_MESSAGE,
        )

    actor_id = _apify_actor_id_for_api(APIFY_YOUTUBE_TRANSCRIPT_ACTOR_ID)
    if not actor_id:
        raise YouTubeIngestionError(
            "youtube_unavailable",
            details=ApifyTranscriptFailure.ACTOR_MISSING.value,
            retryable=False,
            user_message=_UNAVAILABLE_MESSAGE,
        )

    run_url = (
        f"{APIFY_API_BASE}/acts/{actor_id}/run-sync-get-dataset-items"
    )
    params = {"token": APIFY_YOUTUBE_API_TOKEN}

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
            details=(
                f"{ApifyTranscriptFailure.NETWORK_ERROR.value}:{type(exc).__name__}"
            ),
            retryable=True,
            user_message=_TEMPORARY_MESSAGE,
        ) from exc

    if response.status_code == 402:
        raise YouTubeIngestionError(
            "youtube_apify_failed",
            details=ApifyTranscriptFailure.PAYMENT_REQUIRED.value,
            retryable=False,
            user_message=_UNAVAILABLE_MESSAGE,
        )
    if response.status_code in (401, 403):
        raise YouTubeIngestionError(
            "youtube_apify_failed",
            details=(
                f"{ApifyTranscriptFailure.AUTH_ERROR.value}:{response.status_code}"
            ),
            retryable=False,
            user_message=_UNAVAILABLE_MESSAGE,
        )
    if response.status_code >= 500:
        raise YouTubeIngestionError(
            "youtube_apify_failed",
            details=(
                f"{ApifyTranscriptFailure.SERVER_ERROR.value}:{response.status_code}"
            ),
            retryable=True,
            user_message=_TEMPORARY_MESSAGE,
        )
    if response.status_code >= 400:
        raise YouTubeIngestionError(
            "youtube_apify_failed",
            details=(
                f"{ApifyTranscriptFailure.CLIENT_ERROR.value}:{response.status_code}"
            ),
            retryable=False,
            user_message=_UNAVAILABLE_MESSAGE,
        )

    try:
        items = response.json()
    except Exception:
        raise YouTubeIngestionError(
            "youtube_apify_failed",
            details=ApifyTranscriptFailure.INVALID_JSON.value,
            retryable=False,
            user_message=_UNAVAILABLE_MESSAGE,
        )

    if not isinstance(items, list) or not items:
        raise YouTubeIngestionError(
            "youtube_unavailable",
            details=ApifyTranscriptFailure.NO_RESULTS.value,
            retryable=False,
            user_message=_UNAVAILABLE_MESSAGE,
        )

    first_item = items[0]
    if not isinstance(first_item, dict):
        raise YouTubeIngestionError(
            "youtube_unavailable",
            details=ApifyTranscriptFailure.INVALID_RESULT.value,
            retryable=False,
            user_message=_UNAVAILABLE_MESSAGE,
        )
    return first_item


def _apify_item_transcript_text(item: Dict[str, Any], dialect: Dict[str, Any]) -> str:
    """Extract the plain transcript text from an actor dataset item.

    Each actor names its flat transcript field differently
    (``transcript_text`` for starvibe, ``transcript_only_text`` for
    scrape-creators), so the field names come from the dialect. Both actors also
    return a timestamped ``transcript`` segment array, used as a fallback when
    the flat field is missing.
    """
    for field in dialect["text_fields"]:
        flat = item.get(field)
        if isinstance(flat, str) and flat.strip():
            return flat.strip()

    segments = item.get("transcript")
    if isinstance(segments, list):
        lines = [
            str(segment.get("text")).strip()
            for segment in segments
            if isinstance(segment, dict) and str(segment.get("text") or "").strip()
        ]
        if lines:
            return "\n".join(lines)
    return ""


def _is_language_not_available(item: Dict[str, Any]) -> bool:
    """Whether the actor refused the run only because the language is missing."""
    return (
        str(item.get("status") or "").strip().lower() == "error"
        and str(item.get("error_category") or "").strip().lower()
        == "language_not_available"
    )


async def _fetch_apify_transcript(
    source_url: str,
    *,
    transcript_language: Optional[str],
) -> Dict[str, Any]:
    """
    Call the Apify YouTube Transcript actor to retrieve transcript text.

    The requested ``transcript_language`` (the user's reading_language, or the
    per-request override — see task-216) is sent to the actor so the returned
    captions are already in the target language when the video offers them.
    If the actor reports the language is unavailable, we retry once without
    ``language`` to take the video's default track; the task-192 translation
    step then brings the transcript to the user's reading_language.

    When the configured actor cannot select a language, the request is logged as
    unhonoured and the video's default captions are used; task-192 still brings
    the transcript to the user's reading_language, at the cost of one LLM call.

    Returns a dict with text, language, segments_count, source_detail, fetched_at.
    Raises YouTubeIngestionError if Apify fails or returns no transcript.
    """
    dialect = _apify_actor_dialect(APIFY_YOUTUBE_TRANSCRIPT_ACTOR_ID)
    language_supported = bool(dialect["supports_language"])
    if transcript_language and not language_supported:
        log_event(
            logger,
            logging.WARNING,
            "transcription.language_request_unsupported",
            (
                "Configured Apify actor cannot select a transcript language; "
                "falling back to the video default captions and relying on the "
                "downstream translation step"
            ),
            transcript_source="apify_transcript",
            configured_actor_id=_apify_actor_id_for_api(
                APIFY_YOUTUBE_TRANSCRIPT_ACTOR_ID
            ),
            language_aware_actor_id=_STARVIBE_ACTOR,
            requested_language=transcript_language,
        )

    payload = _build_apify_transcript_payload(
        source_url,
        transcript_language=transcript_language,
        dialect=dialect,
    )
    item = await _run_apify_transcript_actor(payload)

    language_fallback = False
    if transcript_language and language_supported and _is_language_not_available(item):
        log_event(
            logger,
            logging.INFO,
            "transcription.language_fallback",
            "Requested transcript language unavailable on Apify; retrying with the video default",
            transcript_source="apify_transcript",
            requested_language=transcript_language,
            detail=str(item.get("message") or "")[:200],
        )
        language_fallback = True
        item = await _run_apify_transcript_actor(
            _build_apify_transcript_payload(
                source_url,
                transcript_language=None,
                dialect=dialect,
            )
        )

    if str(item.get("status") or "").strip().lower() == "error":
        raise YouTubeIngestionError(
            "youtube_unavailable",
            details=ApifyTranscriptFailure.ACTOR_ERROR.value,
            retryable=False,
            user_message=_UNAVAILABLE_MESSAGE,
        )

    transcript_text = _apify_item_transcript_text(item, dialect)
    if not transcript_text:
        raise YouTubeIngestionError(
            "youtube_unavailable",
            details=ApifyTranscriptFailure.EMPTY_TRANSCRIPT.value,
            retryable=False,
            user_message=_UNAVAILABLE_MESSAGE,
        )

    segments = item.get("transcript")
    segments_count = (
        len(segments)
        if isinstance(segments, list) and segments
        else len([line for line in transcript_text.splitlines() if line.strip()])
    )

    return {
        "text": transcript_text,
        # Language actually delivered by the actor; may differ from the request
        # when we fell back to the video default or the actor cannot select a
        # language at all (task-192 translates downstream). Resolved through
        # `resolve_language_code` because scrape-creators reports an English
        # display name ("English") where starvibe reports a code ("en").
        "language": resolve_language_code(item.get("language")),
        "requested_language": transcript_language,
        "language_supported": language_supported,
        "language_fallback": language_fallback,
        "selected_language_label": item.get("selected_language")
        or item.get("language"),
        "actor_id": _apify_actor_id_for_api(APIFY_YOUTUBE_TRANSCRIPT_ACTOR_ID),
        "segments_count": segments_count,
        "source_detail": "apify_youtube_transcript",
        "source_url": source_url,
        "fetched_at": _now_iso_utc(),
        "is_automatic": bool(item.get("is_auto_generated")),
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
    requested_language: Optional[str],
) -> Dict[str, Any]:
    return {
        "provider": "yt-dlp",
        "extractor": "yt_dlp",
        "extractor_version": _YTDLP_EXTRACTOR_VERSION,
        "strategy_used": "native_subtitles",
        "video_id": video_id,
        "source_url": source_url,
        "requested_language": requested_language,
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
        "actor_id": apify_result.get("actor_id"),
        "requested_language": apify_result.get("requested_language"),
        "transcript_language": apify_result.get("language"),
        # False when the configured actor has no language input at all: the
        # request could not be honoured, so a downstream translation is expected.
        "language_supported": apify_result.get("language_supported", False),
        "language_fallback": apify_result.get("language_fallback", False),
        "selected_language_label": apify_result.get("selected_language_label"),
        "is_automatic_caption": apify_result.get("is_automatic", False),
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
        "actor_id": apify_result.get("actor_id"),
        # Language of the delivered transcript. Consumed by task-192
        # (`job_source_language_hint`) to decide whether a translation to the
        # user's reading_language is still needed.
        "language": apify_result.get("language"),
        "requested_language": apify_result.get("requested_language"),
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
            "requested_language": transcript_language,
            "transcript_language": apify_result.get("language"),
            "language_supported": apify_result.get("language_supported"),
            "language_fallback": apify_result.get("language_fallback"),
            "actor_id": apify_result.get("actor_id"),
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
        requested_language=transcript_language,
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
        "requested_language": transcript_language,
        "transcript_language": normalize_language_code(native_result.get("language")),
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
                requested_language=result.get("requested_language"),
                transcript_language=result.get("transcript_language"),
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
                requested_language=result.get("requested_language"),
                transcript_language=result.get("transcript_language"),
                language_supported=result.get("language_supported"),
                language_fallback=result.get("language_fallback"),
                actor_id=result.get("actor_id"),
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
