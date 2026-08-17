"""Wiring helpers for media ingestion core."""

from __future__ import annotations

from typing import Iterable, Optional

from media_summarizer.core.media_ingestion.adapters import (
    ArticleResolver,
    AudioResolver,
    InstagramResolver,
    PodcastResolver,
    ProcessingJobSubmissionOrchestrator,
    RuleBasedUrlClassifier,
    SocialVideoResolver,
    TikTokResolver,
    XPostResolver,
    YouTubeResolver,
)
from media_summarizer.core.media_ingestion.ports import (
    ContentResolverPort,
    SubmissionOrchestratorPort,
    UrlClassifierPort,
)
from media_summarizer.core.media_ingestion.registry import ResolverRegistry
from media_summarizer.core.media_ingestion.router import ResolverRouter
from media_summarizer.core.media_ingestion.use_cases import (
    IngestSharedContentUseCase,
    IngestUrlUseCase,
)


def build_default_resolver_registry(
    *,
    extra_resolvers: Optional[Iterable[ContentResolverPort]] = None,
) -> ResolverRegistry:
    registry = ResolverRegistry()
    registry.register_many(
        [
            PodcastResolver(),
            XPostResolver(),
            ArticleResolver(),
            YouTubeResolver(),
            InstagramResolver(),
            TikTokResolver(),
            SocialVideoResolver(),
            AudioResolver(),
        ]
    )
    if extra_resolvers:
        registry.register_many(extra_resolvers)
    return registry


def build_default_resolver_router(
    *,
    classifier: Optional[UrlClassifierPort] = None,
    resolver_registry: Optional[ResolverRegistry] = None,
    extra_resolvers: Optional[Iterable[ContentResolverPort]] = None,
) -> ResolverRouter:
    return ResolverRouter(
        classifier=classifier or RuleBasedUrlClassifier(),
        resolver_registry=resolver_registry
        or build_default_resolver_registry(extra_resolvers=extra_resolvers),
    )


def build_default_ingest_url_use_case(
    *,
    router: Optional[ResolverRouter] = None,
    classifier: Optional[UrlClassifierPort] = None,
    resolver_registry: Optional[ResolverRegistry] = None,
    orchestrator: Optional[SubmissionOrchestratorPort] = None,
    extra_resolvers: Optional[Iterable[ContentResolverPort]] = None,
) -> IngestUrlUseCase:
    return IngestUrlUseCase(
        router=router
        or build_default_resolver_router(
            classifier=classifier,
            resolver_registry=resolver_registry,
            extra_resolvers=extra_resolvers
        ),
        orchestrator=orchestrator or ProcessingJobSubmissionOrchestrator(),
    )


def build_default_ingest_shared_content_use_case(
    *,
    orchestrator: Optional[SubmissionOrchestratorPort] = None,
) -> IngestSharedContentUseCase:
    return IngestSharedContentUseCase(
        orchestrator=orchestrator or ProcessingJobSubmissionOrchestrator(),
    )
