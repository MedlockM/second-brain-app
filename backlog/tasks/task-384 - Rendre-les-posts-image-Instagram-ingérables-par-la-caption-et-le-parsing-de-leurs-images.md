---
id: task-384
title: >-
  Rendre les posts image Instagram ingérables par la caption et le parsing de
  leurs images
status: To Do
assignee: []
created_date: '2026-09-09 15:55'
labels:
  - backend
  - ingestion
  - feature
dependencies:
  - task-383
priority: medium
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
## Le constat

Un post photo Instagram se résout parfaitement, puis est **jeté**. `_resolve_post` (`infrastructure/resolvers/instagram_apify_resolver.py:327-401`) rend un `ResolvedMedia` complet : `media_type=IMAGE_POST`, `image_urls` (toutes les images du carrousel, dédupliquées dans l'ordre — `_extract_image_urls_from_post_result:76-116`), `image_count`, `post_type` (`image` / `carousel`), `caption`, un titre dérivé de la caption, le `creator_name` et une `cover_url`. Le worker reçoit tout cela et lève :

```python
if resolved.media_type == MediaType.IMAGE_POST:   # instagram_ingestion_worker.py:349
    ...  # "no OCR/vision pipeline exists"
    raise InstagramIngestionError(MediaFailureCode.IMAGE_POST_UNSUPPORTED, ...)  # :364
```

**La prémisse de ce refus est fausse depuis task-90.** Le parsing OCR existe et tourne : `DocumentFormat` porte `IMAGE_JPG/JPEG/PNG/TIFF/BMP/HEIF` (`core/ports/document_parser.py:18-42`, « the image formats, OCR'd by the same providers »), et `parse_document_with_fallback` (`workers/document_parsing/worker.py:122`) les envoie à LlamaParse puis à Unstructured — la décision owner de task-90 (`owner_decision: ok`, « llamaparse free tier api cloud --> fallback unstructured api »). task-70, le benchmark OCR dédié, a été **abandonné** avec ce motif : « la solution ocr sera implémentée à travers la solution de parsing (cf task 90) ». Une photo prise dans la galerie passe déjà par là. Le même octet venu d'Instagram est refusé.

La caption, elle, est déjà extraite (`_extract_caption:119`), déjà persistée sur le job, et task-383 lui construit précisément le chemin jusqu'au corpus des artefacts et de l'aperçu.

## Ce qu'on veut

Un post photo se termine en `completed` avec un transcript, comme n'importe quelle autre source.

**1. Le transcript, c'est le texte des images.** Chaque URL de `resolver_metadata["image_urls"]`, dans l'ordre du carrousel, est téléchargée puis parsée par la chaîne LlamaParse → Unstructured, et les textes obtenus sont concaténés en une section par image. Le téléchargement se fait **maintenant**, sur le callback Apify : les URLs `scontent.*.cdninstagram.com` sont signées et 403 en quelques jours (le commentaire de `instagram_ingestion_worker.py:398-401` le dit déjà pour la cover). Stocker les URLs pour parser plus tard, c'est parser du vide.

**2. La caption, c'est la description de task-383.** Elle ne se recopie pas dans le transcript : elle est déjà lue depuis `extraction_metadata.resolver_metadata.caption` et posée dans son bloc du corpus. Un post photo est le cas où la caption porte souvent l'essentiel du propos, et c'est exactement pour cela que cette tâche dépend de task-383 plutôt que de dupliquer le texte.

**3. Le cas « aucun texte » est un vrai cas, pas un bug.** Une photo de coucher de soleil ne rend rien à l'OCR. Or `_load_transcript_bytes` (`core/services/artifact_service.py:581-596`) lève `ArtifactTranscriptNotReadyError` sur un transcript vide : un job `completed` sans texte serait un média qui ne peut rien générer. La règle : **plus de texte parsé → la caption devient le corps du transcript**, et la description est alors omise pour ce job (sinon le prompt porte deux fois le même paragraphe). Ni texte parsé ni caption → échec terminal.

**4. La dépense se compte comme celle d'un document.** N images = N pages LlamaParse. C'est le même achat qu'un upload de N photos, donc le même débit : `record_document_parse` (une minute par cinq pages, `quota_enforcer.minutes_for_document_pages:190`) et la consommation du pool `POOL_LLAMAPARSE`. Aucun *gate* n'est ajouté : `check_submission_allowed` est déjà passé au partage, et le chemin document ne fait que constater après coup (`document_parsing/worker.py:514`).

**5. `IMAGE_POST_UNSUPPORTED` disparaît.** Le code n'a qu'un seul émetteur, et il n'aura plus de raison d'exister. Aucune compatibilité à garder : `_media_failure_code` (`api/endpoints/media.py:943-956`) documente déjà le cas d'un code sorti du vocabulaire et le laisse tomber, le client retombant sur sa formulation générique.

## Ce que l'implémenteur n'a pas à chercher

- **Aucun changement Terraform, aucune variable neuve.** `local.lambda_environment` est *partagé par l'API et tous les workers* (`infrastructure/terraform/modules/platform/runtime_env.tf:99-118`), donc le Lambda Instagram a déjà `TRANSCRIPT_BUCKET`, `DOCUMENT_BUCKET` et les autres. Et `LLAMAPARSE_API_KEY` / `UNSTRUCTURED_API_KEY` viennent du secret runtime, hydraté par `workers/lambda_handlers.py:26` pour tous les handlers workers.
- **Le motif de fin de course existe en double** : `x_ingestion_worker.py:461-507` (upload du transcript, `set_transcription_location`, `set_transcription_metadata`, `mark_completed`, puis événement `episode_completion_status`) et `document_parsing/worker.py:504-608`. Rien à inventer.
- **`job.media_type` se propage tout seul** à la ligne de bibliothèque : `mirror_job` recopie `media_type`, `title`, `creator_name` et `media_image` (`core/services/durable_media_service.py:446-451`).
- **Le callback Apify est déjà idempotent** : `apify_orchestration.complete_callback(job)` (`instagram_ingestion_worker.py:411-415`) est le garde que la branche reel utilise. La branche image post arrive *toujours* par un callback, puisque `resolve()` lève systématiquement `InstagramApifyRequired` depuis task-310.
- **`POST_TEXT_EMPTY` et `DOCUMENT_PARSE_FAILED` existent déjà**, avec leur phrase dans les 11 catalogues de traduction et leur place dans les 8 codes « demandables » de task-381. Aucun code neuf n'est à créer.

## Pourquoi cette tâche dépend de task-383

task-383 est ce qui fait voyager une description jusqu'au corpus. Sans elle, la caption d'un post photo n'aurait qu'un seul chemin possible : être collée dans le transcript — ce que task-383 refuse explicitement, parce que le transcript est affiché tel quel dans l'onglet lecteur. Les deux tâches touchent le même worker, et l'ordre inverse obligerait à écrire puis défaire ce collage.

## Hors périmètre

- **Le badge et le libellé côté app.** Un post photo apparaîtra avec la pastille « LINK » (`MediaListCard.tsx:343-362`, branche `default`), et son vocabulaire mobile est traité par la tâche mobile qui dépend de celle-ci.
- **Les carrousels photo TikTok**, refusés au classement (`_is_tiktok_photo_path`, `classifiers.py:231-239`). La même technique s'y appliquerait, mais l'URL n'est même pas acceptée aujourd'hui : c'est un autre périmètre.
- **Les vidéos d'un carrousel mixte.** `image_urls` ne porte que des images ; une vidéo glissée dans un carrousel n'est pas transcrite ici.
- **Le stockage des images.** Seule la cover est ré-hébergée, comme aujourd'hui. Les images parsées ne sont pas conservées.

## Notes à l'owner (pas des ACs)

1. **La validation réelle demande un déploiement puis un E2E** : partager un post `/p/` photo simple, puis un carrousel, sur `-dev`. Attendu : l'item se termine, son transcript porte le texte des images, l'aperçu et un résumé s'appuient dessus et sur la caption. L'implémenteur ne peut vérifier que le câblage.
2. **Une re-soumission de la même URL est bloquée par la dédup** : prévoir un lien neuf ou rejouer le message SQS.
3. **Le quota LlamaParse est un pool partagé** (15 000 pages gratuites au départ, task-90). Un carrousel consomme autant de pages qu'il a d'images : c'est la première source capable d'en brûler plusieurs d'un coup. À surveiller sur l'alarme du pool.
4. **Si l'acteur Apify rend des URLs `.webp`**, `DocumentFormat` n'a pas ce membre : le log de parsing le dira. Le choix serait alors d'ajouter le format ou de convertir avant l'envoi — à décider sur une observation réelle, pas maintenant.
5. **Deux docs de test utilisent le post photo Instagram comme moyen de provoquer un échec « demandable »** (`docs/testing/manual-e2e-validation-matrix.md:217`, `mobile/MANUAL_TEST_CHECKLIST.md:221`). Cette tâche remplace le scénario côté matrice ; le checklist mobile est corrigé par la tâche mobile.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 `parse_document_with_fallback` et le décompte de consommation (`_record_document_consumption`) vivent dans un module partagé sous `core/services/`, appelés depuis là par le worker document comme par le worker Instagram. Aucun worker n'importe un autre worker.
- [x] #2 Sur `MediaType.IMAGE_POST`, le worker Instagram télécharge chaque URL de `resolver_metadata["image_urls"]` dans l'ordre du carrousel vers un fichier temporaire et la parse par la chaîne partagée. Rien n'est téléchargé plus tard que le callback Apify : un commentaire dit que les URLs `scontent.*.cdninstagram.com` sont signées et expirent.
- [x] #3 Le `DocumentFormat` de chaque image est déduit du suffixe de son chemin d'URL ; un suffixe absent ou inconnu de l'enum est parsé comme `IMAGE_JPG`, avec un commentaire disant pourquoi (le `displayUrl` du post scraper sert du JPEG).
- [x] #4 Le transcript est le texte parsé des images, une section par image dans l'ordre du carrousel, uploadé dans `TRANSCRIPT_BUCKET` sous la clé du job, puis `set_transcription_location` + `set_transcription_metadata` (provider, nombre d'images parsées, `duration_seconds: 0`, source) + `mark_completed` + événement `episode_completion_status`, sur le motif de `x_ingestion_worker.py:461-507`.
- [x] #5 La caption n'est jamais recopiée dans le transcript quand des images ont rendu du texte : elle voyage par la description de task-383. Le prompt d'un post photo ne porte donc pas deux fois le même paragraphe.
- [x] #6 Quand aucune image ne rend de texte — OCR vide ou parsing en échec sur toutes — et qu'une caption existe, la caption devient le corps du transcript et la description est omise pour ce job. Le média se termine normalement.
- [x] #7 Sans texte parsé et sans caption, le job échoue en terminal : `POST_TEXT_EMPTY` si le parsing a réussi mais n'a rien rendu, `DOCUMENT_PARSE_FAILED` si les deux providers ont échoué. Aucun membre n'est ajouté à `MediaFailureCode`.
- [x] #8 Le parsing est facturé une fois par job comme un document : `record_document_parse` avec `page_count` = nombre d'images parsées, et `provider_pool_guard.record_spend(POOL_LLAMAPARSE)` quand LlamaParse a fait le travail. Les deux sont idempotents sur l'id du job (`quota_enforcer.gate_token`), et un échec de compteur ne fait pas échouer une ingestion réussie.
- [x] #9 Aucun gate de quota n'est ajouté sur ce chemin : le débit est constaté après le parsing, comme sur le chemin document (`document_parsing/worker.py:514`). Un commentaire dit que `check_submission_allowed` est déjà passé au partage.
- [x] #10 La branche image post passe par `apify_orchestration.complete_callback(job)` comme la branche reel (`instagram_ingestion_worker.py:411-415`) : un callback Apify redélivré ne re-parse pas, ne re-uploade pas et ne re-débite pas.
- [x] #11 La cover vient de `cover_capture.capture_from_url` sur la `cover_url` du resolver (la première image), le même appel que la branche reel : aucune URL CDN signée n'est stockée sur la ligne de bibliothèque.
- [x] #12 Le worker pose `job.media_type` à `image_post` avant de terminer, de sorte que la ligne de bibliothèque cesse de décrire un post photo comme une vidéo (le mirror recopie `media_type`, `durable_media_service.py:446-451`).
- [x] #13 `_LEGACY_MEDIA_TYPE_MAP` (`api/endpoints/media.py:672-680`) mappe `image_post`, si bien que l'endpoint de détail sert un `MediaType` canonique au lieu de `unknown`.
- [x] #14 `MediaFailureCode.IMAGE_POST_UNSUPPORTED` est supprimé de `failure_codes.py:44` et de tous ses sites backend ; `grep -rn IMAGE_POST_UNSUPPORTED media_summarizer/` ne renvoie plus rien. Rien n'est conservé pour les lignes déjà écrites en base : `_media_failure_code` les laisse tomber par contrat.
- [x] #15 Le commentaire de `share_targets.py:123-128` ne dit plus que les posts photo ne sont pas offerts, et celui de `_is_tiktok_photo_path` (`classifiers.py:236`) ne renvoie plus au « même traitement » que les posts image Instagram.
- [x] #16 `docs/INGESTION_WORKERS_PROVIDERS.md` (:317, :356, :360, :858) et `docs/CANONICAL_MEDIA_API_CONTRACT.md:234` décrivent le chemin réel des posts image et ne citent plus `IMAGE_POST_UNSUPPORTED`.
- [x] #17 Les lignes MD-25 et MD-26 de `docs/testing/manual-e2e-validation-matrix.md:217-218` n'utilisent plus le post photo Instagram pour produire un échec « demandable » : elles nomment un autre des 8 codes qu'un testeur peut réellement provoquer.
- [ ] #18 Une vérification directe contre `-dev` est consignée dans les Implementation Notes : sur un job de post photo réel, `extraction_metadata.resolver_metadata.image_urls` est bien peuplée en base (`aws dynamodb ... --region eu-west-3` — `AWS_REGION` du shell pointe ailleurs). C'est la prémisse dont dépend tout le chemin de parsing.
- [x] #19 `ruff check` et `mypy` passent sur `media_summarizer/`.
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
18 of the 19 ACs are done. **AC #18 stays unchecked**, and the reason is not a
missing effort but a missing row: `-dev` has never held a photo-post job.

What was actually run against real `-dev` DynamoDB (region passed explicitly,
because the shell's `AWS_REGION` points elsewhere):

```
aws dynamodb scan --table-name processing_jobs-dev --region eu-west-3 \
  --projection-expression "source_url,media_type,source_platform"
aws dynamodb scan --table-name processing_jobs-dev --region eu-west-3 \
  --filter-expression "source_platform = :p" \
  --expression-attribute-values '{":p":{"S":"instagram"}}' \
  --projection-expression "extraction_metadata,job_status"
aws dynamodb scan --table-name user_media-dev --region eu-west-3 \
  --projection-expression "media_type"
```

- 77 jobs in `processing_jobs-dev`, 15 of them Instagram, and **all 15 are `/reel/`
  URLs — zero `/p/`**. There is no row whose
  `extraction_metadata.resolver_metadata.image_urls` could be read back.
  `user_media-dev` (76 rows) confirms it from the other side: media types are only
  `document`, `article`, `short_video`, `youtube_video`, `podcast_episode`,
  `audio_file` — no `image_post`, and no job in the table carries an
  `IMAGE_POST_UNSUPPORTED` code either.
- The premise could not have been satisfied even if a photo post had been shared:
  the refusal path this task deletes went through `_mark_job_failed`, which rewrites
  `extraction_metadata` **without** `resolver_metadata`. The image URLs were
  computed by the resolver and dropped by the failure handler before any write. The
  same scan shows this directly: of the 15 Instagram jobs, the 13 `completed` ones
  carry a `resolver_metadata` map and the 2 `failed` ones carry none.

What *was* verified directly instead, on the same table, and is the closest true
statement to what AC #18 wanted: on those 13 completed Instagram jobs,
`extraction_metadata.resolver_metadata` round-trips intact through DynamoDB — the
observed keys are `audio_url_available`, `audio_url_kind`, `caption`,
`duration_seconds`, `instagram_content_type`, `provider`, `provider_actor`,
`resolution_mode`, `resolver_version`, `transcript_source`. The map the new code
reads `image_urls` from is therefore stored and returned verbatim; `_resolve_post`
puts `image_urls` in that same map. Confirming it on a real photo post requires a
deploy and one share, which is owner note #1 of this task.

### One deviation from the description

The description states "no Terraform change". That was wrong, and following it
would have shipped a path that dies on every carousel: the `instagram_ingestion`
Lambda had a **60 s** timeout, while a single LlamaParse upload-then-poll can take
up to 120 s. `modules/platform/lambda_workers.tf` now gives that function 300 s,
with a comment explaining the workload, the worker's own 240 s parsing budget and
why 300 s stays under the queue's 360 s visibility timeout (a redelivery must not
overlap a running invocation). `terraform plan` against dev shows exactly this and
nothing else from this task:

```
# module.platform.aws_lambda_function.worker["instagram_ingestion"] will be updated in-place
~ timeout = 60 -> 300
```

(The plan's two other diffs — a `BugReportCreated` metric filter to add and
`job_archiver`'s `source_code_hash` — are pre-existing drift, untouched here.)

The env-var half of that claim held: `TRANSCRIPT_BUCKET` and the parser keys were
already on this Lambda through the shared `local.lambda_environment`.

### Also corrected, because the change made them false

- `quota_enforcer.py` and `pricing_config_service.py` both listed "Instagram photo
  posts" among the paths that cost zero minutes. They now bill at the document rate.
- `docs/MEDIA_INGESTION_CORE_ARCHITECTURE.md` said the worker fails image posts
  with `unsupported_content`, and repeated the free-list claim.
- `docs/CANONICAL_MEDIA_API_OPENAPI.yaml` had a stale `media_type` enum; `image_post`
  is added, and the two enums are resynced with the canonical models.
- Matrix rows S7/IN-29 used the photo post as a failure fixture. IN-29 and MD-25 now
  use a direct image-file URL, which fails `NOT_AN_ARTICLE_PAGE` in the article
  worker — a code that is in task-381's requestable list, so MD-25 still tests what
  it was written to test. S7b is the new photo-post success row.

### Not done, on purpose

**No automated test was added** (this project forbids them unless explicitly
requested). Nothing in the ACs asked for one, so nothing was skipped for it.
<!-- SECTION:NOTES:END -->
