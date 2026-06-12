"""Summary (detailed) artifact generator.

Model choice validated by owner (task-72 benchmark): gpt-5.4-nano-2026-03-17.
Exhaustive format for learning (structured sections).
"""

from __future__ import annotations

import json
import os
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ValidationError, field_validator


class SummaryDetailedValidationError(Exception):
    """Raised when the model output does not match the summary_detailed schema."""


class SummaryDetailedContent(BaseModel):
    """Schema for detailed summary content (structured learning format)."""
    context: str
    main_topics: List[str]
    key_points: List[str]
    notable_quotes: List[str]
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
    def _non_empty_list(cls, value: List[str]) -> List[str]:
        if not value:
            raise ValueError("list must not be empty")
        return [p.strip() for p in value if p.strip()]

    @field_validator("notable_quotes")
    @classmethod
    def _clean_quotes(cls, value: List[str]) -> List[str]:
        # Quotes may be empty if no notable quotes found
        return [q.strip() for q in value if q.strip()]


class SummaryDetailedGenerator:
    """Generator for comprehensive, structured summary for deep learning."""

    @property
    def artifact_type_value(self) -> str:
        return "summary_detailed"

    @property
    def default_model(self) -> str:
        return os.environ.get(
            "SUMMARY_DETAILED_LLM_MODEL",
            os.environ.get("OPENAI_MODEL", "gpt-5.4-nano-2026-03-17"),
        )

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

    def response_format_schema(self) -> Optional[Dict[str, Any]]:
        return None

    def unwrap_structured_response(self, content: str) -> str:
        return content

    def validate(self, content: str) -> Dict[str, Any]:
        from media_summarizer.workers.artifact_generator.worker import _strip_code_fences

        try:
            parsed = json.loads(_strip_code_fences(content))
        except json.JSONDecodeError as exc:
            raise SummaryDetailedValidationError(
                f"summary_detailed output is not valid JSON: {exc}"
            ) from exc

        if not isinstance(parsed, dict):
            raise SummaryDetailedValidationError("summary_detailed output must be a JSON object")

        try:
            validated = SummaryDetailedContent.model_validate(parsed)
        except ValidationError as exc:
            raise SummaryDetailedValidationError(
                f"summary_detailed schema validation failed: {exc}"
            ) from exc

        return validated.model_dump()

    def build_artifact_content(
        self,
        validated: Any,
        *,
        body: Dict[str, Any],
    ) -> Dict[str, Any]:
        return validated
