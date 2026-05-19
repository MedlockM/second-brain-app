"""Hexagonal ports for media ingestion."""

from __future__ import annotations

from abc import ABC, abstractmethod

from media_summarizer.core.media_ingestion.domain import (
    ClassifiedUrl,
    IngestionOutcome,
    IngestSharedContentCommand,
    IngestUrlCommand,
    ResolveContext,
    ResolvedMedia,
)


class UrlClassifierPort(ABC):
    """Classifies canonical URLs into a resolver key and media family."""

    @abstractmethod
    def classify(self, normalized_url: str) -> ClassifiedUrl:
        raise NotImplementedError


class ContentResolverPort(ABC):
    """Resolves classified URLs into normalized media payload."""

    @property
    @abstractmethod
    def key(self) -> str:
        raise NotImplementedError

    @abstractmethod
    async def resolve(self, context: ResolveContext) -> ResolvedMedia:
        raise NotImplementedError


class SubmissionOrchestratorPort(ABC):
    """Orchestrates persistence and pipeline submission from resolved media."""

    @abstractmethod
    async def submit(
        self,
        *,
        command: IngestUrlCommand | IngestSharedContentCommand,
        resolved: ResolvedMedia,
    ) -> IngestionOutcome:
        raise NotImplementedError
