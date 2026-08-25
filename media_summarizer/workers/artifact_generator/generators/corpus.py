"""Shared prompt layout: preamble, then tagged corpus, then type instructions.

The order matters and is not cosmetic. OpenAI's prompt cache only matches an
**exactly identical prefix**, from 1 024 tokens up, and bills cache reads at 0.1x
the input price. The generators used to emit instructions → schema → transcript,
which left a shared prefix of a few dozen tokens between two types: the cache
never bit. With the corpus first, the five types of one request share the whole
corpus prefix, which is what makes a 25-source collection cost 0.0364 € for all
five instead of 0.0903 € (task-269 §2.6) — no intermediate store, no lock, the
sharing is done provider-side.

The corpus is tagged ``[S1] … [Sn]`` in snapshot order. Tags are also what output
schemas reference in ``source_ref``: the model copies back a short token instead
of a UUID it would be prone to hallucinate, and the API resolves the label
through the index in ``sources``.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Sequence

# Identical for every artifact type — the first bytes of the shared cache prefix.
PROMPT_PREAMBLE = (
    "You are given the full text of one or more sources, tagged [S1], [S2], and "
    "so on. Read all of them. Instructions describing what to produce follow the "
    "sources.\n"
)


def source_label(index: int) -> str:
    """``[S1]`` for the first source, in snapshot order."""
    return f"[S{index + 1}]"


def build_corpus_block(sources: Sequence[Dict[str, Any]]) -> str:
    """The tagged corpus: a header per source, then its full text.

    The full text of every source goes in — no condensation stage. That is the
    point of the retained strategy: flashcards and quizzes are detail extractors,
    and anything that summarises before generating removes exactly the material
    they live on.
    """
    blocks: List[str] = []
    for index, source in enumerate(sources):
        header_parts = [source_label(index)]
        title = (source.get("title") or "").strip()
        if title:
            header_parts.append(f"title: {title}")
        language = (source.get("language") or "").strip()
        if language:
            header_parts.append(f"language: {language}")
        text = (source.get("text") or "").strip()
        blocks.append(" | ".join(header_parts) + "\n" + text)
    return "\n\n".join(blocks)


def build_prompt(
    sources: Sequence[Dict[str, Any]],
    instructions: str,
) -> str:
    """Assemble preamble → corpus → instructions, in that order."""
    return (
        f"{PROMPT_PREAMBLE}\n"
        f"===== SOURCES =====\n"
        f"{build_corpus_block(sources)}\n"
        f"===== END OF SOURCES =====\n\n"
        f"{instructions}"
    )


def language_instruction(language: Optional[str]) -> str:
    return (
        f"Use {language} for the output."
        if language
        else "Use the same language as the sources."
    )


def title_instruction(kind: str) -> str:
    """Every type emits its own title, which is what tells two entries apart.

    The history lists several entries of the same type for the same scope, so a
    mechanically derived label ("Quiz — 12 March") would leave same-day entries
    indistinguishable. The model just read the corpus and is the only party able
    to write "The limits of scaling"; it costs ~10 output tokens.
    """
    return (
        f'- "title": a short specific title (3 to 80 characters) naming what this '
        f"{kind} is about. Name the subject matter, never the artifact type or "
        f"the date."
    )


def coverage_instruction(unit: str, unit_plural: str, *, fields: str) -> str:
    """Quantity is a function of the material — no floor, no ceiling.

    The fixed ranges this replaces ("between 5 and 15 depending on content
    density") were measured doing the opposite of what they say: a 414-byte
    sketch yielded ten flashcards and twelve "detailed key points", while a
    28 kB video yielded seven quiz questions (task-316 §2.1, §2.2). A count the
    model must reach is padding on a thin source; a count it must not exceed is
    truncation on a dense one. An artifact is generated once per media item, so a
    partial pass is never made up for later: the material is stated as the only
    bound, in both directions.
    """
    return (
        f"- Let the sources set how many {unit_plural} you write in {fields}: one "
        f"{unit} per distinct point the sources actually teach, and cover every "
        f"one of those points. There is no target count and no maximum — a dense "
        f"source yields many {unit_plural}, a source that teaches almost nothing "
        f"yields one or two.\n"
        f"- Never pad: do not restate one point in two {unit_plural}, do not split "
        f"a point in two to raise the count, and do not invent material the "
        f"sources do not carry. Stopping once the material is covered is the "
        f"correct behaviour."
    )


def empty_section_instruction(detail: str) -> str:
    """An empty section is a valid answer.

    Every section being mandatory is what produced learning objectives for a
    weather bulletin and an "actionable insight" addressed to nobody on a TikTok
    clip (task-316 §2.3). The mobile screen already renders each section
    conditionally, so an empty list or string displays correctly — only the
    prompt forbade it.
    """
    return (
        f"- {detail} Leaving a section empty is a correct answer when the sources "
        f"carry nothing for it; filling it with something invented is not."
    )


def subject_matter_instruction(*, verbatim_exception: bool = False) -> str:
    """Write about the subject, not about the document.

    39 % of the quiz questions in dev tested the memory of the document rather
    than the subject ("Selon la source, pourquoi…"), and the detailed summaries
    described their source instead of restating it ("Le texte présente un court
    sketch") — task-316 §2.5.
    """
    text = (
        "- Write about the subject matter, never about the document. Do not write "
        '"the source says", "according to the text", "the video explains", "the '
        'narrator mentions", "this passage opens on". State the fact itself, the '
        "way someone who knows the subject would state it."
    )
    if verbatim_exception:
        text += (
            ' The one exception is "notable_quotes", which is verbatim by '
            "construction: copy the words as they appear."
        )
    return text


def source_ref_instruction(*, required: bool) -> str:
    if required:
        return (
            '- "source_ref": the tag of the source the quote comes from, e.g. '
            '"[S2]". Required: a quote is verbatim, so its origin must be '
            "checkable."
        )
    return (
        '- "source_ref": the tag of the source this entry comes from, e.g. '
        '"[S2]". Use null when it draws on several sources.'
    )
