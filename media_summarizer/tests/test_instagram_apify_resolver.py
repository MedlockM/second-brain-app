"""
Unit tests for the Instagram Apify resolver.

Covers:
- Reel resolution (video URL extraction via Reel Scraper)
- Video post resolution (video URL via Post Scraper)
- Single image post resolution (image URLs via Post Scraper)
- Carousel post resolution (multiple image URLs via Post Scraper)
- Caption extraction for all content types
- Comment extraction via Comment Scraper
- Error handling (auth, timeout, no results)
"""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from media_summarizer.core.media_ingestion.domain import (
    ClassifiedUrl,
    IngestUrlCommand,
    IngestUrlRequest,
    MediaFamily,
    MediaType,
    ResolveContext,
    SourcePlatform,
    UserContext,
)
from media_summarizer.core.media_ingestion.errors import (
    NonRetryableProviderResolutionError,
    RetryableProviderResolutionError,
)
from media_summarizer.infrastructure.resolvers.instagram_apify_resolver import (
    InstagramApifyResolver,
    InstagramContentType,
    _detect_instagram_content_type,
    _extract_caption,
    _extract_comments,
    _extract_image_urls_from_post_result,
    _extract_video_url_from_post_result,
    _extract_video_url_from_reel_result,
)


def _make_context(url: str) -> ResolveContext:
    """Create a ResolveContext for testing."""
    return ResolveContext(
        command=IngestUrlCommand(
            user=UserContext(user_id="user-123", user_email="test@example.com"),
            request=IngestUrlRequest(url=url),
        ),
        normalized_url=url,
        media_key=f"ig:{url}",
        classification=ClassifiedUrl(
            media_family=MediaFamily.SOCIAL_VIDEO,
            source_platform=SourcePlatform.INSTAGRAM,
            resolver_key="instagram.default",
        ),
    )


# -- Content type detection tests --


class TestDetectInstagramContentType:
    def test_reel_url(self):
        result = _detect_instagram_content_type("https://www.instagram.com/reel/ABC123/")
        assert result == InstagramContentType.REEL

    def test_post_url(self):
        result = _detect_instagram_content_type("https://www.instagram.com/p/XYZ789/")
        assert result == InstagramContentType.POST

    def test_igtv_url(self):
        result = _detect_instagram_content_type("https://www.instagram.com/tv/DEF456/")
        assert result == InstagramContentType.IGTV

    def test_invalid_url_raises(self):
        with pytest.raises(NonRetryableProviderResolutionError):
            _detect_instagram_content_type("https://www.instagram.com/")

    def test_unsupported_path_raises(self):
        with pytest.raises(NonRetryableProviderResolutionError):
            _detect_instagram_content_type("https://www.instagram.com/explore/tags/test/")


# -- Video URL extraction tests --


class TestExtractVideoUrlFromReel:
    def test_prefers_downloaded_video(self):
        item = {
            "downloadedVideo": "https://apify-storage.s3.amazonaws.com/video.mp4",
            "videoUrl": "https://scontent.cdninstagram.com/v/video.mp4",
        }
        assert _extract_video_url_from_reel_result(item) == (
            "https://apify-storage.s3.amazonaws.com/video.mp4"
        )

    def test_falls_back_to_video_url(self):
        item = {"videoUrl": "https://scontent.cdninstagram.com/v/video.mp4"}
        assert _extract_video_url_from_reel_result(item) == (
            "https://scontent.cdninstagram.com/v/video.mp4"
        )

    def test_returns_none_when_no_video(self):
        assert _extract_video_url_from_reel_result({}) is None

    def test_ignores_non_http_values(self):
        item = {"downloadedVideo": "", "videoUrl": "not-a-url"}
        assert _extract_video_url_from_reel_result(item) is None


class TestExtractVideoUrlFromPost:
    def test_extracts_video_url(self):
        item = {"videoUrl": "https://cdn.instagram.com/video.mp4"}
        assert _extract_video_url_from_post_result(item) == (
            "https://cdn.instagram.com/video.mp4"
        )

    def test_returns_none_for_image_post(self):
        item = {"displayUrl": "https://cdn.instagram.com/image.jpg"}
        assert _extract_video_url_from_post_result(item) is None


# -- Image URL extraction tests --


