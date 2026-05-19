"""Default resolver adapters for media ingestion."""

from __future__ import annotations

import logging
import os
from typing import Any, Final
from urllib.parse import urlsplit

import httpx

from media_summarizer.core.media_ingestion.adapters.podcast_resolver_foundation import (
    PodcastPlatformResolverRegistry,
    PodcastResolutionOutcome,
    PodcastResolutionStatus,
    PodcastResolverErrorCode,
    build_deferred_podcast_platform_resolver_registry,
    build_podcast_resolution_metadata,
    build_raw_podcast_url_descriptor,
    normalize_podcast_source_url,
)
from media_summarizer.core.media_ingestion.domain import (
    MediaFamily,
    MediaType,
    ResolveContext,
    ResolvedMedia,
    SourcePlatform,
)
from media_summarizer.core.media_ingestion.errors import (
    DEFAULT_INSTAGRAM_PROVIDER_BAD_REQUEST_MESSAGE,
    DEFAULT_INSTAGRAM_PROVIDER_TEMPORARY_MESSAGE,
    NonRetryableProviderResolutionError,
    RetryableProviderResolutionError,
    UnsupportedUrlError,
)
from media_summarizer.core.media_ingestion.ports import ContentResolverPort
from media_summarizer.utils.logging_config import log_event

logger = logging.getLogger(__name__)

_SUPPORTED_PODCAST_PLATFORMS: Final[set[SourcePlatform]] = {
    SourcePlatform.SPOTIFY,
    SourcePlatform.APPLE_PODCASTS,
    SourcePlatform.DEEZER,
    SourcePlatform.RSS,
}
_GETINSAVER_API_BASE_URL = os.environ.get(
    "GETINSAVER_API_BASE_URL", "https://getinsaver.com/api/v1"
).rstrip("/")
_GETINSAVER_API_KEY = os.environ.get("GETINSAVER_API_KEY", "").strip()
_GETINSAVER_TIMEOUT_SECONDS = float(
    os.environ.get("GETINSAVER_TIMEOUT_SECONDS", "20")
)
_IMAGE_DOWNLOAD_EXTENSIONS: Final[tuple[str, ...]] = (
    ".jpg",
    ".jpeg",
    ".png",
    ".gif",
    ".webp",
)


def _instagram_content_type_from_url(normalized_url: str) -> str:
    path = (urlsplit(normalized_url).path or "").lower()
    parts = [segment for segment in path.split("/") if segment]
    if not parts:
        raise NonRetryableProviderResolutionError(
            DEFAULT_INSTAGRAM_PROVIDER_BAD_REQUEST_MESSAGE
        )

    content_type = parts[0]
    if content_type == "reel":
        return "reel"
    if content_type == "p":
        return "post"
    if content_type == "tv":
        return "igtv"
    raise NonRetryableProviderResolutionError(
        DEFAULT_INSTAGRAM_PROVIDER_BAD_REQUEST_MESSAGE
    )


def _looks_like_transcribable_download_url(candidate: str) -> bool:
    value = (candidate or "").strip()
    if not value.startswith(("http://", "https://")):
        return False

    path = (urlsplit(value).path or "").lower()
    return not path.endswith(_IMAGE_DOWNLOAD_EXTENSIONS)


def _extract_instagram_download_url(payload: dict[str, Any]) -> str:
    data = payload.get("data")
    if not isinstance(data, dict):
        raise NonRetryableProviderResolutionError(
            DEFAULT_INSTAGRAM_PROVIDER_BAD_REQUEST_MESSAGE
        )

    provider_media_type = str(data.get("type") or "").strip().lower()
    if provider_media_type in {"image", "photo"}:
        raise NonRetryableProviderResolutionError(
            DEFAULT_INSTAGRAM_PROVIDER_BAD_REQUEST_MESSAGE
        )

    downloads = data.get("downloads")
    if not isinstance(downloads, list) or not downloads:
        raise NonRetryableProviderResolutionError(
            DEFAULT_INSTAGRAM_PROVIDER_BAD_REQUEST_MESSAGE
        )

    for item in downloads:
        if not isinstance(item, dict):
            continue
        candidate = item.get("url")
        if isinstance(candidate, str) and _looks_like_transcribable_download_url(
            candidate
        ):
            return candidate.strip()

    raise NonRetryableProviderResolutionError(
        DEFAULT_INSTAGRAM_PROVIDER_BAD_REQUEST_MESSAGE
    )


