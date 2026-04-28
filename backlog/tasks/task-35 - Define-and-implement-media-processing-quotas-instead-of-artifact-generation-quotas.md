---
id: task-35
title: >-
  Define and implement media-processing quotas instead of artifact-generation
  quotas
status: Done
assignee: []
created_date: '2026-02-24 11:03'
updated_date: '2026-04-22 14:07'
labels:
  - quota
  - pricing
  - v1
dependencies:
  - task-11
  - task-12
  - task-34
  - task-65
priority: high
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Reframe quota policy around user media processing volume rather than per-artifact generation. In the canonical model, `summary`, `quiz`, and `notes` are artifacts attached to a media item with a completed transcript. A user can request each artifact type on demand once the media is present in that user's documentary base, but each artifact type should only ever be generated once per media item. Once generated, the artifact is persisted in S3 and reused across any user/documentary base that contains the same media. The quota surface should therefore move away from per-user artifact counts and toward limits on how many media items a user can submit/process over a given time window, aligned with the pricing model that will replace the current legacy system.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 The quota/pricing policy explicitly states that `summary`, `quiz`, and `notes` are single-generation-per-media-item artifacts and are reused from shared storage across users/documentary bases when already available.
- [ ] #2 Artifact request paths do not introduce recurring per-user artifact quotas; when an artifact already exists for a media item, the system reuses the stored artifact instead of creating new generation work.
- [ ] #3 A quota model is defined for media submission/processing volume per user/plan/time window, including the canonical enforcement point(s) in the ingestion/transcription flow.
- [ ] #4 Quota exceed conditions for media submission/processing return stable, user-safe errors and do not block access to already-available artifacts for media already present in the user's documentary base.

- [ ] #5 Quota/pricing controls are documented, environment-configurable where applicable, and observable through logs/metrics for operations.
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
2026-03-29 : quiz exclu de V1. Artefacts V1 = summary_short, summary_detailed, flashcards, notes. Le pricing complet est revu dans task-65. Les quotas doivent s'aligner sur le nouveau modèle de pricing une fois celui-ci défini. Dépend de task-65.
<!-- SECTION:NOTES:END -->
