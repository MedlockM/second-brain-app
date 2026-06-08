"""
Flashcards generation worker for canonical artifact generation.

Generates Q/A flashcards from a transcript using an LLM. The flashcards
follow the minimum information principle: one concept per card, no trivial
or ambiguous questions. Output is a JSON array of {question, answer} objects.

Model choice validated by owner (task-72 benchmark): gpt-5.4-nano-2026-03-17
for flashcards. Uses OpenAI Structured Outputs (response_format) for
reliable JSON generation.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import re
from datetime import datetime, timezone
from typing import Any, Dict, List

import aiohttp
from pydantic import BaseModel, ValidationError, field_validator

from media_summarizer.core.services.artifact_service import (
    complete_artifact_generation,
    fail_artifact_generation,
    mark_artifact_generating,
)
from media_summarizer.core.services import fsrs_service
from media_summarizer.utils import database_async, s3, sqs
from media_summarizer.utils.logging_config import (
    bind_log_context,
    log_event,
    reset_log_context,
    setup_logging,
)

logger = logging.getLogger(__name__)

FLASHCARDS_QUEUE = os.environ.get("FLASHCARDS_QUEUE", "flashcards-queue")
TRANSCRIPT_BUCKET = os.environ.get(
    "TRANSCRIPT_BUCKET", "media-summarizer-transcripts"
)
LLM_API_URL = os.environ.get(
    "LLM_API_URL", "https://api.openai.com/v1/chat/completions"
)
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")
LLM_MODEL = os.environ.get(
    "FLASHCARDS_LLM_MODEL",
    os.environ.get("OPENAI_MODEL", "gpt-5.4-nano-2026-03-17"),
)

MIN_FLASHCARDS = 5
MAX_FLASHCARDS = 15


class FlashcardsValidationError(Exception):
    """Raised when the model output does not match the canonical flashcards schema."""


class FlashcardItem(BaseModel):
    question: str
    answer: str

    @field_validator("question", "answer")
    @classmethod
    def _non_empty_text(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("value must be non-empty")
        return normalized


def _build_flashcards_prompt(transcript: str, language: str | None = None) -> str:
    language_instruction = (
        f"Use {language} for the output."
        if language
        else "Use the same language as the transcript."
    )
    return f"""You produce a set of Q&A flashcards from a transcript for spaced repetition learning.

Rules:
- {language_instruction}
- Output STRICT JSON only. No markdown. No commentary. No code fences.
- Return a JSON array of objects, each with exactly two keys: "question" and "answer".
- Generate between {MIN_FLASHCARDS} and {MAX_FLASHCARDS} flashcards depending on content density.
- Follow the minimum information principle: one concept per card.
- Do NOT generate trivial cards (e.g. "What is the title of this episode?").
- Do NOT generate ambiguous cards: each question must have a single, verifiable answer.
- Keep questions clear and concise.
- Keep answers factual and brief (1-3 sentences max).
- Avoid sponsor/ad content unless it is central to the source material.
- Cover the most important concepts, facts, and takeaways from the transcript.

Return JSON with this exact schema:
[
  {{
    "question": "...",
    "answer": "..."
  }}
]