def _build_instagram_request_headers() -> dict[str, str]:
    if not _GETINSAVER_API_KEY:
        raise RetryableProviderResolutionError(
            DEFAULT_INSTAGRAM_PROVIDER_TEMPORARY_MESSAGE
        )
    return {
        "Authorization": f"Bearer {_GETINSAVER_API_KEY}",
        "Content-Type": "application/json",
    }


def _normalize_getinsaver_error_message(payload: dict[str, Any]) -> str:
    error = payload.get("error")
    if isinstance(error, dict):
        message = error.get("message")
        if isinstance(message, str) and message.strip():
            return message.strip()
    message = payload.get("message")
    if isinstance(message, str) and message.strip():
        return message.strip()
    return ""


def _extract_x_post_id(normalized_url: str) -> str:
    path = urlsplit((normalized_url or "").strip()).path or ""
    parts = [segment for segment in path.split("/") if segment]
    if len(parts) >= 3 and parts[0] == "i" and parts[1] == "status" and parts[2].isdigit():
        return parts[2].strip()
    if (
        len(parts) >= 4
        and parts[0] == "i"
        and parts[1] == "web"
        and parts[2] == "status"
        and parts[3].isdigit()
    ):
        return parts[3].strip()
    if len(parts) >= 3 and parts[1] == "status" and parts[2].isdigit():
        return parts[2].strip()
    raise UnsupportedUrlError("Unsupported X/Twitter URL format.")


async def _resolve_instagram_download_url(
    *,
    normalized_url: str,
) -> tuple[str, dict[str, Any]]:
    content_type = _instagram_content_type_from_url(normalized_url)
    endpoint = f"{_GETINSAVER_API_BASE_URL}/download/instagram"
    headers = _build_instagram_request_headers()
    payload = {
        "url": normalized_url,
        "type": content_type,
    }

    try:
        async with httpx.AsyncClient(timeout=_GETINSAVER_TIMEOUT_SECONDS) as client:
            response = await client.post(
                endpoint,
                json=payload,
                headers=headers,
            )
    except (httpx.TimeoutException, httpx.TransportError) as exc:
        log_event(
            logger,
            logging.WARNING,
            "external_call.failed",
            "Instagram provider transport request failed",
            provider="getinsaver",
            resolver_key="instagram.default",
            source_platform=SourcePlatform.INSTAGRAM.value,
            error_type=type(exc).__name__,
            exc_info=exc,
        )
        raise RetryableProviderResolutionError(
            DEFAULT_INSTAGRAM_PROVIDER_TEMPORARY_MESSAGE
        ) from exc

    try:
        response_payload = response.json()
    except ValueError:
        response_payload = {}
    if not isinstance(response_payload, dict):
        response_payload = {}

    status_code = response.status_code
    if status_code in {400, 404, 422}:
        raise NonRetryableProviderResolutionError(
            DEFAULT_INSTAGRAM_PROVIDER_BAD_REQUEST_MESSAGE
        )
    if status_code in {401, 403, 429} or status_code >= 500:
        log_event(
            logger,
            logging.WARNING,
            "external_call.failed",
            "Instagram provider returned a transient failure",
            provider="getinsaver",
            resolver_key="instagram.default",
            source_platform=SourcePlatform.INSTAGRAM.value,
            status=status_code,
            detail=_normalize_getinsaver_error_message(response_payload),
        )
        raise RetryableProviderResolutionError(
            DEFAULT_INSTAGRAM_PROVIDER_TEMPORARY_MESSAGE
        )
    if status_code >= 300:
        raise NonRetryableProviderResolutionError(
            DEFAULT_INSTAGRAM_PROVIDER_BAD_REQUEST_MESSAGE
        )

    if response_payload.get("success") is False:
        raise NonRetryableProviderResolutionError(
            DEFAULT_INSTAGRAM_PROVIDER_BAD_REQUEST_MESSAGE
        )

    download_url = _extract_instagram_download_url(response_payload)
    return download_url, {
        "instagram_content_type": content_type,
        "provider_media_type": (
            response_payload.get("data", {}).get("type")
            if isinstance(response_payload.get("data"), dict)
            else None
        ),
    }


