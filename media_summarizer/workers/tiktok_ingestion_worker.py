"""
Queue-first TikTok ingestion worker.

Pipeline:
- Consumes messages from TIKTOK_INGESTION_QUEUE
- Attempts native subtitle retrieval through yt-dlp metadata first
- Uploads native transcript text to S3 and publishes completion events on success
- Falls back to a direct remote media URL and reuses the Deepgram queue
"""

from __future__ import annotations

import asyncio
import html
from io import BytesIO
import json
import logging
from datetime import datetime, timezone
import os
import re
from typing import Any, Dict, Optional
from urllib.parse import urlsplit

import httpx
import yt_dlp

from media_summarizer.core.config import settings
from media_summarizer.utils import database_async, s3, sqs
from media_summarizer.utils.logging_config import (
    bind_log_context,
    log_event,
    reset_log_context,
    setup_logging,
)
from media_summarizer.utils.tiktok_limiter import (
    TikTokRateLimitExceeded,
    acquire_tiktok_slot,
)
from media_summarizer.workers.base_worker import (
    get_sqs_receive_params,
    process_message_with_retry,
)

logger = logging.getLogger(__name__)

TRANSCRIPT_BUCKET = os.environ.get(
    "TRANSCRIPT_BUCKET", "media-summarizer-transcripts"
)
TIKTOK_INGESTION_QUEUE = os.environ.get(
    "TIKTOK_INGESTION_QUEUE", "tiktok-ingestion-queue"
)
DEEPGRAM_TRANSCRIPTION_QUEUE = os.environ.get(
    "DEEPGRAM_TRANSCRIPTION_QUEUE", "deepgram-transcription-queue"
)
EPISODE_COMPLETED_EVENTS_QUEUE = os.environ.get(
    "EPISODE_COMPLETED_EVENTS_QUEUE", "episode-completed-events"
)
YTDLP_TIMEOUT_SECONDS = float(os.environ.get("YTDLP_TIMEOUT_SECONDS", "30"))
TIKTOK_SUBTITLE_FETCH_TIMEOUT_SECONDS = float(
    os.environ.get("TIKTOK_SUBTITLE_FETCH_TIMEOUT_SECONDS", "20")
)
TIKTOK_WORKER_MAX_RETRIES = max(
    1, int(os.environ.get("TIKTOK_WORKER_MAX_RETRIES", "3"))
)

APIFY_API_BASE_URL = "https://api.apify.com/v2"

_YTDLP_EXTRACTOR_VERSION = "v1"
_AUDIO_URL_PROTOCOLS = {
    "http",
    "https",
    "http_dash_segments",
    "https_dash_segments",
}
_TIMESTAMP_LINE_RE = re.compile(
    r"^\s*(?:\d{1,2}:)?\d{2}:\d{2}[.,]\d{3}\s+-->\s+(?:\d{1,2}:)?\d{2}:\d{2}[.,]\d{3}"
)
_HTML_TAG_RE = re.compile(r"<[^>]+>")
_TEXT_KEYS = ("text", "content", "utterance", "caption")
_CONTAINER_KEYS = (
    "utterances",
    "segments",
    "captions",
    "subtitles",
    "body",
    "events",
    "lines",
    "paragraphs",
)

_UNAVAILABLE_MESSAGE = "This TikTok video is unavailable or cannot be processed."
_UNSUPPORTED_MESSAGE = "Unable to resolve transcribable media from this TikTok URL."
_TEMPORARY_EXTRACTOR_MESSAGE = (
    "TikTok extraction is temporarily unavailable. Please retry."
)
_RATE_LIMITED_MESSAGE = (
    "TikTok media extraction is temporarily rate limited. Please retry later."
)
_IP_BLOCKED_UNRECOVERABLE_MESSAGE = (
    "This TikTok video cannot be accessed from our servers. "
    "It may be restricted by TikTok."
)
_APIFY_ACTOR_FAILED_MESSAGE = (
    "TikTok extraction via fallback service failed due to a configuration error."
)
_APIFY_QUOTA_EXCEEDED_MESSAGE = (
    "TikTok fallback extraction quota exceeded. Please retry later."
)
_APIFY_TIMEOUT_MESSAGE = (
    "TikTok fallback extraction timed out. Please retry."
)


class NativeSubtitlesUnavailable(Exception):
    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


class TikTokIngestionError(Exception):
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
        self.user_message = user_message or _UNSUPPORTED_MESSAGE


def _now_iso_utc() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _looks_like_rate_limited_error(message: str) -> bool:
    normalized = (message or "").lower()
    return any(
        token in normalized
        for token in ("429", "rate limit", "rate-limited", "too many requests", "quota")
    )


def _looks_like_unavailable_error(message: str) -> bool:
    normalized = (message or "").lower()
    return any(
        token in normalized
        for token in (
            "unavailable",
            "private",
            "deleted",
            "not found",
            "status code 404",
            "video is unavailable",
        )
    )


def _is_ip_blocked_error(exc: Exception) -> bool:
    """Return True only for yt-dlp IP block errors (TikTok status 10204).

    This helper detects the specific TikTok anti-bot IP block that warrants
    fallback to Apify. It does NOT match geo-restriction, deleted videos,
    rate limits, or other yt-dlp errors.
    """
    message = str(exc).lower()
    if "ip address is blocked" in message:
        return True
    if "10204" in message:
        return True
    return False


