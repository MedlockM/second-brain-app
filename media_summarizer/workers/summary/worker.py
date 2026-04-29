"""
Summary artifact workers for short and detailed summaries.

Generates two distinct summary artifact types:
- summary_short: Concise format for digest/newsletter (2-3 paragraphs)
- summary_detailed: Exhaustive format for learning (structured sections)

Model choice validated by owner (task-72 benchmark):
- summary_short: gpt-5-nano-2025-08-07
- summary_detailed: gpt-5.4-nano-2026-03-17
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import re
from datetime import datetime, timezone
from typing import Any, Dict, Optional

import aiohttp
from pydantic import BaseModel, ValidationError, field_validator

from media_summarizer.core.models.media_artifact import MediaArtifactType
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

SUMMARY_SHORT_QUEUE = os.environ.get("SUMMARY_SHORT_QUEUE", "summary-short-queue")
SUMMARY_DETAILED_QUEUE = os.environ.get("SUMMARY_DETAILED_QUEUE", "summary-detailed-queue")
TRANSCRIPT_BUCKET = os.environ.get(
    "TRANSCRIPT_BUCKET", "media-summarizer-transcriptions"
)
LLM_API_URL = os.environ.get(
    "LLM_API_URL", "https://api.openai.com/v1/chat/completions"
)
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")
DEFAULT_MODEL = os.environ.get("OPENAI_MODEL", "gpt-5.4-nano-2026-03-17")
SUMMARY_SHORT_MODEL = os.environ.get("SUMMARY_SHORT_LLM_MODEL", "gpt-5-nano-2025-08-07")
SUMMARY_DETAILED_MODEL = os.environ.get("SUMMARY_DETAILED_LLM_MODEL", DEFAULT_MODEL)


class SummaryValidationError(Exception):
    """Raised when the model output does not match the expected summary schema."""


class SummaryShortContent(BaseModel):
    """Schema for short summary content (concise digest format)."""
    headline: str
    key_points: list[str]
    takeaway: str

    @field_validator("headline", "takeaway")
    @classmethod
    def _non_empty_text(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("value must be non-empty")
        return normalized

    @field_validator("key_points")
    @classmethod
    def _non_empty_list(cls, value: list[str]) -> list[str]:
        if not value:
            raise ValueError("key_points must not be empty")
        return [p.strip() for p in value if p.strip()]


class SummaryDetailedContent(BaseModel):
    """Schema for detailed summary content (structured learning format)."""
    context: str
    main_topics: list[str]
    key_points: list[str]
    notable_quotes: list[str]
    conclusion: str

    @field_validator("context", "conclusion")
    @classmethod
    def _non_empty_text(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("value must be non-empty")
        return normalized

    @field_validator("main_topics", "key_points")
    @classmethod
    def _non_empty_list(cls, value: list[str]) -> list[str]:
        if not value:
            raise ValueError("list must not be empty")
        return [p.strip() for p in value if p.strip()]

    @field_validator("notable_quotes")
    @classmethod
    def _clean_quotes(cls, value: list[str]) -> list[str]:
        # Quotes may be empty if no notable quotes found
        return [q.strip() for q in value if q.strip()]


def _build_summary_short_prompt(
    transcript: str,
    podcast_title: Optional[str] = None,
    episode_title: Optional[str] = None,
    language: Optional[str] = None,
) -> str:
    """Build the prompt for short summary generation."""
    language_instruction = (
        f"Use {language} for the output."
        if language
        else "Use the same language as the transcript."
    )
    context = ""
    if podcast_title or episode_title:
        context = f"\nPodcast: {podcast_title or 'Unknown'}\nEpisode: {episode_title or 'Unknown'}\n"

    return f"""You produce a concise summary suitable for a daily/weekly digest newsletter.

Rules:
- {language_instruction}
- Output STRICT JSON only. No markdown. No commentary. No code fences.
- Keep the summary SHORT and DIGESTIBLE (suitable for quick reading).
- The headline should capture the essence in one sentence (max 15 words).
- Key points should be 3-5 bullet points, each one sentence.
- The takeaway should be one actionable insight or memorable conclusion.