class TestExtractImageUrls:
    def test_single_image_from_display_url(self):
        item = {"displayUrl": "https://cdn.instagram.com/image.jpg"}
        urls = _extract_image_urls_from_post_result(item)
        assert urls == ["https://cdn.instagram.com/image.jpg"]

    def test_carousel_from_child_posts(self):
        item = {
            "displayUrl": "https://cdn.instagram.com/cover.jpg",
            "childPosts": [
                {"displayUrl": "https://cdn.instagram.com/slide1.jpg"},
                {"displayUrl": "https://cdn.instagram.com/slide2.jpg"},
                {"displayUrl": "https://cdn.instagram.com/slide3.jpg"},
            ],
        }
        urls = _extract_image_urls_from_post_result(item)
        assert "https://cdn.instagram.com/cover.jpg" in urls
        assert "https://cdn.instagram.com/slide1.jpg" in urls
        assert "https://cdn.instagram.com/slide2.jpg" in urls
        assert "https://cdn.instagram.com/slide3.jpg" in urls
        assert len(urls) == 4

    def test_images_array(self):
        item = {
            "images": [
                "https://cdn.instagram.com/img1.jpg",
                "https://cdn.instagram.com/img2.jpg",
            ],
        }
        urls = _extract_image_urls_from_post_result(item)
        assert len(urls) == 2

    def test_deduplicates_urls(self):
        item = {
            "displayUrl": "https://cdn.instagram.com/same.jpg",
            "images": ["https://cdn.instagram.com/same.jpg"],
        }
        urls = _extract_image_urls_from_post_result(item)
        assert len(urls) == 1

    def test_empty_item_returns_empty_list(self):
        assert _extract_image_urls_from_post_result({}) == []


# -- Caption extraction tests --


class TestExtractCaption:
    def test_extracts_caption(self):
        item = {"caption": "This is a great post! #travel"}
        assert _extract_caption(item) == "This is a great post! #travel"

    def test_strips_whitespace(self):
        item = {"caption": "  hello world  "}
        assert _extract_caption(item) == "hello world"

    def test_returns_none_for_empty(self):
        assert _extract_caption({}) is None
        assert _extract_caption({"caption": ""}) is None
        assert _extract_caption({"caption": "   "}) is None


# -- Comment extraction tests --


class TestExtractComments:
    def test_extracts_comments(self):
        items = [
            {
                "text": "Great post!",
                "ownerUsername": "user1",
                "timestamp": "2026-01-01T00:00:00Z",
                "likesCount": 5,
                "repliesCount": 2,
            },
            {
                "text": "Love this!",
                "ownerUsername": "user2",
                "timestamp": "2026-01-02T00:00:00Z",
                "likesCount": 3,
                "repliesCount": 0,
            },
        ]
        comments = _extract_comments(items)
        assert len(comments) == 2
        assert comments[0]["text"] == "Great post!"
        assert comments[0]["owner_username"] == "user1"
        assert comments[1]["text"] == "Love this!"

    def test_skips_empty_comments(self):
        items = [
            {"text": "Valid comment"},
            {"text": ""},
            {"text": None},
            {},
        ]
        comments = _extract_comments(items)
        assert len(comments) == 1

    def test_handles_alternative_field_name(self):
        items = [{"comment": "Alternative field"}]
        comments = _extract_comments(items)
        assert len(comments) == 1
        assert comments[0]["text"] == "Alternative field"

    def test_empty_input_returns_empty(self):
        assert _extract_comments([]) == []


# -- Resolver integration tests (mocked HTTP) --