def _extract_tiktok_id(normalized_url: str) -> str:
    split = urlsplit((normalized_url or "").strip())
    parts = [segment for segment in (split.path or "").split("/") if segment]

    if len(parts) >= 3 and parts[0].startswith("@") and parts[1] == "video":
        return parts[2].strip()
    if len(parts) >= 2 and parts[0] == "t":
        return parts[1].strip()

    raise TikTokIngestionError(
        "unsupported_content",
        details="missing_tiktok_id",
        retryable=False,
        user_message=_UNAVAILABLE_MESSAGE,
    )


def _is_valid_http_url(value: str) -> bool:
    candidate = (value or "").strip().lower()
    return candidate.startswith("http://") or candidate.startswith("https://")


def _subtitle_ext_priority(ext: str) -> int:
    normalized = (ext or "").strip().lower()
    if normalized == "vtt":
        return 4
    if normalized == "srt":
        return 3
    if normalized in {"json", "srv3"}:
        return 2
    return 1


def _collect_subtitle_candidates(info: Dict[str, Any]) -> list[Dict[str, Any]]:
    candidates: list[Dict[str, Any]] = []
    seen: set[tuple[str, str, str]] = set()

    requested_subtitles = info.get("requested_subtitles")
    if isinstance(requested_subtitles, dict):
        for language, item in requested_subtitles.items():
            if not isinstance(item, dict):
                continue
            url = str(item.get("url") or "").strip()
            ext = str(item.get("ext") or "").strip().lower()
            key = (language, ext, url)
            if key in seen:
                continue
            seen.add(key)
            candidates.append(
                {
                    "language": language,
                    "ext": ext,
                    "url": url,
                    "data": item.get("data"),
                    "requested": True,
                }
            )

    subtitles = info.get("subtitles")
    if isinstance(subtitles, dict):
        for language, entries in subtitles.items():
            if not isinstance(entries, list):
                continue
            for entry in entries:
                if not isinstance(entry, dict):
                    continue
                url = str(entry.get("url") or "").strip()
                ext = str(entry.get("ext") or "").strip().lower()
                key = (language, ext, url)
                if key in seen:
                    continue
                seen.add(key)
                candidates.append(
                    {
                        "language": language,
                        "ext": ext,
                        "url": url,
                        "data": entry.get("data"),
                        "requested": False,
                    }
                )

    candidates.sort(
        key=lambda item: (
            0 if item["requested"] else 1,
            -_subtitle_ext_priority(item["ext"]),
            item["language"],
        )
    )
    return candidates


def _clean_caption_line(line: str) -> str:
    stripped = _HTML_TAG_RE.sub("", html.unescape((line or "").strip()))
    return stripped.strip()


def _parse_timed_text_payload(payload: str) -> str:
    lines: list[str] = []
    for raw_line in payload.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        upper = line.upper()
        if upper.startswith(("WEBVTT", "NOTE", "STYLE", "REGION", "X-TIMESTAMP-MAP")):
            continue
        if _TIMESTAMP_LINE_RE.match(line):
            continue
        if line.isdigit():
            continue
        cleaned = _clean_caption_line(line)
        if cleaned:
            lines.append(cleaned)
    return "\n".join(lines).strip()


def _extract_json_caption_text(node: Any, collected: list[str], seen: set[str]) -> None:
    if isinstance(node, dict):
        for key in _TEXT_KEYS:
            value = node.get(key)
            if isinstance(value, str):
                cleaned = _clean_caption_line(value)
                if cleaned and cleaned not in seen:
                    seen.add(cleaned)
                    collected.append(cleaned)
        for key in _CONTAINER_KEYS:
            if key in node:
                _extract_json_caption_text(node[key], collected, seen)
        if not any(key in node for key in _CONTAINER_KEYS):
            for value in node.values():
                if isinstance(value, (dict, list)):
                    _extract_json_caption_text(value, collected, seen)
    elif isinstance(node, list):
        for item in node:
            _extract_json_caption_text(item, collected, seen)


def _parse_json_caption_payload(payload: str) -> str:
    data = json.loads(payload)
    collected: list[str] = []
    seen: set[str] = set()
    _extract_json_caption_text(data, collected, seen)
    return "\n".join(collected).strip()


def _parse_caption_payload(
    *,
    payload: str,
    ext: str,
    content_type: str,
) -> str:
    normalized_ext = (ext or "").strip().lower()
    normalized_content_type = (content_type or "").strip().lower()
    is_json = (
        normalized_ext in {"json", "srv3"}
        or "application/json" in normalized_content_type
        or payload.lstrip().startswith(("{", "["))
    )
    if is_json:
        return _parse_json_caption_payload(payload)
    return _parse_timed_text_payload(payload)


