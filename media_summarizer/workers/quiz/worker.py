"""
Quiz generation worker for canonical artifact generation.

Generates multiple-choice quiz questions from a transcript using an LLM.
Each question has exactly 4 options with one correct answer. Output follows
a structured JSON schema for client rendering.

Model choice validated by owner (task-72 benchmark): gpt-5.4-nano-2026-03-17
for quiz. Uses OpenAI Structured Outputs (response_format) for reliable
JSON generation.
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
from media_summarizer.utils import s3, sqs
from media_summarizer.utils.logging_config import (
    bind_log_context,
    log_event,
    reset_log_context,
    setup_logging,
)

logger = logging.getLogger(__name__)

QUIZ_QUEUE = os.environ.get("QUIZ_QUEUE", "quiz-queue")
TRANSCRIPT_BUCKET = os.environ.get(
    "TRANSCRIPT_BUCKET", "media-summarizer-transcriptions"
)
LLM_API_URL = os.environ.get(
    "LLM_API_URL", "https://api.openai.com/v1/chat/completions"
)
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")
LLM_MODEL = os.environ.get(
    "QUIZ_LLM_MODEL",
    os.environ.get("OPENAI_MODEL", "gpt-5.4-nano-2026-03-17"),
)

MIN_QUESTIONS = 5
MAX_QUESTIONS = 10
OPTIONS_PER_QUESTION = 4


class QuizValidationError(Exception):
    """Raised when the model output does not match the canonical quiz schema."""


class QuizOption(BaseModel):
    label: str
    text: str

    @field_validator("label")
    @classmethod
    def _valid_label(cls, value: str) -> str:
        normalized = value.strip().upper()
        if normalized not in {"A", "B", "C", "D"}:
            raise ValueError("label must be one of A, B, C, D")
        return normalized

    @field_validator("text")
    @classmethod
    def _non_empty_text(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("text must be non-empty")
        return normalized


class QuizQuestion(BaseModel):
    question: str
    options: List[QuizOption]
    correct_answer: str
    explanation: str

    @field_validator("question", "explanation")
    @classmethod
    def _non_empty_text(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("value must be non-empty")
        return normalized

    @field_validator("correct_answer")
    @classmethod
    def _valid_answer(cls, value: str) -> str:
        normalized = value.strip().upper()
        if normalized not in {"A", "B", "C", "D"}:
            raise ValueError("correct_answer must be one of A, B, C, D")
        return normalized


def _build_quiz_prompt(transcript: str, language: str | None = None) -> str:
    language_instruction = (
        f"Use {language} for the output."
        if language
        else "Use the same language as the transcript."
    )
    return f"""You produce a multiple-choice quiz from a transcript for knowledge testing.

Rules:
- {language_instruction}
- Output STRICT JSON only. No markdown. No commentary. No code fences.
- Return a JSON array of question objects.
- Generate between {MIN_QUESTIONS} and {MAX_QUESTIONS} questions depending on content density.
- Each question must have exactly {OPTIONS_PER_QUESTION} options labeled A, B, C, D.
- Exactly one option is correct per question.
- Questions should test comprehension of key concepts, not trivial details.
- Do NOT generate questions about ads/sponsors unless central to the content.
- Include a brief explanation for why the correct answer is right.
- Make incorrect options plausible but clearly wrong to someone who understood the content.

Return JSON with this exact schema:
[
  {{
    "question": "...",
    "options": [
      {{"label": "A", "text": "..."}},
      {{"label": "B", "text": "..."}},
      {{"label": "C", "text": "..."}},
      {{"label": "D", "text": "..."}}
    ],
    "correct_answer": "A",
    "explanation": "..."
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


def _validate_quiz_payload(content: str) -> List[Dict[str, Any]]:
    try:
        parsed = json.loads(_strip_code_fences(content))
    except json.JSONDecodeError as exc:
        raise QuizValidationError(
            f"quiz output is not valid JSON: {exc}"
        ) from exc

    if not isinstance(parsed, list):
        raise QuizValidationError("quiz output must be a JSON array")

    if len(parsed) < MIN_QUESTIONS:
        raise QuizValidationError(
            f"quiz output must contain at least {MIN_QUESTIONS} questions, got {len(parsed)}"
        )

    if len(parsed) > MAX_QUESTIONS:
        # Silently truncate to MAX_QUESTIONS rather than failing
        parsed = parsed[:MAX_QUESTIONS]

    validated: List[Dict[str, Any]] = []
    for idx, item in enumerate(parsed):
        if not isinstance(item, dict):
            raise QuizValidationError(
                f"quiz item at index {idx} must be a JSON object"
            )
        try:
            question = QuizQuestion.model_validate(item)
        except ValidationError as exc:
            raise QuizValidationError(
                f"quiz item at index {idx} schema validation failed: {exc}"
            ) from exc

        if len(question.options) != OPTIONS_PER_QUESTION:
            raise QuizValidationError(
                f"quiz item at index {idx} must have exactly {OPTIONS_PER_QUESTION} options, "
                f"got {len(question.options)}"
            )

        validated.append(question.model_dump())

    return validated


async def _download_transcript(key: str, bucket: str = TRANSCRIPT_BUCKET) -> str:
    content = await s3.download_file_to_memory(bucket=bucket, key=key)
    return content.decode("utf-8")


def _build_response_format_schema() -> Dict[str, Any]:
    """Build the JSON Schema for OpenAI Structured Outputs (response_format).

    This ensures the model returns valid JSON matching our quiz structure,
    eliminating parse failures for models that support native structured outputs.
    """
    return {
        "type": "json_schema",
        "json_schema": {
            "name": "quiz",
            "strict": True,
            "schema": {
                "type": "object",
                "properties": {
                    "questions": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "question": {"type": "string"},
                                "options": {
                                    "type": "array",
                                    "items": {
                                        "type": "object",
                                        "properties": {
                                            "label": {"type": "string"},
                                            "text": {"type": "string"},
                                        },
                                        "required": ["label", "text"],
                                        "additionalProperties": False,
                                    },
                                },
                                "correct_answer": {"type": "string"},
                                "explanation": {"type": "string"},
                            },
                            "required": ["question", "options", "correct_answer", "explanation"],
                            "additionalProperties": False,
                        },
                    }
                },
                "required": ["questions"],
                "additionalProperties": False,
            },
        },
    }


async def _call_llm_for_quiz(
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
            {"role": "user", "content": _build_quiz_prompt(transcript, language)}
        ],
    }

    # Use OpenAI Structured Outputs for models that support it (gpt-4o, gpt-5 family)
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
                    "Quiz LLM API returned an error",
                    provider="openai",
                    artifact_type="quiz",
                    status=response.status,
                    detail=body[:500],
                )
            response.raise_for_status()
            result = await response.json()
            content = result["choices"][0]["message"]["content"]

            # When using structured outputs, the response wraps questions in an object
            if supports_structured_outputs:
                try:
                    parsed = json.loads(content)
                    if isinstance(parsed, dict) and "questions" in parsed:
                        # Re-serialize the questions array for validation
                        content = json.dumps(parsed["questions"])
                except json.JSONDecodeError:
                    pass  # Fall through to standard validation

            return _validate_quiz_payload(content)


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
        artifact_type="quiz",
    )

    try:
        if not all([artifact_id, transcript_s3_key]):
            log_event(
                logger,
                logging.ERROR,
                "worker.invalid_message",
                "Missing fields for quiz generation",
                queue=QUIZ_QUEUE,
            )
            raise ValueError("Missing fields for quiz generation")

        await mark_artifact_generating(artifact_id)
        transcript = await _download_transcript(
            transcript_s3_key,
            bucket=transcript_bucket,
        )
        questions = await _call_llm_for_quiz(transcript, language=language)
        await complete_artifact_generation(
            artifact_id=artifact_id,
            content={
                "artifact_id": artifact_id,
                "media_item_id": body.get("media_item_id"),
                "artifact_type": "quiz",
                "generated_at": datetime.now(timezone.utc).isoformat(),
                "source": {
                    "transcript_s3_key": transcript_s3_key,
                    "generator_version": body.get("generator_version"),
                },
                "content": {
                    "questions": questions,
                    "question_count": len(questions),
                },
            },
        )
    except QuizValidationError as exc:
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
        "Starting quiz worker queue poller",
        queue=QUIZ_QUEUE,
    )
    while True:
        try:
            messages = await sqs.receive_messages(
                queue_name=QUIZ_QUEUE,
                max_messages=5,
                wait_time_seconds=20,
                visibility_timeout=int(os.environ.get("SQS_VISIBILITY_TIMEOUT", "120")),
            )
            if messages:
                for message in messages:
                    await process_message_with_retry(
                        message=message,
                        processor=process_message,
                        queue_name=QUIZ_QUEUE,
                        max_retries=int(os.environ.get("QUIZ_MAX_RETRIES", "3")),
                        worker_name="quiz-worker",
                    )
            await asyncio.sleep(1)
        except Exception as exc:
            log_event(
                logger,
                logging.ERROR,
                "worker.polling_error",
                "Quiz worker polling failed",
                queue=QUIZ_QUEUE,
                exc_info=exc,
            )
            await asyncio.sleep(5)


async def main() -> None:
    setup_logging("quiz-worker")
    await poll_queue()


if __name__ == "__main__":
    asyncio.run(main())
