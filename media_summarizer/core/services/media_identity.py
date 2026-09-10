"""
Media identity helpers.

This module defines the canonical URL normalization policy and the deterministic
media key generation used for cross-media idempotence.

It also owns the **source type** of a URL (`MediaSourceType`,
`classify_source_type`): the single place that decides what kind of thing a link
points at. Both the canonicalization below and the ingestion classifier
(`core/media_ingestion/adapters/classifiers.py`) read that one answer, because
two host tables deciding the same question is how they come to disagree.

`WEB_ARTICLE` is a *recognised* type with its own criterion, not the leftover of
a chain of per-domain branches (task-392): whether a URL is an article decides
whether its text is fetched before its identity is settled, so it cannot be a
classification default.
"""

from __future__ import annotations

import hashlib
import re
from enum import Enum
from typing import Dict, List, Tuple
from urllib.parse import parse_qsl, quote, urlencode, urlsplit, urlunsplit

_TRACKING_QUERY_PREFIXES = ("utm_",)
_TRACKING_QUERY_KEYS = {
    "fbclid",
    "gclid",
    "igshid",
    "mc_cid",
    "mc_eid",
    "ref",
    "source",
    "_r",
    "_t",
}

_YOUTUBE_HOSTS = {
    "youtube.com",
    "www.youtube.com",
    "m.youtube.com",
    "music.youtube.com",
    "youtu.be",
    "www.youtu.be",
}
_INSTAGRAM_HOSTS = {"instagram.com", "www.instagram.com"}
_X_HOSTS = {"x.com", "www.x.com", "twitter.com", "www.twitter.com"}
_TIKTOK_SHORT_HOSTS = {"vm.tiktok.com", "vt.tiktok.com"}
_TIKTOK_HOSTS = {
    "tiktok.com",
    "www.tiktok.com",
    "m.tiktok.com",
    *_TIKTOK_SHORT_HOSTS,
}
_SPOTIFY_HOSTS = {"open.spotify.com", "www.open.spotify.com"}
_APPLE_PODCASTS_HOSTS = {"podcasts.apple.com", "www.podcasts.apple.com"}
_DEEZER_HOSTS = {"deezer.com", "www.deezer.com"}

#: A host that serves feeds and nothing else. `feeds.example.com` is a feed even
#: when its path says nothing.
_FEED_HOST_PREFIXES = ("feeds.", "rss.")
#: Path extensions that make a URL a direct audio import rather than a page.
_AUDIO_EXTENSIONS = (
    ".mp3",
    ".m4a",
    ".aac",
    ".ogg",
    ".wav",
    ".flac",
    ".opus",
)

_MULTI_SLASH_RE = re.compile(r"/+")


class MediaSourceType(str, Enum):
    """What kind of source a URL points at, decided once for the whole pipeline.

    The values are stable identifiers, not display labels. `WEB_ARTICLE` is the
    last *criterion*, not a fallback bucket: a link is an article when it is an
    http(s) page on a host we recognise no platform for, and whose path is
    neither a feed nor a media file. Everything a page is not has its own member,
    so adding a source means adding a member here rather than another `elif`
    somewhere downstream.
    """

    YOUTUBE = "youtube"
    INSTAGRAM = "instagram"
    TIKTOK = "tiktok"
    X = "x"
    SPOTIFY = "spotify"
    APPLE_PODCASTS = "apple_podcasts"
    DEEZER = "deezer"
    FEED = "feed"
    AUDIO_FILE = "audio_file"
    WEB_ARTICLE = "web_article"


#: The hosts each platform source type is recognised by. Published so the
#: ingestion classifier and the share showcase read the same table.
PLATFORM_HOSTS: Dict[MediaSourceType, frozenset[str]] = {
    MediaSourceType.YOUTUBE: frozenset(_YOUTUBE_HOSTS),
    MediaSourceType.INSTAGRAM: frozenset(_INSTAGRAM_HOSTS),
    MediaSourceType.TIKTOK: frozenset(_TIKTOK_HOSTS),
    MediaSourceType.X: frozenset(_X_HOSTS),
    MediaSourceType.SPOTIFY: frozenset(_SPOTIFY_HOSTS),
    MediaSourceType.APPLE_PODCASTS: frozenset(_APPLE_PODCASTS_HOSTS),
    MediaSourceType.DEEZER: frozenset(_DEEZER_HOSTS),
}