async def _fetch_subtitle_candidate(candidate: Dict[str, Any]) -> Dict[str, Any]:
    data = candidate.get("data")
    payload = ""
    content_type = ""

    if isinstance(data, (dict, list)):
        payload = json.dumps(data)
        content_type = "application/json"
    elif isinstance(data, str) and data.strip():
        payload = data
    else:
        subtitle_url = str(candidate.get("url") or "").strip()
        if not _is_valid_http_url(subtitle_url):
            raise NativeSubtitlesUnavailable("native_subtitles_absent")
        try:
            async with httpx.AsyncClient(
                timeout=TIKTOK_SUBTITLE_FETCH_TIMEOUT_SECONDS,
                follow_redirects=True,
            ) as client:
                response = await client.get(subtitle_url)
        except (httpx.TimeoutException, httpx.TransportError) as exc:
            raise TikTokIngestionError(
                "extractor_failed",
                details=f"subtitle_fetch:{type(exc).__name__}",
                retryable=True,
                user_message=_TEMPORARY_EXTRACTOR_MESSAGE,
            ) from exc
        if response.status_code >= 400:
            raise TikTokIngestionError(
                "extractor_failed",
                details=f"subtitle_http_status:{response.status_code}",
                retryable=response.status_code >= 500,
                user_message=_TEMPORARY_EXTRACTOR_MESSAGE,
            )
        payload = response.text
        content_type = response.headers.get("content-type", "")

    text = _parse_caption_payload(
        payload=payload,
        ext=str(candidate.get("ext") or ""),
        content_type=content_type,
    )
    if not text:
        raise NativeSubtitlesUnavailable("native_subtitles_absent")

    return {
        "text": text,
        "language": str(candidate.get("language") or "").strip() or None,
        "segments_count": len([line for line in text.splitlines() if line.strip()]),
        "source_detail": (
            f"tiktok_native_subtitles:{candidate.get('language') or 'unknown'}:"
            f"{candidate.get('ext') or 'unknown'}"
        ),
        "source_url": str(candidate.get("url") or "").strip() or None,
        "ext": str(candidate.get("ext") or "").strip() or None,
        "fetched_at": _now_iso_utc(),
    }


async def _extract_tiktok_info(normalized_url: str) -> Dict[str, Any]:
    ydl_opts = {
        "quiet": True,
        "no_warnings": True,
        "skip_download": True,
        "writesubtitles": True,
        "subtitleslangs": ["all"],
        "socket_timeout": YTDLP_TIMEOUT_SECONDS,
    }

    def _extract() -> Dict[str, Any]:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            return ydl.extract_info(normalized_url, download=False)

    try:
        await acquire_tiktok_slot()
        return await asyncio.wait_for(
            asyncio.to_thread(_extract),
            timeout=YTDLP_TIMEOUT_SECONDS,
        )
    except TikTokRateLimitExceeded as exc:
        raise TikTokIngestionError(
            "rate_limited",
            details=f"{exc.limit_type}:{exc.retry_after_seconds}",
            retryable=True,
            user_message=_RATE_LIMITED_MESSAGE,
        ) from exc
    except asyncio.TimeoutError as exc:
        raise TikTokIngestionError(
            "extractor_failed",
            details="yt_dlp_timeout",
            retryable=True,
            user_message=_TEMPORARY_EXTRACTOR_MESSAGE,
        ) from exc
    except yt_dlp.utils.DownloadError as exc:
        message = str(exc)
        if _looks_like_rate_limited_error(message):
            raise TikTokIngestionError(
                "rate_limited",
                details=type(exc).__name__,
                retryable=True,
                user_message=_RATE_LIMITED_MESSAGE,
            ) from exc
        if _looks_like_unavailable_error(message):
            raise TikTokIngestionError(
                "unsupported_content",
                details=type(exc).__name__,
                retryable=False,
                user_message=_UNAVAILABLE_MESSAGE,
            ) from exc
        raise TikTokIngestionError(
            "extractor_failed",
            details=type(exc).__name__,
            retryable=True,
            user_message=_TEMPORARY_EXTRACTOR_MESSAGE,
        ) from exc
    except Exception as exc:
        message = str(exc)
        if _looks_like_rate_limited_error(message):
            raise TikTokIngestionError(
                "rate_limited",
                details=type(exc).__name__,
                retryable=True,
                user_message=_RATE_LIMITED_MESSAGE,
            ) from exc
        if _looks_like_unavailable_error(message):
            raise TikTokIngestionError(
                "unsupported_content",
                details=type(exc).__name__,
                retryable=False,
                user_message=_UNAVAILABLE_MESSAGE,
            ) from exc
        raise TikTokIngestionError(
            "extractor_failed",
            details=type(exc).__name__,
            retryable=True,
            user_message=_TEMPORARY_EXTRACTOR_MESSAGE,
        ) from exc


async def _fetch_native_subtitles(info: Dict[str, Any]) -> Dict[str, Any]:
    candidates = _collect_subtitle_candidates(info)
    if not candidates:
        raise NativeSubtitlesUnavailable("native_subtitles_absent")

    last_unavailable_reason = "native_subtitles_absent"
    for candidate in candidates:
        try:
            return await _fetch_subtitle_candidate(candidate)
        except NativeSubtitlesUnavailable as exc:
            last_unavailable_reason = exc.reason
            continue
    raise NativeSubtitlesUnavailable(last_unavailable_reason)


