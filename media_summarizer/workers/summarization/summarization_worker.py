"""
Summarization worker for generating summaries from transcripts using LLM.

Migrated to the canonical artifact_id contract (task-123).
Uses mark_artifact_generating / complete_artifact_generation / fail_artifact_generation
consistent with notes, flashcards, and quiz workers.
"""

import asyncio
import json
import logging
import os
import re
from datetime import datetime, timezone
from typing import Any, Dict

import aiohttp

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
from media_summarizer.workers.base_worker import process_message_with_retry


class LLMAPIError(Exception):
    """Exception raised when LLM API returns an error or refuses to process content."""


logger = logging.getLogger(__name__)

# Configuration
SUMMARIZATION_QUEUE = os.environ.get("SUMMARIZATION_QUEUE", "summarization-queue")
TRANSCRIPT_BUCKET = os.environ.get(
    "TRANSCRIPT_BUCKET", "media-summarizer-transcriptions"
)
LLM_API_URL = os.environ.get(
    "LLM_API_URL", "https://api.openai.com/v1/chat/completions"
)
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")
LLM_MODEL = os.environ.get(
    "SUMMARY_LLM_MODEL",
    os.environ.get("OPENAI_MODEL", "gpt-5.4-nano-2026-03-17"),
)
LLM_TIMEOUT_SECONDS = int(os.environ.get("LLM_TIMEOUT_SECONDS", "180"))


