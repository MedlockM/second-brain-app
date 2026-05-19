"""
Unit tests for the SOCIAL_VIDEO + audio_url dispatch case in the orchestrator.

Validates that Instagram (and other social video providers returning a remote
audio_url) are correctly dispatched to the Deepgram transcription queue with
proper job state transition.
"""

import os
import pytest
from unittest.mock import AsyncMock, patch, MagicMock

# Set AWS credentials for testing
os.environ.setdefault("AWS_ACCESS_KEY_ID", "test")
os.environ.setdefault("AWS_SECRET_ACCESS_KEY", "test")
os.environ.setdefault("AWS_DEFAULT_REGION", "us-east-1")
os.environ.setdefault("AWS_ENDPOINT_URL", "http://localhost:4566")

from media_summarizer.core.media_ingestion.adapters.orchestrators import (
    ProcessingJobSubmissionOrchestrator,
)
from media_summarizer.core.media_ingestion.domain import (
    IngestUrlCommand,
    IngestUrlRequest,
    MediaFamily,
    MediaType,
    ProcessingLifecycleStatus,
    ResolvedMedia,
    SourcePlatform,
    UserContext,
)


def _make_instagram_resolved() -> ResolvedMedia:
    """Create a ResolvedMedia mimicking what InstagramResolver returns."""
    return ResolvedMedia(
        media_key="instagram:reel:ABC123",
        normalized_url="https://www.instagram.com/reel/ABC123/",
        media_family=MediaFamily.SOCIAL_VIDEO,
        media_type=MediaType.SHORT_VIDEO,
        source_platform=SourcePlatform.INSTAGRAM,
        resolver_key="instagram.default",
        audio_url="https://example.com/audio.mp3",
        metadata={
            "resolver_version": "v1",
            "provider": "getinsaver",
            "provider_endpoint": "instagram",
            "instagram_content_type": "reel",
            "provider_media_type": "video",
            "audio_url_available": True,
            "resolution_mode": "provider_inline",
        },
    )


def _make_ingest_command() -> IngestUrlCommand:
    """Create a minimal IngestUrlCommand for testing."""
    return IngestUrlCommand(
        user=UserContext(user_id="user-001", user_email="test@example.com"),
        request=IngestUrlRequest(
            url="https://www.instagram.com/reel/ABC123/",
            source_app="mobile",
        ),
    )


