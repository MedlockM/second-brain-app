"""
Endpoints pour la recherche et la sélection de podcasts via l'API Podcast Index.
"""

import json
import logging
import os
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import EmailStr

from media_summarizer.api.dependencies.auth import (
    get_current_user,
    require_verified_email,
)
from media_summarizer.api.models.podcast_models import (
    EpisodeInfo,
    EpisodeSelectionRequest,
    EpisodeSelectionResponse,
    EpisodesListRequest,
    EpisodesListResponse,
    PodcastInfo,
    PodcastSearchRequest,
    PodcastSearchResponse,
    TrendingPodcastsRequest,
    TrendingPodcastsResponse,
)
from media_summarizer.api.rate_limit import get_limit_from_env, limiter
from media_summarizer.core.models import ProcessingJob, User
from media_summarizer.core.models.auth import AuthUser
from media_summarizer.core.services.episode_submission import submit_episode_for_user
from media_summarizer.utils import database_async, podcast_index, sqs
from media_summarizer.utils.database_async import get_db

router = APIRouter()

# Configure logging
logger = logging.getLogger(__name__)

# Configuration
DEFAULT_MINUTES_ESTIMATE = 0  # Estimation initiale (affinée plus tard)

# Per-endpoint rate limits
SEARCH_LIMIT = get_limit_from_env("RATE_LIMIT_PODCAST_SEARCH", "60/minute")
EPISODES_LIMIT = get_limit_from_env("RATE_LIMIT_PODCAST_EPISODES", "60/minute")
SUBMIT_EPISODE_LIMIT = get_limit_from_env("RATE_LIMIT_SUBMIT_EPISODE", "6/minute")
TRENDING_LIMIT = get_limit_from_env("RATE_LIMIT_PODCAST_TRENDING", "60/minute")


@router.post("/search", response_model=PodcastSearchResponse)
@limiter.limit(SEARCH_LIMIT)
async def search_podcasts(payload: PodcastSearchRequest, request: Request):
    """
    Recherche des podcasts par mot-clé via l'API Podcast Index.

    Args:
        request: Requête de recherche contenant le terme de recherche
        podcast_adapter: Adaptateur Podcast Index

    Returns:
        Liste des podcasts trouvés

    Raises:
        HTTPException: Si la recherche échoue
    """
    try:
        logger.info(f"Searching for podcasts with query: {payload.query}")

        # Recherche via l'API Podcast Index
        search_result = await podcast_index.search_podcasts(
            query=payload.query,
            max_results=payload.max_results,
            clean=payload.clean,
            similar=payload.similar,
        )

        if not search_result.get("status") == "true":
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Erreur lors de la recherche dans Podcast Index",
            )

        # Formater les résultats
        podcasts = []
        for feed_data in search_result.get("feeds", []):
            formatted_podcast = podcast_index.format_podcast_for_response(feed_data)
            if formatted_podcast:
                podcasts.append(PodcastInfo(**formatted_podcast))

        return PodcastSearchResponse(
            status="success",
            podcasts=podcasts,
            count=len(podcasts),
            query=payload.query,
        )

    except Exception as e:
        logger.error(f"Error searching podcasts: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erreur lors de la recherche de podcasts: {str(e)}",
        )


@router.post("/episodes", response_model=EpisodesListResponse)
@limiter.limit(EPISODES_LIMIT)
async def get_podcast_episodes(payload: EpisodesListRequest, request: Request):
    """
    Récupère la liste des épisodes d'un podcast.

    Args:
        request: Requête contenant l'ID du feed
        podcast_adapter: Adaptateur Podcast Index

    Returns:
        Liste des épisodes du podcast

    Raises:
        HTTPException: Si la récupération échoue
    """
    try:
        logger.info(f"Getting episodes for feed ID: {payload.feed_id}")

        # Récupérer les épisodes directement
        episodes_result = await podcast_index.get_episodes_by_feed_id(
            feed_id=payload.feed_id, max_results=payload.max_results
        )

        if not episodes_result.get("status") == "true":
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Erreur lors de la récupération des épisodes",
            )

        # Formater les épisodes
        episodes = []
        for episode_data in episodes_result.get("items", []):
            formatted_episode = podcast_index.format_episode_for_response(episode_data)
            if formatted_episode:
                episodes.append(EpisodeInfo(**formatted_episode))

        # Récupérer le titre du podcast depuis les données des épisodes
        podcast_title = ""
        if episodes and len(episodes) > 0:
            podcast_title = episodes[0].feed_title

        return EpisodesListResponse(
            status="success",
            episodes=episodes,
            count=len(episodes),
            feed_id=payload.feed_id,
            podcast_title=podcast_title,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting episodes: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erreur lors de la récupération des épisodes: {str(e)}",
        )


