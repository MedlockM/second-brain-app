"""Default URL classifier adapter for media ingestion."""

from __future__ import annotations

import ipaddress
import logging
import os
import re
from urllib.parse import parse_qs, urlsplit

from media_summarizer.core.media_ingestion.domain import (
    ClassifiedUrl,
    MediaFamily,
    SourcePlatform,
)
from media_summarizer.core.media_ingestion.errors import (
    DEFAULT_INVALID_URL_MESSAGE,
    InvalidUrlError,
    UnsupportedUrlError,
)
from media_summarizer.core.media_ingestion.ports import UrlClassifierPort

logger = logging.getLogger(__name__)

_SPOTIFY_HOSTS = {"open.spotify.com", "www.open.spotify.com"}
_APPLE_HOSTS = {"podcasts.apple.com", "www.podcasts.apple.com"}
_DEEZER_HOSTS = {"www.deezer.com", "deezer.com"}
_YOUTUBE_HOSTS = {
    "youtube.com",
    "www.youtube.com",
    "m.youtube.com",
    "music.youtube.com",
    "youtu.be",
    "www.youtu.be",
}
_YOUTUBE_SHORT_HOSTS = {"youtu.be", "www.youtu.be"}
_INSTAGRAM_HOSTS = {"instagram.com", "www.instagram.com"}
_X_HOSTS = {"x.com", "www.x.com", "twitter.com", "www.twitter.com"}
_TIKTOK_SHORT_HOSTS = {"vm.tiktok.com", "vt.tiktok.com"}
_TIKTOK_HOSTS = {
    "tiktok.com",
    "www.tiktok.com",
    "m.tiktok.com",
    *_TIKTOK_SHORT_HOSTS,
}
_SUPPORTED_SCHEMES = {"http", "https"}
_FORBIDDEN_HOSTS = {"localhost"}
_DEFAULT_BLOCKED_DOMAINS = {
    "malware.test",
    "phishing.test",
    "localhost.localdomain",
}
_AUDIO_EXTENSIONS = (
    ".mp3",
    ".m4a",
    ".aac",
    ".ogg",
    ".wav",
    ".flac",
    ".opus",
)
_UNSUPPORTED_SCHEME_MESSAGE = (
    "Unsupported URL scheme. Only http:// and https:// are allowed."
)
_UNSUPPORTED_HOST_MESSAGE = "Unsupported URL host."
_UNSUPPORTED_SPOTIFY_FORMAT_MESSAGE = "Unsupported Spotify URL format."
_UNSUPPORTED_APPLE_FORMAT_MESSAGE = "Unsupported Apple Podcasts URL format."
_UNSUPPORTED_DEEZER_FORMAT_MESSAGE = "Unsupported Deezer URL format."
_UNSUPPORTED_YOUTUBE_FORMAT_MESSAGE = "Unsupported YouTube URL format."
_UNSUPPORTED_INSTAGRAM_FORMAT_MESSAGE = "Unsupported Instagram URL format."
_UNSUPPORTED_X_FORMAT_MESSAGE = "Unsupported X/Twitter URL format."
_UNSUPPORTED_TIKTOK_FORMAT_MESSAGE = "Unsupported TikTok URL format."
_UNSUPPORTED_TIKTOK_PHOTO_MESSAGE = "TikTok photo posts are not supported yet."
_UNSAFE_URL_FORMAT_MESSAGE = "Unsupported unsafe URL format."
_BLOCKED_DOMAIN_MESSAGE = "Blocked URL host by safety policy."
_MAX_URL_LENGTH = 2048
_RSS_HOST_HINT_PREFIXES = ("feeds.", "rss.")
_HOST_LABEL_RE = re.compile(r"^[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?$")


def _parse_domain_set(raw_value: str) -> frozenset[str]:
    domains: set[str] = set()
    for entry in (raw_value or "").split(","):
        candidate = entry.strip().lower().strip(".")
        if candidate:
            domains.add(candidate)
    return frozenset(domains)


_BLOCKED_DOMAIN_SUFFIXES = frozenset(_DEFAULT_BLOCKED_DOMAINS).union(
    _parse_domain_set(os.environ.get("INGEST_URL_BLOCKED_DOMAINS", ""))
)
_ALLOWED_DOMAIN_SUFFIXES = _parse_domain_set(
    os.environ.get("INGEST_URL_ALLOWED_DOMAINS", "")
)


def _path_segments(path: str) -> tuple[str, ...]:
    return tuple(segment for segment in path.split("/") if segment)


def _path_has_feed_segment(path: str) -> bool:
    return "feed" in _path_segments(path)


def _path_looks_like_rss(path: str) -> bool:
    return (
        path.endswith(".rss")
        or path.endswith(".xml")
        or _path_has_feed_segment(path)
    )


def _host_looks_like_rss(host: str) -> bool:
    return host.startswith(_RSS_HOST_HINT_PREFIXES)


def _path_looks_like_audio(path: str) -> bool:
    return path.endswith(_AUDIO_EXTENSIONS)