Return JSON with this exact schema:
{{
  "headline": "A catchy one-sentence summary",
  "key_points": ["Point 1", "Point 2", "Point 3"],
  "takeaway": "One actionable insight or memorable conclusion"
}}
{context}
Transcript:
{transcript}
"""


def _build_summary_detailed_prompt(
    transcript: str,
    podcast_title: Optional[str] = None,
    episode_title: Optional[str] = None,
    language: Optional[str] = None,
) -> str:
    """Build the prompt for detailed summary generation."""
    language_instruction = (
        f"Use {language} for the output."
        if language
        else "Use the same language as the transcript."
    )
    context = ""
    if podcast_title or episode_title:
        context = f"\nPodcast: {podcast_title or 'Unknown'}\nEpisode: {episode_title or 'Unknown'}\n"

    return f"""You produce a comprehensive, structured summary suitable for deep learning and reference.

Rules:
- {language_instruction}
- Output STRICT JSON only. No markdown. No commentary. No code fences.
- Be EXHAUSTIVE and THOROUGH - this summary is for learning, not quick reading.
- Context should set the stage (who, what, why) in 2-3 sentences.
- Main topics should list 3-7 major themes discussed.
- Key points should be 7-15 detailed bullet points covering important information.
- Notable quotes should include 2-5 memorable or important quotes (if any).
- Conclusion should synthesize the main message in 2-3 sentences.

