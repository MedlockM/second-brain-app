"""Instagram primary resolver and parser for completed Apify datasets.

The resolver never calls or waits for Apify. It resolves the free yt-dlp path
when possible and raises ``InstagramApifyRequired`` when the queue worker must
start an asynchronous actor run through the shared Apify adapter. On callback,
the worker passes the completed dataset back here for domain parsing.
"""

from __future__ import annotations

import asyncio
import logging
import os
from enum import Enum
from typing import Any, Optional
from urllib.parse import urlsplit

import yt_dlp

from media_summarizer.core.media_ingestion.domain import (
    MediaFamily,
    MediaType,
    ResolveContext,
    ResolvedMedia,
    SourcePlatform,
)
from media_summarizer.core.media_ingestion.errors import (
    NonRetryableProviderResolutionError,
)
from media_summarizer.core.media_ingestion.media_metadata import (
    normalize_cover_url,
    select_creator,
)
from media_summarizer.core.media_ingestion.ports import ContentResolverPort
from media_summarizer.core.media_ingestion.title_derivation import (
    derive_media_title,
    first_sentence,
)
from media_summarizer.utils.ingestion_sentinels import (
    strip_e2e_force_ip_block_sentinel,
)
from media_summarizer.utils.logging_config import log_event
from media_summarizer.utils.ytdlp_helpers import (
    MediaStreamUnavailableError,
    resolve_direct_media_url,
)

logger = logging.getLogger(__name__)

# yt-dlp Instagram primary path: tries to extract a direct audio URL gratis
# before falling back to Apify. Lambda IPs are sometimes blocked; on block
# we fall through to the Apify branch transparently.
YTDLP_TIMEOUT_SECONDS = float(os.environ.get("YTDLP_TIMEOUT_SECONDS", "30"))


class InstagramContentType(str, Enum):
    """Detected Instagram content type from URL path."""

    REEL = "reel"
    POST = "post"
    IGTV = "igtv"


def _detect_instagram_content_type(normalized_url: str) -> InstagramContentType:
    """Determine Instagram content type from the URL path.

    Instagram URLs come in two shapes:
    - `/<indicator>/<id>/`  e.g. `/reel/abc/`, `/p/abc/`, `/tv/abc/`
    - `/<username>/<indicator>/<id>/`  e.g. `/natgeo/reel/abc/`
    Both must resolve to the same content type, so we scan every segment
    instead of only inspecting the first.
    """
    path = (urlsplit(normalized_url).path or "").lower()
    parts = [segment for segment in path.split("/") if segment]

    indicators = {
        "reel": InstagramContentType.REEL,
        "p": InstagramContentType.POST,
        "tv": InstagramContentType.IGTV,
    }
    for segment in parts:
        if segment in indicators:
            return indicators[segment]
    raise NonRetryableProviderResolutionError("Unable to determine Instagram content type from URL.")


def _extract_image_urls_from_post_result(item: dict[str, Any]) -> list[str]:
    """Extract high-resolution image URLs from an Apify Post Scraper result item."""
    urls: list[str] = []

    # Single image post: displayUrl
    display_url = item.get("displayUrl")
    if isinstance(display_url, str) and display_url.strip().startswith("http"):
        urls.append(display_url.strip())

    # Carousel/sidecar posts: childPosts array
    child_posts = item.get("childPosts")
    if isinstance(child_posts, list):
        for child in child_posts:
            if not isinstance(child, dict):
                continue
            child_display = child.get("displayUrl")
            if isinstance(child_display, str) and child_display.strip().startswith("http"):
                urls.append(child_display.strip())
            # Also check images array in child
            child_images = child.get("images")
            if isinstance(child_images, list):
                for img in child_images:
                    if isinstance(img, str) and img.strip().startswith("http"):
                        urls.append(img.strip())

    # Top-level images array
    images = item.get("images")
    if isinstance(images, list):
        for img in images:
            if isinstance(img, str) and img.strip().startswith("http"):
                urls.append(img.strip())

    # Deduplicate while preserving order
    seen: set[str] = set()
    unique_urls: list[str] = []
    for url in urls:
        if url not in seen:
            seen.add(url)
            unique_urls.append(url)

    return unique_urls


