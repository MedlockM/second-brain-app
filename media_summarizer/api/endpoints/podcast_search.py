"""
Endpoints pour la recherche et la sélection de podcasts via l'API Podcast Index.
"""
import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status, Request
from pydantic import EmailStr

from media_summarizer.utils.database_async import get_db
from media_summarizer.utils import database_async, sqs, podcast_index
from media_summarizer.core.models import User, ProcessingJob
from media_summarizer.api.dependencies.auth import get_current_user, require_verified_email
from media_summarizer.core.models.auth import AuthUser
from media_summarizer.api.rate_limit import limiter, get_limit_from_env
from media_summarizer.api.models.podcast_models import (
    PodcastSearchRequest,
    PodcastSearchResponse,
    PodcastInfo,
    EpisodesListRequest,
    EpisodesListResponse,
    EpisodeInfo,
    EpisodeSelectionRequest,
    EpisodeSelectionResponse,
    TrendingPodcastsRequest,
    TrendingPodcastsResponse
)

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
async def search_podcasts(
    payload: PodcastSearchRequest,
    request: Request
):
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
            clean=payload.clean
        )

        if not search_result.get("status") == "true":
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Erreur lors de la recherche dans Podcast Index"
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
            query=payload.query
        )

    except Exception as e:
        logger.error(f"Error searching podcasts: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erreur lors de la recherche de podcasts: {str(e)}"
        )


@router.post("/episodes", response_model=EpisodesListResponse)
@limiter.limit(EPISODES_LIMIT)
async def get_podcast_episodes(
    payload: EpisodesListRequest,
    request: Request
):
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
            feed_id=payload.feed_id,
            max_results=payload.max_results
        )

        if not episodes_result.get("status") == "true":
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Erreur lors de la récupération des épisodes"
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
            podcast_title=podcast_title
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting episodes: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erreur lors de la récupération des épisodes: {str(e)}"
        )


@router.post("/submit-episode", response_model=EpisodeSelectionResponse)
@limiter.limit(SUBMIT_EPISODE_LIMIT)
async def submit_episode_for_processing(
    payload: EpisodeSelectionRequest,
    request: Request,
    db=Depends(get_db),
    current_user: AuthUser = Depends(require_verified_email)
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
        logger.info(f"Processing episode submission for feed {payload.feed_id}, episode {payload.episode_guid}")

        # Récupérer les épisodes du feed pour trouver celui avec le GUID correspondant
        episodes_data = await podcast_index.get_episodes_by_feed_id(
            feed_id=payload.feed_id,
            max_results=100  # Récupérer plus d'épisodes pour augmenter les chances de trouver le bon
        )

        if not episodes_data.get("status") == "true":
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Erreur lors de la récupération des épisodes"
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
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Épisode non trouvé"
            )
        audio_url = episode_info.get("enclosureUrl")

        if not audio_url:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Aucun fichier audio trouvé pour cet épisode"
            )

        # Validation stricte de l'URL audio
        try:
            from media_summarizer.core.validators import validate_audio_url
            await validate_audio_url(audio_url)
        except ValueError as ve:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"URL audio invalide: {str(ve)}"
            )

        # Récupérer l'utilisateur authentifié
        user = await database_async.get_user_by_id(current_user.id)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Utilisateur authentifié introuvable"
            )

        # Créer le job de traitement
        try:
            logger.info(f"Creating ProcessingJob for user {user.id}")
            job = ProcessingJob(
                user_id=user.id,
                user_email=user.email,
                podcast_url=episode_info.get("feedUrl", ""),
                episode_url=audio_url
            )
            logger.info(f"ProcessingJob created successfully: {job.id}")
            logger.info(f"Job created_at: {job.created_at}")
            logger.info(f"Job data: {job.to_dynamodb_item()}")

            created_job = await database_async.create_processing_job(job)
            logger.info(f"Job saved to DynamoDB: {created_job.id}")
        except Exception as e:
            logger.error(f"Error creating or saving ProcessingJob: {str(e)}")
            logger.error(f"Error type: {type(e)}")
            raise

        # Minute-based: place an initial hold (estimated minutes)
        episode_title = episode_info.get("title", "Episode inconnu")
        feed_title = episode_info.get("feedTitle", "Podcast inconnu")

        try:
            from math import ceil
            minutes_estimated = ceil(duration_seconds / 60) if duration_seconds > 0 else DEFAULT_MINUTES_ESTIMATE
            from media_summarizer.core.services.minute_pool import allocate_hold_for_job
            await allocate_hold_for_job(user_id=user.id, job_id=created_job.id, minutes_estimated=minutes_estimated)
        except Exception as e:
            logger.warning(f"Failed to allocate minute hold for job {created_job.id}: {e}")

        # Persist job as created
        await database_async.update_processing_job(created_job)

        # Envoyer directement vers la queue de download puisqu'on a déjà l'URL audio
        message_body = {
            "job_id": created_job.id,
            "user_id": user.id,
            "user_email": user.email,
            "audio_url": audio_url,
            "episode_title": episode_title,
            "podcast_title": feed_title,
            "audio_duration_seconds": duration_seconds
        }

        try:
            logger.info(f"Sending message to audio download queue for job {created_job.id}")
            await sqs.send_message("audio-download-queue", message_body)
            logger.info(f"Successfully sent message to audio download queue for job {created_job.id}")
        except Exception as e:
            logger.error(f"Failed to send message to audio download queue for job {created_job.id}: {e}")
            # Ne pas faire échouer toute la requête si SQS échoue

        return EpisodeSelectionResponse(
            job_id=created_job.id,
            status=created_job.status.value,
            message="Épisode soumis avec succès pour traitement",
            minutes_hold_estimated=(minutes_estimated if duration_seconds > 0 else DEFAULT_MINUTES_ESTIMATE),
            estimated_processing_time="5-10 minutes",
            episode_title=episode_title,
            podcast_title=feed_title
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error submitting episode: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erreur lors de la soumission de l'épisode: {str(e)}"
        )


@router.get("/trending", response_model=TrendingPodcastsResponse)
@limiter.limit(TRENDING_LIMIT)
async def get_trending_podcasts(
    request: Request,
    max_results: int = 20,
    language: Optional[str] = None,
    category: Optional[str] = None
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
            max_results=max_results,
            language=language,
            category=category
        )

        if not trending_result.get("status") == "true":
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Erreur lors de la récupération des podcasts tendances"
            )

        # Formater les résultats
        podcasts = []
        for feed_data in trending_result.get("feeds", []):
            formatted_podcast = podcast_index.format_trending_podcast_for_response(feed_data)
            if formatted_podcast:
                podcasts.append(PodcastInfo(**formatted_podcast))

        return TrendingPodcastsResponse(
            status="success",
            podcasts=podcasts,
            count=len(podcasts)
        )

    except Exception as e:
        logger.error(f"Error getting trending podcasts: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erreur lors de la récupération des podcasts tendances: {str(e)}"
        )
