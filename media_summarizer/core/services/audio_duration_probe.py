"""
Audio duration probing without an ffmpeg dependency (task-250 Layer 1).

The quota gate needs the duration of an audio file *before* paying Deepgram for
it. Two shapes are needed:

- `probe_duration_seconds_from_bytes`: the whole file is already in memory
  (direct upload, WhatsApp share).
- `probe_duration_seconds_from_url`: only a remote URL is known (podcast
  enclosure, direct audio URL, RSS item). Three short HTTP Range requests at
  most, under a hard time budget.

Both read the container metadata directly:

- MPEG audio (MP3): ID3v2 tag length, then the first frame header plus the
  `Xing`/`Info`/`VBRI` frame count; falls back to CBR bitrate x byte length. When
  the ID3v2 tag is larger than the head window — embedded cover art of several
  hundred kB is routine on podcast CDNs — the tag header gives the exact offset
  of the first audio frame, so one extra Range request lands on it.
- MP4/M4A/AAC: box walking down to `moov` > `mvhd` (timescale + duration). The
  walk works even when `moov` sits at the end of the file: box headers give the
  exact offset, so a single extra Range request lands on it.
- Ogg (Opus/Vorbis): granule position of the last page, from a tail Range.
- WAV: `fmt ` byte rate and `data` chunk size.
- FLAC: STREAMINFO total samples and sample rate.

Every entry point returns `None` rather than raising when the duration cannot be
established: per the owner's decision on task-250, a metadata failure must never
refuse a legitimate submission. The caller debits a provisional minute and the
Deepgram settlement (Layer 2) corrects the counter with the real duration.
"""

from __future__ import annotations

import logging
import struct
import time
from math import ceil
from typing import NamedTuple, Optional, Tuple

import httpx

from media_summarizer.utils.logging_config import log_event

logger = logging.getLogger(__name__)

# Total wall-clock budget for a remote probe, per the task-250 decision.
DEFAULT_PROBE_BUDGET_SECONDS = 5.0

# Head window: enough for ID3v2 tags, a WAV/FLAC header, an Ogg first page and
# the top-level box headers of an MP4.
_HEAD_WINDOW_BYTES = 96 * 1024
# Tail window for Ogg granule position lookup.
_TAIL_WINDOW_BYTES = 64 * 1024
# Window fetched at an offset the head told us to jump to: an `moov` box after
# `mdat`, or the first audio frame after an oversized ID3v2 tag.
_JUMP_WINDOW_BYTES = 96 * 1024
# Upper sanity bound: 24 h. Anything above is a parse artefact, not a podcast.
_MAX_PLAUSIBLE_DURATION_SECONDS = 24 * 3600

# --- MPEG audio tables -------------------------------------------------------

# [version_index][bitrate_index] in kbit/s. version_index: 0 = MPEG1,
# 1 = MPEG2/2.5. Layer III/II share a table row set per version.
_MPEG_BITRATES = {
    # (version, layer) -> bitrate table
    (3, 3): [0, 32, 64, 96, 128, 160, 192, 224, 256, 288, 320, 352, 384, 416, 448, 0],
    (3, 2): [0, 32, 48, 56, 64, 80, 96, 112, 128, 160, 192, 224, 256, 320, 384, 0],
    (3, 1): [0, 32, 40, 48, 56, 64, 80, 96, 112, 128, 160, 192, 224, 256, 320, 0],
    (2, 3): [0, 32, 48, 56, 64, 80, 96, 112, 128, 144, 160, 176, 192, 224, 256, 0],
    (2, 2): [0, 8, 16, 24, 32, 40, 48, 56, 64, 80, 96, 112, 128, 144, 160, 0],
    (2, 1): [0, 8, 16, 24, 32, 40, 48, 56, 64, 80, 96, 112, 128, 144, 160, 0],
}
# MPEG 2.5 reuses the MPEG 2 tables.
_MPEG_BITRATES.update({(0, layer): _MPEG_BITRATES[(2, layer)] for layer in (1, 2, 3)})

