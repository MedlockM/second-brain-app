"""
Instagram Apify resolver -- resolves Instagram reels via the Apify reel scraper actor.

When the Apify actor returns a `transcript` field of sufficient length, this
resolver populates `ResolvedMedia.raw_text` directly (bypassing Deepgram).
Otherwise, it falls back to `downloadedVideo` (or `videoUrl`) as `audio_url`
so the orchestrator can enqueue Deepgram transcription.

For non-reel Instagram content (posts), the resolver delegates to the existing
GetInSaver-based resolution path.

Environment variables:
    APIFY_API_TOKEN: Apify API token (required for reel resolution)
    APIFY_INSTAGRAM_REEL_ACTOR_ID: Actor ID for reel scraping
        (default: apify/instagram-reel-scraper)
    INSTAGRAM_TRANSCRIPT_MIN_LENGTH: Minimum transcript character count
        to accept the Apify-provided transcript (default: 20)
    INSTAGRAM_USE_APIFY_TRANSCRIPT: Feature flag to enable/disable transcript
        bypass; when false, always falls back to Deepgram (default: true)
"""

from __future__ import annotations

import logging
import os
from typing import Any, Dict, Optional
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
    DEFAULT_INSTAGRAM_PROVIDER_BAD_REQUEST_MESSAGE,
    DEFAULT_INSTAGRAM_PROVIDER_TEMPORARY_MESSAGE,
    NonRetryableProviderResolutionError,
    RetryableProviderResolutionError,
)
from media_summarizer.core.media_ingestion.ports import ContentResolverPort
from media_summarizer.utils.logging_config import log_event

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

APIFY_API_TOKEN = os.environ.get("APIFY_API_TOKEN", "").strip()
APIFY_INSTAGRAM_REEL_ACTOR_ID = os.environ.get(
    "APIFY_INSTAGRAM_REEL_ACTOR_ID", "apify/instagram-reel-scraper"
).strip()
APIFY_API_BASE_URL = os.environ.get(
    "APIFY_API_BASE_URL", "https://api.apify.com/v2"
).rstrip("/")
APIFY_TIMEOUT_SECONDS = float(os.environ.get("APIFY_TIMEOUT_SECONDS", "60"))

