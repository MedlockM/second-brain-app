"""Single, server-side rules for a media's cover image and creator name (task-304).

Implements the derivation the owner retained at the end of task-302
(`docs/research/task-302-media-cover-and-creator/README.md`, `Decision`:
**Approach C**): read what the pipeline already holds, hotlink the covers whose
CDN URL is unsigned and stable, and re-host only the sources whose URL is signed
and expiring (Instagram, TikTok) or private (camera and gallery photos).

Two facts, two rules:

* **The creator is a publisher, not an author** (benchmark §7.3). One field, and
  where a source offers both the site and the byline, the site wins: in five of
  six sources the entity a reader recognises is the thing that publishes. The
  candidates arrive in that order and the first survivor is kept.
* **A cover is either hotlinked or re-hosted**, and `user_media.thumbnail_url`
  carries both shapes: an absolute ``https://`` URL, or an ``s3://bucket/key``
  locator resolved into a presigned URL at read time (benchmark §5.5). One
  carrier, no parallel image attribute.

Everything in this module is pure: no I/O, no provider call. Fetching and
resizing a re-hosted cover lives in ``core/services/cover_capture.py``, which is
the only part of the feature that touches the network.
"""

from __future__ import annotations

import re
from typing import Iterable, Optional, Sequence, Tuple
from urllib.parse import parse_qs, urlsplit

from media_summarizer.core.media_ingestion.title_derivation import (
    _normalize_for_comparison,
    _truncate_on_word_boundary,
)

# A tile's second line. Long enough for "Le Monde diplomatique" or "The Rest Is
# History", short enough that it never wraps under the title.
MAX_CREATOR_LENGTH = 80

# How a re-hosted cover is stored on the durable row. Any other value of
# ``thumbnail_url`` is a third-party URL the client fetches directly.
COVER_LOCATOR_SCHEME = "s3://"

_WHITESPACE_RE = re.compile(r"\s+")

# Names that identify nobody. Same spirit as the title placeholders: a closed
# list of *provable* rejections, never a quality score (benchmark §6.2 of
# task-265, which this module deliberately mirrors).
_GENERIC_CREATORS = frozenset(
    {
        "unknown",
        "unknown artist",
        "unknown author",
        "anonymous",
        "admin",
        "administrator",
        "author",
        "editor",
        "staff",
        "guest",
        "user",
        "none",
        "null",
        "n/a",
        "na",
        "-",
        "podcast",
        "untitled",
    }
)

# yt-dlp and several CMS templates emit these instead of a real account name.
_CREATOR_PLACEHOLDER_RES = (
    re.compile(r"^video by\b", re.IGNORECASE),
    re.compile(r"^post by\b", re.IGNORECASE),
    re.compile(r"^by\s*$", re.IGNORECASE),
    re.compile(r"^[0-9a-f]{16,}$", re.IGNORECASE),
    re.compile(r"^\d+$"),
)

# Schemes a client can actually render. `data:` is excluded on purpose: an
# inlined image would be stored in DynamoDB and returned on every list read.
_ALLOWED_COVER_SCHEMES = frozenset({"http", "https"})

_YOUTUBE_ID_RE = re.compile(r"^[A-Za-z0-9_-]{11}$")

# Hosts whose `/watch?v=`, `/shorts/`, `/embed/` and `/live/` forms all carry the
# video id in the URL itself. `youtu.be` puts it in the first path segment.
_YOUTUBE_HOSTS = frozenset(
    {"youtube.com", "www.youtube.com", "m.youtube.com", "music.youtube.com"}
)
_YOUTUBE_SHORT_HOSTS = frozenset({"youtu.be", "www.youtu.be"})
_YOUTUBE_ID_PATH_PREFIXES = frozenset({"shorts", "embed", "live"})


def normalize_creator_name(raw: Optional[str]) -> Optional[str]:
    """Clean one raw creator candidate, or ``None`` when nothing usable remains.

    Folds whitespace, drops the provider placeholders above, and truncates on a
    word boundary. A leading ``@`` is deliberately **kept**: it is how a handle
    reads on a tile. Deduplication against the display name still works, because
    the comparison key strips punctuation.

    Purely deterministic -- there is no notion of a "good" name here, only of a
    provably useless one.
    """
    if not raw:
        return None
    value = _WHITESPACE_RE.sub(" ", str(raw).strip())
    if not value:
        return None

    if any(pattern.match(value.lstrip("@")) for pattern in _CREATOR_PLACEHOLDER_RES):
        return None
    comparable = _normalize_for_comparison(value)
    # Punctuation-only ("@", "--"): nothing a reader could recognise.
    if not comparable or comparable in _GENERIC_CREATORS:
        return None
    # A URL is a location, not a name. Some feeds put the site's homepage in
    # `<itunes:author>`.
    if urlsplit(value).scheme in _ALLOWED_COVER_SCHEMES:
        return None

    return _truncate_on_word_boundary(value, MAX_CREATOR_LENGTH) or None


