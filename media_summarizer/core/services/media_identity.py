"""
Media identity helpers.

This module defines the canonical URL normalization policy and the deterministic
media key generation used for cross-media idempotence.
"""

from __future__ import annotations

import hashlib
import re
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
_TIKTOK_HOSTS = {
    "tiktok.com",
    "www.tiktok.com",
    "m.tiktok.com",
    "vm.tiktok.com",
}
_SPOTIFY_HOSTS = {"open.spotify.com", "www.open.spotify.com"}

_MULTI_SLASH_RE = re.compile(r"/+")


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


def _canon_tiktok(path: str) -> Tuple[str, str, str]:
    host = "tiktok.com"
    path = _normalize_path(path)
    parts = [p for p in path.split("/") if p]
    # Keep canonical user/video route and t-short routes.
    if len(parts) >= 3 and parts[0].startswith("@") and parts[1] == "video":
        path = f"/{parts[0]}/video/{parts[2]}"
    elif len(parts) >= 2 and parts[0] == "t":
        path = f"/t/{parts[1]}"
    return host, path, ""


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

    if host in _YOUTUBE_HOSTS:
        netloc, path, query = _canon_youtube(host, path, query_items)
    elif host in _INSTAGRAM_HOSTS:
        netloc, path, query = _canon_instagram(path)
    elif host in _TIKTOK_HOSTS:
        netloc, path, query = _canon_tiktok(path)
    elif host in _X_HOSTS:
        netloc, path, query = _canon_x(path)
    elif host in _SPOTIFY_HOSTS:
        netloc, path, query = _canon_spotify(path)
    else:
        query = urlencode(query_items, doseq=True)

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