INSTAGRAM_TRANSCRIPT_MIN_LENGTH = int(
    os.environ.get("INSTAGRAM_TRANSCRIPT_MIN_LENGTH", "20")
)
INSTAGRAM_USE_APIFY_TRANSCRIPT = os.environ.get(
    "INSTAGRAM_USE_APIFY_TRANSCRIPT", "true"
).strip().lower() in ("true", "1", "yes")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _instagram_content_type_from_path(normalized_url: str) -> str:
    """Determine the Instagram content type from the URL path."""
    path = (urlsplit(normalized_url).path or "").lower()
    parts = [segment for segment in path.split("/") if segment]
    if not parts:
        raise NonRetryableProviderResolutionError(
            DEFAULT_INSTAGRAM_PROVIDER_BAD_REQUEST_MESSAGE
        )
    content_type = parts[0]
    if content_type == "reel":
        return "reel"
    if content_type == "p":
        return "post"
    if content_type == "tv":
        return "igtv"
    raise NonRetryableProviderResolutionError(
        DEFAULT_INSTAGRAM_PROVIDER_BAD_REQUEST_MESSAGE
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


def _select_audio_fallback(
    actor_result: Dict[str, Any],
) -> tuple[Optional[str], str]:
    """
    Select the best audio URL from the Apify actor result.

    Returns (audio_url, transcript_source_label).
    """
    downloaded_video = (actor_result.get("downloadedVideo") or "").strip()
    if downloaded_video and downloaded_video.startswith(("http://", "https://")):
        return downloaded_video, "deepgram_pending"

    video_url = (actor_result.get("videoUrl") or "").strip()
    if video_url and video_url.startswith(("http://", "https://")):
        return video_url, "deepgram_pending_cdn_fallback"

    return None, "deepgram_pending"


async def _run_apify_reel_actor(
    *,
    url: str,
    api_token: str = APIFY_API_TOKEN,
    actor_id: str = APIFY_INSTAGRAM_REEL_ACTOR_ID,
) -> Dict[str, Any]:
    """
    Run the Apify Instagram reel scraper actor synchronously and return the
    first result item.
    """
    if not api_token:
        raise RetryableProviderResolutionError(
            DEFAULT_INSTAGRAM_PROVIDER_TEMPORARY_MESSAGE
        )

    run_url = (
        f"{APIFY_API_BASE_URL}/acts/{actor_id}/run-sync-get-dataset-items"
        f"?token={api_token}"
    )
    payload = {
        "directUrls": [url],
        "resultsLimit": 1,
    }

    try:
        async with httpx.AsyncClient(timeout=APIFY_TIMEOUT_SECONDS) as client:
            response = await client.post(run_url, json=payload)
    except (httpx.TimeoutException, httpx.TransportError) as exc:
        log_event(
            logger,
            logging.WARNING,
            "external_call.failed",
            "Apify Instagram reel actor transport failure",
            provider="apify",
            actor_id=actor_id,
            source_platform=SourcePlatform.INSTAGRAM.value,
            error_type=type(exc).__name__,
            exc_info=exc,
        )
        raise RetryableProviderResolutionError(
            DEFAULT_INSTAGRAM_PROVIDER_TEMPORARY_MESSAGE
        ) from exc

    status_code = response.status_code
    if status_code in {400, 404, 422}:
        raise NonRetryableProviderResolutionError(
            DEFAULT_INSTAGRAM_PROVIDER_BAD_REQUEST_MESSAGE
        )
    if status_code in {401, 403, 429} or status_code >= 500:
        log_event(
            logger,
            logging.WARNING,
            "external_call.failed",
            "Apify Instagram reel actor returned a transient failure",
            provider="apify",
            actor_id=actor_id,
            source_platform=SourcePlatform.INSTAGRAM.value,
            status=status_code,
        )
        raise RetryableProviderResolutionError(
            DEFAULT_INSTAGRAM_PROVIDER_TEMPORARY_MESSAGE
        )

    try:
        items = response.json()
    except ValueError:
        items = []

    if not isinstance(items, list) or not items:
        raise NonRetryableProviderResolutionError(
            DEFAULT_INSTAGRAM_PROVIDER_BAD_REQUEST_MESSAGE
        )

    first_item = items[0]
    if not isinstance(first_item, dict):
        raise NonRetryableProviderResolutionError(
            DEFAULT_INSTAGRAM_PROVIDER_BAD_REQUEST_MESSAGE
        )

    return first_item


# ---------------------------------------------------------------------------
# Resolver
# ---------------------------------------------------------------------------


class InstagramApifyResolver(ContentResolverPort):
    """
    Resolves Instagram reels via the Apify instagram-reel-scraper actor.

    Transcript bypass:
        When the actor returns a non-empty `transcript` field meeting the
        minimum length threshold (and the feature flag is enabled), the
        resolver populates `raw_text` directly -- no Deepgram call needed.

    Fallback:
        When no usable transcript is available, `audio_url` is populated with
        `downloadedVideo` (preferred) or `videoUrl` (CDN fallback).
    """

    def __init__(
        self,
        *,
        apify_api_token: Optional[str] = None,
        apify_reel_actor_id: Optional[str] = None,
        transcript_min_length: Optional[int] = None,
        use_apify_transcript: Optional[bool] = None,
    ) -> None:
        self._api_token = apify_api_token or APIFY_API_TOKEN
        self._reel_actor_id = apify_reel_actor_id or APIFY_INSTAGRAM_REEL_ACTOR_ID
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
        content_type = _instagram_content_type_from_path(context.normalized_url)

        if content_type == "reel":
            return await self._resolve_reel(context)

        # For posts/IGTV, return a deferred resolution (no inline download)
        return self._resolve_post(context, content_type)

    async def _resolve_reel(self, context: ResolveContext) -> ResolvedMedia:
        """Resolve a reel using the Apify instagram-reel-scraper actor."""
        actor_result = await _run_apify_reel_actor(
            url=context.normalized_url,
            api_token=self._api_token,
            actor_id=self._reel_actor_id,
        )

        transcript_raw = actor_result.get("transcript")
        transcript_text = (transcript_raw or "").strip() if isinstance(transcript_raw, str) else ""

        # Determine duration from Apify metadata (seconds)
        video_duration = actor_result.get("videoDuration") or actor_result.get("duration")
        duration_seconds: Optional[float] = None
        if video_duration is not None:
            try:
                duration_seconds = float(video_duration)
            except (ValueError, TypeError):
                duration_seconds = None

        if _is_valid_transcript(
            transcript_text,
            min_length=self._transcript_min_length,
            use_apify_transcript=self._use_apify_transcript,
        ):
            # Transcript bypass: skip Deepgram entirely
            transcript_source = "apify_native"
            metadata: Dict[str, Any] = {
                "resolver_version": "v1",
                "provider": "apify",
                "actor_id": self._reel_actor_id,
                "instagram_content_type": "reel",
                "transcript_source": transcript_source,
                "transcript_char_count": len(transcript_text),
                "audio_url_available": False,
                "resolution_mode": "apify_transcript_inline",
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
                transcript_source=transcript_source,
                transcript_char_count=len(transcript_text),
            )
            return resolved

        # Fallback: use downloadedVideo or videoUrl for Deepgram
        audio_url, transcript_source = _select_audio_fallback(actor_result)

        metadata = {
            "resolver_version": "v1",
            "provider": "apify",
            "actor_id": self._reel_actor_id,
            "instagram_content_type": "reel",
            "transcript_source": transcript_source,
            "audio_url_available": bool(audio_url),
            "resolution_mode": "apify_audio_fallback",
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
            audio_url=audio_url,
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
            transcript_source=transcript_source,
            audio_url_available=bool(audio_url),
        )
        return resolved

    def _resolve_post(
        self, context: ResolveContext, content_type: str
    ) -> ResolvedMedia:
        """Resolve a post/IGTV -- no transcript exposed, deferred resolution."""
        metadata: Dict[str, Any] = {
            "resolver_version": "v1",
            "provider": "apify",
            "instagram_content_type": content_type,
            "extraction_mode": "deferred_connector",
            "resolution_mode": "queued_worker",
            "source_url": context.normalized_url,
        }
        resolved = ResolvedMedia(
            media_key=context.media_key,
            normalized_url=context.normalized_url,
            media_family=MediaFamily.SOCIAL_VIDEO,
            media_type=MediaType.SHORT_VIDEO,
            source_platform=SourcePlatform.INSTAGRAM,
            resolver_key=self.key,
            metadata=metadata,
        )
        log_event(
            logger,
            logging.INFO,
            "resolver.completed",
            "Instagram post/IGTV resolver completed (deferred)",
            source_platform=SourcePlatform.INSTAGRAM.value,
            resolver_key=self.key,
            media_type=MediaType.SHORT_VIDEO.value,
            instagram_content_type=content_type,
            fallback_strategy="queued_worker",
        )
        return resolved
