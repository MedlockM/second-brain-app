"""
Shared transcript formatting (task-232, benchmark task-231 option B).

Single source of truth for "what a readable transcript looks like".

The canonical transcript object in S3 stays **plain UTF-8 text**; paragraph
structure is expressed in-band as blank lines. That keeps the four consumers of
the transcript object (translation worker, artifact fingerprinting/prompts,
Algolia chunking, raw-content API) working on prose, and it survives the
translation pipeline for free because the translation prompt already mandates
preserving paragraph breaks and speaker labels.

Two call sites use this module:

- **write path**: every transcript producer normalizes the text before uploading
  it to S3, so the stored bytes are already readable (translation, artifact
  prompts and search all benefit, not only the viewer);
- **read path**: ``raw_content_service`` normalizes again on every read. The
  normalizer is idempotent, so already-structured text passes through untouched
  while legacy flat transcripts get structured on the fly. This is what makes an
  S3 backfill unnecessary (migration strategy M0): stored bytes never change, so
  artifact fingerprints and translation caches stay valid.

Guarantees:

- ``normalize_transcript_text(normalize_transcript_text(x)) ==
  normalize_transcript_text(x)`` (idempotence);
- only whitespace is added or removed, never transcript content;
- no dependency on the source platform for correctness.
"""

from __future__ import annotations

import re
from typing import Any, Dict, Iterable, List, Optional, Sequence

# Target paragraph size. ~110 words / ~380 chars matches what Deepgram's own
# paragraph segmentation produces, so the punctuated and the fallback paths
# yield visually consistent blocks.
PARAGRAPH_TARGET_WORDS = 110
# Hard ceiling on a produced block. Any block above it is re-split, which is
# also the idempotence invariant: a normalized text contains no block longer
# than this (except the degenerate single-word case).
PARAGRAPH_MAX_CHARS = 900
# Below this size the content is a short post (X, LinkedIn): the author's own
# line breaks are meaningful, so it is returned verbatim.
SHORT_CONTENT_MAX_CHARS = 400
# Share of single-newline lines that must look like a finished sentence for the
# text to be read as already-paragraphed prose rather than caption cues.
PARAGRAPHED_LINE_RATIO = 0.6

_SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?…])\s+")
_BLANK_LINE_RE = re.compile(r"\n{2,}")
_SPEAKER_PREFIX_RE = re.compile(r"^(Speaker\s+\d+)\s*:\s*", re.IGNORECASE)
# A line that ends on sentence-terminating punctuation is a finished thought, not
# a mid-sentence caption cue wrap.
_SENTENCE_END_RE = re.compile(r"[.!?…][\"'”’)\]]*$")
# Any run of horizontal whitespace (regular space, tab, NBSP, thin space...)
# collapses to a single space. \s would also eat newlines, which carry the
# paragraph structure we are trying to preserve.
_INLINE_SPACE_RE = re.compile(r"[^\S\n]+")


def normalize_transcript_text(text: Optional[str], *, source: Optional[str] = None) -> str:
    """Turn any transcript shape into paragraph-delimited plain text.

    Args:
        text: The transcript text, in any shape (flat blob, caption cue lines,
            already-paragraphed prose).
        source: Optional platform hint. Only used for readability of call sites;
            correctness never depends on it.

    Returns:
        Plain text whose paragraphs are separated by a single blank line.
    """
    cleaned = _clean_whitespace(text)
    if not cleaned:
        return ""

    # Short content: preserve the author's own line breaks verbatim.
    if len(cleaned) <= SHORT_CONTENT_MAX_CHARS:
        return cleaned

    blocks: List[str] = []
    for block in _initial_blocks(cleaned):
        blocks.extend(_split_block(block))
    return "\n\n".join(blocks)


def group_caption_lines(lines: Iterable[str], *, source: Optional[str] = None) -> str:
    """Turn subtitle/caption cue lines into paragraph-delimited plain text.

    Cue lines carry no semantic boundary (a cue is a display unit, not a
    sentence), so they are always joined into a single stream before being
    re-split into paragraphs.
    """
    stream = " ".join(
        stripped for line in lines if (stripped := str(line or "").strip())
    )
    return normalize_transcript_text(stream, source=source)


def count_paragraphs(text: Optional[str]) -> int:
    """Number of paragraphs in a normalized transcript."""
    if not text or not text.strip():
        return 0
    return len([block for block in _BLANK_LINE_RE.split(text.strip()) if block.strip()])


