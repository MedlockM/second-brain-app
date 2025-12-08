#!/usr/bin/env python3
"""
Spotify Sync Scheduler - Simulates EventBridge for local development

This script runs continuously and triggers the Spotify sync dispatcher
at the configured interval (default: daily).
"""
import asyncio
import logging
import os
import subprocess
from datetime import datetime, timedelta

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Configuration from environment
SYNC_INTERVAL_HOURS = int(os.environ.get("SPOTIFY_SYNC_INTERVAL_HOURS", "24"))
SYNC_INTERVAL_MINUTES = int(os.environ.get("SPOTIFY_SYNC_INTERVAL_MINUTES", "0"))


async def trigger_dispatcher():
    """Trigger the dispatcher script"""
    try:
        logger.info("🎯 Triggering Spotify Sync Dispatcher...")
        
        # Run dispatcher
        result = subprocess.run(
            ["python", "-m", "media_summarizer.workers.spotify_sync.dispatcher"],
            capture_output=True,
            text=True,
            check=True
        )
        
        logger.info(f"✅ Dispatcher completed: {result.stdout}")
        
        # Note: Worker is triggered by SQS event source mapping (Lambda)
        # or runs separately as a service
        
    except subprocess.CalledProcessError as e:
        logger.error(f"❌ Dispatcher failed: {e.stderr}")
    except Exception as e:
        logger.error(f"❌ Unexpected error: {e}")


async def run_scheduler():
    """Main scheduler loop"""
    interval_seconds = (SYNC_INTERVAL_HOURS * 3600) + (SYNC_INTERVAL_MINUTES * 60)
    
    logger.info(f"🚀 Spotify Sync Scheduler started")
    logger.info(f"📅 Interval: {SYNC_INTERVAL_HOURS}h {SYNC_INTERVAL_MINUTES}m ({interval_seconds}s)")
    
    # Run immediately on startup
    await trigger_dispatcher()
    
    # Then run on schedule
    while True:
        next_run = datetime.now() + timedelta(seconds=interval_seconds)
        logger.info(f"⏰ Next sync scheduled for: {next_run.strftime('%Y-%m-%d %H:%M:%S')}")
        
        await asyncio.sleep(interval_seconds)
        await trigger_dispatcher()


if __name__ == "__main__":
    try:
        asyncio.run(run_scheduler())
    except KeyboardInterrupt:
        logger.info("🛑 Scheduler stopped by user")
