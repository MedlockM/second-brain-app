import asyncio
import logging
from unittest.mock import MagicMock, patch
from media_summarizer.core.services.episode_submission import submit_episode_for_user

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def test_credit_check():
    logger.info("Testing Credit Check Logic...")
    
    # Mock User
    user = MagicMock()
    user.id = "test_user_id"
    user.email = "test@example.com"
    
    # Case 1: Insufficient Credits
    logger.info("Case 1: Insufficient Credits")
    with patch("media_summarizer.core.services.episode_submission.get_total_available_minutes", return_value=5) as mock_get_minutes:
        # Episode duration 10 mins -> requires 10 credits
        result = await submit_episode_for_user(
            user=user,
            episode_guid="guid_1",
            episode_title="Long Episode",
            feed_title="Test Feed",
            audio_url="http://example.com/audio.mp3",
            duration_seconds=600, # 10 mins
        )
        
        if result.get("status") == "skipped" and result.get("reason") == "insufficient_credits":
            logger.info("PASS: Correctly skipped due to insufficient credits.")
        else:
            logger.error(f"FAIL: Expected skipped, got {result}")

    # Case 2: Sufficient Credits
    logger.info("Case 2: Sufficient Credits")
    with patch("media_summarizer.core.services.episode_submission.get_total_available_minutes", return_value=20) as mock_get_minutes:
        # Mock the rest of the flow to avoid DB calls
        with patch("media_summarizer.core.services.episode_submission.episode_idempotence.reserve_or_skip", return_value=True), \
             patch("media_summarizer.core.services.episode_submission.database_async.create_processing_job") as mock_create_job, \
             patch("media_summarizer.core.services.episode_submission.allocate_hold_for_job"), \
             patch("media_summarizer.core.services.episode_submission.database_async.update_processing_job"), \
             patch("media_summarizer.core.services.episode_submission.sqs.send_message"):
            
            mock_job = MagicMock()
            mock_job.id = "job_123"
            mock_job.status.value = "pending"
            mock_create_job.return_value = mock_job
            
            result = await submit_episode_for_user(
                user=user,
                episode_guid="guid_2",
                episode_title="Short Episode",
                feed_title="Test Feed",
                audio_url="http://example.com/audio.mp3",
                duration_seconds=300, # 5 mins
            )
            
            if result.get("status") == "pending":
                logger.info("PASS: Correctly proceeded with submission.")
            else:
                logger.error(f"FAIL: Expected pending, got {result}")

if __name__ == "__main__":
    asyncio.run(test_credit_check())
