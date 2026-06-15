---
id: task-208
title: >-
  Migrate /api/media/ingest-url to IngestUrlUseCase and delete legacy URL
  ingestion path
status: To Do
assignee: []
created_date: '2026-06-15 15:44'
labels:
  - cleanup
  - refactor
  - backend
  - bug
dependencies: []
priority: high
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
## Contexte

Le 15 juin 2026, lors du test post-task-205, une recherche Algolia sur "Australia" (mot présent dans un transcript YouTube ingéré via le fallback Apify) a retourné zéro résultat. Investigation : le worker `media_completed_events` reçoit un event `episode_completion_status` avec `media_key: None` et bail-out immédiatement (`if not media_key: return`), donc :
- le fan-out aux watchers ne se fait pas (les minutes ne sont jamais finalisées sur `finalize_usage`),
- l'enqueue Algolia (le hub canonique introduit par task-205) n'a jamais lieu → l'index `transcripts_user_<uid>` n'est jamais créé,
- le mark_watcher_processed n'est jamais appelé → l'inbox peut rester en état "in-flight" côté UI (à confirmer).

### Cause racine

Deux chemins de submission coexistent dans le backend :

1. **Pipeline hexagonal canonique** — `IngestSharedContentUseCase` + `IngestUrlUseCase` + `Orchestrator.submit` (dans `media_summarizer/core/media_ingestion/`). C'est ce chemin qui calcule `derive_media_identity(raw_url) -> (normalized_url, media_key)` et passe `media_key=resolved.media_key` aux producteurs SQS.
2. **Legacy** — `/api/media/ingest-url` dans `media_summarizer/api/endpoints/media.py:502-668` qui contourne le use_case : il instancie directement un `ProcessingJob`, crée un `base_payload` SQS sans `media_key`, et fait des `sqs.send_message` selon `source_platform` détecté à la main. Conséquence : tous les workers (YouTube, TikTok, Instagram, X, Article, Deepgram audio direct, PodcastIndex) reçoivent `message_body["media_key"]` à None et le propagent jusqu'à l'event de complétion.

`/api/media/ingest-shared-content` utilise déjà le use_case correctement (cf. media.py:1197-1198). Seul `/ingest-url` n'a jamais été migré.

### Décision owner

Migrer `/ingest-url` sur `IngestUrlUseCase` (option A), et supprimer **tout** le code legacy de l'endpoint et alentours. Pas de feature flag, coupure nette.

## Solution

### 1. Migrer le handler

Remplacer le corps de `ingest_url()` (`media.py:502-668`) par :
- Validation HTTP (auth, folder ownership, tag ownership, quotas) — reste à l'endpoint car ce sont des concerns HTTP/4xx
- Construction `IngestUrlCommand(user=UserContext(...), request=IngestUrlRequest(url, folder_id, tag_ids, locale, transcript_language, source_app, idempotency_key))`
- `outcome = await build_default_ingest_url_use_case().execute(command)`
- `record_submission(...)` post-execute (quota usage)
- Retour `IngestUrlResponse(media_item_id=outcome.media_item_id, status=outcome.status.value, source_platform=outcome.metadata[...])` (vérifier que `outcome.metadata` ou un champ direct expose source_platform — sinon, le récupérer autrement, ou ajouter un champ `source_platform` à `IngestionOutcome` si nécessaire)

### 2. Étendre le domain pour porter folder_id et tag_ids

`IngestUrlRequest` (domain.py:71-76) doit gagner :
```python
folder_id: Optional[str] = None
tag_ids: Optional[List[str]] = None
```

`Orchestrator.submit` (orchestrators.py:151+) doit appliquer ces deux champs sur le `ProcessingJob` avant `database_async.create_processing_job(job)` :
```python
job = ProcessingJob(...)
if isinstance(command, IngestUrlCommand):
    if command.request.folder_id:
        job.folder_id = command.request.folder_id
    if command.request.tag_ids:
        job.tag_ids = list(dict.fromkeys(command.request.tag_ids))
```

### 3. Déplacer allocate_hold_for_job dans l'orchestrator

