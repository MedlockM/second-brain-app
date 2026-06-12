"""Flashcards artifact generator.

Model choice validated by owner (task-72 benchmark): gpt-5.4-nano-2026-03-17.
Uses OpenAI Structured Outputs (response_format) for reliable JSON generation.
"""

from __future__ import annotations

import json
import os
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ValidationError, field_validator

MIN_FLASHCARDS = 5
MAX_FLASHCARDS = 15


class FlashcardsValidationError(Exception):
    """Raised when the model output does not match the canonical flashcards schema."""


class FlashcardItem(BaseModel):
    question: str
    answer: str

    @field_validator("question", "answer")
    @classmethod
    def _non_empty_text(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("value must be non-empty")
        return normalized


class FlashcardsGenerator:
    """Generator for Q/A flashcards from a transcript."""

    @property
    def artifact_type_value(self) -> str:
        return "flashcards"

    @property
    def default_model(self) -> str:
        return os.environ.get(
            "FLASHCARDS_LLM_MODEL",
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
        return f"""You produce a set of Q&A flashcards from a transcript for spaced repetition learning.

Rules:
- {language_instruction}
- Output STRICT JSON only. No markdown. No commentary. No code fences.
- Return a JSON array of objects, each with exactly two keys: "question" and "answer".
- Generate between {MIN_FLASHCARDS} and {MAX_FLASHCARDS} flashcards depending on content density.
- Follow the minimum information principle: one concept per card.
- Do NOT generate trivial cards (e.g. "What is the title of this episode?").
- Do NOT generate ambiguous cards: each question must have a single, verifiable answer.
- Keep questions clear and concise.
- Keep answers factual and brief (1-3 sentences max).
- Avoid sponsor/ad content unless it is central to the source material.
- Cover the most important concepts, facts, and takeaways from the transcript.

Return JSON with this exact schema:
[
  {{
    "question": "...",
    "answer": "..."
  }}
]

Transcript:
{transcript}
"""

    def response_format_schema(self) -> Optional[Dict[str, Any]]:
        return {
            "type": "json_schema",
            "json_schema": {
                "name": "flashcards",
                "strict": True,
                "schema": {
                    "type": "object",
                    "properties": {
                        "cards": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "question": {"type": "string"},
                                    "answer": {"type": "string"},
                                },
                                "required": ["question", "answer"],
                                "additionalProperties": False,
                            },
                        }
                    },
                    "required": ["cards"],
                    "additionalProperties": False,
                },
            },
        }

    def unwrap_structured_response(self, content: str) -> str:
        try:
            parsed = json.loads(content)
            if isinstance(parsed, dict) and "cards" in parsed:
                return json.dumps(parsed["cards"])
        except json.JSONDecodeError:
            pass
        return content

    def validate(self, content: str) -> List[Dict[str, Any]]:
        from media_summarizer.workers.artifact_generator.worker import _strip_code_fences

        try:
            parsed = json.loads(_strip_code_fences(content))
        except json.JSONDecodeError as exc:
            raise FlashcardsValidationError(
                f"flashcards output is not valid JSON: {exc}"
            ) from exc

        if not isinstance(parsed, list):
            raise FlashcardsValidationError("flashcards output must be a JSON array")

        if len(parsed) < MIN_FLASHCARDS:
            raise FlashcardsValidationError(
                f"flashcards output must contain at least {MIN_FLASHCARDS} items, got {len(parsed)}"
            )

        if len(parsed) > MAX_FLASHCARDS:
            parsed = parsed[:MAX_FLASHCARDS]

        validated: List[Dict[str, Any]] = []
        for idx, item in enumerate(parsed):
            if not isinstance(item, dict):
                raise FlashcardsValidationError(
                    f"flashcards item at index {idx} must be a JSON object"
                )
            try:
                card = FlashcardItem.model_validate(item)
            except ValidationError as exc:
                raise FlashcardsValidationError(
                    f"flashcards item at index {idx} schema validation failed: {exc}"
                ) from exc
            validated.append(card.model_dump())

        return validated

    def build_artifact_content(
        self,
        validated: Any,
        *,
        body: Dict[str, Any],
    ) -> Dict[str, Any]:
        return {
            "cards": validated,
            "card_count": len(validated),
        }
