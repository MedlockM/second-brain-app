"""
Summarization worker for processing transcriptions and generating summaries using LLM.

Migrated to use the new utils for S3 and SQS operations instead of direct AWS libraries.
"""

import asyncio
import json
import json as json_module
import logging
import os
from datetime import datetime
from typing import Any, Dict, Optional

import aiohttp
from tenacity import retry, stop_after_attempt, wait_exponential

from media_summarizer.utils import s3, sqs
from media_summarizer.utils.logging_config import bind_log_context, log_event, reset_log_context
from media_summarizer.workers.base_worker import (
    get_sqs_receive_params,
    process_message_with_retry,
)


class LLMAPIError(Exception):
    """Exception raised when LLM API returns an error or refuses to process content."""

    pass


logger = logging.getLogger(__name__)


# Minimal class wrapper for backward-compatibility with tests that patch
class SummarizationWorker:
    async def run(self):
        await poll_queue()


# Configuration
SUMMARY_BUCKET = os.environ.get("SUMMARY_BUCKET", "media-summarizer-summaries")
TRANSCRIPT_BUCKET = os.environ.get("TRANSCRIPT_BUCKET", "")
EPISODE_COMPLETED_EVENTS_QUEUE = os.environ.get(
    "EPISODE_COMPLETED_EVENTS_QUEUE", "episode-completed-events"
)
FLASHCARDS_QUEUE = os.environ.get("FLASHCARDS_QUEUE", "flashcards-queue")
FLASHCARDS_AUTO_GENERATE = os.environ.get(
    "FLASHCARDS_AUTO_GENERATE", "true"
).lower() == "true"


# LLM timeout from env (seconds)
LLM_TIMEOUT_SECONDS = int(os.environ.get("LLM_TIMEOUT_SECONDS", "120"))

# LLM model — validated by owner in task-72 benchmark
LLM_MODEL = os.environ.get("OPENAI_MODEL", "gpt-5.4-nano-2026-03-17")


async def call_llm_api(api_url, api_key, transcription, podcast_title, episode_title):
    """Call LLM API directly for summarization."""
    prompt = f"""
    Please summarize the following podcast episode transcript in the SAME LANGUAGE as the transcript itself.

    Podcast: {podcast_title}
    Episode: {episode_title}

    Transcript:
    {transcription}

    IMPORTANT: Your summary MUST be written in the same language as the transcript above (French, English, Spanish, etc.).

    Please provide a structured summary with:
    - Main topics discussed
    - Key points
    - Notable quotes (if any)
    - Conclusion

    Format the response as JSON with these fields: main_topics, key_points, notable_quotes, conclusion
    """

    timeout = aiohttp.ClientTimeout(total=LLM_TIMEOUT_SECONDS)
    async with aiohttp.ClientSession(timeout=timeout) as session:
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }

        payload = {
            "model": LLM_MODEL,
            "messages": [{"role": "user", "content": prompt}],
            "max_completion_tokens": 1000,
        }

        # Only add temperature for models that support it (not o1/o3/gpt-5 family)
        if not any(x in LLM_MODEL.lower() for x in ["o1", "o3", "gpt-5"]):
            payload["temperature"] = 0.7

        async with session.post(api_url, headers=headers, json=payload) as response:
            response.raise_for_status()
            result = await response.json()

            # Extract the content from the response
            content = result["choices"][0]["message"]["content"]

            # Debug logging to see LLM response
            logger.info(f"LLM model: {LLM_MODEL}")
            logger.info(f"LLM response length: {len(content)} chars")
            logger.info(f"LLM response (first 500 chars): {content[:500]}")

            # Check if the LLM response indicates an error or inability to process
            error_indicators = [
                "cannot generate",
                "impossible to",
                "not possible to",
                "unable to",
                "challenging to understand",
                "typographical errors",
                "clear and accurate transcript",
                "incorrectly formatted",
                "translation error",
                "nonsensical",
            ]

            content_lower = content.lower()
            if any(indicator in content_lower for indicator in error_indicators):
                raise LLMAPIError(f"LLM refused to process content: {content[:200]}...")

            # Try to parse as JSON, fallback to plain text only for valid summaries
            try:
                summary_data = json_module.loads(content)
                return summary_data
            except json_module.JSONDecodeError:
                # If it's not JSON but also not an error, treat as plain text summary
                if len(content.strip()) < 50:
                    raise LLMAPIError(
                        f"LLM response too short, likely an error: {content}"
                    )

                return {
                    "main_topics": ["Content summarized"],
                    "key_points": [
                        content[:500] + "..." if len(content) > 500 else content
                    ],
                    "notable_quotes": [],
                    "conclusion": "Summary provided in plain text format",
                }


SUMMARIZATION_QUEUE = os.environ.get("SUMMARIZATION_QUEUE", "summarization-queue")
TEST_MODE = os.environ.get("TEST_MODE", "false").lower() == "true"


