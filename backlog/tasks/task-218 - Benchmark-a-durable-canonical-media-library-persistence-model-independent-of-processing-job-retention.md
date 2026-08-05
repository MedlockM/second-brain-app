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
- [x] #1 The benchmark documents the current failure mode with evidence: folders persist while media disappears because library reads depend on processing_jobs records subject to TTL
- [x] #2 At least the dedicated durable media record, extension of the existing user-media persistence, and removal or alteration of processing-job TTL are compared
- [x] #3 Each option is evaluated for source-of-truth clarity, ownership and deduplication semantics, folder/tag persistence, lifecycle updates, query patterns, cost, operational complexity, and failure recovery
- [x] #4 The recommendation preserves processing-job cleanup without allowing job retention to control user-library retention
- [x] #5 The canonical relationship between a saved media item, a user submission, a processing job, artifacts, folders, and tags is explicitly defined
- [x] #6 A deployment and migration strategy covers currently surviving records, dangling user_media_submissions references, idempotent writes, rollback, and pre-production compatibility policy
- [x] #7 Retention, deletion, account-deletion, archival, backup, and observability requirements are specified
- [x] #8 The research document contains a clear recommendation and an Owner Validation section with owner_decision: pending
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Mode: **initial** (no prior `docs/research/task-218-*` directory existed, so this is a from-scratch benchmark).

Produced `docs/research/task-218-durable-media-library-persistence/README.md` with
`owner_decision: pending`.

Root cause established with code and live-infrastructure evidence: `media_item_id` is literally
`processing_job.id`, every library read path resolves through the `processing_jobs` table
(`media_search_service.py:89`, `media.py:1292`/`:1463`, `artifacts.py:55`,
`database_async.py:736`), and `folder_id`/`tag_ids` are stored as attributes on the job row
(`processing_job.py:70-71`). That table has TTL enabled on `expire_at`
(`dynamodb_core_tables.tf:62-66`), re-stamped to now+30 days on every `update_status()`/`update()`
(`processing_job.py:250`, `:361`), while `user_folders` and `user_tags` have no TTL - hence
folders persist and media disappears.

Live AWS dev confirmation (eu-west-3, 2026-08-05): the owner's account has 5 folders and
6 `user_media_submissions` but only 1 surviving processing job, with 5 dangling `job_id`
references; `media_artifacts` holds 20 distinct `media_item_id`s against 7 jobs table-wide.
Recovery is impossible for the already-lost rows: the deployed `job_archiver` Lambda is a
462-byte no-op placeholder that returned 200 for 144 stream REMOVE events and wrote 0 objects,
and PITR is disabled on `processing_jobs` and `user_folders`.

Recommendation: Option A, a dedicated durable `user_media` table (PK `user_id`, SK
`media_item_id`) as the sole source of truth for the library, with `processing_jobs` demoted to
operational-only state that keeps its TTL. Rollout is phased: Phase 0 disables the job TTL
immediately as a data-loss freeze, Phases 1-4 introduce the durable record, dual-write, backfill
from all five surviving sources, flip reads, and then re-enable the job TTL - which is how AC #4
(preserve job cleanup without letting job retention govern library retention) is satisfied.
Options B (extend `user_media_submissions`) and C (permanently remove the TTL) are compared and
rejected as end states, along with two additional options evaluated for completeness.

The document also records eight side findings (unshipped archiver, disabled PITR, missing
account-deletion cascade, 83/150 artifact rows without `media_item_id`, `media_idempotence` rows
stuck at `reserved`, stale `pending` jobs with no `expire_at`, dead `user_media_submissions`
reader, full-row `put_item` in `update_processing_job`) and six open questions for the owner.

**The recommendation awaits owner validation.** No source code or infrastructure was modified.
The task stays `To Do`; the owner sets `owner_decision` on the README, which the dispatcher's
Phase 0 will sync back to the backlog.

Dispatch note: this benchmark was produced by an agent whose isolation worktree was destroyed
mid-run by an unrelated concurrent change to the dispatch tooling. The research content was
recovered from the agent's final report and persisted by the dispatcher; the claims quoted above
were independently re-verified against the codebase and live AWS dev before committing.
<!-- SECTION:NOTES:END -->
