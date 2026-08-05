"""
Instagram Apify resolver -- Apify-based Instagram content extraction adapter.

Orchestrates two Apify actors to cover all Instagram content types:
- Instagram Reel Scraper (apify/instagram-reel-scraper): returns reel metadata
  with `audioUrl` (direct audio CDN) and `videoUrl` (full video CDN). The
  resolver surfaces the audio URL for downstream Deepgram transcription
  (pull-with-push-fallback mode — the IG CDN sometimes blocks Deepgram).
- Instagram Post Scraper: extracts high-resolution image URLs for posts/carousels

For Reels, the resolver does NOT attempt to extract a native transcript: it
hands the audio URL to the Deepgram pipeline which decides between pull and
push based on whether the CDN responds.

Environment variables:
    APIFY_INSTAGRAM_API_TOKEN: API token for the Instagram Apify account (required)
    APIFY_INSTAGRAM_REEL_ACTOR_ID: Actor ID for the reel scraper
        (default: apify~instagram-reel-scraper)
    APIFY_INSTAGRAM_POST_ACTOR_ID: Actor ID for Instagram Post Scraper
        (default: apify~instagram-post-scraper)
    APIFY_TIMEOUT_SECONDS: Request timeout (default 60)
    APIFY_POLL_INTERVAL_SECONDS: Poll interval for actor run status (default 3)
    APIFY_MAX_POLLS: Maximum number of poll attempts (default 40)
"""

from __future__ import annotations

import asyncio
import logging
import os
from enum import Enum
from typing import Any, Optional
from urllib.parse import urlsplit

import httpx
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
    RetryableProviderResolutionError,
)
from media_summarizer.core.media_ingestion.ports import ContentResolverPort
from media_summarizer.utils.ingestion_sentinels import (
    strip_e2e_force_ip_block_sentinel,
)
from media_summarizer.utils.logging_config import log_event
from media_summarizer.utils.ytdlp_helpers import (
    MediaStreamUnavailableError,
    resolve_direct_media_url,
)

logger = logging.getLogger(__name__)

APIFY_INSTAGRAM_API_TOKEN = os.environ.get("APIFY_INSTAGRAM_API_TOKEN", "").strip()
APIFY_API_BASE_URL = "https://api.apify.com/v2"
APIFY_INSTAGRAM_REEL_ACTOR_ID = os.environ.get(
    "APIFY_INSTAGRAM_REEL_ACTOR_ID", "apify~instagram-reel-scraper"
)
APIFY_INSTAGRAM_POST_ACTOR_ID = os.environ.get(
    "APIFY_INSTAGRAM_POST_ACTOR_ID", "apify~instagram-post-scraper"
)
APIFY_TIMEOUT_SECONDS = float(os.environ.get("APIFY_TIMEOUT_SECONDS", "60"))
APIFY_POLL_INTERVAL_SECONDS = float(
    os.environ.get("APIFY_POLL_INTERVAL_SECONDS", "3")
)
APIFY_MAX_POLLS = int(os.environ.get("APIFY_MAX_POLLS", "40"))

# yt-dlp Instagram primary path: tries to extract a direct audio URL gratis
# before falling back to Apify. Lambda IPs are sometimes blocked; on block
# we fall through to the Apify branch transparently.
YTDLP_TIMEOUT_SECONDS = float(os.environ.get("YTDLP_TIMEOUT_SECONDS", "30"))


class InstagramContentType(str, Enum):
    """Detected Instagram content type from URL path."""

    REEL = "reel"
    POST = "post"
    IGTV = "igtv"


class ApifyRunStatus(str, Enum):
    """Apify actor run statuses."""

    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"
    ABORTED = "ABORTED"
    TIMED_OUT = "TIMED-OUT"
    RUNNING = "RUNNING"
    READY = "READY"


class ApifyErrorCode(str, Enum):
    """Stable error codes for Apify resolution failures."""

    AUTHENTICATION_ERROR = "apify_authentication_error"
    ACTOR_RUN_FAILED = "apify_actor_run_failed"
    ACTOR_TIMEOUT = "apify_actor_timeout"
    NO_RESULTS = "apify_no_results"
    NO_VIDEO_URL = "apify_no_video_url"
    NETWORK_ERROR = "apify_network_error"
    INVALID_CONTENT_TYPE = "apify_invalid_content_type"
    RATE_LIMITED = "apify_rate_limited"


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
    raise NonRetryableProviderResolutionError(
        "Unable to determine Instagram content type from URL."
    )


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
            if isinstance(child_display, str) and child_display.strip().startswith(
                "http"
            ):
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


