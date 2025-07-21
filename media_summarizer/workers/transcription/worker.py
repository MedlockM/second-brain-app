"""
Worker de transcription utilisant Whisper Large pour convertir l'audio en texte.
"""
import asyncio
import json
import logging
import os
from pathlib import Path
import tempfile
import time
from typing import Dict, Any

import aioboto3
import whisper
from botocore.exceptions import ClientError

# Configuration du logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Configuration AWS
AWS_ENDPOINT_URL = os.environ.get("AWS_ENDPOINT_URL")
AWS_REGION = os.environ.get("AWS_DEFAULT_REGION", "us-east-1")
AUDIO_BUCKET = os.environ.get("AUDIO_BUCKET", "media-summarizer-audio")
TRANSCRIPT_BUCKET = os.environ.get("TRANSCRIPT_BUCKET", "media-summarizer-transcripts")
TRANSCRIPTION_QUEUE = os.environ.get("TRANSCRIPTION_QUEUE", "transcription-queue")
SUMMARIZATION_QUEUE = os.environ.get("SUMMARIZATION_QUEUE", "summarization-queue")
NOTIFICATION_QUEUE = os.environ.get("NOTIFICATION_QUEUE", "email-notification-queue")
MAX_RETRIES = 3
RETRY_BASE_DELAY = 1  # secondes

# Initialisation du modèle Whisper
# Check if we should mock Whisper for testing
if os.environ.get("MOCK_WHISPER", "0") == "1":
    # Create a mock model for testing
    class MockWhisperModel:
        def transcribe(self, audio_file, **kwargs):
            """Mock transcription function that returns a predefined result."""
            return {
                "text": "This is a mock transcription for testing purposes.",
                "segments": [
                    {
                        "id": 0,
                        "start": 0.0,
                        "end": 10.0,
                        "text": "This is a mock transcription segment."
                    }
                ],
                "language": "en"
            }
    
    model = MockWhisperModel()
    logger.info("Using mock Whisper model for testing")
else:
    # Use the real Whisper model
    model = whisper.load_model("large")

# Session aioboto3 pour les opérations asynchrones
session = aioboto3.Session()

def get_queue_url(queue_name: str) -> str:
    """Construit l'URL de la file SQS en fonction de l'environnement."""
    if AWS_ENDPOINT_URL:
        return f"{AWS_ENDPOINT_URL}/000000000000/{queue_name}"
    return queue_name

async def download_audio_file(bucket: str, key: str) -> str:
    """Télécharge un fichier audio depuis S3 de manière asynchrone."""
    with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as temp_file:
        audio_path = temp_file.name
    
    async with session.client(
        "s3", endpoint_url=AWS_ENDPOINT_URL, region_name=AWS_REGION
    ) as s3:
        try:
            await s3.download_file(bucket, key, audio_path)
            logger.info(f"Fichier audio téléchargé: {key}")
            return audio_path
        except ClientError as e:
            logger.error(f"Erreur lors du téléchargement du fichier audio: {str(e)}")
            raise

async def upload_transcript(bucket: str, key: str, transcript: str) -> None:
    """Téléverse une transcription vers S3 de manière asynchrone."""
    async with session.client(
        "s3", endpoint_url=AWS_ENDPOINT_URL, region_name=AWS_REGION
    ) as s3:
        try:
            await s3.put_object(
                Bucket=bucket,
                Key=key,
                Body=transcript.encode("utf-8"),
            )
            logger.info(f"Transcription téléversée: {key}")
        except ClientError as e:
            logger.error(f"Erreur lors du téléversement de la transcription: {str(e)}")
            raise

async def send_sqs_message(queue_name: str, message: Dict[str, Any]) -> None:
    """Envoie un message à une file SQS de manière asynchrone."""
    queue_url = get_queue_url(queue_name)
    
    async with session.client(
        "sqs", endpoint_url=AWS_ENDPOINT_URL, region_name=AWS_REGION
    ) as sqs:
        try:
            await sqs.send_message(
                QueueUrl=queue_url,
                MessageBody=json.dumps(message),
            )
            logger.info(f"Message envoyé à {queue_name}")
        except ClientError as e:
            logger.error(f"Erreur lors de l'envoi du message SQS: {str(e)}")
            raise

