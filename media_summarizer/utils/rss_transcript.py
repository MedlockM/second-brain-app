"""
RSS Transcript fetcher for Podcasting 2.0 <podcast:transcript> tags.

This module attempts to retrieve a pre-existing transcript from a podcast's
RSS feed before falling back to audio transcription (Deepgram/Whisper).

Podcasting 2.0 spec reference:
  https://github.com/Podcastindex-org/podcast-namespace/blob/main/docs/1.0.md#transcript

The <podcast:transcript> element may appear inside an <item> and provides a
URL to a transcript file in various formats (SRT, VTT, JSON, plain text).
"""

from __future__ import annotations

import logging
import re
from typing import Optional
from xml.etree import ElementTree as ET

import httpx

logger = logging.getLogger(__name__)

# Podcasting 2.0 namespace
PODCAST_NS = "https://podcastindex.org/namespace/1.0"

# Supported transcript MIME types in order of preference
# Plain text and SRT/VTT are easy to normalize; JSON transcript requires more parsing.
SUPPORTED_TYPES = [
    "text/plain",
    "text/srt",
    "application/srt",
    "text/vtt",
    "application/x-subrip",
    "application/json",
]

# HTTP timeout for fetching feeds and transcripts
_FETCH_TIMEOUT = httpx.Timeout(20.0)


async def fetch_rss_transcript(
    *,
    feed_url: str,
    episode_guid: str,
) -> Optional[str]:
    """
    Attempt to fetch a transcript from the RSS feed for a specific episode.

    Looks for <podcast:transcript> elements inside the <item> whose <guid>
    matches `episode_guid`. Downloads and normalizes the first usable
    transcript found.

    Args:
        feed_url: The RSS feed URL.
        episode_guid: The GUID of the target episode.

    Returns:
        The transcript text if found and usable, None otherwise.
    """
    if not feed_url or not episode_guid:
        return None

    try:
        rss_content = await _fetch_feed(feed_url)
        if not rss_content:
            return None

        transcript_url, transcript_type = _find_transcript_element(
            rss_content, episode_guid
        )
        if not transcript_url:
            logger.info(
                "No <podcast:transcript> found for episode %s in feed %s",
                episode_guid,
                feed_url,
            )
            return None

        logger.info(
            "Found RSS transcript for episode %s: %s (type=%s)",
            episode_guid,
            transcript_url,
            transcript_type,
        )

        raw_content = await _download_transcript(transcript_url)
        if not raw_content:
            return None

        normalized = _normalize_transcript(raw_content, transcript_type)
        if not normalized or len(normalized.strip()) < 50:
            logger.warning(
                "RSS transcript too short or empty after normalization (episode=%s)",
                episode_guid,
            )
            return None

        return normalized

    except Exception as e:
        logger.warning(
            "Failed to fetch RSS transcript for episode %s: %s",
            episode_guid,
            str(e),
        )
        return None


async def _fetch_feed(feed_url: str) -> Optional[str]:
    """Fetch the raw RSS feed XML content."""
    try:
        async with httpx.AsyncClient(timeout=_FETCH_TIMEOUT, follow_redirects=True) as client:
            response = await client.get(feed_url)
            response.raise_for_status()
            return response.text
    except Exception as e:
        logger.warning("Failed to fetch RSS feed %s: %s", feed_url, str(e))
        return None


def _find_transcript_element(
    rss_content: str, episode_guid: str
) -> tuple[Optional[str], Optional[str]]:
    """
    Parse RSS XML and find the <podcast:transcript> element for the given episode.

    Returns (transcript_url, mime_type) or (None, None) if not found.
    """
    try:
        # Register the podcast namespace
        ET.register_namespace("podcast", PODCAST_NS)

        root = ET.fromstring(rss_content)
        channel = root.find("channel")
        if channel is None:
            return None, None

        # Iterate over items to find the matching episode
        for item in channel.findall("item"):
            guid_el = item.find("guid")
            if guid_el is None:
                continue

            item_guid = (guid_el.text or "").strip()
            if item_guid != episode_guid:
                continue

            # Found the episode - look for podcast:transcript elements
            transcripts = item.findall(f"{{{PODCAST_NS}}}transcript")
            if not transcripts:
                return None, None

            # Sort by preference (prefer plain text, then SRT/VTT, then JSON)
            best_url = None
            best_type = None
            best_priority = len(SUPPORTED_TYPES)

            for t_el in transcripts:
                url = t_el.get("url", "").strip()
                mime_type = (t_el.get("type") or "").strip().lower()

                if not url:
                    continue

                # Find priority based on supported types
                try:
                    priority = SUPPORTED_TYPES.index(mime_type)
                except ValueError:
                    # Unknown type - still try if it looks like text
                    priority = len(SUPPORTED_TYPES)

                if priority < best_priority:
                    best_url = url
                    best_type = mime_type
                    best_priority = priority

            # If no typed match, take the first one with a URL
            if not best_url:
                for t_el in transcripts:
                    url = t_el.get("url", "").strip()
                    if url:
                        best_url = url
                        best_type = t_el.get("type", "text/plain").strip().lower()
                        break

            return best_url, best_type

        # Episode GUID not found in feed
        return None, None

    except ET.ParseError as e:
        logger.warning("Failed to parse RSS feed XML: %s", str(e))
        return None, None