async def upload_summary(bucket: str, key: str, summary_data: Dict[str, Any]) -> None:
    """Upload a summary to S3 asynchronously using utils."""
    try:
        summary_json = json.dumps(summary_data, indent=2)
        summary_bytes = summary_json.encode("utf-8")

        # Use BytesIO to create a file-like object
        from io import BytesIO

        summary_file = BytesIO(summary_bytes)

        await s3.upload_file_object(
            bucket=bucket,
            key=key,
            file_obj=summary_file,
            content_type="application/json",
            metadata={
                "content-type": "application/json",
                "job-type": "podcast-summary",
            },
        )

        logger.info(f"Successfully uploaded summary to s3://{bucket}/{key}")

    except Exception as e:
        logger.error(f"Failed to upload summary to S3: {str(e)}")
        raise


async def download_transcription(bucket: str, key: str) -> str:
    """Download transcription from S3 asynchronously using utils."""
    try:
        # Download the transcription content
        content = await s3.download_file_to_memory(bucket=bucket, key=key)

        # Decode bytes to string
        transcription_text = content.decode("utf-8")

        logger.info(f"Successfully downloaded transcription from s3://{bucket}/{key}")
        return transcription_text

    except Exception as e:
        logger.error(f"Failed to download transcription from S3: {str(e)}")
        raise


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=4, max=10))
async def generate_summary_with_retry(
    transcription_text: str, job_data: Dict[str, Any]
) -> Dict[str, Any]:
    """Generate summary with retry logic."""
    try:
        # Initialize the summarization service with environment variables
        llm_api_url = os.environ.get(
            "LLM_API_URL", "https://api.openai.com/v1/chat/completions"
        )
        llm_api_key = os.environ.get("OPENAI_API_KEY")

        if not llm_api_key:
            raise ValueError("OPENAI_API_KEY environment variable is required")

        # Extract metadata for better summarization
        podcast_title = job_data.get("podcast_title", "Unknown Podcast")
        episode_title = job_data.get("episode_title", "Unknown Episode")

        # Generate the summary using direct API call
        summary_result = await call_llm_api(
            llm_api_url, llm_api_key, transcription_text, podcast_title, episode_title
        )

        logger.info(f"Successfully generated summary for job {job_data.get('job_id')}")
        return summary_result
    except Exception as e:
        logger.error(f"Unexpected error during summarization: {str(e)}")
        raise


