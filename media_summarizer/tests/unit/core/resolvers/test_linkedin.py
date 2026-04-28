"""
Unit tests for the LinkedIn resolver.

Tests URL detection, validation, content resolution, and error handling.
"""

import pytest

from media_summarizer.core.resolvers.linkedin import (
    LinkedInResolver,
    LinkedInResolverError,
    LinkedInUrl,
    is_linkedin_url,
    validate_linkedin_url,
)


# ---------------------------------------------------------------------------
# is_linkedin_url() tests
# ---------------------------------------------------------------------------


class TestIsLinkedInUrl:
    """Tests for the is_linkedin_url detection function."""

    def test_feed_update_url(self):
        url = "https://www.linkedin.com/feed/update/urn:li:activity:7123456789012345678"
        assert is_linkedin_url(url) is True

    def test_feed_update_url_without_www(self):
        url = "https://linkedin.com/feed/update/urn:li:activity:7123456789012345678"
        assert is_linkedin_url(url) is True

    def test_posts_url(self):
        url = "https://www.linkedin.com/posts/john-doe-12345678-some-title-activity-7123456789"
        assert is_linkedin_url(url) is True

    def test_posts_url_without_www(self):
        url = "https://linkedin.com/posts/john-doe-12345678"
        assert is_linkedin_url(url) is True

    def test_ugc_post_url(self):
        url = "https://www.linkedin.com/feed/update/urn:li:ugcPost:7123456789012345678"
        assert is_linkedin_url(url) is True

    def test_http_url(self):
        url = "http://linkedin.com/feed/update/urn:li:activity:7123456789012345678"
        assert is_linkedin_url(url) is True

    def test_with_query_params(self):
        url = "https://www.linkedin.com/feed/update/urn:li:activity:7123456789?utm_source=share"
        assert is_linkedin_url(url) is True

    def test_youtube_url(self):
        url = "https://www.youtube.com/watch?v=abc123"
        assert is_linkedin_url(url) is False

    def test_linkedin_profile_url(self):
        """LinkedIn profile URLs should NOT match (not a post)."""
        url = "https://www.linkedin.com/in/john-doe"
        assert is_linkedin_url(url) is False

    def test_linkedin_company_url(self):
        """LinkedIn company pages should NOT match."""
        url = "https://www.linkedin.com/company/anthropic"
        assert is_linkedin_url(url) is False

    def test_linkedin_jobs_url(self):
        """LinkedIn job listings should NOT match."""
        url = "https://www.linkedin.com/jobs/view/12345"
        assert is_linkedin_url(url) is False

    def test_empty_string(self):
        assert is_linkedin_url("") is False

    def test_none(self):
        assert is_linkedin_url(None) is False

    def test_not_a_url(self):
        assert is_linkedin_url("not a url at all") is False


# ---------------------------------------------------------------------------
# validate_linkedin_url() tests
# ---------------------------------------------------------------------------


class TestValidateLinkedInUrl:
    """Tests for URL validation and normalization."""

    def test_valid_feed_update_url(self):
        url = "https://www.linkedin.com/feed/update/urn:li:activity:7123456789012345678"
        result = validate_linkedin_url(url)
        assert isinstance(result, LinkedInUrl)
        assert result.url_type == "feed_update"
        assert result.post_identifier == "7123456789012345678"
        assert result.normalized_url == "https://www.linkedin.com/feed/update/urn:li:activity:7123456789012345678"

    def test_valid_posts_url(self):
        url = "https://www.linkedin.com/posts/john-doe-12345678-title-slug"
        result = validate_linkedin_url(url)
        assert isinstance(result, LinkedInUrl)
        assert result.url_type == "posts"
        assert result.post_identifier == "john-doe-12345678-title-slug"

    def test_strips_query_params_in_normalized(self):
        url = "https://www.linkedin.com/feed/update/urn:li:activity:7123456789?utm_source=share&utm_medium=member_desktop"
        result = validate_linkedin_url(url)
        # normalized_url should use the path only (no query params)
        assert "utm_source" not in result.normalized_url

    def test_strips_whitespace(self):
        url = "  https://www.linkedin.com/feed/update/urn:li:activity:7123456789  "
        result = validate_linkedin_url(url)
        assert result.original_url == url.strip()

    def test_invalid_empty_url(self):
        with pytest.raises(ValueError) as exc_info:
            validate_linkedin_url("")
        assert LinkedInResolverError.INVALID_URL.value in str(exc_info.value)

    def test_invalid_none_url(self):
        with pytest.raises(ValueError) as exc_info:
            validate_linkedin_url(None)
        assert LinkedInResolverError.INVALID_URL.value in str(exc_info.value)

    def test_invalid_non_linkedin_host(self):
        with pytest.raises(ValueError) as exc_info:
            validate_linkedin_url("https://www.youtube.com/watch?v=abc")
        assert LinkedInResolverError.INVALID_URL.value in str(exc_info.value)

    def test_unsupported_linkedin_path(self):
        with pytest.raises(ValueError) as exc_info:
            validate_linkedin_url("https://www.linkedin.com/in/john-doe")
        assert LinkedInResolverError.UNSUPPORTED_URL_FORMAT.value in str(exc_info.value)