class InstagramApifyResolver(ContentResolverPort):
    """
    Apify-based Instagram content resolver.

    Implements the ContentResolverPort interface. Orchestrates Apify actors
    to extract media URLs, image URLs, and captions from Instagram content
    (Reels, Posts, Carousels, IGTV).

    Reels and IGTV are resolved through `apify/instagram-reel-scraper` and
    surface either an `audioUrl` (preferred) or `videoUrl` (fallback) for
    downstream Deepgram transcription. There is no native transcript path —
    consumers must enqueue Deepgram with `pull_with_push_fallback` mode so
    push-mode kicks in when the IG CDN blocks Deepgram pull.
    """

    def __init__(
        self,
        api_token: Optional[str] = None,
        timeout: Optional[float] = None,
        reel_actor_id: Optional[str] = None,
        post_actor_id: Optional[str] = None,
    ):
        self._api_token = api_token or APIFY_INSTAGRAM_API_TOKEN
        self._timeout = timeout or APIFY_TIMEOUT_SECONDS
        self._reel_actor_id = reel_actor_id or APIFY_INSTAGRAM_REEL_ACTOR_ID
        self._post_actor_id = post_actor_id or APIFY_INSTAGRAM_POST_ACTOR_ID

    @property
    def key(self) -> str:
        return "instagram.default"

    async def resolve(self, context: ResolveContext) -> ResolvedMedia:
        """
        Resolve an Instagram URL using Apify actors.

        Workflow:
        1. Detect content type (reel/post/igtv) from URL
        2. Run appropriate Apify actor (Reel Scraper or Post Scraper)
        3. Extract media URLs, caption, and metadata
        4. Return ResolvedMedia with all extracted content
        """
        if not self._api_token:
            raise RetryableProviderResolutionError(
                "Instagram media resolution is temporarily unavailable."
            )

        clean_url, force_apify_fallback = strip_e2e_force_ip_block_sentinel(
            context.normalized_url
        )
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
            "Instagram Apify resolution started",
            source_platform=SourcePlatform.INSTAGRAM.value,
            resolver_key=self.key,
            provider="apify",
            instagram_content_type=content_type.value,
        )

        is_video = content_type in (
            InstagramContentType.REEL,
            InstagramContentType.IGTV,
        )

        try:
            if is_video and not force_apify_fallback:
                # Primary: try yt-dlp gratis. Fall back to Apify only on IP block.
                try:
                    return await self._resolve_reel_via_ytdlp(context, content_type)
                except _InstagramYtdlpBlocked as block_exc:
                    log_event(
                        logger,
                        logging.WARNING,
                        "instagram.reel.ytdlp_ip_blocked",
                        "yt-dlp IP-blocked on Instagram, falling back to Apify",
                        source_platform=SourcePlatform.INSTAGRAM.value,
                        resolver_key=self.key,
                        instagram_content_type=content_type.value,
                        detail=block_exc.reason,
                    )
                    return await self._resolve_reel(context, content_type)
            if is_video and force_apify_fallback:
                log_event(
                    logger,
                    logging.WARNING,
                    "instagram.reel.ytdlp_ip_blocked",
                    "E2E sentinel forced Apify fallback path",
                    source_platform=SourcePlatform.INSTAGRAM.value,
                    resolver_key=self.key,
                    instagram_content_type=content_type.value,
                    detail="e2e_sentinel_force_ip_block",
                )
                return await self._resolve_reel(context, content_type)
            # POST: could be video or image, use Post Scraper to determine
            return await self._resolve_post(context, content_type)

        except (
            NonRetryableProviderResolutionError,
            RetryableProviderResolutionError,
        ):
            raise
        except httpx.TimeoutException as exc:
            log_event(
                logger,
                logging.WARNING,
                "external_call.failed",
                "Apify request timed out",
                provider="apify",
                resolver_key=self.key,
                source_platform=SourcePlatform.INSTAGRAM.value,
                error_type="TimeoutException",
            )
            raise RetryableProviderResolutionError(
                "Instagram media resolution is temporarily unavailable."
            ) from exc
        except httpx.ConnectError as exc:
            log_event(
                logger,
                logging.WARNING,
                "external_call.failed",
                "Failed to connect to Apify API",
                provider="apify",
                resolver_key=self.key,
                source_platform=SourcePlatform.INSTAGRAM.value,
                error_type="ConnectError",
            )
            raise RetryableProviderResolutionError(
                "Instagram media resolution is temporarily unavailable."
            ) from exc
        except Exception as exc:
            log_event(
                logger,
                logging.ERROR,
                "external_call.failed",
                "Unexpected Apify error during Instagram resolution",
                provider="apify",
                resolver_key=self.key,
                source_platform=SourcePlatform.INSTAGRAM.value,
                error_type=type(exc).__name__,
                exc_info=exc,
            )
            raise RetryableProviderResolutionError(
                "Instagram media resolution is temporarily unavailable."
            ) from exc

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
                raise _InstagramYtdlpBlocked(
                    f"ytdlp_ip_blocked:{type(exc).__name__}"
                ) from exc
            # Unknown yt-dlp failure — defer to Apify rather than fail outright.
            raise _InstagramYtdlpBlocked(
                f"ytdlp_download_error:{type(exc).__name__}"
            ) from exc
        except Exception as exc:
            if _looks_like_ig_ip_blocked_error(exc):
                raise _InstagramYtdlpBlocked(
                    f"ytdlp_ip_blocked:{type(exc).__name__}"
                ) from exc
            raise _InstagramYtdlpBlocked(
                f"ytdlp_unexpected:{type(exc).__name__}"
            ) from exc

        try:
            audio_result = resolve_direct_media_url(info)
        except MediaStreamUnavailableError as exc:
            # yt-dlp returned info but no usable audio stream — Apify probably
            # won't do better, but try anyway for parity with TikTok/YouTube.
            raise _InstagramYtdlpBlocked(
                f"ytdlp_no_media_stream:{exc.reason}"
            ) from exc

        caption_value = info.get("description") or info.get("title")
        caption = (
            caption_value.strip()
            if isinstance(caption_value, str) and caption_value.strip()
            else None
        )
        title_value = info.get("uploader") or info.get("channel")
        title = (
            title_value.strip()
            if isinstance(title_value, str) and title_value.strip()
            else None
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
            title=title or (caption[:100] if caption else None),
            metadata=metadata,
        )

    async def _resolve_reel(
        self,
        context: ResolveContext,
        content_type: InstagramContentType,
    ) -> ResolvedMedia:
        """Resolve a Reel or IGTV URL using the Apify Reel Scraper.

        Calls `apify/instagram-reel-scraper` and surfaces the audio URL
        (preferred) or video URL (fallback) for downstream Deepgram
        transcription. The downstream worker decides between pull and push
        modes — Instagram CDNs sometimes block Deepgram, so callers should
        use ``deepgram_mode="pull_with_push_fallback"``.
        """
        results = await self._run_actor(
            actor_id=self._reel_actor_id,
            input_data={
                "username": [context.normalized_url],
                "resultsLimit": 1,
            },
        )

        if not results:
            raise NonRetryableProviderResolutionError(
                "Unable to resolve transcribable media from this Instagram URL."
            )

        item = results[0]
        if item.get("error"):
            raise NonRetryableProviderResolutionError(
                "Unable to resolve transcribable media from this Instagram URL."
            )

        audio_url_raw = item.get("audioUrl")
        video_url_raw = item.get("videoUrl")
        audio_url = (
            audio_url_raw.strip()
            if isinstance(audio_url_raw, str) and audio_url_raw.strip()
            else None
        )
        video_url = (
            video_url_raw.strip()
            if isinstance(video_url_raw, str) and video_url_raw.strip()
            else None
        )
        # The scraper sometimes omits audioUrl on shorts where the video track
        # carries the audio inline; fall back to videoUrl so Deepgram can pull
        # the muxed stream.
        chosen_url = audio_url or video_url
        if not chosen_url:
            raise NonRetryableProviderResolutionError(
                "Unable to resolve transcribable media from this Instagram URL."
            )

        duration_seconds: Optional[float] = None
        raw_duration = item.get("videoDuration") or item.get("duration")
        if raw_duration is not None:
            try:
                duration_seconds = float(raw_duration)
            except (ValueError, TypeError):
                duration_seconds = None

        caption = _extract_caption(item)
        title_value = item.get("ownerFullName") or item.get("ownerUsername")
        title = (
            title_value.strip()
            if isinstance(title_value, str) and title_value.strip()
            else None
        )

        metadata: dict[str, Any] = {
            "resolver_version": "v4",
            "provider": "apify",
            "provider_actor": self._reel_actor_id,
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
            title=title or (caption[:100] if caption else None),
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
            provider_actor=self._reel_actor_id,
            instagram_content_type=content_type.value,
            audio_url_kind=metadata["audio_url_kind"],
        )

        return resolved

    async def _resolve_post(
        self,
        context: ResolveContext,
        content_type: InstagramContentType,
    ) -> ResolvedMedia:
        """Resolve a Post URL using the Post Scraper actor.

        Posts can be video posts, single image posts, or carousels.
        This method determines the actual content and returns the appropriate
        ResolvedMedia type.
        """
        results = await self._run_actor(
            actor_id=self._post_actor_id,
            input_data={"username": [context.normalized_url], "resultsLimit": 1},
        )

        if not results:
            raise NonRetryableProviderResolutionError(
                "Unable to resolve transcribable media from this Instagram URL."
            )

        item = results[0]
        caption = _extract_caption(item)

        # Image post (single or carousel)
        image_urls = _extract_image_urls_from_post_result(item)
        is_carousel = len(image_urls) > 1 or bool(item.get("childPosts"))

        metadata = {
            "resolver_version": "v2",
            "provider": "apify",
            "provider_actor": self._post_actor_id,
            "instagram_content_type": content_type.value,
            "post_type": "carousel" if is_carousel else "image",
            "image_urls": image_urls,
            "image_count": len(image_urls),
            "audio_url_available": False,
            "resolution_mode": "queued_worker",
            "caption": caption,
        }

        resolved = ResolvedMedia(
            media_key=context.media_key,
            normalized_url=context.normalized_url,
            media_family=MediaFamily.SOCIAL_VIDEO,
            media_type=MediaType.IMAGE_POST,
            source_platform=SourcePlatform.INSTAGRAM,
            resolver_key=self.key,
            title=caption[:100] if caption else None,
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

    async def _run_actor(
        self,
        actor_id: str,
        input_data: dict[str, Any],
    ) -> list[dict[str, Any]]:
        """
        Run an Apify actor synchronously and return the dataset items.

        Workflow:
        1. POST to start the actor run
        2. Poll GET /runs/{runId} until status is terminal
        3. GET /datasets/{datasetId}/items to retrieve results
        """
        headers = {
            "Authorization": f"Bearer {self._api_token}",
            "Content-Type": "application/json",
        }

        async with httpx.AsyncClient(timeout=self._timeout) as client:
            # Step 1: Start the actor run
            run_url = f"{APIFY_API_BASE_URL}/acts/{actor_id}/runs"
            response = await client.post(
                run_url,
                headers=headers,
                json=input_data,
            )

            if response.status_code in (401, 403):
                raise RetryableProviderResolutionError(
                    "Instagram media resolution is temporarily unavailable."
                )
            if response.status_code == 429:
                raise RetryableProviderResolutionError(
                    "Instagram media resolution is temporarily unavailable."
                )
            if response.status_code >= 500:
                raise RetryableProviderResolutionError(
                    "Instagram media resolution is temporarily unavailable."
                )
            if response.status_code >= 400:
                raise NonRetryableProviderResolutionError(
                    "Unable to resolve transcribable media from this Instagram URL."
                )

            run_data = response.json().get("data", {})
            run_id = run_data.get("id")
            if not run_id:
                raise RetryableProviderResolutionError(
                    "Instagram media resolution is temporarily unavailable."
                )

            # Step 2: Poll until the run completes
            run_status_url = f"{APIFY_API_BASE_URL}/actor-runs/{run_id}"
            dataset_id: Optional[str] = None

            for _ in range(APIFY_MAX_POLLS):
                await asyncio.sleep(APIFY_POLL_INTERVAL_SECONDS)

                status_response = await client.get(
                    run_status_url, headers=headers
                )
                if status_response.status_code != 200:
                    continue

                status_data = status_response.json().get("data", {})
                run_status = status_data.get("status", "")

                if run_status == ApifyRunStatus.SUCCEEDED:
                    dataset_id = status_data.get("defaultDatasetId")
                    break
                elif run_status in (
                    ApifyRunStatus.FAILED,
                    ApifyRunStatus.ABORTED,
                    ApifyRunStatus.TIMED_OUT,
                ):
                    raise NonRetryableProviderResolutionError(
                        "Unable to resolve transcribable media from this Instagram URL."
                    )

            if not dataset_id:
                raise RetryableProviderResolutionError(
                    "Instagram media resolution is temporarily unavailable."
                )

            # Step 3: Retrieve dataset items
            dataset_url = (
                f"{APIFY_API_BASE_URL}/datasets/{dataset_id}/items"
                "?format=json&limit=100"
            )
            dataset_response = await client.get(dataset_url, headers=headers)
            if dataset_response.status_code != 200:
                raise RetryableProviderResolutionError(
                    "Instagram media resolution is temporarily unavailable."
                )

            items = dataset_response.json()
            if not isinstance(items, list):
                items = []

            return items