async def process_message(message: Dict[str, Any], retry_count: int = 0) -> None:
    """Traite un message de la file SQS pour la transcription avec logique de retry."""
    job_id = "unknown"
    audio_path = None
    
    try:
        body = json.loads(message["Body"])
        job_id = body.get("job_id", "unknown")
    except json.JSONDecodeError as e:
        error_message = {
            "job_id": job_id,
            "error": f"Invalid JSON format in message: {str(e)}",
            "step": "transcription",
            "success": False,
        }
        await send_sqs_message(NOTIFICATION_QUEUE, error_message)
        return
    
    try:
        s3_audio_key = body["s3_audio_key"]
        bucket_name = body.get("bucket_name", AUDIO_BUCKET)
        
        logger.info(f"Traitement de la transcription pour le job {job_id}")
        
        # Téléchargement du fichier audio depuis S3
        start_time = time.time()
        audio_path = await download_audio_file(bucket_name, s3_audio_key)
        
        # Transcription avec Whisper
        logger.info(f"Début de la transcription pour {job_id}")
        result = model.transcribe(audio_path)
        transcript_text = result["text"]
        
        # Mesure du temps de transcription
        transcription_time = time.time() - start_time
        logger.info(f"Transcription terminée en {transcription_time:.2f}s pour {job_id}")
        
        # Sauvegarde de la transcription dans S3
        transcript_key = f"transcripts/{job_id}.txt"
        await upload_transcript(TRANSCRIPT_BUCKET, transcript_key, transcript_text)
        
        # Get file size for metadata
        file_size = os.path.getsize(audio_path) if os.path.exists(audio_path) else 0
        
        # Prepare metadata
        metadata = {
            "transcription_time": transcription_time,
            "audio_source": s3_audio_key,
            "file_size_bytes": file_size
        }
        
        # Add warning if transcription is empty
        if not transcript_text.strip():
            metadata["warning"] = "empty transcription detected"
        
        # Envoi du message à la file de résumé
        next_message = {
            "job_id": job_id,
            "transcript_key": transcript_key,
            "success": True,
            "metadata": metadata
        }
        
        await send_sqs_message(SUMMARIZATION_QUEUE, next_message)
        logger.info(f"Transcription terminée pour le job {job_id}")
        
    except Exception as e:
        logger.error(f"Erreur lors de la transcription du job {job_id}: {str(e)}")
        
        # Logique de retry avec backoff exponentiel
        if retry_count < MAX_RETRIES:
            retry_delay = RETRY_BASE_DELAY * (2 ** retry_count)
            logger.info(f"Tentative de retry {retry_count + 1}/{MAX_RETRIES} dans {retry_delay}s pour {job_id}")
            await asyncio.sleep(retry_delay)
            await process_message(message, retry_count + 1)
        else:
            # Envoi d'un message d'erreur après épuisement des retries
            error_message = {
                "job_id": job_id,
                "error": str(e),
                "step": "transcription",
                "success": False,
            }
            
            await send_sqs_message(NOTIFICATION_QUEUE, error_message)
    finally:
        # Nettoyage du fichier temporaire
        if audio_path and os.path.exists(audio_path):
            os.unlink(audio_path)
            logger.debug(f"Fichier temporaire supprimé: {audio_path}")

async def poll_queue() -> None:
    """Interroge la file SQS pour les nouveaux messages."""
    queue_url = get_queue_url(TRANSCRIPTION_QUEUE)
    
    while True:
        try:
            async with session.client(
                "sqs", endpoint_url=AWS_ENDPOINT_URL, region_name=AWS_REGION
            ) as sqs:
                response = await sqs.receive_message(
                    QueueUrl=queue_url,
                    MaxNumberOfMessages=1,
                    WaitTimeSeconds=20,
                )
                
                messages = response.get("Messages", [])
                
                for message in messages:
                    # Traitement asynchrone du message
                    asyncio.create_task(process_message(message))
                    
                    # Suppression du message après mise en file de traitement
                    await sqs.delete_message(
                        QueueUrl=queue_url,
                        ReceiptHandle=message["ReceiptHandle"],
                    )
                
        except Exception as e:
            logger.error(f"Erreur lors de l'interrogation de la file: {str(e)}")
            await asyncio.sleep(5)

async def main() -> None:
    """Fonction principale du worker."""
    logger.info("Démarrage du worker de transcription")
    await poll_queue()

if __name__ == "__main__":
    asyncio.run(main())