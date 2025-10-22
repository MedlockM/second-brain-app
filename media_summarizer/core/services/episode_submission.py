"""
Service partagé de soumission d'épisodes avec idempotence globale (GUID PodcastIndex),
création de jobs, facturation minutes, et notifications.

Conçu pour être appelé par les endpoints API et le futur sync Spotify.
"""
from __future__ import annotations

import os
import json
from math import ceil
from typing import Dict, Any

from media_summarizer.utils import database_async, sqs, s3, episode_idempotence, episode_watchers
from media_summarizer.core.models import ProcessingJob
from media_summarizer.core.services.minute_pool import allocate_hold_for_job, finalize_usage


async def submit_episode_for_user(
    *,
    user: Any,
    episode_guid: str,
    episode_title: str,
    feed_title: str,
    audio_url: str,
    duration_seconds: int,
    source: str = "manual",
) -> Dict[str, Any]:
    """
    Soumet un épisode pour un utilisateur avec idempotence globale.

    - Si GUID nouveau: crée un job canonique, réserve GUID, alloue minutes, envoie le message download.
    - Si GUID déjà traité: crée un job de facturation/notification, facture les minutes, envoie l'email avec résumé existant.
    - Si GUID réservé/en cours: renvoie un statut "pending" (Option B: watchers à brancher ultérieurement).

    Returns a dict compatible avec EpisodeSelectionResponse.
    """
    # Créer un job (tentatif) pour accompagner la réservation
    job = ProcessingJob(
        user_id=user.id,
        user_email=user.email,
        podcast_url="",
        episode_url=audio_url,
        episode_guid=episode_guid,
    )

    # Essayer de réserver globalement
    reserved = await episode_idempotence.reserve_or_skip(episode_guid, job.id)
    if not reserved:
        # Déjà connu globalement
        existing = await episode_idempotence.already_processed(episode_guid)
        if existing and existing.get("status") == "processed" and existing.get("job_id"):
            existing_job_id = existing.get("job_id")
            existing_job = await database_async.get_processing_job_by_id(existing_job_id)

            # Charger le résumé existant si possible
            summary_content = None
            if existing_job and getattr(existing_job, "summary_s3_key", None):
                try:
                    summary_bucket = os.environ.get("SUMMARY_BUCKET", "media-summarizer-summaries")
                    raw = await s3.download_file_to_memory(summary_bucket, existing_job.summary_s3_key)
                    try:
                        parsed = json.loads(raw.decode("utf-8"))
                        summary_content = parsed.get("summary", parsed)
                    except Exception:
                        summary_content = raw.decode("utf-8", errors="ignore")
                except Exception:
                    summary_content = None

            # Créer un job de facturation/notification pour l'utilisateur
            billing_job = ProcessingJob(
                user_id=user.id,
                user_email=user.email,
                podcast_url=getattr(existing_job, "podcast_url", ""),
                episode_url=audio_url,
                episode_guid=episode_guid,
            )
            billing_job = await database_async.create_processing_job(billing_job)

            # Facturation: allouer puis finaliser avec la durée connue (fallback min 1)
            minutes_used = max(1, ceil((duration_seconds or 0) / 60))
            await allocate_hold_for_job(user_id=user.id, job_id=billing_job.id, minutes_estimated=minutes_used)
            await finalize_usage(billing_job.id, minutes_used)

            # Envoi email (from_cache=True)
            await sqs.send_message(
                queue_name="email-notification-queue",
                message_body={
                    "notification_type": "completion",
                    "job_id": billing_job.id,
                    "email": user.email,
                    "podcast_title": feed_title,
                    "episode_title": episode_title,
                    "summary_content": summary_content,
                    "from_cache": True,
                },
            )

            return {
                "job_id": billing_job.id,
                "status": "completed",
                "message": "Résumé existant détecté — email de complétion envoyé (minutes facturées)",
                "minutes_hold_estimated": minutes_used,
                "estimated_processing_time": "0",
                "episode_title": episode_title,
                "podcast_title": feed_title,
            }

        # Pas encore traité (réservé / en cours par un autre traitement)
        # Créer un job "watcher" pour cet utilisateur, allouer un hold estimatif et enregistrer le watcher.
        minutes_estimated = ceil(duration_seconds / 60) if duration_seconds and duration_seconds > 0 else 0
        watcher_job = await database_async.create_processing_job(job)
        try:
            await allocate_hold_for_job(user_id=user.id, job_id=watcher_job.id, minutes_estimated=minutes_estimated)
        except Exception:
            # Allocation best-effort
            pass
        try:
            await episode_watchers.add_watcher(
                episode_guid=episode_guid,
                user_id=user.id,
                email=user.email,
                job_id=watcher_job.id,
                minutes_estimated=minutes_estimated,
                source=source,
            )
        except Exception:
            # Si l'ajout échoue (conditionnel), on continue quand même
            pass

        return {
            "job_id": watcher_job.id,
            "status": "pending",
            "message": "Épisode déjà soumis — traitement en cours ou réservé (vous serez notifié)",
            "minutes_hold_estimated": minutes_estimated,
            "estimated_processing_time": "quelques minutes",
            "episode_title": episode_title,
            "podcast_title": feed_title,
        }

    # Nouveau traitement canonique: persister le job et orchestrer
    # Renseigner le podcast_url si connu via episode_info côté appelant
    # (L'appelant pourra remplir podcast_url en amont si disponible)
    created_job = await database_async.create_processing_job(job)

    # Allouer minutes (estimation si durée connue)
    minutes_estimated = ceil(duration_seconds / 60) if duration_seconds and duration_seconds > 0 else 0
    try:
        await allocate_hold_for_job(user_id=user.id, job_id=created_job.id, minutes_estimated=minutes_estimated)
    except Exception:
        # Allocation best-effort
        pass

    # Persister mise à jour
    await database_async.update_processing_job(created_job)

    # Envoi du message download
    await sqs.send_message(
        queue_name="audio-download-queue",
        message_body={
            "job_id": created_job.id,
            "user_id": user.id,
            "user_email": user.email,
            "audio_url": audio_url,
            "episode_title": episode_title,
            "podcast_title": feed_title,
            "audio_duration_seconds": duration_seconds,
            "episode_guid": episode_guid,
        },
    )

    return {
        "job_id": created_job.id,
        "status": created_job.status.value,
        "message": "Épisode soumis avec succès pour traitement",
        "minutes_hold_estimated": minutes_estimated,
        "estimated_processing_time": "5-10 minutes",
        "episode_title": episode_title,
        "podcast_title": feed_title,
    }