class PodcastResolver(ContentResolverPort):
    def __init__(
        self,
        *,
        platform_resolver_registry: PodcastPlatformResolverRegistry | None = None,
    ) -> None:
        self._platform_resolver_registry = (
            platform_resolver_registry
            or build_deferred_podcast_platform_resolver_registry()
        )

    @property
    def key(self) -> str:
        return "podcast.default"

    async def resolve(self, context: ResolveContext) -> ResolvedMedia:
        source_platform = context.classification.source_platform
        descriptor = build_raw_podcast_url_descriptor(
            normalized_url=context.normalized_url,
            source_platform=source_platform,
        )

        try:
            descriptor = normalize_podcast_source_url(
                normalized_url=context.normalized_url,
                source_platform=source_platform,
            )
        except ValueError:
            error_code = (
                PodcastResolverErrorCode.INVALID_PLATFORM_URL
                if source_platform in _SUPPORTED_PODCAST_PLATFORMS
                else PodcastResolverErrorCode.UNSUPPORTED_PLATFORM
            )
            outcome = PodcastResolutionOutcome.failed(
                error_code=error_code,
                metadata={
                    "reason": "podcast_source_url_normalization_failed",
                    "source_platform": source_platform.value,
                },
            )
        else:
            try:
                platform_resolver = self._platform_resolver_registry.get(
                    descriptor.source_platform
                )
            except ValueError:
                outcome = PodcastResolutionOutcome.failed(
                    error_code=PodcastResolverErrorCode.UNSUPPORTED_PLATFORM,
                    metadata={
                        "reason": "podcast_platform_resolver_missing",
                        "source_platform": descriptor.source_platform.value,
                    },
                )
            else:
                try:
                    outcome = await platform_resolver.resolve(descriptor=descriptor)
                except Exception as exc:
                    outcome = PodcastResolutionOutcome.failed(
                        error_code=PodcastResolverErrorCode.UPSTREAM_LOOKUP_FAILED,
                        retryable=True,
                        metadata={
                            "reason": "podcast_platform_resolver_exception",
                            "source_platform": descriptor.source_platform.value,
                            "error_type": type(exc).__name__,
                        },
                    )

        audio_url = (
            outcome.audio_url
            if outcome.status == PodcastResolutionStatus.RESOLVED
            and (outcome.audio_url or "").strip()
            else None
        )

        metadata = {
            "resolver_version": "v2",
            "audio_url_available": bool(audio_url),
            "resolution_mode": (
                "platform_inline"
                if outcome.status == PodcastResolutionStatus.RESOLVED and audio_url
                else "deferred"
            ),
        }
        metadata.update(
            build_podcast_resolution_metadata(
                descriptor=descriptor,
                outcome=outcome,
            )
        )

        resolved = ResolvedMedia(
            media_key=context.media_key,
            normalized_url=context.normalized_url,
            media_family=MediaFamily.PODCAST,
            media_type=MediaType.PODCAST_EPISODE,
            source_platform=source_platform,
            resolver_key=self.key,
            title=outcome.title,
            audio_url=audio_url,
            metadata=metadata,
        )
        log_event(
            logger,
            logging.INFO,
            "resolver.completed",
            "Podcast resolver completed",
            source_platform=source_platform.value,
            resolver_key=self.key,
            media_type=MediaType.PODCAST_EPISODE.value,
            fallback_strategy=metadata.get("resolution_mode"),
        )
        return resolved