def _host_has_invalid_pattern(host: str) -> bool:
    if not host or host.startswith(".") or host.endswith(".") or ".." in host:
        return True
    if len(host) > 253:
        return True
    labels = host.split(".")
    return any(not _HOST_LABEL_RE.match(label) for label in labels)


def _host_matches_domain_suffix(host: str, domain: str) -> bool:
    return host == domain or host.endswith(f".{domain}")


def _host_is_blocked_by_policy(host: str) -> bool:
    if any(
        _host_matches_domain_suffix(host, allowed_domain)
        for allowed_domain in _ALLOWED_DOMAIN_SUFFIXES
    ):
        return False
    return any(
        _host_matches_domain_suffix(host, blocked_domain)
        for blocked_domain in _BLOCKED_DOMAIN_SUFFIXES
    )


def _host_is_forbidden(host: str) -> bool:
    if host in _FORBIDDEN_HOSTS:
        return True
    try:
        parsed_host = ipaddress.ip_address(host)
    except ValueError:
        return False
    return (
        parsed_host.is_private
        or parsed_host.is_loopback
        or parsed_host.is_link_local
        or parsed_host.is_reserved
        or parsed_host.is_multicast
        or parsed_host.is_unspecified
    )


def _is_spotify_podcast_path(path: str) -> bool:
    segments = _path_segments(path)
    return len(segments) >= 2 and segments[0] in {"episode", "show"}


def _is_apple_podcast_path(path: str) -> bool:
    return "podcast" in _path_segments(path)


def _is_deezer_podcast_path(path: str) -> bool:
    segments = set(_path_segments(path))
    return "show" in segments or "episode" in segments


def _is_youtube_video_path(
    *,
    host: str,
    path: str,
    query_params: dict[str, list[str]],
) -> bool:
    if host in _YOUTUBE_SHORT_HOSTS:
        return bool(_path_segments(path))
    if path == "/watch":
        return bool((query_params.get("v") or [""])[0].strip())
    return (
        path.startswith("/shorts/")
        or path.startswith("/live/")
        or path.startswith("/embed/")
    )


def _is_instagram_video_path(path: str) -> bool:
    return (
        path.startswith("/reel/")
        or path.startswith("/p/")
        or path.startswith("/tv/")
    )


def _is_tiktok_photo_path(path: str) -> bool:
    """True for a photo/carousel post, which has no transcribable audio track.

    Worth telling apart from an unsupported URL *format*: the link is perfectly
    valid and the user has no way to turn it into a video, so the answer has to
    name the real reason (the same treatment Instagram image posts get).
    """
    parts = _path_segments(path)
    return len(parts) >= 3 and parts[0].startswith("@") and parts[1] == "photo"


def _is_tiktok_video_path(*, host: str, path: str) -> bool:
    # An unexpanded share link: the path is an opaque redirect code, so nothing
    # here can tell what it points at. Accept it and let the worker, which
    # follows the redirect through yt-dlp, find out.
    if host in _TIKTOK_SHORT_HOSTS:
        return bool(_path_segments(path))
    return (path.startswith("/@") and "/video/" in path) or path.startswith("/t/")


def _is_x_post_path(path: str) -> bool:
    parts = _path_segments(path)
    if len(parts) >= 3 and parts[0] == "i" and parts[1] == "status":
        return parts[2].isdigit()
    if len(parts) >= 4 and parts[0] == "i" and parts[1] == "web" and parts[2] == "status":
        return parts[3].isdigit()
    return len(parts) >= 3 and parts[1] == "status" and parts[2].isdigit()


def _log_safety_decision(
    *,
    decision: str,
    reason: str,
    scheme: str,
    host: str,
) -> None:
    logger.info(
        "ingestion_url_safety_decision",
        extra={
            "decision": decision,
            "reason": reason,
            "scheme": scheme,
            "host": host,
        },
    )


