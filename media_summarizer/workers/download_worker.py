"""
Worker de téléchargement audio pour récupérer les fichiers MP3 des podcasts.

Before downloading audio, this worker checks for a pre-existing transcript
in the RSS feed using the Podcasting 2.0 <podcast:transcript> standard.
If a usable transcript is found, it skips audio download and Deepgram entirely.
"""

import asyncio
import json
import logging
import os
import tempfile
import time
from io import BytesIO
from math import ceil
from pathlib import Path

import httpx
from media_summarizer.utils import s3, sqs
from media_summarizer.utils.logging_config import bind_log_context, log_event, reset_log_context, setup_logging
from media_summarizer.utils.rss_transcript import fetch_rss_transcript
from media_summarizer.workers.base_worker import (
    process_message_with_retry,
    get_sqs_receive_params,
)

logger = logging.getLogger(__name__)

# Backward-compatibility helpers expected by some tests
# Not used by the new utils-based implementation, but kept for patchability in tests


def get_s3_client():
    import boto3

    return boto3.client(
        "s3",
        region_name=os.environ.get("AWS_REGION", "us-east-1"),
    )


def get_sqs_client():
    import boto3

    return boto3.client(
        "sqs",
        region_name=os.environ.get("AWS_REGION", "us-east-1"),
    )


# Configuration des buckets S3
AUDIO_BUCKET = os.environ.get("AUDIO_BUCKET", "media-summarizer-audio")
TRANSCRIPT_BUCKET = os.environ.get(
    "TRANSCRIPT_BUCKET", "media-summarizer-transcriptions"
)
DOWNLOAD_QUEUE = os.environ.get("AUDIO_DOWNLOAD_QUEUE", "audio-download-queue")
DEEPGRAM_TRANSCRIPTION_QUEUE = os.environ.get(
    "DEEPGRAM_TRANSCRIPTION_QUEUE", "deepgram-transcription-queue"
)
EPISODE_COMPLETION_EVENTS_QUEUE = os.environ.get(
    "EPISODE_COMPLETION_EVENTS_QUEUE", "episode-completion-events"
)
SEARCH_INDEXING_QUEUE = os.environ.get("SEARCH_INDEXING_QUEUE", "search-indexing-queue")


async def download_audio(url, output_path):
    """Télécharge un fichier audio depuis une URL."""
    try:
        async with httpx.AsyncClient(timeout=60.0, follow_redirects=True) as client:
            async with client.stream("GET", url) as response:
                response.raise_for_status()

                with open(output_path, "wb") as f:
                    async for chunk in response.aiter_bytes():
                        f.write(chunk)
    except Exception as e:
        # Re-raise the exception to be handled by the caller
        raise e