# ---------------------------------------------------------------------------
# LinkedInResolver tests
# ---------------------------------------------------------------------------


class TestLinkedInResolver:
    """Tests for the LinkedInResolver class."""

    def setup_method(self):
        self.resolver = LinkedInResolver()

    def test_resolve_from_paste_success(self):
        url = "https://www.linkedin.com/feed/update/urn:li:activity:7123456789012345678"
        text = "This is a LinkedIn post about AI and machine learning. It has enough content to be valid."
        result = self.resolver.resolve_from_paste(url=url, pasted_text=text)

        assert result.text == text
        assert result.source_platform == "linkedin"
        assert result.content_hash  # non-empty hash
        assert result.url.url_type == "feed_update"

    def test_resolve_from_paste_with_author(self):
        url = "https://www.linkedin.com/posts/john-doe-12345678-title"
        text = "This is a thoughtful post about technology and its impact on society."
        result = self.resolver.resolve_from_paste(
            url=url, pasted_text=text, author="John Doe"
        )

        assert result.author == "John Doe"
        assert result.source_platform == "linkedin"

    def test_resolve_from_paste_empty_text(self):
        url = "https://www.linkedin.com/feed/update/urn:li:activity:7123456789012345678"
        with pytest.raises(ValueError) as exc_info:
            self.resolver.resolve_from_paste(url=url, pasted_text="")
        assert LinkedInResolverError.EMPTY_CONTENT.value in str(exc_info.value)

    def test_resolve_from_paste_text_too_short(self):
        url = "https://www.linkedin.com/feed/update/urn:li:activity:7123456789012345678"
        with pytest.raises(ValueError) as exc_info:
            self.resolver.resolve_from_paste(url=url, pasted_text="Too short")
        assert LinkedInResolverError.CONTENT_TOO_SHORT.value in str(exc_info.value)

    def test_resolve_from_paste_invalid_url(self):
        with pytest.raises(ValueError) as exc_info:
            self.resolver.resolve_from_paste(
                url="https://youtube.com/watch?v=abc",
                pasted_text="This is valid content that should be long enough.",
            )
        assert LinkedInResolverError.INVALID_URL.value in str(exc_info.value)

    def test_content_hash_is_deterministic(self):
        url = "https://www.linkedin.com/posts/john-doe-12345678-title"
        text = "Same content produces same hash for deduplication purposes."

        result1 = self.resolver.resolve_from_paste(url=url, pasted_text=text)
        result2 = self.resolver.resolve_from_paste(url=url, pasted_text=text)
        assert result1.content_hash == result2.content_hash

    def test_content_hash_normalizes_whitespace(self):
        """Different whitespace formatting should produce the same hash."""
        url = "https://www.linkedin.com/posts/john-doe-12345678-title"
        text1 = "This is   some   content   with   extra   spaces."
        text2 = "This is some content with extra spaces."

        result1 = self.resolver.resolve_from_paste(url=url, pasted_text=text1)
        result2 = self.resolver.resolve_from_paste(url=url, pasted_text=text2)
        assert result1.content_hash == result2.content_hash

    def test_generate_media_key(self):
        url = "https://www.linkedin.com/posts/john-doe-12345678-title"
        text = "A long enough post about interesting topics in technology."
        content = self.resolver.resolve_from_paste(url=url, pasted_text=text)
        media_key = self.resolver.generate_media_key(content)

        assert media_key.startswith("linkedin:")
        assert len(media_key) > len("linkedin:")


# ---------------------------------------------------------------------------
# _detect_platform integration (media.py)
# These tests import the full endpoint module which has heavy dependencies.
# They are skipped if transitive imports are unavailable (e.g., CI isolation).
# ---------------------------------------------------------------------------

try:
    from media_summarizer.api.endpoints.media import _detect_platform
    _MEDIA_IMPORT_AVAILABLE = True
except (ImportError, ModuleNotFoundError):
    _MEDIA_IMPORT_AVAILABLE = False


@pytest.mark.skipif(
    not _MEDIA_IMPORT_AVAILABLE,
    reason="media_summarizer.api.endpoints.media not importable (missing transitive deps)",
)
class TestDetectPlatformLinkedIn:
    """Tests for LinkedIn detection in the _detect_platform function."""

    def test_linkedin_feed_update_detected(self):
        platform, key = _detect_platform(
            "https://www.linkedin.com/feed/update/urn:li:activity:7123456789"
        )
        assert platform == "linkedin"
        assert key == "linkedin"

    def test_linkedin_posts_detected(self):
        platform, key = _detect_platform(
            "https://www.linkedin.com/posts/john-doe-title-12345"
        )
        assert platform == "linkedin"
        assert key == "linkedin"

    def test_linkedin_profile_not_detected_as_linkedin(self):
        platform, key = _detect_platform("https://www.linkedin.com/in/john-doe")
        # Profile URLs should fall through to "web" since they are not posts
        assert platform == "web"
        assert key == "article"

    def test_linkedin_company_not_detected_as_linkedin(self):
        platform, key = _detect_platform(
            "https://www.linkedin.com/company/anthropic"
        )
        assert platform == "web"
        assert key == "article"
