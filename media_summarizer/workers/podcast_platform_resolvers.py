"""
Platform resolvers for PodcastIndex worker using shared podcast resolver foundation.
"""

from __future__ import annotations

import asyncio
import json
import logging
import random
import re
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from html import unescape
from typing import Any
from urllib.parse import urljoin, urlsplit

import httpx

from media_summarizer.core.media_ingestion.adapters.podcast_resolver_foundation import (
    DEFAULT_PODCAST_RESOLUTION_FAILED_MESSAGE,
    PodcastPlatformResolver,
    PodcastPlatformResolverRegistry,
    PodcastResolutionOutcome,
    PodcastResolverErrorCode,
    PodcastUrlDescriptor,
)
from media_summarizer.core.media_ingestion.domain import SourcePlatform
from media_summarizer.core.services.podcast_matching import best_match_episode
from media_summarizer.utils import podcast_index

logger = logging.getLogger(__name__)

_RSS_HINT_SUFFIXES = (".rss", ".xml")
_SPOTIFY_OEMBED_ENDPOINT = "https://open.spotify.com/oembed"
_SPOTIFY_SHOW_SUFFIX_TOKEN = "·"
_SPOTIFY_SHOW_ID_PATTERN = re.compile(r"/show/([A-Za-z0-9]{22})")
_APPLE_PODCASTS_OEMBED_ENDPOINT = "https://podcasts.apple.com/api/oembed"
_APPLE_OG_DESCRIPTION_SEPARATOR = "·"
_DEEZER_API_BASE_URL = "https://api.deezer.com"
_RSS_HTTP_ACCEPT_HEADER = (
    "application/rss+xml, application/atom+xml, "
    "application/xml;q=0.9, text/xml;q=0.8, */*;q=0.5"
)
_RSS_HOST_HINT_PREFIXES = ("feeds.", "rss.")
_HTML_META_TAG_PATTERN = re.compile(r"<meta[^>]*>", re.IGNORECASE)
_HTML_META_ATTR_PATTERN = re.compile(
    r"(?P<name>[A-Za-z_:]+)\s*=\s*(?P<quote>['\"])(?P<value>.*?)(?P=quote)"
)
_APPLE_SCHEMA_EPISODE_PATTERN = re.compile(
    r"<script[^>]*id=schema:episode[^>]*>(?P<payload>.*?)</script>",
    re.IGNORECASE | re.DOTALL,
)


def _looks_like_feed_url(url: str) -> bool:
    try:
        split = urlsplit(url)
    except ValueError:
        return False
    host = (split.hostname or "").lower()
    path = (split.path or "").lower()
    if path.endswith(_RSS_HINT_SUFFIXES):
        return True
    if "/feed" in path or "/rss" in path:
        return True
    return host.startswith(_RSS_HOST_HINT_PREFIXES)


def _is_transient_error(exc: Exception) -> bool:
    msg = str(exc).lower()
    transient_tokens = (
        "429",
        "500",
        "502",
        "503",
        "504",
        "timeout",
        "temporar",
        "connection",
    )
    return any(token in msg for token in transient_tokens)


def _extract_meta_content(document: str, *, key: str, attribute: str) -> str:
    for tag in _HTML_META_TAG_PATTERN.findall(document or ""):
        attrs: dict[str, str] = {}
        for match in _HTML_META_ATTR_PATTERN.finditer(tag):
            attrs[match.group("name").lower()] = unescape(match.group("value")).strip()
        if attrs.get(attribute.lower()) == key.lower():
            return attrs.get("content", "").strip()
    return ""


def _extract_feed_id(feed_result: dict) -> int | None:
    feed = feed_result.get("feed")
    if isinstance(feed, dict) and feed.get("id") is not None:
        try:
            return int(feed["id"])
        except Exception:
            return None

    feeds = feed_result.get("feeds")
    if isinstance(feeds, list) and feeds:
        first = feeds[0]
        if isinstance(first, dict) and first.get("id") is not None:
            try:
                return int(first["id"])
            except Exception:
                return None
    return None


def _pick_episode_with_audio(items: list[dict]) -> dict | None:
    if not items:
        return None

    sorted_items = sorted(
        items,
        key=lambda item: int(item.get("datePublished") or 0),
        reverse=True,
    )
    for item in sorted_items:
        if item.get("enclosureUrl"):
            return item
    return None


def _xml_local_name(tag: str) -> str:
    return (tag or "").rsplit("}", 1)[-1].lower()


def _first_direct_text(element: ET.Element, names: tuple[str, ...]) -> str:
    name_set = {name.lower() for name in names}
    for child in list(element):
        if _xml_local_name(child.tag) not in name_set:
            continue
        text = (child.text or "").strip()
        if text:
            return text
    return ""


def _first_direct_attr(
    element: ET.Element,
    *,
    names: tuple[str, ...],
    attrs: tuple[str, ...],
) -> str:
    name_set = {name.lower() for name in names}
    for child in list(element):
        if _xml_local_name(child.tag) not in name_set:
            continue
        for attr_name in attrs:
            value = (child.attrib.get(attr_name) or "").strip()
            if value:
                return value
    return ""


def _absolutize_http_url(*, base_url: str, candidate: str) -> str:
    raw = (candidate or "").strip()
    if not raw:
        return ""
    resolved = urljoin(base_url, raw)
    if resolved.lower().startswith(("http://", "https://")):
        return resolved
    return ""


def _parse_timestamp_seconds(value: str) -> int:
    raw = (value or "").strip()
    if not raw:
        return 0
    try:
        dt = parsedate_to_datetime(raw)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return int(dt.timestamp())
    except Exception:
        pass

    iso_candidate = raw.replace("Z", "+00:00")
    try:
        dt = datetime.fromisoformat(iso_candidate)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return int(dt.timestamp())
    except Exception:
        return 0


def _parse_duration_seconds(value: str) -> int:
    raw = (value or "").strip()
    if not raw:
        return 0
    if raw.isdigit():
        return int(raw)

    parts = [part.strip() for part in raw.split(":")]
    if not parts or any(not part.isdigit() for part in parts):
        return 0
    if len(parts) == 3:
        hours, minutes, seconds = (int(part) for part in parts)
        return hours * 3600 + minutes * 60 + seconds
    if len(parts) == 2:
        minutes, seconds = (int(part) for part in parts)
        return minutes * 60 + seconds
    return 0


class _RssFeedInvalidError(Exception):
    def __init__(self, message: str, *, metadata: dict[str, Any] | None = None) -> None:
        super().__init__(message)
        self.metadata = dict(metadata or {})


class _RssFeedNoAudioError(Exception):
    def __init__(self, message: str, *, metadata: dict[str, Any] | None = None) -> None:
        super().__init__(message)
        self.metadata = dict(metadata or {})


class NotImplementedPodcastPlatformResolver(PodcastPlatformResolver):
    """Placeholder resolver keeping a stable failure contract until implementation."""

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
        return PodcastResolutionOutcome.failed(
            error_code=PodcastResolverErrorCode.PLATFORM_NOT_IMPLEMENTED,
            client_message=DEFAULT_PODCAST_RESOLUTION_FAILED_MESSAGE,
            retryable=False,
            metadata={
                "reason": "platform_resolver_not_implemented",
                "source_platform": descriptor.source_platform.value,
            },
        )


