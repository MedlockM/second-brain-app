"""Default adapters for the media ingestion core."""

from .classifiers import RuleBasedUrlClassifier
from .orchestrators import ProcessingJobSubmissionOrchestrator
from .podcast_resolver_foundation import (
    DEFAULT_PODCAST_RESOLUTION_FAILED_MESSAGE,
    DEFAULT_PODCAST_RESOLUTION_PENDING_MESSAGE,
    DeferredPodcastPlatformResolver,
    PodcastPlatformResolver,
    PodcastPlatformResolverRegistry,
    PodcastResolutionOutcome,
    PodcastResolutionStatus,
    PodcastResolverErrorCode,
    PodcastUrlDescriptor,
    build_deferred_podcast_platform_resolver_registry,
    build_podcast_resolution_metadata,
    build_raw_podcast_url_descriptor,
    normalize_podcast_source_url,
)
from .resolvers import (
    ArticleResolver,
    AudioResolver,
    InstagramResolver,
    PodcastResolver,
    SocialVideoResolver,
    TikTokResolver,
    XPostResolver,
    YouTubeResolver,
)

__all__ = [
    "ArticleResolver",
    "AudioResolver",
    "DEFAULT_PODCAST_RESOLUTION_FAILED_MESSAGE",
    "DEFAULT_PODCAST_RESOLUTION_PENDING_MESSAGE",
    "DeferredPodcastPlatformResolver",
    "InstagramResolver",
    "PodcastResolver",
    "PodcastPlatformResolver",
    "PodcastPlatformResolverRegistry",
    "PodcastResolutionOutcome",
    "PodcastResolutionStatus",
    "PodcastResolverErrorCode",
    "PodcastUrlDescriptor",
    "ProcessingJobSubmissionOrchestrator",
    "RuleBasedUrlClassifier",
    "SocialVideoResolver",
    "TikTokResolver",
    "XPostResolver",
    "YouTubeResolver",
    "build_deferred_podcast_platform_resolver_registry",
    "build_podcast_resolution_metadata",
    "build_raw_podcast_url_descriptor",
    "normalize_podcast_source_url",
]