def deepgram_transcript_text(
    alt: Dict[str, Any],
    utterances: Optional[Sequence[Dict[str, Any]]] = None,
) -> str:
    """Pick the best available representation of a Deepgram alternative.

    Preference order:

    1. speaker-grouped utterances, when a speaker index is present (requires
       diarization, which is off by default);
    2. ``paragraphs.paragraphs[]`` when those carry a speaker index;
    3. ``paragraphs.transcript`` — the same text Deepgram already returns with
       blank lines between paragraphs, at no extra cost;
    4. the flat ``transcript`` string, re-paragraphed by the normalizer.
    """
    if utterances and any(item.get("speaker") is not None for item in utterances if isinstance(item, dict)):
        grouped = _utterances_text(utterances)
        if grouped:
            return normalize_transcript_text(grouped, source="deepgram")

    paragraphs_obj = alt.get("paragraphs")
    paragraphs_list = paragraphs_obj.get("paragraphs") if isinstance(paragraphs_obj, dict) else None
    if isinstance(paragraphs_list, list) and any(
        item.get("speaker") is not None for item in paragraphs_list if isinstance(item, dict)
    ):
        speaker_text = _deepgram_paragraphs_text(paragraphs_list)
        if speaker_text:
            return normalize_transcript_text(speaker_text, source="deepgram")

    if isinstance(paragraphs_obj, dict):
        paragraphed = paragraphs_obj.get("transcript")
        if isinstance(paragraphed, str) and paragraphed.strip():
            return normalize_transcript_text(paragraphed, source="deepgram")

    if isinstance(paragraphs_list, list) and paragraphs_list:
        rebuilt = _deepgram_paragraphs_text(paragraphs_list)
        if rebuilt:
            return normalize_transcript_text(rebuilt, source="deepgram")

    return normalize_transcript_text(alt.get("transcript"), source="deepgram")


# ---------------------------------------------------------------------------
# Deepgram helpers
# ---------------------------------------------------------------------------


def _utterances_text(utterances: Sequence[Dict[str, Any]]) -> str:
    """Group consecutive utterances of the same speaker into one paragraph.

    Speaker labels are emitted in-band as a plain ``Speaker N: `` prefix. No
    markdown: nothing in the mobile client renders markdown, so asterisks would
    show up literally.
    """
    blocks: List[str] = []
    current_speaker: Optional[Any] = None
    current_parts: List[str] = []

    for utterance in utterances:
        if not isinstance(utterance, dict):
            continue
        text = str(utterance.get("transcript") or utterance.get("text") or "").strip()
        if not text:
            continue
        speaker = utterance.get("speaker")
        if current_parts and speaker != current_speaker:
            blocks.append(_with_speaker_prefix(current_speaker, " ".join(current_parts)))
            current_parts = []
        current_speaker = speaker
        current_parts.append(text)

    if current_parts:
        blocks.append(_with_speaker_prefix(current_speaker, " ".join(current_parts)))

    return "\n\n".join(blocks)


def _deepgram_paragraphs_text(paragraphs: Sequence[Dict[str, Any]]) -> str:
    """Rebuild text from ``paragraphs.paragraphs[]``, keeping speaker changes."""
    blocks: List[str] = []
    previous_speaker: Optional[Any] = None

    for paragraph in paragraphs:
        if not isinstance(paragraph, dict):
            continue
        sentences = paragraph.get("sentences")
        parts: List[str] = []
        if isinstance(sentences, list):
            for sentence in sentences:
                if not isinstance(sentence, dict):
                    continue
                sentence_text = str(sentence.get("text") or "").strip()
                if sentence_text:
                    parts.append(sentence_text)
        if not parts:
            continue

        speaker = paragraph.get("speaker")
        combined = " ".join(parts)
        if speaker is not None and speaker != previous_speaker:
            combined = _with_speaker_prefix(speaker, combined)
        previous_speaker = speaker
        blocks.append(combined)

    return "\n\n".join(blocks)


def _with_speaker_prefix(speaker: Optional[Any], text: str) -> str:
    if speaker is None:
        return text
    return f"Speaker {speaker}: {text}"


# ---------------------------------------------------------------------------
# Normalizer internals
# ---------------------------------------------------------------------------


