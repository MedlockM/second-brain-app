"""
Unit tests for the YouTube Apify ingestion worker.

Covers:
- Successful transcript fetch with timed segments
- Successful transcript fetch with flat text
- HTTP 401/403 -> apify_actor_failed mapping
- HTTP 429 -> apify_quota_exceeded mapping
- HTTP 5xx -> apify_timeout mapping
- Actor run status FAILED -> apify_actor_failed
- Video unavailable payload from actor
"""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from media_summarizer.workers.youtube_ingestion_worker import (
    ApifyRunStatus,
    YouTubeIngestionError,
    _extract_video_id,
    _fetch_apify_transcript,
    _normalize_apify_result,
)


# -- _extract_video_id tests --


class TestExtractVideoId:
    def test_standard_watch_url(self):
        assert _extract_video_id("https://www.youtube.com/watch?v=dQw4w9WgXcQ") == "dQw4w9WgXcQ"

    def test_short_url(self):
        assert _extract_video_id("https://youtu.be/dQw4w9WgXcQ") == "dQw4w9WgXcQ"

    def test_shorts_url(self):
        assert _extract_video_id("https://www.youtube.com/shorts/dQw4w9WgXcQ") == "dQw4w9WgXcQ"

    def test_embed_url(self):
        assert _extract_video_id("https://www.youtube.com/embed/dQw4w9WgXcQ") == "dQw4w9WgXcQ"

    def test_missing_video_id_raises(self):
        with pytest.raises(YouTubeIngestionError) as exc_info:
            _extract_video_id("https://www.youtube.com/channel/UC123")
        assert exc_info.value.code == "youtube_unavailable"


# -- _normalize_apify_result tests --


class TestNormalizeApifyResult:
    def test_timed_segments(self):
        items = [{
            "transcript": [
                {"text": "Hello world", "start": 0.0, "duration": 2.5},
                {"text": "This is a test", "start": 2.5, "duration": 3.0},
            ],
            "language": "English",
            "languageCode": "en",
        }]
        result = _normalize_apify_result(items, "https://youtube.com/watch?v=abc", "abc")
        assert result["text"] == "Hello world\nThis is a test"
        assert result["segments_count"] == 2
        assert result["language"] == "English"
        assert result["language_code"] == "en"
        assert result["source_detail"] == "apify_youtube"
        assert result["source_url"] == "https://youtube.com/watch?v=abc"

    def test_flat_text_in_transcript_field(self):
        items = [{
            "transcript": "This is a flat transcript text from the actor.",
            "language": "French",
            "languageCode": "fr",
        }]
        result = _normalize_apify_result(items, "https://youtube.com/watch?v=xyz", "xyz")
        assert result["text"] == "This is a flat transcript text from the actor."
        assert result["segments_count"] == 0
        assert result["language_code"] == "fr"

    def test_top_level_text_field(self):
        items = [{"text": "Top level text content."}]
        result = _normalize_apify_result(items, "https://youtube.com/watch?v=t", "t")
        assert result["text"] == "Top level text content."
        assert result["segments_count"] == 0

    def test_empty_items_raises(self):
        with pytest.raises(YouTubeIngestionError) as exc_info:
            _normalize_apify_result([], "https://youtube.com/watch?v=x", "x")
        assert exc_info.value.code == "youtube_unavailable"
        assert "empty_dataset" in exc_info.value.details

    def test_no_transcript_in_payload_raises(self):
        items = [{"some_other_field": "value"}]
        with pytest.raises(YouTubeIngestionError) as exc_info:
            _normalize_apify_result(items, "https://youtube.com/watch?v=x", "x")
        assert exc_info.value.code == "youtube_unavailable"
        assert "no_transcript_in_payload" in exc_info.value.details

    def test_error_signal_unavailable(self):
        items = [{"error": "Video unavailable"}]
        with pytest.raises(YouTubeIngestionError) as exc_info:
            _normalize_apify_result(items, "https://youtube.com/watch?v=x", "x")
        assert exc_info.value.code == "youtube_unavailable"

    def test_error_signal_age_restricted(self):
        items = [{"error": "This video is age-restricted"}]
        with pytest.raises(YouTubeIngestionError) as exc_info:
            _normalize_apify_result(items, "https://youtube.com/watch?v=x", "x")
        assert exc_info.value.code == "youtube_age_restricted"

    def test_error_signal_geo_restricted(self):
        items = [{"error": "Geo restricted content"}]
        with pytest.raises(YouTubeIngestionError) as exc_info:
            _normalize_apify_result(items, "https://youtube.com/watch?v=x", "x")
        assert exc_info.value.code == "youtube_geo_restricted"

    def test_generic_actor_error(self):
        items = [{"error": "Something went wrong internally"}]
        with pytest.raises(YouTubeIngestionError) as exc_info:
            _normalize_apify_result(items, "https://youtube.com/watch?v=x", "x")
        assert exc_info.value.code == "apify_actor_failed"

    def test_segments_as_strings(self):
        items = [{
            "transcript": ["Hello", "World", "Test"],
            "languageCode": "en",
        }]
        result = _normalize_apify_result(items, "https://youtube.com/watch?v=s", "s")
        assert result["text"] == "Hello\nWorld\nTest"
        assert result["segments_count"] == 3


