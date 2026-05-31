"""
Instagram Apify resolver -- Apify-based Instagram content extraction adapter.

Orchestrates three Apify actors to cover all Instagram content types:
- Instagram Reel Scraper: extracts video URLs for Reels/IGTV
- Instagram Post Scraper: extracts high-resolution image URLs for posts/carousels
- Instagram Comment Scraper: extracts comments with pagination

All scrapers also return the caption field for text content.

For Reels, when the Apify actor returns a `transcript` field of sufficient length
(and the feature flag is enabled), the resolver populates `ResolvedMedia.raw_text`
directly — bypassing Deepgram transcription entirely. Otherwise it falls back to
`downloadedVideo` (or `videoUrl`) as `audio_url` for Deepgram.

Environment variables:
    APIFY_API_TOKEN: API token for Apify (required)
    APIFY_INSTAGRAM_REEL_ACTOR_ID: Actor ID for Instagram Reel Scraper
        (default: apify/instagram-reel-scraper)
    APIFY_INSTAGRAM_POST_ACTOR_ID: Actor ID for Instagram Post Scraper
        (default: apify/instagram-post-scraper)
    APIFY_INSTAGRAM_COMMENT_ACTOR_ID: Actor ID for Instagram Comment Scraper
        (default: apify/instagram-comment-scraper)
    APIFY_TIMEOUT_SECONDS: Request timeout (default 60)
    APIFY_POLL_INTERVAL_SECONDS: Poll interval for actor run status (default 3)
    APIFY_MAX_POLLS: Maximum number of poll attempts (default 40)
    INSTAGRAM_TRANSCRIPT_MIN_LENGTH: Minimum transcript character count
        to accept the Apify-provided transcript (default: 20)
    INSTAGRAM_USE_APIFY_TRANSCRIPT: Feature flag to enable/disable transcript
        bypass; when false, always falls back to Deepgram (default: true)
"""

from __future__ import annotations

import asyncio
import logging
import os
from enum import Enum
from typing import Any, Optional

from urllib.parse import urlsplit

import httpx

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
from media_summarizer.utils.logging_config import log_event

logger = logging.getLogger(__name__)

APIFY_API_TOKEN = os.environ.get("APIFY_API_TOKEN", "").strip()
APIFY_API_BASE_URL = "https://api.apify.com/v2"
APIFY_INSTAGRAM_REEL_ACTOR_ID = os.environ.get(
    "APIFY_INSTAGRAM_REEL_ACTOR_ID", "apify~instagram-reel-scraper"
)
APIFY_INSTAGRAM_POST_ACTOR_ID = os.environ.get(
    "APIFY_INSTAGRAM_POST_ACTOR_ID", "apify~instagram-post-scraper"
)
APIFY_INSTAGRAM_COMMENT_ACTOR_ID = os.environ.get(
    "APIFY_INSTAGRAM_COMMENT_ACTOR_ID", "apify~instagram-comment-scraper"
)
APIFY_TIMEOUT_SECONDS = float(os.environ.get("APIFY_TIMEOUT_SECONDS", "60"))
APIFY_POLL_INTERVAL_SECONDS = float(
    os.environ.get("APIFY_POLL_INTERVAL_SECONDS", "3")
)
APIFY_MAX_POLLS = int(os.environ.get("APIFY_MAX_POLLS", "40"))

# Transcript bypass configuration (task-112)
INSTAGRAM_TRANSCRIPT_MIN_LENGTH = int(
    os.environ.get("INSTAGRAM_TRANSCRIPT_MIN_LENGTH", "20")
)
INSTAGRAM_USE_APIFY_TRANSCRIPT = os.environ.get(
    "INSTAGRAM_USE_APIFY_TRANSCRIPT", "true"
).strip().lower() in ("true", "1", "yes")


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
    """Determine Instagram content type from the URL path."""
    path = (urlsplit(normalized_url).path or "").lower()
    parts = [segment for segment in path.split("/") if segment]
    if not parts:
        raise NonRetryableProviderResolutionError(
            "Unable to determine Instagram content type from URL."
        )

    content_indicator = parts[0]
    if content_indicator == "reel":
        return InstagramContentType.REEL
    if content_indicator == "p":
        return InstagramContentType.POST
    if content_indicator == "tv":
        return InstagramContentType.IGTV
    raise NonRetryableProviderResolutionError(
        "Unable to determine Instagram content type from URL."
    )


