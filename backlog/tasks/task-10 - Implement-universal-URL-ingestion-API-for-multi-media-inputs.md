---
id: task-10
title: Implement universal URL ingestion API for multi-media inputs
status: Done
assignee:
  - '@codex'
created_date: '2026-02-23 22:08'
updated_date: '2026-02-24 20:47'
labels: []
dependencies:
  - task-19
  - task-20
  - task-21
priority: high
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Create the canonical ingestion entrypoint for shared URLs so the backend accepts any supported media link, classifies it, normalizes it, and creates a trackable media processing record.

The source of inspiration is this repo: https://github.com/dgirard/fiches-veille
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 Provide a single authenticated API entrypoint to ingest a shared URL and return a trackable processing identifier.
- [x] #2 URL normalization and deduplication behavior are defined and prevent duplicate processing for equivalent links.
- [x] #3 The ingestion response includes enough status metadata for mobile clients to track progress.
- [x] #4 Errors for invalid or unsupported URLs are explicit, stable, and user-safe.
- [x] #5 OpenAPI and developer documentation are updated for the canonical ingestion contract.
<!-- AC:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
1. Auditer l’état actuel de l’API d’ingestion (endpoints, modèles, erreurs, OpenAPI).
2. Ajouter un endpoint canonique authentifié pour ingestion URL universelle, branché sur le core `IngestUrlUseCase`.
3. Aligner normalisation/dédoublonnage via identité canonique et renvoyer un identifiant de suivi stable.
4. Exposer une réponse riche en métadonnées de statut pour clients mobiles.
5. Rendre les erreurs invalid/unsupported explicites, stables et user-safe.
6. Mettre à jour contrat OpenAPI + documentation développeur.
7. Valider (lint/compilation ciblée) puis clôturer la tâche avec notes d’implémentation.
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Implemented canonical authenticated ingestion endpoint `POST /api/media/ingest-url` in `media_summarizer/api/endpoints/media.py`, wired into FastAPI app via `media_summarizer/api/main.py` with unversioned `/api/media/*` prefix.

Endpoint is directly wired to the hexagonal core ingestion use-case (`build_default_ingest_url_use_case`) and converts domain `IngestionOutcome` into canonical API contract `IngestUrlResponse` (`media_item` + `processing_job` + dedup flags).

Defined deterministic normalization/dedup behavior at runtime by reusing canonical media identity + idempotence from the ingestion core; equivalent URLs reuse the same canonical media key and return deduplicated responses.

Expanded duplicate outcome metadata in orchestrator (`media_type`, `source_platform`, `media_family`) to keep canonical response payloads stable and informative even on deduplicated submissions.

Added explicit stable user-safe error mapping for URL failures: `InvalidUrlError -> INVALID_URL (400)` and `UnsupportedUrlError -> UNSUPPORTED_URL (400)`, with canonical error response model declarations in OpenAPI responses.

Provided tracking metadata for mobile clients in ingestion response: canonical job lifecycle stage, progress percentage, timestamps (`created_at`, `updated_at`, optional `started_at`, `completed_at`), transcript status, and media item status.

Updated developer docs: `docs/CANONICAL_MEDIA_API_CONTRACT.md` now includes runtime implementation status and ingestion operational behavior for task-10.

Updated canonical OpenAPI contract file `docs/CANONICAL_MEDIA_API_OPENAPI.yaml` with bearer auth security declaration.

Regenerated runtime `openapi.json` from FastAPI app (`.venv/bin/python`) and confirmed `/api/media/ingest-url` is present with expected auth + response schema references.

Validation executed: AST parse OK on modified Python modules, route presence check in app routes (`/api/media/ingest-url`), and YAML parse OK for canonical OpenAPI document.
<!-- SECTION:NOTES:END -->