#: Published for the same reason as `PLATFORM_HOSTS`: the list the share showcase
#: names has to be the list that decides acceptance.
AUDIO_URL_EXTENSIONS: Tuple[str, ...] = _AUDIO_EXTENSIONS

#: Source types whose canonical URL is the publisher's own URL, cleaned of
#: tracking parameters and nothing else. There is no id to extract and no
#: platform route to rewrite.
_URL_PRESERVING_SOURCE_TYPES = frozenset(
    {
        MediaSourceType.APPLE_PODCASTS,
        MediaSourceType.DEEZER,
        MediaSourceType.FEED,
        MediaSourceType.AUDIO_FILE,
        MediaSourceType.WEB_ARTICLE,
    }
)


def _normalize_host(host: str) -> str:
    return (host or "").strip().lower()


def _normalize_path(path: str) -> str:
    # Keep path semantics while normalizing repeated slashes and trailing slash.
    raw = _MULTI_SLASH_RE.sub("/", (path or "").strip())
    if not raw:
        return "/"
    if not raw.startswith("/"):
        raw = "/" + raw
    if raw != "/" and raw.endswith("/"):
        raw = raw[:-1]
    # Quote each segment to keep deterministic escaping.
    return "/".join(quote(seg, safe=":@+") for seg in raw.split("/"))


def _path_segments(path: str) -> Tuple[str, ...]:
    return tuple(segment for segment in path.split("/") if segment)


def _path_looks_like_feed(path: str) -> bool:
    return (
        path.endswith(".rss")
        or path.endswith(".xml")
        or "feed" in _path_segments(path)
    )


def _path_looks_like_audio_file(path: str) -> bool:
    return path.endswith(_AUDIO_EXTENSIONS)


def classify_source_type(*, host: str, path: str) -> MediaSourceType:
    """The source type of one URL, from its host and path.

    The order below is the order the pipeline has always used and is load-bearing
    in one place: the feed criterion is read **before** the platform hosts, so
    `youtube.com/feeds/videos.xml` is a feed rather than a video. Everything else
    is disjoint.

    Returns `WEB_ARTICLE` when the URL is a page: no platform owns the host, the
    path is not a feed and does not end in an audio extension. That is the
    explicit criterion task-392 asked for -- an article is recognised, not left
    over.
    """
    normalized_host = _normalize_host(host)
    normalized_path = (path or "/").lower()

    if normalized_host in _SPOTIFY_HOSTS:
        return MediaSourceType.SPOTIFY
    if normalized_host in _APPLE_PODCASTS_HOSTS:
        return MediaSourceType.APPLE_PODCASTS
    if normalized_host in _DEEZER_HOSTS:
        return MediaSourceType.DEEZER
    if _path_looks_like_feed(normalized_path) or normalized_host.startswith(
        _FEED_HOST_PREFIXES
    ):
        return MediaSourceType.FEED
    if normalized_host in _YOUTUBE_HOSTS:
        return MediaSourceType.YOUTUBE
    if normalized_host in _INSTAGRAM_HOSTS:
        return MediaSourceType.INSTAGRAM
    if normalized_host in _X_HOSTS:
        return MediaSourceType.X
    if normalized_host in _TIKTOK_HOSTS:
        return MediaSourceType.TIKTOK
    if _path_looks_like_audio_file(normalized_path):
        return MediaSourceType.AUDIO_FILE
    return MediaSourceType.WEB_ARTICLE


def _strip_tracking_query(query: str) -> List[Tuple[str, str]]:
    parsed = parse_qsl(query, keep_blank_values=True)
    kept: List[Tuple[str, str]] = []
    for key, value in parsed:
        lowered = key.lower()
        if lowered in _TRACKING_QUERY_KEYS:
            continue
        if any(lowered.startswith(prefix) for prefix in _TRACKING_QUERY_PREFIXES):
            continue
        kept.append((key, value))
    kept.sort(key=lambda item: (item[0], item[1]))
    return kept