def _is_valid_transcript(
    transcript: Optional[str],
    *,
    min_length: int = INSTAGRAM_TRANSCRIPT_MIN_LENGTH,
    use_apify_transcript: bool = INSTAGRAM_USE_APIFY_TRANSCRIPT,
) -> bool:
    """Check whether a transcript from Apify is usable."""
    if not use_apify_transcript:
        return False
    if not transcript:
        return False
    stripped = transcript.strip()
    return len(stripped) >= min_length


def _extract_video_url_from_reel_result(item: dict[str, Any]) -> Optional[str]:
    """Extract the best video URL from an Apify Reel Scraper result item."""
    # Prefer the hosted downloadedVideo (3-day TTL, reliable)
    downloaded = item.get("downloadedVideo")
    if isinstance(downloaded, str) and downloaded.strip().startswith("http"):
        return downloaded.strip()

    # Fallback to CDN videoUrl
    video_url = item.get("videoUrl")
    if isinstance(video_url, str) and video_url.strip().startswith("http"):
        return video_url.strip()

    return None


def _select_transcript_source_from_fallback(item: dict[str, Any]) -> str:
    """Determine the transcript_source label based on which video URL is used."""
    downloaded = item.get("downloadedVideo")
    if isinstance(downloaded, str) and downloaded.strip().startswith("http"):
        return "deepgram_pending"

    video_url = item.get("videoUrl")
    if isinstance(video_url, str) and video_url.strip().startswith("http"):
        return "deepgram_pending_cdn_fallback"

    return "deepgram_pending"


def _extract_video_url_from_post_result(item: dict[str, Any]) -> Optional[str]:
    """Extract video URL from an Apify Post Scraper result item (video posts)."""
    video_url = item.get("videoUrl")
    if isinstance(video_url, str) and video_url.strip().startswith("http"):
        return video_url.strip()
    return None


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