class ArticleResolver(ContentResolverPort):
    @property
    def key(self) -> str:
        return "article.default"

    async def resolve(self, context: ResolveContext) -> ResolvedMedia:
        resolved = ResolvedMedia(
            media_key=context.media_key,
            normalized_url=context.normalized_url,
            media_family=MediaFamily.ARTICLE,
            media_type=MediaType.ARTICLE,
            source_platform=SourcePlatform.WEB,
            resolver_key=self.key,
            metadata={
                "resolver_version": "v1",
                "extraction_mode": "queued_worker",
                "source_url": context.normalized_url,
            },
        )
        log_event(
            logger,
            logging.INFO,
            "resolver.completed",
            "Article resolver completed",
            source_platform=SourcePlatform.WEB.value,
            resolver_key=self.key,
            media_type=MediaType.ARTICLE.value,
            fallback_strategy="queued_worker",
        )
        return resolved


class XPostResolver(ContentResolverPort):
    @property
    def key(self) -> str:
        return "x.default"

    async def resolve(self, context: ResolveContext) -> ResolvedMedia:
        tweet_id = _extract_x_post_id(context.normalized_url)
        resolved = ResolvedMedia(
            media_key=context.media_key,
            normalized_url=context.normalized_url,
            media_family=MediaFamily.ARTICLE,
            media_type=MediaType.ARTICLE,
            source_platform=SourcePlatform.X,
            resolver_key=self.key,
            metadata={
                "resolver_version": "v1",
                "tweet_id": tweet_id,
                "lookup_mode": "api_v2",
                "extraction_mode": "queued_worker",
                "source_url": context.normalized_url,
            },
        )
        log_event(
            logger,
            logging.INFO,
            "resolver.completed",
            "X post resolver completed",
            source_platform=SourcePlatform.X.value,
            resolver_key=self.key,
            media_type=MediaType.ARTICLE.value,
            fallback_strategy="queued_worker",
        )
        return resolved


class YouTubeResolver(ContentResolverPort):
    @property
    def key(self) -> str:
        return "youtube.default"

    async def resolve(self, context: ResolveContext) -> ResolvedMedia:
        resolved = ResolvedMedia(
            media_key=context.media_key,
            normalized_url=context.normalized_url,
            media_family=MediaFamily.YOUTUBE,
            media_type=MediaType.YOUTUBE_VIDEO,
            source_platform=SourcePlatform.YOUTUBE,
            resolver_key=self.key,
            metadata={
                "resolver_version": "v2",
                "extraction_mode": "queued_worker",
                "transcript_strategy": "manual_auto_audio",
                "source_url": context.normalized_url,
            },
        )
        log_event(
            logger,
            logging.INFO,
            "resolver.completed",
            "YouTube resolver completed",
            source_platform=SourcePlatform.YOUTUBE.value,
            resolver_key=self.key,
            media_type=MediaType.YOUTUBE_VIDEO.value,
            fallback_strategy="manual_auto_audio",
        )
        return resolved


