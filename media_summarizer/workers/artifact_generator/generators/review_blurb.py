"""Review blurb artifact generator: one short paragraph of prose (task-323).

What the triage screen needs is not a list of points but a paragraph a reader can
skim in five seconds to decide whether to discard the item, dig into it, or file it
in a collection: *what is this about, what is its thesis, who is it for*. That is
why this is its own type rather than a variant of ``summary_short``, whose output is
a bullet list assembled for the digest.

Prose has no schema, so there is nothing to hand to Structured Outputs and nothing
to parse: the model's text *is* the artifact. Validation is therefore the two things
that can actually go wrong — an empty answer, and an answer that ignored the length
the prompt asked for (a one-line telegram, or the detailed summary all over again).

Model: ``OPENAI_MODEL``, i.e. the "all other artefacts" side of the task-72 owner
decision. Deliberately no per-type override variable for this type: the
``*_LLM_MODEL`` family the older generators read only exists in ``.env.example``, no
runtime secret carries it, and a knob no environment sets is a dead button.
"""

from __future__ import annotations

import os
from typing import Any, Dict, Optional, Sequence

from media_summarizer.workers.artifact_generator.generators import corpus

# The band the validator enforces, deliberately much wider than the 5-10 lines the
# prompt asks for: the point is to catch an answer that is not a blurb at all, not
# to police prose length. ~5 lines of French prose is ~350 characters and ~10 lines
# ~900, so the band leaves a factor of ~2.5 on either side.
MIN_BLURB_CHARS = 140
MAX_BLURB_CHARS = 2600


class ReviewBlurbValidationError(Exception):
    """Raised when the model output is empty or nowhere near the asked-for length."""


class ReviewBlurbGenerator:
    """Generator for the short prose blurb shown on the triage screen."""

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
        instructions = f"""You produce a short prose summary of everything above, for a reader
deciding in a few seconds whether this is worth their time.

Rules:
- {corpus.language_instruction(language)}
- Output plain prose only. No markdown, no headings, no bullet list, no JSON, no
  code fences, no title, no preamble such as "Here is the summary".
- One single paragraph of 5 to 10 lines. Write continuous sentences, not a list of
  points glued together.
- Answer three things, in this order and without labelling them: what the subject
  is, what the central claim or takeaway is, and who would get something out of it.
- Be specific: name the actual subject, the actual claim, the actual audience. A
  blurb that would fit any other source is a failed blurb.
- Never write more than the sources say, and never invent a thesis a source does
  not carry. A source that mostly entertains is described as what it is.
{corpus.subject_matter_instruction()}

Return the paragraph and nothing else.
"""
        return corpus.build_prompt(sources, instructions)

    def response_format_schema(self) -> Optional[Dict[str, Any]]:
        return None

    def unwrap_structured_response(self, content: str) -> str:
        return content

    def validate(self, content: str) -> Dict[str, Any]:
        """Return ``{"blurb": <prose>}``.

        No ``title`` key, unlike the five requestable types: a title is what tells
        two entries of a type apart in the history listing, and this type is
        filtered out of that listing. The worker reads the title with ``.get``, so
        the record simply keeps a null one.

        Rejecting an empty answer does not contradict the "a section may be empty"
        rule the other prompts carry: that rule is about *how many* items a thin
        source yields, whereas here the artifact is one single field and the
        precondition to even reach this point is that a transcript exists.
        """
        from media_summarizer.workers.artifact_generator.worker import _strip_code_fences

        blurb = " ".join(_strip_code_fences(content or "").split())
        if not blurb:
            raise ReviewBlurbValidationError("review_blurb output is empty")
        if not (MIN_BLURB_CHARS <= len(blurb) <= MAX_BLURB_CHARS):
            raise ReviewBlurbValidationError(
                f"review_blurb output is {len(blurb)} characters, outside the "
                f"accepted {MIN_BLURB_CHARS}-{MAX_BLURB_CHARS} band"
            )
        return {"blurb": blurb}

    def build_artifact_content(
        self,
        validated: Any,
        *,
        body: Dict[str, Any],
    ) -> Dict[str, Any]:
        return validated
