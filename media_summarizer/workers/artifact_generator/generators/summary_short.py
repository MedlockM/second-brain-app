"""Summary (short) artifact generator.

Model choice validated by owner (task-72 benchmark): gpt-5-nano-2025-08-07.
Concise format for digest/newsletter (title + key points + optional takeaway).
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
    # Optional: a source that carries no actionable conclusion has no takeaway,
    # and demanding one is exactly what made the model fabricate advice on a
    # TikTok clip that gave none (task-316 §2.3). Missing or null normalises to
    # "", which the mobile screen already hides.
    takeaway: str = ""

    @field_validator("title")
    @classmethod
    def _non_empty_text(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("value must be non-empty")
        return normalized

    @field_validator("takeaway", mode="before")
    @classmethod
    def _optional_takeaway(cls, value: Any) -> str:
        if value is None:
            return ""
        return str(value).strip()

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
        optional_takeaway = corpus.empty_section_instruction(
            '"takeaway" is optional: give one actionable insight or memorable '
            "conclusion when the sources genuinely carry one, and return an empty "
            "string when they do not."
        )
        instructions = f"""You produce a concise summary of everything above, suitable for a daily/weekly digest newsletter.

Rules:
- {corpus.language_instruction(language)}
- Output STRICT JSON only. No markdown. No commentary. No code fences.
- Keep each key point to one sentence, and keep the whole summary quick to read.
{corpus.corpus_shape_instruction()}
{corpus.coverage_instruction("key point", "key points", fields='"key_points"')}
- Never write more than the sources say. If one sentence covers everything they
  carry, write one key point.
{optional_takeaway}
{corpus.transcript_markers_instruction()}
{corpus.dated_facts_instruction()}
{corpus.subject_matter_instruction()}
{corpus.title_instruction("summary")}

Return JSON with this exact schema:
{{
  "title": "A short specific title",
  "key_points": ["Point 1", "Point 2"],
  "takeaway": "One actionable insight, or an empty string when the sources carry none"
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
