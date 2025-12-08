import asyncio
import json
import logging
import os
import boto3
from media_summarizer.workers.spotify_sync.worker import process_sync_message

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# AWS Configuration
AWS_REGION = os.environ.get("AWS_REGION", "us-east-1")
AWS_ENDPOINT_URL = os.environ.get("AWS_ENDPOINT_URL", "http://localhost:4566")
SPOTIFY_SYNC_QUEUE_NAME = "spotify-sync-queue"

async def verify_worker_one_shot():
    logger.info("Starting one-shot worker verification...")
    
    sqs = boto3.resource("sqs", region_name=AWS_REGION, endpoint_url=AWS_ENDPOINT_URL)
    try:
        queue = sqs.get_queue_by_name(QueueName=SPOTIFY_SYNC_QUEUE_NAME)
    except Exception as e:
        logger.error(f"Queue not found: {e}")
        return

    # Receive 1 message
    messages = queue.receive_messages(MaxNumberOfMessages=1, WaitTimeSeconds=5)
    
    if not messages:
        logger.warning("No messages found in queue!")
        return

    message = messages[0]
    logger.info(f"Received message: {message.body}")
    
    try:
        body = json.loads(message.body)
        # Process it
        result = await process_sync_message(body)
        logger.info(f"Processing result: {result}")
        
        # Delete if successful
        message.delete()
        logger.info("Message processed and deleted successfully.")
    except Exception as e:
        logger.error(f"Failed to process message: {e}")

if __name__ == "__main__":
    asyncio.run(verify_worker_one_shot())
