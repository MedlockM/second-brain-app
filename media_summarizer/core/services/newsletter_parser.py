"""
Newsletter email parser.

Parses raw MIME email content and extracts clean text suitable for the
summarization pipeline. Works independently of the sending platform
(Mailchimp, Substack, direct SMTP, etc.).

Design decisions:
- Uses only stdlib (email, html.parser) -- no third-party dependency
- Aggressive stripping of boilerplate (unsubscribe, tracking pixels, nav)
- Returns structured result with metadata (subject, sender, extracted text)
"""

from __future__ import annotations

import email
import email.policy
import html
import re
from dataclasses import dataclass, field
from email.message import EmailMessage
from html.parser import HTMLParser
from typing import Optional

from media_summarizer.core.services.newsletter_errors import (
    MIN_NEWSLETTER_CONTENT_LENGTH,
    NewsletterIngestionError,
)


@dataclass
class NewsletterParseResult:
    """Result of parsing a newsletter email."""

    success: bool
    text: str = ""
    subject: str = ""
    sender: str = ""
    sender_name: str = ""
    date: str = ""
    error: Optional[NewsletterIngestionError] = None
    word_count: int = 0
    metadata: dict = field(default_factory=dict)


# ---------------------------------------------------------------------------
# HTML to text converter (stdlib-only, no external deps)
# ---------------------------------------------------------------------------

# Tags whose content should be entirely removed
_REMOVE_CONTENT_TAGS = frozenset([
    "script", "style", "head", "title", "meta", "link", "noscript",
    "template", "svg", "iframe",
])

# Block-level tags that produce a newline break
_BLOCK_TAGS = frozenset([
    "p", "div", "br", "h1", "h2", "h3", "h4", "h5", "h6",
    "li", "tr", "blockquote", "article", "section", "header", "footer",
    "table", "thead", "tbody", "tfoot", "hr", "pre", "dd", "dt",
])

# Patterns indicating boilerplate content (case-insensitive)
_BOILERPLATE_PATTERNS = [
    re.compile(r"unsubscribe", re.IGNORECASE),
    re.compile(r"view\s+(this\s+)?in\s+(your\s+)?browser", re.IGNORECASE),
    re.compile(r"manage\s+(your\s+)?preferences", re.IGNORECASE),
    re.compile(r"update\s+(your\s+)?subscription", re.IGNORECASE),
    re.compile(r"sent\s+to\s+\S+@\S+", re.IGNORECASE),
    re.compile(r"you('re|\s+are)\s+receiving\s+this", re.IGNORECASE),
    re.compile(r"click\s+here\s+to\s+unsubscribe", re.IGNORECASE),
    re.compile(r"no\s+longer\s+wish\s+to\s+receive", re.IGNORECASE),
    re.compile(r"©\s*\d{4}", re.IGNORECASE),  # copyright
    re.compile(r"all\s+rights\s+reserved", re.IGNORECASE),
    re.compile(r"privacy\s+policy", re.IGNORECASE),
    re.compile(r"terms\s+of\s+(service|use)", re.IGNORECASE),
]


class _HTMLToTextParser(HTMLParser):
    """Custom HTML parser that converts HTML to clean text."""

    def __init__(self):
        super().__init__()
        self._result: list[str] = []
        self._skip_depth = 0
        self._current_tag_stack: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, Optional[str]]]):
        tag_lower = tag.lower()
        self._current_tag_stack.append(tag_lower)

        if tag_lower in _REMOVE_CONTENT_TAGS:
            self._skip_depth += 1
            return

        if self._skip_depth > 0:
            return

        if tag_lower in _BLOCK_TAGS:
            self._result.append("\n")

        if tag_lower == "br":
            self._result.append("\n")
        elif tag_lower == "li":
            self._result.append("\n- ")
        elif tag_lower == "a":
            # Keep link text, skip the URL
            pass

    def handle_endtag(self, tag: str):
        tag_lower = tag.lower()

        if tag_lower in _REMOVE_CONTENT_TAGS:
            self._skip_depth = max(0, self._skip_depth - 1)

        if self._current_tag_stack and self._current_tag_stack[-1] == tag_lower:
            self._current_tag_stack.pop()

        if self._skip_depth > 0:
            return

        if tag_lower in _BLOCK_TAGS:
            self._result.append("\n")

    def handle_data(self, data: str):
        if self._skip_depth > 0:
            return
        self._result.append(data)

    def get_text(self) -> str:
        return "".join(self._result)


