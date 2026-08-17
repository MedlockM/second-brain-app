"""Summary (short) artifact generator.

Model choice validated by owner (task-72 benchmark): gpt-5-nano-2025-08-07.
Concise format for digest/newsletter (title + key points + takeaway).
"""

from __future__ import annotations

import json
import os
from typing import Any, Dict, List, Optional, Sequence

from pydantic import BaseModel, ValidationError, field_validator

from media_summarizer.workers.artifact_generator.generators import corpus


class SummaryShortValidationError(Exception):
    """Raised when the model output does not match the summary_short schema."""


class SummaryShortContent(BaseModel):
    """Schema for short summary content (concise digest format).

    ``title`` is what used to be ``headline``: renamed rather than duplicated, so
    the five types expose the same field and the history listing reads one name.
    """

    title: str
    key_points: List[str]
    takeaway: str

    @field_validator("title", "takeaway")
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
        sources: Sequence[Dict[str, Any]],
        *,
        language: Optional[str] = None,
    ) -> str:
        instructions = f"""You produce a concise summary of everything above, suitable for a daily/weekly digest newsletter.

Rules:
- {corpus.language_instruction(language)}
- Output STRICT JSON only. No markdown. No commentary. No code fences.
- Keep the summary SHORT and DIGESTIBLE (suitable for quick reading).
- Cover the sources as a whole; do not summarise them one by one.
- Key points should be 3-5 bullet points, each one sentence.
- The takeaway should be one actionable insight or memorable conclusion.
{corpus.title_instruction("summary")}

Return JSON with this exact schema:
{{
  "title": "A short specific title",
  "key_points": ["Point 1", "Point 2", "Point 3"],
  "takeaway": "One actionable insight or memorable conclusion"
}}
"""
        return corpus.build_prompt(sources, instructions)

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