def _extract_caption(item: dict[str, Any]) -> Optional[str]:
    """Extract caption text from an Apify scraper result item."""
    caption = item.get("caption")
    if isinstance(caption, str) and caption.strip():
        return caption.strip()
    return None


def _looks_like_ig_ip_blocked_error(exc: Exception) -> bool:
    """Detect Instagram IP-block / login-wall errors from yt-dlp.

    Instagram uses several phrasings depending on the rate-limiting reason:
    a generic login wall ("login required"), restricted videos requiring
    authentication, or rate-limit responses on residential CDNs. We treat
    all of them as "primary path blocked, fall back to Apify".
    """
    msg = str(exc).lower()
    return any(
        token in msg
        for token in (
            "login required",
            "login_required",
            "rate-limit",
            "rate limit",
            "this content isn't available",
            "this content is not available",
            "restricted video",
            "requested content is not available",
            "please wait a few minutes",
        )
    )


class _InstagramYtdlpBlocked(Exception):
    """Internal signal raised by the yt-dlp primary path when blocked.

    The caller catches this and falls back to Apify. Carries the original
    yt-dlp error string for observability.
    """

    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


class InstagramApifyRequired(Exception):
    """Signal that the queue worker must start an asynchronous Apify run."""

    def __init__(
        self,
        *,
        normalized_url: str,
        content_type: InstagramContentType,
        reason: str,
    ) -> None:
        super().__init__(reason)
        self.normalized_url = normalized_url
        self.content_type = content_type
        self.reason = reason


