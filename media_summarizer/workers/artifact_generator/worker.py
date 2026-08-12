"""
Unified artifact generator worker.

Polls a single SQS queue (artifact-generator-queue) and dispatches to
per-kind generators based on `body.artifact_type`. Shared logic for S3
download, LLM call, retries, validation, and status transitions lives here
once instead of being duplicated across 5 separate workers.

Consolidates the former flashcards, notes, quiz, summarization, and summary
workers (task-195).
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import re
from datetime import datetime, timezone
from typing import Any, Dict

import aiohttp

from media_summarizer.core.models.media_artifact import MediaArtifactType
from media_summarizer.core.services import fsrs_service
from media_summarizer.core.services.artifact_service import (
    complete_artifact_generation,
    fail_artifact_generation,
    mark_artifact_generating,
)
from media_summarizer.utils import database_async, s3, sqs
from media_summarizer.utils.env import required_env
from media_summarizer.utils.logging_config import (
    bind_log_context,
    log_event,
    reset_log_context,
    setup_logging,
)

logger = logging.getLogger(__name__)

ARTIFACT_GENERATOR_QUEUE = required_env("ARTIFACT_GENERATOR_QUEUE")
TRANSCRIPT_BUCKET = required_env("TRANSCRIPT_BUCKET")
LLM_API_URL = os.environ.get(
    "LLM_API_URL", "https://api.openai.com/v1/chat/completions"
)
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")


class ArtifactValidationError(Exception):
    """Raised when the model output does not pass the generator's validator."""


def _strip_code_fences(content: str) -> str:
    """Remove markdown code fences from LLM output."""
    cleaned = content.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
        cleaned = re.sub(r"\s*```$", "", cleaned)
    return cleaned.strip()


async def _download_transcript(key: str, bucket: str = TRANSCRIPT_BUCKET) -> str:
    """Download transcript text from S3."""
    content = await s3.download_file_to_memory(bucket=bucket, key=key)
    return content.decode("utf-8")


async def _call_llm(
    prompt: str,
    model: str,
    artifact_type: str,
    response_format: Dict[str, Any] | None = None,
) -> str:
    """Call the LLM API and return the raw content string."""
    if not OPENAI_API_KEY:
        raise ValueError("OPENAI_API_KEY environment variable is required")

    timeout = aiohttp.ClientTimeout(
        total=int(os.environ.get("LLM_TIMEOUT_SECONDS", "180"))
    )
    payload: Dict[str, Any] = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
    }

    if response_format is not None:
        payload["response_format"] = response_format

    # gpt-5 family does not support temperature parameter
    model_lower = (model or "").lower()
    if not any(marker in model_lower for marker in ["o1", "o3", "gpt-5"]):
        try:
            payload["temperature"] = float(os.environ.get("LLM_TEMPERATURE", "0.3"))
        except Exception:
            payload["temperature"] = 0.3

    async with aiohttp.ClientSession(timeout=timeout) as session:
        async with session.post(
            LLM_API_URL,
            headers={
                "Authorization": f"Bearer {OPENAI_API_KEY}",
                "Content-Type": "application/json",
            },
            json=payload,
        ) as response:
            if response.status >= 400:
                body = await response.text()
                log_event(
                    logger,
                    logging.ERROR,
                    "external_call.failed",
                    "LLM API returned an error",
                    provider="openai",
                    artifact_type=artifact_type,
                    status=response.status,
                    detail=body[:500],
                )
            response.raise_for_status()
            result = await response.json()
            return result["choices"][0]["message"]["content"]


def _supports_structured_outputs(model: str) -> bool:
    """Check if the model supports OpenAI Structured Outputs."""
    model_lower = (model or "").lower()
    return any(
        marker in model_lower
        for marker in ["gpt-4o", "gpt-5", "gpt-4.1"]
    )


