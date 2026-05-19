"""Errors for the media ingestion core."""

from __future__ import annotations

DEFAULT_INVALID_URL_MESSAGE = (
    "Invalid URL. Provide a full http(s) URL with a valid host."
)
DEFAULT_UNSUPPORTED_URL_MESSAGE = (
    "Unsupported URL. Supported media families: "
    "podcast, article, youtube, social_video, audio."
)
DEFAULT_INSTAGRAM_PROVIDER_BAD_REQUEST_MESSAGE = (
    "Unable to resolve transcribable media from this Instagram URL."
)
DEFAULT_INSTAGRAM_PROVIDER_TEMPORARY_MESSAGE = (
    "Instagram media resolution is temporarily unavailable."
)


class MediaIngestionError(Exception):
    """Base error for ingestion core failures."""


class ClassificationError(MediaIngestionError):
    """Raised when URL classification cannot produce a deterministic result."""


class InvalidUrlError(ClassificationError):
    """Raised when the provided URL cannot be parsed as a valid absolute URL."""


class UnsupportedUrlError(ClassificationError):
    """Raised when the URL is valid but unsupported by ingestion routing policy."""


class ResolverRegistrationError(MediaIngestionError):
    """Raised when resolver registration in the registry is invalid."""


class ResolverNotFoundError(MediaIngestionError):
    """Raised when no resolver exists for a classified resolver key."""


class ResolutionError(MediaIngestionError):
    """Raised when a resolver fails to produce a normalized media payload."""


class NonRetryableProviderResolutionError(ResolutionError):
    """Raised when a provider rejects or cannot resolve the requested content."""


class RetryableProviderResolutionError(ResolutionError):
    """Raised when a provider error may succeed on retry."""


class OrchestrationError(MediaIngestionError):
    """Raised when submission orchestration fails."""
