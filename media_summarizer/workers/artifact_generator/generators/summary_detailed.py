"""Summary (detailed) artifact generator.

Model choice validated by owner (task-72 benchmark): gpt-5.4-nano-2026-03-17.
Exhaustive format for learning (structured sections).
"""

from __future__ import annotations

import json
import os
from typing import Any, Dict, List, Optional, Sequence

from pydantic import BaseModel, ValidationError, field_validator

from media_summarizer.workers.artifact_generator.generators import corpus


class SummaryDetailedValidationError(Exception):
    """Raised when the model output does not match the summary_detailed schema."""


class SummaryDetailedQuote(BaseModel):
    """A verbatim quote and the source it came from.

    ``source_ref`` is mandatory here and optional everywhere else: a quote is
    literal text, so its origin is objectively defined and checkable. A synthesis
    bullet legitimately draws on several sources, and demanding a reference there
    would only make the model invent one.
    """

    text: str
    source_ref: str

    @field_validator("text", "source_ref")
    @classmethod
    def _non_empty_text(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("value must be non-empty")
        return normalized


class SummaryDetailedContent(BaseModel):
    """Schema for detailed summary content (structured learning format)."""

    title: str
    context: str
    main_topics: List[str]
    key_points: List[str]
    notable_quotes: List[SummaryDetailedQuote]
    conclusion: str

    @field_validator("title", "context", "conclusion")
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
        sources: Sequence[Dict[str, Any]],
        *,
        language: Optional[str] = None,
    ) -> str:
        optional_quotes = corpus.empty_section_instruction(
            '"notable_quotes" is optional: leave it empty when no passage is worth '
            "quoting rather than quoting for the sake of it."
        )
        instructions = f"""You produce a comprehensive, structured summary of everything above.
It is meant for deep learning and reference.

Rules:
- {corpus.language_instruction(language)}
- Output STRICT JSON only. No markdown. No commentary. No code fences.
- This summary is for learning, not quick reading: it must cover the material,
  which means being as long as the material is and no longer.
{corpus.corpus_shape_instruction()}
- Context should set the stage (who, what, why) in 2-3 sentences.
- "main_topics": one entry per major theme the sources actually develop — a short
  source legitimately carries a single theme.
{corpus.coverage_instruction("bullet point", "bullet points", fields='"key_points"')}
{corpus.source_balance_instruction("bullet point", "bullet points")}
- "notable_quotes": copy verbatim only the passages that carry the material
  themselves, and never quote a passage that a bullet point already states.
{optional_quotes}
{corpus.source_ref_instruction(required=True)}
- Conclusion should synthesize the main message in 2-3 sentences.
{corpus.transcript_markers_instruction()}
{corpus.dated_facts_instruction()}
{corpus.subject_matter_instruction(verbatim_exception=True)}
{corpus.title_instruction("summary")}

Return JSON with this exact schema:
{{
  "title": "A short specific title",
  "context": "2-3 sentences setting the stage",
  "main_topics": ["Topic 1", "Topic 2"],
  "key_points": ["Detailed point 1", "Detailed point 2"],
  "notable_quotes": [{{"text": "Quote copied verbatim", "source_ref": "[S1]"}}],
  "conclusion": "2-3 sentences synthesizing the main message"
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