async def process_summarization_message(message_body: Dict[str, Any]) -> None:
    """
    Process a single summarization message.

    Args:
        message_body: The message body containing job information
    """
    job_id = message_body.get("job_id")
    transcript_s3_key = message_body.get("transcript_s3_key")
    transcript_bucket = message_body.get("transcript_bucket") or TRANSCRIPT_BUCKET

    if not all([job_id, transcript_s3_key]):
        logger.error(f"Missing required fields in message: {message_body}")
        raise ValueError("Missing required fields in summarization message")

    if not transcript_bucket:
        raise ValueError(
            "transcript_bucket not provided in message and TRANSCRIPT_BUCKET env var is not set"
        )

    # Ensure all required fields are strings
    if not isinstance(job_id, str) or not isinstance(transcript_s3_key, str):
        logger.error(f"Invalid field types in message: {message_body}")
        raise ValueError("Invalid field types in summarization message")

    logger.info(f"Starting summarization for job {job_id}")

    # Update job status to summarizing
    from media_summarizer.utils import database_async

    job = await database_async.get_processing_job_by_id(job_id)
    if job:
        job.mark_summarizing()
        await database_async.update_processing_job(job)

    try:
        import time

        # Download the transcription
        logger.info(f"Downloading transcription for job {job_id}")
        transcription_text = await download_transcription(
            transcript_bucket, transcript_s3_key
        )

        if not transcription_text or len(transcription_text.strip()) == 0:
            raise ValueError("Empty or invalid transcription content")

        # Generate the summary
        logger.info(f"Generating summary for job {job_id}")
        start_time = time.time()
        summary_result = await generate_summary_with_retry(
            transcription_text, message_body
        )
        summarization_duration = time.time() - start_time

        # Prepare summary data for storage
        summary_data = {
            "job_id": job_id,
            "podcast_title": message_body.get("podcast_title", "Unknown Podcast"),
            "episode_title": message_body.get("episode_title", "Unknown Episode"),
            "episode_image": message_body.get("episode_image", ""),
            "summary": summary_result,
            "transcription_length": len(transcription_text),
            "generated_at": datetime.now().isoformat(),
            "processing_metadata": {
                "transcript_s3_key": transcript_s3_key,
                "summary_s3_key": f"{job_id}.json",
            },
        }

        # Upload summary to S3
        summary_s3_key = f"{job_id}.json"
        logger.info(f"Uploading summary for job {job_id}")
        await upload_summary(SUMMARY_BUCKET, summary_s3_key, summary_data)

        # Update job with summary location and duration
        if job:
            job.set_summary_location(summary_s3_key)
            job.set_processing_duration("summarization", int(summarization_duration))
            await database_async.update_processing_job(job)

        # Finalize minute usage based on audio duration if provided; fallback to heuristic
        try:
            from math import ceil

            provided_duration = message_body.get("audio_duration_seconds")
            if isinstance(provided_duration, (int, float)) and provided_duration > 0:
                minutes_used = max(1, ceil(provided_duration / 60))
            else:
                # Fallback heuristic if duration missing
                minutes_used = max(1, int(len(transcription_text) / 800))
            from media_summarizer.core.services.minute_pool import finalize_usage

            await finalize_usage(job_id, minutes_used)

            # Publish episode-completed event for watchers fan-out
            try:
                await sqs.send_message(
                    queue_name=EPISODE_COMPLETED_EVENTS_QUEUE,
                    message_body={
                        "event_type": "episode_completed",
                        "episode_guid": message_body.get("episode_guid"),
                        "canonical_job_id": job_id,
                        "summary_s3_key": summary_s3_key,
                        "podcast_title": message_body.get("podcast_title"),
                        "episode_title": message_body.get("episode_title"),
                        "minutes_used": minutes_used,
                    },
                )
            except Exception as ee:
                logger.warning(
                    f"Failed to publish episode-completed event for job {job_id}: {ee}"
                )

            # Auto-trigger flashcards generation after transcript completion
            if FLASHCARDS_AUTO_GENERATE:
                try:
                    from media_summarizer.core.services.artifact_service import (
                        request_artifact_generation,
                    )
                    from media_summarizer.core.models.media_artifact import MediaArtifactType

                    await request_artifact_generation(
                        media_item_id=job_id,
                        job=job,
                        artifact_type=MediaArtifactType.FLASHCARDS,
                    )
                    logger.info(f"Auto-triggered flashcards generation for job {job_id}")
                except Exception as fc_err:
                    logger.warning(
                        f"Failed to auto-trigger flashcards for job {job_id}: {fc_err}"
                    )
        except Exception as e:
            logger.warning(f"Failed to finalize minute usage for job {job_id}: {e}")

        # Generate summary URL (presigned URL for access)
        try:
            summary_url = await s3.generate_presigned_url(
                bucket=SUMMARY_BUCKET,
                key=summary_s3_key,
                expiration=3600 * 24 * 7,  # 7 days
            )
        except Exception as e:
            logger.warning(f"Failed to generate presigned URL: {str(e)}")
            summary_url = f"s3://{SUMMARY_BUCKET}/{summary_s3_key}"

        logger.info(f"Successfully completed summarization for job {job_id}")

    except Exception as e:
        logger.error(f"Summarization failed for job {job_id}: {e}", exc_info=True)
        raise


async def process_message(
    message: Dict[str, Any],
    llm_api_url: Optional[str] = None,
    llm_api_key: Optional[str] = None,
) -> None:
    """
    Process an SQS message for summarization.

    Args:
        message: SQS message containing job information
    """
    try:
        # Parse message body
        body = json.loads(message.get("Body", "{}"))

        # Process the summarization
        await process_summarization_message(body)

    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse message body: {str(e)}")
        raise
    except Exception as e:
        logger.error(f"Error processing summarization message: {str(e)}")
        raise


async def poll_queue() -> None:
    """
    Poll the SQS queue for summarization messages.
    """
    logger.info("Starting summarization worker - polling queue")

    while True:
        try:
            # Receive messages from the queue
            messages = await sqs.receive_messages(
                queue_name=SUMMARIZATION_QUEUE,
                max_messages=1,  # Process one at a time for LLM rate limiting
                wait_time_seconds=20,  # Long polling
                visibility_timeout=300,  # 5 minutes for processing
            )

            if messages:
                logger.info(f"Received {len(messages)} messages")

                # Process messages one by one
                for message in messages:
                    # Use base_worker retry logic which handles retries, logging, and DLQ/Failure
                    await process_message_with_retry(
                        message=message,
                        processor=process_message,
                        queue_name=SUMMARIZATION_QUEUE,
                        max_retries=3,
                        worker_name="summarization"
                    )

            # Small delay to prevent excessive API calls
            await asyncio.sleep(1)

        except Exception as e:
            logger.error(f"Error polling summarization queue: {str(e)}")
            # Wait before retrying
            await asyncio.sleep(5)


async def main() -> None:
    """
    Main entry point for the summarization worker.
    """
    logger.info("Starting summarization worker")
    await poll_queue()


if __name__ == "__main__":
    from media_summarizer.utils.logging_config import setup_logging as _setup_logging
    _setup_logging("worker-summarization")
    asyncio.run(main())
