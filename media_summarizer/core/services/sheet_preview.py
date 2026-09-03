"""Draw a first-sheet preview for an uploaded spreadsheet (task-344).

A spreadsheet is the one uploaded format nobody on this path rasterises: no
LlamaParse mode or tier returns a page image for an XLSX, and the API bills a
sheet rather than a page because a grid has no pagination model at all -- it has
no page 1 until a print layout is computed from print area, scaling and margins
(task-343 §4.2). The two ways to buy a genuine print-layout page were an 877 MB
x86_64-only LibreOffice image (§3.4) and an external conversion API with a new
provider and a new secret (§3.6), both disproportionate for the rarest of the
four formats.

So this module *draws* the sheet, from the parse output the worker already holds
(§3.7): the first table of the markdown, rendered as a header-banded grid. No new
dependency -- Pillow is already in the ``worker`` extra -- and no font package
either, since ``ImageFont.load_default(size=...)`` returns a scalable font
bundled inside Pillow while the Lambda base image ships none.

It is a preview of the data, not a photograph of a page: a chart-only sheet
renders as its underlying cells, and merged cells flatten. Best-effort like every
cover path -- a sheet whose parse carries no table returns ``None`` and the tile
keeps its media-type glyph.

The output is a 1280x720 PNG, already the 16:9 of the tile, so
``cover_capture.capture_document_page`` only has to downscale and encode it.
"""

from __future__ import annotations

import html
import logging
import re
from io import BytesIO
from typing import List, Optional

logger = logging.getLogger(__name__)

# Rendered at 2x the stored derivative (640x360) so the downscale sharpens it.
PREVIEW_WIDTH = 1280
PREVIEW_HEIGHT = 720

_PADDING = 40
_CELL_PADDING = 16
# The rows stretch to fill the canvas rather than leaving a white half under a
# short sheet, and the text grows with them, between these bounds.
_ROW_HEIGHT_MIN = 56
_ROW_HEIGHT_MAX = 96
_FONT_SIZE_MIN = 26
_FONT_SIZE_MAX = 34
# Beyond these the cells are unreadable once the tile is 112 px wide; the point
# is to show what kind of table this is, not to reproduce the sheet.
_MAX_COLUMNS = 6
_MAX_ROWS = 10
_ELLIPSIS = "..."

# The app's own palette (mobile/src/constants/theme.ts): `surface`,
# `surfaceContainerHigh` for the header band, `surfaceContainerLow` for the
# alternating rows, `textMain` for the text. The banding is what reads as a grid
# at tile size -- no rules are drawn.
_SURFACE = (255, 255, 255)
_HEADER_BAND = (235, 231, 229)
_ROW_BAND = (247, 243, 240)
_TEXT_MAIN = (43, 45, 66)

_SEPARATOR_CELL = re.compile(r"^:?-+:?$")
_HTML_TABLE = re.compile(r"<table[^>]*>(.*?)</table>", re.IGNORECASE | re.DOTALL)
_HTML_ROW = re.compile(r"<tr[^>]*>(.*?)</tr>", re.IGNORECASE | re.DOTALL)
_HTML_CELL = re.compile(r"<t[hd][^>]*>(.*?)</t[hd]>", re.IGNORECASE | re.DOTALL)
_HTML_TAG = re.compile(r"<[^>]+>")


def _parse_pipe_table(markdown: str) -> Optional[List[List[str]]]:
    """First markdown pipe table of the document, as rows of cells."""
    rows: List[List[str]] = []
    for raw_line in markdown.splitlines():
        line = raw_line.strip()
        if line.startswith("|"):
            body = line[1:]
            if body.endswith("|"):
                body = body[:-1]
            cells = [cell.strip() for cell in body.split("|")]
            if rows and all(
                not cell or _SEPARATOR_CELL.match(cell) for cell in cells
            ):
                # The `| --- | --- |` rule under the header row.
                continue
            rows.append(cells)
        elif rows:
            # The first table ends at the first line that is not part of it.
            break
    return rows or None


