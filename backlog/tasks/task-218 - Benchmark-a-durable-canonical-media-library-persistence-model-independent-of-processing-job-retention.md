---
id: task-218
title: >-
  Benchmark a durable canonical media-library persistence model independent of
  processing-job retention
status: To Do
assignee: []
created_date: '2026-08-02 22:38'
labels:
  - benchmark
dependencies: []
priority: high
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Determine the canonical durable data model and lifecycle for a user's saved media library so media, folder membership, tags, ownership, and discoverability never disappear when ephemeral processing jobs expire. Compare the viable options already present in the system (a dedicated durable media record, extending an existing user-media record, or changing processing-job retention), define the authoritative ownership and update boundaries, and recommend a rollout and recovery strategy. Produce docs/research/task-218-durable-media-library-persistence/README.md with owner_decision: pending. The paired implementation tasks must follow the owner's final Decision from this document.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 The benchmark documents the current failure mode with evidence: folders persist while media disappears because library reads depend on processing_jobs records subject to TTL
- [ ] #2 At least the dedicated durable media record, extension of the existing user-media persistence, and removal or alteration of processing-job TTL are compared
- [ ] #3 Each option is evaluated for source-of-truth clarity, ownership and deduplication semantics, folder/tag persistence, lifecycle updates, query patterns, cost, operational complexity, and failure recovery
- [ ] #4 The recommendation preserves processing-job cleanup without allowing job retention to control user-library retention
- [ ] #5 The canonical relationship between a saved media item, a user submission, a processing job, artifacts, folders, and tags is explicitly defined
- [ ] #6 A deployment and migration strategy covers currently surviving records, dangling user_media_submissions references, idempotent writes, rollback, and pre-production compatibility policy
- [ ] #7 Retention, deletion, account-deletion, archival, backup, and observability requirements are specified
- [ ] #8 The research document contains a clear recommendation and an Owner Validation section with owner_decision: pending
<!-- AC:END -->
