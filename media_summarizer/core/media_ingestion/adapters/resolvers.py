"""Default resolver adapters for media ingestion."""

from __future__ import annotations

import logging
from typing import Any, Final
from urllib.parse import urlsplit

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
from media_summarizer.core.media_ingestion.errors import UnsupportedUrlError
from media_summarizer.core.media_ingestion.ports import ContentResolverPort
from media_summarizer.utils.logging_config import log_event

logger = logging.getLogger(__name__)

_SUPPORTED_PODCAST_PLATFORMS: Final[set[SourcePlatform]] = {
    SourcePlatform.SPOTIFY,
    SourcePlatform.APPLE_PODCASTS,
    SourcePlatform.DEEZER,
    SourcePlatform.RSS,
}


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
