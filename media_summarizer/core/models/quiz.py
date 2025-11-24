from __future__ import annotations

from typing import List, Optional
from pydantic import BaseModel, Field, validator


class Choice(BaseModel):
    id: str
    text: str = Field(min_length=1, max_length=200)
    correct: bool = False


class Question(BaseModel):
    id: str
    prompt: str = Field(min_length=1, max_length=300)
    multiple: bool = False
    choices: List[Choice]
    explanation: Optional[str] = Field(default=None, max_length=300)

    @validator("choices")
    def validate_choices(cls, v: List[Choice], values):  # type: ignore[override]
        if not v or len(v) < 2:
            raise ValueError("Each question must have at least 2 choices")
        if len(v) > 6:
            raise ValueError("Too many choices; keep <= 6 (recommend 4)")
        correct_count = sum(1 for c in v if c.correct)
        if correct_count == 0:
            raise ValueError("At least one choice must be marked correct")
        if values.get("multiple") is False and correct_count != 1:
            raise ValueError("Single-select questions must have exactly 1 correct choice")
        if values.get("multiple") is True and correct_count < 2:
            raise ValueError("Multi-select questions must have at least 2 correct choices")
        return v


class Quiz(BaseModel):
    id: str
    episode_id: Optional[str] = None
    language: str = Field(default="EN")
    questions: List[Question]

    @validator("questions")
    def validate_questions(cls, v: List[Question]):  # type: ignore[override]
        if not v:
            raise ValueError("Quiz must contain at least one question")
        if len(v) > 15:
            # Enforce the cap
            return v[:15]
        return v