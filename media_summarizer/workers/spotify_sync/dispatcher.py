"""
Lambda handler for Spotify Sync Dispatcher

This can run as:
- AWS Lambda (production)
- Standalone script (local dev)
- Docker container triggered by EventBridge (LocalStack)
"""
import asyncio
import json
import logging
import os
from collections import defaultdict
from typing import Dict, Any

import boto3
from media_summarizer.utils import spotify_follows_db

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# AWS Configuration
AWS_REGION = os.environ.get("AWS_REGION", "us-east-1")
AWS_ENDPOINT_URL = os.environ.get("AWS_ENDPOINT_URL")
SPOTIFY_SYNC_QUEUE_URL = os.environ.get("SPOTIFY_SYNC_QUEUE_URL")


async def dispatch_jobs_async():
    """
    Fetch all enabled subscriptions, group by user, and dispatch to SQS.
    """
    logger.info("Starting Spotify Sync Dispatcher...")
    
    # 1. Fetch all enabled follows
    follows = await spotify_follows_db.get_all_enabled_follows()
    logger.info(f"Found {len(follows)} enabled playlist subscriptions.")
    
    if not follows:
        logger.info("No subscriptions to process.")
        return {"dispatched": 0, "users": 0}

    # 2. Group by User ID
    user_playlists: Dict[str, list] = defaultdict(list)
    for follow in follows:
        user_playlists[follow.user_id].append(follow.playlist_id)
    
    logger.info(f"Grouped into {len(user_playlists)} unique users.")

    # 3. Dispatch to SQS
    sqs = boto3.client("sqs", region_name=AWS_REGION, endpoint_url=AWS_ENDPOINT_URL)
    
    queue_url = SPOTIFY_SYNC_QUEUE_URL
    if not queue_url:
        try:
            response = sqs.get_queue_url(QueueName="spotify-sync-queue")
            queue_url = response["QueueUrl"]
        except Exception as e:
            logger.error(f"Failed to get queue URL: {e}")
            raise

    logger.info(f"Dispatching to queue: {queue_url}")
    
    sent_count = 0
    for user_id, playlist_ids in user_playlists.items():
        message_body = {
            "user_id": user_id,
            "playlist_ids": playlist_ids,
            "source": "daily_cron"
        }
        
        try:
            sqs.send_message(
                QueueUrl=queue_url,
                MessageBody=json.dumps(message_body)
            )
            sent_count += 1
        except Exception as e:
            logger.error(f"Failed to send message for user {user_id}: {e}")

    logger.info(f"Successfully dispatched {sent_count} user jobs.")
    return {"dispatched": sent_count, "users": len(user_playlists)}


def lambda_handler(event, context):
    """
    AWS Lambda handler (also works for EventBridge events)
    """
    logger.info(f"Lambda invoked with event: {json.dumps(event)}")
    
    # Run async function
    result = asyncio.run(dispatch_jobs_async())
    
    return {
        "statusCode": 200,
        "body": json.dumps(result)
    }


if __name__ == "__main__":
    # Standalone execution
    result = asyncio.run(dispatch_jobs_async())
    print(f"Result: {result}")