async def _fetch_apify_tiktok_transcript(video_url: str) -> Dict[str, Any]:
    """Fetch transcript for a TikTok video via the Apify actor fallback.

    This is triggered ONLY when yt-dlp fails with an IP block (status 10204).
    Reads configuration from settings at call time (no module-level reads).

    Returns a dict matching the worker's normalized transcript contract:
        text, language, language_code, segments_count, source_detail,
        source_url, fetched_at.

    Raises TikTokIngestionError with appropriate error codes on failure.
    """
    api_token = settings.APIFY_TIKTOK_API_TOKEN
    actor_id = settings.APIFY_TIKTOK_TRANSCRIPT_ACTOR_ID
    timeout_seconds = settings.APIFY_TIKTOK_TIMEOUT_SECONDS
    poll_interval = settings.APIFY_TIKTOK_POLL_INTERVAL_SECONDS
    max_polls = settings.APIFY_TIKTOK_MAX_POLLS

    if not api_token or not actor_id:
        raise TikTokIngestionError(
            "apify_actor_failed",
            details="missing_apify_tiktok_config",
            retryable=False,
            user_message=_APIFY_ACTOR_FAILED_MESSAGE,
        )

    headers = {
        "Authorization": f"Bearer {api_token}",
        "Content-Type": "application/json",
    }
    input_data = {
        "urls": [video_url],
        "shouldDownloadVideos": False,
        "shouldDownloadCovers": False,
    }

    log_event(
        logger,
        logging.INFO,
        "apify_tiktok.call_started",
        "Starting Apify TikTok transcript fallback",
        video_url=video_url,
        actor_id=actor_id,
    )

    async with httpx.AsyncClient(timeout=timeout_seconds) as client:
        # Step 1: Start the actor run
        run_url = f"{APIFY_API_BASE_URL}/acts/{actor_id}/runs"
        try:
            response = await client.post(run_url, headers=headers, json=input_data)
        except (httpx.TimeoutException, httpx.TransportError) as exc:
            log_event(
                logger,
                logging.WARNING,
                "apify_tiktok.network_error",
                "Apify TikTok network error on run start",
                error_type=type(exc).__name__,
            )
            raise TikTokIngestionError(
                "apify_timeout",
                details=f"run_start_network_error:{type(exc).__name__}",
                retryable=True,
                user_message=_APIFY_TIMEOUT_MESSAGE,
            ) from exc

        if response.status_code in (401, 403):
            log_event(
                logger,
                logging.ERROR,
                "apify_tiktok.auth_error",
                "Apify TikTok authentication failed",
                status_code=response.status_code,
            )
            raise TikTokIngestionError(
                "apify_actor_failed",
                details=f"auth_error:{response.status_code}",
                retryable=False,
                user_message=_APIFY_ACTOR_FAILED_MESSAGE,
            )
        if response.status_code == 429:
            log_event(
                logger,
                logging.WARNING,
                "apify_tiktok.quota_exceeded",
                "Apify TikTok quota exceeded",
            )
            raise TikTokIngestionError(
                "apify_quota_exceeded",
                details="apify_429",
                retryable=True,
                user_message=_APIFY_QUOTA_EXCEEDED_MESSAGE,
            )
        if response.status_code >= 500:
            raise TikTokIngestionError(
                "apify_timeout",
                details=f"run_start_server_error:{response.status_code}",
                retryable=True,
                user_message=_APIFY_TIMEOUT_MESSAGE,
            )
        if response.status_code >= 400:
            raise TikTokIngestionError(
                "apify_actor_failed",
                details=f"run_start_client_error:{response.status_code}",
                retryable=False,
                user_message=_APIFY_ACTOR_FAILED_MESSAGE,
            )

        run_data = response.json().get("data", {})
        run_id = run_data.get("id")
        if not run_id:
            raise TikTokIngestionError(
                "apify_actor_failed",
                details="missing_run_id_in_response",
                retryable=True,
                user_message=_APIFY_TIMEOUT_MESSAGE,
            )

        # Step 2: Poll until the run completes
        run_status_url = f"{APIFY_API_BASE_URL}/actor-runs/{run_id}"
        dataset_id: Optional[str] = None

        for _ in range(max_polls):
            await asyncio.sleep(poll_interval)

            try:
                status_response = await client.get(run_status_url, headers=headers)
            except (httpx.TimeoutException, httpx.TransportError):
                continue

            if status_response.status_code != 200:
                continue

            status_data = status_response.json().get("data", {})
            run_status = status_data.get("status", "")

            if run_status == "SUCCEEDED":
                dataset_id = status_data.get("defaultDatasetId")
                break
            elif run_status in ("FAILED", "ABORTED", "TIMED-OUT"):
                log_event(
                    logger,
                    logging.WARNING,
                    "apify_tiktok.actor_run_failed",
                    "Apify TikTok actor run ended in failure status",
                    run_status=run_status,
                    run_id=run_id,
                )
                raise TikTokIngestionError(
                    "apify_actor_failed",
                    details=f"actor_run_status:{run_status}",
                    retryable=False,
                    user_message=_APIFY_ACTOR_FAILED_MESSAGE,
                )

        if not dataset_id:
            raise TikTokIngestionError(
                "apify_timeout",
                details="poll_exhausted_no_dataset",
                retryable=True,
                user_message=_APIFY_TIMEOUT_MESSAGE,
            )

        # Step 3: Retrieve dataset items
        dataset_url = (
            f"{APIFY_API_BASE_URL}/datasets/{dataset_id}/items"
            "?format=json&limit=10"
        )
        try:
            dataset_response = await client.get(dataset_url, headers=headers)
        except (httpx.TimeoutException, httpx.TransportError) as exc:
            raise TikTokIngestionError(
                "apify_timeout",
                details=f"dataset_fetch_error:{type(exc).__name__}",
                retryable=True,
                user_message=_APIFY_TIMEOUT_MESSAGE,
            ) from exc

        if dataset_response.status_code != 200:
            raise TikTokIngestionError(
                "apify_actor_failed",
                details=f"dataset_http_status:{dataset_response.status_code}",
                retryable=True,
                user_message=_APIFY_TIMEOUT_MESSAGE,
            )

        items = dataset_response.json()
        if not isinstance(items, list):
            items = []

    # Step 4: Normalize the output to the worker transcript contract
    transcript_text = _extract_apify_transcript_text(items)
    if not transcript_text:
        log_event(
            logger,
            logging.WARNING,
            "apify_tiktok.no_transcript",
            "Apify TikTok actor returned no usable transcript",
            video_url=video_url,
            items_count=len(items),
        )
        raise TikTokIngestionError(
            "apify_actor_failed",
            details="no_transcript_in_actor_output",
            retryable=False,
            user_message=_UNAVAILABLE_MESSAGE,
        )

    log_event(
        logger,
        logging.INFO,
        "apify_tiktok.call_succeeded",
        "Apify TikTok transcript fallback succeeded",
        video_url=video_url,
        text_length=len(transcript_text),
    )

    return {
        "text": transcript_text,
        "language": None,
        "language_code": None,
        "segments_count": len(
            [line for line in transcript_text.splitlines() if line.strip()]
        ),
        "source_detail": "apify_tiktok",
        "source_url": video_url,
        "fetched_at": _now_iso_utc(),
    }