def _canon_youtube(host: str, path: str, query_items: List[Tuple[str, str]]) -> Tuple[str, str, str]:
    original_host = host
    host = "youtube.com"
    path = _normalize_path(path)
    query_map: Dict[str, str] = {}
    for key, value in query_items:
        lowered = key.lower()
        if lowered == "v" and value:
            query_map["v"] = value

    if original_host in {"youtube.com", "www.youtube.com", "m.youtube.com", "music.youtube.com"}:
        if (
            path.startswith("/shorts/")
            or path.startswith("/embed/")
            or path.startswith("/live/")
        ):
            parts = [p for p in path.split("/") if p]
            if len(parts) >= 2 and parts[1]:
                query_map["v"] = parts[1]
                path = "/watch"
        elif path == "/watch":
            pass
        elif path and path != "/":
            # Normalize uncommon watch URL variants as-is if no clear video id.
            pass

    # youtu.be short links map to /watch?v=<id>
    if original_host in {"youtu.be", "www.youtu.be"} and path and path != "/watch" and path != "/":
        parts = [p for p in path.split("/") if p]
        if parts and len(parts[0]) >= 6 and "v" not in query_map and parts[0] not in {"watch", "shorts", "embed"}:
            query_map["v"] = parts[0]
            path = "/watch"

    if path == "/watch" and query_map.get("v"):
        query = urlencode([("v", query_map["v"])])
        return host, path, query

    return host, path, ""


def _canon_instagram(path: str) -> Tuple[str, str, str]:
    host = "instagram.com"
    path = _normalize_path(path)
    parts = [p for p in path.split("/") if p]
    if len(parts) >= 2 and parts[0] in {"p", "reel", "tv"}:
        path = f"/{parts[0]}/{parts[1]}"
    return host, path, ""


def _canon_tiktok(host: str, path: str) -> Tuple[str, str, str]:
    path = _normalize_path(path)
    parts = [p for p in path.split("/") if p]
    # Keep canonical user/video and user/photo routes, and t-short routes.
    if len(parts) >= 3 and parts[0].startswith("@") and parts[1] in ("video", "photo"):
        return "tiktok.com", f"/{parts[0]}/{parts[1]}/{parts[2]}", ""
    if len(parts) >= 2 and parts[0] == "t":
        return "tiktok.com", f"/t/{parts[1]}", ""
    # An unexpanded share link: its path is an opaque redirect code that only
    # means anything on the host that issued it. Collapsing the host to
    # `tiktok.com` here used to strand the code on a domain where it matches no
    # route at all, and the classifier rejected every link the TikTok share
    # button produces. Short links are normally expanded upstream
    # (`short_url_resolver`); this branch is what keeps one that could not be
    # expanded ingestible.
    if host in _TIKTOK_SHORT_HOSTS:
        return host, path, ""
    return "tiktok.com", path, ""


def _canon_spotify(path: str) -> Tuple[str, str, str]:
    host = "open.spotify.com"
    path = _normalize_path(path)
    parts = [p for p in path.split("/") if p]
    if len(parts) >= 2:
        path = f"/{parts[0]}/{parts[1]}"
    return host, path, ""


def _extract_x_status_id(path: str) -> str | None:
    parts = [p for p in _normalize_path(path).split("/") if p]
    if len(parts) >= 3 and parts[0] == "i" and parts[1] == "status" and parts[2].isdigit():
        return parts[2]
    if (
        len(parts) >= 4
        and parts[0] == "i"
        and parts[1] == "web"
        and parts[2] == "status"
        and parts[3].isdigit()
    ):
        return parts[3]
    if len(parts) >= 3 and parts[1] == "status" and parts[2].isdigit():
        return parts[2]
    return None


def _canon_x(path: str) -> Tuple[str, str, str]:
    status_id = _extract_x_status_id(path)
    canonical_path = f"/i/status/{status_id}" if status_id else _normalize_path(path)
    return "x.com", canonical_path, ""


