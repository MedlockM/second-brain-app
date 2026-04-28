---
id: task-22
title: 'Implement media status endpoint GET /api/media/{media_item_id}'
status: Done
assignee:
  - '@codex'
created_date: '2026-02-24 11:03'
updated_date: '2026-02-24 20:58'
labels: []
dependencies:
  - task-10
priority: high
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Expose media processing status through a canonical read endpoint so clients can track ingestion and processing progress reliably.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 The endpoint returns current status, progress metadata, and terminal state details.
- [x] #2 The endpoint returns stable error responses for not-found and unauthorized access.
- [x] #3 Response shape is aligned with the frozen API/domain contract.
- [x] #4 The endpoint is documented for client integration.
<!-- AC:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
1. Ajouter l’endpoint authentifié `GET /api/media/{media_item_id}` dans `media_summarizer/api/endpoints/media.py` avec `response_model=MediaStatusResponse` et la table de réponses d’erreur canonique (401/403/404/500).
2. Réutiliser les helpers de mapping déjà en place (stage canonique, media status, transcript status, progression) pour construire `MediaItemContract` et `ProcessingJobContract` à partir du `ProcessingJob` runtime.
3. Implémenter les contrôles d’accès: 404 `MEDIA_NOT_FOUND` si job absent, 403 `NOT_AUTHORIZED` si le job n’appartient pas à l’utilisateur courant.
4. Retourner `artifacts: []` de façon explicite (les endpoints artifacts seront traités par task-33) tout en conservant la forme exacte du contrat `MediaStatusResponse`.
5. Mettre à jour la documentation développeur pour indiquer que le endpoint runtime est implémenté et comment interpréter les champs de suivi.
6. Régénérer `openapi.json` depuis l’app FastAPI pour exposer le nouveau path runtime et vérifier sa présence.
7. Vérifier la cohérence structurelle (parse Python + présence route OpenAPI), puis documenter les notes d’implémentation et cocher les AC atteints dans Backlog.
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Implemented canonical authenticated endpoint `GET /api/media/{media_item_id}` in `media_summarizer/api/endpoints/media.py` with `response_model=MediaStatusResponse` and explicit canonical error response declarations for 401/403/404/500.

Added stable access/error behavior for status reads: returns `MEDIA_NOT_FOUND` (404) when media item does not exist and `NOT_AUTHORIZED` (403) when current user does not own the media item.

Added reusable status-read contract builder `_build_media_status_contracts_from_job(...)` that maps runtime `ProcessingJob` into canonical `MediaItemContract` and `ProcessingJobContract`, including canonical lifecycle/stage mapping, progress metadata, timestamps, transcript status, and terminal error details.

Implemented deterministic runtime inference for `media_type` and `source_platform` from stored URLs (with safe fallbacks), while keeping response shape aligned with frozen contract.

Status response currently returns `artifacts: []` intentionally as placeholder until task-33 implements artifact read endpoints.

Updated developer documentation in `docs/CANONICAL_MEDIA_API_CONTRACT.md` runtime implementation section to include task-22 behavior and integration expectations.

Regenerated runtime `openapi.json` from FastAPI app; verified `/api/media/{media_item_id}` is present with `MediaStatusResponse` schema and expected error responses.

Validation run: Python AST parse of `media_summarizer/api/endpoints/media.py` (`AST_OK`). `compileall` could not be used due repository `__pycache__` write permission restrictions in this environment.
<!-- SECTION:NOTES:END -->
