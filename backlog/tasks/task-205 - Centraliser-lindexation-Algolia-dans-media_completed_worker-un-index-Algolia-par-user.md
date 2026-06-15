---
id: task-205
title: >-
  Centraliser l'indexation Algolia dans media_completed_worker + un index
  Algolia par user
status: Done
assignee: []
created_date: '2026-06-15 14:48'
updated_date: '2026-06-15 15:09'
labels:
  - feature
  - search
  - ingestion
  - refactor
dependencies: []
priority: high
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
## Contexte

Deux problèmes liés à régler dans le même PR :

### Problème 1 — Couverture incomplète des chemins d'ingestion

La task-204 a câblé l'enqueue de SEARCH_INDEXING_QUEUE uniquement dans deepgram_worker.py. Conséquence en prod : une vidéo YouTube transcrite via le **fallback Apify** (chemin `ip_blocked_apify_fallback` dans youtube_ingestion_worker.py:777) n'est jamais indexée — la barre de recherche renvoie zéro résultat sur des mots présents dans le transcript (cas reproduit le 2026-06-15 avec le mot "cheater").

Inventaire des producteurs de transcript (chacun publie aujourd'hui `episode_completion_status` avec `transcription_s3_key`) :

| Worker | Chemin | Indexation Algolia ? |
|---|---|---|
| deepgram_worker.py | audio Deepgram | ✅ task-204 |
| document_parsing/worker.py | upload document | ✅ task-136 |
| youtube_ingestion_worker.py | native subtitles + Apify fallback | ❌ |
| tiktok_ingestion_worker.py | tous chemins | ❌ |
| instagram_ingestion_worker.py | tous chemins | ❌ |
| x_ingestion_worker.py | tous chemins | ❌ |
| article_extraction_worker.py | extraction article | ❌ |
| podcastindex_resolution_worker.py | résolution RSS | ❌ |

### Problème 2 — Un seul index Algolia partagé, filtrage logique seulement

L'implémentation actuelle (media_summarizer/core/services/search_indexing.py + utils/algolia_client.py) utilise **un seul index global** nommé `transcripts` (env `ALGOLIA_INDEX_NAME`) avec une isolation logique via `filters: "user_id:{user_id}"` (search_indexing.py:233). Au-delà de quelques milliers d'utilisateurs, l'index grossit linéairement avec tous les transcripts cumulés et chaque recherche doit scanner l'intégralité avant filtrage — coût qui devient inutile dès qu'on peut isoler physiquement.

Décision owner : **un index Algolia par utilisateur**, pour que la recherche d'un user ne touche que ses propres records.

## Solutions retenues

### Solution 1 — Centraliser l'enqueue dans media_completed_worker

Bouger l'enqueue Algolia dans **media_summarizer/workers/events/media_completed_worker.py** — le hub canonique qui consomme `episode-completed-events` et reçoit chaque `episode_completion_status` (status=success) émis par tous les workers. Il fait déjà un `database_async.get_processing_job_by_id(job_id)` dans son fan-out aux watchers, donc il dispose nativement du `user_id`, `title`, `source_platform`. Avantages :

- 1 seul point de jonction; tout nouveau chemin d'ingestion qui respecte le contrat `episode_completion_status` est automatiquement indexé.
- Permet de **supprimer** la duplication ad-hoc déjà ajoutée dans deepgram_worker.py (task-204) et document_parsing/worker.py (task-136).

### Solution 2 — Index Algolia per-user avec convention de nommage

Pattern recommandé Algolia pour multi-tenant à fort volume : **un index par tenant**, ici par utilisateur. Nommage déterministe : `transcripts_user_{user_id}` (ou un slug si user_id contient des caractères non valides — Algolia accepte `[a-zA-Z0-9_-]`). Modifier `algolia_client.get_index_name()` pour accepter un `user_id` et retourner `f"{ALGOLIA_INDEX_PREFIX}_user_{user_id}"` (prefix par défaut: `transcripts`). Toutes les opérations (`save_objects`, `delete`, `search`) passent désormais par cet index nominatif au lieu d'un index global.

Conséquences :

- `ensure_index_settings()` doit être appelé **par index** (idempotent côté Algolia, mais on doit le faire au premier index_transcript de chaque user, ou au démarrage du worker pour les users connus). Stratégie : appeler `ensure_index_settings(user_id)` avant chaque `save_objects` du worker — coût d'1 set_settings par user et par message, négligeable.
- Le filtre `user_id:{user_id}` dans search_transcripts() devient redondant — à supprimer (l'isolation physique remplace l'isolation logique). On peut garder `filters` uniquement pour `source_platform` et autres facets futures.
- `attributesForFaceting` n'a plus besoin de `user_id` — à retirer aussi.
- **Migration** : aucun backfill demandé. Les transcripts déjà indexés dans l'index global `transcripts` resteront cherchables jusqu'à suppression manuelle de l'index, mais ne seront plus consultés par le code après ce PR. L'owner pourra supprimer l'index legacy via le dashboard Algolia une fois que les nouveaux indexes per-user sont remplis. Le code n'a aucune logique de fallback vers l'index global — coupure nette.
- **Limite de plan Algolia à vérifier** : nombre max d'indexes par application. Sur le plan Build/Grow c'est généralement très permissif (>10 000) mais à confirmer dans le dashboard avant déploiement.

## Périmètre

1. **algolia_client.py** : refactorer `get_index_name()` en `get_index_name(user_id: str) -> str`. Ajouter ALGOLIA_INDEX_PREFIX (défaut `transcripts`). Retirer ALGOLIA_INDEX_NAME (cassé par convention), ou le garder pour rétrocompatibilité d'un éventuel mode "shared" derrière un feature flag — décision owner : **coupure nette, pas de feature flag**.
2. **search_indexing.py** : `index_transcript`, `_delete_chunks_for_media`, `delete_transcripts_for_media`, `search_transcripts` prennent toutes le `user_id` et l'utilisent pour résoudre l'index cible. Supprimer le filtre `user_id:{user_id}` de `search_transcripts` (redondant). Retirer `user_id` de `attributesForFaceting`.
3. **media_completed_worker.py** : après le fan-out réussi par watcher (la boucle existante autour de la ligne 93), enqueuer un message vers SEARCH_INDEXING_QUEUE avec `media_item_id`, `user_id`, `transcription_s3_key`, `title`, `source_platform`, `created_at`. **Best-effort** : log warning + ne pas échouer le traitement de l'event ni le fan-out. Skipper si `transcription_s3_key` ou `user_id` absent. Lire `transcription_s3_key` directement sur l'event (déjà présent) ou sur le ProcessingJob du watcher.
4. **deepgram_worker.py** & **document_parsing/worker.py** : supprimer les blocs d'enqueue Algolia ajoutés par task-204 et task-136.
5. **infrastructure/terraform** : vérifier que le lambda `media_completed_events` a bien `SQS:SendMessage` sur la queue search_indexing (probablement déjà OK via la policy partagée — sinon ajouter).
6. **Tests** : adapter les tests existants de search_indexing pour vérifier le nommage per-user de l'index. Ajouter un test du worker media_completed qui vérifie l'enqueue Algolia est bien fait pour un event de succès. Test E2E (manuel ou Maestro) : YouTube via Apify fallback → recherche cherche le mot dans le transcript → résultat retourné.

## Hors périmètre

- Backfill des medias historiques.
- Suppression automatique de l'ancien index `transcripts` global — l'owner le fera manuellement.
- Modifier le contrat episode_completion_status — il contient déjà tout le nécessaire.
- Quotas / observabilité du nombre d'indexes Algolia — à voir si nécessaire dans une tâche future si on dépasse plusieurs centaines d'users.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 Après une transcription réussie sur n'importe lequel des chemins d'ingestion (deepgram, document, youtube native, youtube apify, tiktok, instagram, x, article, podcastindex), un message d'indexation est enqueué vers SEARCH_INDEXING_QUEUE par media_completed_worker uniquement
- [ ] #2 Le message contient media_item_id, user_id, transcription_s3_key, title, source_platform, created_at — schéma compatible avec search_indexing_worker existant
- [ ] #3 Les blocs d'enqueue ajoutés par task-204 dans deepgram_worker.py et par task-136 dans document_parsing/worker.py sont supprimés (plus de double enqueue)
- [ ] #4 L'échec d'enqueue Algolia est journalisé en warning et n'échoue pas le traitement de l'event ni le fan-out aux watchers
- [ ] #5 Si transcription_s3_key ou user_id sont absents (ex: event de failure ou legacy), l'enqueue est skippé avec un log structuré
- [ ] #6 Chaque user dispose de son propre index Algolia nommé selon le pattern déterministe `transcripts_user_{user_id}` (préfixe configurable via ALGOLIA_INDEX_PREFIX)
- [ ] #7 search_indexing.index_transcript / delete_transcripts_for_media / search_transcripts résolvent l'index cible à partir du user_id passé en argument — plus aucun accès à un index global partagé

- [ ] #8 Le filtre `user_id:{user_id}` est retiré de search_transcripts (redondant avec l'isolation physique), et `user_id` est retiré de attributesForFaceting dans ensure_index_settings
- [ ] #9 ensure_index_settings est appelé de manière idempotente avant chaque save_objects pour garantir que les settings (searchableAttributes, attributesForFaceting, ranking) sont bien configurés sur l'index per-user
- [ ] #10 Test E2E ou intégration : un media YouTube ingéré via le fallback Apify devient cherchable dans Algolia sur un mot présent dans son transcript, et la recherche cible bien l'index per-user de l'authentifié
- [ ] #11 Aucun backfill des medias historiques n'est effectué ; l'index legacy `transcripts` global n'est pas supprimé par le code (l'owner s'en charge via le dashboard Algolia)
- [ ] #12 Aucun fallback du code vers l'ancien index global ; coupure nette une fois ce PR déployé
<!-- AC:END -->
