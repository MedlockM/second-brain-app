"""
Queue-first TikTok ingestion worker.

Pipeline:
- Consumes messages from TIKTOK_INGESTION_QUEUE
- Attempts native subtitle retrieval through yt-dlp metadata first
- Uploads native transcript text to S3 and publishes completion events on success
- When yt-dlp succeeds without captions, falls back to the resolved media URL
  and reuses the Deepgram queue (push mode)
- When yt-dlp is IP-blocked, falls back to the Apify TikTok transcript actor;
  on usable transcript the job completes, otherwise it fails terminally
"""

from __future__ import annotations

import asyncio
import html
import json
import logging
import os
import re
from datetime import datetime, timezone
from io import BytesIO
from typing import Any, Dict, Optional
from urllib.parse import urlsplit

import httpx
import yt_dlp

from media_summarizer.core.media_ingestion.title_derivation import select_title
from media_summarizer.core.models.processing_job import ProcessingJob
from media_summarizer.core.services import audio_quota_gate
from media_summarizer.core.services.transcript_formatting import (
    count_paragraphs,
    group_caption_lines,
    normalize_transcript_text,
)
from media_summarizer.infrastructure import apify_adapter
from media_summarizer.infrastructure.apify_adapter import ApifyActorKind
from media_summarizer.utils import database_async, s3, sqs
from media_summarizer.utils.deepgram_dispatch import (
    DEEPGRAM_TRANSCRIPTION_QUEUE,
    enqueue_deepgram_transcription,
)
from media_summarizer.utils.env import required_env
from media_summarizer.utils.ingestion_sentinels import (
    strip_e2e_force_ip_block_sentinel,
)
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
from media_summarizer.workers import apify_orchestration
from media_summarizer.workers.base_worker import (
    get_sqs_receive_params,
    process_message_with_retry,
)

logger = logging.getLogger(__name__)

TRANSCRIPT_BUCKET = required_env("TRANSCRIPT_BUCKET")
TIKTOK_INGESTION_QUEUE = required_env("TIKTOK_INGESTION_QUEUE")
EPISODE_COMPLETED_EVENTS_QUEUE = required_env("EPISODE_COMPLETED_EVENTS_QUEUE")
YTDLP_TIMEOUT_SECONDS = float(os.environ.get("YTDLP_TIMEOUT_SECONDS", "30"))
TIKTOK_SUBTITLE_FETCH_TIMEOUT_SECONDS = float(os.environ.get("TIKTOK_SUBTITLE_FETCH_TIMEOUT_SECONDS", "20"))
TIKTOK_WORKER_MAX_RETRIES = max(1, int(os.environ.get("TIKTOK_WORKER_MAX_RETRIES", "3")))

_YTDLP_EXTRACTOR_VERSION = "v1"
_AUDIO_URL_PROTOCOLS = {
    "http",
    "https",
    "http_dash_segments",
    "https_dash_segments",
}
_TIMESTAMP_LINE_RE = re.compile(r"^\s*(?:\d{1,2}:)?\d{2}:\d{2}[.,]\d{3}\s+-->\s+(?:\d{1,2}:)?\d{2}:\d{2}[.,]\d{3}")
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

# Mirrors classifiers._TIKTOK_SHORT_HOSTS: vm.tiktok.com share links carry a
# random shortcode instead of /@user/video/<id> or /t/<id>.
_TIKTOK_SHORT_HOSTS = {"vm.tiktok.com"}

