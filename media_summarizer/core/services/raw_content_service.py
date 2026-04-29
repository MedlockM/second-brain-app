"""
Service for retrieving and formatting raw content from media items.

Raw content is the source material (transcript, extracted text, OCR result)
stored in S3 under the processing job's transcription_s3_key.
This service downloads that content and formats it into readable text.
"""

from __future__ import annotations

import json
import logging
import os
import re
from typing import Optional

from media_summarizer.core.models import ProcessingJob
from media_summarizer.utils import s3

logger = logging.getLogger(__name__)

TRANSCRIPT_BUCKET = os.environ.get(
    "TRANSCRIPT_BUCKET", "media-summarizer-transcriptions"
)


class RawContentNotAvailableError(Exception):
    """Raised when raw content is not yet available for a media item."""

    pass


class RawContentResponse:
    """Structured response for raw content retrieval."""

    def __init__(
        self,
        content: str,
        content_type: str,
        media_type: Optional[str] = None,
        source_format: Optional[str] = None,
    ):
        self.content = content
        self.content_type = content_type
        self.media_type = media_type
        self.source_format = source_format


async def get_raw_content(job: ProcessingJob) -> RawContentResponse:
    """
    Retrieve and format the raw content for a media item.

    Downloads the transcript/text from S3 and formats it into readable text.
    The source format depends on the media type:
    - Audio/Video/Podcast: transcript (Deepgram JSON or plain text)
    - Articles: extracted text (plain text from trafilatura)
    - Social posts: raw text content
    - Images/PDFs: OCR result

    Args:
        job: The ProcessingJob containing the S3 key reference.

    Returns:
        RawContentResponse with formatted content.

    Raises:
        RawContentNotAvailableError: If the content is not yet available.
    """
    transcript_s3_key = (getattr(job, "transcription_s3_key", None) or "").strip()
    if not transcript_s3_key:
        raise RawContentNotAvailableError(
            "Raw content is not yet available for this media item."
        )

    try:
        raw_bytes = await s3.download_file_to_memory(
            bucket=TRANSCRIPT_BUCKET,
            key=transcript_s3_key,
        )
    except Exception as exc:
        logger.error(
            "Failed to download raw content from S3 for key %s: %s",
            transcript_s3_key,
            exc,
        )
        raise RawContentNotAvailableError(
            "Raw content could not be retrieved."
        ) from exc

    if not raw_bytes or not raw_bytes.strip():
        raise RawContentNotAvailableError(
            "Raw content is empty for this media item."
        )

    raw_text = raw_bytes.decode("utf-8")
    media_type = getattr(job, "media_type", None) or ""
    source_platform = getattr(job, "source_platform", None) or ""

    # Determine source format and format accordingly
    source_format = _detect_source_format(raw_text, media_type, source_platform)
    formatted_content = _format_content(raw_text, source_format)

    return RawContentResponse(
        content=formatted_content,
        content_type="text/plain",
        media_type=media_type or None,
        source_format=source_format,
    )


def _detect_source_format(
    raw_text: str, media_type: str, source_platform: str
) -> str:
    """
    Detect the source format of the raw content.

    Returns one of: "deepgram_json", "plain_text", "article_text", "social_post", "ocr"
    """
    # Try to detect Deepgram JSON format
    if raw_text.strip().startswith("{") or raw_text.strip().startswith("["):
        try:
            data = json.loads(raw_text)
            if isinstance(data, dict):
                # Deepgram response has "results" or "channels" keys
                if "results" in data or "channels" in data:
                    return "deepgram_json"
                # Some other JSON transcript format (e.g., Whisper segments)
                if "segments" in data or "text" in data:
                    return "whisper_json"
            return "json_transcript"
        except (json.JSONDecodeError, ValueError):
            pass

    # Classify by media type and platform
    if media_type in ("article",) or source_platform in ("web",):
        return "article_text"
    if source_platform in ("twitter", "linkedin"):
        return "social_post"
    if media_type in ("image", "pdf") or source_platform in ("ocr",):
        return "ocr"

    return "plain_text"