def _clean_whitespace(text: Optional[str]) -> str:
    """Normalize line endings and collapse redundant whitespace."""
    if not text:
        return ""
    normalized = str(text).replace("\r\n", "\n").replace("\r", "\n")
    lines = [_INLINE_SPACE_RE.sub(" ", line).strip() for line in normalized.split("\n")]
    return _BLANK_LINE_RE.sub("\n\n", "\n".join(lines)).strip()


def _initial_blocks(cleaned: str) -> List[str]:
    """Derive the starting paragraph candidates from a cleaned text."""
    if "\n\n" in cleaned:
        # Already paragraphed (Deepgram paragraphs, articles, a previous
        # normalization pass): keep those boundaries.
        return [
            " ".join(block.split())
            for block in _BLANK_LINE_RE.split(cleaned)
            if block.strip()
        ]

    lines = [line for line in cleaned.split("\n") if line.strip()]
    if len(lines) > 1:
        # trafilatura and RSS transcripts separate paragraphs with a single
        # newline, and each of those lines ends on sentence punctuation. Caption
        # cues, on the other hand, wrap mid-sentence. Use that to tell them apart
        # rather than line length, which is not discriminating (a caption cue and
        # a one-sentence paragraph can be the same width).
        finished = sum(1 for line in lines if _SENTENCE_END_RE.search(line))
        if finished / len(lines) >= PARAGRAPHED_LINE_RATIO:
            # Already-paragraphed prose: each line is its own paragraph.
            return lines
        # Caption cues: join them into one stream before re-splitting.
        return [" ".join(lines)]

    return [cleaned]


def _split_block(block: str) -> List[str]:
    """Split an oversized block into readable paragraphs.

    Blocks at or under ``PARAGRAPH_MAX_CHARS`` are returned untouched — this is
    the idempotence gate.
    """
    if len(block) <= PARAGRAPH_MAX_CHARS:
        return [block]

    speaker_prefix, body = _pop_speaker_prefix(block)
    sentences = _split_sentences(body)
    if len(sentences) >= 2:
        chunks = _group_sentences(sentences)
    else:
        # Unpunctuated fallback: no sentence boundary exists in the text, so
        # group on a word budget. This is the case that produced a single
        # 50k-character wall of text for YouTube/TikTok auto-captions.
        chunks = _group_words(body.split())

    if speaker_prefix and chunks:
        chunks[0] = f"{speaker_prefix}{chunks[0]}"
    return chunks


def _pop_speaker_prefix(block: str) -> tuple[str, str]:
    match = _SPEAKER_PREFIX_RE.match(block)
    if not match:
        return "", block
    return f"{match.group(1)}: ", block[match.end():]


def _split_sentences(text: str) -> List[str]:
    return [part.strip() for part in _SENTENCE_SPLIT_RE.split(text) if part.strip()]


def _group_sentences(sentences: Sequence[str]) -> List[str]:
    """Group sentences into paragraphs, never breaking mid-sentence."""
    blocks: List[str] = []
    current: List[str] = []
    current_words = 0

    for sentence in sentences:
        candidate_length = len(" ".join(current + [sentence]))
        if current and candidate_length > PARAGRAPH_MAX_CHARS:
            blocks.append(" ".join(current))
            current, current_words = [], 0
        current.append(sentence)
        current_words += len(sentence.split())
        if current_words >= PARAGRAPH_TARGET_WORDS:
            blocks.append(" ".join(current))
            current, current_words = [], 0

    if current:
        blocks.append(" ".join(current))

    # A single sentence can still exceed the ceiling; fall back to a word budget
    # so the output always satisfies the idempotence invariant.
    result: List[str] = []
    for block in blocks:
        if len(block) <= PARAGRAPH_MAX_CHARS:
            result.append(block)
        else:
            result.extend(_group_words(block.split()))
    return result


def _group_words(words: Sequence[str]) -> List[str]:
    """Group words into paragraphs on a word and character budget."""
    blocks: List[str] = []
    current: List[str] = []
    current_length = 0

    for word in words:
        projected = current_length + len(word) + (1 if current else 0)
        if current and (len(current) >= PARAGRAPH_TARGET_WORDS or projected > PARAGRAPH_MAX_CHARS):
            blocks.append(" ".join(current))
            current, current_length = [], 0
            projected = len(word)
        current.append(word)
        current_length = projected

    if current:
        blocks.append(" ".join(current))
    return blocks
