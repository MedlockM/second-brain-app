"""
Worker de transcription utilisant Whisper Large pour convertir l'audio en texte.

Migrated to use the new utils for S3 and SQS operations instead of direct AWS libraries.
"""

import asyncio
import json
import logging
from math import ceil
import os
from pathlib import Path
import tempfile
import time
from typing import Dict, Any

import whisper

from media_summarizer.utils import s3, sqs
from media_summarizer.workers.base_worker import process_message_with_retry

# Re-export commonly patched attributes for test compatibility
from media_summarizer.utils.sqs import session as _aio_session  # type: ignore
from media_summarizer.utils.sqs import AWS_ENDPOINT_URL as AWS_ENDPOINT_URL  # type: ignore
from media_summarizer.utils.sqs import AWS_REGION as AWS_REGION  # type: ignore


# Provide a compat shim exposing .client(...) to mirror aiobotocore session usage in tests
class _SessionShim:
    def __init__(self, aio_session):
        self._s = aio_session

    def client(self, *args, **kwargs):
        return self._s.create_client(*args, **kwargs)


session = _SessionShim(_aio_session)
from media_summarizer.core.utils.whisper_async import transcribe_async

# Configuration du logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Configuration
AUDIO_BUCKET = os.environ.get("AUDIO_BUCKET", "media-summarizer-audio")
EPISODE_COMPLETION_EVENTS_QUEUE = os.environ.get(
    "EPISODE_COMPLETION_EVENTS_QUEUE", "episode-completion-events"
)
TRANSCRIPT_BUCKET = os.environ.get(
    "TRANSCRIPT_BUCKET", "media-summarizer-transcriptions"
)
TRANSCRIPTION_QUEUE = os.environ.get("TRANSCRIPTION_QUEUE", "transcription-queue")
MAX_RETRIES = 3
TEST_MODE = os.environ.get("TEST_MODE", "false").lower() == "true"
RETRY_BASE_DELAY = 0.01 if TEST_MODE else 1  # secondes

# Heartbeat/visibility settings
HEARTBEAT_INTERVAL = float(os.environ.get("HEARTBEAT_INTERVAL", "60"))
TRANSCRIPTION_VISIBILITY_TIMEOUT = int(
    os.environ.get("TRANSCRIPTION_VISIBILITY_TIMEOUT", "1800")
)

# Whisper model configuration
WHISPER_MODEL = os.environ.get("WHISPER_MODEL", "tiny" if TEST_MODE else "large")


async def download_audio_file(audio_s3_key: str, local_path: str) -> None:
    """
    Download audio file from S3 to local path using utils.

    Args:
        audio_s3_key: S3 key for the audio file
        local_path: Local path where to save the audio file
    """
    try:
        await s3.download_file(
            bucket=AUDIO_BUCKET, key=audio_s3_key, file_path=local_path
        )
        logger.info(
            f"Downloaded audio file from s3://{AUDIO_BUCKET}/{audio_s3_key} to {local_path}"
        )

    except Exception as e:
        logger.error(f"Failed to download audio file: {str(e)}")
        raise


async def upload_transcription(transcript_s3_key: str, transcription_text: str) -> None:
    """
    Upload transcription text to S3 using utils.

    Args:
        transcript_s3_key: S3 key for the transcription file
        transcription_text: The transcription content
    """
    try:
        # Create a file-like object from the transcription text
        from io import BytesIO

        transcript_bytes = transcription_text.encode("utf-8")
        transcript_file = BytesIO(transcript_bytes)

        await s3.upload_file_object(
            bucket=TRANSCRIPT_BUCKET,
            key=transcript_s3_key,
            file_obj=transcript_file,
            content_type="text/plain",
            metadata={
                "content-type": "text/plain",
                "job-type": "podcast-transcription",
            },
        )

        logger.info(
            f"Uploaded transcription to s3://{TRANSCRIPT_BUCKET}/{transcript_s3_key}"
        )

    except Exception as e:
        logger.error(f"Failed to upload transcription: {str(e)}")
        raise