def _extract_apify_transcript_text(items: list[Dict[str, Any]]) -> str:
    """Extract transcript text from Apify actor dataset items.

    The actor may return transcript text in various fields depending on
    configuration. We try multiple known field paths in priority order.
    """
    for item in items:
        # Try direct transcript/text fields
        for field in (
            "transcript",
            "transcriptionText",
            "subtitles",
            "text",
            "caption",
            "description",
        ):
            value = item.get(field)
            if isinstance(value, str) and value.strip():
                return value.strip()

        # Try nested transcript data (timed segments)
        segments = item.get("transcriptSegments") or item.get("segments")
        if isinstance(segments, list) and segments:
            lines = []
            for seg in segments:
                if isinstance(seg, dict):
                    seg_text = seg.get("text") or seg.get("content") or ""
                    if isinstance(seg_text, str) and seg_text.strip():
                        lines.append(seg_text.strip())
            if lines:
                return "\n".join(lines)

    return ""


def _select_direct_media_stream(info: Dict[str, Any]) -> Dict[str, Any]:
    if info.get("is_live"):
        raise TikTokIngestionError(
            "unsupported_content",
            details="live_content_not_supported",
            retryable=False,
            user_message=_UNSUPPORTED_MESSAGE,
        )

    candidates: list[Dict[str, Any]] = []

    direct_url = info.get("url")
    if isinstance(direct_url, str) and _is_valid_http_url(direct_url):
        candidates.append(info)

    requested_downloads = info.get("requested_downloads")
    if isinstance(requested_downloads, list):
        for item in requested_downloads:
            if isinstance(item, dict):
                candidates.append(item)

    requested_formats = info.get("requested_formats")
    if isinstance(requested_formats, list):
        for item in requested_formats:
            if isinstance(item, dict):
                candidates.append(item)

    formats = info.get("formats")
    if isinstance(formats, list):
        for item in formats:
            if isinstance(item, dict):
                candidates.append(item)

    best_candidate = None
    best_score: tuple[float, float, float] | None = None

    for candidate in candidates:
        url = candidate.get("url")
        if not isinstance(url, str) or not _is_valid_http_url(url):
            continue

        protocol = str(candidate.get("protocol") or "").strip().lower()
        if protocol and protocol not in _AUDIO_URL_PROTOCOLS:
            continue

        acodec = str(candidate.get("acodec") or "").strip().lower()
        if acodec in {"", "none"}:
            continue

        vcodec = str(candidate.get("vcodec") or "").strip().lower()
        is_audio_only = 1.0 if vcodec in {"", "none"} else 0.0
        abr = float(candidate.get("abr") or 0.0)
        tbr = float(candidate.get("tbr") or 0.0)
        score = (is_audio_only, abr, tbr)
        if best_score is None or score > best_score:
            best_candidate = candidate
            best_score = score

    if best_candidate is None:
        raise TikTokIngestionError(
            "no_direct_media_url",
            details="no_transcribable_media_url",
            retryable=False,
            user_message=_UNSUPPORTED_MESSAGE,
        )

    return best_candidate


