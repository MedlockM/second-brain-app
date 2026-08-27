"""Flashcards artifact generator.

Model choice validated by owner (task-72 benchmark): gpt-5.4-nano-2026-03-17.
Uses OpenAI Structured Outputs (response_format) for reliable JSON generation.
"""

from __future__ import annotations

import json
import os
from typing import Any, Dict, List, Optional, Sequence

from pydantic import BaseModel, ValidationError, field_validator

from media_summarizer.workers.artifact_generator.generators import corpus

# One card is a valid deck: the material decides how many cards there are, and a
# source that teaches one thing must be allowed to yield one card instead of the
# four padded ones the old floor of five forced (task-316 §2.2, §2.3). Zero stays
# a hard reject — an artifact with no card at all is a failed generation, not a
# deck. There is deliberately no ceiling: an artifact is generated once per media
# item, so truncating a dense source would drop material for good.
MIN_FLASHCARDS = 1


class FlashcardsValidationError(Exception):
    """Raised when the model output does not match the canonical flashcards schema."""


class FlashcardItem(BaseModel):
    question: str
    answer: str
    # Optional: a card may legitimately cross several sources, and forcing a
    # reference there would only make the model pick one arbitrarily.
    source_ref: Optional[str] = None

    @field_validator("question", "answer")
    @classmethod
    def _non_empty_text(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("value must be non-empty")
        return normalized

    @field_validator("source_ref")
    @classmethod
    def _clean_source_ref(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        normalized = value.strip()
        return normalized or None


class FlashcardsGenerator:
    """Generator for Q/A flashcards over the corpus."""

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
        sources: Sequence[Dict[str, Any]],
        *,
        language: Optional[str] = None,
    ) -> str:
        instructions = f"""You produce a set of Q&A flashcards from everything above, for spaced repetition learning.

Rules:
- {corpus.language_instruction(language)}
- Output STRICT JSON only. No markdown. No commentary. No code fences.
{corpus.coverage_instruction("card", "cards", fields='"cards"')}
{corpus.source_balance_instruction("card", "cards")}
- Follow the minimum information principle: one concept per card.
- Do NOT generate trivial cards (e.g. "What is the title of this episode?").
- Do NOT generate ambiguous cards: each question must have a single, verifiable answer.
- Keep questions clear and concise.
- Keep answers factual and brief (1-3 sentences max).
- Avoid sponsor/ad content unless it is central to the source material.
- A deck of one card is a valid deck. The deck must hold at least one card, so
  when the sources barely teach anything, card the one or two facts they do
  establish and stop there — one solid card beats five padded ones.
{corpus.empty_section_instruction('Anything the sources do not fill stays empty: "source_ref" is null rather than guessed.')}
{corpus.source_ref_instruction(required=False)}
{corpus.transcript_markers_instruction()}
{corpus.dated_facts_instruction(review_item="flashcard")}
{corpus.subject_matter_instruction()}
{corpus.title_instruction("card deck")}

Return JSON with this exact schema:
{{
  "title": "A short specific title",
  "cards": [
    {{
      "question": "...",
      "answer": "...",
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
                "name": "flashcards",
                "strict": True,
                "schema": {
                    "type": "object",
                    "properties": {
                        "title": {"type": "string"},
                        "cards": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "question": {"type": "string"},
                                    "answer": {"type": "string"},
                                    "source_ref": {"type": ["string", "null"]},
                                },
                                "required": ["question", "answer", "source_ref"],
                                "additionalProperties": False,
                            },
                        },
                    },
                    "required": ["title", "cards"],
                    "additionalProperties": False,
                },
            },
        }

    def unwrap_structured_response(self, content: str) -> str:
        # The structured wrapper is already the shape `validate` expects now that
        # the title lives beside the cards, so there is nothing to unwrap.
        return content

    def validate(self, content: str) -> Dict[str, Any]:
        from media_summarizer.workers.artifact_generator.worker import _strip_code_fences

        try:
            parsed = json.loads(_strip_code_fences(content))
        except json.JSONDecodeError as exc:
            raise FlashcardsValidationError(
                f"flashcards output is not valid JSON: {exc}"
            ) from exc

        if not isinstance(parsed, dict):
            raise FlashcardsValidationError("flashcards output must be a JSON object")

        title = str(parsed.get("title") or "").strip()
        if not title:
            raise FlashcardsValidationError("flashcards output must carry a non-empty title")

        raw_cards = parsed.get("cards")
        if not isinstance(raw_cards, list):
            raise FlashcardsValidationError("flashcards output must carry a 'cards' array")

        if len(raw_cards) < MIN_FLASHCARDS:
            raise FlashcardsValidationError(
                f"flashcards output must contain at least {MIN_FLASHCARDS} items, got {len(raw_cards)}"
            )

        cards: List[Dict[str, Any]] = []
        for idx, item in enumerate(raw_cards):
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
            cards.append(card.model_dump())

        return {"title": title, "cards": cards}

    def build_artifact_content(
        self,
        validated: Any,
        *,
        body: Dict[str, Any],
    ) -> Dict[str, Any]:
        cards = validated["cards"]
        return {
            "title": validated["title"],
            "cards": cards,
            "card_count": len(cards),
        }