async def _download_transcript(url: str) -> Optional[str]:
    """Download the transcript content from the given URL."""
    try:
        async with httpx.AsyncClient(timeout=_FETCH_TIMEOUT, follow_redirects=True) as client:
            response = await client.get(url)
            response.raise_for_status()
            return response.text
    except Exception as e:
        logger.warning("Failed to download transcript from %s: %s", url, str(e))
        return None


def _normalize_transcript(content: str, mime_type: Optional[str]) -> str:
    """
    Normalize transcript content based on its format.

    Converts SRT, VTT, and JSON transcripts to plain text.
    """
    if not content:
        return ""

    mime_type = (mime_type or "").lower()

    if mime_type in ("text/plain",):
        return content.strip()

    if mime_type in ("text/srt", "application/srt", "application/x-subrip"):
        return _srt_to_text(content)

    if mime_type in ("text/vtt",):
        return _vtt_to_text(content)

    if mime_type in ("application/json",):
        return _json_transcript_to_text(content)

    # Unknown type - try SRT/VTT heuristic, otherwise return as-is
    if _looks_like_srt(content):
        return _srt_to_text(content)
    if _looks_like_vtt(content):
        return _vtt_to_text(content)

    return content.strip()


def _looks_like_srt(content: str) -> bool:
    """Heuristic: does this content look like SRT format?"""
    lines = content.strip().split("\n")
    if len(lines) < 3:
        return False
    # SRT files start with a sequence number (digit)
    return lines[0].strip().isdigit() and "-->" in lines[1]


def _looks_like_vtt(content: str) -> bool:
    """Heuristic: does this content look like WebVTT format?"""
    return content.strip().startswith("WEBVTT")


def _srt_to_text(content: str) -> str:
    """Convert SRT subtitle format to plain text."""
    lines = content.split("\n")
    text_lines = []
    # SRT format: sequence number, timestamp line, text, blank line
    # We skip sequence numbers and timestamp lines
    timestamp_pattern = re.compile(r"\d{2}:\d{2}:\d{2}[.,]\d{3}\s*-->\s*\d{2}:\d{2}:\d{2}[.,]\d{3}")

    for line in lines:
        line = line.strip()
        if not line:
            continue
        if line.isdigit():
            continue
        if timestamp_pattern.match(line):
            continue
        # Remove HTML-like tags (e.g., <i>, <b>)
        line = re.sub(r"<[^>]+>", "", line)
        text_lines.append(line)

    return " ".join(text_lines)


def _vtt_to_text(content: str) -> str:
    """Convert WebVTT format to plain text."""
    lines = content.split("\n")
    text_lines = []
    timestamp_pattern = re.compile(r"\d{2}:\d{2}[:.]\d{2}[.,]\d{3}\s*-->\s*\d{2}:\d{2}[:.]\d{2}[.,]\d{3}")

    skip_header = True
    for line in lines:
        line = line.strip()

        # Skip the WEBVTT header and any NOTE/STYLE blocks
        if skip_header:
            if line.startswith("WEBVTT"):
                continue
            if line.startswith("NOTE") or line.startswith("STYLE"):
                continue
            if not line:
                skip_header = False
                continue

        if not line:
            continue
        if timestamp_pattern.match(line):
            continue
        # Skip cue identifiers (lines that are just numbers or identifiers before timestamps)
        if line.isdigit():
            continue
        # Remove HTML-like tags
        line = re.sub(r"<[^>]+>", "", line)
        text_lines.append(line)

    return " ".join(text_lines)


def _json_transcript_to_text(content: str) -> str:
    """
    Convert JSON transcript format to plain text.

    Supports common JSON transcript formats:
    - Podcasting 2.0 JSON: {"segments": [{"body": "text", ...}]}
    - Alternative: {"segments": [{"text": "...", ...}]}
    - Or direct array: [{"body": "text"}, ...]
    """
    import json

    try:
        data = json.loads(content)
    except json.JSONDecodeError:
        return content.strip()

    segments = []

    if isinstance(data, dict):
        # Try "segments" key first
        raw_segments = data.get("segments", data.get("results", []))
        if not raw_segments and isinstance(data.get("body"), str):
            # Simple {body: "full text"} format
            return data["body"].strip()
    elif isinstance(data, list):
        raw_segments = data
    else:
        return str(data)

    for seg in raw_segments:
        if isinstance(seg, dict):
            text = seg.get("body") or seg.get("text") or seg.get("content") or ""
            if text:
                segments.append(text.strip())
        elif isinstance(seg, str):
            segments.append(seg.strip())

    return " ".join(segments)
