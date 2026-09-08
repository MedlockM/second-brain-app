"""Plain-text resolver -- the parser for files that are already their own text.

A `.txt`, a `.md` and a `.rtf` are the three formats on the document path that
need no provider at all (task-380): the bytes *are* the content, so sending them
to LlamaParse would spend a page of a paid pool to be handed back what we already
had, and would make a note exported from Apple Notes or Google Keep depend on a
third party being up.

So this adapter implements `DocumentParserPort` without a network call:

- **decode**, trying the encodings a note-taking app really writes (a BOM'd
  UTF-8 from Windows, UTF-16 from a Samsung Notes export, then Latin-1/cp1252 for
  an old file), and never raising -- a byte that decodes nowhere is replaced
  rather than failing an import;
- **de-RTF**, for the one of the three formats that is markup: control words,
  groups and the two escape forms, stripped deterministically. No RTF library is
  added for it -- what an exported note contains is text, paragraph breaks and
  the odd accented character, all of which the rules below cover.

`page_count` is `0` on purpose and is not a missing value: a text file has no
pages, and the worker reads that zero to charge nothing rather than inventing the
single page every other format has (see `quota_enforcer.record_text_file_parse`).
"""

from __future__ import annotations

import logging
import os
import re

from media_summarizer.core.ports.document_parser import (
    TEXT_FORMATS,
    DocumentFormat,
    DocumentParserPort,
    ParseError,
    ParseErrorCode,
    ParseResult,
)

logger = logging.getLogger(__name__)

#: Tried in order. `utf-8-sig` first so a BOM is consumed instead of becoming a
#: zero-width character at the head of the title; `utf-16` reads either byte
#: order from its BOM; `cp1252` is the last *strict* attempt, and decodes any
#: byte sequence, which is why it is also the end of the list.
_ENCODINGS: tuple[str, ...] = ("utf-8-sig", "utf-16", "cp1252")

#: `{\*\destination ...}` -- an RTF group flagged as ignorable, plus the named
#: destinations whose payload is never document text (tables of fonts and
#: colours, the document properties, an embedded picture's hex data).
_RTF_SKIPPED_DESTINATIONS: frozenset[str] = frozenset(
    {
        "fonttbl",
        "colortbl",
        "stylesheet",
        "listtable",
        "listoverridetable",
        "info",
        "pict",
        "object",
        "themedata",
        "colorschememapping",
        "latentstyles",
        "datastore",
        "generator",
    }
)

#: An RTF control word: a backslash, letters, an optional signed numeric
#: parameter, and an optional single space that belongs to the word rather than
#: to the text.
_RTF_CONTROL_WORD = re.compile(r"\\([a-zA-Z]+)(-?\d+)? ?")
#: `\'e9` -- one byte written as hex, the pre-Unicode way of spelling "é".
_RTF_HEX_ESCAPE = re.compile(r"\\'([0-9a-fA-F]{2})")
#: `\u233?` -- a code point with its replacement character for old readers.
_RTF_UNICODE_ESCAPE = re.compile(r"\\u(-?\d+)\??")
#: Three or more blank lines say nothing a single blank line does not.
_EXCESS_BLANK_LINES = re.compile(r"\n{3,}")


def decode_text_bytes(raw: bytes) -> str:
    """Bytes as text, trying the encodings in `_ENCODINGS` and always answering.

    The last resort replaces undecodable bytes: a note whose encoding nobody can
    name still reads, and the alternative -- refusing the import -- would be a
    dead end over a single character.
    """
    for encoding in _ENCODINGS:
        try:
            return raw.decode(encoding)
        except (UnicodeDecodeError, LookupError):
            continue
    return raw.decode("utf-8", errors="replace")


def _rtf_control_word_to_text(word: str, parameter: str | None) -> str:
    """What a control word contributes to the text, which is usually nothing."""
    if word in ("par", "line", "sect"):
        return "\n"
    if word == "tab":
        return "\t"
    # `\pard` resets paragraph formatting and in practice separates blocks.
    if word == "pard":
        return "\n"
    if word in ("emdash", "endash"):
        return "-"
    if word in ("lquote", "rquote"):
        return "'"
    if word in ("ldblquote", "rdblquote"):
        return '"'
    if word == "bullet":
        return "-"
    if word == "u" and parameter is not None:
        try:
            code_point = int(parameter)
        except ValueError:
            return ""
        # RTF writes a code point above 32767 as its negative complement.
        if code_point < 0:
            code_point += 65536
        return chr(code_point) if 0 < code_point < 0x110000 else ""
    return ""