class SpotifyPodcastPlatformResolver(PodcastPlatformResolver):
    """Spotify resolver mapping episode URLs to PodcastIndex enclosure URLs."""

    def __init__(
        self,
        *,
        max_retries: int,
        feed_candidates: int,
        episode_candidates: int,
        request_timeout_seconds: float = 20.0,
    ) -> None:
        self._max_retries = max(1, int(max_retries))
        self._feed_candidates = max(1, int(feed_candidates))
        self._episode_candidates = max(1, int(episode_candidates))
        self._request_timeout_seconds = max(1.0, float(request_timeout_seconds))

    @property
    def source_platform(self) -> SourcePlatform:
        return SourcePlatform.SPOTIFY

    async def resolve(
        self,
        *,
        descriptor: PodcastUrlDescriptor,
    ) -> PodcastResolutionOutcome:
        spotify_episode_id = (
            (descriptor.identifiers.get("episode_id") or "").strip()
            if descriptor.identifiers
            else ""
        )
        if not spotify_episode_id:
            return PodcastResolutionOutcome.failed(
                error_code=PodcastResolverErrorCode.INVALID_PLATFORM_URL,
                client_message=DEFAULT_PODCAST_RESOLUTION_FAILED_MESSAGE,
                retryable=False,
                metadata={
                    "reason": "spotify_episode_url_required",
                    "source_platform": descriptor.source_platform.value,
                },
            )

        attempt = 0
        while attempt < self._max_retries:
            attempt += 1
            try:
                spotify_metadata = await self._fetch_spotify_episode_metadata(
                    descriptor=descriptor
                )
                return await self._resolve_from_podcastindex(
                    spotify_metadata=spotify_metadata,
                )
            except ValueError as exc:
                return PodcastResolutionOutcome.failed(
                    error_code=PodcastResolverErrorCode.INVALID_PLATFORM_URL,
                    client_message=DEFAULT_PODCAST_RESOLUTION_FAILED_MESSAGE,
                    retryable=False,
                    metadata={
                        "reason": "spotify_episode_metadata_unavailable",
                        "spotify_episode_id": spotify_episode_id,
                        "attempt": attempt,
                        "error_type": type(exc).__name__,
                    },
                )
            except Exception as exc:
                transient = _is_transient_error(exc)
                if attempt < self._max_retries and transient:
                    backoff = min(2 ** (attempt - 1), 8) + random.uniform(0.0, 0.25)
                    logger.warning(
                        "Transient Spotify resolver error "
                        "(attempt %s/%s), retrying in %.2fs: %s",
                        attempt,
                        self._max_retries,
                        backoff,
                        exc,
                    )
                    await asyncio.sleep(backoff)
                    continue
                return PodcastResolutionOutcome.failed(
                    error_code=PodcastResolverErrorCode.UPSTREAM_LOOKUP_FAILED,
                    client_message=DEFAULT_PODCAST_RESOLUTION_FAILED_MESSAGE,
                    retryable=transient,
                    metadata={
                        "reason": "spotify_resolver_upstream_failed",
                        "spotify_episode_id": spotify_episode_id,
                        "attempt": attempt,
                        "error_type": type(exc).__name__,
                    },
                )

        return PodcastResolutionOutcome.failed(
            error_code=PodcastResolverErrorCode.UPSTREAM_LOOKUP_FAILED,
            client_message=DEFAULT_PODCAST_RESOLUTION_FAILED_MESSAGE,
            retryable=True,
            metadata={
                "reason": "spotify_resolver_retries_exhausted",
                "spotify_episode_id": spotify_episode_id,
                "attempt": attempt,
            },
        )

    async def _fetch_spotify_episode_metadata(
        self,
        *,
        descriptor: PodcastUrlDescriptor,
    ) -> dict[str, Any]:
        timeout = httpx.Timeout(self._request_timeout_seconds)
        async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
            oembed_response = await client.get(
                _SPOTIFY_OEMBED_ENDPOINT,
                params={"url": descriptor.canonical_url},
            )
            if oembed_response.status_code in {400, 404}:
                raise ValueError(
                    "Spotify episode oEmbed endpoint returned invalid URL."
                )
            oembed_response.raise_for_status()
            oembed_payload = oembed_response.json()

            page_response = await client.get(descriptor.canonical_url)
            if page_response.status_code in {400, 404}:
                raise ValueError("Spotify episode page not found.")
            page_response.raise_for_status()
            page = page_response.text

        episode_title = (oembed_payload.get("title") or "").strip()
        if not episode_title:
            episode_title = _extract_meta_content(
                page,
                attribute="property",
                key="og:title",
            )

        show_description = _extract_meta_content(
            page,
            attribute="property",
            key="og:description",
        )
        show_title = ""
        if show_description:
            if _SPOTIFY_SHOW_SUFFIX_TOKEN in show_description:
                show_title = show_description.split(
                    _SPOTIFY_SHOW_SUFFIX_TOKEN,
                    1,
                )[0].strip()
            else:
                show_title = show_description.strip()

        if not show_title:
            title_tag = re.search(
                r"<title>\s*(.*?)\s*</title>",
                page,
                flags=re.IGNORECASE | re.DOTALL,
            )
            title_value = unescape(title_tag.group(1)).strip() if title_tag else ""
            if " - " in title_value and " | Podcast on Spotify" in title_value:
                # "<episode> - <show> | Podcast on Spotify"
                show_title = (
                    title_value.split(" | Podcast on Spotify", 1)[0]
                    .rsplit(" - ", 1)[-1]
                    .strip()
                )

        if not episode_title or not show_title:
            raise ValueError("Spotify episode metadata is incomplete.")

        duration_raw = _extract_meta_content(
            page,
            attribute="name",
            key="music:duration",
        )
        try:
            duration_seconds = int(duration_raw) if duration_raw else 0
        except Exception:
            duration_seconds = 0

        show_match = _SPOTIFY_SHOW_ID_PATTERN.search(page or "")
        spotify_show_id = show_match.group(1) if show_match else ""
        spotify_episode_id = (
            (descriptor.identifiers.get("episode_id") or "").strip()
            if descriptor.identifiers
            else ""
        )

        return {
            "spotify_episode_id": spotify_episode_id,
            "spotify_show_id": spotify_show_id,
            "episode_title": episode_title,
            "show_title": show_title,
            "episode_image": (oembed_payload.get("thumbnail_url") or "").strip(),
            "audio_duration_seconds": duration_seconds,
        }

    async def _resolve_from_podcastindex(
        self,
        *,
        spotify_metadata: dict[str, Any],
    ) -> PodcastResolutionOutcome:
        show_title = (spotify_metadata.get("show_title") or "").strip()
        episode_title = (spotify_metadata.get("episode_title") or "").strip()
        spotify_episode_id = (spotify_metadata.get("spotify_episode_id") or "").strip()

        if not show_title or not episode_title:
            return PodcastResolutionOutcome.failed(
                error_code=PodcastResolverErrorCode.INVALID_PLATFORM_URL,
                client_message=DEFAULT_PODCAST_RESOLUTION_FAILED_MESSAGE,
                retryable=False,
                metadata={
                    "reason": "spotify_metadata_missing_titles",
                    "spotify_episode_id": spotify_episode_id,
                },
            )

        search_result = await podcast_index.search_podcasts(
            query=show_title,
            max_results=self._feed_candidates,
            similar=True,
        )
        if search_result.get("status") != "true":
            raise RuntimeError("PodcastIndex feed search returned non-success status.")

        feeds = search_result.get("feeds", [])
        if not feeds:
            return PodcastResolutionOutcome.failed(
                error_code=PodcastResolverErrorCode.EPISODE_NOT_FOUND,
                client_message=DEFAULT_PODCAST_RESOLUTION_FAILED_MESSAGE,
                retryable=False,
                metadata={
                    "reason": "no_candidate_feeds_found",
                    "spotify_episode_id": spotify_episode_id,
                    "show_title": show_title,
                    "episode_title": episode_title,
                },
            )

        attempted_feed_ids: list[int] = []
        transient_feed_errors = 0
        for feed in feeds[: self._feed_candidates]:
            feed_id = feed.get("id")
            if feed_id is None:
                continue
            try:
                normalized_feed_id = int(feed_id)
            except Exception:
                continue
            attempted_feed_ids.append(normalized_feed_id)

            try:
                episodes_result = await podcast_index.get_episodes_by_feed_id(
                    feed_id=normalized_feed_id,
                    max_results=min(self._episode_candidates, 1000),
                )
                if episodes_result.get("status") != "true":
                    raise RuntimeError(
                        "PodcastIndex episodes lookup returned non-success status."
                    )
            except Exception as exc:
                if _is_transient_error(exc):
                    transient_feed_errors += 1
                logger.warning(
                    "Spotify resolver failed fetching PodcastIndex feed_id=%s: %s",
                    normalized_feed_id,
                    exc,
                )
                continue

            episode_items = episodes_result.get("items", [])
            match = best_match_episode(episode_items, episode_title)
            if not match:
                continue

            audio_url = (match.get("enclosureUrl") or "").strip()
            if not audio_url:
                return PodcastResolutionOutcome.failed(
                    error_code=PodcastResolverErrorCode.AUDIO_URL_NOT_FOUND,
                    client_message=DEFAULT_PODCAST_RESOLUTION_FAILED_MESSAGE,
                    retryable=False,
                    metadata={
                        "reason": "matched_episode_missing_enclosure_url",
                        "feed_id": normalized_feed_id,
                        "spotify_episode_id": spotify_episode_id,
                        "episode_title": episode_title,
                    },
                )

            return PodcastResolutionOutcome.resolved(
                audio_url=audio_url,
                title=match.get("title") or episode_title,
                metadata={
                    "feed_id": normalized_feed_id,
                    "podcast_title": match.get("feedTitle")
                    or feed.get("title")
                    or show_title,
                    "episode_title": match.get("title") or episode_title,
                    "episode_image": match.get("image")
                    or match.get("feedImage")
                    or spotify_metadata.get("episode_image")
                    or "",
                    "episode_date_published": int(match.get("datePublished") or 0),
                    "audio_duration_seconds": int(
                        match.get("duration")
                        or spotify_metadata.get("audio_duration_seconds")
                        or 0
                    ),
                    "spotify_episode_id": spotify_episode_id,
                    "spotify_show_id": spotify_metadata.get("spotify_show_id") or "",
                },
            )

        if attempted_feed_ids and transient_feed_errors == len(attempted_feed_ids):
            return PodcastResolutionOutcome.failed(
                error_code=PodcastResolverErrorCode.UPSTREAM_LOOKUP_FAILED,
                client_message=DEFAULT_PODCAST_RESOLUTION_FAILED_MESSAGE,
                retryable=True,
                metadata={
                    "reason": "podcastindex_feed_lookup_failed_for_all_candidates",
                    "spotify_episode_id": spotify_episode_id,
                    "attempted_feed_ids": attempted_feed_ids,
                },
            )

        return PodcastResolutionOutcome.failed(
            error_code=PodcastResolverErrorCode.EPISODE_NOT_FOUND,
            client_message=DEFAULT_PODCAST_RESOLUTION_FAILED_MESSAGE,
            retryable=False,
            metadata={
                "reason": "no_matching_episode_found",
                "spotify_episode_id": spotify_episode_id,
                "show_title": show_title,
                "episode_title": episode_title,
                "attempted_feed_ids": attempted_feed_ids,
            },
        )