_MPEG_SAMPLE_RATES = {
    3: [44100, 48000, 32000, 0],  # MPEG1
    2: [22050, 24000, 16000, 0],  # MPEG2
    0: [11025, 12000, 8000, 0],  # MPEG2.5
}

# Keyed by (version, layer) where layer is the raw 2-bit field:
# 1 = Layer III, 2 = Layer II, 3 = Layer I.
_MPEG_SAMPLES_PER_FRAME = {
    (3, 3): 384,  # MPEG1 Layer I
    (3, 2): 1152,  # MPEG1 Layer II
    (3, 1): 1152,  # MPEG1 Layer III
    (2, 3): 384,  # MPEG2 Layer I
    (2, 2): 1152,  # MPEG2 Layer II
    (2, 1): 576,  # MPEG2 Layer III
    (0, 3): 384,  # MPEG2.5 Layer I
    (0, 2): 1152,  # MPEG2.5 Layer II
    (0, 1): 576,  # MPEG2.5 Layer III
}


def _plausible(seconds: Optional[float]) -> Optional[float]:
    """Reject nonsense values so a bad parse degrades to `None`, not to a lie."""
    if seconds is None:
        return None
    if seconds <= 0 or seconds > _MAX_PLAUSIBLE_DURATION_SECONDS:
        return None
    return seconds


# --- MPEG audio --------------------------------------------------------------


def _id3v2_payload_offset(data: bytes) -> int:
    """Return the offset of the first audio byte after any ID3v2 tag."""
    if len(data) < 10 or data[:3] != b"ID3":
        return 0
    flags = data[5]
    size = (
        (data[6] & 0x7F) << 21
        | (data[7] & 0x7F) << 14
        | (data[8] & 0x7F) << 7
        | (data[9] & 0x7F)
    )
    offset = 10 + size
    if flags & 0x10:  # footer present
        offset += 10
    return offset


def _parse_mpeg_frame_header(header: bytes) -> Optional[dict]:
    if len(header) < 4:
        return None
    if header[0] != 0xFF or (header[1] & 0xE0) != 0xE0:
        return None

    version_bits = (header[1] >> 3) & 0x03
    if version_bits == 1:  # reserved
        return None
    version = {0: 0, 2: 2, 3: 3}[version_bits]  # 0 = MPEG2.5

    layer_bits = (header[1] >> 1) & 0x03
    if layer_bits == 0:  # reserved
        return None
    layer = layer_bits  # 1 = Layer III, 2 = Layer II, 3 = Layer I

    bitrate_index = (header[2] >> 4) & 0x0F
    sample_rate_index = (header[2] >> 2) & 0x03
    padding = (header[2] >> 1) & 0x01
    channel_mode = (header[3] >> 6) & 0x03

    bitrate_table = _MPEG_BITRATES.get((version, layer))
    if not bitrate_table:
        return None
    bitrate_kbps = bitrate_table[bitrate_index]
    sample_rate = _MPEG_SAMPLE_RATES[version][sample_rate_index]
    if bitrate_kbps <= 0 or sample_rate <= 0:
        return None

    samples_per_frame = _MPEG_SAMPLES_PER_FRAME[(version, layer)]
    if layer == 3:  # Layer I frames are measured in 4-byte slots
        frame_length = int((12 * bitrate_kbps * 1000 / sample_rate + padding) * 4)
    else:
        frame_length = int(samples_per_frame / 8 * bitrate_kbps * 1000 / sample_rate) + padding

    return {
        "version": version,
        "layer": layer,
        "bitrate_bps": bitrate_kbps * 1000,
        "sample_rate": sample_rate,
        "samples_per_frame": samples_per_frame,
        "frame_length": frame_length,
        "mono": channel_mode == 3,
    }


def _find_mpeg_frame(data: bytes, start: int) -> Tuple[Optional[dict], int]:
    """Scan for the first plausible MPEG frame header at or after `start`."""
    limit = min(len(data) - 4, start + 128 * 1024)
    index = max(0, start)
    while index <= limit:
        if data[index] == 0xFF and (data[index + 1] & 0xE0) == 0xE0:
            parsed = _parse_mpeg_frame_header(data[index : index + 4])
            if parsed:
                return parsed, index
        index += 1
    return None, -1


