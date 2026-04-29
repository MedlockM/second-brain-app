"""
Unit tests for the newsletter email parser.

Tests cover:
- HTML to text conversion
- MIME email parsing (multipart and single-part)
- Boilerplate stripping
- Edge cases (empty, too short, no content)
- Multiple sending platforms (Mailchimp, Substack, raw SMTP)
"""

import pytest

from media_summarizer.core.services.newsletter_errors import (
    NewsletterIngestionError,
    MIN_NEWSLETTER_CONTENT_LENGTH,
)
from media_summarizer.core.services.newsletter_parser import (
    NewsletterParseResult,
    html_to_text,
    parse_raw_email,
    _strip_boilerplate,
)


# ---------------------------------------------------------------------------
# html_to_text tests
# ---------------------------------------------------------------------------


class TestHtmlToText:
    def test_simple_paragraph(self):
        html = "<p>Hello world</p>"
        result = html_to_text(html)
        assert "Hello world" in result

    def test_strips_scripts_and_styles(self):
        html = """
        <html>
        <head><style>body { color: red; }</style></head>
        <body>
            <script>alert('xss')</script>
            <p>Visible content</p>
        </body>
        </html>
        """
        result = html_to_text(html)
        assert "Visible content" in result
        assert "alert" not in result
        assert "color: red" not in result

    def test_preserves_line_breaks_for_block_elements(self):
        html = "<h1>Title</h1><p>Paragraph 1</p><p>Paragraph 2</p>"
        result = html_to_text(html)
        assert "Title" in result
        assert "Paragraph 1" in result
        assert "Paragraph 2" in result
        # Block elements should cause separation
        lines = [l for l in result.split("\n") if l.strip()]
        assert len(lines) >= 3

    def test_list_items_formatted(self):
        html = "<ul><li>Item 1</li><li>Item 2</li><li>Item 3</li></ul>"
        result = html_to_text(html)
        assert "- Item 1" in result
        assert "- Item 2" in result
        assert "- Item 3" in result

    def test_html_entities_decoded(self):
        html = "<p>Hello &amp; welcome to &ldquo;the show&rdquo;</p>"
        result = html_to_text(html)
        assert "Hello & welcome" in result

    def test_nested_tags(self):
        html = "<div><p>Outer <strong>bold <em>and italic</em></strong> text</p></div>"
        result = html_to_text(html)
        assert "Outer bold and italic text" in result

    def test_empty_html(self):
        assert html_to_text("") == ""

    def test_tracking_pixel_removed(self):
        html = '<p>Content</p><img src="https://track.example.com/pixel.gif" width="1" height="1">'
        result = html_to_text(html)
        assert "Content" in result
        assert "track.example" not in result


# ---------------------------------------------------------------------------
# _strip_boilerplate tests
# ---------------------------------------------------------------------------


class TestStripBoilerplate:
    def test_removes_unsubscribe_line(self):
        text = "Main content here.\n\nClick here to unsubscribe from this list."
        result = _strip_boilerplate(text)
        assert "Main content here" in result
        assert "unsubscribe" not in result

    def test_removes_view_in_browser(self):
        text = "View this in your browser\n\nActual newsletter content starts here."
        result = _strip_boilerplate(text)
        assert "Actual newsletter content" in result
        assert "View this in your browser" not in result

    def test_removes_copyright(self):
        text = "Great article content.\n\n© 2026 Newsletter Inc. All rights reserved."
        result = _strip_boilerplate(text)
        assert "Great article content" in result
        assert "All rights reserved" not in result

    def test_preserves_main_content(self):
        text = (
            "This is a great article about technology.\n"
            "It covers many important topics.\n"
            "The conclusions are interesting."
        )
        result = _strip_boilerplate(text)
        assert result == text


# ---------------------------------------------------------------------------
# parse_raw_email tests
# ---------------------------------------------------------------------------


