---
id: task-220
title: >-
  Migrate media library, Search, and folder workflows to the durable media
  source of truth
status: Done
assignee: []
created_date: '2026-08-02 22:38'
updated_date: '2026-08-13 06:45'
labels: []
dependencies:
  - task-241
priority: high
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Move all user-facing library and organization behavior onto the durable media persistence established by task-219, following the owner-approved decision in docs/research/task-218-durable-media-library-persistence/README.md. Search results, collection counts, folder contents, media detail ownership, and organization mutations must remain correct even after the associated processing job expires.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 Canonical media list and search responses are sourced from durable user-media records rather than from the presence of processing_jobs rows
- [ ] #2 Folder counts and folder-content views include durable media whose processing jobs have expired
- [ ] #3 Moving media between folders and assigning or removing tags updates the durable authoritative record
- [ ] #4 Deleting a folder applies the documented reassignment behavior to all affected durable media, including media with no remaining processing job
- [ ] #5 Media ownership checks and artifact navigation continue to enforce user isolation when processing-job data is absent
- [ ] #6 Processing state is represented as optional operational data and its absence does not remove the media from the library
- [ ] #7 The default Uncategorized behavior assigns newly saved media consistently, including saves without an explicit folder_id
- [ ] #8 All active backend code paths that treat processing_jobs as the user-library source of truth are removed or explicitly justified as operational-only
- [ ] #9 The existing canonical /api/media/* and /api/artifacts/* contracts remain coherent for mobile consumers without introducing /api/v1 media endpoints
- [ ] #10 AWS dev verification covers list, Search, folder count, folder open, folder move, tag filtering, media detail, and processing-job expiry scenarios
- [ ] #11 The known owner's account scenario (ID: `4cd1abcb-…`) is documented as a regression case: folders remain populated after job TTL cleanup
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
2026-08-11 — task-219 a été découpée en task-239 → 240 → 241 (→ 220) → 242 → 243 selon les phases §5 du benchmark task-218. Cette tâche **est** la Phase 3 (§5.4, « flip reads ») : la dépendance passe donc de task-219 (archivée) à **task-241** (backfill), car les lectures ne peuvent basculer qu'une fois la bibliothèque reconstruite. §5.4 précise le contenu attendu : basculer les sept chemins de lecture de §4.4, puis supprimer franchement le code obsolète (politique pre-prod) — `ProcessingJob.folder_id`/`tag_ids` (processing_job.py:70-71), `get_processing_jobs_by_folder_id` (database_async.py:736), la table et le module `user_media_submissions`, le gate d'ownership basé sur le job (artifacts.py:55) — et remplacer le `put_item` pleine ligne de `update_processing_job` (database_async.py:360) par des updates au niveau attribut.

Porte de sortie imposée par le benchmark : en AWS dev, supprimer un processing job à la main et prouver que list, Search, comptage de dossier, ouverture de dossier, déplacement, filtre par tag, détail média et accès aux artefacts fonctionnent tous encore. Le compte de l'owner (ID: `4cd1abcb-…`) est le cas de régression nommé : ses dossiers doivent rester peuplés après la suppression manuelle du job. Contrainte d'ordonnancement : ne pas lancer task-242 (réactivation du TTL) avant que cette porte soit franchie.
<!-- SECTION:NOTES:END -->