def _mpeg_vbr_frame_count(data: bytes, frame_offset: int, frame: dict) -> Optional[int]:
    """Read the frame count from a `Xing`/`Info` or `VBRI` header."""
    if frame["version"] == 3:
        side_info = 17 if frame["mono"] else 32
    else:
        side_info = 9 if frame["mono"] else 17

    xing_offset = frame_offset + 4 + side_info
    if xing_offset + 12 <= len(data) and data[xing_offset : xing_offset + 4] in (
        b"Xing",
        b"Info",
    ):
        flags = struct.unpack(">I", data[xing_offset + 4 : xing_offset + 8])[0]
        if flags & 0x01:
            return struct.unpack(">I", data[xing_offset + 8 : xing_offset + 12])[0]
        return None

    vbri_offset = frame_offset + 4 + 32
    if vbri_offset + 18 <= len(data) and data[vbri_offset : vbri_offset + 4] == b"VBRI":
        return struct.unpack(">I", data[vbri_offset + 14 : vbri_offset + 18])[0]

    return None


def _duration_from_mpeg(
    data: bytes,
    total_size: Optional[int],
    *,
    base_offset: int = 0,
    audio_offset: Optional[int] = None,
) -> Optional[float]:
    """Duration of MPEG audio bytes.

    `base_offset` is the absolute position of `data[0]` inside the file, so the
    CBR fallback still sizes the audio payload correctly when `data` is a window
    fetched from the middle of the file (large ID3v2 tag). `audio_offset` is the
    offset *within* `data` where audio bytes start; by default it is derived from
    an ID3v2 tag at the start of `data`.
    """
    if audio_offset is None:
        audio_offset = _id3v2_payload_offset(data)
    frame, frame_offset = _find_mpeg_frame(data, audio_offset)
    if not frame:
        return None

    frame_count = _mpeg_vbr_frame_count(data, frame_offset, frame)
    if frame_count and frame_count > 0:
        return _plausible(frame_count * frame["samples_per_frame"] / frame["sample_rate"])

    # CBR fallback: needs the total byte length of the audio payload.
    absolute_frame_offset = base_offset + frame_offset
    if not total_size or total_size <= absolute_frame_offset:
        return None
    audio_bytes = total_size - absolute_frame_offset
    return _plausible(audio_bytes * 8 / frame["bitrate_bps"])


# --- MP4 / M4A ---------------------------------------------------------------


def _duration_from_mvhd(box_body: bytes) -> Optional[float]:
    """Parse an `mvhd` box body (everything after the 8-byte box header)."""
    if len(box_body) < 4:
        return None
    version = box_body[0]
    try:
        if version == 1:
            if len(box_body) < 32:
                return None
            timescale = struct.unpack(">I", box_body[20:24])[0]
            duration = struct.unpack(">Q", box_body[24:32])[0]
        else:
            if len(box_body) < 20:
                return None
            timescale = struct.unpack(">I", box_body[12:16])[0]
            duration = struct.unpack(">I", box_body[16:20])[0]
    except struct.error:
        return None
    if timescale <= 0 or duration <= 0:
        return None
    if duration == 0xFFFFFFFF:  # unknown duration marker
        return None
    return _plausible(duration / timescale)


def _iter_mp4_boxes(data: bytes, start: int, end: int):
    """Yield (box_type, body_start, body_end, next_offset) for boxes in a range.

    `body_end` may point past `len(data)` — the caller decides whether the body
    is actually available or has to be fetched.
    """
    offset = start
    while offset + 8 <= min(end, len(data)):
        size = struct.unpack(">I", data[offset : offset + 4])[0]
        box_type = data[offset + 4 : offset + 8]
        header_size = 8
        if size == 1:
            if offset + 16 > len(data):
                return
            size = struct.unpack(">Q", data[offset + 8 : offset + 16])[0]
            header_size = 16
        elif size == 0:
            size = end - offset
        if size < header_size:
            return
        yield box_type, offset + header_size, offset + size, offset + size
        offset += size


