"""
LinkedIn post resolver for the media ingestion pipeline.

V1 approach: Manual paste fallback (copy-paste UX).
LinkedIn ToS Section 8.2 prohibits automated scraping, so V1 uses a
compliant approach where users manually paste post text.

This resolver provides:
- URL detection and validation for linkedin.com/feed/update/ and linkedin.com/posts/
- Normalized URL extraction
- Error handling with stable enum codes
- Content acceptance for the manual paste flow

Future phases may add best-effort HTTP extraction with graceful degradation.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from enum import Enum
from typing import Optional
from urllib.parse import urlsplit


# ---------------------------------------------------------------------------
# Error enum (stable codes for client consumption)
# ---------------------------------------------------------------------------


class LinkedInResolverError(str, Enum):
    """Stable error codes for LinkedIn resolution failures."""

    INVALID_URL = "linkedin_invalid_url"
    PRIVATE_POST = "linkedin_private_post"
    LOGIN_WALL = "linkedin_login_wall"
    STRUCTURE_CHANGED = "linkedin_structure_changed"
    EMPTY_CONTENT = "linkedin_empty_content"
    CONTENT_TOO_SHORT = "linkedin_content_too_short"
    UNSUPPORTED_URL_FORMAT = "linkedin_unsupported_url_format"


# ---------------------------------------------------------------------------
# URL patterns
# ---------------------------------------------------------------------------

# Pattern: linkedin.com/feed/update/urn:li:activity:1234567890
_FEED_UPDATE_PATTERN = re.compile(
    r"^https?://(?:www\.)?linkedin\.com/feed/update/urn:li:(?:activity|ugcPost):\d+",
    re.IGNORECASE,
)

# Pattern: linkedin.com/posts/username-slug-1234567890-XXXX
_POSTS_PATTERN = re.compile(
    r"^https?://(?:www\.)?linkedin\.com/posts/[\w\-]+",
    re.IGNORECASE,
)

# LinkedIn host detection
_LINKEDIN_HOSTS = {"linkedin.com", "www.linkedin.com"}

# Minimum content length to consider valid (characters)
_MIN_CONTENT_LENGTH = 20


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class LinkedInUrl:
    """Validated and normalized LinkedIn post URL."""

    original_url: str
    normalized_url: str
    url_type: str  # "feed_update" or "posts"
    post_identifier: str  # extracted identifier from URL


@dataclass(frozen=True)
class LinkedInContent:
    """Resolved LinkedIn post content."""

    url: LinkedInUrl
    text: str
    content_hash: str  # SHA-256 of normalized text, used as media_key
    author: Optional[str] = None
    source_platform: str = "linkedin"


# ---------------------------------------------------------------------------
# URL validation and detection
# ---------------------------------------------------------------------------


def is_linkedin_url(url: str) -> bool:
    """Check if a URL is a LinkedIn post URL (feed/update or /posts/ format).

    Args:
        url: URL string to check.

    Returns:
        True if the URL matches a known LinkedIn post pattern.
    """
    if not url or not isinstance(url, str):
        return False

    try:
        split = urlsplit(url.strip())
        host = (split.netloc or "").lower().removeprefix("www.")
    except (ValueError, AttributeError):
        return False

    if host not in ("linkedin.com",):
        return False

    path = (split.path or "").lower()
    return (
        "/feed/update/" in path
        or path.startswith("/posts/")
    )


def validate_linkedin_url(url: str) -> LinkedInUrl:
    """Validate and normalize a LinkedIn post URL.

    Args:
        url: Raw URL string from user input.

    Returns:
        LinkedInUrl with normalized data.

    Raises:
        ValueError: If URL is not a valid LinkedIn post URL.
            The error message includes the LinkedInResolverError code.
    """
    if not url or not isinstance(url, str):
        raise ValueError(
            f"{LinkedInResolverError.INVALID_URL.value}: URL is required"
        )

    url = url.strip()

    # Remove tracking parameters by keeping only the path
    try:
        split = urlsplit(url)
        host = (split.netloc or "").lower()
    except (ValueError, AttributeError):
        raise ValueError(
            f"{LinkedInResolverError.INVALID_URL.value}: Cannot parse URL"
        )

    # Validate host
    clean_host = host.removeprefix("www.")
    if clean_host != "linkedin.com":
        raise ValueError(
            f"{LinkedInResolverError.INVALID_URL.value}: Not a LinkedIn URL"
        )

    path = split.path or ""

    # Detect URL type and extract identifier
    if _FEED_UPDATE_PATTERN.match(url):
        url_type = "feed_update"
        # Extract the URN identifier
        urn_match = re.search(r"urn:li:(?:activity|ugcPost):(\d+)", url)
        post_identifier = urn_match.group(1) if urn_match else path
        # Normalize: strip query params and fragments
        normalized = f"https://www.linkedin.com{path}"
    elif _POSTS_PATTERN.match(url):
        url_type = "posts"
        # Extract the slug
        slug_match = re.match(r"/posts/([\w\-]+)", path)
        post_identifier = slug_match.group(1) if slug_match else path
        # Normalize: strip query params and fragments
        normalized = f"https://www.linkedin.com{path}"
    else:
        raise ValueError(
            f"{LinkedInResolverError.UNSUPPORTED_URL_FORMAT.value}: "
            f"URL must match linkedin.com/feed/update/ or linkedin.com/posts/ patterns"
        )

    return LinkedInUrl(
        original_url=url,
        normalized_url=normalized,
        url_type=url_type,
        post_identifier=post_identifier,
    )


# ---------------------------------------------------------------------------
# Content resolution
# ---------------------------------------------------------------------------


def _compute_content_hash(text: str) -> str:
    """Compute a stable SHA-256 hash for deduplication.

    Normalizes whitespace before hashing to avoid duplicate entries
    for the same content with different formatting.
    """
    normalized = " ".join(text.split()).strip().lower()
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


class LinkedInResolver:
    """LinkedIn post content resolver.

    V1 implementation uses manual paste approach (user copies text from LinkedIn).
    The resolver validates the URL and accepts pasted content, generating a
    stable media_key from the content hash for deduplication.

    Future phases may attempt best-effort HTTP extraction before falling back
    to manual paste.
    """

    def resolve_from_paste(
        self,
        url: str,
        pasted_text: str,
        author: Optional[str] = None,
    ) -> LinkedInContent:
        """Resolve LinkedIn post content from user-pasted text.

        This is the V1 approach: user copies post text from LinkedIn and
        pastes it into the application.

        Args:
            url: LinkedIn post URL (for reference and deduplication).
            pasted_text: Text content pasted by the user.
            author: Optional author name provided by the user.

        Returns:
            LinkedInContent with validated text and media_key hash.

        Raises:
            ValueError: If URL is invalid or content is empty/too short.
        """
        # Validate URL
        linkedin_url = validate_linkedin_url(url)

        # Validate content
        if not pasted_text or not isinstance(pasted_text, str):
            raise ValueError(
                f"{LinkedInResolverError.EMPTY_CONTENT.value}: "
                f"Post text content is required"
            )

        text = pasted_text.strip()
        if len(text) < _MIN_CONTENT_LENGTH:
            raise ValueError(
                f"{LinkedInResolverError.CONTENT_TOO_SHORT.value}: "
                f"Post text must be at least {_MIN_CONTENT_LENGTH} characters"
            )

        content_hash = _compute_content_hash(text)

        return LinkedInContent(
            url=linkedin_url,
            text=text,
            content_hash=content_hash,
            author=author,
            source_platform="linkedin",
        )

    def generate_media_key(self, content: LinkedInContent) -> str:
        """Generate a stable media_key for deduplication.

        Uses the content hash prefixed with 'linkedin:' to ensure
        global uniqueness across source platforms.
        """
        return f"linkedin:{content.content_hash}"
