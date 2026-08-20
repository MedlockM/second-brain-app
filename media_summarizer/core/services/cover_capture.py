"""Re-host a media cover into our own bucket (task-304).

Applies the owner's decision at the end of task-302 (**Approach C**): a cover is
hotlinked when its CDN URL is unsigned and stable, and re-hosted only when the
URL is *signed and expiring* -- Instagram (``oh``/``oe``) and TikTok
(``x-expires``), which answer 403 within hours to days -- or when the image is
the user's own private file (a camera capture or a gallery pick, up to 50 MB).

Everything here is best-effort by contract. A cover is a display detail: a
timeout, a 404, an unreadable payload or a missing bucket must degrade to "this
tile shows its media-type icon", never to a failed ingestion. Every entry point
therefore returns ``None`` instead of raising, and logs the reason.

The stored object is a downscaled JPEG bounded by ``COVER_MAX_EDGE`` on both
sides, so a 16:9 thumbnail becomes 640x360 and a 9:16 reel cover becomes
360x640. The crop to the tile's ratio is the client's job (``contentFit:
"cover"``), which keeps this side free of any layout decision.
"""

from __future__ import annotations

import logging
import os
from io import BytesIO
from typing import Optional

import httpx

from media_summarizer.core.media_ingestion.media_metadata import (
    build_cover_locator,
    normalize_cover_url,
    parse_cover_locator,
)
from media_summarizer.utils import s3
from media_summarizer.utils.logging_config import log_event

logger = logging.getLogger(__name__)

# Injected by Terraform (modules/platform/runtime_env.tf). Read lazily rather
# than through `required_env` so that importing this module never breaks a
# worker that does not re-host anything.
COVERS_BUCKET_ENV = "COVERS_BUCKET"

COVER_FETCH_TIMEOUT_SECONDS = float(os.environ.get("COVER_FETCH_TIMEOUT_SECONDS", "10"))
# A cover that does not fit in this is not a cover. Instagram and TikTok serve
# a few hundred KB; the ceiling exists for the user-photo path, where the source
# can legitimately be 50 MB and must not be pulled into a Lambda's memory.
COVER_MAX_SOURCE_BYTES = int(os.environ.get("COVER_MAX_SOURCE_BYTES", str(12 * 1024 * 1024)))
# Longest edge of the stored derivative. 640 keeps a JPEG around 40 KB at q80,
# which is what the benchmark's cost model assumes (task-302 §5.4).
COVER_MAX_EDGE = 640
COVER_JPEG_QUALITY = 80
COVER_CONTENT_TYPE = "image/jpeg"

EVENT_CAPTURE_FAILED = "media_cover.capture_failed"
EVENT_CAPTURED = "media_cover.captured"
EVENT_DELETE_FAILED = "media_cover.delete_failed"

# A browser-ish agent: several CDNs answer 403 to the default httpx UA.
_COVER_USER_AGENT = os.environ.get(
    "COVER_FETCH_USER_AGENT",
    "Mozilla/5.0 (compatible; MediaSummarizerBot/1.0)",
)


def covers_bucket() -> Optional[str]:
    """The covers bucket name, or ``None`` when the env var is absent."""
    return (os.environ.get(COVERS_BUCKET_ENV) or "").strip() or None


def cover_key(media_item_id: str) -> str:
    """One object per library row, so a re-ingestion overwrites in place."""
    return f"covers/{media_item_id}.jpg"


def _downscale_to_jpeg(payload: bytes) -> Optional[bytes]:
    """Decode, downscale and re-encode as JPEG. ``None`` if it is not an image.

    Pillow is imported inside the function: it ships only in the worker image
    (``pyproject.toml``, ``worker`` extra), and the API image must stay able to
    import this module to resolve a locator.
    """
    try:
        from PIL import Image, ImageOps
    except ImportError:
        logger.warning("Pillow is not installed in this image; cover skipped")
        return None

    try:
        with Image.open(BytesIO(payload)) as opened:
            # EXIF orientation: a phone capture is otherwise stored sideways.
            image = ImageOps.exif_transpose(opened) or opened
            if image.mode not in ("RGB", "L"):
                image = image.convert("RGB")
            image.thumbnail(
                (COVER_MAX_EDGE, COVER_MAX_EDGE), Image.Resampling.LANCZOS
            )
            buffer = BytesIO()
            image.save(
                buffer,
                format="JPEG",
                quality=COVER_JPEG_QUALITY,
                optimize=True,
                progressive=True,
            )
            return buffer.getvalue()
    except Exception as exc:  # noqa: BLE001 - an undecodable payload is not an error
        logger.warning("Cover payload could not be decoded: %s", exc)
        return None