async def process_message(message: Dict[str, Any]) -> None:
    """Process a single artifact generation message from the unified queue."""
    from media_summarizer.workers.artifact_generator.generators import GENERATORS

    body = json.loads(message.get("Body", "{}"))
    artifact_id = body.get("artifact_id")
    artifact_type_str = body.get("artifact_type")
    transcript_s3_key = body.get("transcript_s3_key")
    transcript_bucket = body.get("transcript_bucket") or TRANSCRIPT_BUCKET
    parameters = body.get("parameters") or {}
    language = parameters.get("language")
    podcast_title = body.get("podcast_title")
    episode_title = body.get("episode_title")
    # Translation provenance set by the common detect+translate step (task-192).
    translation = body.get("translation") if isinstance(body.get("translation"), dict) else None

    # Resolve artifact type
    try:
        artifact_type = MediaArtifactType(artifact_type_str)
    except (ValueError, KeyError):
        log_event(
            logger,
            logging.ERROR,
            "worker.unknown_artifact_type",
            f"Unknown artifact_type: {artifact_type_str}",
            artifact_id=artifact_id,
        )
        raise ValueError(f"Unknown artifact_type: {artifact_type_str}")

    generator = GENERATORS.get(artifact_type)
    if generator is None:
        log_event(
            logger,
            logging.ERROR,
            "worker.unsupported_artifact_type",
            f"No generator registered for artifact_type: {artifact_type_str}",
            artifact_id=artifact_id,
        )
        raise ValueError(f"No generator for artifact_type: {artifact_type_str}")

    context_token = bind_log_context(
        artifact_id=artifact_id,
        media_item_id=body.get("media_item_id"),
        artifact_type=artifact_type.value,
    )

    try:
        if not all([artifact_id, transcript_s3_key]):
            log_event(
                logger,
                logging.ERROR,
                "worker.invalid_message",
                f"Missing fields for {artifact_type.value} generation",
                queue=ARTIFACT_GENERATOR_QUEUE,
            )
            raise ValueError(f"Missing fields for {artifact_type.value} generation")

        await mark_artifact_generating(artifact_id)

        transcript = await _download_transcript(
            transcript_s3_key,
            bucket=transcript_bucket,
        )

        # Build prompt
        prompt = generator.build_prompt(
            transcript,
            language=language,
            podcast_title=podcast_title,
            episode_title=episode_title,
        )

        # Determine model and structured output support
        model = generator.default_model
        response_format = None
        uses_structured_outputs = _supports_structured_outputs(model)
        schema = generator.response_format_schema()
        if uses_structured_outputs and schema is not None:
            response_format = schema

        # Call LLM
        raw_content = await _call_llm(
            prompt=prompt,
            model=model,
            artifact_type=artifact_type.value,
            response_format=response_format,
        )

        # Unwrap structured response wrapper if applicable
        if uses_structured_outputs and schema is not None:
            raw_content = generator.unwrap_structured_response(raw_content)

        # Validate
        validated = generator.validate(raw_content)

        # Build artifact content
        artifact_content = generator.build_artifact_content(validated, body=body)

        envelope: Dict[str, Any] = {
            "artifact_id": artifact_id,
            "media_item_id": body.get("media_item_id"),
            "artifact_type": artifact_type.value,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "source": {
                "transcript_s3_key": transcript_s3_key,
                "generator_version": body.get("generator_version"),
                "podcast_title": podcast_title,
                "episode_title": episode_title,
            },
            "content": artifact_content,
        }
        if translation is not None:
            envelope["translation"] = translation

        await complete_artifact_generation(
            artifact_id=artifact_id,
            content=envelope,
        )

        # Post-generation hooks (per-kind)
        if artifact_type == MediaArtifactType.FLASHCARDS:
            await _init_fsrs_cards(body, artifact_id, validated)

    except Exception as exc:
        # Determine error code for validation errors
        error_code = None
        from media_summarizer.workers.artifact_generator.generators.flashcards import FlashcardsValidationError
        from media_summarizer.workers.artifact_generator.generators.notes import NotesValidationError
        from media_summarizer.workers.artifact_generator.generators.quiz import QuizValidationError
        from media_summarizer.workers.artifact_generator.generators.summary_detailed import (
            SummaryDetailedValidationError,
        )
        from media_summarizer.workers.artifact_generator.generators.summary_short import SummaryShortValidationError

        if isinstance(exc, (
            FlashcardsValidationError,
            NotesValidationError,
            QuizValidationError,
            SummaryShortValidationError,
            SummaryDetailedValidationError,
        )):
            error_code = "VALIDATION_ERROR"

        if artifact_id:
            await fail_artifact_generation(
                artifact_id=artifact_id,
                error_message=str(exc),
                error_code=error_code,
            )
        raise
    finally:
        reset_log_context(context_token)


async def _init_fsrs_cards(
    body: Dict[str, Any],
    artifact_id: str,
    flashcards: Any,
) -> None:
    """Initialize FSRS review schedule cards for spaced repetition (flashcards only)."""
    media_item_id = body.get("media_item_id")
    if not media_item_id:
        return
    try:
        job = await database_async.get_processing_job_by_id(media_item_id)
        if job:
            await fsrs_service.initialize_cards_for_flashcards(
                user_id=job.user_id,
                media_item_id=media_item_id,
                artifact_id=artifact_id,
                flashcards=flashcards,
            )
    except Exception as fsrs_exc:
        # Non-fatal: flashcard generation succeeded, FSRS init is best-effort
        log_event(
            logger,
            logging.WARNING,
            "worker.fsrs_init_failed",
            "Failed to initialize FSRS cards (non-fatal)",
            artifact_id=artifact_id,
            media_item_id=media_item_id,
            error_type=type(fsrs_exc).__name__,
            detail=str(fsrs_exc)[:200],
        )


async def poll_queue() -> None:
    """Poll the unified artifact-generator queue."""
    from media_summarizer.workers.base_worker import process_message_with_retry

    log_event(
        logger,
        logging.INFO,
        "worker.started",
        "Starting artifact-generator worker queue poller",
        queue=ARTIFACT_GENERATOR_QUEUE,
    )
    while True:
        try:
            messages = await sqs.receive_messages(
                queue_name=ARTIFACT_GENERATOR_QUEUE,
                max_messages=5,
                wait_time_seconds=20,
                visibility_timeout=int(os.environ.get("SQS_VISIBILITY_TIMEOUT", "120")),
            )
            if messages:
                for message in messages:
                    await process_message_with_retry(
                        message=message,
                        processor=process_message,
                        queue_name=ARTIFACT_GENERATOR_QUEUE,
                        max_retries=int(os.environ.get("ARTIFACT_GENERATOR_MAX_RETRIES", "3")),
                        worker_name="artifact-generator-worker",
                    )
            await asyncio.sleep(1)
        except Exception as exc:
            log_event(
                logger,
                logging.ERROR,
                "worker.polling_error",
                "Artifact generator worker polling failed",
                queue=ARTIFACT_GENERATOR_QUEUE,
                exc_info=exc,
            )
            await asyncio.sleep(5)


async def main() -> None:
    setup_logging("artifact-generator-worker")
    await poll_queue()


if __name__ == "__main__":
    asyncio.run(main())
