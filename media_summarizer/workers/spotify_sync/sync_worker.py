"""
Container-based Spotify Sync Worker

Polls SQS messages and processes playlist synchronization requests.
This is the container version of the Lambda worker for local development.
"""
import asyncio
import json
import logging
import os
import signal
import sys
from typing import Dict, Any, Optional

import boto3
from botocore.exceptions import ClientError

from media_summarizer.workers.spotify_sync.worker import process_sync_message

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Configuration from environment
AWS_REGION = os.environ.get("AWS_REGION", "us-east-1")
AWS_ENDPOINT_URL = os.environ.get("AWS_ENDPOINT_URL")
QUEUE_NAME = os.environ.get("SPOTIFY_SYNC_QUEUE", "spotify-sync-queue")
MAX_MESSAGES = int(os.environ.get("SQS_MAX_MESSAGES", "1"))
WAIT_TIME = int(os.environ.get("SQS_WAIT_TIME", "20"))
VISIBILITY_TIMEOUT = int(os.environ.get("SQS_VISIBILITY_TIMEOUT", "300"))

# Global flag for graceful shutdown
shutdown_requested = False


def signal_handler(signum, frame):
    """Handle shutdown signals gracefully."""
    global shutdown_requested
    logger.info(f"Received signal {signum}, initiating graceful shutdown...")
    shutdown_requested = True


# Register signal handlers
signal.signal(signal.SIGTERM, signal_handler)
signal.signal(signal.SIGINT, signal_handler)


class SpotifySyncWorker:
    """Container-based worker for Spotify playlist synchronization."""

    def __init__(self):
        """Initialize the worker with SQS client."""
        self.sqs_client = boto3.client(
            'sqs',
            region_name=AWS_REGION,
            endpoint_url=AWS_ENDPOINT_URL
        )
        self.queue_url = None
        self._setup_queue()

    def _setup_queue(self):
        """Setup SQS queue URL."""
        try:
            if AWS_ENDPOINT_URL:
                # LocalStack format
                self.queue_url = f"{AWS_ENDPOINT_URL}/000000000000/{QUEUE_NAME}"
            else:
                # AWS format
                response = self.sqs_client.get_queue_url(QueueName=QUEUE_NAME)
                self.queue_url = response['QueueUrl']
            
            logger.info(f"Connected to SQS queue: {self.queue_url}")
        except ClientError as e:
            logger.error(f"Failed to setup queue {QUEUE_NAME}: {e}")
            raise

    async def receive_messages(self) -> list:
        """Receive messages from SQS queue."""
        try:
            response = self.sqs_client.receive_message(
                QueueUrl=self.queue_url,
                MaxNumberOfMessages=MAX_MESSAGES,
                WaitTimeSeconds=WAIT_TIME,
                VisibilityTimeoutSeconds=VISIBILITY_TIMEOUT,
                MessageAttributeNames=['All']
            )
            return response.get('Messages', [])
        except ClientError as e:
            logger.error(f"Error receiving messages: {e}")
            return []

    async def delete_message(self, receipt_handle: str):
        """Delete processed message from queue."""
        try:
            self.sqs_client.delete_message(
                QueueUrl=self.queue_url,
                ReceiptHandle=receipt_handle
            )
            logger.debug(f"Deleted message with receipt handle: {receipt_handle}")
        except ClientError as e:
            logger.error(f"Error deleting message: {e}")

    async def process_message(self, message: Dict[str, Any]) -> bool:
        """
        Process a single SQS message.
        
        Returns:
            bool: True if message was processed successfully
        """
        receipt_handle = message.get('ReceiptHandle')
        message_id = message.get('MessageId', 'unknown')
        
        try:
            # Parse message body
            body = json.loads(message['Body'])
            user_id = body.get('user_id', 'unknown')
            
            logger.info(f"Processing sync message {message_id} for user: {user_id}")
            
            # Process the sync using the Lambda handler logic
            result = await process_sync_message(body)
            
            # Check if processing was successful
            if result.get('status') == 'success':
                successful_syncs = result.get('successful_syncs', 0)
                total_playlists = result.get('total_playlists', 0)
                logger.info(f"Successfully processed sync for user {user_id}: "
                           f"{successful_syncs}/{total_playlists} playlists synced")
                await self.delete_message(receipt_handle)
                return True
            elif result.get('status') == 'partial_failure':
                # Some playlists succeeded, some failed - still consider success
                successful_syncs = result.get('successful_syncs', 0)
                total_playlists = result.get('total_playlists', 0)
                logger.warning(f"Partial sync success for user {user_id}: "
                              f"{successful_syncs}/{total_playlists} playlists synced")
                await self.delete_message(receipt_handle)
                return True
            else:
                reason = result.get('reason', 'unknown')
                logger.warning(f"Sync processing failed for user {user_id}: {reason}")
                
                # Delete messages for certain permanent failures to avoid infinite retries
                permanent_failures = {'user_not_found', 'missing_user_id', 'no_playlists', 'spotify_not_linked'}
                if reason in permanent_failures:
                    logger.info(f"Deleting message {message_id} due to permanent failure: {reason}")
                    await self.delete_message(receipt_handle)
                    return False
                
                # Don't delete for temporary failures - let them retry or go to DLQ
                return False
                
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON in message {message_id}: {e}")
            # Delete malformed messages to prevent infinite reprocessing
            if receipt_handle:
                await self.delete_message(receipt_handle)
            return False
        except Exception as e:
            logger.error(f"Unexpected error processing message {message_id}: {e}", exc_info=True)
            # Don't delete on unexpected errors - let SQS handle retries
            return False

    async def run(self):
        """Main worker loop."""
        logger.info("Starting Spotify Sync Worker...")
        logger.info(f"Queue: {QUEUE_NAME}")
        logger.info(f"Max messages: {MAX_MESSAGES}")
        logger.info(f"Wait time: {WAIT_TIME}s")
        logger.info(f"Visibility timeout: {VISIBILITY_TIMEOUT}s")
        
        processed_count = 0
        
        while not shutdown_requested:
            try:
                # Receive messages from queue
                messages = await self.receive_messages()
                
                if not messages:
                    logger.debug("No messages received, continuing to poll...")
                    continue
                
                logger.info(f"Received {len(messages)} message(s)")
                
                # Process each message
                for message in messages:
                    if shutdown_requested:
                        logger.info("Shutdown requested, stopping message processing")
                        break
                    
                    success = await self.process_message(message)
                    if success:
                        processed_count += 1
                
                # Small delay to prevent tight polling
                await asyncio.sleep(1)
                
            except KeyboardInterrupt:
                logger.info("Received keyboard interrupt, shutting down...")
                break
            except Exception as e:
                logger.error(f"Error in main loop: {e}")
                # Wait before retrying to avoid tight error loops
                await asyncio.sleep(5)
        
        logger.info(f"Worker shutting down. Processed {processed_count} messages.")


async def main():
    """Main entry point."""
    try:
        worker = SpotifySyncWorker()
        await worker.run()
    except Exception as e:
        logger.error(f"Worker failed to start: {e}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())