class TestInstagramApifyResolverReel:
    """Test the full Reel resolution flow with mocked Apify API."""

    @pytest.mark.asyncio
    async def test_resolve_reel_returns_video_url(self):
        resolver = InstagramApifyResolver(api_token="test-token")
        context = _make_context("https://www.instagram.com/reel/ABC123/")

        mock_run_response = MagicMock()
        mock_run_response.status_code = 200
        mock_run_response.json.return_value = {
            "data": {"id": "run-123", "defaultDatasetId": "dataset-456"}
        }

        mock_status_response = MagicMock()
        mock_status_response.status_code = 200
        mock_status_response.json.return_value = {
            "data": {"status": "SUCCEEDED", "defaultDatasetId": "dataset-456"}
        }

        mock_dataset_response = MagicMock()
        mock_dataset_response.status_code = 200
        mock_dataset_response.json.return_value = [
            {
                "downloadedVideo": "https://apify-storage.s3.amazonaws.com/reel.mp4",
                "videoUrl": "https://cdn.instagram.com/reel.mp4",
                "caption": "Check out this reel! #awesome",
            }
        ]

        # Mock comment scraper returning empty (best-effort)
        mock_comment_run_response = MagicMock()
        mock_comment_run_response.status_code = 200
        mock_comment_run_response.json.return_value = {
            "data": {"id": "run-789", "defaultDatasetId": "dataset-comment"}
        }

        mock_comment_status_response = MagicMock()
        mock_comment_status_response.status_code = 200
        mock_comment_status_response.json.return_value = {
            "data": {"status": "SUCCEEDED", "defaultDatasetId": "dataset-comment"}
        }

        mock_comment_dataset_response = MagicMock()
        mock_comment_dataset_response.status_code = 200
        mock_comment_dataset_response.json.return_value = [
            {"text": "Amazing!", "ownerUsername": "fan1", "likesCount": 3, "repliesCount": 0}
        ]

        call_count = {"value": 0}

        async def mock_post(url, **kwargs):
            call_count["value"] += 1
            if "reel-scraper" in url or call_count["value"] == 1:
                return mock_run_response
            return mock_comment_run_response

        async def mock_get(url, **kwargs):
            if "dataset-comment" in url and "items" in url:
                return mock_comment_dataset_response
            if "dataset-456" in url and "items" in url:
                return mock_dataset_response
            if "dataset-comment" in url or "run-789" in url:
                return mock_comment_status_response
            return mock_status_response

        with patch("media_summarizer.infrastructure.resolvers.instagram_apify_resolver.APIFY_POLL_INTERVAL_SECONDS", 0):
            with patch("httpx.AsyncClient") as mock_client_cls:
                mock_client = AsyncMock()
                mock_client.post = mock_post
                mock_client.get = mock_get
                mock_client.__aenter__ = AsyncMock(return_value=mock_client)
                mock_client.__aexit__ = AsyncMock(return_value=False)
                mock_client_cls.return_value = mock_client

                result = await resolver.resolve(context)

        assert result.media_family == MediaFamily.SOCIAL_VIDEO
        assert result.media_type == MediaType.SHORT_VIDEO
        assert result.source_platform == SourcePlatform.INSTAGRAM
        assert result.audio_url == "https://apify-storage.s3.amazonaws.com/reel.mp4"
        assert result.metadata["provider"] == "apify"
        assert result.metadata["caption"] == "Check out this reel! #awesome"
        assert result.metadata["instagram_content_type"] == "reel"


class TestInstagramApifyResolverImagePost:
    """Test image post resolution (single and carousel)."""

    @pytest.mark.asyncio
    async def test_resolve_image_post_returns_image_urls(self):
        resolver = InstagramApifyResolver(api_token="test-token")
        context = _make_context("https://www.instagram.com/p/XYZ789/")

        mock_run_response = MagicMock()
        mock_run_response.status_code = 200
        mock_run_response.json.return_value = {
            "data": {"id": "run-post-1", "defaultDatasetId": "dataset-post"}
        }

        mock_status_response = MagicMock()
        mock_status_response.status_code = 200
        mock_status_response.json.return_value = {
            "data": {"status": "SUCCEEDED", "defaultDatasetId": "dataset-post"}
        }

        mock_dataset_response = MagicMock()
        mock_dataset_response.status_code = 200
        mock_dataset_response.json.return_value = [
            {
                "displayUrl": "https://cdn.instagram.com/photo.jpg",
                "caption": "Beautiful sunset #photography",
            }
        ]

        mock_comment_run_response = MagicMock()
        mock_comment_run_response.status_code = 200
        mock_comment_run_response.json.return_value = {
            "data": {"id": "run-comment", "defaultDatasetId": "dataset-comment-2"}
        }
        mock_comment_status_response = MagicMock()
        mock_comment_status_response.status_code = 200
        mock_comment_status_response.json.return_value = {
            "data": {"status": "SUCCEEDED", "defaultDatasetId": "dataset-comment-2"}
        }
        mock_comment_dataset_response = MagicMock()
        mock_comment_dataset_response.status_code = 200
        mock_comment_dataset_response.json.return_value = []

        call_count = {"value": 0}

        async def mock_post(url, **kwargs):
            call_count["value"] += 1
            if call_count["value"] == 1:
                return mock_run_response
            return mock_comment_run_response

        async def mock_get(url, **kwargs):
            if "dataset-comment-2" in url and "items" in url:
                return mock_comment_dataset_response
            if "dataset-post" in url and "items" in url:
                return mock_dataset_response
            if "run-comment" in url or "dataset-comment-2" in url:
                return mock_comment_status_response
            return mock_status_response

        with patch("media_summarizer.infrastructure.resolvers.instagram_apify_resolver.APIFY_POLL_INTERVAL_SECONDS", 0):
            with patch("httpx.AsyncClient") as mock_client_cls:
                mock_client = AsyncMock()
                mock_client.post = mock_post
                mock_client.get = mock_get
                mock_client.__aenter__ = AsyncMock(return_value=mock_client)
                mock_client.__aexit__ = AsyncMock(return_value=False)
                mock_client_cls.return_value = mock_client

                result = await resolver.resolve(context)

        assert result.media_type == MediaType.IMAGE_POST
        assert result.source_platform == SourcePlatform.INSTAGRAM
        assert result.audio_url is None
        assert result.metadata["provider"] == "apify"
        assert result.metadata["post_type"] == "image"
        assert "https://cdn.instagram.com/photo.jpg" in result.metadata["image_urls"]
        assert result.metadata["caption"] == "Beautiful sunset #photography"

    @pytest.mark.asyncio
    async def test_resolve_carousel_returns_multiple_images(self):
        resolver = InstagramApifyResolver(api_token="test-token")
        context = _make_context("https://www.instagram.com/p/CAROUSEL1/")

        mock_run_response = MagicMock()
        mock_run_response.status_code = 200
        mock_run_response.json.return_value = {
            "data": {"id": "run-carousel", "defaultDatasetId": "dataset-carousel"}
        }

        mock_status_response = MagicMock()
        mock_status_response.status_code = 200
        mock_status_response.json.return_value = {
            "data": {"status": "SUCCEEDED", "defaultDatasetId": "dataset-carousel"}
        }

        mock_dataset_response = MagicMock()
        mock_dataset_response.status_code = 200
        mock_dataset_response.json.return_value = [
            {
                "displayUrl": "https://cdn.instagram.com/cover.jpg",
                "childPosts": [
                    {"displayUrl": "https://cdn.instagram.com/slide1.jpg"},
                    {"displayUrl": "https://cdn.instagram.com/slide2.jpg"},
                    {"displayUrl": "https://cdn.instagram.com/slide3.jpg"},
                ],
                "caption": "Trip highlights!",
            }
        ]

        # Comment scraper times out (best effort)
        mock_comment_run_response = MagicMock()
        mock_comment_run_response.status_code = 200
        mock_comment_run_response.json.return_value = {
            "data": {"id": "run-comment-c", "defaultDatasetId": "dataset-comment-c"}
        }
        mock_comment_status_response = MagicMock()
        mock_comment_status_response.status_code = 200
        mock_comment_status_response.json.return_value = {
            "data": {"status": "SUCCEEDED", "defaultDatasetId": "dataset-comment-c"}
        }
        mock_comment_dataset_response = MagicMock()
        mock_comment_dataset_response.status_code = 200
        mock_comment_dataset_response.json.return_value = []

        call_count = {"value": 0}

        async def mock_post(url, **kwargs):
            call_count["value"] += 1
            if call_count["value"] == 1:
                return mock_run_response
            return mock_comment_run_response

        async def mock_get(url, **kwargs):
            if "dataset-comment-c" in url and "items" in url:
                return mock_comment_dataset_response
            if "dataset-carousel" in url and "items" in url:
                return mock_dataset_response
            if "run-comment-c" in url or "dataset-comment-c" in url:
                return mock_comment_status_response
            return mock_status_response

        with patch("media_summarizer.infrastructure.resolvers.instagram_apify_resolver.APIFY_POLL_INTERVAL_SECONDS", 0):
            with patch("httpx.AsyncClient") as mock_client_cls:
                mock_client = AsyncMock()
                mock_client.post = mock_post
                mock_client.get = mock_get
                mock_client.__aenter__ = AsyncMock(return_value=mock_client)
                mock_client.__aexit__ = AsyncMock(return_value=False)
                mock_client_cls.return_value = mock_client

                result = await resolver.resolve(context)

        assert result.media_type == MediaType.IMAGE_POST
        assert result.metadata["post_type"] == "carousel"
        assert result.metadata["image_count"] == 4
        assert len(result.metadata["image_urls"]) == 4
        assert result.metadata["caption"] == "Trip highlights!"