def _find_mvhd(data: bytes, start: int, end: int, depth: int = 0) -> Optional[float]:
    if depth > 3:
        return None
    for box_type, body_start, body_end, _ in _iter_mp4_boxes(data, start, end):
        if box_type == b"mvhd":
            return _duration_from_mvhd(data[body_start : min(body_end, len(data))])
        if box_type in (b"moov", b"trak", b"mdia"):
            nested = _find_mvhd(data, body_start, body_end, depth + 1)
            if nested is not None:
                return nested
    return None


def _looks_like_mp4(data: bytes) -> bool:
    return len(data) >= 12 and data[4:8] in (b"ftyp", b"moov", b"free", b"mdat", b"skip")


def _locate_mp4_moov_offset(data: bytes, total_size: Optional[int]) -> Optional[int]:
    """Return the byte offset where `moov` starts when it is outside our window.

    Box headers carry their own size, so walking the top-level boxes present in
    the head window yields the exact offset of the boxes that follow — typically
    `moov` sitting after a multi-megabyte `mdat` in a non-faststart file.
    """
    end = total_size if total_size else len(data)
    offset = 0
    while offset + 8 <= len(data):
        size = struct.unpack(">I", data[offset : offset + 4])[0]
        box_type = data[offset + 4 : offset + 8]
        header_size = 8
        if size == 1:
            if offset + 16 > len(data):
                return None
            size = struct.unpack(">Q", data[offset + 8 : offset + 16])[0]
            header_size = 16
        elif size == 0:
            return None
        if size < header_size:
            return None
        if box_type == b"moov":
            # Present but truncated by the head window: refetch from its start.
            return offset
        offset += size
        if offset >= len(data):
            return offset if offset < end else None
    return None


def _duration_from_mp4(data: bytes) -> Optional[float]:
    return _find_mvhd(data, 0, len(data))


def _duration_from_mp4_search(data: bytes) -> Optional[float]:
    """Last resort: locate `mvhd` by signature instead of by box walking."""
    index = data.find(b"mvhd")
    while index != -1:
        duration = _duration_from_mvhd(data[index + 4 :])
        if duration is not None:
            return duration
        index = data.find(b"mvhd", index + 1)
    return None


# --- Ogg (Opus / Vorbis) -----------------------------------------------------


def _ogg_sample_rate(head: bytes) -> int:
    """Granule rate of an Ogg stream. Opus always uses 48 kHz granules."""
    if b"OpusHead" in head[:4096]:
        return 48000
    index = head.find(b"\x01vorbis")
    if index != -1 and index + 16 <= len(head):
        rate = struct.unpack("<I", head[index + 12 : index + 16])[0]
        if rate > 0:
            return rate
    return 48000


def _ogg_last_granule(tail: bytes) -> Optional[int]:
    index = tail.rfind(b"OggS")
    while index != -1:
        if index + 14 <= len(tail):
            granule = struct.unpack("<q", tail[index + 6 : index + 14])[0]
            if granule > 0:
                return granule
        index = tail.rfind(b"OggS", 0, index)
    return None


def _duration_from_ogg(head: bytes, tail: bytes) -> Optional[float]:
    """Ogg duration, which is only knowable from the *last* page of the file.

    `tail` must really be the end of the file. Reading the granule position of
    the last page inside a head window would report a fraction of the real
    duration, which for a quota gate is worse than reporting nothing.
    """
    if not tail:
        return None
    granule = _ogg_last_granule(tail)
    if granule is None:
        return None
    return _plausible(granule / _ogg_sample_rate(head))


# --- WAV ---------------------------------------------------------------------


def _duration_from_wav(data: bytes, total_size: Optional[int]) -> Optional[float]:
    if len(data) < 12 or data[:4] != b"RIFF" or data[8:12] != b"WAVE":
        return None
    byte_rate = 0
    offset = 12
    while offset + 8 <= len(data):
        chunk_id = data[offset : offset + 4]
        chunk_size = struct.unpack("<I", data[offset + 4 : offset + 8])[0]
        body = offset + 8
        if chunk_id == b"fmt " and body + 16 <= len(data):
            byte_rate = struct.unpack("<I", data[body + 8 : body + 12])[0]
        elif chunk_id == b"data":
            if byte_rate <= 0:
                return None
            data_size = chunk_size
            if data_size in (0, 0xFFFFFFFF) and total_size:
                data_size = max(0, total_size - body)
            return _plausible(data_size / byte_rate)
        offset = body + chunk_size + (chunk_size % 2)
    return None