async def process_transcription_message(message_body: Dict[str, Any]) -> None:
    """
    Process a single transcription message.

    Args:
        message_body: The message body containing job information
    """
    job_id = message_body.get("job_id")
    # Accept both key variants used across tests
    audio_s3_key = message_body.get("audio_s3_key") or message_body.get("s3_audio_key")

    if not all([job_id, audio_s3_key]):
        logger.error(f"Missing required fields in message: {message_body}")
        raise ValueError("Missing required fields in transcription message")

    # Ensure all required fields are strings
    if not isinstance(job_id, str) or not isinstance(audio_s3_key, str):
        logger.error(f"Invalid field types in message: {message_body}")
        raise ValueError("Invalid field types in transcription message")

    logger.info(f"Starting transcription for job {job_id}")

    # Update job status to transcribing
    from media_summarizer.utils import database_async

    job = await database_async.get_processing_job_by_id(job_id)
    if job:
        job.mark_transcribing()
        await database_async.update_processing_job(job)

    # Create temporary directory for audio processing
    with tempfile.TemporaryDirectory() as temp_dir:
        # Download audio file
        audio_filename = f"{job_id}_audio.mp3"
        local_audio_path = Path(temp_dir) / audio_filename

        logger.info(f"Downloading audio for job {job_id}")
        await download_audio_file(audio_s3_key, str(local_audio_path))

        # Verify audio file exists and has content
        if not local_audio_path.exists() or local_audio_path.stat().st_size == 0:
            raise ValueError("Downloaded audio file is empty or missing")

        # Transcribe audio
        logger.info(
            f"Starting transcription for job {job_id} using Whisper {WHISPER_MODEL}"
        )
        start_time = time.time()

        # Use async transcription to avoid blocking
        transcription_result = await transcribe_async(
            audio_path=str(local_audio_path), model_name=WHISPER_MODEL
        )

        transcription_duration = time.time() - start_time
        logger.info(
            f"Transcription completed for job {job_id} in {transcription_duration:.2f} seconds"
        )

        # Extract transcription text
        if isinstance(transcription_result, dict):
            transcription_text = transcription_result.get("text", "")
            segments = transcription_result.get("segments", [])
            language = transcription_result.get("language", "unknown")
        else:
            # Fallback for simple string result
            transcription_text = str(transcription_result)
            segments = []
            language = "unknown"

        if not transcription_text or len(transcription_text.strip()) == 0:
            raise ValueError("Transcription resulted in empty text")

        # Upload transcription to S3
        transcript_s3_key = f"{job_id}.txt"
        logger.info(f"Uploading transcription for job {job_id}")
        await upload_transcription(transcript_s3_key, transcription_text)

        transcription_metadata = {
            "provider": "whisper",
            "language": language,
            "duration_seconds": transcription_duration,
            "segments_count": len(segments),
            "audio_s3_key": audio_s3_key,
            "model_used": WHISPER_MODEL,
            "transcribed_at": time.strftime(
                "%Y-%m-%dT%H:%M:%SZ", time.gmtime()
            ),
        }

        # Update job with transcription location and duration
        if job:
            job.set_transcription_location(transcript_s3_key)
            job.set_transcription_metadata(transcription_metadata)
            job.set_processing_duration(
                "transcription", int(transcription_duration)
            )
            await database_async.update_processing_job(job)

        # Publish completion event directly: automatic pipeline ends at transcription.
        audio_duration_seconds_raw = message_body.get("audio_duration_seconds")
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
                "media_key": message_body.get("media_key"),
                "canonical_job_id": job_id,
                "minutes_used": minutes_used,
                "transcription_s3_key": transcript_s3_key,
                "transcription_metadata": transcription_metadata,
            },
        )

        logger.info(f"Successfully completed transcription for job {job_id}")


