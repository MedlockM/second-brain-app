"""
Fixtures and configuration for end-to-end tests.
"""
import os
import logging
import boto3
import pytest

logger = logging.getLogger(__name__)


@pytest.fixture(autouse=True)
def cleanup_episode_idempotence_before_and_after():
    """Clean episode_idempotence table before and after each E2E test.
    
    BEFORE is critical: prevents pollution from previous test runs.
    AFTER is nice-to-have: cleanup for the next developer/CI run.
    """
    # BEFORE: Clean table to avoid duplicate detection from previous runs
    _clean_episode_idempotence_table()
    
    yield  # Test runs here
    
    # AFTER: Cleanup (nice-to-have, but BEFORE is what matters)
    _clean_episode_idempotence_table()


def _clean_episode_idempotence_table():
    """Delete all items from episode_idempotence table."""
    try:
        dynamodb = boto3.resource(
            "dynamodb",
            endpoint_url=os.environ.get("AWS_ENDPOINT_URL"),
            region_name=os.environ.get("AWS_REGION", "us-east-1"),
            aws_access_key_id=os.environ.get("AWS_ACCESS_KEY_ID", "test"),
            aws_secret_access_key=os.environ.get("AWS_SECRET_ACCESS_KEY", "test"),
        )
        table = dynamodb.Table("episode_idempotence")
        
        response = table.scan()
        items = response.get("Items", [])
        
        if items:
            logger.info(f"Cleaning {len(items)} items from episode_idempotence")
            with table.batch_writer() as batch:
                for item in items:
                    batch.delete_item(Key={"episode_guid": item["episode_guid"]})
    except Exception as e:
        logger.warning(f"Could not cleanup episode_idempotence table: {e}")
        # Don't fail the test if cleanup fails - it's best-effort