async def _fetch(url: str) -> Optional[bytes]:
    """Download a cover, bounded in time and size. ``None`` on any failure."""
    try:
        async with httpx.AsyncClient(
            timeout=COVER_FETCH_TIMEOUT_SECONDS,
            follow_redirects=True,
            headers={"User-Agent": _COVER_USER_AGENT},
        ) as client:
            async with client.stream("GET", url) as response:
                response.raise_for_status()
                chunks: list[bytes] = []
                total = 0
                async for chunk in response.aiter_bytes():
                    total += len(chunk)
                    if total > COVER_MAX_SOURCE_BYTES:
                        logger.warning(
                            "Cover source exceeds %s bytes; skipped",
                            COVER_MAX_SOURCE_BYTES,
                        )
                        return None
                    chunks.append(chunk)
                return b"".join(chunks)
    except Exception as exc:  # noqa: BLE001 - best-effort by contract
        logger.warning("Cover fetch failed for %s: %s", url, type(exc).__name__)
        return None


async def _store(*, media_item_id: str, jpeg: bytes) -> Optional[str]:
    bucket = covers_bucket()
    if not bucket:
        logger.warning("COVERS_BUCKET is not set; cover not stored")
        return None
    key = cover_key(media_item_id)
    try:
        await s3.upload_file_object(
            bucket=bucket,
            key=key,
            file_obj=BytesIO(jpeg),
            content_type=COVER_CONTENT_TYPE,
            metadata={"media-item-id": media_item_id},
        )
    except Exception as exc:  # noqa: BLE001 - best-effort by contract
        log_event(
            logger,
            logging.WARNING,
            EVENT_CAPTURE_FAILED,
            f"Cover upload failed: {exc}",
            media_item_id=media_item_id,
            error_type=type(exc).__name__,
        )
        return None
    return build_cover_locator(bucket, key)


async def capture_from_url(
    *,
    source_url: Optional[str],
    media_item_id: Optional[str],
) -> Optional[str]:
    """Re-host a third-party cover. Returns an ``s3://`` locator, or ``None``.

    ``None`` is a normal outcome, not an error: the caller then leaves the row
    without a cover and the tile falls back to its media-type icon.
    """
    url = normalize_cover_url(source_url)
    if not url or not media_item_id:
        return None
    if parse_cover_locator(url):
        # Already ours (a re-processed job): nothing to re-download.
        return url

    payload = await _fetch(url)
    if not payload:
        return None
    jpeg = _downscale_to_jpeg(payload)
    if not jpeg:
        return None

    locator = await _store(media_item_id=media_item_id, jpeg=jpeg)
    if locator:
        log_event(
            logger,
            logging.INFO,
            EVENT_CAPTURED,
            "Media cover re-hosted",
            media_item_id=media_item_id,
            source="url",
            bytes_stored=len(jpeg),
        )
    return locator


async def capture_from_s3(
    *,
    bucket: str,
    key: str,
    media_item_id: Optional[str],
) -> Optional[str]:
    """Build a cover from an object we already hold (a camera or gallery photo).

    The original stays where it is; only a downscaled derivative is written to
    the covers bucket, because the source can be up to 50 MB and would be
    unservable as a list thumbnail.
    """
    if not media_item_id or not bucket or not key:
        return None
    try:
        payload = await s3.download_file_to_memory(bucket=bucket, key=key)
    except Exception as exc:  # noqa: BLE001 - best-effort by contract
        logger.warning("Cover source could not be read from S3: %s", type(exc).__name__)
        return None

    jpeg = _downscale_to_jpeg(payload)
    if not jpeg:
        return None

    locator = await _store(media_item_id=media_item_id, jpeg=jpeg)
    if locator:
        log_event(
            logger,
            logging.INFO,
            EVENT_CAPTURED,
            "Media cover built from stored upload",
            media_item_id=media_item_id,
            source="s3",
            bytes_stored=len(jpeg),
        )
    return locator


async def resolve_cover_url(
    stored_value: Optional[str],
    *,
    expiration: int = 86400,
) -> Optional[str]:
    """Turn a stored cover value into something a client can fetch.

    A hotlinked value is returned unchanged. An ``s3://`` locator is signed for
    ``expiration`` seconds -- 24 h, so an Inbox left open across a session never
    renders a stale signature. The client keeps the image cached across
    signature rotations through ``expo-image``'s ``cacheKey`` (task-302 §6.2),
    so a changing query string costs nothing.
    """
    if not stored_value:
        return None
    located = parse_cover_locator(stored_value)
    if not located:
        return stored_value
    bucket, key = located
    try:
        return await s3.generate_presigned_url(
            bucket=bucket,
            key=key,
            expiration=expiration,
            http_method="GET",
        )
    except Exception as exc:  # noqa: BLE001 - a missing cover is a display detail
        logger.warning("Could not sign cover %s/%s: %s", bucket, key, type(exc).__name__)
        return None


async def delete_cover(stored_value: Optional[str]) -> bool:
    """Delete a re-hosted cover. A hotlinked value has nothing to delete."""
    located = parse_cover_locator(stored_value)
    if not located:
        return False
    bucket, key = located
    try:
        await s3.delete_object(bucket=bucket, key=key)
        return True
    except Exception as exc:  # noqa: BLE001 - purge must not stall on a thumbnail
        log_event(
            logger,
            logging.WARNING,
            EVENT_DELETE_FAILED,
            f"Cover deletion failed: {exc}",
            bucket=bucket,
            key=key,
            error_type=type(exc).__name__,
        )
        return False