def canonicalize_media_url(url: str) -> str:
    """
    Canonicalize a media URL using deterministic rules.

    Rules (v1):
    - normalize scheme/host case, remove fragments and default ports
    - normalize path separators and trailing slashes
    - remove known tracking query params and sort remaining query params
    - apply platform-specific canonicalization for YouTube/Instagram/TikTok/Spotify

    The dispatch reads `classify_source_type` rather than testing hosts again: the
    types that need no rewriting are named (`_URL_PRESERVING_SOURCE_TYPES`), so a
    web article goes through this function as a recognised type instead of as the
    tail of a domain chain (task-392).
    """
    if not isinstance(url, str) or not url.strip():
        raise ValueError("media URL must be a non-empty string")

    split = urlsplit(url.strip())
    scheme = (split.scheme or "https").lower()
    host = _normalize_host(split.hostname or "")
    if not host:
        raise ValueError("media URL must include a host")

    # Remove default ports; preserve non-defaults.
    netloc = host
    if split.port and not (
        (scheme == "http" and split.port == 80)
        or (scheme == "https" and split.port == 443)
    ):
        netloc = f"{host}:{split.port}"

    path = _normalize_path(split.path)
    query_items = _strip_tracking_query(split.query)

    source_type = classify_source_type(host=host, path=path)

    if source_type is MediaSourceType.YOUTUBE:
        netloc, path, query = _canon_youtube(host, path, query_items)
    elif source_type is MediaSourceType.INSTAGRAM:
        netloc, path, query = _canon_instagram(path)
    elif source_type is MediaSourceType.TIKTOK:
        netloc, path, query = _canon_tiktok(host, path)
    elif source_type is MediaSourceType.X:
        netloc, path, query = _canon_x(path)
    elif source_type is MediaSourceType.SPOTIFY:
        netloc, path, query = _canon_spotify(path)
    elif source_type in _URL_PRESERVING_SOURCE_TYPES:
        query = urlencode(query_items, doseq=True)
    else:  # pragma: no cover - every member is handled above
        raise ValueError(f"unhandled media source type '{source_type.value}'")

    return urlunsplit((scheme, netloc, path, query, ""))


def generate_media_key(canonical_url: str) -> str:
    """Generate a deterministic media key from a canonical URL."""
    if not isinstance(canonical_url, str) or not canonical_url.strip():
        raise ValueError("canonical URL must be a non-empty string")
    digest = hashlib.sha256(canonical_url.encode("utf-8")).hexdigest()
    return f"mkey_v1_{digest}"


def derive_media_identity(media_url: str) -> Tuple[str, str]:
    """Return (canonical_url, media_key) from a raw URL."""
    canonical_url = canonicalize_media_url(media_url)
    return canonical_url, generate_media_key(canonical_url)


#: Version of the article content-identity recipe. Bumping it re-keys every
#: article, which is a decision and not a refactor -- hence a named constant.
ARTICLE_CONTENT_IDENTITY_VERSION = "v1"


def article_content_fingerprint(article_text: str) -> str:
    """The fingerprint of an article's body, exactly as it will be stored.

    Taken on the *extracted* text and not on the HTML: the markup around an
    article changes on every request (ad slots, CSRF tokens, a "3 comments"
    counter), so hashing the page would make each save a new media and would
    break the half of task-392 that matters most -- an unchanged article stays
    mutualised, within an account and across accounts.

    Strict by design: any change to the body is a different article. A publisher
    that appends a live counter *to the body* will therefore re-key on each save,
    which is the direction the owner chose (a stale text is the failure to avoid,
    a duplicate save is not).
    """
    if not isinstance(article_text, str) or not article_text.strip():
        raise ValueError("article text must be a non-empty string")
    return hashlib.sha256(article_text.encode("utf-8")).hexdigest()


def generate_article_media_key(
    *,
    canonical_url: str,
    content_fingerprint: str,
) -> str:
    """The content identity of a web article: its URL *and* the text it served.

    Two saves of the same unchanged page produce the same key and stay
    deduplicated; a rewritten page produces a different one, so it becomes a
    different media -- with its own transcript and, because `build_artifact_id`
    hashes content ids, its own artifacts. Serving the previous text's summary
    for the new text is what this makes impossible (task-392).

    The URL stays in the material: two unrelated pages that happen to carry the
    same text (a syndicated article, an empty placeholder) remain two medias,
    each opening its own source link.
    """
    if not isinstance(canonical_url, str) or not canonical_url.strip():
        raise ValueError("canonical URL must be a non-empty string")
    if not isinstance(content_fingerprint, str) or not content_fingerprint.strip():
        raise ValueError("content fingerprint must be a non-empty string")
    locator = (
        f"article:{ARTICLE_CONTENT_IDENTITY_VERSION}:"
        f"{canonical_url.strip()}#text-sha256={content_fingerprint.strip()}"
    )
    return generate_media_key(locator)
