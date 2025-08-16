"""
Endpoints pour la recherche et la sélection de podcasts via l'API Podcast Index.
"""
import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import EmailStr

from media_summarizer.utils.database_async import get_db
from media_summarizer.utils import database_async, sqs, podcast_index
from media_summarizer.core.models import User, ProcessingJob, CreditTransaction
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
REQUIRED_CREDITS = 1  # Nombre de crédits requis pour traiter un épisode





@router.post("/search", response_model=PodcastSearchResponse)
async def search_podcasts(
    request: PodcastSearchRequest
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
        logger.info(f"Searching for podcasts with query: {request.query}")

        # Recherche via l'API Podcast Index
        search_result = await podcast_index.search_podcasts(
            query=request.query,
            max_results=request.max_results,
            clean=request.clean
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
            query=request.query
        )

    except Exception as e:
        logger.error(f"Error searching podcasts: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erreur lors de la recherche de podcasts: {str(e)}"
        )


@router.post("/episodes", response_model=EpisodesListResponse)
async def get_podcast_episodes(
    request: EpisodesListRequest
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
        logger.info(f"Getting episodes for feed ID: {request.feed_id}")

        # Récupérer les épisodes directement
        episodes_result = await podcast_index.get_episodes_by_feed_id(
            feed_id=request.feed_id,
            max_results=request.max_results
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
            feed_id=request.feed_id,
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
async def submit_episode_for_processing(
    request: EpisodeSelectionRequest,
    db=Depends(get_db)
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
        logger.info(f"Processing episode submission for feed {request.feed_id}, episode {request.episode_guid}")

        # Récupérer les épisodes du feed pour trouver celui avec le GUID correspondant
        episodes_data = await podcast_index.get_episodes_by_feed_id(
            feed_id=request.feed_id,
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
            if episode.get("guid") == request.episode_guid:
                episode_info = episode
                break

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

        # Validation de l'URL audio extraite
        if not audio_url.startswith(('http://', 'https://')):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Impossible d'extraire une URL audio valide pour cet épisode"
            )

        # Récupérer ou créer l'utilisateur
        user = await database_async.get_user_by_email(request.user_email)
        if not user:
            # Créer un nouvel utilisateur avec 0 crédits
            user = User(
                email=request.user_email,
                credits=0
            )
            user = await database_async.create_user(user)

        # Vérifier que l'utilisateur a assez de crédits
        if user.credits < REQUIRED_CREDITS:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Crédits insuffisants. Vous avez {user.credits} crédits, mais {REQUIRED_CREDITS} sont nécessaires pour traiter un épisode."
            )

        # Créer le job de traitement
        try:
            logger.info(f"Creating ProcessingJob for user {user.id}")
            job = ProcessingJob(
                user_id=user.id,
                user_email=user.email,
                podcast_url=episode_info.get("feedUrl", ""),
                episode_url=audio_url,
                credits_cost=REQUIRED_CREDITS
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

        # Déduire les crédits
        new_credits = user.credits - REQUIRED_CREDITS
        await database_async.update_user_credits(user.id, new_credits)

        # Créer la transaction de déduction
        episode_title = episode_info.get("title", "Episode inconnu")
        feed_title = episode_info.get("feedTitle", "Podcast inconnu")

        transaction = CreditTransaction.create_deduction(
            user_id=user.id,
            amount=REQUIRED_CREDITS,
            job_id=created_job.id,
            description=f"Traitement de l'épisode: {episode_title}"
        )
        await database_async.create_credit_transaction(transaction)

        # Marquer les crédits comme déduits
        created_job.deduct_credits()
        await database_async.update_processing_job(created_job)

        # Envoyer directement vers la queue de download puisqu'on a déjà l'URL audio
        message_body = {
            "job_id": created_job.id,
            "user_id": user.id,
            "user_email": user.email,
            "audio_url": audio_url,
            "episode_title": episode_title,
            "podcast_title": feed_title
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
            credits_deducted=REQUIRED_CREDITS,
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
async def get_trending_podcasts(
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