async def process_message(message):
    """Traite un message de la file SQS pour le téléchargement audio.

    Publie un événement episode_completion_status(status=failure) en cas d'erreur pour débloquer les watchers.
    """
    body = {}
    job_id = "unknown"

    # Handle both direct message body and SQS message format
    if message is None:
        raise ValueError("Message is None")

    if "Body" in message:
        # SQS message format
        try:
            body = json.loads(message["Body"])
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON in message body: {str(e)}")
    else:
        # Direct message format (for testing)
        body = message

    # Check required fields
    if "job_id" not in body:
        raise ValueError("Missing required field: job_id")

    job_id = body["job_id"]

    if "audio_url" not in body:
        raise ValueError("Missing required field: audio_url")

    audio_url = body["audio_url"]

    # Check if audio_url is empty
    if not audio_url:
        raise ValueError("empty audio URL provided")

    # Update job status to downloading
    from media_summarizer.utils import database_async

    job = await database_async.get_processing_job_by_id(job_id)
    if job:
        job.mark_downloading()
        await database_async.update_processing_job(job)

    # --- Podcasting 2.0 RSS Transcript Check ---
    # Before downloading audio, attempt to retrieve a pre-existing transcript
    # from the RSS feed via the <podcast:transcript> tag (AC #1).
    feed_url = body.get("feed_url")
    episode_guid = body.get("episode_guid") or body.get("media_key")

    if feed_url and episode_guid:
        try:
            rss_transcript = await fetch_rss_transcript(
                feed_url=feed_url,
                episode_guid=episode_guid,
            )
        except Exception as e:
            logger.warning(
                "RSS transcript fetch failed for job %s, falling back to audio: %s",
                job_id,
                str(e),
            )
            rss_transcript = None

        if rss_transcript:
            # Transcript found from RSS -- skip audio download and Deepgram (AC #2 fallback not needed)
            log_event(
                logger,
                logging.INFO,
                "worker.download.rss_transcript_found",
                "RSS transcript found via Podcasting 2.0 -- skipping audio download",
                job_id=job_id,
                transcript_source="rss_feed",
            )

            # Upload transcript to S3
            transcript_s3_key = f"{job_id}.txt"
            transcript_bytes = rss_transcript.encode("utf-8")
            await s3.upload_file_object(
                bucket=TRANSCRIPT_BUCKET,
                key=transcript_s3_key,
                file_obj=BytesIO(transcript_bytes),
                content_type="text/plain",
                metadata={
                    "content-type": "text/plain",
                    "job-type": "podcast-transcription",
                    "transcript-source": "rss-podcasting-2.0",
                },
            )

            # Update job status
            if job:
                job.mark_transcribing()
                job.set_transcription_location(transcript_s3_key)
                job.set_processing_duration("transcription", 0)
                await database_async.update_processing_job(job)

            # Publish completion event (same schema as Whisper/Deepgram workers)
            audio_duration_seconds_raw = body.get("audio_duration_seconds")
            try:
                audio_duration_seconds = int(float(audio_duration_seconds_raw))
            except (TypeError, ValueError):
                audio_duration_seconds = 0

            minutes_used = (
                max(1, ceil(audio_duration_seconds / 60))
                if audio_duration_seconds > 0
                else 1
            )

            await sqs.send_message(
                queue_name=EPISODE_COMPLETION_EVENTS_QUEUE,
                message_body={
                    "event_type": "episode_completion_status",
                    "status": "success",
                    "media_key": body.get("media_key"),
                    "canonical_job_id": job_id,
                    "minutes_used": minutes_used,
                    "transcription_s3_key": transcript_s3_key,
                    "transcription_metadata": {
                        "provider": "rss_feed",
                        "source": "podcasting_2.0",
                        "feed_url": feed_url,
                        "episode_guid": episode_guid,
                        "transcribed_at": time.strftime(
                            "%Y-%m-%dT%H:%M:%SZ", time.gmtime()
                        ),
                    },
                },
            )

            # Emit search indexing message for async transcript indexing
            try:
                await sqs.send_message(
                    queue_name=SEARCH_INDEXING_QUEUE,
                    message_body={
                        "media_item_id": job_id,
                        "user_id": body.get("user_id"),
                        "transcription_s3_key": transcript_s3_key,
                        "title": body.get("episode_title") or body.get("media_title"),
                        "source_platform": "audio",
                        "created_at": int(time.time()),
                    },
                )
            except Exception as search_err:
                logger.warning(f"Failed to emit search indexing message for job {job_id}: {search_err}")

            log_event(
                logger,
                logging.INFO,
                "worker.download.completed_via_rss",
                "Job completed via RSS transcript (no audio download needed)",
                job_id=job_id,
                transcript_source="rss_feed",
            )
            return
    else:
        log_event(
            logger,
            logging.DEBUG,
            "worker.download.no_feed_info",
            "No feed_url/episode_guid in message -- skipping RSS transcript check",
            job_id=job_id,
        )

    # --- Fallback: Audio Download + Deepgram Transcription (AC #2) ---
    log_event(logger, logging.INFO, "worker.download.started", "Audio download started", job_id=job_id, source_platform="audio")

    # Création d'un fichier temporaire pour le téléchargement
    with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as temp_file:
        temp_path = temp_file.name

    try:
        # Téléchargement du fichier audio
        await download_audio(audio_url, temp_path)

        # Get file size for metadata
        file_size = os.path.getsize(temp_path)

        # Upload vers S3
        s3_key = f"{job_id}.mp3"
        await s3.upload_file(AUDIO_BUCKET, s3_key, temp_path)

        # Update job with S3 location
        if job:
            job.set_audio_location(s3_key)
            await database_async.update_processing_job(job)

        # Envoi du message à la file de transcription
        next_message = {
            "job_id": job_id,
            "audio_s3_key": s3_key,
            "audio_url": audio_url,
            "user_id": body.get("user_id"),
            "episode_title": body.get("episode_title"),
            "podcast_title": body.get("podcast_title"),
            "media_key": body.get("media_key"),
            "normalized_url": body.get("normalized_url"),
            "episode_image": body.get("episode_image", ""),
            "audio_duration_seconds": body.get("audio_duration_seconds"),
            "success": True,
            "metadata": {"file_size_bytes": file_size},
        }

        # Send message to Deepgram transcription queue
        await sqs.send_message(
            queue_name=DEEPGRAM_TRANSCRIPTION_QUEUE, message_body=next_message
        )

        log_event(logger, logging.INFO, "worker.download.completed", "Audio download completed", job_id=job_id, transcript_source="deepgram")

    except Exception as e:
        log_event(logger, logging.ERROR, "worker.download.failed", "Audio download failed", job_id=job_id, error_type=type(e).__name__, error_code="DOWNLOAD_FAILED", exc_info=e)
        # Publish failure event to unblock watchers
        try:
            await sqs.send_message(
                queue_name=EPISODE_COMPLETION_EVENTS_QUEUE,
                message_body={
                    "event_type": "episode_completion_status",
                    "status": "failure",
                    "media_key": body.get("media_key"),
                    "canonical_job_id": job_id,
                    "reason": f"download_failed: {str(e)}",
                },
            )
        except Exception as ee:
            log_event(logger, logging.WARNING, "external_call.failed", "Failed to publish failure event", job_id=job_id, error_type=type(ee).__name__, provider="sqs")
        # Re-raise to trigger retry/DLQ logic
        raise
    finally:
        # Nettoyage du fichier temporaire (always cleanup)
        if os.path.exists(temp_path):
            os.unlink(temp_path)