def _build_summary_prompt(
    transcript: str,
    language: str | None = None,
    podcast_title: str | None = None,
    episode_title: str | None = None,
) -> str:
    language_instruction = (
        f"Use {language} for the output."
        if language
        else "Use the same language as the transcript."
    )
    context_line = ""
    if podcast_title or episode_title:
        parts = []
        if podcast_title:
            parts.append(f"Podcast: {podcast_title}")
        if episode_title:
            parts.append(f"Episode: {episode_title}")
        context_line = "\n".join(parts) + "\n\n"

    return f"""You produce a structured summary of a transcript.

Rules:
- {language_instruction}
- Output STRICT JSON only. No markdown. No commentary. No code fences.
- Keep the structure stable for client rendering.
- Focus on useful, actionable information.
- Avoid sponsor/ad content unless it is central to the source material.
- Every string must be concise and useful.

{context_line}Return JSON with this exact schema:
{{
  "main_topics": ["..."],
  "key_points": ["..."],
  "notable_quotes": ["..."],
  "conclusion": "..."
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


def _validate_summary_payload(content: str) -> Dict[str, Any]:
    """Validate and parse summary JSON output from LLM."""
    try:
        parsed = json.loads(_strip_code_fences(content))
    except json.JSONDecodeError as exc:
        raise LLMAPIError(f"Summary output is not valid JSON: {exc}") from exc

    if not isinstance(parsed, dict):
        raise LLMAPIError("Summary output must be a JSON object")

    # Validate expected keys exist
    expected_keys = {"main_topics", "key_points", "notable_quotes", "conclusion"}
    missing = expected_keys - set(parsed.keys())
    if missing:
        raise LLMAPIError(f"Summary output missing keys: {missing}")

    # Validate types
    for list_key in ("main_topics", "key_points", "notable_quotes"):
        if not isinstance(parsed.get(list_key), list):
            raise LLMAPIError(f"Summary field '{list_key}' must be an array")
    if not isinstance(parsed.get("conclusion"), str):
        raise LLMAPIError("Summary field 'conclusion' must be a string")

    return parsed


async def _download_transcript(key: str, bucket: str = TRANSCRIPT_BUCKET) -> str:
    content = await s3.download_file_to_memory(bucket=bucket, key=key)
    return content.decode("utf-8")


async def _call_llm_for_summary(
    transcript: str,
    language: str | None = None,
    podcast_title: str | None = None,
    episode_title: str | None = None,
) -> Dict[str, Any]:
    if not OPENAI_API_KEY:
        raise ValueError("OPENAI_API_KEY environment variable is required")

    timeout = aiohttp.ClientTimeout(total=LLM_TIMEOUT_SECONDS)
    payload: Dict[str, Any] = {
        "model": LLM_MODEL,
        "messages": [
            {
                "role": "user",
                "content": _build_summary_prompt(
                    transcript, language, podcast_title, episode_title
                ),
            }
        ],
    }

    # Only add temperature for models that support it (not o1/o3/gpt-5 family)
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
                    "Summary LLM API returned an error",
                    provider="openai",
                    artifact_type="summary",
                    status=response.status,
                    detail=body[:500],
                )
            response.raise_for_status()
            result = await response.json()
            content = result["choices"][0]["message"]["content"]
            return _validate_summary_payload(content)


async def process_message(message: Dict[str, Any]) -> None:
    """
    Process an SQS message for summarization using the canonical artifact_id contract.

    Expected message body fields (sent by artifact_service.request_artifact_generation):
      - artifact_id (str, required)
      - media_item_id (str)
      - transcript_s3_key (str, required)
      - transcript_bucket (str, optional -- defaults to TRANSCRIPT_BUCKET)
      - parameters (dict, optional -- may contain "language")
      - generation_fingerprint (str)
      - generator_version (str)
      - podcast_title (str, optional)
      - episode_title (str, optional)
    """
    body = json.loads(message.get("Body", "{}"))
    artifact_id = body.get("artifact_id")
    transcript_s3_key = body.get("transcript_s3_key")
    transcript_bucket = body.get("transcript_bucket") or TRANSCRIPT_BUCKET
    parameters = body.get("parameters") or {}
    language = parameters.get("language")
    podcast_title = body.get("podcast_title")
    episode_title = body.get("episode_title")

    context_token = bind_log_context(
        artifact_id=artifact_id,
        media_item_id=body.get("media_item_id"),
        artifact_type="summary",
    )

    try:
        if not all([artifact_id, transcript_s3_key]):
            log_event(
                logger,
                logging.ERROR,
                "worker.invalid_message",
                "Missing required fields for summary generation",
                queue=SUMMARIZATION_QUEUE,
            )
            raise ValueError("Missing required fields for summary generation")

        await mark_artifact_generating(artifact_id)

        transcript = await _download_transcript(
            transcript_s3_key,
            bucket=transcript_bucket,
        )

        if not transcript or not transcript.strip():
            raise ValueError("Empty or invalid transcription content")

        summary = await _call_llm_for_summary(
            transcript,
            language=language,
            podcast_title=podcast_title,
            episode_title=episode_title,
        )

        await complete_artifact_generation(
            artifact_id=artifact_id,
            content={
                "artifact_id": artifact_id,
                "media_item_id": body.get("media_item_id"),
                "artifact_type": "summary",
                "generated_at": datetime.now(timezone.utc).isoformat(),
                "source": {
                    "transcript_s3_key": transcript_s3_key,
                    "generator_version": body.get("generator_version"),
                },
                "content": summary,
            },
        )

    except LLMAPIError as exc:
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
    log_event(
        logger,
        logging.INFO,
        "worker.started",
        "Starting summarization worker queue poller",
        queue=SUMMARIZATION_QUEUE,
    )
    while True:
        try:
            messages = await sqs.receive_messages(
                queue_name=SUMMARIZATION_QUEUE,
                max_messages=5,
                wait_time_seconds=20,
                visibility_timeout=int(os.environ.get("SQS_VISIBILITY_TIMEOUT", "300")),
            )
            if messages:
                for message in messages:
                    await process_message_with_retry(
                        message=message,
                        processor=process_message,
                        queue_name=SUMMARIZATION_QUEUE,
                        max_retries=int(
                            os.environ.get("SUMMARIZATION_MAX_RETRIES", "3")
                        ),
                        worker_name="summarization-worker",
                    )
            await asyncio.sleep(1)
        except Exception as exc:
            log_event(
                logger,
                logging.ERROR,
                "worker.polling_error",
                "Summarization worker polling failed",
                queue=SUMMARIZATION_QUEUE,
                exc_info=exc,
            )
            await asyncio.sleep(5)


async def main() -> None:
    setup_logging("summarization-worker")
    await poll_queue()


if __name__ == "__main__":
    asyncio.run(main())
