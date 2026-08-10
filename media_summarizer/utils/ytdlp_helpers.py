"""
Shared yt-dlp helpers for subtitle collection and media-URL resolution.

Used by both the TikTok and YouTube ingestion workers.
"""

from __future__ import annotations

import html
import json
import re
from typing import Any, Dict

import httpx

from media_summarizer.core.services.transcript_formatting import (
    count_paragraphs,
    group_caption_lines,
)

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
_AUDIO_URL_PROTOCOLS = {
    "http",
    "https",
    "http_dash_segments",
    "https_dash_segments",
}


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


def collect_subtitle_candidates(info: Dict[str, Any]) -> list[Dict[str, Any]]:
    """
    Collect all subtitle candidates from yt-dlp info dict.

    Prefers requested_subtitles, then manual subtitles, then automatic_captions.
    Sorted by: requested first, then higher ext priority, then language.
    """
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
                    "is_automatic": False,
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
                        "is_automatic": False,
                    }
                )

    automatic_captions = info.get("automatic_captions")
    if isinstance(automatic_captions, dict):
        for language, entries in automatic_captions.items():
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
                        "is_automatic": True,
                    }
                )

    # Sort: requested first, manual before automatic, higher ext priority, then language
    candidates.sort(
        key=lambda item: (
            0 if item["requested"] else 1,
            0 if not item.get("is_automatic") else 1,
            -_subtitle_ext_priority(item["ext"]),
            item["language"],
        )
    )
    return candidates


def _clean_caption_line(line: str) -> str:
    stripped = _HTML_TAG_RE.sub("", html.unescape((line or "").strip()))
    return stripped.strip()


def parse_timed_text_payload(payload: str) -> str:
    """Parse VTT/SRT formatted subtitle payload into plain text."""
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


def _extract_json_caption_text(
    node: Any, collected: list[str], seen: set[str]
) -> None:
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


def parse_json_caption_payload(payload: str) -> str:
    """Parse JSON-formatted subtitle payload into plain text."""
    data = json.loads(payload)
    collected: list[str] = []
    seen: set[str] = set()
    _extract_json_caption_text(data, collected, seen)
    return "\n".join(collected).strip()


def parse_caption_payload(
    *,
    payload: str,
    ext: str,
    content_type: str,
) -> str:
    """
    Parse a subtitle payload into plain text.

    Detects JSON vs timed-text (VTT/SRT) format based on ext, content-type,
    or payload prefix.
    """
    normalized_ext = (ext or "").strip().lower()
    normalized_content_type = (content_type or "").strip().lower()
    is_json = (
        normalized_ext in {"json", "srv3"}
        or "application/json" in normalized_content_type
        or payload.lstrip().startswith(("{", "["))
    )
    if is_json:
        return parse_json_caption_payload(payload)
    return parse_timed_text_payload(payload)


async def fetch_subtitle_candidate(
    candidate: Dict[str, Any],
    *,
    timeout_seconds: float = 20.0,
    platform_label: str = "unknown",
) -> Dict[str, Any]:
    """
    Fetch and parse a single subtitle candidate.

    Returns a dict with text, language, segments_count, source_detail, etc.
    Raises SubtitleFetchError on network/HTTP failures.
    Raises SubtitleUnavailableError when the subtitle content is empty.
    """
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
            raise SubtitleUnavailableError("native_subtitles_absent")
        try:
            async with httpx.AsyncClient(
                timeout=timeout_seconds,
                follow_redirects=True,
            ) as client:
                response = await client.get(subtitle_url)
        except (httpx.TimeoutException, httpx.TransportError) as exc:
            raise SubtitleFetchError(
                f"subtitle_fetch:{type(exc).__name__}",
                retryable=True,
            ) from exc
        if response.status_code >= 400:
            raise SubtitleFetchError(
                f"subtitle_http_status:{response.status_code}",
                retryable=response.status_code >= 500,
            )
        payload = response.text
        content_type = response.headers.get("content-type", "")

    cue_text = parse_caption_payload(
        payload=payload,
        ext=str(candidate.get("ext") or ""),
        content_type=content_type,
    )
    if not cue_text:
        raise SubtitleUnavailableError("native_subtitles_absent")

    # Caption cues are display units, not sentences: one cue per line renders as
    # a wall of short fragments. Group them into paragraphs before the text is
    # stored (task-231 option B).
    text = group_caption_lines(cue_text.splitlines(), source=platform_label)
    if not text:
        raise SubtitleUnavailableError("native_subtitles_absent")

    is_automatic = candidate.get("is_automatic", False)
    source_prefix = f"{platform_label}_auto_captions" if is_automatic else f"{platform_label}_native_subtitles"

    return {
        "text": text,
        "language": str(candidate.get("language") or "").strip() or None,
        # Paragraph count, so the badge is comparable with the Deepgram path
        # instead of reporting raw cue-line counts (task-231 section 13.1).
        "segments_count": count_paragraphs(text),
        "source_detail": (
            f"{source_prefix}:{candidate.get('language') or 'unknown'}:"
            f"{candidate.get('ext') or 'unknown'}"
        ),
        "source_url": str(candidate.get("url") or "").strip() or None,
        "ext": str(candidate.get("ext") or "").strip() or None,
        "is_automatic": is_automatic,
    }


def select_direct_media_stream(
    info: Dict[str, Any],
    *,
    reject_live: bool = True,
) -> Dict[str, Any]:
    """
    Select the best transcribable media stream from yt-dlp info dict.

    Prefers audio-only streams with the highest bitrate.
    Raises MediaStreamUnavailableError if no suitable stream is found.
    """
    if reject_live and info.get("is_live"):
        raise MediaStreamUnavailableError("live_content_not_supported")

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
        raise MediaStreamUnavailableError("no_transcribable_media_url")

    return best_candidate


def resolve_direct_media_url(info: Dict[str, Any]) -> Dict[str, Any]:
    """
    Resolve the best direct media URL from yt-dlp info dict.

    Returns a dict with audio_url, audio_duration_seconds, format metadata.
    Raises MediaStreamUnavailableError if no suitable stream is found.
    """
    selected = select_direct_media_stream(info)
    audio_url = str(selected.get("url") or "").strip()
    if not audio_url:
        raise MediaStreamUnavailableError("missing_media_url")

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


# ---------------------------------------------------------------------------
# Exception classes for the shared helpers
# ---------------------------------------------------------------------------


class SubtitleUnavailableError(Exception):
    """Raised when subtitles are not available (empty or absent)."""

    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


class SubtitleFetchError(Exception):
    """Raised when subtitle fetch fails due to network/HTTP error."""

    def __init__(self, details: str, *, retryable: bool = False) -> None:
        super().__init__(details)
        self.details = details
        self.retryable = retryable


class MediaStreamUnavailableError(Exception):
    """Raised when no suitable media stream can be resolved."""

    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason
