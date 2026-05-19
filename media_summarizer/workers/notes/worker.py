"""
Notes generation worker for canonical artifact generation.
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

NOTES_QUEUE = os.environ.get("NOTES_QUEUE", "notes-queue")
TRANSCRIPT_BUCKET = os.environ.get(
    "TRANSCRIPT_BUCKET", "media-summarizer-transcriptions"
)
LLM_API_URL = os.environ.get(
    "LLM_API_URL", "https://api.openai.com/v1/chat/completions"
)
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")
LLM_MODEL = os.environ.get(
    "NOTES_LLM_MODEL",
    os.environ.get("OPENAI_MODEL", "gpt-4o-mini-2024-07-18"),
)


class NotesValidationError(Exception):
    """Raised when the model output does not match the canonical notes schema."""


class NotesConcept(BaseModel):
    term: str
    explanation: str
    importance: str

    @field_validator("term", "explanation", "importance")
    @classmethod
    def _non_empty_text(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("value must be non-empty")
        return normalized

    @field_validator("importance")
    @classmethod
    def _valid_importance(cls, value: str) -> str:
        normalized = value.lower()
        if normalized not in {"core", "supporting"}:
            raise ValueError("importance must be 'core' or 'supporting'")
        return normalized


class NotesGlossaryItem(BaseModel):
    term: str
    definition: str

    @field_validator("term", "definition")
    @classmethod
    def _non_empty_text(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("value must be non-empty")
        return normalized


class NotesContent(BaseModel):
    objectives: List[str]
    concepts: List[NotesConcept]
    key_points: List[str]
    action_items: List[str]
    glossary: List[NotesGlossaryItem]

    @field_validator("objectives", "key_points", "action_items")
    @classmethod
    def _non_empty_text_list(cls, items: List[str]) -> List[str]:
        normalized = []
        for item in items:
            if not isinstance(item, str):
                raise ValueError("list entries must be strings")
            cleaned = item.strip()
            if not cleaned:
                raise ValueError("list entries must be non-empty")
            normalized.append(cleaned)
        return normalized


def _build_notes_prompt(transcript: str, language: str | None = None) -> str:
    language_instruction = (
        f"Use {language} for the output."
        if language
        else "Use the same language as the transcript."
    )
    return f"""
You produce a structured study/review notes artifact from a transcript.

Rules:
- {language_instruction}
- Output STRICT JSON only. No markdown. No commentary. No code fences.
- Keep the structure stable for client rendering.
- Focus on learning/review value, not a generic summary.
- Avoid sponsor/ad content unless it is central to the source material.
- Every string must be concise and useful.
- `importance` must be either `core` or `supporting`.

Return JSON with this exact schema:
{{
  "objectives": ["..."],
  "concepts": [
    {{
      "term": "...",
      "explanation": "...",
      "importance": "core"
    }}
  ],
  "key_points": ["..."],
  "action_items": ["..."],
  "glossary": [
    {{
      "term": "...",
      "definition": "..."
    }}
  ]
}}

Transcript:
{transcript}
"""


def _strip_code_fences(content: str) -> str:
    cleaned = content.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
        cleaned = re.sub(r"\s*```$", "", cleaned)
    return cleaned.strip()


def _validate_notes_payload(content: str) -> Dict[str, Any]:
    try:
        parsed = json.loads(_strip_code_fences(content))
    except json.JSONDecodeError as exc:
        raise NotesValidationError(f"notes output is not valid JSON: {exc}") from exc

    if not isinstance(parsed, dict):
        raise NotesValidationError("notes output must be a JSON object")

    try:
        validated = NotesContent.model_validate(parsed)
    except ValidationError as exc:
        raise NotesValidationError(f"notes output schema validation failed: {exc}") from exc

    return validated.model_dump()


async def _download_transcript(key: str, bucket: str = TRANSCRIPT_BUCKET) -> str:
    content = await s3.download_file_to_memory(bucket=bucket, key=key)
    return content.decode("utf-8")


async def _call_llm_for_notes(
    transcript: str,
    language: str | None = None,
) -> Dict[str, Any]:
    if not OPENAI_API_KEY:
        raise ValueError("OPENAI_API_KEY environment variable is required")

    timeout = aiohttp.ClientTimeout(
        total=int(os.environ.get("LLM_TIMEOUT_SECONDS", "180"))
    )
    payload: Dict[str, Any] = {
        "model": LLM_MODEL,
        "messages": [
            {"role": "user", "content": _build_notes_prompt(transcript, language)}
        ],
    }

    model_lower = (LLM_MODEL or "").lower()
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
                    "Notes LLM API returned an error",
                    provider="openai",
                    artifact_type="notes",
                    status=response.status,
                    detail=body[:500],
                )
            response.raise_for_status()
            result = await response.json()
            content = result["choices"][0]["message"]["content"]
            return _validate_notes_payload(content)


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
        artifact_type="notes",
    )

    try:
        if not all([artifact_id, transcript_s3_key]):
            log_event(
                logger,
                logging.ERROR,
                "worker.invalid_message",
                "Missing fields for notes generation",
                queue=NOTES_QUEUE,
            )
            raise ValueError("Missing fields for notes generation")

        await mark_artifact_generating(artifact_id)
        transcript = await _download_transcript(
            transcript_s3_key,
            bucket=transcript_bucket,
        )
        notes = await _call_llm_for_notes(transcript, language=language)
        await complete_artifact_generation(
            artifact_id=artifact_id,
            content={
                "artifact_id": artifact_id,
                "media_item_id": body.get("media_item_id"),
                "artifact_type": "notes",
                "generated_at": datetime.now(timezone.utc).isoformat(),
                "source": {
                    "transcript_s3_key": transcript_s3_key,
                    "generator_version": body.get("generator_version"),
                },
                "content": notes,
            },
        )
    except NotesValidationError as exc:
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
        "Starting notes worker queue poller",
        queue=NOTES_QUEUE,
    )
    while True:
        try:
            messages = await sqs.receive_messages(
                queue_name=NOTES_QUEUE,
                max_messages=5,
                wait_time_seconds=20,
                visibility_timeout=int(os.environ.get("SQS_VISIBILITY_TIMEOUT", "120")),
            )
            if messages:
                for message in messages:
                    await process_message_with_retry(
                        message=message,
                        processor=process_message,
                        queue_name=NOTES_QUEUE,
                        max_retries=int(os.environ.get("NOTES_MAX_RETRIES", "3")),
                        worker_name="notes-worker",
                    )
            await asyncio.sleep(1)
        except Exception as exc:
            log_event(
                logger,
                logging.ERROR,
                "worker.polling_error",
                "Notes worker polling failed",
                queue=NOTES_QUEUE,
                exc_info=exc,
            )
            await asyncio.sleep(5)


async def main() -> None:
    setup_logging("notes-worker")
    await poll_queue()


if __name__ == "__main__":
    asyncio.run(main())