class TestInstagramApifyResolverVideoPost:
    """Test video post resolution (post URL with video content)."""

    @pytest.mark.asyncio
    async def test_resolve_video_post_returns_audio_url(self):
        resolver = InstagramApifyResolver(api_token="test-token")
        context = _make_context("https://www.instagram.com/p/VIDEO123/")

        mock_run_response = MagicMock()
        mock_run_response.status_code = 200
        mock_run_response.json.return_value = {
            "data": {"id": "run-vid", "defaultDatasetId": "dataset-vid"}
        }

        mock_status_response = MagicMock()
        mock_status_response.status_code = 200
        mock_status_response.json.return_value = {
            "data": {"status": "SUCCEEDED", "defaultDatasetId": "dataset-vid"}
        }

        mock_dataset_response = MagicMock()
        mock_dataset_response.status_code = 200
        mock_dataset_response.json.return_value = [
            {
                "videoUrl": "https://cdn.instagram.com/video_post.mp4",
                "caption": "Video post caption",
            }
        ]

        mock_comment_run_response = MagicMock()
        mock_comment_run_response.status_code = 200
        mock_comment_run_response.json.return_value = {
            "data": {"id": "run-c", "defaultDatasetId": "dataset-c"}
        }
        mock_comment_status_response = MagicMock()
        mock_comment_status_response.status_code = 200
        mock_comment_status_response.json.return_value = {
            "data": {"status": "SUCCEEDED", "defaultDatasetId": "dataset-c"}
        }
        mock_comment_dataset_response = MagicMock()
        mock_comment_dataset_response.status_code = 200
        mock_comment_dataset_response.json.return_value = []

        call_count = {"value": 0}

        async def mock_post(url, **kwargs):
            call_count["value"] += 1
            if call_count["value"] == 1:
                return mock_run_response
            return mock_comment_run_response

        async def mock_get(url, **kwargs):
            if "dataset-c" in url and "items" in url:
                return mock_comment_dataset_response
            if "dataset-vid" in url and "items" in url:
                return mock_dataset_response
            if "run-c" in url or "dataset-c" in url:
                return mock_comment_status_response
            return mock_status_response

        with patch("media_summarizer.infrastructure.resolvers.instagram_apify_resolver.APIFY_POLL_INTERVAL_SECONDS", 0):
            with patch("httpx.AsyncClient") as mock_client_cls:
                mock_client = AsyncMock()
                mock_client.post = mock_post
                mock_client.get = mock_get
                mock_client.__aenter__ = AsyncMock(return_value=mock_client)
                mock_client.__aexit__ = AsyncMock(return_value=False)
                mock_client_cls.return_value = mock_client

                result = await resolver.resolve(context)

        assert result.media_family == MediaFamily.SOCIAL_VIDEO
        assert result.media_type == MediaType.SHORT_VIDEO
        assert result.audio_url == "https://cdn.instagram.com/video_post.mp4"
        assert result.metadata["post_type"] == "video"
        assert result.metadata["caption"] == "Video post caption"


class TestInstagramApifyResolverErrors:
    """Test error handling in the resolver."""

    @pytest.mark.asyncio
    async def test_missing_api_token_raises_retryable(self):
        resolver = InstagramApifyResolver(api_token="")
        context = _make_context("https://www.instagram.com/reel/ABC/")

        with pytest.raises(RetryableProviderResolutionError):
            await resolver.resolve(context)

    @pytest.mark.asyncio
    async def test_auth_error_raises_retryable(self):
        resolver = InstagramApifyResolver(api_token="bad-token")
        context = _make_context("https://www.instagram.com/reel/ABC/")

        mock_response = MagicMock()
        mock_response.status_code = 401
        mock_response.json.return_value = {"error": "Unauthorized"}

        async def mock_post(url, **kwargs):
            return mock_response

        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.post = mock_post
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client_cls.return_value = mock_client

            with pytest.raises(RetryableProviderResolutionError):
                await resolver.resolve(context)

    @pytest.mark.asyncio
    async def test_no_results_raises_non_retryable(self):
        resolver = InstagramApifyResolver(api_token="test-token")
        context = _make_context("https://www.instagram.com/reel/GONE/")

        mock_run_response = MagicMock()
        mock_run_response.status_code = 200
        mock_run_response.json.return_value = {
            "data": {"id": "run-empty", "defaultDatasetId": "dataset-empty"}
        }

        mock_status_response = MagicMock()
        mock_status_response.status_code = 200
        mock_status_response.json.return_value = {
            "data": {"status": "SUCCEEDED", "defaultDatasetId": "dataset-empty"}
        }

        mock_dataset_response = MagicMock()
        mock_dataset_response.status_code = 200
        mock_dataset_response.json.return_value = []

        async def mock_post(url, **kwargs):
            return mock_run_response

        async def mock_get(url, **kwargs):
            if "items" in url:
                return mock_dataset_response
            return mock_status_response

        with patch("media_summarizer.infrastructure.resolvers.instagram_apify_resolver.APIFY_POLL_INTERVAL_SECONDS", 0):
            with patch("httpx.AsyncClient") as mock_client_cls:
                mock_client = AsyncMock()
                mock_client.post = mock_post
                mock_client.get = mock_get
                mock_client.__aenter__ = AsyncMock(return_value=mock_client)
                mock_client.__aexit__ = AsyncMock(return_value=False)
                mock_client_cls.return_value = mock_client

                with pytest.raises(NonRetryableProviderResolutionError):
                    await resolver.resolve(context)
