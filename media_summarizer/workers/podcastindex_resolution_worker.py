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

from media_summarizer.core.media_ingestion.adapters.podcast_resolver_foundation import (
    DEFAULT_PODCAST_RESOLUTION_FAILED_MESSAGE,
    PodcastResolutionStatus,
    PodcastResolverErrorCode,
    normalize_podcast_source_url,
)
from media_summarizer.core.media_ingestion.domain import SourcePlatform
from media_summarizer.utils import database_async, sqs
from media_summarizer.utils.logging_config import (
    bind_log_context,
    log_event,
    reset_log_context,
    setup_logging,
)
from media_summarizer.workers.podcast_platform_resolvers import (
    build_worker_podcast_platform_resolver_registry,
)
from media_summarizer.workers.base_worker import (
    get_sqs_receive_params,
    process_message_with_retry,
)

logger = logging.getLogger(__name__)

PODCASTINDEX_RESOLUTION_QUEUE = os.environ.get(
    "PODCASTINDEX_RESOLUTION_QUEUE", "podcastindex-resolution-queue"
)
DEEPGRAM_TRANSCRIPTION_QUEUE = os.environ.get(
    "DEEPGRAM_TRANSCRIPTION_QUEUE", "deepgram-transcription-queue"
)
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
    }


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

        # Keep resolving stage explicit when this worker starts handling the job.
        if job.status.value == "pending":
            job.mark_started()
            await database_async.update_processing_job(job)

        resolution = await _resolve_audio_url(body)
        audio_url = resolution.get("audio_url")
        if not audio_url:
            raise RuntimeError("PodcastIndex resolution returned no audio URL.")

        job.episode_url = audio_url
        job.podcast_title = resolution.get("podcast_title") or job.podcast_title
        job.episode_title = resolution.get("episode_title") or job.episode_title
        job.episode_image = resolution.get("episode_image") or job.episode_image
        if resolution.get("episode_date_published"):
            job.episode_date_published = int(resolution["episode_date_published"])
        await database_async.update_processing_job(job)

        await sqs.send_message(
            queue_name=DEEPGRAM_TRANSCRIPTION_QUEUE,
            message_body={
                "job_id": job.id,
                "user_id": body.get("user_id"),
                "user_email": body.get("user_email"),
                "audio_url": audio_url,
                "episode_title": job.episode_title or "Podcast episode",
                "podcast_title": job.podcast_title or "Podcast",
                "media_key": body.get("media_key"),
                "normalized_url": body.get("normalized_url"),
                "episode_image": job.episode_image or "",
                "audio_duration_seconds": resolution.get("audio_duration_seconds") or 0,
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
