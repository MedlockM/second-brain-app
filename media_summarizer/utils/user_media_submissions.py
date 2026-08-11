"""
User media submissions tracking utilities using DynamoDB.

Purpose: prevent re-submitting the same media item for the same user when
scanning external sources.

Table schema:
- Env var: USER_MEDIA_SUBMISSIONS_TABLE (default "user_media_submissions")
- PK: user_id (S)
- SK: media_key (S)
- Attributes: submitted_at (ISO), job_id (S), source (S)
"""
from __future__ import annotations

from datetime import datetime, timezone

from botocore.exceptions import ClientError

from media_summarizer.utils import database_async
from media_summarizer.utils.env import required_env

USER_MEDIA_SUBMISSIONS_TABLE = required_env("USER_MEDIA_SUBMISSIONS_TABLE")


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


async def has_user_already_submitted(user_id: str, media_key: str) -> bool:
    """
    Return True if this user has already SUCCESSFULLY submitted this media key,
    OR if the previous submission failed after exhausting all retries.

    Returns False if:
    - No previous submission exists
    - Previous submission's job failed but can still be retried (retry_count < max_retries)

    This allows automatic retry for failed jobs, but blocks re-submission after max retries.
    """
    import logging
    logger = logging.getLogger(__name__)

    session = database_async.get_session()
    async with session.resource(
        "dynamodb",
        
        region_name=database_async.AWS_REGION,
    ) as dynamodb:
        table = await dynamodb.Table(USER_MEDIA_SUBMISSIONS_TABLE)
        resp = await table.get_item(
            Key={
                "user_id": user_id,
                "media_key": media_key,
            }
        )

        if "Item" not in resp:
            return False  # No previous submission

        # Check if the associated job completed successfully or failed permanently
        item = resp["Item"]
        job_id = item.get("job_id")

        if not job_id:
            # No job_id recorded, be conservative and block
            logger.warning(f"Submission found for user {user_id}, media_key {media_key} but no job_id")
            return True

        try:
            job = await database_async.get_processing_job_by_id(job_id)

            if not job:
                # Job not found, allow retry
                logger.warning(f"Job {job_id} not found for submission, allowing retry")
                return False

            # Block if job completed successfully (no error_step)
            if job.job_status == "completed" and not getattr(job, "error_step", None):
                logger.info(f"Media key {media_key} already successfully processed for user {user_id}")
                return True

            # Block if job failed AND exhausted all retries
            if getattr(job, "error_step", None):
                retry_count = getattr(job, "retry_count", 0)
                max_retries = getattr(job, "max_retries", 3)

                if retry_count >= max_retries:
                    # Max retries exhausted, block re-submission
                    logger.info(
                        f"Media key {media_key} failed permanently for user {user_id} "
                        f"(retries: {retry_count}/{max_retries}), blocking re-submission"
                    )
                    return True
                else:
                    # Still has retries left, allow retry
                    logger.info(
                        f"Media key {media_key} failed but can retry for user {user_id} "
                        f"(retries: {retry_count}/{max_retries}), allowing retry"
                    )
                    return False

            # Job still processing, block to avoid duplicates
            logger.info(f"Media key {media_key} still processing for user {user_id}")
            return True

        except Exception as e:
            # If we can't verify job status, be conservative and block
            logger.error(f"Error checking job status for {job_id}: {e}")
            return True


async def mark_user_submission(
    *, user_id: str, media_key: str, job_id: str, source: str
) -> bool:
    """
    Record that a user submitted a media item.

    Records submissions in canonical media-keyed table only.
    """
    item = {
        "user_id": user_id,
        "media_key": media_key,
        "submitted_at": _now_iso(),
        "job_id": job_id,
        "source": source,
    }
    session = database_async.get_session()
    try:
        async with session.resource(
            "dynamodb",
            
            region_name=database_async.AWS_REGION,
        ) as dynamodb:
            table = await dynamodb.Table(USER_MEDIA_SUBMISSIONS_TABLE)
            await table.put_item(
                Item=item,
                ConditionExpression="attribute_not_exists(user_id)",
            )
        return True
    except ClientError as e:
        # If already exists, treat as no-op
        if e.response.get("Error", {}).get("Code") == "ConditionalCheckFailedException":
            return False
        raise
