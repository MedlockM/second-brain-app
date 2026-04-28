---
id: task-19
title: >-
  Freeze canonical API contract and domain types for media ingestion and
  artifacts
status: Done
assignee:
  - '@codex'
created_date: '2026-02-24 11:02'
updated_date: '2026-02-24 20:18'
labels: []
dependencies: []
priority: high
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Define and lock the canonical API and domain contracts used by ingestion, processing status tracking, and artifacts so backend and mobile work share stable interfaces.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 Canonical request/response contracts are defined for ingest, media status, artifact creation, and artifact reads.
- [x] #2 Domain types and statuses are locked for MediaItem, MediaArtifact, and ProcessingJob lifecycle usage.
- [x] #3 Error codes and error payload structure are stable and documented for client handling.
- [x] #4 Contract documentation is sufficient for independent backend and mobile implementation.
<!-- AC:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
1. Baseline et périmètre de gel
- Inventorier les contrats API existants (`/api/v1/podcast-search/*`, `/api/v1/jobs/*`, `/api/v1/episodes/*`) et les écarts avec la cible canonique (`/api/media/*`, `/api/artifacts/*`).
- Vérifier les primitives déjà disponibles à réutiliser: identité média (`media_key`, URL normalisée), idempotence/fan-out, format d’erreur global.

2. Définir les types de domaine canoniques (frozen)
- Introduire des modèles de contrat explicites pour `MediaItem`, `MediaArtifact` et `ProcessingJob` lifecycle usage dans un module dédié de modèles API.
- Figer les enums de statuts (media lifecycle, transcript lifecycle, artifact lifecycle, processing job lifecycle) et les champs obligatoires/optionnels.

3. Définir les contrats API canoniques (frozen)
- Spécifier les payloads request/response pour:
  - `POST /api/media/ingest-url`
  - `GET /api/media/{media_item_id}`
  - `POST /api/media/{media_item_id}/artifacts`
  - `GET /api/media/{media_item_id}/artifacts`
  - `GET /api/artifacts/{artifact_id}`
- Ajouter conventions d’auth, idempotence, pagination, et métadonnées de suivi utiles au mobile.

4. Figer le contrat d’erreur stable
- Aligner le contrat canonique sur le format global existant (`error.code`, `error.message`, `error.request_id`) et documenter le catalogue de codes stables attendu côté client.
- Définir clairement les erreurs user-safe pour URL invalide/non supportée, accès, quota, not found, conflit, rate limit, interne.

5. Documenter pour implémentation indépendante backend/mobile
- Produire une documentation de référence unique et exploitable (backend + mobile) avec exemples JSON complets, transitions de statuts et règles de compatibilité.
- Référencer explicitement les tâches dépendantes (`task-10`, `task-20`, `task-22`, `task-33`) pour garantir l’alignement.

6. Mise à jour des artefacts projet
- Ajouter/mettre à jour les fichiers de types/contrats côté backend et côté frontend (types partagés de consommation API).
- Mettre à jour les notes de tâche avec les décisions de design et vérifier l’alignement des critères d’acceptation.

7. Clôture fonctionnelle de la tâche
- Vérifier que les 4 AC de `task-19` sont couverts par les artefacts de contrat et la documentation.
- Mettre à jour la tâche Backlog (AC cochés + notes d’implémentation) pour handoff aux tâches d’implémentation.
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Frozen canonical backend domain/API models in `media_summarizer/api/models/media_contracts.py` (MediaItem, MediaArtifact, ProcessingJob lifecycle usage, ingest/status/artifact request-response models, stable error code enum).

Exposed canonical contract models through `media_summarizer/api/models/__init__.py` to make import/reuse straightforward across upcoming implementation tasks.

Added frontend canonical types mirror in `front/src/types/media.ts` for independent mobile/web implementation against the same schema vocabulary.

Added contract reference documentation in `docs/CANONICAL_MEDIA_API_CONTRACT.md` including endpoint payload examples, locked enums, lifecycle mapping, error payload structure, stable error code catalog, and invariants.

Added contract-only OpenAPI freeze file `docs/CANONICAL_MEDIA_API_OPENAPI.yaml` for canonical endpoint and schema handoff (`/api/media/*`, `/api/artifacts/*`).

Validation performed: structural checks via `rg` on contract files and Python AST parse (`AST_OK`) for the new backend contract module. Bytecode compile attempts were blocked by repository `__pycache__` write permissions.
<!-- SECTION:NOTES:END -->
