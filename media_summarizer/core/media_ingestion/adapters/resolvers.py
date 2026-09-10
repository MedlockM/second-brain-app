"""Default resolver adapters for media ingestion."""

from __future__ import annotations

import logging
from typing import Final, Optional
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
from media_summarizer.core.media_ingestion.errors import (
    UnsupportedUrlError,
)
from media_summarizer.core.media_ingestion.media_metadata import (
    youtube_thumbnail_url,
    youtube_video_id,
)
from media_summarizer.core.media_ingestion.ports import ContentResolverPort
from media_summarizer.core.media_ingestion.title_derivation import select_title
from media_summarizer.core.ports.article_content import (
    ArticleContentFetcherPort,
    ArticleFetchError,
)
from media_summarizer.core.services.media_identity import (
    article_content_fingerprint,
    generate_article_media_key,
)
from media_summarizer.utils.language_codes import normalize_language_code
from media_summarizer.utils.logging_config import log_event

logger = logging.getLogger(__name__)

_SUPPORTED_PODCAST_PLATFORMS: Final[set[SourcePlatform]] = {
    SourcePlatform.SPOTIFY,
    SourcePlatform.APPLE_PODCASTS,
    SourcePlatform.DEEZER,
    SourcePlatform.RSS,
}


def _url_file_name(normalized_url: str) -> Optional[str]:
    """Last path segment of a URL, when there is one."""
    path = urlsplit((normalized_url or "").strip()).path or ""
    segments = [segment for segment in path.split("/") if segment]
    return segments[-1] if segments else None


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
    """Reads the page, then decides what media it is (task-392).

    The only resolver that inverts the pipeline's usual order, and it has to: a
    web page can be rewritten, so its content identity cannot be its URL. The text
    is fetched here, before `ProcessingJobSubmissionOrchestrator` writes anything,
    and its fingerprint goes into `media_key` -- which is what makes a rewritten
    article a *different* media, with its own transcript and its own artifacts,
    while an unchanged one keeps being shared between accounts.

    Cost accepted by the owner: this is a scrape, not a model call. The budget is
    the API's 30 s ceiling, so the reader is built with a shorter timeout than the
    worker's (`build_api_article_content_fetcher`).

    A page that cannot be read does not raise. The submission goes through with
    the URL-derived identity and the failure code in its metadata, so the reader
    gets the same failed library tile -- in their own language, with the same
    "request support for this source" action -- as when this ran in a worker.
    """

    def __init__(
        self,
        *,
        content_fetcher: Optional[ArticleContentFetcherPort] = None,
    ) -> None:
        self._content_fetcher = content_fetcher

    @property
    def key(self) -> str:
        return "article.default"

    def _fetcher(self) -> ArticleContentFetcherPort:
        """The reader, built on first use.

        Lazily, because the adapter imports `trafilatura` (and therefore `lxml`):
        an API cold start that never touches an article must not pay for it.
        """
        if self._content_fetcher is None:
            from media_summarizer.infrastructure.resolvers.trafilatura_article_resolver import (  # noqa: E501
                build_api_article_content_fetcher,
            )

            self._content_fetcher = build_api_article_content_fetcher()
        return self._content_fetcher

    async def resolve(self, context: ResolveContext) -> ResolvedMedia:
        try:
            article = await self._fetcher().fetch(context.normalized_url)
        except ArticleFetchError as exc:
            return self._unreadable_page(context=context, error=exc)

        content_fingerprint = article_content_fingerprint(article.text)
        media_key = generate_article_media_key(
            canonical_url=context.normalized_url,
            content_fingerprint=content_fingerprint,
        )
        resolved = ResolvedMedia(
            media_key=media_key,
            normalized_url=context.normalized_url,
            media_family=MediaFamily.ARTICLE,
            media_type=MediaType.ARTICLE,
            source_platform=SourcePlatform.WEB,
            resolver_key=self.key,
            title=article.title,
            creator_name=article.creator_name,
            cover_url=article.cover_url,
            raw_text=article.text,
            metadata={
                "resolver_version": "v2",
                "extraction_mode": "inline_fetch",
                "source_url": context.normalized_url,
                "content_fingerprint": content_fingerprint,
                "url_media_key": context.media_key,
                "extraction_metadata": article.extraction_metadata(),
                "transcript_provider": article.provider,
                "transcript_extractor": article.extractor,
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
            fallback_strategy="inline_fetch",
            media_key=media_key,
            content_fingerprint=content_fingerprint,
            char_count=article.char_count,
        )
        return resolved

    def _unreadable_page(
        self,
        *,
        context: ResolveContext,
        error: ArticleFetchError,
    ) -> ResolvedMedia:
        """A page we could not read: submitted anyway, with the reason attached.

        The URL-derived key is the only identity available -- there is no text to
        fingerprint -- and it is the right one: nothing was stored under it, so the
        first save that *does* read the page settles the real identity.
        """
        log_event(
            logger,
            logging.WARNING,
            "resolver.failed",
            "Article resolver could not read the page",
            source_platform=SourcePlatform.WEB.value,
            resolver_key=self.key,
            media_type=MediaType.ARTICLE.value,
            error_code=error.media_failure_code.value,
            detail=error.details,
            retryable=error.retryable,
        )
        return ResolvedMedia(
            media_key=context.media_key,
            normalized_url=context.normalized_url,
            media_family=MediaFamily.ARTICLE,
            media_type=MediaType.ARTICLE,
            source_platform=SourcePlatform.WEB,
            resolver_key=self.key,
            metadata={
                "resolver_version": "v2",
                "extraction_mode": "inline_fetch",
                "source_url": context.normalized_url,
                "article_fetch_error_code": error.code.value,
                "article_failure_code": error.media_failure_code.value,
                "article_fetch_retryable": error.retryable,
                "article_fetch_error_metadata": error.error_metadata(
                    step="article_extraction"
                ),
            },
        )


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
        metadata = {
            "resolver_version": "v2",
            "extraction_mode": "queued_worker",
            "transcript_strategy": "manual_auto_audio",
            "source_url": context.normalized_url,
        }
        requested_transcript_language = normalize_language_code(
            context.command.request.transcript_language
        )
        if requested_transcript_language:
            metadata["requested_transcript_language"] = requested_transcript_language

        resolved = ResolvedMedia(
            media_key=context.media_key,
            normalized_url=context.normalized_url,
            media_family=MediaFamily.YOUTUBE,
            media_type=MediaType.YOUTUBE_VIDEO,
            source_platform=SourcePlatform.YOUTUBE,
            resolver_key=self.key,
            # The cover is the one source of metadata this deferred resolver can
            # produce without calling anything: `i.ytimg.com` is addressed by the
            # video id, which is in the URL. Emitting it here is what puts the
            # image on the library row at submission time instead of at the end
            # of the transcript run, minutes later (task-353).
            cover_url=youtube_thumbnail_url(youtube_video_id(context.normalized_url)),
            metadata=metadata,
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
    """Deferred Instagram resolver: classifies, never calls a provider.

    Instagram resolution needs yt-dlp and, when the Lambda egress IP is blocked,
    an Apify actor run that takes 63-100 s (measured 2026-08-17). The API has a
    hard 30 s ceiling it cannot raise -- API Gateway's HTTP API integration
    timeout is not configurable -- so resolving here could only ever time the
    request out, discard a billed actor run, and leave nothing persisted
    (task-274). The provider call belongs to ``instagram_ingestion_worker``,
    which the orchestrator reaches through the queue.
    """

    @property
    def key(self) -> str:
        return "instagram.default"

    async def resolve(self, context: ResolveContext) -> ResolvedMedia:
        resolved = ResolvedMedia(
            media_key=context.media_key,
            normalized_url=context.normalized_url,
            media_family=MediaFamily.SOCIAL_VIDEO,
            media_type=MediaType.SHORT_VIDEO,
            source_platform=SourcePlatform.INSTAGRAM,
            resolver_key=self.key,
            metadata={
                "resolver_version": "v5",
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
            "Instagram resolver completed",
            source_platform=SourcePlatform.INSTAGRAM.value,
            resolver_key=self.key,
            media_type=MediaType.SHORT_VIDEO.value,
            fallback_strategy="queued_worker",
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
            # A direct audio link exposes exactly one piece of metadata: the file
            # name in its path. Cleaned and rejected like any other filename
            # (task-266) -- `/podcasts/the-daily-2026-08-17.mp3` is a title,
            # `/media/a3f9c1d4e8b27f60.mp3` is not and falls to the label.
            title=select_title(
                [],
                file_name_candidates=[_url_file_name(context.normalized_url)],
            ),
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