def select_creator(
    candidates: Sequence[Optional[str]],
    *,
    title: Optional[str] = None,
) -> Optional[str]:
    """First candidate that survives, publisher first, or ``None``.

    ``title`` is the row's stored title: a creator equal to it is dropped rather
    than rendered twice on the tile. That is the inverse of task-266's "the title
    must never be the author" rule, and it uses the same comparison helper so the
    two can never disagree.
    """
    title_key = _normalize_for_comparison(title) if title else ""
    seen: set[str] = set()

    for candidate in candidates:
        normalized = normalize_creator_name(candidate)
        if not normalized:
            continue
        key = _normalize_for_comparison(normalized)
        if not key or key in seen:
            continue
        seen.add(key)
        if title_key and key == title_key:
            continue
        return normalized
    return None


def normalize_cover_url(raw: Optional[str]) -> Optional[str]:
    """An absolute ``http(s)`` cover URL, or ``None``.

    Providers return empty strings, relative paths and the occasional ``data:``
    blob; none of those is renderable by the client, and storing one costs a
    round-trip per list read to discover that.
    """
    if not raw:
        return None
    value = str(raw).strip()
    if not value:
        return None
    if value.startswith(COVER_LOCATOR_SCHEME):
        return value
    parts = urlsplit(value)
    if parts.scheme not in _ALLOWED_COVER_SCHEMES or not parts.netloc:
        return None
    return value


def largest_thumbnail(thumbnails: Optional[Iterable[dict]]) -> Optional[str]:
    """Best cover from a yt-dlp ``thumbnails`` list, by pixel area.

    yt-dlp exposes both ``thumbnail`` (its own pick) and ``thumbnails`` (every
    variant). The single field is enough on YouTube, where it is always an
    ``i.ytimg.com`` URL; this helper exists for the extractors that only fill the
    list.
    """
    if not thumbnails:
        return None
    best: Optional[str] = None
    best_area = -1
    for entry in thumbnails:
        if not isinstance(entry, dict):
            continue
        url = normalize_cover_url(entry.get("url"))
        if not url:
            continue
        try:
            area = int(entry.get("width") or 0) * int(entry.get("height") or 0)
        except (TypeError, ValueError):
            area = 0
        if area > best_area:
            best, best_area = url, area
    return best


def youtube_video_id(url: Optional[str]) -> Optional[str]:
    """The video id carried by a YouTube URL, or ``None`` when there is none.

    Pure parsing, like everything else in this module, and the *only* YouTube id
    parser in the codebase: the ingestion worker calls it too, so the id the
    submission derives its cover from and the id the worker fetches a transcript
    for can never diverge.

    ``None`` rather than an exception, because the first caller is the resolver:
    an URL the router classified as YouTube but whose id cannot be read must
    still be submitted -- it just starts without a cover.
    """
    split = urlsplit((url or "").strip())
    host = (split.hostname or "").lower()
    path = split.path or ""
    parts = [segment for segment in path.split("/") if segment]

    if host in _YOUTUBE_HOSTS:
        if path == "/watch":
            candidate = (parse_qs(split.query).get("v") or [""])[0].strip()
            if candidate:
                return candidate
        if len(parts) >= 2 and parts[0] in _YOUTUBE_ID_PATH_PREFIXES:
            return parts[1].strip() or None
    if host in _YOUTUBE_SHORT_HOSTS and parts:
        return parts[0].strip() or None
    return None


def youtube_thumbnail_url(video_id: Optional[str]) -> Optional[str]:
    """Deterministic ``i.ytimg.com`` cover for a video id, or ``None``.

    ``hqdefault`` rather than ``maxresdefault``: the high-resolution variant is
    absent on older and low-resolution uploads, and a 404 here is a blank tile.

    No network and no provider: the id is in the URL, so a YouTube save carries
    its cover from the moment it is submitted rather than from the end of its
    transcription (task-353).
    """
    if not video_id:
        return None
    candidate = str(video_id).strip()
    if not _YOUTUBE_ID_RE.match(candidate):
        return None
    return f"https://i.ytimg.com/vi/{candidate}/hqdefault.jpg"


def build_cover_locator(bucket: str, key: str) -> str:
    """``s3://bucket/key`` -- how a re-hosted cover is stored on the row."""
    return f"{COVER_LOCATOR_SCHEME}{bucket}/{key}"


def parse_cover_locator(value: Optional[str]) -> Optional[Tuple[str, str]]:
    """``(bucket, key)`` for a re-hosted cover, ``None`` for a hotlinked URL."""
    if not value or not value.startswith(COVER_LOCATOR_SCHEME):
        return None
    remainder = value[len(COVER_LOCATOR_SCHEME):]
    bucket, _, key = remainder.partition("/")
    if not bucket or not key:
        return None
    return bucket, key
