"""Notes artifact generator.

Model choice: gpt-4o-mini-2024-07-18 for notes (per worker default).
"""

from __future__ import annotations

import json
import os
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ValidationError, field_validator


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