class TestParseRawEmail:
    def _make_simple_email(
        self,
        body: str = "Newsletter content " * 20,
        subject: str = "TLDR Newsletter #42",
        sender: str = "TLDR <newsletter@tldr.tech>",
        content_type: str = "text/plain",
    ) -> str:
        """Helper to create a simple RFC 2822 email."""
        return (
            f"From: {sender}\r\n"
            f"To: user123@ingest.example.com\r\n"
            f"Subject: {subject}\r\n"
            f"Date: Mon, 29 Apr 2026 08:00:00 +0000\r\n"
            f"Content-Type: {content_type}; charset=utf-8\r\n"
            f"\r\n"
            f"{body}"
        )

    def _make_multipart_email(
        self,
        html_body: str,
        text_body: str = "Fallback text",
        subject: str = "Morning Brew Daily",
        sender: str = "Morning Brew <crew@morningbrew.com>",
    ) -> str:
        """Helper to create a multipart MIME email."""
        boundary = "----=_Part_12345"
        return (
            f"From: {sender}\r\n"
            f"To: user456@ingest.example.com\r\n"
            f"Subject: {subject}\r\n"
            f"Date: Tue, 30 Apr 2026 07:00:00 +0000\r\n"
            f"MIME-Version: 1.0\r\n"
            f"Content-Type: multipart/alternative; boundary=\"{boundary}\"\r\n"
            f"\r\n"
            f"--{boundary}\r\n"
            f"Content-Type: text/plain; charset=utf-8\r\n"
            f"\r\n"
            f"{text_body}\r\n"
            f"--{boundary}\r\n"
            f"Content-Type: text/html; charset=utf-8\r\n"
            f"\r\n"
            f"{html_body}\r\n"
            f"--{boundary}--\r\n"
        )

    def test_empty_input_returns_error(self):
        result = parse_raw_email("")
        assert not result.success
        assert result.error == NewsletterIngestionError.EMPTY_EMAIL_BODY

    def test_none_input_returns_error(self):
        result = parse_raw_email(None)
        assert not result.success
        assert result.error == NewsletterIngestionError.EMPTY_EMAIL_BODY

    def test_simple_text_email(self):
        content = "This is the newsletter content. " * 10
        raw = self._make_simple_email(body=content)
        result = parse_raw_email(raw)
        assert result.success
        assert "newsletter content" in result.text
        assert result.subject == "TLDR Newsletter #42"
        assert result.sender_name == "TLDR"
        assert result.word_count > 0

    def test_multipart_html_email(self):
        html = "<h1>Top Stories</h1><p>" + "Important news content. " * 20 + "</p>"
        raw = self._make_multipart_email(html_body=html)
        result = parse_raw_email(raw)
        assert result.success
        assert "Top Stories" in result.text
        assert "Important news content" in result.text
        assert result.subject == "Morning Brew Daily"
        assert result.sender_name == "Morning Brew"

    def test_html_preferred_over_plaintext(self):
        html = "<p>" + "HTML version of the newsletter. " * 10 + "</p>"
        text = "Plain text version. " * 10
        raw = self._make_multipart_email(html_body=html, text_body=text)
        result = parse_raw_email(raw)
        assert result.success
        assert "HTML version" in result.text
        assert result.metadata["had_html"] is True

    def test_content_too_short(self):
        raw = self._make_simple_email(body="Short")
        result = parse_raw_email(raw)
        assert not result.success
        assert result.error == NewsletterIngestionError.CONTENT_TOO_SHORT

    def test_bytes_input(self):
        content = "Byte content newsletter. " * 10
        raw = self._make_simple_email(body=content)
        result = parse_raw_email(raw.encode("utf-8"))
        assert result.success
        assert "Byte content newsletter" in result.text

    def test_sender_without_angle_brackets(self):
        raw = self._make_simple_email(
            body="Content " * 20,
            sender="plain@example.com",
        )
        result = parse_raw_email(raw)
        assert result.success
        assert result.sender_name == ""

    def test_boilerplate_stripped_from_html(self):
        html = (
            "<h1>Newsletter</h1>"
            "<p>" + "Interesting article content here. " * 20 + "</p>"
            "<footer><p>Click here to unsubscribe from this list.</p></footer>"
        )
        raw = self._make_multipart_email(html_body=html)
        result = parse_raw_email(raw)
        assert result.success
        assert "unsubscribe" not in result.text
        assert "Interesting article content" in result.text

    def test_substack_style_email(self):
        """Simulate a Substack newsletter structure."""
        html = (
            '<div class="body markup">'
            "<h2>Weekly Digest</h2>"
            "<p>" + "Substack newsletter paragraph. " * 15 + "</p>"
            "<hr>"
            "<p>You are receiving this because you subscribed on Substack.</p>"
            "</div>"
        )
        raw = self._make_multipart_email(
            html_body=html,
            subject="The Batch - AI News",
            sender="Andrew Ng <andrew@deeplearning.ai>",
        )
        result = parse_raw_email(raw)
        assert result.success
        assert "Weekly Digest" in result.text
        assert "Substack newsletter paragraph" in result.text
        assert result.sender_name == "Andrew Ng"

    def test_mailchimp_style_email(self):
        """Simulate a Mailchimp newsletter structure."""
        html = (
            '<table><tr><td>'
            '<div class="mcnTextContent">'
            "<h3>Top Headlines</h3>"
            "<p>" + "Mailchimp formatted content line. " * 15 + "</p>"
            "</div></td></tr></table>"
            "<p>You're receiving this email because you subscribed.</p>"
            '<p><a href="#">Unsubscribe</a> | '
            '<a href="#">Update preferences</a></p>'
        )
        raw = self._make_multipart_email(
            html_body=html,
            subject="TLDR Newsletter 2026-04-29",
            sender="TLDR <dan@tldrnewsletter.com>",
        )
        result = parse_raw_email(raw)
        assert result.success
        assert "Top Headlines" in result.text
        assert "Mailchimp formatted content" in result.text