def _resolve_direct_media_url(info: Dict[str, Any]) -> Dict[str, Any]:
    selected = _select_direct_media_stream(info)
    audio_url = str(selected.get("url") or "").strip()
    if not audio_url:
        raise TikTokIngestionError(
            "no_direct_media_url",
            details="missing_media_url",
            retryable=False,
            user_message=_UNSUPPORTED_MESSAGE,
        )

    duration_value = selected.get("duration") or info.get("duration") or 0
    try:
        audio_duration_seconds = int(float(duration_value))
    except (TypeError, ValueError):
        audio_duration_seconds = 0

    return {
        "audio_url": audio_url,
        "audio_duration_seconds": audio_duration_seconds,
        "format_id": selected.get("format_id"),
        "format_note": selected.get("format_note") or info.get("format_note"),
        "ext": selected.get("ext") or info.get("ext"),
        "acodec": selected.get("acodec") or info.get("acodec"),
        "vcodec": selected.get("vcodec") or info.get("vcodec"),
    }


async def _upload_native_transcript(job_id: str, text: str) -> str:
    transcript_s3_key = f"{job_id}.txt"
    await s3.upload_file_object(
        bucket=TRANSCRIPT_BUCKET,
        key=transcript_s3_key,
        file_obj=BytesIO(text.encode("utf-8")),
        content_type="text/plain",
        metadata={
            "content-type": "text/plain",
            "job-type": "tiktok-transcript",
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


def _build_native_extraction_metadata(
    *,
    tiktok_id: str,
    source_url: str,
    native_result: Dict[str, Any],
) -> Dict[str, Any]:
    return {
        "provider": "yt-dlp",
        "extractor": "yt_dlp",
        "extractor_version": _YTDLP_EXTRACTOR_VERSION,
        "strategy_used": "native_subtitles",
        "selected_strategy": "native_subtitles",
        "source_url": source_url,
        "tiktok_id": tiktok_id,
        "subtitle_status": "native_subtitles_found",
        "direct_media_url_present": False,
        "direct_media_url_status": None,
        "resolved_url": native_result.get("source_url"),
        "subtitle_language": native_result.get("language"),
        "subtitle_ext": native_result.get("ext"),
        "segments_count": native_result.get("segments_count"),
        "last_error_code": None,
        "fetched_at": native_result["fetched_at"],
    }


def _build_native_transcription_metadata(
    *,
    source_url: str,
    native_result: Dict[str, Any],
) -> Dict[str, Any]:
    return {
        "provider": "native_transcript",
        "model_used": "yt_dlp_tiktok_subtitles",
        "language": native_result.get("language"),
        "segments_count": native_result.get("segments_count"),
        "duration_seconds": 0,
        "source_url": source_url,
        "transcribed_at": native_result["fetched_at"],
        "source_detail": native_result["source_detail"],
    }


def _build_fallback_extraction_metadata(
    *,
    tiktok_id: str,
    source_url: str,
    fallback_reason: str,
    audio_result: Dict[str, Any],
) -> Dict[str, Any]:
    return {
        "provider": "yt-dlp",
        "extractor": "yt_dlp",
        "extractor_version": _YTDLP_EXTRACTOR_VERSION,
        "strategy_used": "direct_media_url_fallback",
        "selected_strategy": "direct_media_url_fallback",
        "source_url": source_url,
        "tiktok_id": tiktok_id,
        "subtitle_status": "native_subtitles_absent",
        "direct_media_url_present": True,
        "direct_media_url_status": "direct_media_url_found",
        "resolved_url": audio_result["audio_url"],
        "audio_duration_seconds": audio_result["audio_duration_seconds"],
        "native_subtitle_fallback_reason": fallback_reason,
        "yt_dlp_format_id": audio_result.get("format_id"),
        "yt_dlp_format_note": audio_result.get("format_note"),
        "yt_dlp_ext": audio_result.get("ext"),
        "yt_dlp_acodec": audio_result.get("acodec"),
        "yt_dlp_vcodec": audio_result.get("vcodec"),
        "last_error_code": None,
        "queued_at": _now_iso_utc(),
    }


def _build_apify_extraction_metadata(
    *,
    tiktok_id: str,
    source_url: str,
    apify_result: Dict[str, Any],
) -> Dict[str, Any]:
    return {
        "provider": "apify",
        "extractor": "apify_tiktok_actor",
        "extractor_version": _YTDLP_EXTRACTOR_VERSION,
        "strategy_used": "apify_tiktok_ip_block_fallback",
        "selected_strategy": "apify_tiktok_ip_block_fallback",
        "source_url": source_url,
        "tiktok_id": tiktok_id,
        "subtitle_status": "apify_transcript_found",
        "direct_media_url_present": False,
        "direct_media_url_status": None,
        "resolved_url": apify_result.get("source_url"),
        "segments_count": apify_result.get("segments_count"),
        "last_error_code": None,
        "fetched_at": apify_result["fetched_at"],
    }


def _build_apify_transcription_metadata(
    *,
    source_url: str,
    apify_result: Dict[str, Any],
) -> Dict[str, Any]:
    return {
        "provider": "apify_tiktok",
        "model_used": "apify_tiktok_transcript_actor",
        "language": apify_result.get("language"),
        "segments_count": apify_result.get("segments_count"),
        "duration_seconds": 0,
        "source_url": source_url,
        "transcribed_at": apify_result["fetched_at"],
        "source_detail": apify_result["source_detail"],
    }


async def _mark_job_failed(
    *,
    job_id: Optional[str],
    normalized_url: str,
    tiktok_id: Optional[str],
    error: TikTokIngestionError,
) -> None:
    if not job_id:
        return

    job = await database_async.get_processing_job_by_id(job_id)
    if not job:
        return

    job.extraction_metadata = {
        "provider": "yt-dlp",
        "extractor": "tiktok_ingestion_worker",
        "extractor_version": "v1",
        "strategy_used": "failed",
        "selected_strategy": "failed",
        "source_url": normalized_url,
        "tiktok_id": tiktok_id,
        "subtitle_status": "unknown",
        "direct_media_url_present": False,
        "direct_media_url_status": None,
        "resolved_url": None,
        "last_error_code": error.code,
        "failure_details": error.details or error.code,
        "failed_at": _now_iso_utc(),
    }
    job.mark_failed(
        error_message=error.user_message,
        error_step="tiktok_ingestion",
    )
    await database_async.update_processing_job(job)


async def process_tiktok_message(message_body: Dict[str, Any]) -> Dict[str, Any]:
    job_id = (message_body.get("job_id") or "").strip()
    normalized_url = (message_body.get("normalized_url") or "").strip()

    if not job_id:
        raise TikTokIngestionError(
            "extractor_failed",
            details="missing_job_id",
            retryable=False,
            user_message=_TEMPORARY_EXTRACTOR_MESSAGE,
        )
    if not normalized_url:
        raise TikTokIngestionError(
            "extractor_failed",
            details="missing_normalized_url",
            retryable=False,
            user_message=_TEMPORARY_EXTRACTOR_MESSAGE,
        )

    job = await database_async.get_processing_job_by_id(job_id)
    if not job:
        raise TikTokIngestionError(
            "extractor_failed",
            details=f"processing_job_not_found:{job_id}",
            retryable=False,
            user_message=_TEMPORARY_EXTRACTOR_MESSAGE,
        )

    job.mark_downloading()
    await database_async.update_processing_job(job)

    tiktok_id = _extract_tiktok_id(normalized_url)

    # Step 1: Try yt-dlp extraction (primary path)
    ip_blocked = False
    info: Optional[Dict[str, Any]] = None
    try:
        info = await _extract_tiktok_info(normalized_url)
    except TikTokIngestionError as ytdlp_exc:
        if _is_ip_blocked_error(ytdlp_exc):
            # IP block detected -- will attempt Apify fallback below
            ip_blocked = True
            log_event(
                logger,
                logging.WARNING,
                "tiktok.ip_block_detected",
                "TikTok IP block detected, attempting Apify fallback",
                job_id=job_id,
                video_url=normalized_url,
                error_details=ytdlp_exc.details,
            )
        else:
            # Non-IP-block yt-dlp error -- propagate as-is
            raise

    # Step 2a: IP-blocked path -- try Apify fallback
    if ip_blocked:
        try:
            apify_result = await _fetch_apify_tiktok_transcript(normalized_url)
        except TikTokIngestionError as apify_exc:
            # Both yt-dlp (IP blocked) and Apify failed
            raise TikTokIngestionError(
                "tiktok_ip_blocked_unrecoverable",
                details=f"apify_also_failed:{apify_exc.code}:{apify_exc.details}",
                retryable=False,
                user_message=_IP_BLOCKED_UNRECOVERABLE_MESSAGE,
            ) from apify_exc

        # Apify succeeded -- upload transcript and publish completion
        transcript_s3_key = await _upload_native_transcript(
            job_id, apify_result["text"]
        )
        transcription_metadata = _build_apify_transcription_metadata(
            source_url=normalized_url,
            apify_result=apify_result,
        )
        job.set_transcription_location(transcript_s3_key)
        job.set_transcription_metadata(transcription_metadata)
        job.extraction_metadata = _build_apify_extraction_metadata(
            tiktok_id=tiktok_id,
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
            "mode": "apify_tiktok_fallback",
            "job_id": job_id,
            "media_key": message_body.get("media_key"),
            "tiktok_id": tiktok_id,
            "source_detail": "apify_tiktok",
        }

    # Step 2b: yt-dlp succeeded -- try native subtitles, then Deepgram URL fallback
    assert info is not None  # guaranteed by logic above

    try:
        native_result = await _fetch_native_subtitles(info)
    except NativeSubtitlesUnavailable as exc:
        audio_result = _resolve_direct_media_url(info)
        job.extraction_metadata = _build_fallback_extraction_metadata(
            tiktok_id=tiktok_id,
            source_url=normalized_url,
            fallback_reason=exc.reason,
            audio_result=audio_result,
        )
        job.media_url = audio_result["audio_url"]
        job.mark_transcribing()
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
                "episode_title": message_body.get("episode_title") or job.title or "TikTok video",
                "podcast_title": message_body.get("podcast_title") or "TikTok",
                "audio_duration_seconds": audio_result["audio_duration_seconds"],
            },
        )

        return {
            "mode": "deepgram_fallback",
            "job_id": job.id,
            "media_key": message_body.get("media_key"),
            "tiktok_id": tiktok_id,
            "fallback_reason": exc.reason,
        }

    transcript_s3_key = await _upload_native_transcript(job_id, native_result["text"])
    transcription_metadata = _build_native_transcription_metadata(
        source_url=normalized_url,
        native_result=native_result,
    )
    job.set_transcription_location(transcript_s3_key)
    job.set_transcription_metadata(transcription_metadata)
    job.extraction_metadata = _build_native_extraction_metadata(
        tiktok_id=tiktok_id,
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
        "mode": "native_transcript",
        "job_id": job_id,
        "media_key": message_body.get("media_key"),
        "tiktok_id": tiktok_id,
        "source_detail": native_result["source_detail"],
    }