@router.post("/submit-episode", response_model=EpisodeSelectionResponse)
@limiter.limit(SUBMIT_EPISODE_LIMIT)
async def submit_episode_for_processing(
    payload: EpisodeSelectionRequest,
    request: Request,
    db=Depends(get_db),
    current_user: AuthUser = Depends(require_verified_email),
):
    """
    Soumet un épisode spécifique pour traitement après sélection par l'utilisateur.

    Args:
        request: Requête de soumission d'épisode
        db: Connexion à la base de données
        podcast_adapter: Adaptateur Podcast Index
        queue_adapter: Adaptateur de queue

    Returns:
        Informations sur le job créé

    Raises:
        HTTPException: Si l'utilisateur n'existe pas, n'a pas assez de crédits, ou si l'épisode n'existe pas
    """
    try:
        logger.info(
            f"Processing episode submission for feed {payload.feed_id}, episode {payload.episode_guid}"
        )

        # Récupérer les épisodes du feed pour trouver celui avec le GUID correspondant
        episodes_data = await podcast_index.get_episodes_by_feed_id(
            feed_id=payload.feed_id,
            max_results=100,  # Récupérer plus d'épisodes pour augmenter les chances de trouver le bon
        )

        if not episodes_data.get("status") == "true":
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Erreur lors de la récupération des épisodes",
            )

        # Chercher l'épisode avec le GUID correspondant
        episode_info = None
        for episode in episodes_data.get("items", []):
            if episode.get("guid") == payload.episode_guid:
                episode_info = episode
                break

        # Extraire la durée si disponible (en secondes selon PodcastIndex)
        duration_seconds = 0
        try:
            if episode_info and episode_info.get("duration") is not None:
                duration_seconds = int(episode_info.get("duration") or 0)
        except Exception:
            duration_seconds = 0

        if not episode_info:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Épisode non trouvé"
            )
        audio_url = episode_info.get("enclosureUrl")

        if not audio_url:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Aucun fichier audio trouvé pour cet épisode",
            )

        # Validation stricte de l'URL audio
        try:
            from media_summarizer.core.validators import validate_audio_url

            await validate_audio_url(audio_url)
        except ValueError as ve:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"URL audio invalide: {str(ve)}",
            )

        # Récupérer l'utilisateur authentifié
        user = await database_async.get_user_by_id(current_user.id)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Utilisateur authentifié introuvable",
            )

        # Récupérer les détails du podcast pour avoir le titre correct (absent de l'épisode parfois)
        feed_rss_url = ""
        try:
            feed_data = await podcast_index.get_podcast_by_feed_id(payload.feed_id)
            feed_title = feed_data.get("feed", {}).get("title", "Podcast inconnu")
            feed_rss_url = feed_data.get("feed", {}).get("url", "")
        except Exception as e:
            logger.warning(
                f"Failed to fetch podcast details for {payload.feed_id}: {e}"
            )
            feed_title = episode_info.get("feedTitle", "Podcast inconnu")

        # Préparer les titres pour logs/réponses/notifications
        episode_title = episode_info.get("title", "Episode inconnu")
        episode_image = episode_info.get("image", "")

        # Ensure date_published is an integer
        try:
            episode_date_published = int(episode_info.get("datePublished", 0))
        except (ValueError, TypeError):
            episode_date_published = 0

        # DEBUG LOGGING
        raw_feed_title = (
            feed_data.get("feed", {}).get("title") if "feed_data" in locals() else "N/A"
        )
        logger.info(f"DEBUG: raw_feed_title from API: '{raw_feed_title}'")

        # Ensure feed_title is string and not None
        if not feed_title:
            feed_title = "Podcast inconnu"

        # Ensure episode_title is string and not None
        if not episode_title:
            episode_title = "Episode inconnu"

        logger.info(f"DEBUG: Final feed_title: '{feed_title}'")
        logger.info(f"DEBUG: Final episode_title: '{episode_title}'")

        # Déléguer la logique au service partagé (idempotence globale, facturation, notifications)
        result = await submit_episode_for_user(
            user=user,
            episode_guid=payload.episode_guid,
            episode_title=episode_title,
            feed_title=feed_title,
            audio_url=audio_url,
            duration_seconds=duration_seconds,
            episode_image=episode_image,
            episode_date_published=episode_date_published,
            feed_url=feed_rss_url,
        )

        # Gérer le cas où l'utilisateur n'a pas assez de minutes
        if (
            result.get("status") == "skipped"
            and result.get("reason") == "insufficient_credits"
        ):
            raise HTTPException(
                status_code=status.HTTP_402_PAYMENT_REQUIRED,
                detail=result.get(
                    "message", "Crédits insuffisants pour traiter cet épisode."
                ),
            )

        return EpisodeSelectionResponse(**result)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error submitting episode: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erreur lors de la soumission de l'épisode: {str(e)}",
        )


@router.get("/trending", response_model=TrendingPodcastsResponse)
@limiter.limit(TRENDING_LIMIT)
async def get_trending_podcasts(
    request: Request,
    max_results: int = 20,
    language: Optional[str] = None,
    category: Optional[str] = None,
):
    """
    Récupère les podcasts tendances.

    Args:
        max_results: Nombre maximum de résultats
        language: Filtre de langue (optionnel)
        category: Filtre de catégorie (optionnel)
        podcast_adapter: Adaptateur Podcast Index

    Returns:
        Liste des podcasts tendances

    Raises:
        HTTPException: Si la récupération échoue
    """
    try:
        logger.info("Getting trending podcasts")

        trending_result = await podcast_index.get_trending_podcasts(
            max_results=max_results, language=language, category=category
        )

        if not trending_result.get("status") == "true":
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Erreur lors de la récupération des podcasts tendances",
            )

        # Formater les résultats
        podcasts = []
        for feed_data in trending_result.get("feeds", []):
            formatted_podcast = podcast_index.format_trending_podcast_for_response(
                feed_data
            )
            if formatted_podcast:
                podcasts.append(PodcastInfo(**formatted_podcast))

        return TrendingPodcastsResponse(
            status="success", podcasts=podcasts, count=len(podcasts)
        )

    except Exception as e:
        logger.error(f"Error getting trending podcasts: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erreur lors de la récupération des podcasts tendances: {str(e)}",
        )
