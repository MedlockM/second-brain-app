---
id: task-111
title: >-
  Remove download_worker: route podcasts directly to Deepgram via audio_url (RSS
  enclosure)
status: To Do
assignee: []
created_date: '2026-05-30 21:48'
labels:
  - ingestion
  - cleanup
  - feature
dependencies: []
priority: medium
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
## Contexte

Aujourd'hui, le path d'ingestion podcast passe systématiquement par `media_summarizer/workers/download_worker.py` qui :

1. **Step utile** — fetch le feed RSS et cherche un tag `<podcast:transcript>` (Podcasting 2.0). Si trouvé, upload le transcript S3 et **skip Deepgram complètement** (économie 0,003 €/min). Cf. task-55 (Done).
2. **Step inutile** — sinon : télécharge le MP3 via `httpx.AsyncClient.stream("GET", url)` → upload S3 → enfile à `deepgram-transcription-queue` avec `audio_s3_key`. Le `deepgram_worker.py:380-389` ouvre alors le MP3 depuis S3 et l'envoie à Deepgram.

**Le step 2 est redondant** :

- `deepgram_worker.py:362-389` accepte déjà `audio_url` directement et envoie un payload `{"url": audio_url}` à Deepgram (ligne 172) — c'est exactement ce que font YouTube/TikTok/Instagram resolvers.
- L'URL des enclosures RSS pointe vers le CDN du podcaster, qui sert des MP3 publics avec des `Content-Type` standards. Deepgram pull lui-même le contenu.
- Aucun transcodage ni détection de format n'est fait par `download_worker` (`grep -E "ffmpeg|ffprobe|subprocess" media_summarizer/` ne retourne rien).
- Le bucket `media-summarizer-audio` n'est utilisé nulle part en aval pour la re-transcription en pratique : c'est du stockage mort.

Le complement-response du benchmark `docs/research/task-105-lambda-migration/README.md` (généré le 2026-05-30) confirme cette analyse.

**Décision retenue** : on supprime `download_worker` intégralement. Tous les podcasts (RSS + recherche manuelle) passent par le path nominal `MediaFamily.AUDIO + audio_url → deepgram-transcription-queue` comme les autres connecteurs.

## Scope d'implémentation

### 1. Déplacer le RSS transcript lookup

Le step utile (lookup `<podcast:transcript>`) doit migrer hors de `download_worker`. Choisir entre :

- **Option A (préférée)** : appel synchrone inline dans `media_submission.py:submit_media_for_user()` **avant** la décision d'enqueue. Si transcript RSS trouvé : upload S3, mark `transcribing` puis `completed`, publish completion event, skip Deepgram. Sinon : enqueue normalement avec `audio_url` dans `deepgram-transcription-queue`. Avantage : zéro queue intermédiaire.
- **Option B** : nouveau worker léger `rss_transcript_lookup_worker` consommant une nouvelle queue `rss-transcript-lookup-queue`. Avantage : conserver l'asynchronisme, mais ajoute complexité.

L'option A est la cible par défaut sauf raison forte de garder de l'async (coût `httpx.get` sur le feed = quelques centaines de ms, acceptable inline).

### 2. Câbler le dispatch podcast en path direct

Dans `media_summarizer/core/services/media_submission.py:215` (et `rss_feed_poll_worker.py:75`), remplacer l'enqueue vers `audio-download-queue` par un enqueue direct vers `deepgram-transcription-queue` avec `audio_url` (et **sans** `audio_s3_key`).

Vérifier que l'orchestrator (`adapters/orchestrators.py:362-422` pour les paths `audio_url` directs) gère déjà cette branche pour `MediaFamily.AUDIO` ; sinon ajouter le case.

### 3. Supprimer download_worker et ses dépendances

- Supprimer `media_summarizer/workers/download_worker.py`.
- Supprimer la queue `audio-download-queue` (Terraform `infrastructure/terraform/scaling.tf:289`, LocalStack `infrastructure/localstack/init-aws.sh:179, 214, 320`, `infrastructure/terraform/localstack/main.tf:648, 937`).
- Supprimer la task definition ECS `audio-download-queue` correspondante dans `scaling.tf` (la map `aws_ecs_task_definition.ephemeral_worker["download"]`).
- Retirer les références dans `scaling_controller` (lambda Python qui décide combien de tasks ECS lancer par queue).
- Conserver le bucket S3 `media-summarizer-audio` **uniquement** s'il a un autre usage actif, sinon supprimer la ressource Terraform et l'env var `AUDIO_BUCKET`.

### 4. Adapter le path `deepgram_worker` si nécessaire

Le worker accepte déjà `audio_url` (`deepgram_worker.py:362-389`). Vérifier que :
- La branche `audio_s3_key` peut être conservée pour les uploads directs (`api/endpoints/media.py` upload de fichier audio personnel) — **ne pas la supprimer**.
- Le tracking `set_audio_location()` côté `ProcessingJob` n'est pas utilisé en aval critique pour les podcasts (sinon adapter).

### 5. Adapter le minutes hold

Aujourd'hui dans `media_submission.py`, `allocate_hold_for_job` est appelé avec `minutes_estimated = ceil(duration_seconds / 60)`. Vérifier que la durée est **toujours** disponible à la submission pour les podcasts (les enclosures RSS exposent `<itunes:duration>`). Si `duration_seconds=0`, garder le fallback `minutes_estimated=0` actuel, le finalize corrigera.

