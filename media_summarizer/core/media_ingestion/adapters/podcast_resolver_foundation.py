"""Shared foundation for podcast platform resolvers."""

from __future__ import annotations

import re
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, Iterable
from urllib.parse import parse_qs, urlencode, urlsplit, urlunsplit

from media_summarizer.core.media_ingestion.domain import SourcePlatform

DEFAULT_PODCAST_RESOLUTION_PENDING_MESSAGE = (
    "Podcast URL accepted. Resolution is pending."
)
DEFAULT_PODCAST_RESOLUTION_FAILED_MESSAGE = "Podcast URL could not be resolved."

_DEFAULT_PORT_BY_SCHEME = {
    "http": 80,
    "https": 443,
}
_APPLE_SHOW_ID_PATTERN = re.compile(r"^id(\d+)$", re.IGNORECASE)
_SUPPORTED_PODCAST_PLATFORMS = {
    SourcePlatform.SPOTIFY,
    SourcePlatform.APPLE_PODCASTS,
    SourcePlatform.DEEZER,
    SourcePlatform.RSS,
}


class PodcastResolutionStatus(str, Enum):
    RESOLVED = "resolved"
    PENDING = "pending"
    FAILED = "failed"


class PodcastResolverErrorCode(str, Enum):
    RESOLUTION_PENDING = "resolution_pending"
    UNSUPPORTED_PLATFORM = "unsupported_platform"
    INVALID_PLATFORM_URL = "invalid_platform_url"
    PLATFORM_NOT_IMPLEMENTED = "platform_not_implemented"
    UPSTREAM_LOOKUP_FAILED = "upstream_lookup_failed"
    EPISODE_NOT_FOUND = "episode_not_found"
    AUDIO_URL_NOT_FOUND = "audio_url_not_found"


@dataclass(frozen=True)
class PodcastUrlDescriptor:
    source_platform: SourcePlatform
    input_url: str
    canonical_url: str
    host: str
    path: str
    query: str
    identifiers: Dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class PodcastResolutionOutcome:
    status: PodcastResolutionStatus
    audio_url: str | None = None
    title: str | None = None
    error_code: PodcastResolverErrorCode | None = None
    client_message: str | None = None
    retryable: bool = False
    metadata: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def resolved(
        cls,
        *,
        audio_url: str,
        title: str | None = None,
        metadata: Dict[str, Any] | None = None,
    ) -> "PodcastResolutionOutcome":
        return cls(
            status=PodcastResolutionStatus.RESOLVED,
            audio_url=audio_url,
            title=title,
            metadata=dict(metadata or {}),
        )

    @classmethod
    def pending(
        cls,
        *,
        error_code: PodcastResolverErrorCode = PodcastResolverErrorCode.RESOLUTION_PENDING,
        client_message: str = DEFAULT_PODCAST_RESOLUTION_PENDING_MESSAGE,
        retryable: bool = True,
        metadata: Dict[str, Any] | None = None,
    ) -> "PodcastResolutionOutcome":
        return cls(
            status=PodcastResolutionStatus.PENDING,
            error_code=error_code,
            client_message=client_message,
            retryable=retryable,
            metadata=dict(metadata or {}),
        )

    @classmethod
    def failed(
        cls,
        *,
        error_code: PodcastResolverErrorCode,
        client_message: str = DEFAULT_PODCAST_RESOLUTION_FAILED_MESSAGE,
        retryable: bool = False,
        metadata: Dict[str, Any] | None = None,
    ) -> "PodcastResolutionOutcome":
        return cls(
            status=PodcastResolutionStatus.FAILED,
            error_code=error_code,
            client_message=client_message,
            retryable=retryable,
            metadata=dict(metadata or {}),
        )


class PodcastPlatformResolver(ABC):
    """Single shared resolver interface for all podcast source platforms."""

    @property
    @abstractmethod
    def source_platform(self) -> SourcePlatform:
        raise NotImplementedError

    @abstractmethod
    async def resolve(
        self,
        *,
        descriptor: PodcastUrlDescriptor,
    ) -> PodcastResolutionOutcome:
        raise NotImplementedError