class ApplePodcastsPlatformResolver(PodcastPlatformResolver):
    """Apple Podcasts resolver mapping episode URLs to PodcastIndex enclosure URLs."""

    def __init__(
        self,
        *,
        max_retries: int,
        feed_candidates: int,
        episode_candidates: int,
        request_timeout_seconds: float = 20.0,
    ) -> None:
        self._max_retries = max(1, int(max_retries))
        self._feed_candidates = max(1, int(feed_candidates))
        self._episode_candidates = max(1, int(episode_candidates))
        self._request_timeout_seconds = max(1.0, float(request_timeout_seconds))

    @property
    def source_platform(self) -> SourcePlatform:
        return SourcePlatform.APPLE_PODCASTS

    async def resolve(
        self,
        *,
        descriptor: PodcastUrlDescriptor,
    ) -> PodcastResolutionOutcome:
        apple_episode_id = (
            (descriptor.identifiers.get("episode_id") or "").strip()
            if descriptor.identifiers
            else ""
        )
        if not apple_episode_id:
            return PodcastResolutionOutcome.failed(
                error_code=PodcastResolverErrorCode.INVALID_PLATFORM_URL,
                client_message=DEFAULT_PODCAST_RESOLUTION_FAILED_MESSAGE,
                retryable=False,
                metadata={
                    "reason": "apple_episode_url_required",
                    "source_platform": descriptor.source_platform.value,
                },
            )

        attempt = 0
        while attempt < self._max_retries:
            attempt += 1
            try:
                apple_metadata = await self._fetch_apple_episode_metadata(
                    descriptor=descriptor
                )
                return await self._resolve_from_podcastindex(
                    apple_metadata=apple_metadata
                )
            except ValueError as exc:
                return PodcastResolutionOutcome.failed(
                    error_code=PodcastResolverErrorCode.INVALID_PLATFORM_URL,
                    client_message=DEFAULT_PODCAST_RESOLUTION_FAILED_MESSAGE,
                    retryable=False,
                    metadata={
                        "reason": "apple_episode_metadata_unavailable",
                        "apple_episode_id": apple_episode_id,
                        "attempt": attempt,
                        "error_type": type(exc).__name__,
                    },
                )
            except Exception as exc:
                transient = _is_transient_error(exc)
                if attempt < self._max_retries and transient:
                    backoff = min(2 ** (attempt - 1), 8) + random.uniform(0.0, 0.25)
                    logger.warning(
                        "Transient Apple Podcasts resolver error "
                        "(attempt %s/%s), retrying in %.2fs: %s",
                        attempt,
                        self._max_retries,
                        backoff,
                        exc,
                    )
                    await asyncio.sleep(backoff)
                    continue
                return PodcastResolutionOutcome.failed(
                    error_code=PodcastResolverErrorCode.UPSTREAM_LOOKUP_FAILED,
                    client_message=DEFAULT_PODCAST_RESOLUTION_FAILED_MESSAGE,
                    retryable=transient,
                    metadata={
                        "reason": "apple_resolver_upstream_failed",
                        "apple_episode_id": apple_episode_id,
                        "attempt": attempt,
                        "error_type": type(exc).__name__,
                    },
                )

        return PodcastResolutionOutcome.failed(
            error_code=PodcastResolverErrorCode.UPSTREAM_LOOKUP_FAILED,
            client_message=DEFAULT_PODCAST_RESOLUTION_FAILED_MESSAGE,
            retryable=True,
            metadata={
                "reason": "apple_resolver_retries_exhausted",
                "apple_episode_id": apple_episode_id,
                "attempt": attempt,
            },
        )

    async def _fetch_apple_episode_metadata(
        self,
        *,
        descriptor: PodcastUrlDescriptor,
    ) -> dict[str, Any]:
        timeout = httpx.Timeout(self._request_timeout_seconds)
        async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
            oembed_response = await client.get(
                _APPLE_PODCASTS_OEMBED_ENDPOINT,
                params={"url": descriptor.canonical_url},
            )
            if oembed_response.status_code in {400, 404}:
                raise ValueError("Apple Podcasts oEmbed endpoint returned invalid URL.")
            oembed_response.raise_for_status()
            oembed_payload = oembed_response.json()

            page_response = await client.get(descriptor.canonical_url)
            if page_response.status_code in {400, 404}:
                raise ValueError("Apple Podcasts episode page not found.")
            page_response.raise_for_status()
            page = page_response.text

        episode_title = _extract_meta_content(
            page,
            attribute="property",
            key="og:title",
        )
        if not episode_title:
            episode_title = _extract_meta_content(
                page,
                attribute="name",
                key="apple:title",
            )

        show_title = self._extract_show_title_from_og_description(
            _extract_meta_content(
                page,
                attribute="property",
                key="og:description",
            )
        )
        if not show_title:
            show_title = self._extract_show_title_from_schema(page)
        if not show_title:
            show_title = (oembed_payload.get("title") or "").strip()

        if not episode_title:
            raise ValueError("Apple Podcasts episode title is missing.")

        apple_episode_id = (
            (descriptor.identifiers.get("episode_id") or "").strip()
            if descriptor.identifiers
            else ""
        )
        apple_show_id = (
            (descriptor.identifiers.get("show_id") or "").strip()
            if descriptor.identifiers
            else ""
        )

        return {
            "apple_show_id": apple_show_id,
            "apple_episode_id": apple_episode_id,
            "show_title": show_title,
            "episode_title": episode_title,
            "episode_image": _extract_meta_content(
                page,
                attribute="property",
                key="og:image",
            )
            or (oembed_payload.get("thumbnail_url") or "").strip(),
        }

    def _extract_show_title_from_og_description(self, description: str) -> str:
        text = (description or "").strip()
        if not text:
            return ""

        segments = [
            segment.strip()
            for segment in text.split(_APPLE_OG_DESCRIPTION_SEPARATOR)
            if segment.strip()
        ]
        if len(segments) >= 2 and segments[0].lower().startswith("podcast"):
            return segments[1]
        if segments:
            return segments[0]
        return ""

    def _extract_show_title_from_schema(self, page: str) -> str:
        matched = _APPLE_SCHEMA_EPISODE_PATTERN.search(page or "")
        if not matched:
            return ""

        try:
            payload = json.loads(unescape((matched.group("payload") or "").strip()))
        except Exception:
            return ""

        part_of_series = payload.get("partOfSeries")
        if not isinstance(part_of_series, dict):
            return ""
        title = part_of_series.get("name")
        return title.strip() if isinstance(title, str) else ""

    async def _resolve_from_podcastindex(
        self,
        *,
        apple_metadata: dict[str, Any],
    ) -> PodcastResolutionOutcome:
        apple_show_id = (apple_metadata.get("apple_show_id") or "").strip()
        apple_episode_id = (apple_metadata.get("apple_episode_id") or "").strip()
        show_title = (apple_metadata.get("show_title") or "").strip()
        episode_title = (apple_metadata.get("episode_title") or "").strip()

        # Strategy A: Direct iTunes episode ID lookup via episodes/byitunesid.
        # Apple's ?i=<id> is the iTunes episode ID. PodcastIndex has a dedicated
        # endpoint that maps it directly to an episode record.
        if apple_episode_id:
            direct_result = await self._try_direct_itunes_episode_lookup(
                apple_episode_id=apple_episode_id,
                apple_show_id=apple_show_id,
                show_title=show_title,
                episode_title=episode_title,
                apple_metadata=apple_metadata,
            )
            if direct_result is not None:
                return direct_result

        # Fallback: feed-search + title matching (original strategy).
        return await self._resolve_via_feed_search(
            apple_show_id=apple_show_id,
            apple_episode_id=apple_episode_id,
            show_title=show_title,
            episode_title=episode_title,
            apple_metadata=apple_metadata,
        )

    async def _try_direct_itunes_episode_lookup(
        self,
        *,
        apple_episode_id: str,
        apple_show_id: str,
        show_title: str,
        episode_title: str,
        apple_metadata: dict[str, Any],
    ) -> PodcastResolutionOutcome | None:
        """
        Attempt to resolve episode via PodcastIndex episodes/byitunesid endpoint.

        Returns a PodcastResolutionOutcome if successful or a terminal failure,
        or None if the lookup did not yield a result and the caller should fall
        back to feed-search strategy.
        """
        try:
            result = await podcast_index.get_episode_by_itunes_id(apple_episode_id)
        except Exception as exc:
            # Non-fatal: log and let fallback strategy proceed.
            logger.info(
                "Direct iTunes episode ID lookup failed for %s, "
                "falling back to feed search: %s",
                apple_episode_id,
                exc,
            )
            return None

        if result.get("status") != "true":
            logger.info(
                "Direct iTunes episode ID lookup returned non-success for %s, "
                "falling back to feed search.",
                apple_episode_id,
            )
            return None

        # The endpoint returns the episode under "episode" key.
        episode = result.get("episode")
        if not isinstance(episode, dict):
            return None

        audio_url = (episode.get("enclosureUrl") or "").strip()
        if not audio_url:
            logger.info(
                "Direct iTunes episode ID lookup found episode but no enclosureUrl "
                "for iTunes episode %s.",
                apple_episode_id,
            )
            return None

        feed_id = episode.get("feedId")
        return PodcastResolutionOutcome.resolved(
            audio_url=audio_url,
            title=episode.get("title") or episode_title or "Podcast episode",
            metadata={
                "feed_id": int(feed_id) if feed_id is not None else None,
                "podcast_title": episode.get("feedTitle")
                or show_title
                or "Podcast",
                "episode_title": episode.get("title")
                or episode_title
                or "Podcast episode",
                "episode_image": episode.get("image")
                or episode.get("feedImage")
                or apple_metadata.get("episode_image")
                or "",
                "episode_date_published": int(episode.get("datePublished") or 0),
                "audio_duration_seconds": int(episode.get("duration") or 0),
                "apple_show_id": apple_show_id,
                "apple_episode_id": apple_episode_id,
                "resolution_strategy": "direct_itunes_episode_id",
            },
        )

    async def _resolve_via_feed_search(
        self,
        *,
        apple_show_id: str,
        apple_episode_id: str,
        show_title: str,
        episode_title: str,
        apple_metadata: dict[str, Any],
    ) -> PodcastResolutionOutcome:
        """Fallback: search feeds by iTunes show ID / title, then match by title."""
        candidate_feed_ids: list[int] = []
        feed_metadata_by_id: dict[int, dict[str, Any]] = {}
        if apple_show_id:
            try:
                by_itunes_result = await podcast_index.get_podcast_by_itunes_id(
                    apple_show_id
                )
                if by_itunes_result.get("status") == "true":
                    feed_id = _extract_feed_id(by_itunes_result)
                    if feed_id is not None:
                        candidate_feed_ids.append(feed_id)
                        feed = by_itunes_result.get("feed")
                        if isinstance(feed, dict):
                            feed_metadata_by_id[feed_id] = feed
            except Exception as exc:
                logger.warning(
                    "Apple resolver: podcasts/byitunesid lookup failed for show %s: %s",
                    apple_show_id,
                    exc,
                )

        if show_title:
            search_result = await podcast_index.search_podcasts(
                query=show_title,
                max_results=self._feed_candidates,
                similar=True,
            )
            if search_result.get("status") != "true":
                raise RuntimeError(
                    "PodcastIndex feed search returned non-success status."
                )
            for feed in (search_result.get("feeds") or [])[: self._feed_candidates]:
                feed_id = feed.get("id")
                if feed_id is None:
                    continue
                try:
                    normalized_feed_id = int(feed_id)
                except Exception:
                    continue
                if normalized_feed_id in candidate_feed_ids:
                    continue
                candidate_feed_ids.append(normalized_feed_id)
                if isinstance(feed, dict):
                    feed_metadata_by_id[normalized_feed_id] = feed

        if not candidate_feed_ids:
            return PodcastResolutionOutcome.failed(
                error_code=PodcastResolverErrorCode.EPISODE_NOT_FOUND,
                client_message=(
                    "This podcast episode could not be found in PodcastIndex. "
                    "The podcast may not be indexed yet."
                ),
                retryable=False,
                metadata={
                    "reason": "no_candidate_feeds_found",
                    "apple_show_id": apple_show_id,
                    "apple_episode_id": apple_episode_id,
                    "show_title": show_title,
                    "episode_title": episode_title,
                },
            )

        attempted_feed_ids: list[int] = []
        transient_feed_errors = 0
        for feed_id in candidate_feed_ids:
            attempted_feed_ids.append(feed_id)
            try:
                episodes_result = await podcast_index.get_episodes_by_feed_id(
                    feed_id=feed_id,
                    max_results=min(self._episode_candidates, 1000),
                )
                if episodes_result.get("status") != "true":
                    raise RuntimeError(
                        "PodcastIndex episodes lookup returned non-success status."
                    )
            except Exception as exc:
                if _is_transient_error(exc):
                    transient_feed_errors += 1
                logger.warning(
                    (
                        "Apple Podcasts resolver failed "
                        "fetching PodcastIndex feed_id=%s: %s"
                    ),
                    feed_id,
                    exc,
                )
                continue

            match = self._match_episode_by_title(
                episodes=episodes_result.get("items", []),
                episode_title=episode_title,
            )
            if not match:
                continue

            audio_url = (match.get("enclosureUrl") or "").strip()
            if not audio_url:
                return PodcastResolutionOutcome.failed(
                    error_code=PodcastResolverErrorCode.AUDIO_URL_NOT_FOUND,
                    client_message=DEFAULT_PODCAST_RESOLUTION_FAILED_MESSAGE,
                    retryable=False,
                    metadata={
                        "reason": "matched_episode_missing_enclosure_url",
                        "feed_id": feed_id,
                        "apple_episode_id": apple_episode_id,
                        "episode_title": episode_title,
                    },
                )

            return PodcastResolutionOutcome.resolved(
                audio_url=audio_url,
                title=match.get("title") or episode_title or "Podcast episode",
                metadata={
                    "feed_id": feed_id,
                    "podcast_title": match.get("feedTitle")
                    or (feed_metadata_by_id.get(feed_id, {}).get("title") or "")
                    or show_title
                    or "Podcast",
                    "episode_title": match.get("title")
                    or episode_title
                    or "Podcast episode",
                    "episode_image": match.get("image")
                    or match.get("feedImage")
                    or apple_metadata.get("episode_image")
                    or "",
                    "episode_date_published": int(match.get("datePublished") or 0),
                    "audio_duration_seconds": int(match.get("duration") or 0),
                    "apple_show_id": apple_show_id,
                    "apple_episode_id": apple_episode_id,
                    "resolution_strategy": "feed_search_title_match",
                },
            )

        if attempted_feed_ids and transient_feed_errors == len(attempted_feed_ids):
            return PodcastResolutionOutcome.failed(
                error_code=PodcastResolverErrorCode.UPSTREAM_LOOKUP_FAILED,
                client_message=DEFAULT_PODCAST_RESOLUTION_FAILED_MESSAGE,
                retryable=True,
                metadata={
                    "reason": "podcastindex_feed_lookup_failed_for_all_candidates",
                    "apple_show_id": apple_show_id,
                    "apple_episode_id": apple_episode_id,
                    "attempted_feed_ids": attempted_feed_ids,
                },
            )

        return PodcastResolutionOutcome.failed(
            error_code=PodcastResolverErrorCode.EPISODE_NOT_FOUND,
            client_message=(
                "This podcast episode could not be found in PodcastIndex. "
                "The episode may not be indexed, or the podcast is not available "
                "in the open RSS directory."
            ),
            retryable=False,
            metadata={
                "reason": "no_matching_episode_found",
                "apple_show_id": apple_show_id,
                "apple_episode_id": apple_episode_id,
                "show_title": show_title,
                "episode_title": episode_title,
                "attempted_feed_ids": attempted_feed_ids,
            },
        )

    def _match_episode_by_title(
        self,
        *,
        episodes: list[dict[str, Any]],
        episode_title: str,
    ) -> dict[str, Any] | None:
        """Match episodes using title-based fuzzy matching only."""
        if episode_title:
            matched = best_match_episode(episodes, episode_title)
            if isinstance(matched, dict):
                return matched
        return None


