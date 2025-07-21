"""
Worker de résolution RSS pour extraire les informations des podcasts.
"""
import asyncio
import json
import logging
import os

import boto3
import feedparser
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

async def detect_platform(url):
    """Détecte la plateforme de podcast à partir de l'URL."""
    if "spotify.com" in url:
        return "spotify"
    elif "apple.com" in url or "itunes.com" in url:
        return "apple"
    elif "google" in url and "podcast" in url:
        return "google"
    else:
        return "generic"

async def resolve_rss_feed(url):
    """Résout l'URL de la plateforme vers un flux RSS."""
    platform = await detect_platform(url)
    
    # Implémentation de base - à développer dans les tâches futures
    if platform == "spotify":
        # Logique de résolution Spotify
        pass
    elif platform == "apple":
        # Logique de résolution Apple Podcasts
        pass
    elif platform == "google":
        # Logique de résolution Google Podcasts
        pass
    else:
        # Essayer de résoudre directement si c'est déjà un flux RSS
        try:
            feed = feedparser.parse(url)
            if feed.entries:
                return url
        except:
            pass
    
    # Pour l'instant, retourne None si non résolu
    return None

async def process_message(message):
    """Traite un message de la file SQS pour la résolution RSS."""
    job_id = "unknown"
    try:
        body = json.loads(message["Body"])
        job_id = body.get("job_id", "unknown")
        podcast_url = body.get("podcast_url", "")
        
        logger.info(f"Traitement de la résolution RSS pour le job {job_id}")
        
        # Check for missing podcast_url
        if not podcast_url:
            raise ValueError("Missing required field: podcast_url")
            
        # Résolution du flux RSS
        rss_url = await resolve_rss_feed(podcast_url)
            
        if rss_url:
            # Extraction de l'URL audio
            feed = feedparser.parse(rss_url)
            
            # Check if there are any entries
            if not feed.entries:
                raise ValueError("No episodes found in the podcast feed")
                
            episode = feed.entries[0]  # Premier épisode par défaut
            
            # Recherche de l'URL audio dans les enclosures
            audio_url = None
            for enclosure in episode.get("enclosures", []):
                if enclosure.get("type", "").startswith("audio/"):
                    audio_url = enclosure.get("href")
                    break
            
            if audio_url:
                # Envoi du message à la file de téléchargement
                next_message = {
                    "job_id": job_id,
                    "audio_url": audio_url,
                    "podcast_title": feed.feed.get("title", ""),
                    "episode_title": episode.get("title", ""),
                    "success": True,
                }
                
                sqs_client.send_message(
                    QueueUrl=f"{AWS_ENDPOINT_URL}/000000000000/audio-download-queue" 
                    if AWS_ENDPOINT_URL else "audio-download-queue",
                    MessageBody=json.dumps(next_message),
                )
                
                logger.info(f"Résolution RSS réussie pour le job {job_id}")
            else:
                raise Exception("Aucune URL audio trouvée dans le flux RSS")
        else:
            raise Exception("Impossible de résoudre le flux RSS")
        
    except json.JSONDecodeError as e:
        logger.error(f"Erreur lors de la résolution RSS: {str(e)}")
        # Envoi d'un message d'erreur pour JSON invalide
        error_message = {
            "job_id": job_id,
            "error": f"Invalid JSON format in message: {str(e)}",
            "step": "rss_resolution",
            "success": False,
        }
        
        sqs_client.send_message(
            QueueUrl=f"{AWS_ENDPOINT_URL}/000000000000/email-notification-queue" 
            if AWS_ENDPOINT_URL else "email-notification-queue",
            MessageBody=json.dumps(error_message),
        )
    except Exception as e:
        logger.error(f"Erreur lors de la résolution RSS: {str(e)}")
        # Envoi d'un message d'erreur
        error_message = {
            "job_id": job_id,
            "error": str(e),
            "step": "rss_resolution",
            "success": False,
        }
        
        sqs_client.send_message(
            QueueUrl=f"{AWS_ENDPOINT_URL}/000000000000/email-notification-queue" 
            if AWS_ENDPOINT_URL else "email-notification-queue",
            MessageBody=json.dumps(error_message),
        )

async def poll_queue():
    """Interroge la file SQS pour les nouveaux messages."""
    queue_url = f"{AWS_ENDPOINT_URL}/000000000000/rss-resolution-queue" if AWS_ENDPOINT_URL else "rss-resolution-queue"
    
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
    logger.info("Démarrage du worker de résolution RSS")
    await poll_queue()

if __name__ == "__main__":
    asyncio.run(main())