def _parse_html_table(markdown: str) -> Optional[List[List[str]]]:
    """First HTML table of the document, as rows of cells."""
    match = _HTML_TABLE.search(markdown)
    if not match:
        return None
    rows: List[List[str]] = []
    for row_html in _HTML_ROW.findall(match.group(1)):
        cells = [
            html.unescape(_HTML_TAG.sub(" ", cell)).strip()
            for cell in _HTML_CELL.findall(row_html)
        ]
        if any(cells):
            rows.append(cells)
    return rows or None


def _first_table(markdown: str) -> Optional[List[List[str]]]:
    """The first table of a parsed spreadsheet, whichever shape it came in.

    LlamaParse returns a markdown pipe table for ``result_type=markdown``; the
    HTML branch covers the ``<table>`` shape the same provider uses elsewhere.
    """
    return _parse_pipe_table(markdown) or _parse_html_table(markdown)


def _truncate(draw, text: str, font, max_width: float) -> str:
    """Fit one cell's text into its column, ellipsised."""
    collapsed = " ".join(text.split())
    if not collapsed:
        return ""
    if draw.textlength(collapsed, font=font) <= max_width:
        return collapsed
    while collapsed and draw.textlength(
        collapsed + _ELLIPSIS, font=font
    ) > max_width:
        collapsed = collapsed[:-1]
    return f"{collapsed}{_ELLIPSIS}" if collapsed else ""


def render_first_sheet_preview(markdown: str) -> Optional[bytes]:
    """Draw the first sheet of a parsed spreadsheet as a PNG. ``None`` if it cannot.

    Returns the raw PNG bytes of a ``PREVIEW_WIDTH`` x ``PREVIEW_HEIGHT`` canvas,
    left to ``cover_capture`` to frame, downscale and encode as the stored JPEG.
    """
    if not markdown or not markdown.strip():
        return None

    try:
        from PIL import Image, ImageDraw, ImageFont
    except ImportError:
        logger.warning("Pillow is not installed in this image; sheet preview skipped")
        return None

    try:
        rows = _first_table(markdown)
        if not rows:
            logger.info("Parsed spreadsheet carries no table; sheet preview skipped")
            return None

        visible = rows[: _MAX_ROWS + 1]
        columns = min(_MAX_COLUMNS, max(len(row) for row in visible))
        if columns < 1:
            return None

        available = PREVIEW_HEIGHT - 2 * _PADDING
        row_height = min(
            _ROW_HEIGHT_MAX, max(_ROW_HEIGHT_MIN, available / len(visible))
        )
        visible = visible[: max(1, int(available // row_height))]
        body_size = int(min(_FONT_SIZE_MAX, max(_FONT_SIZE_MIN, row_height * 0.42)))

        image = Image.new("RGB", (PREVIEW_WIDTH, PREVIEW_HEIGHT), _SURFACE)
        draw = ImageDraw.Draw(image)
        header_font = ImageFont.load_default(size=body_size + 2)
        body_font = ImageFont.load_default(size=body_size)

        grid_width = PREVIEW_WIDTH - 2 * _PADDING
        column_width = grid_width / columns
        text_width = column_width - 2 * _CELL_PADDING

        # The block is centred vertically: this canvas *is* 16:9, so nothing is
        # cropped out of it later and there is no top band to align to.
        y = (PREVIEW_HEIGHT - row_height * len(visible)) / 2
        for index, row in enumerate(visible):
            is_header = index == 0
            if is_header:
                band = _HEADER_BAND
            elif index % 2 == 0:
                band = _ROW_BAND
            else:
                band = _SURFACE
            if band != _SURFACE:
                draw.rectangle(
                    [(_PADDING, y), (PREVIEW_WIDTH - _PADDING, y + row_height)],
                    fill=band,
                )

            font = header_font if is_header else body_font
            for column in range(columns):
                cell = row[column] if column < len(row) else ""
                label = _truncate(draw, cell, font, text_width)
                if not label:
                    continue
                draw.text(
                    (
                        _PADDING + column * column_width + _CELL_PADDING,
                        y + row_height / 2,
                    ),
                    label,
                    font=font,
                    fill=_TEXT_MAIN,
                    anchor="lm",
                )
            y += row_height

        buffer = BytesIO()
        image.save(buffer, format="PNG", optimize=True)
        return buffer.getvalue()
    except Exception as exc:  # noqa: BLE001 - a cover never fails an ingestion
        logger.warning("Sheet preview could not be drawn: %s", exc)
        return None