class InstagramApifyResolver(ContentResolverPort):
    """
    Instagram primary resolver plus completed Apify dataset parser.

    The queue worker owns asynchronous actor orchestration. This class only
    resolves the direct yt-dlp path, selects actor input, and parses terminal
    datasets into domain media.

    Reels and IGTV are resolved through `apify/instagram-reel-scraper` and
    surface either an `audioUrl` (preferred) or `videoUrl` (fallback) for
    downstream Deepgram transcription. There is no native transcript path —
    consumers must enqueue Deepgram with `pull_with_push_fallback` mode so
    push-mode kicks in when the IG CDN blocks Deepgram pull.
    """

    @property
    def key(self) -> str:
        return "instagram.default"

    async def resolve(self, context: ResolveContext) -> ResolvedMedia:
        """
        Resolve Instagram without blocking on an Apify actor.

        Workflow:
        1. Detect content type (reel/post/igtv) from URL
        Video tries yt-dlp first. Any content requiring Apify raises a typed
        signal carrying the clean URL and actor input selection.
        """
        clean_url, force_apify_fallback = strip_e2e_force_ip_block_sentinel(context.normalized_url)
        # Stash the clean URL so downstream actor calls don't see the sentinel.
        # `ResolveContext` is a frozen dataclass; rebuild it instead of mutating.
        if clean_url != context.normalized_url:
            from dataclasses import replace

            context = replace(context, normalized_url=clean_url)

        content_type = _detect_instagram_content_type(context.normalized_url)

        log_event(
            logger,
            logging.INFO,
            "resolver.instagram.started",
            "Instagram resolution started",
            source_platform=SourcePlatform.INSTAGRAM.value,
            resolver_key=self.key,
            provider="apify",
            instagram_content_type=content_type.value,
        )

        is_video = content_type in (
            InstagramContentType.REEL,
            InstagramContentType.IGTV,
        )

        if is_video and not force_apify_fallback:
            try:
                return await self._resolve_reel_via_ytdlp(context, content_type)
            except _InstagramYtdlpBlocked as block_exc:
                log_event(
                    logger,
                    logging.WARNING,
                    "instagram.reel.ytdlp_ip_blocked",
                    "yt-dlp IP-blocked on Instagram, starting async Apify fallback",
                    source_platform=SourcePlatform.INSTAGRAM.value,
                    resolver_key=self.key,
                    instagram_content_type=content_type.value,
                    detail=block_exc.reason,
                )
                raise InstagramApifyRequired(
                    normalized_url=context.normalized_url,
                    content_type=content_type,
                    reason=block_exc.reason,
                ) from block_exc
        if is_video and force_apify_fallback:
            log_event(
                logger,
                logging.WARNING,
                "instagram.reel.ytdlp_ip_blocked",
                "E2E sentinel forced asynchronous Apify fallback",
                resolver_key=self.key,
                source_platform=SourcePlatform.INSTAGRAM.value,
                instagram_content_type=content_type.value,
                detail="e2e_sentinel_force_ip_block",
            )
        raise InstagramApifyRequired(
            normalized_url=context.normalized_url,
            content_type=content_type,
            reason=("e2e_sentinel_force_ip_block" if force_apify_fallback else "instagram_post_requires_apify"),
        )

    def build_apify_input(
        self,
        *,
        normalized_url: str,
        content_type: InstagramContentType,
    ) -> dict[str, Any]:
        del content_type
        return {"username": [normalized_url], "resultsLimit": 1}

    def resolve_apify_dataset(
        self,
        *,
        context: ResolveContext,
        content_type: InstagramContentType,
        actor_id: str,
        items: list[dict[str, Any]],
    ) -> ResolvedMedia:
        if content_type in (InstagramContentType.REEL, InstagramContentType.IGTV):
            return self._resolve_reel(
                context,
                content_type,
                actor_id=actor_id,
                results=items,
            )
        return self._resolve_post(
            context,
            content_type,
            actor_id=actor_id,
            results=items,
        )

    async def _resolve_reel_via_ytdlp(
        self,
        context: ResolveContext,
        content_type: InstagramContentType,
    ) -> ResolvedMedia:
        """Primary path: extract a direct audio URL via yt-dlp (no Apify cost).

        Returns a ResolvedMedia carrying the audio URL for downstream
        Deepgram transcription. Raises ``_InstagramYtdlpBlocked`` on Lambda
        IP-block / login-wall errors so the caller can fall back to Apify.
        Other errors (live content, no media stream, geo-restriction)
        propagate as ``NonRetryableProviderResolutionError``.
        """
        ydl_opts = {
            "quiet": True,
            "no_warnings": True,
            "skip_download": True,
            "socket_timeout": YTDLP_TIMEOUT_SECONDS,
        }

        def _extract() -> dict[str, Any]:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                return ydl.extract_info(context.normalized_url, download=False)

        try:
            info = await asyncio.wait_for(
                asyncio.to_thread(_extract),
                timeout=YTDLP_TIMEOUT_SECONDS,
            )
        except asyncio.TimeoutError as exc:
            # Treat timeouts as a soft block so we still try Apify.
            raise _InstagramYtdlpBlocked("ytdlp_timeout") from exc
        except yt_dlp.utils.DownloadError as exc:
            if _looks_like_ig_ip_blocked_error(exc):
                raise _InstagramYtdlpBlocked(f"ytdlp_ip_blocked:{type(exc).__name__}") from exc
            # Unknown yt-dlp failure — defer to Apify rather than fail outright.
            raise _InstagramYtdlpBlocked(f"ytdlp_download_error:{type(exc).__name__}") from exc
        except Exception as exc:
            if _looks_like_ig_ip_blocked_error(exc):
                raise _InstagramYtdlpBlocked(f"ytdlp_ip_blocked:{type(exc).__name__}") from exc
            raise _InstagramYtdlpBlocked(f"ytdlp_unexpected:{type(exc).__name__}") from exc

        try:
            audio_result = resolve_direct_media_url(info)
        except MediaStreamUnavailableError as exc:
            # yt-dlp returned info but no usable audio stream — Apify probably
            # won't do better, but try anyway for parity with TikTok/YouTube.
            raise _InstagramYtdlpBlocked(f"ytdlp_no_media_stream:{exc.reason}") from exc

        caption_value = info.get("description") or info.get("title")
        caption = caption_value.strip() if isinstance(caption_value, str) and caption_value.strip() else None
        # Instagram exposes no title of its own: yt-dlp's `title` is the
        # placeholder "Video by <user>". The owner's rule for this platform is
        # the beginning of the description, and the account name is never a
        # title -- it is the same value on every reel of that account and made
        # the whole library read as a list of usernames (task-266).
        title = derive_media_title(
            [first_sentence(caption)],
            media_type=MediaType.SHORT_VIDEO.value,
            source_platform=SourcePlatform.INSTAGRAM.value,
            authors=[info.get("uploader"), info.get("channel"), info.get("uploader_id")],
        )

        metadata: dict[str, Any] = {
            "resolver_version": "v5",
            "provider": "yt-dlp",
            "instagram_content_type": content_type.value,
            "transcript_source": "deepgram_pending",
            "audio_url_available": True,
            "audio_url_kind": "audio_ytdlp",
            "resolution_mode": "deepgram_via_ytdlp_audio_url",
            "caption": caption,
            "duration_seconds": audio_result.get("audio_duration_seconds", 0),
            "yt_dlp_format_id": audio_result.get("format_id"),
            "yt_dlp_ext": audio_result.get("ext"),
        }

        log_event(
            logger,
            logging.INFO,
            "instagram.reel.transcript_source",
            "Instagram reel resolved with yt-dlp audio URL for Deepgram",
            source_platform=SourcePlatform.INSTAGRAM.value,
            resolver_key=self.key,
            media_type=MediaType.SHORT_VIDEO.value,
            provider="yt-dlp",
            instagram_content_type=content_type.value,
            audio_url_kind="audio_ytdlp",
        )

        return ResolvedMedia(
            media_key=context.media_key,
            normalized_url=context.normalized_url,
            media_family=MediaFamily.SOCIAL_VIDEO,
            media_type=MediaType.SHORT_VIDEO,
            source_platform=SourcePlatform.INSTAGRAM,
            resolver_key=self.key,
            audio_url=audio_result["audio_url"],
            title=title,
            metadata=metadata,
        )

    def _resolve_reel(
        self,
        context: ResolveContext,
        content_type: InstagramContentType,
        *,
        actor_id: str,
        results: list[dict[str, Any]],
    ) -> ResolvedMedia:
        """Parse a completed Reel or IGTV actor dataset.

        Parses `apify/instagram-reel-scraper` output and surfaces the audio URL
        (preferred) or video URL (fallback) for downstream Deepgram
        transcription. The downstream worker decides between pull and push
        modes — Instagram CDNs sometimes block Deepgram, so callers should
        use ``deepgram_mode="pull_with_push_fallback"``.
        """
        if not results:
            raise NonRetryableProviderResolutionError("Unable to resolve transcribable media from this Instagram URL.")

        item = results[0]
        if item.get("error"):
            raise NonRetryableProviderResolutionError("Unable to resolve transcribable media from this Instagram URL.")

        audio_url_raw = item.get("audioUrl")
        video_url_raw = item.get("videoUrl")
        audio_url = audio_url_raw.strip() if isinstance(audio_url_raw, str) and audio_url_raw.strip() else None
        video_url = video_url_raw.strip() if isinstance(video_url_raw, str) and video_url_raw.strip() else None
        # The scraper sometimes omits audioUrl on shorts where the video track
        # carries the audio inline; fall back to videoUrl so Deepgram can pull
        # the muxed stream.
        chosen_url = audio_url or video_url
        if not chosen_url:
            raise NonRetryableProviderResolutionError("Unable to resolve transcribable media from this Instagram URL.")

        duration_seconds: Optional[float] = None
        raw_duration = item.get("videoDuration") or item.get("duration")
        if raw_duration is not None:
            try:
                duration_seconds = float(raw_duration)
            except (ValueError, TypeError):
                duration_seconds = None

        caption = _extract_caption(item)
        # Caption first, account name never (task-266).
        title = derive_media_title(
            [first_sentence(caption)],
            media_type=MediaType.SHORT_VIDEO.value,
            source_platform=SourcePlatform.INSTAGRAM.value,
            authors=[item.get("ownerFullName"), item.get("ownerUsername")],
        )
        # The account the reel belongs to. Same two fields the title rejects --
        # they are the publisher, which is exactly what the tile's second line
        # wants (task-304). The Reel Scraper also returns `displayUrl`, which
        # this branch used to ignore even though the post branch parses it.
        creator_name = select_creator(
            [item.get("ownerFullName"), item.get("ownerUsername")],
            title=title,
        )
        cover_url = normalize_cover_url(item.get("displayUrl"))

        metadata: dict[str, Any] = {
            "resolver_version": "v4",
            "provider": "apify",
            "provider_actor": actor_id,
            "instagram_content_type": content_type.value,
            "transcript_source": "deepgram_pending",
            "audio_url_available": True,
            "audio_url_kind": "audio" if audio_url else "video",
            "resolution_mode": "deepgram_via_apify_audio_url",
            "caption": caption,
        }
        if duration_seconds is not None:
            metadata["duration_seconds"] = duration_seconds

        resolved = ResolvedMedia(
            media_key=context.media_key,
            normalized_url=context.normalized_url,
            media_family=MediaFamily.SOCIAL_VIDEO,
            media_type=MediaType.SHORT_VIDEO,
            source_platform=SourcePlatform.INSTAGRAM,
            resolver_key=self.key,
            audio_url=chosen_url,
            title=title,
            cover_url=cover_url,
            creator_name=creator_name,
            metadata=metadata,
        )

        log_event(
            logger,
            logging.INFO,
            "instagram.reel.transcript_source",
            "Instagram reel resolved with audio URL for Deepgram",
            source_platform=SourcePlatform.INSTAGRAM.value,
            resolver_key=self.key,
            media_type=MediaType.SHORT_VIDEO.value,
            provider="apify",
            provider_actor=actor_id,
            instagram_content_type=content_type.value,
            audio_url_kind=metadata["audio_url_kind"],
        )

        return resolved

    def _resolve_post(
        self,
        context: ResolveContext,
        content_type: InstagramContentType,
        *,
        actor_id: str,
        results: list[dict[str, Any]],
    ) -> ResolvedMedia:
        """Parse a completed Post Scraper actor dataset.

        Posts can be video posts, single image posts, or carousels.
        This method determines the actual content and returns the appropriate
        ResolvedMedia type.
        """
        if not results:
            raise NonRetryableProviderResolutionError("Unable to resolve transcribable media from this Instagram URL.")

        item = results[0]
        caption = _extract_caption(item)

        # Image post (single or carousel)
        image_urls = _extract_image_urls_from_post_result(item)
        is_carousel = len(image_urls) > 1 or bool(item.get("childPosts"))

        metadata = {
            "resolver_version": "v2",
            "provider": "apify",
            "provider_actor": actor_id,
            "instagram_content_type": content_type.value,
            "post_type": "carousel" if is_carousel else "image",
            "image_urls": image_urls,
            "image_count": len(image_urls),
            "audio_url_available": False,
            "resolution_mode": "queued_worker",
            "caption": caption,
        }

        post_title = derive_media_title(
            [first_sentence(caption)],
            media_type=MediaType.IMAGE_POST.value,
            source_platform=SourcePlatform.INSTAGRAM.value,
            authors=[item.get("ownerFullName"), item.get("ownerUsername")],
        )
        resolved = ResolvedMedia(
            media_key=context.media_key,
            normalized_url=context.normalized_url,
            media_family=MediaFamily.SOCIAL_VIDEO,
            media_type=MediaType.IMAGE_POST,
            source_platform=SourcePlatform.INSTAGRAM,
            resolver_key=self.key,
            title=post_title,
            cover_url=normalize_cover_url(image_urls[0] if image_urls else None),
            creator_name=select_creator(
                [item.get("ownerFullName"), item.get("ownerUsername")],
                title=post_title,
            ),
            metadata=metadata,
        )

        log_event(
            logger,
            logging.INFO,
            "resolver.completed",
            "Instagram image post resolver completed via Apify",
            source_platform=SourcePlatform.INSTAGRAM.value,
            resolver_key=self.key,
            media_type=MediaType.IMAGE_POST.value,
            provider="apify",
            instagram_content_type=content_type.value,
            post_type="carousel" if is_carousel else "image",
            image_count=len(image_urls),
            fallback_strategy="queued_worker",
        )

        return resolved