async def process_messages_batch(messages):
    """Process multiple messages concurrently using base_worker retry logic."""
    # Limit concurrency to avoid overwhelming the system
    semaphore = asyncio.Semaphore(3)  # Max 3 concurrent downloads

    async def process_with_semaphore(message):
        async with semaphore:
            # Use base_worker retry logic which handles retries, logging, and DLQ/Failure
            return await process_message_with_retry(
                message=message,
                processor=process_message,
                queue_name=DOWNLOAD_QUEUE,
                max_retries=3,
                worker_name="download"
            )

    tasks = []
    for message in messages:
        task = asyncio.create_task(process_with_semaphore(message))
        tasks.append(task)

    # Process messages concurrently
    # We don't need to handle results manually as process_message_with_retry handles deletion/failure
    await asyncio.gather(*tasks, return_exceptions=True)


async def poll_queue():
    """Interroge la file SQS pour les nouveaux messages avec traitement par batch."""
    queue_name = DOWNLOAD_QUEUE

    while True:
        try:
            messages = await sqs.receive_messages(
                queue_name=queue_name,
                max_messages=5,  # Reduced for download worker
                wait_time_seconds=20,
                visibility_timeout=300,  # 5 minutes pour download
            )

            if messages:
                log_event(logger, logging.INFO, "worker.batch_received", "Processing download messages", queue=DOWNLOAD_QUEUE, message_count=len(messages))
                await process_messages_batch(messages)
            else:
                # Short sleep when no messages
                await asyncio.sleep(1)

        except Exception as e:
            log_event(logger, logging.ERROR, "worker.poll_error", "Download queue polling error", queue=DOWNLOAD_QUEUE, error_type=type(e).__name__, error_code="POLL_ERROR")
            await asyncio.sleep(5)


async def main():
    setup_logging("worker-download")
    log_event(logger, logging.INFO, "worker.started", "Download worker started", queue=DOWNLOAD_QUEUE)
    await poll_queue()


if __name__ == "__main__":
    asyncio.run(main())
