"""
Queue-first TikTok ingestion worker.

Pipeline:
- Consumes messages from TIKTOK_INGESTION_QUEUE
- Attempts native subtitle retrieval through yt-dlp metadata first
- Uploads native transcript text to S3 and publishes completion events on success
- Falls back to a direct remote media URL and reuses the Deepgram queue
- When yt-dlp is IP-blocked (status 10204), falls back to Apify TikTok Scraper
- When Apify returns no transcript, resolves media URL from actor response and
  dispatches to Deepgram in push mode
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
    "TRANSCRIPT_BUCKET", "media-summarizer-transcriptions"
)
TIKTOK_INGESTION_QUEUE = os.environ.get(
    "TIKTOK_INGESTION_QUEUE", "tiktok-ingestion-queue"
)
DEEPGRAM_TRANSCRIPTION_QUEUE = os.environ.get(
    "DEEPGRAM_TRANSCRIPTION_QUEUE", "deepgram-transcription-queue"
)
EPISODE_COMPLETION_EVENTS_QUEUE = os.environ.get(
    "EPISODE_COMPLETION_EVENTS_QUEUE", "episode-completion-events"
)
YTDLP_TIMEOUT_SECONDS = float(os.environ.get("YTDLP_TIMEOUT_SECONDS", "30"))
TIKTOK_SUBTITLE_FETCH_TIMEOUT_SECONDS = float(
    os.environ.get("TIKTOK_SUBTITLE_FETCH_TIMEOUT_SECONDS", "20")
)
TIKTOK_WORKER_MAX_RETRIES = max(
    1, int(os.environ.get("TIKTOK_WORKER_MAX_RETRIES", "3"))
)

# Apify configuration for TikTok Scraper fallback
APIFY_API_TOKEN = os.environ.get("APIFY_API_TOKEN", "")
APIFY_TIKTOK_ACTOR_ID = os.environ.get(
    "APIFY_TIKTOK_ACTOR_ID", "clockworks~tiktok-scraper"
)
APIFY_API_BASE_URL = os.environ.get(
    "APIFY_API_BASE_URL", "https://api.apify.com/v2"
)
APIFY_TIKTOK_TIMEOUT_SECONDS = float(
    os.environ.get("APIFY_TIKTOK_TIMEOUT_SECONDS", "120")
)
APIFY_TIKTOK_POLL_INTERVAL = float(
    os.environ.get("APIFY_TIKTOK_POLL_INTERVAL", "5")
)

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


class TikTokIPBlocked(Exception):
    """Raised when yt-dlp encounters an IP block (status 10204) from TikTok."""

    def __init__(self, details: str) -> None:
        super().__init__(details)
        self.details = details


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


def _looks_like_ip_blocked_error(message: str) -> bool:
    """Detect TikTok IP-block errors.

    yt-dlp surfaces TikTok's IP block under several phrasings: the legacy
    status code 10204, generic ip/geo-block tokens, and the modern message
    "Your IP address is blocked from accessing this post" observed in
    CloudWatch on AWS Lambda runs (task-182).
    """
    normalized = (message or "").lower()
    return any(
        token in normalized
        for token in (
            "ip address is blocked",
            "10204",
            "ip block",
            "ip-block",
            "geo block",
            "geo-block",
        )
    )


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
        if _looks_like_ip_blocked_error(message):
            raise TikTokIPBlocked(
                details=f"yt_dlp_ip_blocked:{type(exc).__name__}",
            ) from exc
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
        if _looks_like_ip_blocked_error(message):
            raise TikTokIPBlocked(
                details=f"yt_dlp_ip_blocked:{type(exc).__name__}",
            ) from exc
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


async def _fetch_apify_tiktok_dataset(normalized_url: str) -> list[Dict[str, Any]]:
    """
    Call the Apify TikTok Scraper actor synchronously and return dataset items.

    Uses the actor run-sync endpoint which starts the actor, waits for completion,
    and returns the dataset items in one call.
    """
    if not APIFY_API_TOKEN:
        raise TikTokIngestionError(
            "apify_actor_failed",
            details="missing_apify_api_token",
            retryable=False,
            user_message=_TEMPORARY_EXTRACTOR_MESSAGE,
        )

    run_url = (
        f"{APIFY_API_BASE_URL}/acts/{APIFY_TIKTOK_ACTOR_ID}/run-sync-get-dataset-items"
    )
    params = {"token": APIFY_API_TOKEN}
    payload = {
        "postURLs": [normalized_url],
        "shouldDownloadVideos": False,
        "shouldDownloadCovers": False,
        "maxProfilesPerQuery": 1,
        "resultsPerPage": 1,
    }

    try:
        async with httpx.AsyncClient(
            timeout=APIFY_TIKTOK_TIMEOUT_SECONDS,
            follow_redirects=True,
        ) as client:
            response = await client.post(
                run_url,
                params=params,
                json=payload,
            )
    except (httpx.TimeoutException, httpx.TransportError) as exc:
        raise TikTokIngestionError(
            "apify_actor_failed",
            details=f"apify_network_error:{type(exc).__name__}",
            retryable=True,
            user_message=_TEMPORARY_EXTRACTOR_MESSAGE,
        ) from exc

    if response.status_code in (401, 403):
        raise TikTokIngestionError(
            "apify_actor_failed",
            details=f"apify_auth_error:{response.status_code}",
            retryable=False,
            user_message=_TEMPORARY_EXTRACTOR_MESSAGE,
        )
    if response.status_code >= 500:
        raise TikTokIngestionError(
            "apify_actor_failed",
            details=f"apify_server_error:{response.status_code}",
            retryable=True,
            user_message=_TEMPORARY_EXTRACTOR_MESSAGE,
        )
    if response.status_code >= 400:
        raise TikTokIngestionError(
            "apify_actor_failed",
            details=f"apify_client_error:{response.status_code}",
            retryable=False,
            user_message=_TEMPORARY_EXTRACTOR_MESSAGE,
        )

    try:
        items = response.json()
    except (json.JSONDecodeError, ValueError) as exc:
        raise TikTokIngestionError(
            "apify_actor_failed",
            details="apify_invalid_json_response",
            retryable=False,
            user_message=_TEMPORARY_EXTRACTOR_MESSAGE,
        ) from exc

    if not isinstance(items, list):
        items = []

    return items


def _extract_apify_transcript_text(items: list[Dict[str, Any]]) -> Optional[str]:
    """
    Extract transcript text from Apify TikTok Scraper dataset items.

    Looks for subtitle links in videoMeta.subtitleLinks[].downloadLink and
    returns the raw text content if any subtitle is found inline. For URL-based
    subtitles, returns None (would need an additional fetch -- handled by the
    existing subtitle download flow when available).
    """
    if not items:
        return None

    item = items[0]
    if not isinstance(item, dict):
        return None

    # Check for inline subtitle/caption text from the actor
    video_meta = item.get("videoMeta")
    if isinstance(video_meta, dict):
        subtitle_links = video_meta.get("subtitleLinks")
        if isinstance(subtitle_links, list):
            for sub in subtitle_links:
                if not isinstance(sub, dict):
                    continue
                # Some actor versions include inline text
                text = sub.get("text") or sub.get("content")
                if isinstance(text, str) and text.strip():
                    return text.strip()

    # Check for direct text/description as fallback transcript source
    # (some TikTok videos contain the full transcript in the description)
    # -- We do NOT use description as transcript, it's unreliable.

    return None


def _resolve_apify_tiktok_media_url(items: list[Dict[str, Any]]) -> Optional[str]:
    """
    Extract a direct audio/media URL from Apify TikTok Scraper dataset items.

    Primary: musicMeta.playUrl (CDN URL of the audio track, expires after hours).
    Fallback: mediaUrls[0] if available (Apify-hosted permanent MP4, paid feature).
    """
    if not items:
        return None

    item = items[0]
    if not isinstance(item, dict):
        return None

    # Primary: musicMeta.playUrl
    music_meta = item.get("musicMeta")
    if isinstance(music_meta, dict):
        play_url = music_meta.get("playUrl")
        if isinstance(play_url, str) and _is_valid_http_url(play_url):
            return play_url.strip()

    # Fallback: mediaUrls (only available with shouldDownloadVideos: true)
    media_urls = item.get("mediaUrls")
    if isinstance(media_urls, list):
        for url in media_urls:
            if isinstance(url, str) and _is_valid_http_url(url):
                return url.strip()

    return None


def _build_apify_native_extraction_metadata(
    *,
    tiktok_id: str,
    source_url: str,
    transcript_text: str,
) -> Dict[str, Any]:
    """Build extraction metadata for the Apify native transcript path."""
    return {
        "provider": "apify",
        "extractor": "clockworks_tiktok_scraper",
        "extractor_version": "v1",
        "strategy_used": "apify_native_transcript",
        "selected_strategy": "apify_native_transcript",
        "source_url": source_url,
        "tiktok_id": tiktok_id,
        "subtitle_status": "apify_transcript_found",
        "direct_media_url_present": False,
        "direct_media_url_status": None,
        "resolved_url": None,
        "segments_count": len([line for line in transcript_text.splitlines() if line.strip()]),
        "last_error_code": None,
        "fetched_at": _now_iso_utc(),
    }


def _build_apify_native_transcription_metadata(
    *,
    source_url: str,
    transcript_text: str,
) -> Dict[str, Any]:
    """Build transcription metadata for the Apify native transcript path."""
    return {
        "provider": "apify_native_transcript",
        "model_used": "clockworks_tiktok_scraper",
        "language": None,
        "segments_count": len([line for line in transcript_text.splitlines() if line.strip()]),
        "duration_seconds": 0,
        "source_url": source_url,
        "transcribed_at": _now_iso_utc(),
        "source_detail": "apify_tiktok_scraper_subtitles",
    }


def _build_apify_deepgram_fallback_extraction_metadata(
    *,
    tiktok_id: str,
    source_url: str,
    audio_url: str,
) -> Dict[str, Any]:
    """Build extraction metadata for the Apify -> Deepgram fallback path."""
    return {
        "provider": "apify",
        "extractor": "clockworks_tiktok_scraper",
        "extractor_version": "v1",
        "strategy_used": "deepgram_via_apify_tiktok_url",
        "selected_strategy": "deepgram_via_apify_tiktok_url",
        "source_url": source_url,
        "tiktok_id": tiktok_id,
        "subtitle_status": "apify_no_transcript",
        "direct_media_url_present": True,
        "direct_media_url_status": "apify_media_url_resolved",
        "resolved_url": audio_url,
        "audio_duration_seconds": 0,
        "native_subtitle_fallback_reason": "ip_blocked_apify_no_transcript",
        "last_error_code": None,
        "queued_at": _now_iso_utc(),
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
        queue_name=EPISODE_COMPLETION_EVENTS_QUEUE,
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
        queue_name=EPISODE_COMPLETION_EVENTS_QUEUE,
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

    job.mark_extracting()
    await database_async.update_processing_job(job)

    tiktok_id = _extract_tiktok_id(normalized_url)

    # Attempt yt-dlp extraction; on IP-block, fall through to Apify path
    try:
        info = await _extract_tiktok_info(normalized_url)
    except TikTokIPBlocked as ip_exc:
        log_event(
            logger,
            logging.WARNING,
            "extraction.ip_blocked",
            "yt-dlp IP-blocked, falling back to Apify TikTok Scraper",
            job_id=job_id,
            tiktok_id=tiktok_id,
            detail=ip_exc.details,
        )
        return await _process_apify_fallback(
            job=job,
            job_id=job_id,
            tiktok_id=tiktok_id,
            normalized_url=normalized_url,
            message_body=message_body,
        )

    # yt-dlp succeeded -- try native subtitles first
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
        job.episode_url = audio_result["audio_url"]
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
                "episode_title": message_body.get("episode_title") or job.episode_title,
                "podcast_title": message_body.get("podcast_title") or job.podcast_title,
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


async def _process_apify_fallback(
    *,
    job: Any,
    job_id: str,
    tiktok_id: str,
    normalized_url: str,
    message_body: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Apify fallback path: called when yt-dlp is IP-blocked (status 10204).

    1. Fetch dataset from Apify TikTok Scraper actor
    2. If actor returns transcript text -> upload and complete
    3. If no transcript but media URL found -> enqueue Deepgram (push mode)
    4. If neither -> fail terminally
    """
    items = await _fetch_apify_tiktok_dataset(normalized_url)
    transcript_text = _extract_apify_transcript_text(items)

    if transcript_text:
        # Apify returned a usable transcript
        transcript_s3_key = await _upload_native_transcript(job_id, transcript_text)
        transcription_metadata = _build_apify_native_transcription_metadata(
            source_url=normalized_url,
            transcript_text=transcript_text,
        )
        job.set_transcription_location(transcript_s3_key)
        job.set_transcription_metadata(transcription_metadata)
        job.extraction_metadata = _build_apify_native_extraction_metadata(
            tiktok_id=tiktok_id,
            source_url=normalized_url,
            transcript_text=transcript_text,
        )
        job.mark_completed()
        await database_async.update_processing_job(job)

        await _publish_success_event(
            job_id=job_id,
            media_key=message_body.get("media_key"),
            transcript_s3_key=transcript_s3_key,
            transcription_metadata=transcription_metadata,
        )

        log_event(
            logger,
            logging.INFO,
            "transcription.completed",
            "TikTok Apify native transcript completed",
            job_id=job_id,
            tiktok_id=tiktok_id,
            fallback_strategy="apify_native_transcript",
        )

        return {
            "mode": "apify_native_transcript",
            "job_id": job_id,
            "media_key": message_body.get("media_key"),
            "tiktok_id": tiktok_id,
            "source_detail": "apify_tiktok_scraper_subtitles",
        }

    # No transcript from Apify -- try to resolve a media URL for Deepgram
    audio_url = _resolve_apify_tiktok_media_url(items)

    if audio_url:
        job.extraction_metadata = _build_apify_deepgram_fallback_extraction_metadata(
            tiktok_id=tiktok_id,
            source_url=normalized_url,
            audio_url=audio_url,
        )
        job.episode_url = audio_url
        job.mark_transcribing()
        await database_async.update_processing_job(job)

        await sqs.send_message(
            queue_name=DEEPGRAM_TRANSCRIPTION_QUEUE,
            message_body={
                "job_id": job.id,
                "user_id": message_body.get("user_id"),
                "user_email": message_body.get("user_email"),
                "audio_url": audio_url,
                "media_key": message_body.get("media_key"),
                "normalized_url": normalized_url,
                "episode_title": message_body.get("episode_title") or job.episode_title,
                "podcast_title": message_body.get("podcast_title") or job.podcast_title,
                "audio_duration_seconds": 0,
                "deepgram_mode": "push",
            },
        )

        log_event(
            logger,
            logging.INFO,
            "transcription.enqueued",
            "TikTok queued Deepgram via Apify-resolved media URL",
            job_id=job_id,
            tiktok_id=tiktok_id,
            queue=DEEPGRAM_TRANSCRIPTION_QUEUE,
            fallback_strategy="deepgram_via_apify_tiktok_url",
        )

        return {
            "mode": "deepgram_via_apify_tiktok_url",
            "job_id": job.id,
            "media_key": message_body.get("media_key"),
            "tiktok_id": tiktok_id,
            "fallback_reason": "ip_blocked_apify_no_transcript",
        }

    # Terminal failure: no transcript and no media URL from Apify
    raise TikTokIngestionError(
        "apify_actor_failed",
        details="no_transcript_and_no_media_url_in_actor_output",
        retryable=False,
        user_message=_UNSUPPORTED_MESSAGE,
    )


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
        elif result["mode"] == "apify_native_transcript":
            log_event(
                logger,
                logging.INFO,
                "transcription.completed",
                "TikTok Apify native transcript completed",
                job_id=result["job_id"],
                media_item_id=result["job_id"],
                transcript_source="apify_native_transcript",
                fallback_strategy=result["source_detail"],
            )
        elif result["mode"] == "deepgram_via_apify_tiktok_url":
            log_event(
                logger,
                logging.INFO,
                "transcription.enqueued",
                "TikTok queued Deepgram via Apify-resolved media URL",
                job_id=result["job_id"],
                media_item_id=result["job_id"],
                queue=DEEPGRAM_TRANSCRIPTION_QUEUE,
                transcript_source="deepgram",
                fallback_strategy="deepgram_via_apify_tiktok_url",
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
                fallback_strategy=result.get("fallback_reason", "unknown"),
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