async def process_message(message: Dict[str, Any]) -> None:
    body: Dict[str, Any] = {}

    try:
        body = json.loads(message.get("Body", "{}"))
    except Exception as exc:
        log_event(
            logger,
            logging.ERROR,
            "worker.invalid_message",
            "Invalid JSON in TikTok ingestion message",
            queue=TIKTOK_INGESTION_QUEUE,
            exc_info=exc,
        )
        return

    context_token = bind_log_context(
        job_id=body.get("job_id"),
        media_item_id=body.get("job_id"),
        queue=TIKTOK_INGESTION_QUEUE,
        resolver_key=body.get("resolver_key") or "tiktok.default",
        source_platform="tiktok",
    )

    receive_count = int(
        (message.get("Attributes") or {}).get("ApproximateReceiveCount", "1")
    )

    try:
        result = await process_tiktok_message(body)
        if result["mode"] == "native_transcript":
            log_event(
                logger,
                logging.INFO,
                "transcription.completed",
                "TikTok native subtitles completed",
                job_id=result["job_id"],
                media_item_id=result["job_id"],
                transcript_source="native_transcript",
                fallback_strategy=result["source_detail"],
            )
        elif result["mode"] == "apify_tiktok_fallback":
            log_event(
                logger,
                logging.INFO,
                "transcription.completed",
                "TikTok Apify fallback transcript completed (IP block bypass)",
                job_id=result["job_id"],
                media_item_id=result["job_id"],
                transcript_source="apify_tiktok",
                fallback_strategy="apify_tiktok_ip_block_fallback",
            )
        else:
            log_event(
                logger,
                logging.INFO,
                "transcription.enqueued",
                "TikTok queued Deepgram fallback after subtitle miss",
                job_id=result["job_id"],
                media_item_id=result["job_id"],
                queue=DEEPGRAM_TRANSCRIPTION_QUEUE,
                transcript_source="deepgram",
                fallback_strategy=result["fallback_reason"],
            )
    except TikTokIngestionError as exc:
        should_retry = exc.retryable and receive_count < TIKTOK_WORKER_MAX_RETRIES
        if should_retry:
            raise

        tiktok_id = None
        normalized_url = (body.get("normalized_url") or "").strip()
        if normalized_url:
            try:
                tiktok_id = _extract_tiktok_id(normalized_url)
            except TikTokIngestionError:
                tiktok_id = None

        await _mark_job_failed(
            job_id=body.get("job_id"),
            normalized_url=normalized_url,
            tiktok_id=tiktok_id,
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
            "TikTok ingestion failed",
            job_id=body.get("job_id"),
            media_item_id=body.get("job_id"),
            error_code=exc.code,
            detail=exc.details,
        )
    except Exception as exc:
        if receive_count < TIKTOK_WORKER_MAX_RETRIES:
            raise

        final_error = TikTokIngestionError(
            "extractor_failed",
            details=f"unexpected:{type(exc).__name__}",
            retryable=False,
            user_message=_TEMPORARY_EXTRACTOR_MESSAGE,
        )
        tiktok_id = None
        normalized_url = (body.get("normalized_url") or "").strip()
        if normalized_url:
            try:
                tiktok_id = _extract_tiktok_id(normalized_url)
            except TikTokIngestionError:
                tiktok_id = None
        await _mark_job_failed(
            job_id=body.get("job_id"),
            normalized_url=normalized_url,
            tiktok_id=tiktok_id,
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
            "TikTok ingestion failed after retries",
            job_id=body.get("job_id"),
            media_item_id=body.get("job_id"),
            error_code=final_error.code,
            exc_info=exc,
        )
    finally:
        reset_log_context(context_token)


