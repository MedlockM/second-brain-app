---
id: task-34
title: >-
  Implement artifact storage/idempotence/cache with mandatory existing-system
  reuse audit
status: Done
assignee:
  - '@codex'
created_date: '2026-02-24 11:03'
updated_date: '2026-03-15 20:53'
labels: []
dependencies:
  - task-11
priority: high
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Implement artifact storage, idempotence, and caching while mandating an upfront audit of reusable existing components and prioritizing reuse/adaptation over new implementation.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 A pre-implementation audit inventories reusable existing components for artifact storage, idempotence, and caching.
- [ ] #2 Implementation reuses or adapts existing components first and documents reuse decisions.
- [ ] #3 Any newly introduced component includes explicit justification for why reuse/adaptation was insufficient.
- [ ] #4 The resulting design avoids unjustified duplication across storage, idempotence, and cache responsibilities.
- [ ] #5 Artifact lifecycle remains consistent for summary, quiz, and notes after implementation.
<!-- AC:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
1. Documenter l’audit de réutilisation dans la tâche et conserver comme briques réutilisées `utils.s3`, le pattern DynamoDB conditionnel de `utils.episode_idempotence`, le pattern de cache partagé de `core/services/forecast_service`, ainsi que les prompts/parsers existants des workers `summarization` et `quiz`.
2. Introduire un stockage canonique dédié aux artefacts avec une table `media_artifacts` (source de vérité métier) et une table `artifact_idempotence` (lock/cache global par `generation_fingerprint`), plus les types internes associés pour enregistrements, références S3 et locks.
3. Ajouter les accès DynamoDB/repository pour créer, lire, mettre à jour et rechercher les artefacts par `artifact_id`, `media_item_id`, `request_fingerprint` et `generation_fingerprint`, avec un cycle `queued|generating|ready|failed` et une politique forward-only sans lecture des champs legacy `ProcessingJob.summary_s3_key` / `quiz_s3_key` / `summary_url`.
4. Créer un service artefact partagé qui normalise les paramètres, calcule `request_fingerprint` et `generation_fingerprint`, vérifie la disponibilité du transcript, applique l’idempotence locale par média, réutilise le cache global quand disponible, sinon réserve une génération et enfile le worker adéquat (`summarization-queue` ou `quiz-queue`).
5. Adapter le contrat des messages workers pour être centré `artifact_id` / `media_item_id` / `artifact_type` / `parameters` / `transcript_s3_key`, extraire des helpers communs de génération/persistance depuis les workers summary/quiz, et retirer du chemin artefact les side effects legacy de finalisation `ProcessingJob` / `episode_completion_status`.
6. Alimenter `GET /api/media/{media_item_id}` depuis le stockage canonique `media_artifacts` pour peupler `artifact_statuses` et la liste `artifacts`, sans implémenter les endpoints de lecture dédiés de `task-33` au-delà du repository partagé nécessaire.
7. Mettre à jour l’infrastructure locale/dev (Terraform LocalStack, bootstrap `init-aws.sh`, helpers LocalStack/tests) pour créer les nouvelles tables et garantir la présence du bucket/queue quiz existants utilisés par le socle.
8. Vérifier le résultat par smoke checks ciblés: absence de double enqueue pour une requête identique, réutilisation du cache global sans appel LLM supplémentaire, reprise après échec via nouvel artefact, et exposition correcte des `artifact_statuses` dans `GET /api/media/{id}`.
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Dépendance circulaire corrigée le 2026-02-24: suppression de la dépendance vers task-12 pour casser le cycle task-12 <-> task-34.

Ordonnancement retenu: task-11 (on-demand summary/quiz) -> task-34 (storage/idempotence/cache communs) -> task-12 (notes artifact sur socle commun).

Audit de réutilisation retenu avant implémentation: réutiliser `utils.s3`, le pattern de réservations conditionnelles de `utils.episode_idempotence`, le cache DynamoDB partagé de `core/services/forecast_service`, et la logique de prompt/parsing des workers summary/quiz. Rejeter `ProcessingJob.summary_s3_key`, `quiz_s3_key`, `summary_url` comme source canonique; ces champs ne seront plus alimentés par le nouveau flux artefact.

Implémentation en cours livrée: ajout du stockage canonique `media_artifacts`, des locks/cache `artifact_idempotence`, du service partagé `core/services/artifact_service.py`, du POST canonique `POST /api/media/{media_item_id}/artifacts`, et alimentation de `GET /api/media/{media_item_id}` depuis le nouveau store pour `artifact_statuses` + liste d’artefacts. Les workers summary/quiz écrivent désormais dans le store canonique et n’alimentent plus `ProcessingJob.summary_s3_key` / `quiz_s3_key` ni les événements `episode_completion_status`.

Vérifications effectuées: AST parse OK sur les modules Python modifiés; `bash -n infrastructure/localstack/init-aws.sh` OK; vérification par recherche des nouvelles tables/buckets/queues/route canonique. Limitation d’environnement: import runtime complet impossible dans ce shell car `pydantic` n’est pas installé, et `py_compile` échoue à écrire les `__pycache__` du dépôt.

Durcissement complémentaire du socle canonique: ajout d’une réservation cohérente par `request_fingerprint` dans `media_artifacts` pour éviter la création de doublons same-media sur les requêtes concurrentes, avec pointeur vers l’artefact actif/réutilisé. Les chemins `complete_artifact_generation` et `fail_artifact_generation` mettent désormais à jour l’artefact courant directement avant de propager l’état aux artefacts liés par `generation_fingerprint`, afin de ne pas dépendre uniquement de la visibilité immédiate du GSI.

Validation complémentaire du 2026-03-09: `uv run python` importe correctement `media_artifact`, `media_artifacts`, `artifact_idempotence`, `artifact_service`, `api.endpoints.media`, `workers.summarization.summarization_worker` et `workers.quiz.worker`. `bash -n infrastructure/localstack/init-aws.sh` reste OK. Limite restante: pas de smoke end-to-end DynamoDB/SQS/S3 exécuté dans cette session, et le critère Backlog sur le lifecycle `notes` reste volontairement hors périmètre de cette implémentation car le plan demandé prépare seulement le socle pour `task-12` sans exposer de génération `notes`.
<!-- SECTION:NOTES:END -->