`minute_pool.allocate_hold_for_job` est appelé dans le code legacy juste après la création du job, avant l'enqueue. Il doit migrer dans `Orchestrator.submit` au même point (juste après `database_async.create_processing_job(job)`, avant les branches d'enqueue). Constante `REQUIRED_MINUTES` à exposer depuis `media_summarizer.core.constants` ou équivalent (vérifier où elle est définie aujourd'hui dans `api/endpoints/media.py`).

Ce déplacement assure que tout media créé via le pipeline hexagonal — pas seulement `/ingest-url` — bénéficie de l'allocation. C'est un changement de contrat de l'orchestrator : à documenter dans le docstring de `submit`. Vérifier que `/ingest-shared-content` n'a pas un `allocate_hold_for_job` redondant ailleurs (probablement non — vérifier).

### 4. Supprimer le code legacy

Dans `media_summarizer/api/endpoints/media.py` :
- Tout le bloc `source_platform == "youtube"` ... `else: send_message(PODCASTINDEX_RESOLUTION_QUEUE)` (lignes 559-635) → remplacé par `use_case.execute()`.
- L'helper `_detect_platform()` s'il n'est plus utilisé ailleurs (`grep -rn _detect_platform`).
- Le mapping local `_platform_to_media_type` (lignes 559-567).
- L'instanciation manuelle de `ProcessingJob(...)` (lignes 569-576).
- L'appel direct à `database_async.create_processing_job(job)` (ligne 599).
- L'appel direct à `minute_pool.allocate_hold_for_job` (ligne 601-605) — déplacé dans l'orchestrator.
- Les imports de queues SQS au module scope si plus utilisés (`YOUTUBE_INGESTION_QUEUE`, `TIKTOK_INGESTION_QUEUE`, `INSTAGRAM_INGESTION_QUEUE`, `ARTICLE_EXTRACTION_QUEUE`, `PODCASTINDEX_RESOLUTION_QUEUE` — `DEEPGRAM_TRANSCRIPTION_QUEUE` reste si utilisé par d'autres handlers du même fichier, à vérifier).
- L'import de `sqs` si plus utilisé dans ce fichier.
- Le bloc `folder validation` (532-544) reste pour valider en amont l'ownership du folder (HTTP 400) — mais NE PAS forcer le default folder ici si le use_case est censé le faire ; à clarifier pendant l'impl.
- Le bloc `tag validation` (578-597) reste pour valider l'ownership et la limite `MAX_TAGS_PER_MEDIA` (HTTP 400).

### 5. Vérifier les call sites de `IngestUrlRequest`

`grep -rn "IngestUrlRequest\|IngestUrlCommand"` pour s'assurer qu'aucun autre call site (tests, docs) ne casse avec les deux nouveaux champs optionnels.

### 6. Tests

- Adapter les tests existants de `/api/media/ingest-url` (s'il y en a) pour vérifier que le payload SQS contient bien `media_key` non-null pour les 6 sources : youtube, tiktok, instagram, audio direct, web/article, podcast.
- Ajouter (si possible sans dépendre du runtime AWS) un test du `Orchestrator.submit` qui vérifie que `allocate_hold_for_job` est appelé exactement une fois avec les bons args, et que `folder_id`/`tag_ids` du command remontent bien sur le `ProcessingJob` persisté.

## Hors périmètre

- Modifier la logique de bail-out `if not media_key: return` dans `media_completed_worker` — elle est correcte, c'est juste l'amont qui était cassé.
- Modifier les workers eux-mêmes (`youtube_ingestion_worker`, etc.) — ils continuent de propager `message_body.get("media_key")`, ce qui suffit une fois que le producteur le passe.
- Backfill des médias ingérés avec `media_key=None` avant ce fix — l'owner décidera s'il faut les ré-ingérer manuellement.
- Toucher `/api/media/ingest-shared-content` (déjà sur le bon chemin).
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 Aucun call site de `/api/media/ingest-url` ne contourne le pipeline hexagonal; le handler appelle `build_default_ingest_url_use_case().execute(command)` et n'instancie plus directement `ProcessingJob` ni n'appelle `sqs.send_message` selon source_platform.
- [ ] #2 `IngestUrlRequest` (domain) accepte `folder_id: Optional[str]` et `tag_ids: Optional[List[str]]` ; ces deux champs sont propagés à `ProcessingJob.folder_id` et `ProcessingJob.tag_ids` par `Orchestrator.submit` avant `create_processing_job`.
- [ ] #3 `Orchestrator.submit` invoque `minute_pool.allocate_hold_for_job` exactement une fois, juste après `database_async.create_processing_job(job)`, pour tout type de command (IngestUrlCommand et IngestSharedContentCommand).
- [ ] #4 Pour les 6 sources (youtube, tiktok, instagram, audio direct, web/article, podcast), le message SQS produit par l'orchestrator contient `media_key=resolved.media_key` non-null — vérifié par lecture de logs CloudWatch ou test unitaire.
- [ ] #5 L'event `episode_completion_status` publié par chacun des workers (youtube, tiktok, instagram, x, article, deepgram, podcastindex) contient `media_key` non-null pour toute ingestion passée par /ingest-url ; `media_completed_worker` ne log plus `Missing media_key in event`.
- [ ] #6 Le code legacy supprimé de `media.py` : bloc `if source_platform == 'youtube'/.../else PODCASTINDEX_RESOLUTION_QUEUE`, instanciation manuelle de ProcessingJob dans le handler ingest-url, appel direct à allocate_hold_for_job dans le handler, mapping local _platform_to_media_type, helpers `_detect_platform` (si plus utilisé ailleurs), imports inutiles de constantes de queue.
- [ ] #7 Validation HTTP préservée : folder ownership (HTTP 400 si folder absent ou pas owned), tag ownership + MAX_TAGS_PER_MEDIA (HTTP 400), quotas via check_submission_allowed (HTTP custom selon quota_result), record_submission après succès du use_case. Pas de régression sur les codes HTTP renvoyés.
- [ ] #8 Endpoint `/api/media/ingest-shared-content` non touché (sauf si correction collatérale nécessaire pour cohérence du domain).
- [ ] #9 Aucun test existant ne casse ; les tests qui asseraient sur l'absence de `media_key` dans le payload SQS sont mis à jour.
- [ ] #10 Une ingestion YouTube (avec ou sans fallback Apify) post-déploiement produit un transcript indexé dans Algolia — vérifié via les logs `media_completed_events` (pas de bail-out 'Missing media_key') et via la barre de recherche mobile (le mot du transcript ressort).
<!-- AC:END -->