async def poll_queue() -> None:
    log_event(
        logger,
        logging.INFO,
        "worker.started",
        "Starting TikTok ingestion worker",
        queue=TIKTOK_INGESTION_QUEUE,
    )
    while True:
        try:
            receive_params = get_sqs_receive_params(visibility_timeout=300)
            messages = await sqs.receive_messages(
                queue_name=TIKTOK_INGESTION_QUEUE,
                max_messages=receive_params["MaxNumberOfMessages"],
                wait_time_seconds=receive_params["WaitTimeSeconds"],
                visibility_timeout=receive_params["VisibilityTimeout"],
            )
            if messages:
                for message in messages:
                    await process_message_with_retry(
                        message=message,
                        processor=process_message,
                        queue_name=TIKTOK_INGESTION_QUEUE,
                        max_retries=TIKTOK_WORKER_MAX_RETRIES,
                        worker_name="tiktok_ingestion",
                    )
            else:
                await asyncio.sleep(1)
        except Exception as exc:
            log_event(
                logger,
                logging.ERROR,
                "worker.polling_error",
                "TikTok ingestion polling failed",
                queue=TIKTOK_INGESTION_QUEUE,
                exc_info=exc,
            )
            await asyncio.sleep(5)


async def main() -> None:
    setup_logging("tiktok-ingestion-worker")
    await poll_queue()


if __name__ == "__main__":
    asyncio.run(main())
