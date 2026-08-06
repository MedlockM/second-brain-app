"""Unit tests for tiktok_ingestion_worker._extract_tiktok_id."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from media_summarizer.core.models.processing_job import ProcessingJob
from media_summarizer.workers import tiktok_ingestion_worker
from media_summarizer.workers.tiktok_ingestion_worker import (
    NativeSubtitlesUnavailable,
    TikTokIngestionError,
    _extract_tiktok_id,
)


def test_extract_tiktok_id_from_canonical_video_url():
    url = "https://www.tiktok.com/@someuser/video/7123456789012345678"
    assert _extract_tiktok_id(url) == "7123456789012345678"


def test_extract_tiktok_id_from_short_t_path():
    url = "https://www.tiktok.com/t/ZTd1abcd2/"
    assert _extract_tiktok_id(url) == "ZTd1abcd2"


def test_extract_tiktok_id_from_vm_share_link():
    """vm.tiktok.com share links carry a shortcode yt-dlp resolves itself.

    Regression test: this used to raise unsupported_content/missing_tiktok_id
    before yt-dlp even got a chance to follow the redirect.
    """
    url = "https://vm.tiktok.com/ZNRc7AAcY/"
    assert _extract_tiktok_id(url) == "ZNRc7AAcY"


def test_extract_tiktok_id_unsupported_url_raises():
    url = "https://www.tiktok.com/some/unsupported/path"
    with pytest.raises(TikTokIngestionError) as exc_info:
        _extract_tiktok_id(url)
    assert exc_info.value.code == "unsupported_content"
    assert exc_info.value.details == "missing_tiktok_id"


@pytest.mark.asyncio
async def test_subtitle_fallback_persists_media_url_on_processing_job(monkeypatch):
    job = ProcessingJob(
        id="job-1",
        user_id="user-1",
        user_email="user@example.com",
        title="Video title",
        source_platform="tiktok",
    )
    audio_result = {
        "audio_url": "https://cdn.example.com/audio.mp4",
        "audio_duration_seconds": 42,
        "format_id": "audio-1",
        "format_note": "audio only",
        "ext": "mp4",
        "acodec": "aac",
        "vcodec": "none",
    }
    update_job = AsyncMock()
    enqueue = AsyncMock()

    monkeypatch.setattr(
        tiktok_ingestion_worker.database_async,
        "get_processing_job_by_id",
        AsyncMock(return_value=job),
    )
    monkeypatch.setattr(
        tiktok_ingestion_worker.database_async,
        "update_processing_job",
        update_job,
    )
    monkeypatch.setattr(
        tiktok_ingestion_worker,
        "_extract_tiktok_info",
        AsyncMock(return_value={"id": "7123456789012345678"}),
    )
    monkeypatch.setattr(
        tiktok_ingestion_worker,
        "_fetch_native_subtitles",
        AsyncMock(side_effect=NativeSubtitlesUnavailable("missing")),
    )
    monkeypatch.setattr(
        tiktok_ingestion_worker,
        "_resolve_direct_media_url",
        lambda _info: audio_result,
    )
    monkeypatch.setattr(
        tiktok_ingestion_worker,
        "enqueue_deepgram_transcription",
        enqueue,
    )

    result = await tiktok_ingestion_worker.process_tiktok_message(
        {
            "job_id": job.id,
            "normalized_url": (
                "https://www.tiktok.com/@someuser/video/7123456789012345678"
            ),
            "media_key": "tiktok:7123456789012345678",
            "user_id": job.user_id,
            "user_email": job.user_email,
        }
    )

    assert result["mode"] == "deepgram_fallback"
    assert job.media_url == audio_result["audio_url"]
    assert job.status.value == "transcribing"
    assert update_job.await_count == 2
    enqueue.assert_awaited_once_with(
        job_id=job.id,
        audio_url=audio_result["audio_url"],
        deepgram_mode="pull_with_push_fallback",
        source_platform="tiktok",
        media_key="tiktok:7123456789012345678",
        user_id=job.user_id,
        user_email=job.user_email,
        normalized_url="https://www.tiktok.com/@someuser/video/7123456789012345678",
        episode_title=job.title,
        podcast_title=job.source_platform,
        audio_duration_seconds=audio_result["audio_duration_seconds"],
    )