# --- FLAC --------------------------------------------------------------------


def _duration_from_flac(data: bytes) -> Optional[float]:
    if len(data) < 42 or data[:4] != b"fLaC":
        return None
    # First metadata block header is 4 bytes; STREAMINFO body is 34 bytes.
    body = data[8:42]
    if len(body) < 18:
        return None
    packed = int.from_bytes(body[10:18], "big")
    sample_rate = (packed >> 44) & 0xFFFFF
    total_samples = packed & 0xFFFFFFFFF
    if sample_rate <= 0 or total_samples <= 0:
        return None
    return _plausible(total_samples / sample_rate)


# --- Dispatch ----------------------------------------------------------------


def _duration_from_buffers(
    head: bytes,
    tail: bytes,
    total_size: Optional[int],
) -> Optional[float]:
    """Try every container parser against the bytes we have."""
    if not head:
        return None

    if head[:4] == b"RIFF":
        return _duration_from_wav(head, total_size)
    if head[:4] == b"fLaC":
        return _duration_from_flac(head)
    if head[:4] == b"OggS":
        return _duration_from_ogg(head, tail)
    if _looks_like_mp4(head):
        duration = _duration_from_mp4(head)
        if duration is None:
            duration = _duration_from_mp4_search(head)
        if duration is None and tail:
            duration = _duration_from_mp4_search(tail)
        return duration

    # MPEG audio (with or without an ID3v2 tag) is the remaining common case,
    # and also the default for `audio/mpeg` payloads with odd leading bytes.
    duration = _duration_from_mpeg(head, total_size)
    if duration is None:
        duration = _duration_from_mp4_search(head)
    return duration


def probe_duration_seconds_from_bytes(data: bytes) -> Optional[int]:
    """
    Duration of an in-memory audio file, or None when it cannot be read.

    The whole file is available, so head and tail point at the same buffer and a
    single pass covers every supported container.
    """
    if not data:
        return None
    try:
        seconds = _duration_from_buffers(data, data, len(data))
    except Exception as exc:  # a malformed upload must not break the request
        log_event(
            logger,
            logging.WARNING,
            "audio_probe.local_failed",
            "Local audio duration probe raised",
            error=str(exc),
            byte_length=len(data),
        )
        return None
    if seconds is None:
        return None
    return int(round(seconds))


def _finalize(seconds: Optional[float]) -> Optional[int]:
    """Round a probed duration, logging the give-up case once."""
    if seconds is None:
        log_event(
            logger,
            logging.INFO,
            "audio_probe.remote_unresolved",
            "Remote audio duration could not be determined from container metadata",
        )
        return None
    return int(round(seconds))


class _RangeResult(NamedTuple):
    data: bytes
    total_size: Optional[int]
    # False when the server ignored the Range header and replied with the whole
    # body: the bytes then start at offset 0, whatever range we asked for.
    is_partial: bool


async def _fetch_range(
    client: httpx.AsyncClient,
    url: str,
    range_header: str,
    max_bytes: int,
) -> _RangeResult:
    """Fetch a byte range, capped at `max_bytes` even if the server ignores it."""
    buffer = bytearray()
    total_size: Optional[int] = None
    async with client.stream("GET", url, headers={"Range": range_header}) as response:
        response.raise_for_status()
        is_partial = response.status_code == 206
        content_range = response.headers.get("content-range", "")
        if "/" in content_range:
            try:
                total_size = int(content_range.rsplit("/", 1)[1])
            except ValueError:
                total_size = None
        elif response.status_code == 200:
            try:
                total_size = int(response.headers.get("content-length", "0")) or None
            except ValueError:
                total_size = None
        async for chunk in response.aiter_bytes(chunk_size=16 * 1024):
            buffer.extend(chunk)
            if len(buffer) >= max_bytes:
                break
    return _RangeResult(bytes(buffer), total_size, is_partial)


