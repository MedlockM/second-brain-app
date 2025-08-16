"""
Worker de téléchargement audio pour récupérer les fichiers MP3 des podcasts.
"""
import asyncio
import json
import logging
import os
import tempfile
from pathlib import Path

import httpx
from media_summarizer.utils import s3, sqs
from media_summarizer.workers.base_worker import (
    process_message_with_retry,
    get_sqs_receive_params
)

# Configuration du logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Configuration des buckets S3
AUDIO_BUCKET = os.environ.get("AUDIO_BUCKET", "media-summarizer-audio")

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
    """Traite un message de la file SQS pour le téléchargement audio."""
    body = {}
    job_id = "unknown"

    try:
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

        logger.info(f"Téléchargement audio pour le job {job_id}")

        # Update job status to downloading
        from media_summarizer.utils import database_async
        job = await database_async.get_processing_job_by_id(job_id)
        if job:
            job.mark_downloading()
            await database_async.update_processing_job(job)

        # Création d'un fichier temporaire pour le téléchargement
        with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as temp_file:
            temp_path = temp_file.name

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

        # Nettoyage du fichier temporaire
        os.unlink(temp_path)

        # Envoi du message à la file de transcription
        next_message = {
            "job_id": job_id,
            "audio_s3_key": s3_key,
            "user_id": body.get("user_id"),
            "email": body.get("user_email") or body.get("email"),
            "episode_title": body.get("episode_title"),
            "podcast_title": body.get("podcast_title"),
            "success": True,
            "metadata": {
                "file_size_bytes": file_size
            }
        }

        # Send message to transcription queue
        await sqs.send_message(
            queue_name="transcription-queue",
            message_body=next_message
        )

        logger.info(f"Téléchargement audio terminé pour le job {job_id}")

    except Exception as e:
        logger.error(f"Erreur lors du téléchargement audio: {str(e)}")

        # Mark job as failed in database
        try:
            from media_summarizer.utils import database_async
            job = await database_async.get_processing_job_by_id(job_id)
            if job:
                job.mark_failed(str(e), "audio_download")
                await database_async.update_processing_job(job)
        except Exception as db_error:
            logger.error(f"Error updating job status to failed: {str(db_error)}")

        # Envoi d'un message d'erreur
        error_message = {
            "job_id": body.get("job_id", job_id),
            "error": str(e),
            "step": "audio_download",
            "success": False,
        }

        await sqs.send_message(
            queue_name="email-notification-queue",
            message_body=error_message
        )

        # Re-raise l'exception pour que base_worker puisse gérer les retries
        raise


async def process_messages_batch(messages):
    """Process multiple messages concurrently."""
    # Limit concurrency to avoid overwhelming the system
    semaphore = asyncio.Semaphore(3)  # Max 3 concurrent downloads

    async def process_with_semaphore(message):
        async with semaphore:
            return await process_message(message)

    tasks = []
    for message in messages:
        task = asyncio.create_task(process_with_semaphore(message))
        tasks.append(task)

    # Process messages concurrently
    results = await asyncio.gather(*tasks, return_exceptions=True)

    # Handle results and delete successful messages
    for i, (message, result) in enumerate(zip(messages, results)):
        if isinstance(result, Exception):
            logger.error(f"Error processing message {i}: {str(result)}")
            # Let the message become visible again for retry
        else:
            # Delete successful message
            try:
                await sqs.delete_message(
                    queue_name="audio-download-queue",
                    receipt_handle=message["ReceiptHandle"]
                )
            except Exception as e:
                logger.error(f"Error deleting message: {str(e)}")

async def poll_queue():
    """Interroge la file SQS pour les nouveaux messages avec traitement par batch."""
    queue_name = "audio-download-queue"

    while True:
        try:
            messages = await sqs.receive_messages(
                queue_name=queue_name,
                max_messages=5,  # Reduced for download worker
                wait_time_seconds=20,
                visibility_timeout=300  # 5 minutes pour download
            )

            if messages:
                logger.info(f"Processing {len(messages)} download messages")
                await process_messages_batch(messages)
            else:
                # Short sleep when no messages
                await asyncio.sleep(1)

        except Exception as e:
            logger.error(f"Erreur lors de l'interrogation de la file: {str(e)}")
            await asyncio.sleep(5)

async def main():
    """Fonction principale du worker."""
    logger.info("Démarrage du worker de téléchargement audio")
    await poll_queue()

if __name__ == "__main__":
    asyncio.run(main())
