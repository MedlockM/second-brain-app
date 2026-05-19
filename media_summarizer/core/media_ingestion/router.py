"""Central URL-to-resolver routing for media ingestion."""

from __future__ import annotations

from dataclasses import dataclass

from media_summarizer.core.media_ingestion.domain import ClassifiedUrl
from media_summarizer.core.media_ingestion.ports import (
    ContentResolverPort,
    UrlClassifierPort,
)
from media_summarizer.core.media_ingestion.registry import ResolverRegistry


@dataclass(frozen=True)
class ResolverRoute:
    classification: ClassifiedUrl
    resolver: ContentResolverPort


class ResolverRouter:
    """Encapsulates classification and resolver lookup as one reusable decision."""

    def __init__(
        self,
        *,
        classifier: UrlClassifierPort,
        resolver_registry: ResolverRegistry,
    ) -> None:
        self._classifier = classifier
        self._resolver_registry = resolver_registry

    def route(self, normalized_url: str) -> ResolverRoute:
        classification = self._classifier.classify(normalized_url)
        resolver = self._resolver_registry.get(classification.resolver_key)
        return ResolverRoute(classification=classification, resolver=resolver)
