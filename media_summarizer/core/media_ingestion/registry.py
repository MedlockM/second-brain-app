"""Resolver registry used as the single extension point for ingestion routing."""

from __future__ import annotations

from typing import Dict, Iterable, List

from media_summarizer.core.media_ingestion.errors import (
    ResolverNotFoundError,
    ResolverRegistrationError,
)
from media_summarizer.core.media_ingestion.ports import ContentResolverPort


class ResolverRegistry:
    """
    Central resolver registry.

    New media resolvers are added by registering a new resolver key. The use-case
    does not change when adding a new resolver.
    """

    def __init__(self) -> None:
        self._resolvers: Dict[str, ContentResolverPort] = {}

    def register(self, resolver: ContentResolverPort) -> None:
        key = (resolver.key or "").strip()
        if not key:
            raise ResolverRegistrationError("Resolver key must be a non-empty string.")
        if key in self._resolvers:
            raise ResolverRegistrationError(
                f"Resolver key '{key}' is already registered."
            )
        self._resolvers[key] = resolver

    def register_many(self, resolvers: Iterable[ContentResolverPort]) -> None:
        for resolver in resolvers:
            self.register(resolver)

    def get(self, resolver_key: str) -> ContentResolverPort:
        key = (resolver_key or "").strip()
        resolver = self._resolvers.get(key)
        if resolver is None:
            raise ResolverNotFoundError(
                f"No resolver registered for key '{key}'. "
                "Register a resolver in ResolverRegistry."
            )
        return resolver

    def keys(self) -> List[str]:
        return sorted(self._resolvers.keys())