class PodcastPlatformResolverRegistry:
    """Registry of podcast platform resolvers keyed by `SourcePlatform`."""

    def __init__(self) -> None:
        self._resolvers: Dict[SourcePlatform, PodcastPlatformResolver] = {}

    def register(self, resolver: PodcastPlatformResolver) -> None:
        platform = resolver.source_platform
        if platform in self._resolvers:
            raise ValueError(
                f"Podcast resolver already registered for '{platform.value}'."
            )
        self._resolvers[platform] = resolver

    def register_many(self, resolvers: Iterable[PodcastPlatformResolver]) -> None:
        for resolver in resolvers:
            self.register(resolver)

    def get(self, source_platform: SourcePlatform) -> PodcastPlatformResolver:
        resolver = self._resolvers.get(source_platform)
        if resolver is None:
            raise ValueError(
                f"No podcast resolver registered for '{source_platform.value}'."
            )
        return resolver


class DeferredPodcastPlatformResolver(PodcastPlatformResolver):
    """Default placeholder resolver used before platform-specific implementation."""

    def __init__(self, source_platform: SourcePlatform) -> None:
        self._source_platform = source_platform

    @property
    def source_platform(self) -> SourcePlatform:
        return self._source_platform

    async def resolve(
        self,
        *,
        descriptor: PodcastUrlDescriptor,
    ) -> PodcastResolutionOutcome:
        return PodcastResolutionOutcome.pending(
            error_code=PodcastResolverErrorCode.RESOLUTION_PENDING,
            metadata={
                "reason": "platform_resolution_deferred",
                "source_platform": descriptor.source_platform.value,
            },
        )


def build_deferred_podcast_platform_resolver_registry() -> PodcastPlatformResolverRegistry:
    """Build default podcast registry where all platforms are deferred."""
    registry = PodcastPlatformResolverRegistry()
    registry.register_many(
        [
            DeferredPodcastPlatformResolver(SourcePlatform.SPOTIFY),
            DeferredPodcastPlatformResolver(SourcePlatform.APPLE_PODCASTS),
            DeferredPodcastPlatformResolver(SourcePlatform.DEEZER),
            DeferredPodcastPlatformResolver(SourcePlatform.RSS),
        ]
    )
    return registry


def normalize_podcast_source_url(
    *,
    normalized_url: str,
    source_platform: SourcePlatform,
) -> PodcastUrlDescriptor:
    """
    Apply centralized podcast URL normalization per platform.

    This function is shared by podcast resolvers to guarantee deterministic,
    reusable URL parsing and identifier extraction.
    """
    raw_url = (normalized_url or "").strip()
    if not raw_url:
        raise ValueError("Podcast URL is empty.")

    if source_platform not in _SUPPORTED_PODCAST_PLATFORMS:
        raise ValueError(f"Unsupported podcast source platform: {source_platform.value}")

    split = urlsplit(raw_url)
    scheme, netloc, host = _normalize_scheme_and_netloc(split)
    path = _normalize_path(split.path)
    query = split.query or ""

    if source_platform == SourcePlatform.SPOTIFY:
        canonical_url, path, query, identifiers = _normalize_spotify(
            scheme=scheme,
            path=path,
        )
        host = "open.spotify.com"
    elif source_platform == SourcePlatform.APPLE_PODCASTS:
        canonical_url, path, query, identifiers = _normalize_apple(
            scheme=scheme,
            path=path,
            query=query,
        )
        host = "podcasts.apple.com"
    elif source_platform == SourcePlatform.DEEZER:
        canonical_url, path, query, identifiers = _normalize_deezer(
            scheme=scheme,
            path=path,
        )
        host = "deezer.com"
    else:
        canonical_url = urlunsplit((scheme, netloc, path, query, ""))
        identifiers = {}

    return PodcastUrlDescriptor(
        source_platform=source_platform,
        input_url=raw_url,
        canonical_url=canonical_url,
        host=host,
        path=path,
        query=query,
        identifiers=identifiers,
    )


def build_raw_podcast_url_descriptor(
    *,
    normalized_url: str,
    source_platform: SourcePlatform,
) -> PodcastUrlDescriptor:
    """Fallback descriptor used when normalization fails."""
    raw_url = (normalized_url or "").strip()
    return PodcastUrlDescriptor(
        source_platform=source_platform,
        input_url=raw_url,
        canonical_url=raw_url,
        host="",
        path="",
        query="",
        identifiers={},
    )


