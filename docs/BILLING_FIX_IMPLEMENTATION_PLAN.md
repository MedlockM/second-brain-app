# Plan d'Implémentation : Correction du Système de Facturation des Minutes

## 🎯 Objectif
S'assurer que les minutes ne sont consommées **QUE SI** l'email contenant le quiz et le summary a été envoyé avec succès.

## 🐛 Problèmes Identifiés

### 1. **Ordre d'Exécution Incorrect**
**Fichier** : `media_summarizer/workers/events/episode_completed_worker.py`
- **Ligne 109** : `finalize_usage()` est appelé AVANT l'envoi de l'email
- **Ligne 134-139** : L'email est envoyé APRÈS que les minutes ont été débitées
- **Risque** : Si l'envoi échoue, les minutes sont perdues sans que l'utilisateur reçoive le contenu

### 2. **Déduplication Sans Vérification de Succès**
**Fichier** : `media_summarizer/core/services/playlist_sync.py`
- **Ligne 223** : `has_user_already_submitted()` bloque la re-soumission
- **Problème** : Même si le job a échoué, l'utilisateur ne peut pas re-soumettre l'épisode
- **Impact** : L'utilisateur a payé mais n'a rien reçu et ne peut pas réessayer

### 3. **Pas de Remboursement en Cas d'Échec**
- Aucun mécanisme de remboursement automatique si le traitement échoue
- Pas d'email explicatif envoyé à l'utilisateur

## ✅ Solutions à Implémenter

### Solution 1 : Inverser l'Ordre de Facturation
**Fichier** : `media_summarizer/workers/events/episode_completed_worker.py`

**Changements** :
1. Déplacer `finalize_usage()` APRÈS l'envoi réussi de l'email
2. Ajouter un try-catch autour de l'envoi d'email
3. Si l'envoi échoue, NE PAS finaliser l'usage et marquer le watcher comme "failed"

```python
# AVANT (ligne 109-140)
ok = await finalize_usage(job_id, minutes_used)
if not ok:
    # Handle insufficient minutes
    ...
await _notify_watcher_completion(...)
await episode_watchers.mark_watcher_emailed(...)

# APRÈS
try:
    # 1. Envoyer l'email d'abord
    await _notify_watcher_completion(
        watcher=w,
        podcast_title=podcast_title,
        episode_title=episode_title,
        summary_content=summary_content,
    )
    
    # 2. Marquer comme envoyé
    await episode_watchers.mark_watcher_emailed(episode_guid, w.get("user_id"))
    
    # 3. SEULEMENT MAINTENANT, finaliser l'usage
    ok = await finalize_usage(job_id, minutes_used)
    if not ok:
        # Si échec de facturation, envoyer email d'erreur
        logger.error(f"Failed to finalize usage for job {job_id} after email sent")
        # TODO: Implémenter un mécanisme de compensation
        
except Exception as e:
    # Si l'envoi échoue, NE PAS facturer
    logger.error(f"Failed to send email for watcher {w.get('user_id')}: {e}")
    await episode_watchers.mark_watcher_failed(episode_guid, w.get("user_id"), reason=f"email_failed: {e}")
    # Les minutes ne sont PAS débitées
```

### Solution 2 : Vérifier le Statut du Job Avant Déduplication
**Fichier** : `media_summarizer/utils/user_episode_submissions.py`

**Changements** :
1. Modifier `has_user_already_submitted()` pour vérifier aussi le statut du job
2. Autoriser la re-soumission si le job précédent a échoué

