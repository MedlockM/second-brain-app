"""Quiz artifact generator.

Model choice validated by owner (task-72 benchmark): gpt-5.4-nano-2026-03-17.
Uses OpenAI Structured Outputs (response_format) for reliable JSON generation.
"""

from __future__ import annotations

import hashlib
import json
import os
import random
from typing import Any, Dict, List, Optional, Sequence

from pydantic import BaseModel, ValidationError, field_validator

from media_summarizer.workers.artifact_generator.generators import corpus

MIN_QUESTIONS = 5
MAX_QUESTIONS = 10
OPTIONS_PER_QUESTION = 4
LABELS = ("A", "B", "C", "D")


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
    # Optional: a question may draw on several sources.
    source_ref: Optional[str] = None

    @field_validator("source_ref")
    @classmethod
    def _clean_source_ref(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        normalized = value.strip()
        return normalized or None

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
        sources: Sequence[Dict[str, Any]],
        *,
        language: Optional[str] = None,
    ) -> str:
        instructions = f"""You produce a multiple-choice quiz from everything above, for knowledge testing.

Rules:
- {corpus.language_instruction(language)}
- Output STRICT JSON only. No markdown. No commentary. No code fences.
- Generate between {MIN_QUESTIONS} and {MAX_QUESTIONS} questions depending on content density.
- Spread the questions across the sources rather than covering only the first one.
- Each question must have exactly {OPTIONS_PER_QUESTION} options labeled A, B, C, D.
- Exactly one option is correct per question.
- "correct_answer" must be the label of the correct option. Vary which label holds it
  across questions — do not systematically put the correct option first.
- Questions should test comprehension of key concepts, not trivial details.
- Do NOT generate questions about ads/sponsors unless central to the content.
- Include a brief explanation for why the correct answer is right.
- Make incorrect options plausible but clearly wrong to someone who understood the content.
{corpus.source_ref_instruction(required=False)}
{corpus.title_instruction("quiz")}

Return JSON with this exact schema:
{{
  "title": "A short specific title",
  "questions": [
    {{
      "question": "...",
      "options": [
        {{"label": "A", "text": "..."}},
        {{"label": "B", "text": "..."}},
        {{"label": "C", "text": "..."}},
        {{"label": "D", "text": "..."}}
      ],
      "correct_answer": "C",
      "explanation": "...",
      "source_ref": "[S1]"
    }}
  ]
}}
"""
        return corpus.build_prompt(sources, instructions)

    def response_format_schema(self) -> Optional[Dict[str, Any]]:
        return {
            "type": "json_schema",
            "json_schema": {
                "name": "quiz",
                "strict": True,
                "schema": {
                    "type": "object",
                    "properties": {
                        "title": {"type": "string"},
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
                                                "label": {
                                                    "type": "string",
                                                    "enum": list(LABELS),
                                                },
                                                "text": {"type": "string"},
                                            },
                                            "required": ["label", "text"],
                                            "additionalProperties": False,
                                        },
                                    },
                                    "correct_answer": {
                                        "type": "string",
                                        "enum": list(LABELS),
                                    },
                                    "explanation": {"type": "string"},
                                    "source_ref": {"type": ["string", "null"]},
                                },
                                "required": [
                                    "question",
                                    "options",
                                    "correct_answer",
                                    "explanation",
                                    "source_ref",
                                ],
                                "additionalProperties": False,
                            },
                        }
                    },
                    "required": ["title", "questions"],
                    "additionalProperties": False,
                },
            },
        }

    def unwrap_structured_response(self, content: str) -> str:
        # The structured wrapper is already the shape `validate` expects now that
        # the title lives beside the questions, so there is nothing to unwrap.
        return content

    def validate(self, content: str) -> Dict[str, Any]:
        from media_summarizer.workers.artifact_generator.worker import _strip_code_fences

        try:
            parsed = json.loads(_strip_code_fences(content))
        except json.JSONDecodeError as exc:
            raise QuizValidationError(
                f"quiz output is not valid JSON: {exc}"
            ) from exc

        if not isinstance(parsed, dict):
            raise QuizValidationError("quiz output must be a JSON object")

        title = str(parsed.get("title") or "").strip()
        if not title:
            raise QuizValidationError("quiz output must carry a non-empty title")

        raw_questions = parsed.get("questions")
        if not isinstance(raw_questions, list):
            raise QuizValidationError("quiz output must carry a 'questions' array")

        if len(raw_questions) < MIN_QUESTIONS:
            raise QuizValidationError(
                f"quiz output must contain at least {MIN_QUESTIONS} questions, got {len(raw_questions)}"
            )

        if len(raw_questions) > MAX_QUESTIONS:
            raw_questions = raw_questions[:MAX_QUESTIONS]

        questions: List[Dict[str, Any]] = []
        for idx, item in enumerate(raw_questions):
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

            labels = [option.label for option in question.options]
            if set(labels) != set(LABELS):
                raise QuizValidationError(
                    f"quiz item at index {idx} must label its options {', '.join(LABELS)} exactly "
                    f"once each, got {labels}"
                )

            questions.append(question.model_dump())

        return {"title": title, "questions": questions}

    def build_artifact_content(
        self,
        validated: Any,
        *,
        body: Dict[str, Any],
    ) -> Dict[str, Any]:
        questions = _shuffle_options(
            validated["questions"], artifact_id=body.get("artifact_id")
        )
        return {
            "title": validated["title"],
            "questions": questions,
            "question_count": len(questions),
        }


def _question_rng(artifact_id: Optional[str], index: int, question: str) -> random.Random:
    """Seed a RNG deterministically so re-running a generation reshuffles identically.

    ``artifact_id`` is the primary seed source; the question text is folded in so
    that two questions of the same artifact do not share a permutation, and acts
    as the sole source when no artifact id is present in the message.
    """
    seed_material = f"{artifact_id or ''}:{index}:{question}".encode("utf-8")
    seed = int.from_bytes(hashlib.sha256(seed_material).digest()[:8], "big")
    return random.Random(seed)


def _shuffle_options(
    questions: List[Dict[str, Any]],
    *,
    artifact_id: Optional[str],
) -> List[Dict[str, Any]]:
    """Redistribute the correct answer across labels A-D.

    The model overwhelmingly emits the correct option first: it writes ``options``
    before ``correct_answer``, so the answer it just had in mind lands on label A
    and the distractors are backfilled after it. Prompt-level instructions only
    soften that bias, so the position is reassigned here instead.
    """
    shuffled: List[Dict[str, Any]] = []
    for index, question in enumerate(questions):
        options = question["options"]
        correct_source = next(
            i for i, option in enumerate(options) if option["label"] == question["correct_answer"]
        )

        order = list(range(len(options)))
        _question_rng(artifact_id, index, question["question"]).shuffle(order)

        shuffled.append(
            {
                **question,
                "options": [
                    {"label": LABELS[position], "text": options[source]["text"]}
                    for position, source in enumerate(order)
                ],
                "correct_answer": LABELS[order.index(correct_source)],
            }
        )
    return shuffled
