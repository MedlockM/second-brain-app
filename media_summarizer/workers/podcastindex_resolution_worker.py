"""
Worker dedicated to PodcastIndex URL-to-audio resolution.

This worker consumes `podcastindex-resolution-queue`, resolves an audio enclosure URL,
then forwards the job to `deepgram-transcription-queue`.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
from io import BytesIO

from media_summarizer.core.media_ingestion.adapters.podcast_resolver_foundation import (
    DEFAULT_PODCAST_RESOLUTION_FAILED_MESSAGE,
    PodcastResolutionStatus,
    PodcastResolverErrorCode,
    normalize_podcast_source_url,
)
from media_summarizer.core.media_ingestion.domain import SourcePlatform
from media_summarizer.core.media_ingestion.title_derivation import derive_media_title
from media_summarizer.core.services import audio_quota_gate
from media_summarizer.core.services.transcript_formatting import (
    count_paragraphs,
    normalize_transcript_text,
)
from media_summarizer.utils import database_async, s3, sqs
from media_summarizer.utils.env import required_env
from media_summarizer.utils.logging_config import (
    bind_log_context,
    log_event,
    reset_log_context,
    setup_logging,
)
from media_summarizer.utils.rss_transcript import fetch_rss_transcript
from media_summarizer.workers.base_worker import (
    get_sqs_receive_params,
    process_message_with_retry,
)
from media_summarizer.workers.podcast_platform_resolvers import (
    build_worker_podcast_platform_resolver_registry,
)

logger = logging.getLogger(__name__)

PODCASTINDEX_RESOLUTION_QUEUE = required_env("PODCASTINDEX_RESOLUTION_QUEUE")
DEEPGRAM_TRANSCRIPTION_QUEUE = required_env("DEEPGRAM_TRANSCRIPTION_QUEUE")
TRANSCRIPT_BUCKET = required_env("TRANSCRIPT_BUCKET")
EPISODE_COMPLETED_EVENTS_QUEUE = required_env("EPISODE_COMPLETED_EVENTS_QUEUE")
PODCASTINDEX_MAX_RETRIES = max(1, int(os.environ.get("PODCASTINDEX_MAX_RETRIES", "3")))
PODCASTINDEX_WORKER_MAX_RETRIES = max(
    1, int(os.environ.get("PODCASTINDEX_WORKER_MAX_RETRIES", "3"))
)
PODCASTINDEX_EPISODE_CANDIDATES = max(
    1, int(os.environ.get("PODCASTINDEX_EPISODE_CANDIDATES", "50"))
)
_SUPPORTED_WORKER_PODCAST_PLATFORMS = {
    SourcePlatform.SPOTIFY,
    SourcePlatform.APPLE_PODCASTS,
    SourcePlatform.DEEZER,
    SourcePlatform.RSS,
}

_PODCAST_PLATFORM_RESOLVER_REGISTRY = build_worker_podcast_platform_resolver_registry(
    max_retries=PODCASTINDEX_MAX_RETRIES,
    episode_candidates=PODCASTINDEX_EPISODE_CANDIDATES,
)


def _source_platform_from_message_value(value: str) -> SourcePlatform:
    normalized = (value or "").strip().lower()
    try:
        return SourcePlatform(normalized)
    except ValueError:
        return SourcePlatform.UNKNOWN


async def _resolve_audio_url(message_body: dict) -> dict:
    normalized_url = (message_body.get("normalized_url") or "").strip()
    source_platform = _source_platform_from_message_value(
        message_body.get("source_platform") or "unknown"
    )

    if not normalized_url:
        raise ValueError("Missing normalized_url in podcastindex resolution message.")

    try:
        descriptor = normalize_podcast_source_url(
            normalized_url=normalized_url,
            source_platform=source_platform,
        )
    except ValueError as exc:
        error_code = (
            PodcastResolverErrorCode.INVALID_PLATFORM_URL
            if source_platform in _SUPPORTED_WORKER_PODCAST_PLATFORMS
            else PodcastResolverErrorCode.UNSUPPORTED_PLATFORM
        )
        raise RuntimeError(
            f"{DEFAULT_PODCAST_RESOLUTION_FAILED_MESSAGE} "
            f"code={error_code.value}"
        ) from exc

    try:
        resolver = _PODCAST_PLATFORM_RESOLVER_REGISTRY.get(descriptor.source_platform)
    except ValueError as exc:
        raise RuntimeError(
            f"{DEFAULT_PODCAST_RESOLUTION_FAILED_MESSAGE} "
            f"code={PodcastResolverErrorCode.UNSUPPORTED_PLATFORM.value}"
        ) from exc

    outcome = await resolver.resolve(descriptor=descriptor)
    if outcome.status != PodcastResolutionStatus.RESOLVED or not outcome.audio_url:
        code = (
            outcome.error_code.value
            if outcome.error_code
            else PodcastResolverErrorCode.AUDIO_URL_NOT_FOUND.value
        )
        raise RuntimeError(
            f"{DEFAULT_PODCAST_RESOLUTION_FAILED_MESSAGE} code={code}"
        )

    return {
        "audio_url": outcome.audio_url,
        "episode_title": outcome.metadata.get("episode_title")
        or outcome.title
        or "Podcast episode",
        "podcast_title": outcome.metadata.get("podcast_title") or "Podcast",
        "episode_image": outcome.metadata.get("episode_image") or "",
        "episode_date_published": int(outcome.metadata.get("episode_date_published") or 0),
        "audio_duration_seconds": int(outcome.metadata.get("audio_duration_seconds") or 0),
        "feed_id": outcome.metadata.get("feed_id"),
        "feed_url": (outcome.metadata.get("feed_url") or "").strip(),
        "episode_guid": (outcome.metadata.get("episode_guid") or "").strip(),
    }


async def _try_rss_transcript_short_circuit(
    *,
    job,
    body: dict,
    resolution: dict,
) -> bool:
    """
    Attempt to fetch a pre-existing transcript from the RSS feed's
    <podcast:transcript> tag (Podcasting 2.0 spec).

    Returns True if the short-circuit succeeded (job completed inline),
    False if we should fall back to the Deepgram path.
    """
    feed_url = resolution.get("feed_url") or ""
    episode_guid = resolution.get("episode_guid") or ""

    if not feed_url:
        log_event(
            logger,
            logging.DEBUG,
            "transcription.transcript_short_circuit_skipped",
            "No feed_url available for RSS transcript lookup",
            job_id=job.id,
            reason="no_feed_url",
        )
        return False

    if not episode_guid:
        log_event(
            logger,
            logging.DEBUG,
            "transcription.transcript_short_circuit_skipped",
            "No episode_guid available for RSS transcript lookup",
            job_id=job.id,
            reason="no_guid",
        )
        return False

    try:
        transcript_text = await fetch_rss_transcript(
            feed_url=feed_url,
            episode_guid=episode_guid,
        )
    except Exception as exc:
        log_event(
            logger,
            logging.DEBUG,
            "transcription.transcript_short_circuit_skipped",
            "fetch_rss_transcript raised an exception",
            job_id=job.id,
            reason="fetch_failed",
            error=str(exc),
        )
        return False

    if not transcript_text or not transcript_text.strip():
        log_event(
            logger,
            logging.DEBUG,
            "transcription.transcript_short_circuit_skipped",
            "RSS transcript tag absent or returned empty payload",
            job_id=job.id,
            reason="tag_absent",
        )
        return False

    # Upload transcript to S3. `fetch_rss_transcript` already normalized the
    # text; the normalizer is idempotent, so this is a defensive pass-through
    # for any transcript shape (task-231 option B).
    normalized_text = normalize_transcript_text(transcript_text, source="rss")
    transcript_s3_key = f"{job.id}.txt"
    transcript_bytes = normalized_text.encode("utf-8")
    await s3.upload_file_object(
        bucket=TRANSCRIPT_BUCKET,
        key=transcript_s3_key,
        file_obj=BytesIO(transcript_bytes),
        content_type="text/plain",
        metadata={
            "content-type": "text/plain",
            "job-type": "podcast-transcription",
            "provider": "podcasting_2.0",
        },
    )

    # Update job metadata and mark completed
    transcription_metadata = {
        "provider": "podcasting_2.0",
        "transcript_format": "txt",
        "source_detail": "rss_podcast_transcript_tag",
        "language": None,
        "segments_count": count_paragraphs(normalized_text),
        "duration_seconds": 0,
    }

    job.set_transcription_location(transcript_s3_key)
    job.set_transcription_metadata(transcription_metadata)
    job.mark_completed()
    await database_async.update_processing_job(job)

    # Publish success event
    await sqs.send_message(
        queue_name=EPISODE_COMPLETED_EVENTS_QUEUE,
        message_body={
            "event_type": "episode_completion_status",
            "status": "success",
            "media_key": body.get("media_key"),
            "canonical_job_id": job.id,
            "transcription_s3_key": transcript_s3_key,
            "transcription_metadata": transcription_metadata,
        },
    )

    log_event(
        logger,
        logging.INFO,
        "transcription.completed_inline",
        "Podcast transcript fetched from RSS feed (Podcasting 2.0 short-circuit)",
        job_id=job.id,
        media_item_id=job.id,
        transcript_source="podcasting_2.0",
        feed_url=feed_url,
        episode_guid=episode_guid,
    )

    return True


async def process_message(message: dict) -> None:
    if message is None:
        raise ValueError("Message is None")

    body = json.loads(message["Body"]) if "Body" in message else message
    job_id = body.get("job_id")
    if not job_id:
        raise ValueError("Missing required field: job_id")

    context_token = bind_log_context(
        job_id=job_id,
        media_item_id=job_id,
        queue=PODCASTINDEX_RESOLUTION_QUEUE,
        resolver_key=body.get("resolver_key") or "podcast.default",
        source_platform=body.get("source_platform"),
    )

    try:
        job = await database_async.get_processing_job_by_id(job_id)
        if not job:
            raise ValueError(f"Job not found for id={job_id}")

        # Keep extracting stage explicit when this worker starts handling the job.
        if job.status.value == "pending":
            job.mark_extracting()
            await database_async.update_processing_job(job)

        resolution = await _resolve_audio_url(body)
        audio_url = resolution.get("audio_url")
        if not audio_url:
            raise RuntimeError("PodcastIndex resolution returned no audio URL.")

        # The episode title the index returned, else whatever the job already
        # holds, else the deterministic label -- never the bare word "Podcast
        # episode", which was the same string for every unresolved episode
        # (task-266).
        episode_title = derive_media_title(
            [resolution.get("episode_title"), job.title],
            media_type="podcast_episode",
            source_platform=job.source_platform,
            site_names=[resolution.get("podcast_title")],
        )
        podcast_title = resolution.get("podcast_title") or "Podcast"
        episode_image = resolution.get("episode_image") or job.media_image or ""

        job.media_url = audio_url
        job.title = episode_title
        job.media_image = resolution.get("episode_image") or job.media_image
        if resolution.get("episode_date_published"):
            job.media_date_published = int(resolution["episode_date_published"])
        await database_async.update_processing_job(job)

        # --- Podcasting 2.0 transcript short-circuit (primary path) ---
        # Attempt to fetch a pre-existing transcript from the RSS feed before
        # paying for Deepgram audio transcription.
        short_circuited = await _try_rss_transcript_short_circuit(
            job=job,
            body=body,
            resolution=resolution,
        )
        if short_circuited:
            return

        # --- Quota gate ---
        # Last chance to refuse before spending Deepgram minutes. The episode
        # duration usually comes from the podcast index; when it does not, the
        # gate falls back to an HTTP Range probe on the enclosure and, failing
        # that, to a provisional minute settled after transcription.
        gate = await audio_quota_gate.gate_audio_transcription(
            job_id=job.id,
            user_id=body.get("user_id"),
            job=job,
            media_key=body.get("media_key"),
            audio_url=audio_url,
            known_duration_seconds=int(resolution.get("audio_duration_seconds") or 0),
            error_step="podcast_resolution",
        )
        if not gate.allowed:
            return

        # --- Fallback: enqueue to Deepgram for audio transcription ---
        await sqs.send_message(
            queue_name=DEEPGRAM_TRANSCRIPTION_QUEUE,
            message_body={
                "job_id": job.id,
                "user_id": body.get("user_id"),
                "user_email": body.get("user_email"),
                "audio_url": audio_url,
                "episode_title": episode_title,
                "podcast_title": podcast_title,
                "media_key": body.get("media_key"),
                "normalized_url": body.get("normalized_url"),
                "episode_image": episode_image,
                "audio_duration_seconds": gate.duration_seconds,
                "quota_debited_minutes": gate.debited_minutes,
                "quota_debit_skipped": gate.debit_skipped,
                "deepgram_mode": "pull",
            },
        )

        log_event(
            logger,
            logging.INFO,
            "transcription.enqueued",
            "Podcast resolution completed and queued for Deepgram",
            job_id=job.id,
            media_item_id=job.id,
            queue=DEEPGRAM_TRANSCRIPTION_QUEUE,
            transcript_source="deepgram",
            audio_duration_seconds=gate.duration_seconds,
            quota_debited_minutes=gate.debited_minutes,
        )
    finally:
        reset_log_context(context_token)


async def process_messages_batch(messages: list[dict]) -> None:
    async def process_one(message: dict) -> bool:
        return await process_message_with_retry(
            message=message,
            processor=process_message,
            queue_name=PODCASTINDEX_RESOLUTION_QUEUE,
            max_retries=PODCASTINDEX_WORKER_MAX_RETRIES,
            worker_name="podcastindex-resolution",
        )

    tasks = [asyncio.create_task(process_one(message)) for message in messages]
    await asyncio.gather(*tasks, return_exceptions=True)


async def poll_queue() -> None:
    while True:
        try:
            receive_params = get_sqs_receive_params(visibility_timeout=300)
            messages = await sqs.receive_messages(
                queue_name=PODCASTINDEX_RESOLUTION_QUEUE,
                max_messages=receive_params["MaxNumberOfMessages"],
                wait_time_seconds=receive_params["WaitTimeSeconds"],
                visibility_timeout=receive_params["VisibilityTimeout"],
            )
            if messages:
                await process_messages_batch(messages)
            else:
                await asyncio.sleep(1)
        except Exception as exc:
            log_event(
                logger,
                logging.ERROR,
                "worker.polling_error",
                "Podcast resolution polling failed",
                queue=PODCASTINDEX_RESOLUTION_QUEUE,
                exc_info=exc,
            )
            await asyncio.sleep(5)


async def main() -> None:
    setup_logging("podcastindex-resolution-worker")
    log_event(
        logger,
        logging.INFO,
        "worker.started",
        "Starting podcast resolution worker",
        queue=PODCASTINDEX_RESOLUTION_QUEUE,
    )
    await poll_queue()


if __name__ == "__main__":
    asyncio.run(main())
