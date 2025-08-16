"""
Worker de transcription utilisant Whisper Large pour convertir l'audio en texte.

Migrated to use the new utils for S3 and SQS operations instead of direct AWS libraries.
"""
import asyncio
import json
import logging
import os
from pathlib import Path
import tempfile
import time
from typing import Dict, Any

import whisper

from media_summarizer.utils import s3, sqs
from media_summarizer.core.utils.whisper_async import transcribe_async

# Configuration du logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Configuration
AUDIO_BUCKET = os.environ.get("AUDIO_BUCKET", "media-summarizer-audio")
TRANSCRIPT_BUCKET = os.environ.get("TRANSCRIPT_BUCKET", "media-summarizer-transcriptions")
TRANSCRIPTION_QUEUE = os.environ.get("TRANSCRIPTION_QUEUE", "transcription-queue")
SUMMARIZATION_QUEUE = os.environ.get("SUMMARIZATION_QUEUE", "summarization-queue")
NOTIFICATION_QUEUE = os.environ.get("NOTIFICATION_QUEUE", "email-notification-queue")
MAX_RETRIES = 3
TEST_MODE = os.environ.get("TEST_MODE", "false").lower() == "true"
RETRY_BASE_DELAY = 0.01 if TEST_MODE else 1  # secondes

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
            bucket=AUDIO_BUCKET,
            key=audio_s3_key,
            file_path=local_path
        )
        logger.info(f"Downloaded audio file from s3://{AUDIO_BUCKET}/{audio_s3_key} to {local_path}")

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
        transcript_bytes = transcription_text.encode('utf-8')
        transcript_file = BytesIO(transcript_bytes)

        await s3.upload_file_object(
            bucket=TRANSCRIPT_BUCKET,
            key=transcript_s3_key,
            file_obj=transcript_file,
            content_type="text/plain",
            metadata={
                "content-type": "text/plain",
                "job-type": "podcast-transcription"
            }
        )

        logger.info(f"Uploaded transcription to s3://{TRANSCRIPT_BUCKET}/{transcript_s3_key}")

    except Exception as e:
        logger.error(f"Failed to upload transcription: {str(e)}")
        raise


async def send_notification(
    notification_type: str,
    job_id: str,
    email: str,
    **kwargs
) -> None:
    """Send notification message to the email queue using utils."""
    try:
        notification_data = {
            "notification_type": notification_type,
            "job_id": job_id,
            "email": email,
            **kwargs
        }

        await sqs.send_message(
            queue_name=NOTIFICATION_QUEUE,
            message_body=notification_data
        )

        logger.info(f"Sent {notification_type} notification for job {job_id}")

    except Exception as e:
        logger.error(f"Failed to send notification: {str(e)}")
        raise


async def send_to_summarization_queue(
    job_id: str,
    transcript_s3_key: str,
    email: str,
    **kwargs
) -> None:
    """Send message to summarization queue using utils."""
    try:
        summarization_data = {
            "job_id": job_id,
            "transcript_s3_key": transcript_s3_key,
            "transcript_bucket": TRANSCRIPT_BUCKET,
            "email": email,
            **kwargs
        }

        await sqs.send_message(
            queue_name=SUMMARIZATION_QUEUE,
            message_body=summarization_data
        )

        logger.info(f"Sent job {job_id} to summarization queue")

    except Exception as e:
        logger.error(f"Failed to send to summarization queue: {str(e)}")
        raise


async def process_transcription_message(message_body: Dict[str, Any]) -> None:
    """
    Process a single transcription message.

    Args:
        message_body: The message body containing job information
    """
    job_id = message_body.get("job_id")
    audio_s3_key = message_body.get("audio_s3_key")
    email = message_body.get("email")

    if not all([job_id, audio_s3_key, email]):
        logger.error(f"Missing required fields in message: {message_body}")
        raise ValueError("Missing required fields in transcription message")

    # Ensure all required fields are strings
    if not isinstance(job_id, str) or not isinstance(audio_s3_key, str) or not isinstance(email, str):
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
        try:
            # Download audio file
            audio_filename = f"{job_id}_audio.mp3"
            local_audio_path = Path(temp_dir) / audio_filename

            logger.info(f"Downloading audio for job {job_id}")
            await download_audio_file(audio_s3_key, str(local_audio_path))

            # Verify audio file exists and has content
            if not local_audio_path.exists() or local_audio_path.stat().st_size == 0:
                raise ValueError("Downloaded audio file is empty or missing")

            # Transcribe audio
            logger.info(f"Starting transcription for job {job_id} using Whisper {WHISPER_MODEL}")
            start_time = time.time()

            # Use async transcription to avoid blocking
            transcription_result = await transcribe_async(
                audio_path=str(local_audio_path),
                model_name=WHISPER_MODEL
            )

            transcription_duration = time.time() - start_time
            logger.info(f"Transcription completed for job {job_id} in {transcription_duration:.2f} seconds")

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

            # Prepare transcription data with metadata
            transcription_data = {
                "job_id": job_id,
                "transcription": transcription_text,
                "metadata": {
                    "language": language,
                    "duration_seconds": transcription_duration,
                    "segments_count": len(segments),
                    "audio_s3_key": audio_s3_key,
                    "model_used": WHISPER_MODEL,
                    "transcribed_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
                }
            }

            # Upload transcription to S3
            transcript_s3_key = f"{job_id}.txt"
            logger.info(f"Uploading transcription for job {job_id}")
            await upload_transcription(transcript_s3_key, transcription_text)

            # Update job with transcription location and duration
            if job:
                job.set_transcription_location(transcript_s3_key)
                job.set_processing_duration('transcription', int(transcription_duration))
                await database_async.update_processing_job(job)

            # Send to summarization queue
            await send_to_summarization_queue(
                job_id=job_id,
                transcript_s3_key=transcript_s3_key,
                email=email,
                podcast_title=message_body.get("podcast_title"),
                episode_title=message_body.get("episode_title"),
                transcription_metadata=transcription_data["metadata"]
            )

            logger.info(f"Successfully completed transcription for job {job_id}")

        except Exception as e:
            logger.error(f"Transcription failed for job {job_id}: {str(e)}")

            # Mark job as failed in database
            if job:
                job.mark_failed(str(e), "transcription")
                await database_async.update_processing_job(job)

            # Send error notification
            await send_notification(
                notification_type="error",
                job_id=job_id,
                email=email,
                error=f"Transcription failed: {str(e)}",
                step="transcription"
            )

            raise


async def process_message(message: Dict[str, Any]) -> None:
    """
    Process an SQS message for transcription.

    Args:
        message: SQS message containing job information
    """
    try:
        # Parse message body
        body = json.loads(message.get("Body", "{}"))

        # Process the transcription
        await process_transcription_message(body)

    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse message body: {str(e)}")
        raise
    except Exception as e:
        logger.error(f"Error processing transcription message: {str(e)}")
        raise


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
                visibility_timeout=1800  # 30 minutes for transcription processing
            )

            if messages:
                logger.info(f"Received {len(messages)} messages")

                # Process messages one by one
                for message in messages:
                    try:
                        await process_message(message)

                        # Delete message after successful processing
                        receipt_handle = message.get("ReceiptHandle")
                        if receipt_handle:
                            await sqs.delete_message(
                                queue_name=TRANSCRIPTION_QUEUE,
                                receipt_handle=receipt_handle
                            )

                        logger.info("Successfully processed and deleted message")

                    except Exception as e:
                        logger.error(f"Failed to process message: {str(e)}")
                        # Message will become visible again after visibility timeout
                        # for retry by another worker instance

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
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    asyncio.run(main())