def build_podcast_resolution_metadata(
    *,
    descriptor: PodcastUrlDescriptor,
    outcome: PodcastResolutionOutcome,
) -> Dict[str, Any]:
    """Build stable metadata envelope for podcast resolver outcomes."""
    metadata: Dict[str, Any] = {
        "podcast_resolution_status": outcome.status.value,
        "podcast_resolution_error_code": (
            outcome.error_code.value if outcome.error_code else None
        ),
        "podcast_resolution_client_message": outcome.client_message,
        "podcast_resolution_retryable": outcome.retryable,
        "podcast_source_platform": descriptor.source_platform.value,
        "podcast_source_url": descriptor.canonical_url,
        "podcast_url_identifiers": descriptor.identifiers,
    }
    if outcome.metadata:
        metadata["podcast_resolution_details"] = dict(outcome.metadata)
    return metadata


def _normalize_scheme_and_netloc(split) -> tuple[str, str, str]:
    scheme = (split.scheme or "https").lower()
    host = (split.hostname or "").strip().lower()
    if not host:
        raise ValueError("Podcast URL host is missing.")

    netloc = host
    if split.port and _DEFAULT_PORT_BY_SCHEME.get(scheme) != split.port:
        netloc = f"{host}:{split.port}"

    return scheme, netloc, host


def _normalize_path(path: str) -> str:
    raw = (path or "").strip()
    if not raw:
        return "/"
    segments = [segment for segment in raw.split("/") if segment]
    if not segments:
        return "/"
    return "/" + "/".join(segments)


def _normalize_spotify(
    *,
    scheme: str,
    path: str,
) -> tuple[str, str, str, Dict[str, str]]:
    segments = [segment for segment in path.split("/") if segment]
    if len(segments) < 2 or segments[0] not in {"episode", "show"}:
        raise ValueError("Unsupported Spotify podcast URL format.")

    entity_type = segments[0]
    entity_id = segments[1]
    canonical_path = f"/{entity_type}/{entity_id}"
    identifiers = {f"{entity_type}_id": entity_id}
    canonical_url = urlunsplit((scheme, "open.spotify.com", canonical_path, "", ""))
    return canonical_url, canonical_path, "", identifiers


def _normalize_apple(
    *,
    scheme: str,
    path: str,
    query: str,
) -> tuple[str, str, str, Dict[str, str]]:
    segments = [segment for segment in path.split("/") if segment]

    show_id = ""
    for segment in reversed(segments):
        matched = _APPLE_SHOW_ID_PATTERN.match(segment)
        if matched:
            show_id = matched.group(1)
            break

    query_params = parse_qs(query, keep_blank_values=True)
    episode_id = (query_params.get("i") or [""])[0].strip()

    canonical_path = path
    if show_id:
        canonical_path = f"/podcast/id{show_id}"

    canonical_query = ""
    if episode_id:
        canonical_query = urlencode([("i", episode_id)])

    identifiers: Dict[str, str] = {}
    if show_id:
        identifiers["show_id"] = show_id
    if episode_id:
        identifiers["episode_id"] = episode_id

    canonical_url = urlunsplit(
        (scheme, "podcasts.apple.com", canonical_path, canonical_query, "")
    )
    return canonical_url, canonical_path, canonical_query, identifiers


def _normalize_deezer(
    *,
    scheme: str,
    path: str,
) -> tuple[str, str, str, Dict[str, str]]:
    segments = [segment for segment in path.split("/") if segment]
    entity_index = -1
    for idx, segment in enumerate(segments):
        if segment in {"show", "episode"}:
            entity_index = idx
            break

    if entity_index < 0 or entity_index + 1 >= len(segments):
        raise ValueError("Unsupported Deezer podcast URL format.")

    entity_type = segments[entity_index]
    entity_id = segments[entity_index + 1]
    canonical_path = f"/{entity_type}/{entity_id}"

    identifier_key = "episode_id" if entity_type == "episode" else "show_id"
    identifiers = {identifier_key: entity_id}

    canonical_url = urlunsplit((scheme, "deezer.com", canonical_path, "", ""))
    return canonical_url, canonical_path, "", identifiers


__all__ = [
    "DEFAULT_PODCAST_RESOLUTION_FAILED_MESSAGE",
    "DEFAULT_PODCAST_RESOLUTION_PENDING_MESSAGE",
    "DeferredPodcastPlatformResolver",
    "PodcastPlatformResolver",
    "PodcastPlatformResolverRegistry",
    "PodcastResolutionOutcome",
    "PodcastResolutionStatus",
    "PodcastResolverErrorCode",
    "PodcastUrlDescriptor",
    "build_deferred_podcast_platform_resolver_registry",
    "build_podcast_resolution_metadata",
    "build_raw_podcast_url_descriptor",
    "normalize_podcast_source_url",
]
