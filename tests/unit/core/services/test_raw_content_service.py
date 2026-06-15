"""Unit tests for raw_content_service.get_raw_content's translation handling.

Regression coverage for the "Unable to load the transcript right now" bug
class: even when the prewarm (task-192) didn't manage to cache a translation
in time, /raw-content must never let a slow translation call exceed API
Gateway's hard 30s integration timeout. ensure_translated_transcript is
bounded by RAW_CONTENT_TRANSLATION_TIMEOUT_SECONDS; on timeout the original
(untranslated) transcript is returned with translation_failed=True instead of
the whole request hanging until API Gateway kills it with a 503.
"""

from __future__ import annotations

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from media_summarizer.core.services import raw_content_service
from media_summarizer.core.services.raw_content_service import get_raw_content
from media_summarizer.core.services.transcript_translation import TranslationOutcome


def _make_job():
    return SimpleNamespace(
        id="job-1",
        user_id="user-1",
        transcription_s3_key="job-1.txt",
        media_type="video",
        source_platform="tiktok",
        transcription_metadata=None,
    )


@pytest.mark.asyncio
async def test_translation_timeout_falls_back_to_original_transcript(monkeypatch):
    job = _make_job()
    monkeypatch.setattr(
        raw_content_service.s3,
        "download_file_to_memory",
        AsyncMock(return_value=b"hello world"),
    )

    async def _never_returns(**kwargs):
        await asyncio.sleep(10)

    monkeypatch.setattr(
        raw_content_service, "ensure_translated_transcript", _never_returns
    )
    monkeypatch.setattr(
        raw_content_service, "RAW_CONTENT_TRANSLATION_TIMEOUT_SECONDS", 0.01
    )
    persist_mock = AsyncMock()
    monkeypatch.setattr(raw_content_service, "persist_detected_language", persist_mock)

    response = await get_raw_content(job, reading_language="fr")

    assert response.content == "hello world"
    assert response.translation == {
        "is_translated": False,
        "translated_from": None,
        "target_language": "fr",
        "detected_language": None,
        "detection_method": "timeout",
        "translation_failed": True,
    }
    persist_mock.assert_not_awaited()


@pytest.mark.asyncio
async def test_translation_within_timeout_returns_translated_text(monkeypatch):
    job = _make_job()

    async def _fake_download(*, bucket, key):
        if key == "job-1.translated.fr.txt":
            return b"bonjour le monde"
        return b"hello world"

    monkeypatch.setattr(
        raw_content_service.s3,
        "download_file_to_memory",
        AsyncMock(side_effect=_fake_download),
    )

    outcome = TranslationOutcome(
        transcript_s3_key="job-1.translated.fr.txt",
        detected_language="en",
        detection_method="langdetect",
        target_language="fr",
        is_translated=True,
    )
    monkeypatch.setattr(
        raw_content_service,
        "ensure_translated_transcript",
        AsyncMock(return_value=outcome),
    )
    persist_mock = AsyncMock()
    monkeypatch.setattr(raw_content_service, "persist_detected_language", persist_mock)

    response = await get_raw_content(job, reading_language="fr")

    assert response.content == "bonjour le monde"
    assert response.translation["is_translated"] is True
    persist_mock.assert_awaited_once_with(job, "en")