class DeezerPodcastPlatformResolver(PodcastPlatformResolver):
    """Deezer resolver mapping episode URLs to PodcastIndex enclosure URLs."""

    def __init__(
        self,
        *,
        max_retries: int,
        feed_candidates: int,
        episode_candidates: int,
        request_timeout_seconds: float = 20.0,
    ) -> None:
        self._max_retries = max(1, int(max_retries))
        self._feed_candidates = max(1, int(feed_candidates))
        self._episode_candidates = max(1, int(episode_candidates))
        self._request_timeout_seconds = max(1.0, float(request_timeout_seconds))

    @property
    def source_platform(self) -> SourcePlatform:
        return SourcePlatform.DEEZER

    async def resolve(
        self,
        *,
        descriptor: PodcastUrlDescriptor,
    ) -> PodcastResolutionOutcome:
        deezer_episode_id = (
            (descriptor.identifiers.get("episode_id") or "").strip()
            if descriptor.identifiers
            else ""
        )
        if not deezer_episode_id:
            return PodcastResolutionOutcome.failed(
                error_code=PodcastResolverErrorCode.INVALID_PLATFORM_URL,
                client_message=DEFAULT_PODCAST_RESOLUTION_FAILED_MESSAGE,
                retryable=False,
                metadata={
                    "reason": "deezer_episode_url_required",
                    "source_platform": descriptor.source_platform.value,
                },
            )

        attempt = 0
        while attempt < self._max_retries:
            attempt += 1
            try:
                deezer_metadata = await self._fetch_deezer_episode_metadata(
                    descriptor=descriptor
                )
            except ValueError as exc:
                return PodcastResolutionOutcome.failed(
                    error_code=PodcastResolverErrorCode.INVALID_PLATFORM_URL,
                    client_message=DEFAULT_PODCAST_RESOLUTION_FAILED_MESSAGE,
                    retryable=False,
                    metadata={
                        "reason": "deezer_episode_metadata_unavailable",
                        "deezer_episode_id": deezer_episode_id,
                        "attempt": attempt,
                        "error_type": type(exc).__name__,
                    },
                )

            try:
                return await self._resolve_from_podcastindex(
                    deezer_metadata=deezer_metadata,
                )
            except Exception as exc:
                transient = _is_transient_error(exc)
                if attempt < self._max_retries and transient:
                    backoff = min(2 ** (attempt - 1), 8) + random.uniform(0.0, 0.25)
                    logger.warning(
                        "Transient Deezer resolver error "
                        "(attempt %s/%s), retrying in %.2fs: %s",
                        attempt,
                        self._max_retries,
                        backoff,
                        exc,
                    )
                    await asyncio.sleep(backoff)
                    continue
                return PodcastResolutionOutcome.failed(
                    error_code=PodcastResolverErrorCode.UPSTREAM_LOOKUP_FAILED,
                    client_message=DEFAULT_PODCAST_RESOLUTION_FAILED_MESSAGE,
                    retryable=transient,
                    metadata={
                        "reason": "deezer_resolver_upstream_failed",
                        "deezer_episode_id": deezer_episode_id,
                        "attempt": attempt,
                        "error_type": type(exc).__name__,
                    },
                )

        return PodcastResolutionOutcome.failed(
            error_code=PodcastResolverErrorCode.UPSTREAM_LOOKUP_FAILED,
            client_message=DEFAULT_PODCAST_RESOLUTION_FAILED_MESSAGE,
            retryable=True,
            metadata={
                "reason": "deezer_resolver_retries_exhausted",
                "deezer_episode_id": deezer_episode_id,
                "attempt": attempt,
            },
        )

    async def _fetch_deezer_episode_metadata(
        self,
        *,
        descriptor: PodcastUrlDescriptor,
    ) -> dict[str, Any]:
        deezer_episode_id = (
            (descriptor.identifiers.get("episode_id") or "").strip()
            if descriptor.identifiers
            else ""
        )
        if not deezer_episode_id:
            raise ValueError("Missing Deezer episode id.")

        timeout = httpx.Timeout(self._request_timeout_seconds)
        async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
            response = await client.get(
                f"{_DEEZER_API_BASE_URL}/episode/{deezer_episode_id}"
            )
            if response.status_code in {400, 404}:
                raise ValueError("Deezer episode endpoint returned invalid URL.")
            response.raise_for_status()
            payload = response.json()

        if not isinstance(payload, dict):
            raise ValueError("Invalid Deezer episode response payload.")

        error_payload = payload.get("error")
        if isinstance(error_payload, dict):
            error_message = (error_payload.get("message") or "").strip()
            if "no data" in error_message.lower():
                raise ValueError("Deezer episode data not found.")
            raise RuntimeError(
                f"Deezer episode API error: {error_message or 'unknown'}"
            )

        episode_title = (payload.get("title") or "").strip()

        podcast_payload = payload.get("podcast")
        deezer_show_id = ""
        show_title = ""
        show_image = ""
        if isinstance(podcast_payload, dict):
            deezer_show_id = str(podcast_payload.get("id") or "").strip()
            show_title = (podcast_payload.get("title") or "").strip()
            show_image = (
                (podcast_payload.get("picture_xl") or "").strip()
                or (podcast_payload.get("picture_big") or "").strip()
                or (podcast_payload.get("picture_medium") or "").strip()
                or (podcast_payload.get("picture_small") or "").strip()
                or (podcast_payload.get("picture") or "").strip()
            )

        if not episode_title or not show_title:
            raise ValueError("Deezer episode metadata is incomplete.")

        try:
            audio_duration_seconds = int(payload.get("duration") or 0)
        except Exception:
            audio_duration_seconds = 0

        episode_image = (
            (payload.get("picture_xl") or "").strip()
            or (payload.get("picture_big") or "").strip()
            or (payload.get("picture_medium") or "").strip()
            or (payload.get("picture_small") or "").strip()
            or (payload.get("picture") or "").strip()
            or show_image
        )

        return {
            "deezer_episode_id": deezer_episode_id,
            "deezer_show_id": deezer_show_id,
            "show_title": show_title,
            "episode_title": episode_title,
            "episode_image": episode_image,
            "audio_duration_seconds": audio_duration_seconds,
        }

    async def _resolve_from_podcastindex(
        self,
        *,
        deezer_metadata: dict[str, Any],
    ) -> PodcastResolutionOutcome:
        deezer_show_id = (deezer_metadata.get("deezer_show_id") or "").strip()
        deezer_episode_id = (deezer_metadata.get("deezer_episode_id") or "").strip()
        show_title = (deezer_metadata.get("show_title") or "").strip()
        episode_title = (deezer_metadata.get("episode_title") or "").strip()

        if not show_title or not episode_title:
            return PodcastResolutionOutcome.failed(
                error_code=PodcastResolverErrorCode.INVALID_PLATFORM_URL,
                client_message=DEFAULT_PODCAST_RESOLUTION_FAILED_MESSAGE,
                retryable=False,
                metadata={
                    "reason": "deezer_metadata_missing_titles",
                    "deezer_show_id": deezer_show_id,
                    "deezer_episode_id": deezer_episode_id,
                },
            )

        search_result = await podcast_index.search_podcasts(
            query=show_title,
            max_results=self._feed_candidates,
            similar=True,
        )
        if search_result.get("status") != "true":
            raise RuntimeError("PodcastIndex feed search returned non-success status.")

        feeds = search_result.get("feeds", [])
        if not feeds:
            return PodcastResolutionOutcome.failed(
                error_code=PodcastResolverErrorCode.EPISODE_NOT_FOUND,
                client_message=DEFAULT_PODCAST_RESOLUTION_FAILED_MESSAGE,
                retryable=False,
                metadata={
                    "reason": "no_candidate_feeds_found",
                    "deezer_show_id": deezer_show_id,
                    "deezer_episode_id": deezer_episode_id,
                    "show_title": show_title,
                    "episode_title": episode_title,
                },
            )

        attempted_feed_ids: list[int] = []
        transient_feed_errors = 0
        for feed in feeds[: self._feed_candidates]:
            feed_id = feed.get("id")
            if feed_id is None:
                continue
            try:
                normalized_feed_id = int(feed_id)
            except Exception:
                continue
            attempted_feed_ids.append(normalized_feed_id)

            try:
                episodes_result = await podcast_index.get_episodes_by_feed_id(
                    feed_id=normalized_feed_id,
                    max_results=min(self._episode_candidates, 1000),
                )
                if episodes_result.get("status") != "true":
                    raise RuntimeError(
                        "PodcastIndex episodes lookup returned non-success status."
                    )
            except Exception as exc:
                if _is_transient_error(exc):
                    transient_feed_errors += 1
                logger.warning(
                    "Deezer resolver failed fetching PodcastIndex feed_id=%s: %s",
                    normalized_feed_id,
                    exc,
                )
                continue

            episode_items = episodes_result.get("items", [])
            match = best_match_episode(episode_items, episode_title)
            if not match:
                continue

            audio_url = (match.get("enclosureUrl") or "").strip()
            if not audio_url:
                return PodcastResolutionOutcome.failed(
                    error_code=PodcastResolverErrorCode.AUDIO_URL_NOT_FOUND,
                    client_message=DEFAULT_PODCAST_RESOLUTION_FAILED_MESSAGE,
                    retryable=False,
                    metadata={
                        "reason": "matched_episode_missing_enclosure_url",
                        "feed_id": normalized_feed_id,
                        "deezer_episode_id": deezer_episode_id,
                        "episode_title": episode_title,
                    },
                )

            return PodcastResolutionOutcome.resolved(
                audio_url=audio_url,
                title=match.get("title") or episode_title,
                metadata={
                    "feed_id": normalized_feed_id,
                    "podcast_title": match.get("feedTitle")
                    or feed.get("title")
                    or show_title,
                    "episode_title": match.get("title") or episode_title,
                    "episode_image": match.get("image")
                    or match.get("feedImage")
                    or deezer_metadata.get("episode_image")
                    or "",
                    "episode_date_published": int(match.get("datePublished") or 0),
                    "audio_duration_seconds": int(
                        match.get("duration")
                        or deezer_metadata.get("audio_duration_seconds")
                        or 0
                    ),
                    "deezer_episode_id": deezer_episode_id,
                    "deezer_show_id": deezer_show_id,
                },
            )

        if attempted_feed_ids and transient_feed_errors == len(attempted_feed_ids):
            return PodcastResolutionOutcome.failed(
                error_code=PodcastResolverErrorCode.UPSTREAM_LOOKUP_FAILED,
                client_message=DEFAULT_PODCAST_RESOLUTION_FAILED_MESSAGE,
                retryable=True,
                metadata={
                    "reason": "podcastindex_feed_lookup_failed_for_all_candidates",
                    "deezer_show_id": deezer_show_id,
                    "deezer_episode_id": deezer_episode_id,
                    "attempted_feed_ids": attempted_feed_ids,
                },
            )

        return PodcastResolutionOutcome.failed(
            error_code=PodcastResolverErrorCode.EPISODE_NOT_FOUND,
            client_message=DEFAULT_PODCAST_RESOLUTION_FAILED_MESSAGE,
            retryable=False,
            metadata={
                "reason": "no_matching_episode_found",
                "deezer_show_id": deezer_show_id,
                "deezer_episode_id": deezer_episode_id,
                "show_title": show_title,
                "episode_title": episode_title,
                "attempted_feed_ids": attempted_feed_ids,
            },
        )