class RuleBasedUrlClassifier(UrlClassifierPort):
    """
    Deterministic URL classifier.

    This adapter is intentionally simple and deterministic. It is a placeholder
    implementation for task-21, while still enforcing strict routing behavior.
    """

    def classify(self, normalized_url: str) -> ClassifiedUrl:
        url = (normalized_url or "").strip()
        if not url:
            raise InvalidUrlError(DEFAULT_INVALID_URL_MESSAGE)
        if len(url) > _MAX_URL_LENGTH:
            raise InvalidUrlError(DEFAULT_INVALID_URL_MESSAGE)

        try:
            split = urlsplit(url)
        except ValueError as exc:
            raise InvalidUrlError(DEFAULT_INVALID_URL_MESSAGE) from exc

        scheme = (split.scheme or "").lower()
        host = (split.hostname or "").lower()
        path = (split.path or "/").lower()
        query_params = parse_qs(split.query, keep_blank_values=True)
        try:
            _ = split.port
        except ValueError as exc:
            raise InvalidUrlError(DEFAULT_INVALID_URL_MESSAGE) from exc

        if scheme not in _SUPPORTED_SCHEMES:
            _log_safety_decision(
                decision="deny",
                reason="unsupported_scheme",
                scheme=scheme,
                host=host,
            )
            raise UnsupportedUrlError(_UNSUPPORTED_SCHEME_MESSAGE)
        if not host:
            _log_safety_decision(
                decision="deny",
                reason="missing_host",
                scheme=scheme,
                host=host,
            )
            raise InvalidUrlError(DEFAULT_INVALID_URL_MESSAGE)
        if split.username or split.password:
            _log_safety_decision(
                decision="deny",
                reason="user_info_not_allowed",
                scheme=scheme,
                host=host,
            )
            raise UnsupportedUrlError(_UNSAFE_URL_FORMAT_MESSAGE)
        if _host_has_invalid_pattern(host):
            _log_safety_decision(
                decision="deny",
                reason="invalid_host_pattern",
                scheme=scheme,
                host=host,
            )
            raise InvalidUrlError(DEFAULT_INVALID_URL_MESSAGE)
        if _host_is_forbidden(host):
            _log_safety_decision(
                decision="deny",
                reason="forbidden_host_or_ip",
                scheme=scheme,
                host=host,
            )
            raise UnsupportedUrlError(_UNSUPPORTED_HOST_MESSAGE)
        if _host_is_blocked_by_policy(host):
            _log_safety_decision(
                decision="deny",
                reason="blocked_domain_policy",
                scheme=scheme,
                host=host,
            )
            raise UnsupportedUrlError(_BLOCKED_DOMAIN_MESSAGE)

        _log_safety_decision(
            decision="allow",
            reason="passed_safety_checks",
            scheme=scheme,
            host=host,
        )

        if host in _SPOTIFY_HOSTS:
            if not _is_spotify_podcast_path(path):
                raise UnsupportedUrlError(_UNSUPPORTED_SPOTIFY_FORMAT_MESSAGE)
            return ClassifiedUrl(
                media_family=MediaFamily.PODCAST,
                source_platform=SourcePlatform.SPOTIFY,
                resolver_key="podcast.default",
            )

        if host in _APPLE_HOSTS:
            if not _is_apple_podcast_path(path):
                raise UnsupportedUrlError(_UNSUPPORTED_APPLE_FORMAT_MESSAGE)
            return ClassifiedUrl(
                media_family=MediaFamily.PODCAST,
                source_platform=SourcePlatform.APPLE_PODCASTS,
                resolver_key="podcast.default",
            )

        if host in _DEEZER_HOSTS:
            if not _is_deezer_podcast_path(path):
                raise UnsupportedUrlError(_UNSUPPORTED_DEEZER_FORMAT_MESSAGE)
            return ClassifiedUrl(
                media_family=MediaFamily.PODCAST,
                source_platform=SourcePlatform.DEEZER,
                resolver_key="podcast.default",
            )

        if _path_looks_like_rss(path) or _host_looks_like_rss(host):
            return ClassifiedUrl(
                media_family=MediaFamily.PODCAST,
                source_platform=SourcePlatform.RSS,
                resolver_key="podcast.default",
            )

        if host in _YOUTUBE_HOSTS:
            if not _is_youtube_video_path(
                host=host,
                path=path,
                query_params=query_params,
            ):
                raise UnsupportedUrlError(_UNSUPPORTED_YOUTUBE_FORMAT_MESSAGE)
            return ClassifiedUrl(
                media_family=MediaFamily.YOUTUBE,
                source_platform=SourcePlatform.YOUTUBE,
                resolver_key="youtube.default",
            )

        if host in _INSTAGRAM_HOSTS:
            if not _is_instagram_video_path(path):
                raise UnsupportedUrlError(_UNSUPPORTED_INSTAGRAM_FORMAT_MESSAGE)
            return ClassifiedUrl(
                media_family=MediaFamily.SOCIAL_VIDEO,
                source_platform=SourcePlatform.INSTAGRAM,
                resolver_key="instagram.default",
            )

        if host in _X_HOSTS:
            if not _is_x_post_path(path):
                raise UnsupportedUrlError(_UNSUPPORTED_X_FORMAT_MESSAGE)
            return ClassifiedUrl(
                media_family=MediaFamily.ARTICLE,
                source_platform=SourcePlatform.X,
                resolver_key="x.default",
            )

        if host in _TIKTOK_HOSTS:
            if _is_tiktok_photo_path(path):
                raise UnsupportedUrlError(_UNSUPPORTED_TIKTOK_PHOTO_MESSAGE)
            if not _is_tiktok_video_path(host=host, path=path):
                raise UnsupportedUrlError(_UNSUPPORTED_TIKTOK_FORMAT_MESSAGE)
            return ClassifiedUrl(
                media_family=MediaFamily.SOCIAL_VIDEO,
                source_platform=SourcePlatform.TIKTOK,
                resolver_key="tiktok.default",
            )

        if _path_looks_like_audio(path):
            return ClassifiedUrl(
                media_family=MediaFamily.AUDIO,
                source_platform=SourcePlatform.DIRECT_URL,
                resolver_key="audio.default",
            )

        return ClassifiedUrl(
            media_family=MediaFamily.ARTICLE,
            source_platform=SourcePlatform.WEB,
            resolver_key="article.default",
        )