def _format_content(raw_text: str, source_format: str) -> str:
    """Format raw content based on its source format."""
    if source_format == "deepgram_json":
        return _format_deepgram_transcript(raw_text)
    if source_format == "whisper_json":
        return _format_whisper_transcript(raw_text)
    if source_format == "json_transcript":
        return _format_json_transcript(raw_text)
    if source_format == "article_text":
        return _format_article_text(raw_text)
    if source_format == "social_post":
        return _format_social_post(raw_text)
    # For "plain_text" and "ocr", just clean up whitespace
    return _format_plain_text(raw_text)


def _format_deepgram_transcript(raw_text: str) -> str:
    """
    Format a Deepgram JSON transcript into readable paragraphed text.

    Deepgram responses can have different structures:
    - results.channels[0].alternatives[0].paragraphs.paragraphs (with speaker info)
    - results.channels[0].alternatives[0].transcript (flat text)
    - results.utterances (with speaker labels)
    """
    try:
        data = json.loads(raw_text)
    except (json.JSONDecodeError, ValueError):
        return _format_plain_text(raw_text)

    # Try utterances first (most structured, with speakers)
    utterances = data.get("results", {}).get("utterances") or data.get("utterances")
    if utterances and isinstance(utterances, list):
        return _format_utterances(utterances)

    # Try paragraphs structure
    results = data.get("results", data)
    channels = results.get("channels", [])
    if channels and isinstance(channels, list):
        alt = channels[0].get("alternatives", [{}])[0] if channels[0].get("alternatives") else {}

        # Check for paragraphs with speaker info
        paragraphs_obj = alt.get("paragraphs", {})
        if isinstance(paragraphs_obj, dict):
            paragraphs_list = paragraphs_obj.get("paragraphs", [])
            if paragraphs_list:
                return _format_deepgram_paragraphs(paragraphs_list)

        # Fall back to flat transcript text
        transcript = alt.get("transcript", "")
        if transcript:
            return _format_plain_text(transcript)

    # Last resort: look for a top-level "transcript" field
    transcript = data.get("transcript", "")
    if transcript:
        return _format_plain_text(transcript)

    return _format_plain_text(raw_text)


def _format_utterances(utterances: list) -> str:
    """Format Deepgram utterances with speaker labels."""
    paragraphs = []
    current_speaker = None
    current_lines = []

    for utterance in utterances:
        speaker = utterance.get("speaker")
        text = (utterance.get("transcript") or utterance.get("text", "")).strip()
        if not text:
            continue

        speaker_label = f"Speaker {speaker}" if speaker is not None else None

        if speaker_label != current_speaker:
            if current_lines:
                prefix = f"**{current_speaker}:** " if current_speaker else ""
                paragraphs.append(prefix + " ".join(current_lines))
            current_speaker = speaker_label
            current_lines = [text]
        else:
            current_lines.append(text)

    # Flush remaining
    if current_lines:
        prefix = f"**{current_speaker}:** " if current_speaker else ""
        paragraphs.append(prefix + " ".join(current_lines))

    return "\n\n".join(paragraphs)


def _format_deepgram_paragraphs(paragraphs: list) -> str:
    """Format Deepgram paragraphs structure with optional speaker labels."""
    output_paragraphs = []

    for para in paragraphs:
        speaker = para.get("speaker")
        sentences = para.get("sentences", [])
        if not sentences:
            continue

        text_parts = []
        for sentence in sentences:
            sentence_text = (sentence.get("text") or "").strip()
            if sentence_text:
                text_parts.append(sentence_text)

        if not text_parts:
            continue

        combined = " ".join(text_parts)
        if speaker is not None:
            output_paragraphs.append(f"**Speaker {speaker}:** {combined}")
        else:
            output_paragraphs.append(combined)

    return "\n\n".join(output_paragraphs)