def _extract_comments(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Extract and normalize comments from Apify Comment Scraper results."""
    comments: list[dict[str, Any]] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        text = item.get("text") or item.get("comment")
        if not isinstance(text, str) or not text.strip():
            continue
        comments.append(
            {
                "text": text.strip(),
                "owner_username": item.get("ownerUsername") or item.get("owner", {}).get("username"),
                "timestamp": item.get("timestamp"),
                "likes_count": item.get("likesCount", 0),
                "replies_count": item.get("repliesCount", 0),
            }
        )
    return comments


class InstagramApifyResolver(ContentResolverPort):
    """
    Apify-based Instagram content resolver.

    Implements the ContentResolverPort interface. Orchestrates Apify actors
    to extract video URLs, image URLs, captions, and comments from Instagram
    content (Reels, Posts, Carousels, IGTV).

    Transcript bypass (task-112):
        For Reels, when the actor returns a non-empty `transcript` field meeting
        the minimum length threshold (and the feature flag is enabled), the
        resolver populates `raw_text` directly -- no Deepgram call needed.
    """

    def __init__(
        self,
        api_token: Optional[str] = None,
        timeout: Optional[float] = None,
        reel_actor_id: Optional[str] = None,
        post_actor_id: Optional[str] = None,
        comment_actor_id: Optional[str] = None,
        transcript_min_length: Optional[int] = None,
        use_apify_transcript: Optional[bool] = None,
    ):
        self._api_token = api_token or APIFY_API_TOKEN
        self._timeout = timeout or APIFY_TIMEOUT_SECONDS
        self._reel_actor_id = reel_actor_id or APIFY_INSTAGRAM_REEL_ACTOR_ID
        self._post_actor_id = post_actor_id or APIFY_INSTAGRAM_POST_ACTOR_ID
        self._comment_actor_id = comment_actor_id or APIFY_INSTAGRAM_COMMENT_ACTOR_ID
        self._transcript_min_length = (
            transcript_min_length
            if transcript_min_length is not None
            else INSTAGRAM_TRANSCRIPT_MIN_LENGTH
        )
        self._use_apify_transcript = (
            use_apify_transcript
            if use_apify_transcript is not None
            else INSTAGRAM_USE_APIFY_TRANSCRIPT
        )

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
        4. Optionally fetch comments via Comment Scraper
        5. Return ResolvedMedia with all extracted content
        """
        if not self._api_token:
            raise RetryableProviderResolutionError(
                "Instagram media resolution is temporarily unavailable."
            )

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

        try:
            if content_type == InstagramContentType.REEL:
                return await self._resolve_reel(context, content_type)
            elif content_type == InstagramContentType.IGTV:
                # IGTV uses the same Reel Scraper (video content)
                return await self._resolve_reel(context, content_type)
            else:
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

    async def _resolve_reel(
        self,
        context: ResolveContext,
        content_type: InstagramContentType,
    ) -> ResolvedMedia:
        """Resolve a Reel or IGTV URL using the Reel Scraper actor.

        If the actor returns a usable transcript (above minimum length threshold
        and feature flag enabled), bypasses Deepgram by populating raw_text directly.
        Otherwise falls back to audio_url for Deepgram transcription.
        """
        results = await self._run_actor(
            actor_id=self._reel_actor_id,
            input_data={"directUrls": [context.normalized_url]},
        )

        if not results:
            raise NonRetryableProviderResolutionError(
                "Unable to resolve transcribable media from this Instagram URL."
            )

        item = results[0]
        caption = _extract_caption(item)

        # Extract transcript from Apify result
        transcript_raw = item.get("transcript")
        transcript_text = (
            (transcript_raw or "").strip()
            if isinstance(transcript_raw, str)
            else ""
        )

        # Determine duration from Apify metadata (seconds)
        video_duration = item.get("videoDuration") or item.get("duration")
        duration_seconds: Optional[float] = None
        if video_duration is not None:
            try:
                duration_seconds = float(video_duration)
            except (ValueError, TypeError):
                duration_seconds = None

        # Fetch comments asynchronously (non-blocking for the main resolution)
        comments = await self._fetch_comments(context.normalized_url)

        # Check if we can bypass Deepgram with Apify's transcript
        if _is_valid_transcript(
            transcript_text,
            min_length=self._transcript_min_length,
            use_apify_transcript=self._use_apify_transcript,
        ):
            # Transcript bypass: skip Deepgram entirely
            transcript_source = "apify_native"
            metadata: dict[str, Any] = {
                "resolver_version": "v2",
                "provider": "apify",
                "provider_actor": self._reel_actor_id,
                "instagram_content_type": content_type.value,
                "transcript_source": transcript_source,
                "transcript_char_count": len(transcript_text),
                "audio_url_available": False,
                "resolution_mode": "apify_transcript_inline",
                "caption": caption,
                "comments": comments,
                "comments_count": len(comments),
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
                raw_text=transcript_text,
                title=caption[:100] if caption else None,
                metadata=metadata,
            )

            log_event(
                logger,
                logging.INFO,
                "instagram.reel.transcript_source",
                "Instagram reel resolved with Apify native transcript",
                source_platform=SourcePlatform.INSTAGRAM.value,
                resolver_key=self.key,
                media_type=MediaType.SHORT_VIDEO.value,
                provider="apify",
                instagram_content_type=content_type.value,
                transcript_source=transcript_source,
                transcript_char_count=len(transcript_text),
            )

            return resolved

        # Fallback: use video URL for Deepgram transcription
        video_url = _extract_video_url_from_reel_result(item)
        if not video_url:
            raise NonRetryableProviderResolutionError(
                "Unable to resolve transcribable media from this Instagram URL."
            )

        transcript_source = _select_transcript_source_from_fallback(item)

        metadata = {
            "resolver_version": "v2",
            "provider": "apify",
            "provider_actor": self._reel_actor_id,
            "instagram_content_type": content_type.value,
            "transcript_source": transcript_source,
            "audio_url_available": True,
            "resolution_mode": "provider_inline",
            "caption": caption,
            "comments": comments,
            "comments_count": len(comments),
        }
        if duration_seconds is not None:
            metadata["duration_seconds"] = duration_seconds
        if transcript_raw is not None:
            metadata["apify_transcript_available"] = bool(transcript_text)
            metadata["apify_transcript_length"] = len(transcript_text)
            metadata["apify_transcript_below_threshold"] = (
                len(transcript_text) < self._transcript_min_length
            )

        resolved = ResolvedMedia(
            media_key=context.media_key,
            normalized_url=context.normalized_url,
            media_family=MediaFamily.SOCIAL_VIDEO,
            media_type=MediaType.SHORT_VIDEO,
            source_platform=SourcePlatform.INSTAGRAM,
            resolver_key=self.key,
            audio_url=video_url,
            title=caption[:100] if caption else None,
            metadata=metadata,
        )

        log_event(
            logger,
            logging.INFO,
            "instagram.reel.transcript_source",
            "Instagram reel resolved with audio fallback for Deepgram",
            source_platform=SourcePlatform.INSTAGRAM.value,
            resolver_key=self.key,
            media_type=MediaType.SHORT_VIDEO.value,
            provider="apify",
            instagram_content_type=content_type.value,
            transcript_source=transcript_source,
            audio_url_available=True,
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
            input_data={"directUrls": [context.normalized_url]},
        )

        if not results:
            raise NonRetryableProviderResolutionError(
                "Unable to resolve transcribable media from this Instagram URL."
            )

        item = results[0]
        caption = _extract_caption(item)
        comments = await self._fetch_comments(context.normalized_url)

        # Check if this is a video post
        video_url = _extract_video_url_from_post_result(item)
        if video_url:
            # Video post -- same path as Reel (Deepgram transcription)
            metadata: dict[str, Any] = {
                "resolver_version": "v2",
                "provider": "apify",
                "provider_actor": self._post_actor_id,
                "instagram_content_type": content_type.value,
                "post_type": "video",
                "audio_url_available": True,
                "resolution_mode": "provider_inline",
                "caption": caption,
                "comments": comments,
                "comments_count": len(comments),
            }

            resolved = ResolvedMedia(
                media_key=context.media_key,
                normalized_url=context.normalized_url,
                media_family=MediaFamily.SOCIAL_VIDEO,
                media_type=MediaType.SHORT_VIDEO,
                source_platform=SourcePlatform.INSTAGRAM,
                resolver_key=self.key,
                audio_url=video_url,
                title=caption[:100] if caption else None,
                metadata=metadata,
            )

            log_event(
                logger,
                logging.INFO,
                "resolver.completed",
                "Instagram video post resolver completed via Apify",
                source_platform=SourcePlatform.INSTAGRAM.value,
                resolver_key=self.key,
                media_type=MediaType.SHORT_VIDEO.value,
                provider="apify",
                instagram_content_type=content_type.value,
                fallback_strategy="provider_inline",
            )

            return resolved

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
            "comments": comments,
            "comments_count": len(comments),
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

    async def _fetch_comments(self, url: str) -> list[dict[str, Any]]:
        """Fetch comments for an Instagram URL using the Comment Scraper actor.

        This is a best-effort operation; failures are logged but do not block
        the main resolution.
        """
        try:
            results = await self._run_actor(
                actor_id=self._comment_actor_id,
                input_data={"directUrls": [url], "resultsLimit": 50},
            )
            if results:
                return _extract_comments(results)
        except Exception as exc:
            log_event(
                logger,
                logging.WARNING,
                "external_call.failed",
                "Apify comment scraper failed (non-blocking)",
                provider="apify",
                resolver_key=self.key,
                source_platform=SourcePlatform.INSTAGRAM.value,
                error_type=type(exc).__name__,
            )
        return []

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