_UNAVAILABLE_MESSAGE = "This TikTok video is unavailable or cannot be processed."
_UNSUPPORTED_MESSAGE = "Unable to resolve transcribable media from this TikTok URL."
_TEMPORARY_EXTRACTOR_MESSAGE = "TikTok extraction is temporarily unavailable. Please retry."
_RATE_LIMITED_MESSAGE = "TikTok media extraction is temporarily rate limited. Please retry later."


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
    return any(token in normalized for token in ("429", "rate limit", "rate-limited", "too many requests", "quota"))


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
    host = (split.hostname or "").lower()
    parts = [segment for segment in (split.path or "").split("/") if segment]

    if len(parts) >= 3 and parts[0].startswith("@") and parts[1] == "video":
        return parts[2].strip()
    if len(parts) >= 2 and parts[0] == "t":
        return parts[1].strip()
    if host in _TIKTOK_SHORT_HOSTS and parts:
        # vm.tiktok.com/<shortcode> share links: yt-dlp resolves the
        # redirect itself, so the shortcode is only used for metadata/logging.
        return parts[0].strip()

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
        normalized_ext in {"json", "srv3"} or "application/json" in normalized_content_type or payload.lstrip().startswith(("{", "["))
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

    cue_text = _parse_caption_payload(
        payload=payload,
        ext=str(candidate.get("ext") or ""),
        content_type=content_type,
    )
    if not cue_text:
        raise NativeSubtitlesUnavailable("native_subtitles_absent")

    # Caption cues are display units, not sentences: group them into paragraphs
    # before the text is stored (task-231 option B).
    text = group_caption_lines(cue_text.splitlines(), source="tiktok")
    if not text:
        raise NativeSubtitlesUnavailable("native_subtitles_absent")

    return {
        "text": text,
        "language": str(candidate.get("language") or "").strip() or None,
        # Paragraph count, comparable with the Deepgram path (task-231 §13.1).
        "segments_count": count_paragraphs(text),
        "source_detail": (f"tiktok_native_subtitles:{candidate.get('language') or 'unknown'}:{candidate.get('ext') or 'unknown'}"),
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


def _extract_apify_transcript_text(items: list[Dict[str, Any]]) -> Optional[str]:
    """
    Extract transcript text from Apify TikTok transcript actor dataset items.

    Each item carries `success` (bool) and `transcript` (WEBVTT string) per the
    actor schema. We strip the VTT cues (timestamps, NOTE/STYLE blocks), keep
    only the spoken lines and group them into paragraphs (task-231 option B).
    Returns None when the actor signalled failure or the transcript is empty.
    """
    if not items:
        return None

    item = items[0]
    if not isinstance(item, dict):
        return None

    if item.get("success") is False:
        return None

    raw = item.get("transcript")
    if not isinstance(raw, str) or not raw.strip():
        return None

    cue_text = _parse_timed_text_payload(raw)
    return group_caption_lines(cue_text.splitlines(), source="tiktok") or None


def _build_apify_native_extraction_metadata(
    *,
    tiktok_id: str,
    source_url: str,
    transcript_text: str,
) -> Dict[str, Any]:
    """Build extraction metadata for the Apify native transcript path."""
    return {
        "provider": "apify",
        "extractor": "scrape_creators_tiktok_transcripts",
        "extractor_version": "v1",
        "strategy_used": "apify_native_transcript",
        "selected_strategy": "apify_native_transcript",
        "source_url": source_url,
        "tiktok_id": tiktok_id,
        "subtitle_status": "apify_transcript_found",
        "direct_media_url_present": False,
        "direct_media_url_status": None,
        "resolved_url": None,
        "segments_count": count_paragraphs(transcript_text),
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
        "model_used": "scrape_creators_tiktok_transcripts",
        "language": None,
        # Paragraph count, comparable with the Deepgram path (task-231 §13.1).
        "segments_count": count_paragraphs(transcript_text),
        "duration_seconds": 0,
        "source_url": source_url,
        "transcribed_at": _now_iso_utc(),
        "source_detail": "apify_tiktok_transcript",
    }


async def _upload_native_transcript(job_id: str, text: str) -> str:
    """Upload the transcript, normalized to paragraph-delimited plain text.

    The normalizer is idempotent, so text already grouped upstream passes
    through untouched.
    """
    transcript_s3_key = f"{job_id}.txt"
    normalized = normalize_transcript_text(text, source="tiktok")
    await s3.upload_file_object(
        bucket=TRANSCRIPT_BUCKET,
        key=transcript_s3_key,
        file_obj=BytesIO(normalized.encode("utf-8")),
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
    if job.apify_state == "processing":
        job.apify_state = "processed"
        job.apify_completed_at = datetime.now(timezone.utc)
    job.mark_failed(
        error_message=error.user_message,
        error_step="tiktok_ingestion",
    )
    await database_async.update_processing_job(job)


async def process_tiktok_message(message_body: Dict[str, Any]) -> Dict[str, Any]:
    message_type = str(message_body.get("message_type") or "ingest")
    job_id = (message_body.get("job_id") or "").strip()

    if not job_id:
        raise TikTokIngestionError(
            "extractor_failed",
            details="missing_job_id",
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

    if message_type == "apify_backstop":
        expired = await apify_orchestration.expire_backstop(
            job_id=job_id,
            run_id=str(message_body.get("apify_run_id") or ""),
            source_platform="tiktok",
        )
        if expired:
            await _publish_failure_event(
                job_id=job_id,
                media_key=message_body.get("media_key") or expired.media_key,
                reason="apify_callback_deadline_exceeded",
            )
        return {"mode": "apify_backstop", "job_id": job_id}

    callback_envelope = dict(message_body)
    if message_type == "apify_callback":
        run_id = str(message_body.get("apify_run_id") or "").strip()
        job = await apify_orchestration.claim_callback(job_id, run_id)
        if not job:
            return {"mode": "apify_callback_ignored", "job_id": job_id}
        message_body = dict(job.apify_context or {})
        callback_status = str(callback_envelope.get("apify_status") or "").upper()
        if callback_status != "SUCCEEDED":
            raise TikTokIngestionError(
                "apify_actor_failed",
                details=f"apify_terminal_{callback_status}",
                retryable=False,
                user_message=_UNSUPPORTED_MESSAGE,
            )
        try:
            items = await apify_adapter.fetch_dataset_items(
                source_platform="tiktok",
                dataset_id=job.apify_dataset_id or "",
            )
        except apify_adapter.ApifyAdapterError as exc:
            raise TikTokIngestionError(
                "apify_actor_failed",
                details=exc.code,
                retryable=exc.retryable,
                user_message=(_TEMPORARY_EXTRACTOR_MESSAGE if exc.retryable else _UNSUPPORTED_MESSAGE),
            ) from exc
        normalized_url = str(message_body.get("normalized_url") or "").strip()
        if not normalized_url:
            raise TikTokIngestionError(
                "apify_actor_failed",
                details="apify_context_missing_url",
                retryable=False,
                user_message=_UNSUPPORTED_MESSAGE,
            )
        tiktok_id = _extract_tiktok_id(normalized_url)
        return await _complete_apify_fallback(
            job=job,
            tiktok_id=tiktok_id,
            normalized_url=normalized_url,
            message_body=message_body,
            items=items,
        )

    normalized_url = (message_body.get("normalized_url") or "").strip()
    if not normalized_url:
        raise TikTokIngestionError(
            "extractor_failed",
            details="missing_normalized_url",
            retryable=False,
            user_message=_TEMPORARY_EXTRACTOR_MESSAGE,
        )

    job.mark_extracting()
    await database_async.update_processing_job(job)

    normalized_url, force_ip_block = strip_e2e_force_ip_block_sentinel(normalized_url)
    tiktok_id = _extract_tiktok_id(normalized_url)

    if force_ip_block:
        log_event(
            logger,
            logging.WARNING,
            "extraction.ip_blocked",
            "E2E sentinel forced IP-block path; routing to Apify fallback",
            job_id=job_id,
            tiktok_id=tiktok_id,
            detail="e2e_sentinel_force_ip_block",
        )
        return await _start_apify_fallback(
            job=job,
            tiktok_id=tiktok_id,
            normalized_url=normalized_url,
            message_body=message_body,
        )

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
        return await _start_apify_fallback(
            job=job,
            tiktok_id=tiktok_id,
            normalized_url=normalized_url,
            message_body=message_body,
        )

    # On TikTok, yt-dlp's `title` IS the clip caption (the extractor derives it
    # from the description), which is the only human-written text the platform
    # exposes -- so it is the title, and the creator handle never is (task-266).
    ytdlp_title = select_title(
        [info.get("title"), info.get("description")],
        authors=[info.get("uploader"), info.get("creator"), info.get("uploader_id")],
    )
    if ytdlp_title:
        job.title = ytdlp_title

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
        job.media_url = audio_result["audio_url"]
        job.mark_transcribing()
        await database_async.update_processing_job(job)

        # No captions: this clip is about to be transcribed by the minute, so it
        # is charged to the audio quota like any other Deepgram job (task-250
        # Layer 1). yt-dlp already resolved the exact duration.
        gate = await audio_quota_gate.gate_audio_transcription(
            job_id=job.id,
            user_id=message_body.get("user_id"),
            job=job,
            media_key=message_body.get("media_key"),
            known_duration_seconds=int(audio_result.get("audio_duration_seconds") or 0),
            error_step="tiktok_ingestion",
        )
        if not gate.allowed:
            return {
                "mode": "quota_refused",
                "job_id": job.id,
                "media_key": message_body.get("media_key"),
                "tiktok_id": tiktok_id,
                "error_code": gate.error_code,
            }

        await enqueue_deepgram_transcription(
            job_id=job.id,
            audio_url=audio_result["audio_url"],
            deepgram_mode="pull_with_push_fallback",
            source_platform="tiktok",
            media_key=message_body.get("media_key"),
            user_id=message_body.get("user_id"),
            user_email=message_body.get("user_email"),
            normalized_url=normalized_url,
            episode_title=job.title or message_body.get("episode_title"),
            podcast_title=message_body.get("podcast_title") or job.source_platform,
            audio_duration_seconds=gate.duration_seconds,
            quota_debited_minutes=gate.debited_minutes,
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


async def _start_apify_fallback(
    *,
    job: ProcessingJob,
    tiktok_id: str,
    normalized_url: str,
    message_body: Dict[str, Any],
) -> Dict[str, Any]:
    """Start the transcript actor and return without waiting for completion."""
    context = dict(message_body)
    context.update(
        {
            "job_id": job.id,
            "normalized_url": normalized_url,
            "tiktok_id": tiktok_id,
        }
    )
    for transient_key in ("message_type", "apify_run_id", "apify_status"):
        context.pop(transient_key, None)
    try:
        run = await apify_orchestration.start_run_for_job(
            job=job,
            kind=ApifyActorKind.TIKTOK_TRANSCRIPT,
            source_platform="tiktok",
            input_data={"videos": [normalized_url]},
            queue_name=TIKTOK_INGESTION_QUEUE,
            context=context,
        )
    except apify_adapter.ApifyAdapterError as exc:
        raise TikTokIngestionError(
            "apify_actor_failed",
            details=exc.code,
            retryable=exc.retryable,
            user_message=(_TEMPORARY_EXTRACTOR_MESSAGE if exc.retryable else _UNSUPPORTED_MESSAGE),
        ) from exc

    return {
        "mode": "apify_pending",
        "job_id": job.id,
        "media_key": message_body.get("media_key"),
        "tiktok_id": tiktok_id,
        "apify_run_id": run.run_id,
    }


async def _complete_apify_fallback(
    *,
    job: ProcessingJob,
    tiktok_id: str,
    normalized_url: str,
    message_body: Dict[str, Any],
    items: list[Dict[str, Any]],
) -> Dict[str, Any]:
    """Complete a claimed callback from its already-terminal dataset."""
    transcript_text = _extract_apify_transcript_text(items)

    if not transcript_text:
        raise TikTokIngestionError(
            "apify_actor_failed",
            details="apify_no_transcript",
            retryable=False,
            user_message=_UNSUPPORTED_MESSAGE,
        )

    transcript_s3_key = await _upload_native_transcript(job.id, transcript_text)
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
    if not await apify_orchestration.complete_callback(job):
        return {"mode": "apify_callback_ignored", "job_id": job.id}

    await _publish_success_event(
        job_id=job.id,
        media_key=message_body.get("media_key"),
        transcript_s3_key=transcript_s3_key,
        transcription_metadata=transcription_metadata,
    )

    log_event(
        logger,
        logging.INFO,
        "transcription.completed",
        "TikTok Apify native transcript completed",
        job_id=job.id,
        tiktok_id=tiktok_id,
        fallback_strategy="apify_native_transcript",
    )

    return {
        "mode": "apify_native_transcript",
        "job_id": job.id,
        "media_key": message_body.get("media_key"),
        "tiktok_id": tiktok_id,
        "source_detail": "apify_tiktok_transcript",
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

    receive_count = int((message.get("Attributes") or {}).get("ApproximateReceiveCount", "1"))

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
        elif result["mode"] in {
            "apify_pending",
            "apify_callback_ignored",
            "apify_backstop",
        }:
            log_event(
                logger,
                logging.INFO,
                "apify.orchestration",
                "TikTok Apify orchestration advanced",
                job_id=result["job_id"],
                media_item_id=result["job_id"],
                orchestration_mode=result["mode"],
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
            receive_params = get_sqs_receive_params(visibility_timeout=360)
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