Return JSON with this exact schema:
{{
  "context": "2-3 sentences setting the stage",
  "main_topics": ["Topic 1", "Topic 2", "Topic 3"],
  "key_points": ["Detailed point 1", "Detailed point 2", ...],
  "notable_quotes": ["Quote 1", "Quote 2"],
  "conclusion": "2-3 sentences synthesizing the main message"
}}
{context}
Transcript:
{transcript}
"""


def _strip_code_fences(content: str) -> str:
    """Remove markdown code fences from LLM output."""
    cleaned = content.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
        cleaned = re.sub(r"\s*```$", "", cleaned)
    return cleaned.strip()


def _validate_summary_short_payload(content: str) -> Dict[str, Any]:
    """Validate and parse short summary JSON output."""
    try:
        parsed = json.loads(_strip_code_fences(content))
    except json.JSONDecodeError as exc:
        raise SummaryValidationError(
            f"summary_short output is not valid JSON: {exc}"
        ) from exc

    if not isinstance(parsed, dict):
        raise SummaryValidationError("summary_short output must be a JSON object")

    try:
        validated = SummaryShortContent.model_validate(parsed)
    except ValidationError as exc:
        raise SummaryValidationError(
            f"summary_short schema validation failed: {exc}"
        ) from exc

    return validated.model_dump()


def _validate_summary_detailed_payload(content: str) -> Dict[str, Any]:
    """Validate and parse detailed summary JSON output."""
    try:
        parsed = json.loads(_strip_code_fences(content))
    except json.JSONDecodeError as exc:
        raise SummaryValidationError(
            f"summary_detailed output is not valid JSON: {exc}"
        ) from exc

    if not isinstance(parsed, dict):
        raise SummaryValidationError("summary_detailed output must be a JSON object")

    try:
        validated = SummaryDetailedContent.model_validate(parsed)
    except ValidationError as exc:
        raise SummaryValidationError(
            f"summary_detailed schema validation failed: {exc}"
        ) from exc

    return validated.model_dump()


async def _download_transcript(key: str, bucket: str = TRANSCRIPT_BUCKET) -> str:
    """Download transcript from S3."""
    content = await s3.download_file_to_memory(bucket=bucket, key=key)
    return content.decode("utf-8")


async def _call_llm_for_summary(
    transcript: str,
    artifact_type: MediaArtifactType,
    podcast_title: Optional[str] = None,
    episode_title: Optional[str] = None,
    language: Optional[str] = None,
) -> Dict[str, Any]:
    """Call LLM API to generate summary."""
    if not OPENAI_API_KEY:
        raise ValueError("OPENAI_API_KEY environment variable is required")

    # Select model and prompt based on artifact type
    if artifact_type == MediaArtifactType.SUMMARY_SHORT:
        model = SUMMARY_SHORT_MODEL
        prompt = _build_summary_short_prompt(
            transcript, podcast_title, episode_title, language
        )
        validator = _validate_summary_short_payload
    elif artifact_type == MediaArtifactType.SUMMARY_DETAILED:
        model = SUMMARY_DETAILED_MODEL
        prompt = _build_summary_detailed_prompt(
            transcript, podcast_title, episode_title, language
        )
        validator = _validate_summary_detailed_payload
    else:
        raise ValueError(f"Unsupported artifact type for summary worker: {artifact_type}")

    timeout = aiohttp.ClientTimeout(
        total=int(os.environ.get("LLM_TIMEOUT_SECONDS", "180"))
    )
    payload: Dict[str, Any] = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
    }

    # Only add temperature for models that support it
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
                    "Summary LLM API returned an error",
                    provider="openai",
                    artifact_type=artifact_type.value,
                    status=response.status,
                    detail=body[:500],
                )
            response.raise_for_status()
            result = await response.json()
            content = result["choices"][0]["message"]["content"]
            return validator(content)


async def process_message(message: Dict[str, Any]) -> None:
    """Process a single summary generation message from either queue."""
    body = json.loads(message.get("Body", "{}"))
    artifact_id = body.get("artifact_id")
    artifact_type_str = body.get("artifact_type", "summary_short")
    transcript_s3_key = body.get("transcript_s3_key")
    transcript_bucket = body.get("transcript_bucket") or TRANSCRIPT_BUCKET
    parameters = body.get("parameters") or {}
    language = parameters.get("language")
    podcast_title = body.get("podcast_title")
    episode_title = body.get("episode_title")

    # Resolve artifact type
    try:
        artifact_type = MediaArtifactType(artifact_type_str)
    except ValueError:
        artifact_type = MediaArtifactType.SUMMARY_SHORT

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
                "Missing fields for summary generation",
                artifact_type=artifact_type.value,
            )
            raise ValueError("Missing fields for summary generation")

        await mark_artifact_generating(artifact_id)
        transcript = await _download_transcript(
            transcript_s3_key,
            bucket=transcript_bucket,
        )
        summary_content = await _call_llm_for_summary(
            transcript,
            artifact_type=artifact_type,
            podcast_title=podcast_title,
            episode_title=episode_title,
            language=language,
        )
        await complete_artifact_generation(
            artifact_id=artifact_id,
            content={
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
                "content": summary_content,
            },
        )
    except SummaryValidationError as exc:
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


async def poll_queue(queue_name: str) -> None:
    """Poll an SQS queue for summary generation messages."""
    from media_summarizer.workers.base_worker import process_message_with_retry

    log_event(
        logger,
        logging.INFO,
        "worker.started",
        "Starting summary worker queue poller",
        queue=queue_name,
    )
    while True:
        try:
            messages = await sqs.receive_messages(
                queue_name=queue_name,
                max_messages=5,
                wait_time_seconds=20,
                visibility_timeout=int(os.environ.get("SQS_VISIBILITY_TIMEOUT", "120")),
            )
            if messages:
                for message in messages:
                    await process_message_with_retry(
                        message=message,
                        processor=process_message,
                        queue_name=queue_name,
                        max_retries=int(os.environ.get("SUMMARY_MAX_RETRIES", "3")),
                        worker_name="summary-worker",
                    )
            await asyncio.sleep(1)
        except Exception as exc:
            log_event(
                logger,
                logging.ERROR,
                "worker.polling_error",
                "Summary worker polling failed",
                queue=queue_name,
                exc_info=exc,
            )
            await asyncio.sleep(5)


async def main_short() -> None:
    """Main entry point for the summary_short worker."""
    setup_logging("summary-short-worker")
    await poll_queue(SUMMARY_SHORT_QUEUE)


async def main_detailed() -> None:
    """Main entry point for the summary_detailed worker."""
    setup_logging("summary-detailed-worker")
    await poll_queue(SUMMARY_DETAILED_QUEUE)


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == "detailed":
        asyncio.run(main_detailed())
    else:
        asyncio.run(main_short())