async def probe_duration_seconds_from_url(
    url: str,
    *,
    budget_seconds: float = DEFAULT_PROBE_BUDGET_SECONDS,
) -> Optional[int]:
    """
    Duration of a remote audio file read over HTTP Range, or None.

    At most three short Range requests (head, then an offset the head pointed at,
    then the tail), all inside `budget_seconds`. Any failure — unsupported
    container, server without Range support, timeout, HTTP error — returns None so
    the caller can fall back to a provisional debit.
    """
    if not url:
        return None

    deadline = time.monotonic() + budget_seconds

    def remaining() -> float:
        return deadline - time.monotonic()

    try:
        async with httpx.AsyncClient(
            timeout=httpx.Timeout(budget_seconds, connect=min(2.0, budget_seconds)),
            follow_redirects=True,
        ) as client:
            first = await _fetch_range(
                client, url, f"bytes=0-{_HEAD_WINDOW_BYTES - 1}", _HEAD_WINDOW_BYTES
            )
            head, total_size = first.data, first.total_size
            if not first.is_partial and total_size and len(head) >= total_size:
                # Range ignored but the whole (small) file arrived: parse it all.
                return _finalize(_duration_from_buffers(head, head, total_size))
            seconds = _duration_from_buffers(head, b"", total_size)

            # Without honoured Range requests every further window would start at
            # offset 0 again, and mis-parsing bytes is worse than not knowing.
            if seconds is None and not first.is_partial:
                return _finalize(None)

            if seconds is None and remaining() > 0.5:
                # Both remaining shapes give us an exact offset to jump to:
                # - MP4 with `moov` after `mdat`: the box walk says where the
                #   remaining boxes start.
                # - MP3 with an ID3v2 tag larger than the head window (cover art
                #   of several hundred kB is common on podcast CDNs): the tag
                #   header says where the first audio frame starts.
                extra_offset: Optional[int] = None
                extra_kind = ""
                if _looks_like_mp4(head):
                    extra_offset = _locate_mp4_moov_offset(head, total_size)
                    extra_kind = "mp4"
                elif head[:3] == b"ID3":
                    id3_offset = _id3v2_payload_offset(head)
                    if id3_offset >= len(head):
                        extra_offset = id3_offset
                        extra_kind = "mpeg"
                if extra_offset is not None and (
                    total_size is None or extra_offset < total_size
                ):
                    extra = await _fetch_range(
                        client,
                        url,
                        f"bytes={extra_offset}-{extra_offset + _JUMP_WINDOW_BYTES - 1}",
                        _JUMP_WINDOW_BYTES,
                    )
                    if extra.is_partial and extra_kind == "mpeg":
                        seconds = _duration_from_mpeg(
                            extra.data,
                            total_size,
                            base_offset=extra_offset,
                            audio_offset=0,
                        )
                    elif extra.is_partial:
                        seconds = _duration_from_mp4_search(extra.data)

            if seconds is None and remaining() > 0.5:
                # Ogg needs the granule position of the last page; a tail range
                # also rescues an MP4 whose `moov` we failed to locate.
                tail = await _fetch_range(
                    client, url, f"bytes=-{_TAIL_WINDOW_BYTES}", _TAIL_WINDOW_BYTES
                )
                if tail.data and tail.is_partial:
                    seconds = _duration_from_buffers(head, tail.data, total_size)
                    if seconds is None:
                        seconds = _duration_from_mp4_search(tail.data)
    except Exception as exc:
        log_event(
            logger,
            logging.INFO,
            "audio_probe.remote_failed",
            "Remote audio duration probe failed",
            error=str(exc),
            error_type=type(exc).__name__,
        )
        return None

    return _finalize(seconds)


def duration_seconds_to_minutes(duration_seconds: int) -> int:
    """Billable minutes for a duration, rounded up, minimum one."""
    if duration_seconds <= 0:
        return 1
    return max(1, ceil(duration_seconds / 60))
