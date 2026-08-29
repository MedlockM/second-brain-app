"""Review blurb artifact generator: the structured card of the triage screen (task-323).

What the triage screen needs is not a paragraph but something the eye can *scan*:
the user has three seconds and three buttons — discard, dig in, file it. The first
shape of this type was one continuous paragraph of 5 to 10 lines, and it failed at
exactly that job: on a real card it overflowed, scrolled inside a horizontal pager,
and had to be read linearly to yield anything. So the artifact is now three fields —
what it is, what is in it, who it is for — and the screen renders them as a headline,
bullets and a footer line.

The structure lives in the *shape of the JSON*, never in whitespace. The previous
validator flattened every run of whitespace with ``" ".join(content.split())``, which
made any line break the model produced unrecoverable downstream; per-field
normalisation replaces it.

Like ``summary_short`` — the closest sibling and the one this follows — there is no
Structured Outputs call: the prompt asks for strict JSON and ``validate`` parses it
into a Pydantic model. None of the five other generators does anything else.

Model: ``OPENAI_MODEL``, i.e. the "all other artefacts" side of the task-72 owner
decision. Deliberately no per-type override variable for this type: the
``*_LLM_MODEL`` family the older generators read only exists in ``.env.example``, no
runtime secret carries it, and a knob no environment sets is a dead button.
"""

from __future__ import annotations

import json
import os
from typing import Any, Dict, List, Optional, Sequence

from pydantic import BaseModel, ValidationError, field_validator

from media_summarizer.workers.artifact_generator.generators import corpus

# At most four bullets reach the card. The cap is enforced by truncating the *list*,
# never by cutting a bullet's text: a clipped sentence reads as a bug, one bullet
# fewer does not.
MAX_POINTS = 4

# A global band on the rendered text, playing the same role the old character band
# played: catch an answer that is not a blurb at all — a three-word telegram, or the
# detailed summary pasted in. It is not there to police per-field length, which the
# prompt states and which ``numberOfLines`` enforces visually on the card.
MIN_TOTAL_CHARS = 120
MAX_TOTAL_CHARS = 1200


class ReviewBlurbValidationError(Exception):
    """Raised when the model output does not match the review_blurb schema."""


class ReviewBlurbContent(BaseModel):
    """``hook`` + ``points`` + ``audience``, the three questions a triage answers."""

    hook: str
    points: List[str]
    # Optional for the same reason ``summary_short.takeaway`` is: demanding a field
    # unconditionally is what makes a model invent one. A clip that is for nobody in
    # particular has no audience, and the card simply hides the line.
    audience: str = ""

    @field_validator("hook")
    @classmethod
    def _non_empty_hook(cls, value: str) -> str:
        normalized = " ".join(value.split())
        if not normalized:
            raise ValueError("hook must be non-empty")
        return normalized

    @field_validator("audience", mode="before")
    @classmethod
    def _optional_audience(cls, value: Any) -> str:
        if value is None:
            return ""
        return " ".join(str(value).split())

    @field_validator("points")
    @classmethod
    def _non_empty_points(cls, value: List[str]) -> List[str]:
        cleaned = [" ".join(str(p).split()) for p in value]
        cleaned = [p for p in cleaned if p]
        if not cleaned:
            raise ValueError("points must not be empty")
        return cleaned[:MAX_POINTS]


class ReviewBlurbGenerator:
    """Generator for the structured blurb shown on the triage screen."""

    @property
    def artifact_type_value(self) -> str:
        return "review_blurb"

    @property
    def default_model(self) -> str:
        return os.environ.get("OPENAI_MODEL", "gpt-5.4-nano-2026-03-17")

    def build_prompt(
        self,
        sources: Sequence[Dict[str, Any]],
        *,
        language: Optional[str] = None,
    ) -> str:
        instructions = f"""You produce the triage card of everything above, for a reader
deciding in about three seconds whether to discard this, dig into it, or file it.

Rules:
- {corpus.language_instruction(language)}
- Output STRICT JSON only. No markdown. No commentary. No code fences. No preamble
  such as "Here is the summary".
- "hook": one single sentence of 60 to 140 characters naming what this actually is.
  Name the subject, never the document, and never open on "this content", "this
  video", "this article".
- "points": 2 to {MAX_POINTS} entries, one line each, 30 to 110 characters. Each one
  carries a distinct piece of what the sources hold — a theme covered, a claim made,
  a method shown. Write them as fragments, not as full sentences with a verb and a
  full stop. A source that holds little yields two; there is no reason to reach {MAX_POINTS}.
- Never restate the hook in the points, and never restate one point in another.
- "audience": one short phrase of at most 80 characters saying who gets something out
  of this. Return an empty string when the sources are for no one in particular
  rather than inventing a reader.
- Be specific throughout: name the actual subject, the actual themes, the actual
  reader. A card that would fit any other source is a failed card.
- Never write more than the sources say, and never invent a thesis a source does not
  carry. A source that mostly entertains is described as what it is.
{corpus.subject_matter_instruction()}

Return JSON with this exact schema:
{{
  "hook": "One sentence naming what this is",
  "points": ["First distinct point", "Second distinct point"],
  "audience": "Who this is for, or an empty string"
}}
"""
        return corpus.build_prompt(sources, instructions)

    def response_format_schema(self) -> Optional[Dict[str, Any]]:
        return None

    def unwrap_structured_response(self, content: str) -> str:
        return content

    def validate(self, content: str) -> Dict[str, Any]:
        """Return ``{"hook": str, "points": [str], "audience": str}``.

        No ``title`` key, unlike the five requestable types: a title is what tells
        two entries of a type apart in the history listing, and this type is
        filtered out of that listing. The worker reads the title with ``.get``, so
        the record simply keeps a null one.

        Rejecting an empty answer does not contradict the "a section may be empty"
        rule the other prompts carry: that rule is about *how many* items a thin
        source yields, and it is honoured here by ``audience``. What cannot be empty
        is the card itself, whose precondition is that a transcript exists.
        """
        from media_summarizer.workers.artifact_generator.worker import _strip_code_fences

        try:
            parsed = json.loads(_strip_code_fences(content or ""))
        except json.JSONDecodeError as exc:
            raise ReviewBlurbValidationError(
                f"review_blurb output is not valid JSON: {exc}"
            ) from exc

        if not isinstance(parsed, dict):
            raise ReviewBlurbValidationError("review_blurb output must be a JSON object")

        try:
            validated = ReviewBlurbContent.model_validate(parsed)
        except ValidationError as exc:
            raise ReviewBlurbValidationError(
                f"review_blurb schema validation failed: {exc}"
            ) from exc

        total = len(validated.hook) + sum(len(p) for p in validated.points) + len(
            validated.audience
        )
        if not (MIN_TOTAL_CHARS <= total <= MAX_TOTAL_CHARS):
            raise ReviewBlurbValidationError(
                f"review_blurb output totals {total} characters, outside the "
                f"accepted {MIN_TOTAL_CHARS}-{MAX_TOTAL_CHARS} band"
            )

        return validated.model_dump()

    def build_artifact_content(
        self,
        validated: Any,
        *,
        body: Dict[str, Any],
    ) -> Dict[str, Any]:
        return validated