def html_to_text(html_content: str) -> str:
    """Convert HTML to clean plain text.

    Strips scripts, styles, navigation elements and converts block-level
    elements to newline-separated text.
    """
    parser = _HTMLToTextParser()
    parser.feed(html_content)
    raw_text = parser.get_text()

    # Decode any remaining HTML entities
    raw_text = html.unescape(raw_text)

    # Normalize whitespace
    # Collapse multiple spaces on same line
    raw_text = re.sub(r"[^\S\n]+", " ", raw_text)
    # Collapse multiple newlines to max 2
    raw_text = re.sub(r"\n{3,}", "\n\n", raw_text)
    # Strip leading/trailing whitespace per line
    lines = [line.strip() for line in raw_text.split("\n")]
    raw_text = "\n".join(lines)

    return raw_text.strip()


def _strip_boilerplate(text: str) -> str:
    """Remove common newsletter boilerplate lines (footer, unsubscribe, etc.)."""
    lines = text.split("\n")
    filtered_lines: list[str] = []
    # Track if we're in a trailing boilerplate section
    boilerplate_streak = 0

    for line in lines:
        is_boilerplate = any(pattern.search(line) for pattern in _BOILERPLATE_PATTERNS)
        if is_boilerplate:
            boilerplate_streak += 1
            # If a single boilerplate line in the middle, still remove it
            continue
        else:
            boilerplate_streak = 0
            filtered_lines.append(line)

    return "\n".join(filtered_lines).strip()


# ---------------------------------------------------------------------------
# MIME email parsing
# ---------------------------------------------------------------------------


def parse_raw_email(raw_email: str | bytes) -> NewsletterParseResult:
    """Parse a raw MIME email and extract the newsletter content.

    Handles multipart emails, preferring HTML (which is then converted to text)
    over plain text parts, since newsletters are almost always HTML-formatted.

    Args:
        raw_email: Raw RFC 2822 email content (str or bytes).

    Returns:
        NewsletterParseResult with extracted content or error information.
    """
    if not raw_email:
        return NewsletterParseResult(
            success=False,
            error=NewsletterIngestionError.EMPTY_EMAIL_BODY,
        )

    try:
        if isinstance(raw_email, bytes):
            msg: EmailMessage = email.message_from_bytes(
                raw_email, policy=email.policy.default
            )
        else:
            msg: EmailMessage = email.message_from_string(
                raw_email, policy=email.policy.default
            )
    except Exception:
        return NewsletterParseResult(
            success=False,
            error=NewsletterIngestionError.INVALID_MIME_FORMAT,
        )

    # Extract metadata
    subject = str(msg.get("Subject", "")) or ""
    sender = str(msg.get("From", "")) or ""
    date = str(msg.get("Date", "")) or ""

    # Parse sender name from "Name <email>" format
    sender_name = ""
    if "<" in sender:
        sender_name = sender.split("<")[0].strip().strip('"').strip("'")

    # Extract body: prefer HTML over plain text
    html_body: Optional[str] = None
    text_body: Optional[str] = None

    if msg.is_multipart():
        for part in msg.walk():
            content_type = part.get_content_type()
            # Skip attachments
            content_disposition = str(part.get("Content-Disposition", ""))
            if "attachment" in content_disposition:
                continue

            try:
                payload = part.get_content()
            except Exception:
                continue

            if not isinstance(payload, str):
                continue

            if content_type == "text/html" and not html_body:
                html_body = payload
            elif content_type == "text/plain" and not text_body:
                text_body = payload
    else:
        content_type = msg.get_content_type()
        try:
            payload = msg.get_content()
        except Exception:
            payload = None

        if isinstance(payload, str):
            if content_type == "text/html":
                html_body = payload
            elif content_type == "text/plain":
                text_body = payload

    # Convert to clean text
    extracted_text = ""
    if html_body:
        extracted_text = html_to_text(html_body)
    elif text_body:
        extracted_text = text_body.strip()

    if not extracted_text:
        return NewsletterParseResult(
            success=False,
            subject=subject,
            sender=sender,
            sender_name=sender_name,
            date=date,
            error=NewsletterIngestionError.NO_TEXT_CONTENT,
        )

    # Strip boilerplate
    cleaned_text = _strip_boilerplate(extracted_text)

    if len(cleaned_text) < MIN_NEWSLETTER_CONTENT_LENGTH:
        return NewsletterParseResult(
            success=False,
            text=cleaned_text,
            subject=subject,
            sender=sender,
            sender_name=sender_name,
            date=date,
            error=NewsletterIngestionError.CONTENT_TOO_SHORT,
            word_count=len(cleaned_text.split()),
        )

    word_count = len(cleaned_text.split())

    return NewsletterParseResult(
        success=True,
        text=cleaned_text,
        subject=subject,
        sender=sender,
        sender_name=sender_name,
        date=date,
        word_count=word_count,
        metadata={
            "had_html": html_body is not None,
            "had_plaintext": text_body is not None,
            "original_html_length": len(html_body) if html_body else 0,
            "cleaned_text_length": len(cleaned_text),
        },
    )