# -- _fetch_apify_transcript tests (mocked HTTP) --


class TestFetchApifyTranscript:
    @pytest.fixture(autouse=True)
    def mock_settings(self):
        with patch("media_summarizer.workers.youtube_ingestion_worker.settings") as mock_s:
            mock_s.APIFY_YOUTUBE_API_TOKEN = "test-token"
            mock_s.APIFY_YOUTUBE_TRANSCRIPT_ACTOR_ID = "test-actor-id"
            mock_s.APIFY_TIMEOUT_SECONDS = 30
            mock_s.APIFY_POLL_INTERVAL_SECONDS = 0.01
            mock_s.APIFY_MAX_POLLS = 3
            yield mock_s

    @pytest.fixture(autouse=True)
    def mock_emit_metric(self):
        with patch("media_summarizer.workers.youtube_ingestion_worker._emit_metric", new_callable=AsyncMock) as m:
            yield m

    @pytest.mark.asyncio
    async def test_success_with_timed_segments(self):
        """Full success path: start run, poll SUCCEEDED, fetch dataset."""
        run_response = httpx.Response(
            200,
            json={"data": {"id": "run-123"}},
        )
        poll_response = httpx.Response(
            200,
            json={"data": {"status": "SUCCEEDED", "defaultDatasetId": "ds-456"}},
        )
        dataset_response = httpx.Response(
            200,
            json=[{
                "transcript": [
                    {"text": "Hello world", "start": 0, "duration": 2},
                    {"text": "Testing", "start": 2, "duration": 1},
                ],
                "languageCode": "en",
                "language": "English",
            }],
        )

        with patch("httpx.AsyncClient") as MockClient:
            mock_client = AsyncMock()
            MockClient.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            MockClient.return_value.__aexit__ = AsyncMock(return_value=False)
            mock_client.post.return_value = run_response
            mock_client.get.side_effect = [poll_response, dataset_response]

            result = await _fetch_apify_transcript("abc123", "https://youtube.com/watch?v=abc123")

        assert result["text"] == "Hello world\nTesting"
        assert result["segments_count"] == 2
        assert result["language_code"] == "en"
        assert result["source_detail"] == "apify_youtube"

    @pytest.mark.asyncio
    async def test_success_with_flat_text(self):
        """Actor returns flat transcript text."""
        run_response = httpx.Response(200, json={"data": {"id": "run-1"}})
        poll_response = httpx.Response(
            200,
            json={"data": {"status": "SUCCEEDED", "defaultDatasetId": "ds-1"}},
        )
        dataset_response = httpx.Response(
            200,
            json=[{"transcript": "This is a flat text transcript.", "languageCode": "fr"}],
        )

        with patch("httpx.AsyncClient") as MockClient:
            mock_client = AsyncMock()
            MockClient.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            MockClient.return_value.__aexit__ = AsyncMock(return_value=False)
            mock_client.post.return_value = run_response
            mock_client.get.side_effect = [poll_response, dataset_response]

            result = await _fetch_apify_transcript("vid1", "https://youtube.com/watch?v=vid1")

        assert result["text"] == "This is a flat text transcript."
        assert result["segments_count"] == 0
        assert result["language_code"] == "fr"

    @pytest.mark.asyncio
    async def test_http_401_raises_actor_failed(self):
        """401 on actor start -> apify_actor_failed (non-retryable)."""
        error_response = httpx.Response(401, json={"error": "Unauthorized"})

        with patch("httpx.AsyncClient") as MockClient:
            mock_client = AsyncMock()
            MockClient.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            MockClient.return_value.__aexit__ = AsyncMock(return_value=False)
            mock_client.post.return_value = error_response

            with pytest.raises(YouTubeIngestionError) as exc_info:
                await _fetch_apify_transcript("v1", "https://youtube.com/watch?v=v1")

        assert exc_info.value.code == "apify_actor_failed"
        assert exc_info.value.retryable is False

    @pytest.mark.asyncio
    async def test_http_429_raises_quota_exceeded(self):
        """429 on actor start -> apify_quota_exceeded (retryable)."""
        error_response = httpx.Response(429, json={"error": "Rate limited"})

        with patch("httpx.AsyncClient") as MockClient:
            mock_client = AsyncMock()
            MockClient.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            MockClient.return_value.__aexit__ = AsyncMock(return_value=False)
            mock_client.post.return_value = error_response

            with pytest.raises(YouTubeIngestionError) as exc_info:
                await _fetch_apify_transcript("v2", "https://youtube.com/watch?v=v2")

        assert exc_info.value.code == "apify_quota_exceeded"
        assert exc_info.value.retryable is True

    @pytest.mark.asyncio
    async def test_http_500_raises_apify_timeout(self):
        """5xx on actor start -> apify_timeout (retryable)."""
        error_response = httpx.Response(500, json={"error": "Internal"})

        with patch("httpx.AsyncClient") as MockClient:
            mock_client = AsyncMock()
            MockClient.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            MockClient.return_value.__aexit__ = AsyncMock(return_value=False)
            mock_client.post.return_value = error_response

            with pytest.raises(YouTubeIngestionError) as exc_info:
                await _fetch_apify_transcript("v3", "https://youtube.com/watch?v=v3")

        assert exc_info.value.code == "apify_timeout"
        assert exc_info.value.retryable is True

    @pytest.mark.asyncio
    async def test_actor_run_failed_status(self):
        """Actor run reaches FAILED status -> apify_actor_failed."""
        run_response = httpx.Response(200, json={"data": {"id": "run-fail"}})
        poll_response = httpx.Response(
            200,
            json={"data": {"status": "FAILED", "defaultDatasetId": None}},
        )

        with patch("httpx.AsyncClient") as MockClient:
            mock_client = AsyncMock()
            MockClient.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            MockClient.return_value.__aexit__ = AsyncMock(return_value=False)
            mock_client.post.return_value = run_response
            mock_client.get.return_value = poll_response

            with pytest.raises(YouTubeIngestionError) as exc_info:
                await _fetch_apify_transcript("v4", "https://youtube.com/watch?v=v4")

        assert exc_info.value.code == "apify_actor_failed"
        assert "FAILED" in exc_info.value.details

    @pytest.mark.asyncio
    async def test_video_unavailable_in_payload(self):
        """Actor succeeds but payload signals video unavailable."""
        run_response = httpx.Response(200, json={"data": {"id": "run-5"}})
        poll_response = httpx.Response(
            200,
            json={"data": {"status": "SUCCEEDED", "defaultDatasetId": "ds-5"}},
        )
        dataset_response = httpx.Response(
            200,
            json=[{"error": "Video unavailable - this video has been removed"}],
        )

        with patch("httpx.AsyncClient") as MockClient:
            mock_client = AsyncMock()
            MockClient.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            MockClient.return_value.__aexit__ = AsyncMock(return_value=False)
            mock_client.post.return_value = run_response
            mock_client.get.side_effect = [poll_response, dataset_response]

            with pytest.raises(YouTubeIngestionError) as exc_info:
                await _fetch_apify_transcript("v5", "https://youtube.com/watch?v=v5")

        assert exc_info.value.code == "youtube_unavailable"
        assert exc_info.value.retryable is False

    @pytest.mark.asyncio
    async def test_missing_token_raises(self, mock_settings):
        """Missing APIFY_YOUTUBE_API_TOKEN raises non-retryable error."""
        mock_settings.APIFY_YOUTUBE_API_TOKEN = ""

        with pytest.raises(YouTubeIngestionError) as exc_info:
            await _fetch_apify_transcript("v6", "https://youtube.com/watch?v=v6")

        assert exc_info.value.code == "apify_actor_failed"
        assert "missing_apify_youtube_api_token" in exc_info.value.details

    @pytest.mark.asyncio
    async def test_polling_exhausted_raises_timeout(self):
        """If polling exhausts max_polls without terminal status -> apify_timeout."""
        run_response = httpx.Response(200, json={"data": {"id": "run-poll"}})
        # Always return RUNNING status
        running_response = httpx.Response(
            200,
            json={"data": {"status": "RUNNING", "defaultDatasetId": None}},
        )

        with patch("httpx.AsyncClient") as MockClient:
            mock_client = AsyncMock()
            MockClient.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            MockClient.return_value.__aexit__ = AsyncMock(return_value=False)
            mock_client.post.return_value = run_response
            mock_client.get.return_value = running_response

            with pytest.raises(YouTubeIngestionError) as exc_info:
                await _fetch_apify_transcript("v7", "https://youtube.com/watch?v=v7")

        assert exc_info.value.code == "apify_timeout"
        assert "polling_exhausted" in exc_info.value.details
        assert exc_info.value.retryable is True
