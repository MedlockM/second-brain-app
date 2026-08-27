"""Notes artifact generator.

Model choice: gpt-4o-mini-2024-07-18 for notes (per worker default).
"""

from __future__ import annotations

import json
import os
from typing import Any, Dict, List, Optional, Sequence

from pydantic import BaseModel, ValidationError, field_validator

from media_summarizer.workers.artifact_generator.generators import corpus


class NotesValidationError(Exception):
    """Raised when the model output does not match the canonical notes schema."""


class NotesConcept(BaseModel):
    term: str
    explanation: str
    # Kept, and framed in the prompt instead of dropped. The measurement that put
    # it in question — 8 concepts out of 8 marked `core` on the surf course
    # (task-316 §3.3) — is a calibration failure, not a design failure: the prompt
    # asked for one of two words without ever saying what separates them. The
    # mobile badge that renders it stays as it is.
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
    title: str
    objectives: List[str]
    concepts: List[NotesConcept]
    key_points: List[str]
    action_items: List[str]
    glossary: List[NotesGlossaryItem]

    @field_validator("title")
    @classmethod
    def _non_empty_title(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("title must be non-empty")
        return normalized

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


class NotesGenerator:
    """Generator for structured study/review notes from a transcript."""

    @property
    def artifact_type_value(self) -> str:
        return "notes"

    @property
    def default_model(self) -> str:
        return os.environ.get(
            "NOTES_LLM_MODEL",
            os.environ.get("OPENAI_MODEL", "gpt-4o-mini-2024-07-18"),
        )

    def build_prompt(
        self,
        sources: Sequence[Dict[str, Any]],
        *,
        language: Optional[str] = None,
    ) -> str:
        optional_sections = corpus.empty_section_instruction(
            'Every section is optional: leave "objectives" empty when the sources '
            'do not teach anything to achieve, "concepts" empty when they explain '
            'no notion, "action_items" empty when they prescribe nothing, and '
            '"glossary" empty when they introduce no term.'
        )
        importance_rule = (
            "- `importance` is either `core` or `supporting`, and the two are not "
            "interchangeable: mark a concept `core` when a reader cannot use the "
            "material at all without it, and `supporting` when it is context, a "
            "refinement, an example or a name worth recognising. Expect a minority "
            "of `core` — on most sources one or two concepts out of five. If "
            "everything is `core`, nothing is, and the distinction has told the "
            "reader nothing."
        )
        instructions = f"""You produce a structured study/review notes artifact from everything above.

Rules:
- {corpus.language_instruction(language)}
- Output STRICT JSON only. No markdown. No commentary. No code fences.
- Keep the structure stable for client rendering.
- Focus on learning/review value, not a generic summary.
- Build one set of notes across all the sources, not one section per source.
- Avoid sponsor/ad content unless it is central to the source material.
{corpus.coverage_instruction("entry", "entries", fields='"concepts" and "key_points"')}
{optional_sections}
- Every string must be concise and useful.
{importance_rule}
{corpus.transcript_markers_instruction()}
{corpus.dated_facts_instruction()}
{corpus.subject_matter_instruction()}
{corpus.title_instruction("set of notes")}

Return JSON with this exact schema:
{{
  "title": "A short specific title",
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
            raise NotesValidationError(f"notes output is not valid JSON: {exc}") from exc

        if not isinstance(parsed, dict):
            raise NotesValidationError("notes output must be a JSON object")

        try:
            validated = NotesContent.model_validate(parsed)
        except ValidationError as exc:
            raise NotesValidationError(f"notes output schema validation failed: {exc}") from exc

        return validated.model_dump()

    def build_artifact_content(
        self,
        validated: Any,
        *,
        body: Dict[str, Any],
    ) -> Dict[str, Any]:
        return validated
