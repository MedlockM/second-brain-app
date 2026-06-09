"""
Podcasts submission endpoints (backward-compatible alias for tests).

Provides /api/v1/podcasts/submit to create a processing job directly from a podcast URL
(RSS feed) and enqueue a message for downstream processing. Deducts 1 credit.
"""

import logging
import os
from typing import Optional, List
from urllib.parse import urlsplit
from fastapi import APIRouter, Depends, HTTPException, status, Request, Query
from pydantic import BaseModel, Field

from media_summarizer.api.dependencies.auth import get_current_user
from media_summarizer.core.models.auth import AuthUser
from media_summarizer.utils.database_async import get_db
from media_summarizer.utils import database_async, sqs, podcast_index
from media_summarizer.core.models import ProcessingJob
from media_summarizer.core.services import minute_pool
from media_summarizer.api.rate_limit import limiter, get_limit_from_env

router = APIRouter()
logger = logging.getLogger(__name__)

REQUIRED_MINUTES = 1
SEARCH_LIMIT = get_limit_from_env("RATE_LIMIT_PODCAST_SEARCH", "60/minute")
_AUDIO_EXTENSIONS = (".mp3", ".m4a", ".aac", ".ogg", ".wav", ".flac", ".opus")
_SPOTIFY_HOSTS = {"open.spotify.com", "www.open.spotify.com"}
_APPLE_HOSTS = {"podcasts.apple.com", "www.podcasts.apple.com"}
_DEEZER_HOSTS = {"www.deezer.com", "deezer.com"}
DEEPGRAM_TRANSCRIPTION_QUEUE = os.environ.get(
    "DEEPGRAM_TRANSCRIPTION_QUEUE", "deepgram-transcription-queue"
)
PODCASTINDEX_RESOLUTION_QUEUE = os.environ.get(
    "PODCASTINDEX_RESOLUTION_QUEUE", "podcastindex-resolution-queue"
)


def _looks_like_audio_url(url: str) -> bool:
    value = (url or "").strip().lower()
    if not value:
        return False
    try:
        split = urlsplit(value)
        path = (split.path or "").lower()
    except ValueError:
        path = value
    return path.endswith(_AUDIO_EXTENSIONS)


def _classify_podcast_source_platform(url: str) -> str:
    """Classify a podcast URL into its source platform string value.

    Maps known podcast platform hosts to their SourcePlatform enum values.
    Falls back to "rss" for unrecognized hosts (generic RSS feed URLs).
    """
    try:
        host = (urlsplit(url).hostname or "").lower()
    except ValueError:
        return "rss"

    if host in _APPLE_HOSTS:
        return "apple_podcasts"
    if host in _SPOTIFY_HOSTS:
        return "spotify"
    if host in _DEEZER_HOSTS:
        return "deezer"
    return "rss"


class PodcastSubmitRequest(BaseModel):
    podcast_url: str = Field(..., description="Podcast RSS URL or direct audio URL")
    user_email: Optional[str] = Field(None, description="User email (fallback)")


class PodcastSubmitResponse(BaseModel):
    job_id: str
    status: str


class PodcastSearchResult(BaseModel):
    """Podcast search result for frontend."""

    id: str
    title: str
    author: str
    description: str
    image: str
    feed_url: str
    website: Optional[str] = None
    categories: Optional[dict] = None
    language: Optional[str] = None
    episode_count: Optional[int] = None


class PodcastSearchResponse(BaseModel):
    """Response model for podcast search (frontend format)."""

    results: List[PodcastSearchResult]
    total: int
    page: int
    page_size: int


