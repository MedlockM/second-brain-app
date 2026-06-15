"""Unit tests for transcript_translation.prewarm_translated_transcript.

Regression coverage for the "Unable to load the transcript right now" bug
class (task-192 follow-up): every worker that completes a job with a
transcript must pre-warm the translation cache *before* mark_completed(), so
the first /raw-content call is a cache hit and stays within API Gateway's hard
30s integration timeout. This module is the single shared implementation
called from all of those worker call sites.
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from media_summarizer.core.services import transcript_translation
from media_summarizer.core.services.transcript_translation import (
    TranslationOutcome,
    prewarm_translated_transcript,
)


def _make_job(*, user_id="user-1", source_platform="tiktok"):
    return SimpleNamespace(
        id="job-1",
        user_id=user_id,
        source_platform=source_platform,
        transcription_metadata=None,
    )


@pytest.mark.asyncio
async def test_no_user_id_skips_translation(monkeypatch):
    job = _make_job(user_id=None)
    ensure_mock = AsyncMock()
    monkeypatch.setattr(transcript_translation, "ensure_translated_transcript", ensure_mock)

    await prewarm_translated_transcript(job, "job-1.txt", "hello world")

    ensure_mock.assert_not_awaited()


@pytest.mark.asyncio
async def test_user_without_reading_language_skips_translation(monkeypatch):
    job = _make_job()
    get_user_mock = AsyncMock(return_value=SimpleNamespace(reading_language=None))
    monkeypatch.setattr(
        "media_summarizer.utils.database_async.get_user_by_id", get_user_mock
    )
    ensure_mock = AsyncMock()
    monkeypatch.setattr(transcript_translation, "ensure_translated_transcript", ensure_mock)

    await prewarm_translated_transcript(job, "job-1.txt", "hello world")

    get_user_mock.assert_awaited_once_with("user-1")
    ensure_mock.assert_not_awaited()


@pytest.mark.asyncio
async def test_user_lookup_failure_is_swallowed(monkeypatch):
    job = _make_job()
    get_user_mock = AsyncMock(side_effect=RuntimeError("dynamodb down"))
    monkeypatch.setattr(
        "media_summarizer.utils.database_async.get_user_by_id", get_user_mock
    )
    ensure_mock = AsyncMock()
    monkeypatch.setattr(transcript_translation, "ensure_translated_transcript", ensure_mock)

    # Must not raise -- prewarm is best-effort.
    await prewarm_translated_transcript(job, "job-1.txt", "hello world")

    ensure_mock.assert_not_awaited()


@pytest.mark.asyncio
async def test_happy_path_translates_and_persists_detected_language(monkeypatch):
    job = _make_job()
    get_user_mock = AsyncMock(return_value=SimpleNamespace(reading_language="fr"))
    monkeypatch.setattr(
        "media_summarizer.utils.database_async.get_user_by_id", get_user_mock
    )

    outcome = TranslationOutcome(
        transcript_s3_key="job-1.translated.fr.txt",
        detected_language="en",
        detection_method="langdetect",
        target_language="fr",
        is_translated=True,
    )
    ensure_mock = AsyncMock(return_value=outcome)
    persist_mock = AsyncMock()
    monkeypatch.setattr(transcript_translation, "ensure_translated_transcript", ensure_mock)
    monkeypatch.setattr(transcript_translation, "persist_detected_language", persist_mock)

    await prewarm_translated_transcript(job, "job-1.txt", "hello world")

    ensure_mock.assert_awaited_once_with(
        transcript_s3_key="job-1.txt",
        transcript_text="hello world",
        target_language="fr",
        source="tiktok",
        source_language_hint=None,
        transcript_bucket=transcript_translation.TRANSCRIPT_BUCKET,
    )
    persist_mock.assert_awaited_once_with(job, "en")


@pytest.mark.asyncio
async def test_translation_timeout_is_swallowed(monkeypatch):
    job = _make_job()
    get_user_mock = AsyncMock(return_value=SimpleNamespace(reading_language="fr"))
    monkeypatch.setattr(
        "media_summarizer.utils.database_async.get_user_by_id", get_user_mock
    )

    async def _never_returns(**kwargs):
        import asyncio

        await asyncio.sleep(10)

    monkeypatch.setattr(transcript_translation, "ensure_translated_transcript", _never_returns)
    monkeypatch.setattr(transcript_translation, "PREWARM_TRANSLATION_TIMEOUT_SECONDS", 0.01)

    # Must not raise and must not hang -- bounded by the timeout.
    await prewarm_translated_transcript(job, "job-1.txt", "hello world")


@pytest.mark.asyncio
async def test_translation_error_is_swallowed(monkeypatch):
    job = _make_job()
    get_user_mock = AsyncMock(return_value=SimpleNamespace(reading_language="fr"))
    monkeypatch.setattr(
        "media_summarizer.utils.database_async.get_user_by_id", get_user_mock
    )
    ensure_mock = AsyncMock(side_effect=RuntimeError("translation_llm_http_500"))
    monkeypatch.setattr(transcript_translation, "ensure_translated_transcript", ensure_mock)

    # Must not raise -- a failed prewarm just means /raw-content translates on demand.
    await prewarm_translated_transcript(job, "job-1.txt", "hello world")
