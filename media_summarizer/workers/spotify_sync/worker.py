"""
Lambda handler for Spotify Sync Worker

Processes SQS messages containing user playlists to sync.
Designed to be triggered by SQS event source mapping.
"""
import asyncio
import json
import logging
import os
from datetime import datetime, timezone
from typing import Dict, Any

from media_summarizer.utils import database_async, spotify_follows_db
from media_summarizer.core.services.playlist_sync import run_playlist_sync_for_user
from media_summarizer.utils.spotify import ensure_access_token

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# AWS Configuration
AWS_REGION = os.environ.get("AWS_REGION", "us-east-1")
AWS_ENDPOINT_URL = os.environ.get("AWS_ENDPOINT_URL")


async def process_sync_message(message_body: Dict[str, Any]):
    """
    Process a single sync message for a user's playlists.
    """
    # Input validation
    user_id = message_body.get("user_id")
    playlist_ids = message_body.get("playlist_ids", [])
    
    if not user_id:
        logger.warning(f"Missing user_id in message: {message_body}")
        return {"status": "error", "reason": "missing_user_id"}
    
    if not playlist_ids:
        logger.warning(f"No playlist_ids provided for user {user_id}")
        return {"status": "error", "reason": "no_playlists"}

    logger.info(f"Processing sync for user {user_id} with {len(playlist_ids)} playlists.")

    try:
        # 1. Get User
        user = await database_async.get_user_by_id(user_id)
        if not user:
            logger.error(f"User {user_id} not found.")
            return {"status": "error", "reason": "user_not_found"}

        # 2. Ensure Token (Refresh once for all playlists)
        try:
            await ensure_access_token(user)
        except Exception as e:
            logger.error(f"Failed to refresh token for user {user_id}: {e}")
            return {"status": "error", "reason": "token_refresh_failed", "error": str(e)}

        # 3. Sync each playlist
        results = []
        successful_syncs = 0
        
        for playlist_id in playlist_ids:
            try:
                logger.info(f"Syncing playlist {playlist_id} for user {user_id}...")
                result = await run_playlist_sync_for_user(user, playlist_id)
                
                # Update last_synced_at for successful syncs
                if result.get("status") == "success":
                    successful_syncs += 1
                    try:
                        follow = await spotify_follows_db.get_follow(user_id, playlist_id)
                        if follow:
                            follow.last_synced_at = datetime.now(timezone.utc)
                            await spotify_follows_db.upsert_follow(follow)
                    except Exception as db_error:
                        logger.warning(f"Failed to update last_synced_at for {playlist_id}: {db_error}")
                    
                    logger.info(f"Sync success for {playlist_id}: submitted={result.get('submitted', 0)}")
                else:
                    logger.warning(f"Sync failed for {playlist_id}: {result.get('reason', 'unknown')}")
                
                results.append({"playlist_id": playlist_id, "result": result})
                    
            except Exception as e:
                logger.error(f"Error syncing playlist {playlist_id} for user {user_id}: {e}")
                results.append({"playlist_id": playlist_id, "error": str(e), "status": "error"})
        
        # Determine overall status
        if successful_syncs > 0:
            overall_status = "success" if successful_syncs == len(playlist_ids) else "partial_failure"
        else:
            overall_status = "error"
        
        return {
            "status": overall_status,
            "user_id": user_id,
            "successful_syncs": successful_syncs,
            "total_playlists": len(playlist_ids),
            "results": results
        }
        
    except Exception as e:
        logger.error(f"Unexpected error processing sync for user {user_id}: {e}")
        return {
            "status": "error", 
            "reason": "unexpected_error", 
            "error": str(e),
            "user_id": user_id
        }


def lambda_handler(event, context):
    """
    AWS Lambda handler for SQS event source mapping.
    Processes batch of SQS messages.
    """
    logger.info(f"Lambda invoked with {len(event.get('Records', []))} records")
    
    batch_results = []
    
    for record in event.get("Records", []):
        try:
            # Parse SQS message body
            body = json.loads(record["body"])
            
            # Process the sync
            result = asyncio.run(process_sync_message(body))
            batch_results.append(result)
            
        except Exception as e:
            logger.error(f"Failed to process record: {e}")
            batch_results.append({"status": "error", "error": str(e)})
    
    return {
        "statusCode": 200,
        "body": json.dumps({"processed": len(batch_results), "results": batch_results})
    }


if __name__ == "__main__":
    # For local testing: simulate SQS event
    import sys
    if len(sys.argv) > 1:
        # Read message from stdin or file
        message_body = json.loads(sys.argv[1])
    else:
        # Default test message
        message_body = {
            "user_id": "test_user",
            "playlist_ids": ["test_playlist"],
            "source": "manual_test"
        }
    
    result = asyncio.run(process_sync_message(message_body))
    print(json.dumps(result, indent=2))