@router.get("/podcasts/search", response_model=PodcastSearchResponse)
@limiter.limit(SEARCH_LIMIT)
async def search_podcasts(
    request: Request,
    query: str = Query(
        ..., description="Search query for podcasts", min_length=1, max_length=500
    ),
    page: int = Query(1, description="Page number", ge=1),
    page_size: int = Query(20, description="Results per page", ge=1, le=100),
    clean: bool = Query(True, description="Filter out explicit content"),
    similar: bool = Query(True, description="Include similar matches (fuzzy search)"),
    current_user: AuthUser = Depends(get_current_user),
):
    """
    Recherche des podcasts par mot-clé via l'API Podcast Index (GET endpoint RESTful).

    Args:
        query: Terme de recherche
        page: Numéro de page (non utilisé pour l'instant, mais prévu pour pagination future)
        page_size: Nombre de résultats par page
        clean: Filtrer le contenu explicite
        similar: Inclure des résultats similaires (recherche fuzzy)

    Returns:
        Liste des podcasts trouvés au format frontend

    Raises:
        HTTPException: Si la recherche échoue
    """
    try:
        logger.info(f"Searching for podcasts with query: {query}")

        # Recherche via l'API Podcast Index
        search_result = await podcast_index.search_podcasts(
            query=query, max_results=page_size, clean=clean, similar=similar
        )

        if not search_result.get("status") == "true":
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Erreur lors de la recherche dans Podcast Index",
            )

        # Formater les résultats pour le frontend
        results = []
        for feed_data in search_result.get("feeds", []):
            formatted = podcast_index.format_podcast_for_response(feed_data)
            if formatted:
                results.append(
                    PodcastSearchResult(
                        id=str(formatted.get("id")),
                        title=formatted.get("title", ""),
                        author=formatted.get("author", ""),
                        description=formatted.get("description", ""),
                        image=formatted.get("image", ""),
                        feed_url=formatted.get("feed_url", ""),
                        website=formatted.get("link"),
                        categories=formatted.get("categories"),
                        language=formatted.get("language"),
                        episode_count=formatted.get("episode_count"),
                    )
                )

        return PodcastSearchResponse(
            results=results,
            total=len(results),
            page=page,
            page_size=page_size,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error searching podcasts: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erreur lors de la recherche de podcasts: {str(e)}",
        )


@router.post("/podcasts/submit")
async def submit_podcast_for_processing(
    payload: PodcastSubmitRequest,
    request: Request,
    db=Depends(get_db),
    current_user: AuthUser = Depends(get_current_user),
):
    """
    Backward-compatible endpoint used by integration tests to submit a podcast by URL.

    Creates a processing job, allocates a minutes hold, then enqueues a message.
    """
    try:
        # Load fresh user (support dict-like overrides in tests)
        current_user_id = getattr(current_user, "id", None) or (
            current_user.get("id") if isinstance(current_user, dict) else None
        )
        current_user_email = getattr(current_user, "email", None) or (
            current_user.get("email") if isinstance(current_user, dict) else None
        )
        if not current_user_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Authenticated user not found",
            )

        user = await database_async.get_user_by_id(current_user_id)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Authenticated user not found",
            )

        # (Removed legacy credits check) Minutes-based billing: availability enforced via minute holds.

        # Create job (pending)
        job = ProcessingJob(
            user_id=user.id,
            user_email=user.email,
            podcast_url=payload.podcast_url,
        )
        job = await database_async.create_processing_job(job)

        # Allocate minute hold (minutes-based billing)
        await minute_pool.allocate_hold_for_job(
            user_id=user.id, job_id=job.id, minutes_estimated=REQUIRED_MINUTES
        )

        submitted_url = (payload.podcast_url or "").strip()
        if _looks_like_audio_url(submitted_url):
            # Direct audio URL path: send to Deepgram worker.
            await sqs.send_message(
                queue_name=DEEPGRAM_TRANSCRIPTION_QUEUE,
                message_body={
                    "job_id": job.id,
                    "audio_url": submitted_url,
                    "user_email": user.email,
                    "user_id": user.id,
                },
            )
        else:
            # Non-audio URL path: resolve enclosure URL first, then route to Deepgram.
            # Classify the URL host to pick the correct platform-specific resolver
            # downstream (Apple Podcasts, Spotify, Deezer, or generic RSS).
            source_platform = _classify_podcast_source_platform(submitted_url)
            await sqs.send_message(
                queue_name=PODCASTINDEX_RESOLUTION_QUEUE,
                message_body={
                    "job_id": job.id,
                    "user_email": user.email,
                    "user_id": user.id,
                    "normalized_url": submitted_url,
                    "feed_url": submitted_url,
                    "source_platform": source_platform,
                },
            )

        return {"job_id": job.id, "status": job.status.value}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in /podcasts/submit: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to submit podcast",
        )
