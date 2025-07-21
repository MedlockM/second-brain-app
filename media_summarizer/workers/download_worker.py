"""
Worker de téléchargement audio pour récupérer les fichiers MP3 des podcasts.
"""
import asyncio
import json
import logging
import os
import tempfile
from pathlib import Path

import boto3
import httpx

# Configuration du logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Configuration AWS
AWS_ENDPOINT_URL = os.environ.get("AWS_ENDPOINT_URL")
AWS_REGION = os.environ.get("AWS_DEFAULT_REGION", "us-east-1")

# Initialisation des clients AWS
s3_client = boto3.client(
    "s3",
    endpoint_url=AWS_ENDPOINT_URL,
    region_name=AWS_REGION,
)

sqs_client = boto3.client(
    "sqs",
    endpoint_url=AWS_ENDPOINT_URL,
    region_name=AWS_REGION,
)

async def download_audio(url, output_path):
    """Télécharge un fichier audio depuis une URL."""
    client = httpx.AsyncClient(timeout=60.0)
    try:
        async with client:
            response = await client.stream("GET", url)
            async with response:
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
        # Parse the message body
        try:
            body = json.loads(message["Body"])
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON in message body: {str(e)}")
        
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
        
        # Création d'un fichier temporaire pour le téléchargement
        with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as temp_file:
            temp_path = temp_file.name
        
        # Téléchargement du fichier audio
        await download_audio(audio_url, temp_path)
        
        # Get file size for metadata
        file_size = os.path.getsize(temp_path)
        
        # Upload vers S3
        s3_key = f"audio/{job_id}.mp3"
        s3_client.upload_file(temp_path, "media-summarizer-audio", s3_key)
        
        # Nettoyage du fichier temporaire
        os.unlink(temp_path)
        
        # Envoi du message à la file de transcription
        next_message = {
            "job_id": job_id,
            "s3_audio_key": s3_key,
            "success": True,
            "metadata": {
                "file_size_bytes": file_size
            }
        }
        
        sqs_client.send_message(
            QueueUrl=f"{AWS_ENDPOINT_URL}/000000000000/transcription-queue" 
            if AWS_ENDPOINT_URL else "transcription-queue",
            MessageBody=json.dumps(next_message),
        )
        
        logger.info(f"Téléchargement audio terminé pour le job {job_id}")
        
    except Exception as e:
        logger.error(f"Erreur lors du téléchargement audio: {str(e)}")
        # Envoi d'un message d'erreur
        error_message = {
            "job_id": body.get("job_id", job_id),
            "error": str(e),
            "step": "audio_download",
            "success": False,
        }
        
        sqs_client.send_message(
            QueueUrl=f"{AWS_ENDPOINT_URL}/000000000000/email-notification-queue" 
            if AWS_ENDPOINT_URL else "email-notification-queue",
            MessageBody=json.dumps(error_message),
        )

async def poll_queue():
    """Interroge la file SQS pour les nouveaux messages."""
    queue_url = f"{AWS_ENDPOINT_URL}/000000000000/audio-download-queue" if AWS_ENDPOINT_URL else "audio-download-queue"
    
    while True:
        try:
            response = sqs_client.receive_message(
                QueueUrl=queue_url,
                MaxNumberOfMessages=1,
                WaitTimeSeconds=20,
            )
            
            messages = response.get("Messages", [])
            
            for message in messages:
                await process_message(message)
                
                # Suppression du message après traitement
                sqs_client.delete_message(
                    QueueUrl=queue_url,
                    ReceiptHandle=message["ReceiptHandle"],
                )
                
        except Exception as e:
            logger.error(f"Erreur lors de l'interrogation de la file: {str(e)}")
            await asyncio.sleep(5)

async def main():
    """Fonction principale du worker."""
    logger.info("Démarrage du worker de téléchargement audio")
    await poll_queue()

if __name__ == "__main__":
    asyncio.run(main())