### 6. Tests

- Tests unitaires sur le path RSS transcript lookup déplacé (3 cas : transcript trouvé / pas trouvé / fetch fail).
- Tests d'intégration vérifiant que la submission d'un podcast enfile bien vers `deepgram-transcription-queue` avec `audio_url` et plus du tout vers `audio-download-queue` (qui n'existe plus).
- Vérifier qu'un job complet `pending → resolving → transcribing → completed` fonctionne end-to-end avec un podcast réel (URL CDN MP3 publique).

### 7. Documentation

- Mettre à jour `docs/MEDIA_INGESTION_CORE_ARCHITECTURE.md` (section ingestion podcasts) pour refléter le nouveau flow direct.
- Mettre à jour `docs/V1_LAUNCH_PLAN.md` si la queue `audio-download-queue` y est mentionnée.
- Retirer toute mention de `download_worker` / `audio-download-queue` dans la doc.

## Hors-scope

- Le path d'upload de fichier audio personnel (`api/endpoints/media.py` POST upload) qui passe par `audio_s3_key` reste inchangé — c'est légitime d'avoir un S3 pour les fichiers user.
- La migration Lambda (task-105/106) reste indépendante : ce refactor simplifie l'archi pour les deux topologies (ECS comme Lambda).
- La gestion des podcasts qui exposent une URL signée temporaire (X-Amz-Signature) ou un User-Agent strict côté CDN : si Deepgram ne peut pas pull, on fallback comment ? À ce stade on assume que les CDN podcasts (Libsyn, Buzzsprout, Acast, Spotify Anchor, Megaphone, etc.) acceptent le User-Agent de Deepgram. Si un blocage émerge en prod, ce sera un follow-up ticket.

## Vérification

- `grep -rE "audio-download-queue|download_worker" media_summarizer/ infrastructure/` ne renvoie plus aucun résultat (sauf éventuellement dans `docs/research/` qui est historique).
- Submission d'un podcast RSS avec transcript Podcasting 2.0 → transcript S3 + `completed` sans appel Deepgram.
- Submission d'un podcast RSS sans transcript → `audio_url` enfile direct vers Deepgram → transcript Deepgram → `completed`.
- Le bucket `media-summarizer-audio` n'est plus créé (ou conservé uniquement pour uploads user, à documenter).

## Contexte fichiers utiles

- `media_summarizer/workers/download_worker.py` — le worker à supprimer.
- `media_summarizer/utils/rss_transcript.py` — `fetch_rss_transcript` à conserver et réutiliser depuis `media_submission.py`.
- `media_summarizer/core/services/media_submission.py:215` — endroit où on enqueue actuellement vers `audio-download-queue`.
- `media_summarizer/workers/rss_feed_poll_worker.py:75` — autre callsite à adapter.
- `media_summarizer/workers/transcription/deepgram_worker.py:362-389` — branche `audio_url` déjà en place.
- `media_summarizer/core/media_ingestion/adapters/orchestrators.py:362-422` — dispatch direct `audio_url` à confirmer pour `MediaFamily.AUDIO`.
- `infrastructure/terraform/scaling.tf:289, 565+` — queue + ECS task à retirer.
- `docs/research/task-105-lambda-migration/complement-response-2026-05-30.md` — analyse confirmant la viabilité du refactor.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 Le RSS transcript lookup (Podcasting 2.0) est déplacé hors de download_worker (option A inline préférée) et reste fonctionnel pour les podcasts qui exposent un <podcast:transcript>
- [ ] #2 Tous les podcasts (RSS + recherche manuelle) sont enfilés directement vers deepgram-transcription-queue avec audio_url, plus aucun passage par audio-download-queue
- [ ] #3 media_summarizer/workers/download_worker.py est supprimé du repo
- [ ] #4 La queue SQS audio-download-queue est retirée de Terraform, LocalStack et de toute doc d'infra
- [ ] #5 La task definition ECS ephemeral_worker["download"] est retirée de scaling.tf et le scaling_controller ne la référence plus
- [ ] #6 Le bucket S3 media-summarizer-audio est soit supprimé (Terraform + env var AUDIO_BUCKET) soit conservé uniquement pour les uploads user, avec décision documentée
- [ ] #7 deepgram_worker.py continue d'accepter audio_s3_key pour les uploads de fichiers audio personnels (path POST /api/media upload inchangé)
- [ ] #8 Tests unitaires couvrent les 3 cas du RSS transcript lookup déplacé (trouvé / pas trouvé / fetch fail)
- [ ] #9 Test d'intégration vérifie qu'une submission podcast enfile bien vers deepgram-transcription-queue avec audio_url et plus vers audio-download-queue
- [ ] #10 Test end-to-end : un podcast RSS avec transcript Podcasting 2.0 → completed sans Deepgram ; un podcast sans transcript → Deepgram via audio_url → completed
- [ ] #11 grep -rE 'audio-download-queue|download_worker' sur media_summarizer/ et infrastructure/ ne renvoie plus aucun résultat hors docs/research/
- [ ] #12 docs/MEDIA_INGESTION_CORE_ARCHITECTURE.md et docs/V1_LAUNCH_PLAN.md sont mis à jour pour refléter le nouveau flow podcast direct
- [ ] #13 Le minutes hold reste correctement alloué à la submission podcast (cas duration_seconds connu et inconnu testés)
<!-- AC:END -->