class RssPodcastPlatformResolver(PodcastPlatformResolver):
    """RSS resolver with direct feed parsing + opportunistic PodcastIndex enrichment."""

    def __init__(
        self,
        *,
        max_retries: int,
        episode_candidates: int,
        request_timeout_seconds: float = 20.0,
    ) -> None:
        self._max_retries = max(1, int(max_retries))
        self._episode_candidates = max(1, int(episode_candidates))
        self._request_timeout_seconds = max(1.0, float(request_timeout_seconds))

    @property
    def source_platform(self) -> SourcePlatform:
        return SourcePlatform.RSS

    async def resolve(
        self,
        *,
        descriptor: PodcastUrlDescriptor,
    ) -> PodcastResolutionOutcome:
        feed_url = descriptor.canonical_url
        if not _looks_like_feed_url(feed_url):
            logger.info(
                "RSS URL has no explicit feed hint, trying direct feed resolution: %s",
                feed_url,
            )

        attempt = 0
        resolution: dict[str, Any] | None = None
        while attempt < self._max_retries:
            attempt += 1
            try:
                resolution = await self._resolve_direct_rss(feed_url=feed_url)
                break
            except _RssFeedInvalidError as exc:
                metadata = {
                    "reason": "rss_feed_parse_failed",
                    "attempt": attempt,
                }
                if exc.metadata:
                    metadata.update(exc.metadata)
                return PodcastResolutionOutcome.failed(
                    error_code=PodcastResolverErrorCode.INVALID_PLATFORM_URL,
                    client_message=DEFAULT_PODCAST_RESOLUTION_FAILED_MESSAGE,
                    retryable=False,
                    metadata=metadata,
                )
            except _RssFeedNoAudioError as exc:
                metadata = {
                    "reason": "rss_feed_has_no_episode_with_audio",
                    "attempt": attempt,
                }
                if exc.metadata:
                    metadata.update(exc.metadata)
                return PodcastResolutionOutcome.failed(
                    error_code=PodcastResolverErrorCode.AUDIO_URL_NOT_FOUND,
                    client_message=DEFAULT_PODCAST_RESOLUTION_FAILED_MESSAGE,
                    retryable=False,
                    metadata=metadata,
                )
            except Exception as exc:
                transient = _is_transient_error(exc)
                if attempt < self._max_retries and transient:
                    backoff = min(2 ** (attempt - 1), 8) + random.uniform(0.0, 0.25)
                    logger.warning(
                        "Transient RSS direct resolution error "
                        "(attempt %s/%s), retrying in %.2fs: %s",
                        attempt,
                        self._max_retries,
                        backoff,
                        exc,
                    )
                    await asyncio.sleep(backoff)
                    continue

                return PodcastResolutionOutcome.failed(
                    error_code=PodcastResolverErrorCode.UPSTREAM_LOOKUP_FAILED,
                    client_message=DEFAULT_PODCAST_RESOLUTION_FAILED_MESSAGE,
                    retryable=transient,
                    metadata={
                        "reason": "rss_direct_lookup_failed",
                        "attempt": attempt,
                        "error_type": type(exc).__name__,
                    },
                )

        if resolution is None:
            return PodcastResolutionOutcome.failed(
                error_code=PodcastResolverErrorCode.UPSTREAM_LOOKUP_FAILED,
                client_message=DEFAULT_PODCAST_RESOLUTION_FAILED_MESSAGE,
                retryable=True,
                metadata={
                    "reason": "retries_exhausted",
                    "attempt": attempt,
                },
            )

        rss_metadata = dict(resolution.get("metadata") or {})
        enrichment = await self._try_podcastindex_enrichment(
            feed_url=feed_url,
            rss_episode_title=rss_metadata.get("episode_title") or "",
            rss_audio_url=resolution.get("audio_url") or "",
        )
        metadata = self._merge_rss_and_enrichment_metadata(
            rss_metadata=rss_metadata,
            enrichment=enrichment,
        )

        return PodcastResolutionOutcome.resolved(
            audio_url=resolution.get("audio_url") or "",
            title=(
                metadata.get("episode_title")
                or resolution.get("title")
                or "Podcast episode"
            ),
            metadata=metadata,
        )

    async def _resolve_direct_rss(self, *, feed_url: str) -> dict[str, Any]:
        document = await self._fetch_feed_document(feed_url=feed_url)
        return self._extract_rss_resolution_payload(
            feed_url=feed_url,
            document=document,
        )

    async def _fetch_feed_document(self, *, feed_url: str) -> str:
        timeout = httpx.Timeout(self._request_timeout_seconds)
        async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
            response = await client.get(
                feed_url,
                headers={"Accept": _RSS_HTTP_ACCEPT_HEADER},
            )
            if response.status_code in {400, 404}:
                raise _RssFeedInvalidError(
                    "RSS feed URL returned an invalid response.",
                    metadata={"feed_url": feed_url},
                )
            response.raise_for_status()
            document = (response.text or "").strip()
            if not document:
                raise _RssFeedInvalidError(
                    "RSS feed response is empty.",
                    metadata={"feed_url": feed_url},
                )
            return document

    def _extract_rss_resolution_payload(
        self,
        *,
        feed_url: str,
        document: str,
    ) -> dict[str, Any]:
        try:
            root = ET.fromstring(document)
        except ET.ParseError as exc:
            raise _RssFeedInvalidError(
                "RSS feed document could not be parsed.",
                metadata={"feed_url": feed_url},
            ) from exc

        channel = self._select_feed_channel(root)
        if channel is None:
            raise _RssFeedInvalidError(
                "RSS/Atom channel element is missing.",
                metadata={"feed_url": feed_url},
            )

        podcast_title = self._extract_channel_title(channel) or "Podcast"
        channel_image = self._extract_channel_image(channel, feed_url=feed_url)
        items = self._extract_channel_items(channel=channel, root=root)
        if not items:
            raise _RssFeedNoAudioError(
                "RSS feed contains no episode entries.",
                metadata={
                    "feed_url": feed_url,
                    "podcast_title": podcast_title,
                },
            )

        episode_candidates: list[dict[str, Any]] = []
        first_episode_title = ""
        for order, item in enumerate(items):
            episode_title = self._extract_episode_title(item) or "Podcast episode"
            if not first_episode_title:
                first_episode_title = episode_title

            audio_url = self._extract_episode_audio_url(item, feed_url=feed_url)
            if not audio_url:
                continue

            episode_candidates.append(
                {
                    "audio_url": audio_url,
                    "episode_title": episode_title,
                    "episode_image": self._extract_episode_image(
                        item,
                        feed_url=feed_url,
                    )
                    or channel_image,
                    "episode_date_published": self._extract_episode_timestamp(item),
                    "audio_duration_seconds": self._extract_episode_duration(item),
                    "order": order,
                }
            )

        if not episode_candidates:
            raise _RssFeedNoAudioError(
                "RSS feed contains no episode with enclosure URL.",
                metadata={
                    "feed_url": feed_url,
                    "podcast_title": podcast_title,
                    "episode_title": first_episode_title,
                },
            )

        selected = max(
            episode_candidates,
            key=lambda item: (
                int(item.get("episode_date_published") or 0),
                -int(item.get("order") or 0),
            ),
        )

        return {
            "audio_url": selected["audio_url"],
            "title": selected["episode_title"],
            "metadata": {
                "podcast_title": podcast_title,
                "episode_title": selected["episode_title"],
                "episode_image": selected["episode_image"],
                "episode_date_published": int(
                    selected.get("episode_date_published") or 0
                ),
                "audio_duration_seconds": int(
                    selected.get("audio_duration_seconds") or 0
                ),
                "resolution_source": "rss_direct",
            },
        }

    def _select_feed_channel(self, root: ET.Element) -> ET.Element | None:
        root_name = _xml_local_name(root.tag)
        if root_name == "feed":
            return root
        if root_name == "rss":
            for child in list(root):
                if _xml_local_name(child.tag) == "channel":
                    return child
        return None

    def _extract_channel_items(
        self,
        *,
        channel: ET.Element,
        root: ET.Element,
    ) -> list[ET.Element]:
        items = [
            child
            for child in list(channel)
            if _xml_local_name(child.tag) in {"item", "entry"}
        ]
        if items:
            return items
        return [
            node
            for node in root.iter()
            if _xml_local_name(node.tag) in {"item", "entry"}
        ]

    def _extract_channel_title(self, channel: ET.Element) -> str:
        return _first_direct_text(channel, ("title",))

    def _extract_channel_image(self, channel: ET.Element, *, feed_url: str) -> str:
        for child in list(channel):
            local_name = _xml_local_name(child.tag)
            if local_name == "image":
                image_attr = (
                    (child.attrib.get("href") or "").strip()
                    or (child.attrib.get("url") or "").strip()
                )
                if image_attr:
                    return _absolutize_http_url(base_url=feed_url, candidate=image_attr)

                image_url = _first_direct_text(child, ("url",))
                if image_url:
                    return _absolutize_http_url(base_url=feed_url, candidate=image_url)

            if local_name in {"logo", "icon"}:
                image_text = (child.text or "").strip()
                if image_text:
                    return _absolutize_http_url(base_url=feed_url, candidate=image_text)

        return ""

    def _extract_episode_title(self, item: ET.Element) -> str:
        return _first_direct_text(item, ("title",))

    def _extract_episode_audio_url(self, item: ET.Element, *, feed_url: str) -> str:
        for child in list(item):
            local_name = _xml_local_name(child.tag)

            if local_name == "enclosure":
                enclosure_url = (
                    (child.attrib.get("url") or "").strip()
                    or (child.text or "").strip()
                )
                resolved = _absolutize_http_url(
                    base_url=feed_url,
                    candidate=enclosure_url,
                )
                if resolved:
                    return resolved

            if local_name == "link":
                rel = (child.attrib.get("rel") or "").strip().lower()
                mime_type = (child.attrib.get("type") or "").strip().lower()
                link_url = (child.attrib.get("href") or "").strip() or (
                    child.text or ""
                ).strip()
                if (
                    rel == "enclosure"
                    or mime_type.startswith("audio/")
                    or "audio" in mime_type
                ):
                    resolved = _absolutize_http_url(
                        base_url=feed_url,
                        candidate=link_url,
                    )
                    if resolved:
                        return resolved

            if local_name == "content":
                mime_type = (child.attrib.get("type") or "").strip().lower()
                content_url = (child.attrib.get("url") or "").strip() or (
                    child.text or ""
                ).strip()
                if not content_url:
                    continue
                if mime_type and "audio" not in mime_type:
                    continue
                resolved = _absolutize_http_url(
                    base_url=feed_url,
                    candidate=content_url,
                )
                if resolved:
                    return resolved

        return ""

    def _extract_episode_image(self, item: ET.Element, *, feed_url: str) -> str:
        image_from_child = _first_direct_attr(
            item,
            names=("image", "thumbnail"),
            attrs=("href", "url"),
        )
        if image_from_child:
            return _absolutize_http_url(base_url=feed_url, candidate=image_from_child)

        for child in list(item):
            if _xml_local_name(child.tag) != "image":
                continue
            image_text = _first_direct_text(child, ("url",)) or (
                child.text or ""
            ).strip()
            if image_text:
                return _absolutize_http_url(base_url=feed_url, candidate=image_text)
        return ""

    def _extract_episode_timestamp(self, item: ET.Element) -> int:
        date_text = _first_direct_text(item, ("pubdate", "published", "updated"))
        return _parse_timestamp_seconds(date_text)

    def _extract_episode_duration(self, item: ET.Element) -> int:
        duration_text = _first_direct_text(item, ("duration",))
        return _parse_duration_seconds(duration_text)

    async def _try_podcastindex_enrichment(
        self,
        *,
        feed_url: str,
        rss_episode_title: str,
        rss_audio_url: str,
    ) -> dict[str, Any]:
        if not self._is_podcastindex_configured():
            return {}

        try:
            feed_result = await podcast_index.get_podcast_by_feed_url(feed_url)
        except Exception as exc:
            logger.info("RSS enrichment skipped (PodcastIndex lookup failed): %s", exc)
            return {}

        if feed_result.get("status") != "true":
            return {}

        enrichment: dict[str, Any] = {}
        feed_id = _extract_feed_id(feed_result)
        if feed_id is None:
            return enrichment
        enrichment["feed_id"] = feed_id

        feed = feed_result.get("feed")
        if isinstance(feed, dict):
            feed_title = (feed.get("title") or "").strip()
            if feed_title:
                enrichment["podcast_title"] = feed_title

        try:
            episodes_result = await podcast_index.get_episodes_by_feed_id(
                feed_id=feed_id,
                max_results=min(self._episode_candidates, 1000),
            )
        except Exception as exc:
            logger.info(
                "RSS enrichment skipped (PodcastIndex episodes lookup failed): %s",
                exc,
            )
            return enrichment

        if episodes_result.get("status") != "true":
            return enrichment

        episode = self._match_podcastindex_episode(
            episodes=episodes_result.get("items", []),
            rss_episode_title=rss_episode_title,
            rss_audio_url=rss_audio_url,
        )
        if not episode:
            return enrichment

        enrichment["episode_title"] = (episode.get("title") or "").strip()
        enrichment["episode_image"] = (
            (episode.get("image") or "").strip()
            or (episode.get("feedImage") or "").strip()
        )
        enrichment["episode_date_published"] = int(episode.get("datePublished") or 0)
        enrichment["audio_duration_seconds"] = int(episode.get("duration") or 0)
        return enrichment

    def _is_podcastindex_configured(self) -> bool:
        api_key = (getattr(podcast_index, "API_KEY", None) or "").strip()
        api_secret = (getattr(podcast_index, "API_SECRET", None) or "").strip()
        return bool(api_key and api_secret)

    def _match_podcastindex_episode(
        self,
        *,
        episodes: list[dict[str, Any]],
        rss_episode_title: str,
        rss_audio_url: str,
    ) -> dict[str, Any] | None:
        for episode in episodes:
            enclosure_url = (episode.get("enclosureUrl") or "").strip()
            if enclosure_url and rss_audio_url and enclosure_url == rss_audio_url:
                return episode

        if rss_episode_title:
            matched = best_match_episode(episodes, rss_episode_title)
            if isinstance(matched, dict):
                return matched

        return _pick_episode_with_audio(episodes)

    def _merge_rss_and_enrichment_metadata(
        self,
        *,
        rss_metadata: dict[str, Any],
        enrichment: dict[str, Any],
    ) -> dict[str, Any]:
        merged = dict(rss_metadata)
        if not enrichment:
            merged["podcastindex_enriched"] = False
            return merged

        merged["podcastindex_enriched"] = True
        if enrichment.get("feed_id") is not None:
            merged["feed_id"] = enrichment["feed_id"]

        if (
            not (merged.get("podcast_title") or "").strip()
            or merged.get("podcast_title") == "Podcast"
        ):
            podcast_title = (enrichment.get("podcast_title") or "").strip()
            if podcast_title:
                merged["podcast_title"] = podcast_title

        if (
            not (merged.get("episode_title") or "").strip()
            or merged.get("episode_title") == "Podcast episode"
        ):
            episode_title = (enrichment.get("episode_title") or "").strip()
            if episode_title:
                merged["episode_title"] = episode_title

        if not (merged.get("episode_image") or "").strip():
            episode_image = (enrichment.get("episode_image") or "").strip()
            if episode_image:
                merged["episode_image"] = episode_image

        if int(merged.get("episode_date_published") or 0) <= 0:
            merged["episode_date_published"] = int(
                enrichment.get("episode_date_published") or 0
            )

        if int(merged.get("audio_duration_seconds") or 0) <= 0:
            merged["audio_duration_seconds"] = int(
                enrichment.get("audio_duration_seconds") or 0
            )

        merged["resolution_source"] = "rss_direct_with_podcastindex_enrichment"
        return merged


def build_worker_podcast_platform_resolver_registry(
    *,
    max_retries: int,
    episode_candidates: int,
) -> PodcastPlatformResolverRegistry:
    """Build worker registry with one shared interface across all podcast platforms."""
    registry = PodcastPlatformResolverRegistry()
    registry.register_many(
        [
            SpotifyPodcastPlatformResolver(
                max_retries=max_retries,
                feed_candidates=5,
                episode_candidates=max(episode_candidates, 200),
            ),
            ApplePodcastsPlatformResolver(
                max_retries=max_retries,
                feed_candidates=5,
                episode_candidates=max(episode_candidates, 200),
            ),
            DeezerPodcastPlatformResolver(
                max_retries=max_retries,
                feed_candidates=5,
                episode_candidates=max(episode_candidates, 200),
            ),
            RssPodcastPlatformResolver(
                max_retries=max_retries,
                episode_candidates=episode_candidates,
            ),
        ]
    )
    return registry


__all__ = [
    "ApplePodcastsPlatformResolver",
    "DeezerPodcastPlatformResolver",
    "NotImplementedPodcastPlatformResolver",
    "SpotifyPodcastPlatformResolver",
    "RssPodcastPlatformResolver",
    "build_worker_podcast_platform_resolver_registry",
]