class InstagramResolver(ContentResolverPort):
    @property
    def key(self) -> str:
        return "instagram.default"

    async def resolve(self, context: ResolveContext) -> ResolvedMedia:
        audio_url, provider_metadata = await _resolve_instagram_download_url(
            normalized_url=context.normalized_url,
        )
        resolved = ResolvedMedia(
            media_key=context.media_key,
            normalized_url=context.normalized_url,
            media_family=MediaFamily.SOCIAL_VIDEO,
            media_type=MediaType.SHORT_VIDEO,
            source_platform=SourcePlatform.INSTAGRAM,
            resolver_key=self.key,
            audio_url=audio_url,
            metadata={
                "resolver_version": "v1",
                "provider": "getinsaver",
                "provider_endpoint": "instagram",
                "instagram_content_type": provider_metadata.get(
                    "instagram_content_type"
                ),
                "provider_media_type": provider_metadata.get("provider_media_type"),
                "audio_url_available": True,
                "resolution_mode": "provider_inline",
            },
        )
        log_event(
            logger,
            logging.INFO,
            "resolver.completed",
            "Instagram resolver completed",
            source_platform=SourcePlatform.INSTAGRAM.value,
            resolver_key=self.key,
            media_type=MediaType.SHORT_VIDEO.value,
            provider="getinsaver",
            fallback_strategy="provider_inline",
        )
        return resolved


class TikTokResolver(ContentResolverPort):
    @property
    def key(self) -> str:
        return "tiktok.default"

    async def resolve(self, context: ResolveContext) -> ResolvedMedia:
        resolved = ResolvedMedia(
            media_key=context.media_key,
            normalized_url=context.normalized_url,
            media_family=MediaFamily.SOCIAL_VIDEO,
            media_type=MediaType.SHORT_VIDEO,
            source_platform=SourcePlatform.TIKTOK,
            resolver_key=self.key,
            metadata={
                "resolver_version": "v1",
                "provider": "yt-dlp",
                "extraction_mode": "deferred_connector",
                "resolution_mode": "queued_worker",
                "source_url": context.normalized_url,
            },
        )
        log_event(
            logger,
            logging.INFO,
            "resolver.completed",
            "TikTok resolver completed",
            source_platform=SourcePlatform.TIKTOK.value,
            resolver_key=self.key,
            media_type=MediaType.SHORT_VIDEO.value,
            fallback_strategy="queued_worker",
        )
        return resolved


class SocialVideoResolver(ContentResolverPort):
    @property
    def key(self) -> str:
        return "social.default"

    async def resolve(self, context: ResolveContext) -> ResolvedMedia:
        resolved = ResolvedMedia(
            media_key=context.media_key,
            normalized_url=context.normalized_url,
            media_family=MediaFamily.SOCIAL_VIDEO,
            media_type=MediaType.SHORT_VIDEO,
            source_platform=context.classification.source_platform,
            resolver_key=self.key,
            metadata={
                "resolver_version": "v1",
                "audio_extraction_mode": "deferred",
                "provider": "yt-dlp",
            },
        )
        log_event(
            logger,
            logging.INFO,
            "resolver.completed",
            "Social resolver completed",
            source_platform=context.classification.source_platform.value,
            resolver_key=self.key,
            media_type=MediaType.SHORT_VIDEO.value,
            fallback_strategy="deferred",
        )
        return resolved


class AudioResolver(ContentResolverPort):
    @property
    def key(self) -> str:
        return "audio.default"

    async def resolve(self, context: ResolveContext) -> ResolvedMedia:
        resolved = ResolvedMedia(
            media_key=context.media_key,
            normalized_url=context.normalized_url,
            media_family=MediaFamily.AUDIO,
            media_type=MediaType.AUDIO_FILE,
            source_platform=SourcePlatform.DIRECT_URL,
            resolver_key=self.key,
            audio_url=context.normalized_url,
            metadata={
                "resolver_version": "v1",
                "audio_url_available": True,
                "resolution_mode": "direct_audio",
            },
        )
        log_event(
            logger,
            logging.INFO,
            "resolver.completed",
            "Direct audio resolver completed",
            source_platform=SourcePlatform.DIRECT_URL.value,
            resolver_key=self.key,
            media_type=MediaType.AUDIO_FILE.value,
            fallback_strategy="direct_audio",
        )
        return resolved