class TestSocialVideoDispatch:
    """Tests for SOCIAL_VIDEO + audio_url orchestrator dispatch."""

    @pytest.mark.asyncio
    async def test_instagram_social_video_enqueued_to_deepgram(self):
        """Instagram resolved media with audio_url dispatches to Deepgram queue."""
        resolved = _make_instagram_resolved()
        command = _make_ingest_command()

        mock_sqs_send = AsyncMock()
        mock_create_job = AsyncMock()
        mock_update_job = AsyncMock()
        mock_reserve = AsyncMock(return_value=True)
        mock_already_processed = AsyncMock(return_value=None)
        mock_mark_submission = AsyncMock()

        with patch(
            "media_summarizer.core.media_ingestion.adapters.orchestrators.episode_idempotence.already_processed",
            mock_already_processed,
        ), patch(
            "media_summarizer.core.media_ingestion.adapters.orchestrators.episode_idempotence.reserve_or_skip",
            mock_reserve,
        ), patch(
            "media_summarizer.core.media_ingestion.adapters.orchestrators.database_async.create_processing_job",
            mock_create_job,
        ), patch(
            "media_summarizer.core.media_ingestion.adapters.orchestrators.database_async.update_processing_job",
            mock_update_job,
        ), patch(
            "media_summarizer.core.media_ingestion.adapters.orchestrators.sqs.send_message",
            mock_sqs_send,
        ), patch(
            "media_summarizer.core.media_ingestion.adapters.orchestrators.mark_user_media_submission",
            mock_mark_submission,
        ):
            orchestrator = ProcessingJobSubmissionOrchestrator(
                deepgram_transcription_queue="test-deepgram-queue",
            )

            outcome = await orchestrator.submit(command=command, resolved=resolved)

        # Verify SQS message sent to the Deepgram transcription queue
        mock_sqs_send.assert_called_once()
        call_kwargs = mock_sqs_send.call_args[1]
        assert call_kwargs["queue_name"] == "test-deepgram-queue"

        message_body = call_kwargs["message_body"]
        assert message_body["audio_url"] == "https://example.com/audio.mp3"
        assert message_body["media_key"] == "instagram:reel:ABC123"
        assert message_body["source_platform"] == "instagram"
        assert message_body["resolver_key"] == "instagram.default"
        assert message_body["user_id"] == "user-001"
        assert message_body["user_email"] == "test@example.com"

    @pytest.mark.asyncio
    async def test_instagram_job_marked_transcribing(self):
        """Job state transitions to TRANSCRIBING when Instagram URL is dispatched."""
        resolved = _make_instagram_resolved()
        command = _make_ingest_command()

        mock_sqs_send = AsyncMock()
        mock_create_job = AsyncMock()
        mock_update_job = AsyncMock()
        mock_reserve = AsyncMock(return_value=True)
        mock_already_processed = AsyncMock(return_value=None)
        mock_mark_submission = AsyncMock()

        with patch(
            "media_summarizer.core.media_ingestion.adapters.orchestrators.episode_idempotence.already_processed",
            mock_already_processed,
        ), patch(
            "media_summarizer.core.media_ingestion.adapters.orchestrators.episode_idempotence.reserve_or_skip",
            mock_reserve,
        ), patch(
            "media_summarizer.core.media_ingestion.adapters.orchestrators.database_async.create_processing_job",
            mock_create_job,
        ), patch(
            "media_summarizer.core.media_ingestion.adapters.orchestrators.database_async.update_processing_job",
            mock_update_job,
        ), patch(
            "media_summarizer.core.media_ingestion.adapters.orchestrators.sqs.send_message",
            mock_sqs_send,
        ), patch(
            "media_summarizer.core.media_ingestion.adapters.orchestrators.mark_user_media_submission",
            mock_mark_submission,
        ):
            orchestrator = ProcessingJobSubmissionOrchestrator(
                deepgram_transcription_queue="test-deepgram-queue",
            )

            outcome = await orchestrator.submit(command=command, resolved=resolved)

        # Verify job state update was called (mark_transcribing triggers update_processing_job)
        assert mock_update_job.call_count == 1
        updated_job = mock_update_job.call_args[0][0]
        assert updated_job.status.value == "transcribing"

    @pytest.mark.asyncio
    async def test_instagram_outcome_status_is_transcribing(self):
        """Outcome status is TRANSCRIBING for social video dispatch."""
        resolved = _make_instagram_resolved()
        command = _make_ingest_command()

        mock_sqs_send = AsyncMock()
        mock_create_job = AsyncMock()
        mock_update_job = AsyncMock()
        mock_reserve = AsyncMock(return_value=True)
        mock_already_processed = AsyncMock(return_value=None)
        mock_mark_submission = AsyncMock()

        with patch(
            "media_summarizer.core.media_ingestion.adapters.orchestrators.episode_idempotence.already_processed",
            mock_already_processed,
        ), patch(
            "media_summarizer.core.media_ingestion.adapters.orchestrators.episode_idempotence.reserve_or_skip",
            mock_reserve,
        ), patch(
            "media_summarizer.core.media_ingestion.adapters.orchestrators.database_async.create_processing_job",
            mock_create_job,
        ), patch(
            "media_summarizer.core.media_ingestion.adapters.orchestrators.database_async.update_processing_job",
            mock_update_job,
        ), patch(
            "media_summarizer.core.media_ingestion.adapters.orchestrators.sqs.send_message",
            mock_sqs_send,
        ), patch(
            "media_summarizer.core.media_ingestion.adapters.orchestrators.mark_user_media_submission",
            mock_mark_submission,
        ):
            orchestrator = ProcessingJobSubmissionOrchestrator(
                deepgram_transcription_queue="test-deepgram-queue",
            )

            outcome = await orchestrator.submit(command=command, resolved=resolved)

        assert outcome.status == ProcessingLifecycleStatus.TRANSCRIBING
        assert outcome.deduplicated is False
        assert outcome.metadata["social_video_transcription_enqueued"] is True
        assert outcome.metadata["pipeline_enqueued"] is True
        assert outcome.metadata["media_family"] == "social_video"
        assert outcome.metadata["source_platform"] == "instagram"

    @pytest.mark.asyncio
    async def test_x_dispatch_unchanged(self):
        """X (Twitter) dispatch path remains unaffected by the SOCIAL_VIDEO case."""
        resolved = ResolvedMedia(
            media_key="x:tweet:12345",
            normalized_url="https://x.com/user/status/12345",
            media_family=MediaFamily.SOCIAL_VIDEO,
            media_type=MediaType.SHORT_VIDEO,
            source_platform=SourcePlatform.X,
            resolver_key="x.default",
            metadata={"tweet_id": "12345"},
        )
        command = IngestUrlCommand(
            user=UserContext(user_id="user-001", user_email="test@example.com"),
            request=IngestUrlRequest(url="https://x.com/user/status/12345"),
        )

        mock_sqs_send = AsyncMock()
        mock_create_job = AsyncMock()
        mock_update_job = AsyncMock()
        mock_reserve = AsyncMock(return_value=True)
        mock_already_processed = AsyncMock(return_value=None)
        mock_mark_submission = AsyncMock()

        with patch(
            "media_summarizer.core.media_ingestion.adapters.orchestrators.episode_idempotence.already_processed",
            mock_already_processed,
        ), patch(
            "media_summarizer.core.media_ingestion.adapters.orchestrators.episode_idempotence.reserve_or_skip",
            mock_reserve,
        ), patch(
            "media_summarizer.core.media_ingestion.adapters.orchestrators.database_async.create_processing_job",
            mock_create_job,
        ), patch(
            "media_summarizer.core.media_ingestion.adapters.orchestrators.database_async.update_processing_job",
            mock_update_job,
        ), patch(
            "media_summarizer.core.media_ingestion.adapters.orchestrators.sqs.send_message",
            mock_sqs_send,
        ), patch(
            "media_summarizer.core.media_ingestion.adapters.orchestrators.mark_user_media_submission",
            mock_mark_submission,
        ):
            orchestrator = ProcessingJobSubmissionOrchestrator(
                x_ingestion_queue="test-x-queue",
            )

            outcome = await orchestrator.submit(command=command, resolved=resolved)

        # X dispatch goes to X queue, not Deepgram
        mock_sqs_send.assert_called_once()
        call_kwargs = mock_sqs_send.call_args[1]
        assert call_kwargs["queue_name"] == "test-x-queue"
        assert outcome.metadata["x_ingestion_enqueued"] is True
        assert outcome.metadata["social_video_transcription_enqueued"] is False

    @pytest.mark.asyncio
    async def test_tiktok_not_intercepted_by_social_video_path(self):
        """TikTok resolved media (no audio_url) does NOT match the SOCIAL_VIDEO + audio_url case.

        TikTok resolver returns media_family=SOCIAL_VIDEO but audio_url=None, so
        it should NOT be intercepted by the new social video dispatch condition.
        This test verifies that TikTok still reaches its own dispatch branch
        (resolver_key == "tiktok.default") rather than the SOCIAL_VIDEO + audio_url path.

        Note: The TikTok branch calls job.mark_extracting() which is a pre-existing
        missing method on ProcessingJob. This test patches it to verify routing logic.
        """
        from media_summarizer.core.models import ProcessingJob

        resolved = ResolvedMedia(
            media_key="tiktok:video:67890",
            normalized_url="https://www.tiktok.com/@user/video/67890",
            media_family=MediaFamily.SOCIAL_VIDEO,
            media_type=MediaType.SHORT_VIDEO,
            source_platform=SourcePlatform.TIKTOK,
            resolver_key="tiktok.default",
            metadata={"extraction_mode": "queued_worker"},
        )
        command = IngestUrlCommand(
            user=UserContext(user_id="user-001", user_email="test@example.com"),
            request=IngestUrlRequest(
                url="https://www.tiktok.com/@user/video/67890"
            ),
        )

        mock_sqs_send = AsyncMock()
        mock_create_job = AsyncMock()
        mock_update_job = AsyncMock()
        mock_reserve = AsyncMock(return_value=True)
        mock_already_processed = AsyncMock(return_value=None)
        mock_mark_submission = AsyncMock()

        with patch(
            "media_summarizer.core.media_ingestion.adapters.orchestrators.episode_idempotence.already_processed",
            mock_already_processed,
        ), patch(
            "media_summarizer.core.media_ingestion.adapters.orchestrators.episode_idempotence.reserve_or_skip",
            mock_reserve,
        ), patch(
            "media_summarizer.core.media_ingestion.adapters.orchestrators.database_async.create_processing_job",
            mock_create_job,
        ), patch(
            "media_summarizer.core.media_ingestion.adapters.orchestrators.database_async.update_processing_job",
            mock_update_job,
        ), patch(
            "media_summarizer.core.media_ingestion.adapters.orchestrators.sqs.send_message",
            mock_sqs_send,
        ), patch(
            "media_summarizer.core.media_ingestion.adapters.orchestrators.mark_user_media_submission",
            mock_mark_submission,
        ), patch.object(
            ProcessingJob, "mark_extracting", create=True, new_callable=lambda: MagicMock
        ):
            orchestrator = ProcessingJobSubmissionOrchestrator(
                tiktok_ingestion_queue="test-tiktok-queue",
            )

            outcome = await orchestrator.submit(command=command, resolved=resolved)

        # TikTok dispatch goes to TikTok queue, not Deepgram
        mock_sqs_send.assert_called_once()
        call_kwargs = mock_sqs_send.call_args[1]
        assert call_kwargs["queue_name"] == "test-tiktok-queue"
        assert outcome.metadata["tiktok_ingestion_enqueued"] is True
        assert outcome.metadata["social_video_transcription_enqueued"] is False