```python
async def has_user_already_submitted(user_id: str, episode_guid: str) -> bool:
    """
    Check if user has already successfully submitted this episode.
    Returns False if previous submission failed, allowing retry.
    """
    submission = await get_user_submission(user_id, episode_guid)
    if not submission:
        return False
    
    # Check if the associated job completed successfully
    job_id = submission.get("job_id")
    if job_id:
        from media_summarizer.utils import database_async
        job = await database_async.get_processing_job_by_id(job_id)
        
        if job:
            # Only block re-submission if job completed successfully
            # (status = "completed" AND no error_step)
            if job.job_status == "completed" and not job.error_step:
                return True
            else:
                # Job failed or still processing, allow retry
                logger.info(f"Previous job {job_id} failed or incomplete, allowing retry")
                return False
    
    # If we can't verify job status, be conservative and block
    return True
```

### Solution 3 : Système de Remboursement Automatique
**Nouveau fichier** : `media_summarizer/core/services/refund_service.py`

**Fonctionnalités** :
1. Fonction `refund_failed_job(job_id: str)` qui :
   - Récupère l'usage de minutes du job
   - Annule la finalisation (remet les minutes dans le bucket)
   - Envoie un email explicatif à l'utilisateur
   - Supprime l'entrée de `user_episode_submissions` pour permettre retry

```python
async def refund_failed_job(job_id: str) -> bool:
    """
    Refund minutes for a failed job and notify user.
    """
    from media_summarizer.utils import minute_db, database_async, sqs
    
    # Get job details
    job = await database_async.get_processing_job_by_id(job_id)
    if not job:
        return False
    
    # Get minute usage
    usage = await minute_db.get_minute_usage_by_job_id(job_id)
    if not usage or usage.status != "finalized":
        return False  # Nothing to refund
    
    # Refund minutes
    minutes_to_refund = usage.minutes_finalized
    buckets = await minute_db.get_minute_buckets_by_user_id(job.user_id)
    
    # Add back to the most recent bucket
    if buckets:
        bucket = buckets[0]  # Assuming sorted by created_at desc
        bucket.minutes_remaining += minutes_to_refund
        await minute_db.update_minute_bucket(bucket)
    
    # Update usage status
    usage.status = "refunded"
    await minute_db.update_minute_usage(usage)
    
    # Send refund notification email
    await sqs.send_message(
        queue_name="email-notification-queue",
        message_body={
            "notification_type": "refund",
            "job_id": job_id,
            "email": job.user_email,
            "minutes_refunded": minutes_to_refund,
            "reason": job.error_message or "Processing failed",
        }
    )
    
    # Remove from user_episode_submissions to allow retry
    # TODO: Implement this function
    
    return True
```

### Solution 4 : Worker de Nettoyage des Jobs Échoués
**Nouveau fichier** : `media_summarizer/workers/cleanup/failed_jobs_cleanup.py`

**Fonctionnalités** :
- Scan périodique des jobs avec `error_step` non-null
- Appelle `refund_failed_job()` pour chaque job échoué
- Peut être déclenché par un cron job quotidien

## 📋 Ordre d'Implémentation

1. ✅ **Solution 1** : Inverser l'ordre (critique, impact immédiat)
2. ✅ **Solution 2** : Vérifier statut avant déduplication (critique)
3. ⚠️ **Solution 3** : Système de remboursement (important, peut être fait après)
4. ⚠️ **Solution 4** : Worker de nettoyage (nice-to-have, automatisation)

## 🧪 Tests à Effectuer

1. **Test d'envoi d'email réussi** : Vérifier que les minutes sont débitées
2. **Test d'échec d'envoi** : Vérifier que les minutes NE SONT PAS débitées
3. **Test de retry après échec** : Vérifier qu'un épisode échoué peut être re-soumis
4. **Test de remboursement** : Vérifier que les minutes sont remboursées pour les jobs échoués

## 📊 Impact sur les Données Existantes

Pour l'utilisateur `test@example.com` :
- 3 jobs échoués pour l'épisode `8988b7eb-be65-4200-a737-3f314e010ca5`
- Minutes débitées : ~9 minutes (3 jobs × ~3 minutes chacun)
- **Action requise** : Exécuter le script de remboursement pour ces jobs
