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

Everything below the layout is a *shared instruction fragment*. A fragment lives
here rather than in one generator as soon as two types need the same rule stated
the same way, which is also what keeps a wording fix from landing in four prompts
out of five.
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

    The header also **dates** each source, which is what lets the model resolve
    the relative time words transcripts are full of. A weather page saying "today
    the sea is 25.7 °C" produced a permanent flashcard asking for the temperature
    "today" (task-316 §2.7) purely because the model had no date to attach that
    sentence to. Two distinct keys rather than one blurred field:

    * ``published`` — a genuine publication date, emitted only when the pipeline
      actually resolved one (a podcast episode carries it; a scraped page does
      not).
    * ``captured`` — the day the text entered the library, i.e. the day it was
      fetched. Always available, and on a source whose content *is* a bulletin it
      is precisely the day its "today" refers to.
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
        published = (source.get("published") or "").strip()
        if published:
            header_parts.append(f"published: {published}")
        captured = (source.get("captured") or "").strip()
        if captured:
            header_parts.append(f"captured: {captured}")
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
    """The target language binds every string, down to the vocabulary.

    "Use {language} for the output" fixed the language of the prose and said
    nothing about the terms lifted from the source, so French notes on a
    bilingual page came back with a half-English glossary — "Long sleeve shorty",
    "Spring wetsuit (ex. 3/2mm)" — and bullets mixing the two (task-316 §2.9). A
    glossary meant for learning cannot be written in a language the reader did
    not ask for, so the rule now names the fields most prone to drift and gives
    the single legitimate exception plus its price: a gloss on first use.
    """
    target = language or "the language of the sources"
    return (
        f"Write every string you produce in {target}: the title, the headings, "
        f"the questions and their answers, and above all the terms and "
        f"definitions of any glossary or concept list — all of them, with no "
        f"exception, even when the sources state them in another language. A term "
        f"stays in its original language only when {target} has no accepted "
        f"equivalent for it, and it is then glossed in {target} at its first "
        f"occurrence."
    )


def title_instruction(kind: str) -> str:
    """Every type emits its own title, which is what tells two entries apart.

    The history lists several entries of the same type for the same scope, so a
    mechanically derived label ("Quiz — 12 March") would leave same-day entries
    indistinguishable. The model just read the corpus and is the only party able
    to write "The limits of scaling"; it costs ~10 output tokens.

    The last clause is measured too: on a three-source collection (a longboard
    tutorial, a surf video, a weather page) the title read "Guide rapide du
    longboard: stance, poussée, freinage et pop-up" and silently dropped two
    sources out of three (task-316 §2.8).
    """
    return (
        f'- "title": a short specific title (3 to 80 characters) naming what this '
        f"{kind} is about. Name the subject matter, never the artifact type or "
        f"the date. When the corpus holds several sources, the title must not name "
        f"only one of them: it names what they have in common, or states the range "
        f"they span."
    )


def corpus_shape_instruction() -> str:
    """A user collection is normally heterogeneous — say so instead of forcing one story.

    "Cover the sources as a whole; do not summarise them one by one" assumed a
    shared subject. On a collection of a longboard tutorial, a surf video and a
    weather page it produced a single narrative about the first source with one
    orphan bullet glued at the end (task-316 §2.8). Nothing in the prompt said
    what to do when the sources have nothing in common, which is the normal case
    for a folder someone filled over weeks — hence two explicit branches.
    """
    return (
        "- Look at whether the sources share a subject before writing anything. If "
        "they do, synthesise across them as one body of material. If they do not, "
        "say so in one sentence and then give one line per source. Never force a "
        "single narrative over unrelated material, and never let one source stand "
        "in for the others."
    )


def source_balance_instruction(unit: str, unit_plural: str) -> str:
    """Cover every source, in proportion to what each one carries.

    "Spread the questions across the sources rather than covering only the first
    one" is qualitative and obtained nothing: on a 4 642 / 2 165 / 2 210 byte
    corpus (51 % / 24 % / 24 %) the quiz split 5 / 1 / 1, i.e. 71 % on S1
    (task-316 §2.8). The proportional rule is stated, and then explicitly
    subordinated to the exhaustiveness rule of ``coverage_instruction``: evening
    out counts must never become a reason to drop a point.
    """
    return (
        f"- When the corpus holds several sources, cover each of them, and let the "
        f"share of {unit_plural} drawn from a source follow the share of the "
        f"material it carries: a source holding about half the material carries "
        f"about half the {unit_plural}, and no source is left with none at all.\n"
        f"- Covering every point of every source comes first. Never drop a point "
        f"from one source to even out the counts, and never add a filler {unit} to "
        f"a thin source for the same reason — a source that genuinely teaches less "
        f"simply contributes fewer {unit_plural}."
    )


def dated_facts_instruction(*, review_item: Optional[str] = None) -> str:
    """Anchor a fact that is only true at one instant, and never drill it.

    A weather page produced "Aujourd'hui : eau à 25,7 °C" inside a permanent set
    of notes, and flashcard n° 1 asked for "la température de la mer aujourd'hui"
    — a card that then entered the FSRS review queue and will re-ask, months
    later, about a single day of August 2026 (task-316 §2.7). The header dates
    every source (``published`` / ``captured``), so the model has something to
    anchor to; ``review_item`` adds the second half for the two types that feed
    spaced repetition and self-testing.
    """
    text = (
        "- Each source header carries the date its text was published or captured. "
        'Relative time words in a source — "today", "currently", "this week", "at '
        'the moment" — refer to that date, not to the day someone reads what you '
        "write. When a fact is only true at one point in time, anchor it to that "
        'date ("on 18 August 2026 the sea was 25.7 °C") and never carry the '
        "relative wording over."
    )
    if review_item:
        text += (
            f" Do not turn a dated measurement into a {review_item} at all: an "
            f"artifact is kept and reviewed long after it is produced, so build the "
            f"{review_item} on the rule, the method or the range the sources "
            f"establish, never on the reading of the day."
        )
    return text


def transcript_markers_instruction() -> str:
    """Transcription artefacts are not content.

    The sources are automatic transcripts and no prompt said so, so the model
    analysed the markup: the ``summary_short`` of a TikTok clip concluded that
    the tone was "rythmé par des rires […] et une touche musicale à la fin",
    which describes ``[rires]`` and ``[musique]`` tags rather than anything said
    (task-316 §2.10).
    """
    return (
        "- The sources are automatic transcripts of speech, not edited prose. "
        '">>" marks a change of speaker, and bracketed tags such as "[laughs]", '
        '"[music]", "[coughs]", "[applause]" are non-speech annotations: use them '
        "to attribute or situate speech, never treat them as content to analyse or "
        "report on. Transcription errors and dropped words are expected — read "
        "through them, and reproduce them only inside a verbatim quote."
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
