"""Summary (short) artifact generator.

Model choice validated by owner (task-72 benchmark): gpt-5-nano-2025-08-07.
Concise format for digest/newsletter (headline + key points + takeaway).
"""

from __future__ import annotations

import json
import os
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ValidationError, field_validator


class SummaryShortValidationError(Exception):
    """Raised when the model output does not match the summary_short schema."""


class SummaryShortContent(BaseModel):
    """Schema for short summary content (concise digest format)."""
    headline: str
    key_points: List[str]
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
    def _non_empty_list(cls, value: List[str]) -> List[str]:
        if not value:
            raise ValueError("key_points must not be empty")
        return [p.strip() for p in value if p.strip()]


class SummaryShortGenerator:
    """Generator for concise summary suitable for a daily/weekly digest."""

    @property
    def artifact_type_value(self) -> str:
        return "summary_short"

    @property
    def default_model(self) -> str:
        return os.environ.get("SUMMARY_SHORT_LLM_MODEL", "gpt-5-nano-2025-08-07")

    def build_prompt(
        self,
        transcript: str,
        *,
        language: Optional[str] = None,
        podcast_title: Optional[str] = None,
        episode_title: Optional[str] = None,
    ) -> str:
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

    def response_format_schema(self) -> Optional[Dict[str, Any]]:
        return None

    def unwrap_structured_response(self, content: str) -> str:
        return content

    def validate(self, content: str) -> Dict[str, Any]:
        from media_summarizer.workers.artifact_generator.worker import _strip_code_fences

        try:
            parsed = json.loads(_strip_code_fences(content))
        except json.JSONDecodeError as exc:
            raise SummaryShortValidationError(
                f"summary_short output is not valid JSON: {exc}"
            ) from exc

        if not isinstance(parsed, dict):
            raise SummaryShortValidationError("summary_short output must be a JSON object")

        try:
            validated = SummaryShortContent.model_validate(parsed)
        except ValidationError as exc:
            raise SummaryShortValidationError(
                f"summary_short schema validation failed: {exc}"
            ) from exc

        return validated.model_dump()

    def build_artifact_content(
        self,
        validated: Any,
        *,
        body: Dict[str, Any],
    ) -> Dict[str, Any]:
        return validated