async def process_message(message: Dict[str, Any]) -> None:
    """
    Process an SQS message for transcription with heartbeat to extend visibility.

    Args:
        message: SQS message containing job information
    """
    receipt_handle = message.get("ReceiptHandle")
    heartbeat_task = None

    async def _heartbeat_loop():
        try:
            # Initial immediate extension to ensure a fresh window
            await sqs.change_message_visibility(
                queue_name=TRANSCRIPTION_QUEUE,
                receipt_handle=receipt_handle,
                timeout_seconds=TRANSCRIPTION_VISIBILITY_TIMEOUT,
            )
            while True:
                await asyncio.sleep(HEARTBEAT_INTERVAL)
                await sqs.change_message_visibility(
                    queue_name=TRANSCRIPTION_QUEUE,
                    receipt_handle=receipt_handle,
                    timeout_seconds=TRANSCRIPTION_VISIBILITY_TIMEOUT,
                )
        except asyncio.CancelledError:
            # Graceful shutdown of heartbeat
            pass
        except Exception as e:
            # Log but do not interrupt main processing
            logger.warning(f"Heartbeat failed to extend visibility: {e}")

    try:
        # Parse message body
        body = json.loads(message.get("Body", "{}"))

        # Start heartbeat if we have a receipt handle
        if receipt_handle:
            heartbeat_task = asyncio.create_task(_heartbeat_loop())

        # Process the transcription
        await process_transcription_message(body)

        # After success, delete message (done by poller loop) and exit
    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse message body: {str(e)}")
        raise
    except Exception as e:
        # Publish a failure event so watchers are unblocked
        try:
            # body may be undefined if parsing failed; guard accordingly
            try:
                b = body if isinstance(body, dict) else {}
            except Exception:
                b = {}
            media_key = b.get("media_key")
            job_id = b.get("job_id")
            if job_id:
                await sqs.send_message(
                    queue_name=EPISODE_COMPLETION_EVENTS_QUEUE,
                    message_body={
                        "event_type": "episode_completion_status",
                        "status": "failure",
                        "media_key": media_key,
                        "canonical_job_id": job_id,
                        "reason": f"transcription_failed: {str(e)}",
                    },
                )
        except Exception as ee:
            logger.warning(f"Failed to publish failure event (transcription) for job {job_id}: {ee}")
        # Re-raise so retry/DLQ logic applies
        raise
    finally:
        if heartbeat_task:
            heartbeat_task.cancel()
            try:
                await heartbeat_task
            except asyncio.CancelledError:
                # Expected during normal shutdown of the heartbeat task
                pass
            except Exception:
                # Swallow any other heartbeat errors on shutdown
                pass


async def poll_queue() -> None:
    """
    Poll the SQS queue for transcription messages.
    """
    logger.info("Starting transcription worker - polling queue")

    while True:
        try:
            # Receive messages from the queue
            messages = await sqs.receive_messages(
                queue_name=TRANSCRIPTION_QUEUE,
                max_messages=1,  # Process one at a time for Whisper
                wait_time_seconds=20,  # Long polling
                visibility_timeout=TRANSCRIPTION_VISIBILITY_TIMEOUT,
            )

            if messages:
                logger.info(f"Received {len(messages)} messages")

                # Process messages one by one
                for message in messages:
                    # Use base_worker retry logic which handles retries, logging, and DLQ/Failure
                    await process_message_with_retry(
                        message=message,
                        processor=process_message,
                        queue_name=TRANSCRIPTION_QUEUE,
                        max_retries=3,
                        worker_name="transcription"
                    )

            # Small delay to prevent excessive API calls
            await asyncio.sleep(1)

        except Exception as e:
            logger.error(f"Error polling transcription queue: {str(e)}")
            # Wait before retrying
            await asyncio.sleep(5)


async def main() -> None:
    """
    Main entry point for the transcription worker.
    """
    logger.info("Starting transcription worker")
    logger.info(f"Using Whisper model: {WHISPER_MODEL}")
    logger.info(f"Audio bucket: {AUDIO_BUCKET}")
    logger.info(f"Transcript bucket: {TRANSCRIPT_BUCKET}")

    await poll_queue()


if __name__ == "__main__":
    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    asyncio.run(main())