def _format_whisper_transcript(raw_text: str) -> str:
    """Format a Whisper JSON transcript into readable text."""
    try:
        data = json.loads(raw_text)
    except (json.JSONDecodeError, ValueError):
        return _format_plain_text(raw_text)

    # Whisper format: {"text": "...", "segments": [...]}
    text = data.get("text", "")
    if text:
        return _format_plain_text(text)

    # Try to assemble from segments
    segments = data.get("segments", [])
    if segments:
        texts = []
        for seg in segments:
            seg_text = (seg.get("text") or "").strip()
            if seg_text:
                texts.append(seg_text)
        if texts:
            return _format_plain_text(" ".join(texts))

    return _format_plain_text(raw_text)


def _format_json_transcript(raw_text: str) -> str:
    """Format a generic JSON transcript."""
    try:
        data = json.loads(raw_text)
    except (json.JSONDecodeError, ValueError):
        return _format_plain_text(raw_text)

    # Try common keys
    if isinstance(data, dict):
        for key in ("text", "transcript", "content", "body"):
            if key in data and isinstance(data[key], str):
                return _format_plain_text(data[key])

    # If it's a list of objects with text
    if isinstance(data, list):
        texts = []
        for item in data:
            if isinstance(item, dict):
                text = item.get("text") or item.get("transcript") or ""
                if text.strip():
                    texts.append(text.strip())
            elif isinstance(item, str):
                texts.append(item.strip())
        if texts:
            return "\n\n".join(texts)

    return _format_plain_text(raw_text)


def _format_article_text(raw_text: str) -> str:
    """Format extracted article text, preserving paragraph structure."""
    # Article text from trafilatura is typically already paragraphed
    # Just clean up excessive whitespace while preserving paragraph breaks
    lines = raw_text.split("\n")
    paragraphs = []
    current_paragraph = []

    for line in lines:
        stripped = line.strip()
        if not stripped:
            if current_paragraph:
                paragraphs.append(" ".join(current_paragraph))
                current_paragraph = []
        else:
            current_paragraph.append(stripped)

    if current_paragraph:
        paragraphs.append(" ".join(current_paragraph))

    return "\n\n".join(paragraphs)


def _format_social_post(raw_text: str) -> str:
    """Format social media post text. Preserve original formatting mostly."""
    # Social posts are typically short; preserve line breaks as they are intentional
    return raw_text.strip()


def _format_plain_text(raw_text: str) -> str:
    """
    Format plain text transcripts into readable paragraphs.

    Splits long continuous text into paragraphs at sentence boundaries
    approximately every 3-5 sentences for readability.
    """
    text = raw_text.strip()

    # If text already has paragraph breaks, respect them
    if "\n\n" in text:
        paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
        return "\n\n".join(paragraphs)

    # If text has single line breaks that look like paragraph separators
    if "\n" in text:
        lines = [l.strip() for l in text.split("\n") if l.strip()]
        # If lines are relatively long (> 80 chars average), treat them as paragraphs
        avg_len = sum(len(l) for l in lines) / max(len(lines), 1)
        if avg_len > 80:
            return "\n\n".join(lines)
        # Otherwise join them and split into paragraphs
        text = " ".join(lines)

    # Split long continuous text into paragraphs at sentence boundaries
    sentences = _split_sentences(text)
    if len(sentences) <= 5:
        return text

    paragraphs = []
    current = []
    for i, sentence in enumerate(sentences):
        current.append(sentence)
        # Create a paragraph every 4-6 sentences
        if len(current) >= 5 or (len(current) >= 3 and i == len(sentences) - 1):
            paragraphs.append(" ".join(current))
            current = []

    if current:
        paragraphs.append(" ".join(current))

    return "\n\n".join(paragraphs)


def _split_sentences(text: str) -> list:
    """Split text into sentences using basic heuristics."""
    # Split on sentence-ending punctuation followed by space and uppercase
    # or just on period/question/exclamation followed by space
    parts = re.split(r'(?<=[.!?])\s+', text)
    return [p for p in parts if p.strip()]
