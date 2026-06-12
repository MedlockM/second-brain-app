"""Quiz artifact generator.

Model choice validated by owner (task-72 benchmark): gpt-5.4-nano-2026-03-17.
Uses OpenAI Structured Outputs (response_format) for reliable JSON generation.
"""

from __future__ import annotations

import json
import os
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ValidationError, field_validator

MIN_QUESTIONS = 5
MAX_QUESTIONS = 10
OPTIONS_PER_QUESTION = 4


class QuizValidationError(Exception):
    """Raised when the model output does not match the canonical quiz schema."""


class QuizOption(BaseModel):
    label: str
    text: str

    @field_validator("label")
    @classmethod
    def _valid_label(cls, value: str) -> str:
        normalized = value.strip().upper()
        if normalized not in {"A", "B", "C", "D"}:
            raise ValueError("label must be one of A, B, C, D")
        return normalized

    @field_validator("text")
    @classmethod
    def _non_empty_text(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("text must be non-empty")
        return normalized


class QuizQuestion(BaseModel):
    question: str
    options: List[QuizOption]
    correct_answer: str
    explanation: str

    @field_validator("question", "explanation")
    @classmethod
    def _non_empty_text(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("value must be non-empty")
        return normalized

    @field_validator("correct_answer")
    @classmethod
    def _valid_answer(cls, value: str) -> str:
        normalized = value.strip().upper()
        if normalized not in {"A", "B", "C", "D"}:
            raise ValueError("correct_answer must be one of A, B, C, D")
        return normalized


class QuizGenerator:
    """Generator for multiple-choice quiz questions from a transcript."""

    @property
    def artifact_type_value(self) -> str:
        return "quiz"

    @property
    def default_model(self) -> str:
        return os.environ.get(
            "QUIZ_LLM_MODEL",
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
        return f"""You produce a multiple-choice quiz from a transcript for knowledge testing.

Rules:
- {language_instruction}
- Output STRICT JSON only. No markdown. No commentary. No code fences.
- Return a JSON array of question objects.
- Generate between {MIN_QUESTIONS} and {MAX_QUESTIONS} questions depending on content density.
- Each question must have exactly {OPTIONS_PER_QUESTION} options labeled A, B, C, D.
- Exactly one option is correct per question.
- Questions should test comprehension of key concepts, not trivial details.
- Do NOT generate questions about ads/sponsors unless central to the content.
- Include a brief explanation for why the correct answer is right.
- Make incorrect options plausible but clearly wrong to someone who understood the content.

Return JSON with this exact schema:
[
  {{
    "question": "...",
    "options": [
      {{"label": "A", "text": "..."}},
      {{"label": "B", "text": "..."}},
      {{"label": "C", "text": "..."}},
      {{"label": "D", "text": "..."}}
    ],
    "correct_answer": "A",
    "explanation": "..."
  }}
]

Transcript:
{transcript}
"""

    def response_format_schema(self) -> Optional[Dict[str, Any]]:
        return {
            "type": "json_schema",
            "json_schema": {
                "name": "quiz",
                "strict": True,
                "schema": {
                    "type": "object",
                    "properties": {
                        "questions": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "question": {"type": "string"},
                                    "options": {
                                        "type": "array",
                                        "items": {
                                            "type": "object",
                                            "properties": {
                                                "label": {"type": "string"},
                                                "text": {"type": "string"},
                                            },
                                            "required": ["label", "text"],
                                            "additionalProperties": False,
                                        },
                                    },
                                    "correct_answer": {"type": "string"},
                                    "explanation": {"type": "string"},
                                },
                                "required": ["question", "options", "correct_answer", "explanation"],
                                "additionalProperties": False,
                            },
                        }
                    },
                    "required": ["questions"],
                    "additionalProperties": False,
                },
            },
        }

    def unwrap_structured_response(self, content: str) -> str:
        try:
            parsed = json.loads(content)
            if isinstance(parsed, dict) and "questions" in parsed:
                return json.dumps(parsed["questions"])
        except json.JSONDecodeError:
            pass
        return content

    def validate(self, content: str) -> List[Dict[str, Any]]:
        from media_summarizer.workers.artifact_generator.worker import _strip_code_fences

        try:
            parsed = json.loads(_strip_code_fences(content))
        except json.JSONDecodeError as exc:
            raise QuizValidationError(
                f"quiz output is not valid JSON: {exc}"
            ) from exc

        if not isinstance(parsed, list):
            raise QuizValidationError("quiz output must be a JSON array")

        if len(parsed) < MIN_QUESTIONS:
            raise QuizValidationError(
                f"quiz output must contain at least {MIN_QUESTIONS} questions, got {len(parsed)}"
            )

        if len(parsed) > MAX_QUESTIONS:
            parsed = parsed[:MAX_QUESTIONS]

        validated: List[Dict[str, Any]] = []
        for idx, item in enumerate(parsed):
            if not isinstance(item, dict):
                raise QuizValidationError(
                    f"quiz item at index {idx} must be a JSON object"
                )
            try:
                question = QuizQuestion.model_validate(item)
            except ValidationError as exc:
                raise QuizValidationError(
                    f"quiz item at index {idx} schema validation failed: {exc}"
                ) from exc

            if len(question.options) != OPTIONS_PER_QUESTION:
                raise QuizValidationError(
                    f"quiz item at index {idx} must have exactly {OPTIONS_PER_QUESTION} options, "
                    f"got {len(question.options)}"
                )

            validated.append(question.model_dump())

        return validated

    def build_artifact_content(
        self,
        validated: Any,
        *,
        body: Dict[str, Any],
    ) -> Dict[str, Any]:
        return {
            "questions": validated,
            "question_count": len(validated),
        }
