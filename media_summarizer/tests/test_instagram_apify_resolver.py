"""
Unit tests for the InstagramApifyResolver.

Covers:
- Reel with valid transcript (long) -> raw_text populated, audio_url is None
- Reel with empty/absent transcript -> fallback to audio_url=downloadedVideo
- Reel with transcript below minimum threshold -> fallback to audio_url=downloadedVideo
- Reel without downloadedVideo but with videoUrl -> CDN fallback
- Feature flag disabled -> transcript ignored even if present
"""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

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
from media_summarizer.infrastructure.resolvers.instagram_apify_resolver import (
    InstagramApifyResolver,
)


def _make_context(url: str = "https://www.instagram.com/reel/ABC123/") -> ResolveContext:
    return ResolveContext(
        command=IngestUrlCommand(
            user=UserContext(user_id="user-1", user_email="test@example.com"),
            request=IngestUrlRequest(url=url),
        ),
        normalized_url=url,
        media_key="instagram:reel:ABC123",
        classification=ClassifiedUrl(
            media_family=MediaFamily.SOCIAL_VIDEO,
            source_platform=SourcePlatform.INSTAGRAM,
            resolver_key="instagram.default",
        ),
    )


def _apify_result(
    *,
    transcript: str | None = None,
    downloaded_video: str | None = "https://apify-cdn.com/video.mp4",
    video_url: str | None = "https://instagram-cdn.com/video.mp4",
    duration: float | None = 45.0,
) -> dict:
    result: dict = {}
    if transcript is not None:
        result["transcript"] = transcript
    if downloaded_video is not None:
        result["downloadedVideo"] = downloaded_video
    if video_url is not None:
        result["videoUrl"] = video_url
    if duration is not None:
        result["videoDuration"] = duration
    return result


@pytest.mark.asyncio
class TestInstagramApifyResolverReelTranscript:
    """Reel with a valid, long transcript -> raw_text populated, no audio_url."""

    async def test_valid_transcript_populates_raw_text(self):
        long_transcript = "This is a valid transcript that is well above the minimum threshold for Apify."
        resolver = InstagramApifyResolver(
            apify_api_token="test-token",
            transcript_min_length=20,
            use_apify_transcript=True,
        )

        with patch(
            "media_summarizer.infrastructure.resolvers.instagram_apify_resolver._run_apify_reel_actor",
            new_callable=AsyncMock,
            return_value=_apify_result(transcript=long_transcript),
        ):
            result = await resolver.resolve(_make_context())

        assert result.raw_text == long_transcript
        assert result.audio_url is None
        assert result.media_family == MediaFamily.SOCIAL_VIDEO
        assert result.media_type == MediaType.SHORT_VIDEO
        assert result.source_platform == SourcePlatform.INSTAGRAM
        assert result.metadata["transcript_source"] == "apify_native"
        assert result.metadata["audio_url_available"] is False
        assert result.metadata["transcript_char_count"] == len(long_transcript)


@pytest.mark.asyncio
class TestInstagramApifyResolverReelEmptyTranscript:
    """Reel with empty/absent transcript -> fallback to audio_url."""

    async def test_empty_transcript_falls_back_to_downloaded_video(self):
        resolver = InstagramApifyResolver(
            apify_api_token="test-token",
            transcript_min_length=20,
            use_apify_transcript=True,
        )

        with patch(
            "media_summarizer.infrastructure.resolvers.instagram_apify_resolver._run_apify_reel_actor",
            new_callable=AsyncMock,
            return_value=_apify_result(transcript=""),
        ):
            result = await resolver.resolve(_make_context())

        assert result.raw_text is None
        assert result.audio_url == "https://apify-cdn.com/video.mp4"
        assert result.metadata["transcript_source"] == "deepgram_pending"

    async def test_absent_transcript_falls_back_to_downloaded_video(self):
        resolver = InstagramApifyResolver(
            apify_api_token="test-token",
            transcript_min_length=20,
            use_apify_transcript=True,
        )

        with patch(
            "media_summarizer.infrastructure.resolvers.instagram_apify_resolver._run_apify_reel_actor",
            new_callable=AsyncMock,
            return_value=_apify_result(transcript=None),
        ):
            result = await resolver.resolve(_make_context())

        assert result.raw_text is None
        assert result.audio_url == "https://apify-cdn.com/video.mp4"
        assert result.metadata["transcript_source"] == "deepgram_pending"