Transcript:
{transcript}
"""


def _strip_code_fences(content: str) -> str:
    cleaned = content.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
        cleaned = re.sub(r"\s*```$", "", cleaned)
    return cleaned.strip()


def _validate_flashcards_payload(content: str) -> List[Dict[str, Any]]:
    try:
        parsed = json.loads(_strip_code_fences(content))
    except json.JSONDecodeError as exc:
        raise FlashcardsValidationError(
            f"flashcards output is not valid JSON: {exc}"
        ) from exc

    if not isinstance(parsed, list):
        raise FlashcardsValidationError("flashcards output must be a JSON array")

    if len(parsed) < MIN_FLASHCARDS:
        raise FlashcardsValidationError(
            f"flashcards output must contain at least {MIN_FLASHCARDS} items, got {len(parsed)}"
        )

    if len(parsed) > MAX_FLASHCARDS:
        # Silently truncate to MAX_FLASHCARDS rather than failing
        parsed = parsed[:MAX_FLASHCARDS]

    validated: List[Dict[str, Any]] = []
    for idx, item in enumerate(parsed):
        if not isinstance(item, dict):
            raise FlashcardsValidationError(
                f"flashcards item at index {idx} must be a JSON object"
            )
        try:
            card = FlashcardItem.model_validate(item)
        except ValidationError as exc:
            raise FlashcardsValidationError(
                f"flashcards item at index {idx} schema validation failed: {exc}"
            ) from exc
        validated.append(card.model_dump())

    return validated


async def _download_transcript(key: str, bucket: str = TRANSCRIPT_BUCKET) -> str:
    content = await s3.download_file_to_memory(bucket=bucket, key=key)
    return content.decode("utf-8")


def _build_response_format_schema() -> Dict[str, Any]:
    """Build the JSON Schema for OpenAI Structured Outputs (response_format).

    This ensures the model returns valid JSON matching our flashcard structure,
    eliminating parse failures for models that support native structured outputs.
    """
    return {
        "type": "json_schema",
        "json_schema": {
            "name": "flashcards",
            "strict": True,
            "schema": {
                "type": "object",
                "properties": {
                    "cards": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "question": {"type": "string"},
                                "answer": {"type": "string"},
                            },
                            "required": ["question", "answer"],
                            "additionalProperties": False,
                        },
                    }
                },
                "required": ["cards"],
                "additionalProperties": False,
            },
        },
    }


async def _call_llm_for_flashcards(
    transcript: str,
    language: str | None = None,
) -> List[Dict[str, Any]]:
    if not OPENAI_API_KEY:
        raise ValueError("OPENAI_API_KEY environment variable is required")

    timeout = aiohttp.ClientTimeout(
        total=int(os.environ.get("LLM_TIMEOUT_SECONDS", "180"))
    )
    payload: Dict[str, Any] = {
        "model": LLM_MODEL,
        "messages": [
            {"role": "user", "content": _build_flashcards_prompt(transcript, language)}
        ],
    }

    # Use OpenAI Structured Outputs for models that support it (gpt-4o, gpt-5 family)
    # This guarantees valid JSON output matching our schema.
    model_lower = (LLM_MODEL or "").lower()
    supports_structured_outputs = any(
        marker in model_lower
        for marker in ["gpt-4o", "gpt-5", "gpt-4.1"]
    )
    if supports_structured_outputs:
        payload["response_format"] = _build_response_format_schema()

    # gpt-5 family does not support temperature parameter
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
                    "Flashcards LLM API returned an error",
                    provider="openai",
                    artifact_type="flashcards",
                    status=response.status,
                    detail=body[:500],
                )
            response.raise_for_status()
            result = await response.json()
            content = result["choices"][0]["message"]["content"]

            # When using structured outputs, the response wraps cards in an object
            if supports_structured_outputs:
                try:
                    parsed = json.loads(content)
                    if isinstance(parsed, dict) and "cards" in parsed:
                        # Re-serialize the cards array for validation
                        content = json.dumps(parsed["cards"])
                except json.JSONDecodeError:
                    pass  # Fall through to standard validation

            return _validate_flashcards_payload(content)


async def process_message(message: Dict[str, Any]) -> None:
    body = json.loads(message.get("Body", "{}"))
    artifact_id = body.get("artifact_id")
    transcript_s3_key = body.get("transcript_s3_key")
    transcript_bucket = body.get("transcript_bucket") or TRANSCRIPT_BUCKET
    parameters = body.get("parameters") or {}
    language = parameters.get("language")
    context_token = bind_log_context(
        artifact_id=artifact_id,
        media_item_id=body.get("media_item_id"),
        artifact_type="flashcards",
    )

    try:
        if not all([artifact_id, transcript_s3_key]):
            log_event(
                logger,
                logging.ERROR,
                "worker.invalid_message",
                "Missing fields for flashcards generation",
                queue=FLASHCARDS_QUEUE,
            )
            raise ValueError("Missing fields for flashcards generation")

        await mark_artifact_generating(artifact_id)
        transcript = await _download_transcript(
            transcript_s3_key,
            bucket=transcript_bucket,
        )
        flashcards = await _call_llm_for_flashcards(transcript, language=language)
        await complete_artifact_generation(
            artifact_id=artifact_id,
            content={
                "artifact_id": artifact_id,
                "media_item_id": body.get("media_item_id"),
                "artifact_type": "flashcards",
                "generated_at": datetime.now(timezone.utc).isoformat(),
                "source": {
                    "transcript_s3_key": transcript_s3_key,
                    "generator_version": body.get("generator_version"),
                },
                "content": {
                    "cards": flashcards,
                    "card_count": len(flashcards),
                },
            },
        )

        # Initialize FSRS review schedule cards for spaced repetition
        media_item_id = body.get("media_item_id")
        if media_item_id:
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
    except FlashcardsValidationError as exc:
        await fail_artifact_generation(
            artifact_id=artifact_id,
            error_message=str(exc),
            error_code="VALIDATION_ERROR",
        )
        raise
    except Exception as exc:
        await fail_artifact_generation(
            artifact_id=artifact_id,
            error_message=str(exc),
        )
        raise
    finally:
        reset_log_context(context_token)


async def poll_queue() -> None:
    from media_summarizer.workers.base_worker import process_message_with_retry

    log_event(
        logger,
        logging.INFO,
        "worker.started",
        "Starting flashcards worker queue poller",
        queue=FLASHCARDS_QUEUE,
    )
    while True:
        try:
            messages = await sqs.receive_messages(
                queue_name=FLASHCARDS_QUEUE,
                max_messages=5,
                wait_time_seconds=20,
                visibility_timeout=int(os.environ.get("SQS_VISIBILITY_TIMEOUT", "120")),
            )
            if messages:
                for message in messages:
                    await process_message_with_retry(
                        message=message,
                        processor=process_message,
                        queue_name=FLASHCARDS_QUEUE,
                        max_retries=int(os.environ.get("FLASHCARDS_MAX_RETRIES", "3")),
                        worker_name="flashcards-worker",
                    )
            await asyncio.sleep(1)
        except Exception as exc:
            log_event(
                logger,
                logging.ERROR,
                "worker.polling_error",
                "Flashcards worker polling failed",
                queue=FLASHCARDS_QUEUE,
                exc_info=exc,
            )
            await asyncio.sleep(5)


async def main() -> None:
    setup_logging("flashcards-worker")
    await poll_queue()


if __name__ == "__main__":
    asyncio.run(main())