def rtf_to_text(rtf: str) -> str:
    """The readable text of an RTF document, without an RTF library.

    A single pass over the string, tracking group depth so an ignorable
    destination can be skipped whole. Deliberately lossy about formatting: bold
    and colour carry no meaning once the text is a transcript, and the only
    structure worth keeping is the paragraph break.
    """
    out: list[str] = []
    depth = 0
    #: Depth at which the current skip started, or `None` when not skipping.
    skip_from: int | None = None
    index = 0
    length = len(rtf)

    while index < length:
        char = rtf[index]

        if char == "{":
            depth += 1
            index += 1
            # `{\*\foo` -- ignorable destination, whatever `foo` is.
            if rtf.startswith("\\*", index):
                if skip_from is None:
                    skip_from = depth
                index += 2
            continue

        if char == "}":
            if skip_from is not None and depth <= skip_from:
                skip_from = None
            depth -= 1
            index += 1
            continue

        if char == "\\":
            # An escaped literal: `\\`, `\{`, `\}`.
            if index + 1 < length and rtf[index + 1] in "\\{}":
                if skip_from is None:
                    out.append(rtf[index + 1])
                index += 2
                continue

            hex_match = _RTF_HEX_ESCAPE.match(rtf, index)
            if hex_match:
                if skip_from is None:
                    out.append(
                        bytes([int(hex_match.group(1), 16)]).decode(
                            "cp1252", errors="replace"
                        )
                    )
                index = hex_match.end()
                continue

            unicode_match = _RTF_UNICODE_ESCAPE.match(rtf, index)
            if unicode_match:
                if skip_from is None:
                    out.append(_rtf_control_word_to_text("u", unicode_match.group(1)))
                index = unicode_match.end()
                continue

            word_match = _RTF_CONTROL_WORD.match(rtf, index)
            if word_match:
                word = word_match.group(1)
                if word in _RTF_SKIPPED_DESTINATIONS and skip_from is None:
                    skip_from = depth
                elif skip_from is None:
                    out.append(_rtf_control_word_to_text(word, word_match.group(2)))
                index = word_match.end()
                continue

            # A lone backslash before something that is not a control word.
            index += 1
            continue

        if char in ("\r", "\n"):
            # Raw line breaks in the source are formatting of the RTF file
            # itself; `\par` is what a paragraph break is written with.
            index += 1
            continue

        if skip_from is None:
            out.append(char)
        index += 1

    return "".join(out)


def normalize_plain_text(text: str) -> str:
    """Line endings unified, trailing spaces dropped, blank runs collapsed.

    Newlines are *kept*: the first line of a note is what its title is derived
    from, and its paragraphs are what makes it readable.
    """
    unified = text.replace("\r\n", "\n").replace("\r", "\n").replace("\x00", "")
    lines = [line.rstrip() for line in unified.split("\n")]
    return _EXCESS_BLANK_LINES.sub("\n\n", "\n".join(lines)).strip()


class PlainTextResolver(DocumentParserPort):
    """Adapter for the text formats: reads the file, decodes it, done."""

    @property
    def provider_name(self) -> str:
        return "plain_text"

    def supports_format(self, document_format: DocumentFormat) -> bool:
        return document_format in TEXT_FORMATS

    async def parse(
        self,
        file_path: str,
        file_name: str,
        document_format: DocumentFormat,
    ) -> ParseResult | ParseError:
        """Decode the file into markdown, or say why there is nothing to read."""
        if not self.supports_format(document_format):
            return ParseError(
                code=ParseErrorCode.UNSUPPORTED_FORMAT,
                message=f"{document_format.value} is not a text format",
                provider=self.provider_name,
                retryable=False,
            )

        try:
            with open(file_path, "rb") as handle:
                raw = handle.read()
        except OSError as exc:
            return ParseError(
                code=ParseErrorCode.INVALID_FILE,
                message=f"Could not read the text file: {exc}",
                provider=self.provider_name,
                retryable=False,
            )

        decoded = decode_text_bytes(raw)
        if document_format == DocumentFormat.TEXT_RTF:
            decoded = rtf_to_text(decoded)
        content = normalize_plain_text(decoded)

        if not content:
            # An empty note, or an RTF holding only formatting. The worker turns
            # this into the same `DOCUMENT_PARSE_FAILED` a blank scan produces,
            # which the client already words as "This document could not be
            # read. Try another file or another format."
            return ParseError(
                code=ParseErrorCode.EMPTY_RESULT,
                message="The text file holds no readable text",
                provider=self.provider_name,
                retryable=False,
            )

        return ParseResult(
            markdown_content=content,
            # No pages: this is what the quota path reads to charge nothing.
            page_count=0,
            metadata={
                "source": "plain_text",
                "document_format": document_format.value,
                "byte_size": os.path.getsize(file_path)
                if os.path.exists(file_path)
                else len(raw),
                "character_count": len(content),
            },
            provider=self.provider_name,
        )
