---
id: task-23
title: Purge legacy ingestion and completion runtime paths
status: Done
assignee:
  - '@codex'
created_date: '2026-02-24 11:03'
updated_date: '2026-02-24 21:11'
labels: []
dependencies:
  - task-15
  - task-17
  - task-10
  - task-22
priority: high
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Remove remaining runtime legacy ingestion/completion compatibility paths so the system runs on the canonical media-key architecture only.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 Legacy fallback flags and legacy runtime branches are removed from active paths.
- [x] #2 Runtime behavior no longer depends on legacy episode-guid compatibility logic.
- [x] #3 Obsolete legacy references are removed from config and operational docs.
- [x] #4 Canonical media-key ingestion/completion remains fully functional after cleanup.
<!-- AC:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
1. Auditer les chemins runtime ingestion/completion encore legacy (`episode_guid`, fallbacks de lecture/écriture legacy, flags de compatibilité) dans services, workers et utilitaires.
2. Supprimer les branches/fallbacks legacy actifs dans les chemins canoniques (idempotence/watchers/completion), en gardant uniquement le modèle `media_key`.
3. Mettre à jour les endpoints/flux qui consomment encore l’identité legacy pour qu’ils utilisent exclusivement `media_item_id`/`media_key` dans les chemins canoniques.
4. Nettoyer la configuration et la documentation opérationnelle des références legacy devenues obsolètes.
5. Vérifier la cohérence statique (AST/parse + vérifications ciblées de routes et recherche de motifs legacy) et documenter les changements dans la tâche.
6. Cocher les AC de task-23 quand le runtime canonique reste fonctionnel sans dépendance legacy.
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Purged legacy runtime fallback logic from canonical idempotence/watchers paths: `media_summarizer/utils/episode_idempotence.py` and `media_summarizer/utils/episode_watchers.py` now use `media_key` only and no longer read/write legacy episode-guid tables.

Updated completion fan-out worker to resolve identity with `media_key` only (`canonical_job_id` fallback lookup for robustness), and removed all `episode_guid`-based watcher/idempotence branching in `media_summarizer/workers/events/episode_completed_worker.py`.

Updated worker pipeline payloads to canonical identity only: removed `episode_guid` propagation in download/transcription/summarization completion events (`download_worker.py`, `transcription/worker.py`, `summarization_worker.py`) and tightened quiz worker required identity to `media_key`.

Updated legacy episode submission service runtime behavior to canonical identity only: `submit_episode_for_user(...)` now ignores legacy `episode_guid` input and uses `media_key` exclusively for idempotence/watchers/event payloads.

Removed deprecated identity resolver fallback in `core/services/media_identity.py` (`resolve_identity_key` removed).

Purged legacy per-user submission fallback behavior from active runtime helper: `user_media_submissions.py` now reads/writes canonical `user_media_submissions` table only; legacy adapter `user_episode_submissions.py` reduced to thin GUID->media_key mapper without legacy table fallback/dual-write.

Removed obsolete legacy config references from `.env.example` (`EPISODE_IDEMPOTENCE_TABLE`, `EPISODE_WATCHERS_TABLE`, `USER_EPISODE_SUBMISSIONS_TABLE`) and kept canonical table vars (`MEDIA_IDEMPOTENCE_TABLE`, `MEDIA_WATCHERS_TABLE`, `USER_MEDIA_SUBMISSIONS_TABLE`).

Updated operational docs to canonical-only model: `docs/MEDIA_KEY_MIGRATION.md`, `docs/MEDIA_KEY_SUBMISSION_GUARD_CONTRACT.md`, and `docs/CANONICAL_MEDIA_API_CONTRACT.md` now describe media-key-only runtime without episode-guid fallback branches.

Updated Terraform table config to remove legacy episode-guid identity tables from active infra definitions/outputs in `infrastructure/terraform/dynamodb_core_tables.tf` and `infrastructure/terraform/localstack/main.tf` (canonical `media_*` tables retained).

Validation performed: AST parse OK across all modified Python modules; targeted grep confirms legacy fallback env refs removed from runtime code/config/docs touched. Terraform formatting check could not be run because `terraform` is not installed in this environment.
<!-- SECTION:NOTES:END -->