@pytest.mark.asyncio
class TestInstagramApifyResolverReelShortTranscript:
    """Reel with transcript below threshold -> fallback to audio_url."""

    async def test_short_transcript_falls_back_to_downloaded_video(self):
        short_transcript = "Too short"  # < 20 chars
        resolver = InstagramApifyResolver(
            apify_api_token="test-token",
            transcript_min_length=20,
            use_apify_transcript=True,
        )

        with patch(
            "media_summarizer.infrastructure.resolvers.instagram_apify_resolver._run_apify_reel_actor",
            new_callable=AsyncMock,
            return_value=_apify_result(transcript=short_transcript),
        ):
            result = await resolver.resolve(_make_context())

        assert result.raw_text is None
        assert result.audio_url == "https://apify-cdn.com/video.mp4"
        assert result.metadata["transcript_source"] == "deepgram_pending"
        assert result.metadata["apify_transcript_below_threshold"] is True


@pytest.mark.asyncio
class TestInstagramApifyResolverReelCdnFallback:
    """Reel without downloadedVideo but with videoUrl -> CDN fallback."""

    async def test_no_downloaded_video_uses_video_url(self):
        resolver = InstagramApifyResolver(
            apify_api_token="test-token",
            transcript_min_length=20,
            use_apify_transcript=True,
        )

        with patch(
            "media_summarizer.infrastructure.resolvers.instagram_apify_resolver._run_apify_reel_actor",
            new_callable=AsyncMock,
            return_value=_apify_result(
                transcript=None,
                downloaded_video=None,
                video_url="https://instagram-cdn.com/video.mp4",
            ),
        ):
            result = await resolver.resolve(_make_context())

        assert result.raw_text is None
        assert result.audio_url == "https://instagram-cdn.com/video.mp4"
        assert result.metadata["transcript_source"] == "deepgram_pending_cdn_fallback"


@pytest.mark.asyncio
class TestInstagramApifyResolverFeatureFlagDisabled:
    """Feature flag disabled -> transcript ignored even if present."""

    async def test_feature_flag_off_ignores_transcript(self):
        long_transcript = "This is a perfectly good transcript but the flag is off so it should be ignored."
        resolver = InstagramApifyResolver(
            apify_api_token="test-token",
            transcript_min_length=20,
            use_apify_transcript=False,
        )

        with patch(
            "media_summarizer.infrastructure.resolvers.instagram_apify_resolver._run_apify_reel_actor",
            new_callable=AsyncMock,
            return_value=_apify_result(transcript=long_transcript),
        ):
            result = await resolver.resolve(_make_context())

        assert result.raw_text is None
        assert result.audio_url == "https://apify-cdn.com/video.mp4"
        assert result.metadata["transcript_source"] == "deepgram_pending"


@pytest.mark.asyncio
class TestInstagramApifyResolverPostUnchanged:
    """Post URLs are handled without transcript logic."""

    async def test_post_url_returns_deferred_resolution(self):
        resolver = InstagramApifyResolver(
            apify_api_token="test-token",
            transcript_min_length=20,
            use_apify_transcript=True,
        )
        context = _make_context(url="https://www.instagram.com/p/XYZ789/")

        result = await resolver.resolve(context)

        assert result.raw_text is None
        assert result.audio_url is None
        assert result.metadata["instagram_content_type"] == "post"
        assert result.metadata["resolution_mode"] == "queued_worker"
