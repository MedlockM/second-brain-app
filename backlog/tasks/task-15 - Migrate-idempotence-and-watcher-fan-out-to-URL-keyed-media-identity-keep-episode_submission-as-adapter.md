---
id: task-15
title: >-
  Migrate idempotence and watcher fan-out to URL-keyed media identity (keep
  episode_submission as adapter)
status: Done
assignee:
  - codex
created_date: '2026-02-23 22:32'
updated_date: '2026-02-23 23:41'
labels: []
dependencies: []
priority: high
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Implement the dedup/caching migration from podcast `episode_guid` to a generic media identity key based on canonicalized shared URL (`media_url`), while preserving current processing reliability and reusing existing orchestration.

Context:
- Current idempotence + watcher flow is hard-wired to `episode_guid` across `episode_submission`, `episode_idempotence`, `episode_watchers`, and completion events.
- New product requirement: the unique key for dedup is the shared media URL (canonical form), for all media types.
- If already processed, system must fetch extracted transcript text from S3 and avoid re-processing.
- `media_summarizer/core/services/episode_submission.py` must be kept temporarily as a compatibility facade (not deleted now).

Scope:
- Define URL canonicalization strategy and deterministic `media_key` generation (including query param policy and platform-specific normalization rules).
- Adapt idempotence storage and API from `episode_guid` to `media_key` (or create parallel media-idempotence adapter and migrate callers).
- Adapt watcher storage/queries from `episode_guid` to `media_key` for in-progress fan-out.
- Propagate `media_key` through queue payloads/events where watcher fan-out and completion/failure handling rely on identity.
- Update duplicate path to load existing `transcription_s3_key` from canonical job and return/reuse transcript without new transcription.
- Keep `episode_submission.py` as compatibility wrapper that delegates to new media-centric submission logic during migration.
- Update infra/table definitions and migration notes for localstack/terraform.

Out of scope:
- Full removal of legacy podcast submit endpoint.
- Email-content workflow redesign beyond what is already covered in task-14.

Key touchpoints:
- `media_summarizer/core/services/episode_submission.py`
- `media_summarizer/utils/episode_idempotence.py`
- `media_summarizer/utils/episode_watchers.py`
- `media_summarizer/workers/download_worker.py`
- `media_summarizer/workers/transcription/worker.py`
- `media_summarizer/workers/summarization/summarization_worker.py`
- `media_summarizer/workers/events/episode_completed_worker.py`
- `media_summarizer/core/models/processing_job.py`
- `infrastructure/terraform/dynamodb_core_tables.tf` and localstack terraform root
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 A canonical URL normalization spec exists and is covered by tests (including platform-specific examples and non-regression fixtures).
- [ ] #2 A stable `media_key` is generated from canonical URL and used as unique idempotence key for duplicate detection.
- [ ] #3 Duplicate submission of an already processed media reuses existing transcript stored in S3 (`transcription_s3_key`) instead of re-running transcription.
- [ ] #4 In-progress duplicate submissions still register as watchers keyed by `media_key` and are resolved on success/failure events.
- [ ] #5 Queue/event payloads and completion workers no longer require `episode_guid` as the only identity for dedup/fan-out correctness.
- [ ] #6 `media_summarizer/core/services/episode_submission.py` remains in repo and acts as compatibility adapter during migration (no deletion in this task).
- [ ] #7 Infra/table schema/docs are updated with a safe migration path from legacy GUID-keyed tables.
- [ ] #8 Automated tests cover: first submission, duplicate processed reuse, duplicate in-progress watcher fan-out, failure propagation, and backward-compatibility paths.
<!-- AC:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
1) Add a dedicated media identity module with canonical URL normalization + deterministic media_key generation.
- Create canonicalization rules with explicit query-param policy and platform-specific normalization (YouTube, Instagram, TikTok, podcast/audio URLs).
- Expose pure helpers used by services/workers and add fixture-style non-regression tests.

2) Introduce media-keyed idempotence and watcher adapters with backward-compatible wrappers.
- Migrate storage helpers from episode_guid semantics to media_key semantics.
- Keep compatibility helper signatures where needed so legacy callers do not break during transition.
- Ensure status transitions (reserved/processed/failed/release) remain equivalent.

3) Extend processing identity metadata and submission orchestration.
- Extend ProcessingJob with media identity fields (media_key, normalized_url as needed) while keeping episode_guid for compatibility.
- Update episode_submission service to compute media_key from audio_url and use media-keyed idempotence/watchers.
- On duplicate processed path, reuse canonical transcript artifact (transcription_s3_key) and avoid re-running transcription.
- Keep episode_submission.py present as migration facade.

4) Propagate media_key through queues/events/workers and keep mixed-mode compatibility.
- Add media_key in audio-download, transcription, summarization, and completion/failure event payloads.
- Update event consumer to key fan-out by media_key while still tolerating legacy episode_guid payloads during migration.
- Preserve failure unblocking and watcher finalization behavior.

5) Update infrastructure schema/docs for safe migration.
- Replace/augment Terraform + LocalStack definitions for media_idempotence/media_watchers (media_key keyed) and outputs.
- Keep migration notes in docs to explain legacy table compatibility path.

6) Add automated coverage for required scenarios.
- Canonicalization/media_key tests (platform examples + non-regression fixtures).
- Integration/unit tests for first submission, duplicate processed transcript reuse, duplicate in-progress watcher fan-out, failure propagation, and backward-compat paths.

7) Validate and finalize task bookkeeping.
- Run targeted tests for modified modules.
- Record implementation notes and acceptance criteria progress in Backlog task.
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Implemented media identity layer with canonical URL normalization + deterministic `media_key` generation in `core/services/media_identity.py` (YouTube/Instagram/TikTok/Spotify + generic query tracking stripping).

Migrated idempotence helper to media-key model in `utils/episode_idempotence.py` with optional legacy `episode_guid` fallback reads for transition safety.

Migrated watchers helper to media-key model in `utils/episode_watchers.py` with legacy fallback reads/updates against `episode_watchers` when needed.

Extended `ProcessingJob` with `media_key` and `normalized_url` fields and serialization support.

Updated `core/services/episode_submission.py` to derive `media_key` from canonical URL, reserve/check idempotence by `media_key`, register watchers by `media_key`, and include `media_key` in downstream queue payloads.

Duplicate processed path now reuses canonical `transcription_s3_key` from the canonical job (best-effort S3 existence check) and avoids re-running the download/transcription pipeline.

Propagated `media_key` through worker payloads/events in download/transcription/summarization and adjusted event fan-out worker to resolve identity by `media_key` first with `episode_guid` fallback.

Updated email worker idempotence marking to pass media identity context (`media_key` + legacy `episode_guid`).

Terraform updated with new `media_idempotence` and `media_watchers` tables (core + localstack), while keeping legacy episode tables for migration.

Added migration runbook notes in `docs/MEDIA_KEY_MIGRATION.md` (new env vars, fallback flags, deployment sequence).

Per explicit user request, stopped all test authoring/execution work and focused on implementation-only changes.

Added legacy-write fallback in `episode_idempotence.mark_processed/mark_failed`: when media row is missing (ConditionalCheckFailed), status is now updated in legacy `episode_idempotence` row by `episode_guid` to avoid stuck `reserved` state during migration.
<!-- SECTION:NOTES:END -->
