---
id: task-183
title: >-
  Remove orphan mark_downloading() callers left over from JobStatus refactor
  (task-175)
status: Done
assignee: []
created_date: '2026-06-10 14:26'
updated_date: '2026-06-10 15:05'
labels:
  - bug
  - ingestion
  - cleanup
dependencies: []
priority: high
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Commit `de7b1b2` (task-175) removed `JobStatus.DOWNLOADING` and `ProcessingJob.mark_downloading()` from the model, but three call sites still invoke `job.mark_downloading()`. They were not exercised by the existing E2E suite and slipped through.

**Symptoms:**
- `tests/e2e/test_phase4_other_sources.py::test_instagram_ingestion` fails with HTTP 500 on `GET /api/media/{id}`
- API CloudWatch traceback: `ValueError: 'downloading' is not a valid JobStatus` raised in `ProcessingJob.from_dynamodb_item` (`processing_job.py:207`) when deserialising a row whose `job_status` was written as `"downloading"` by an orphan caller
- Verified in repro: `ProcessingJob(...).mark_downloading()` raises `AttributeError`

**Orphan call sites on `main`:**
- `media_summarizer/core/media_ingestion/adapters/orchestrators.py:377` — Instagram `IMAGE_POST` branch
- `media_summarizer/core/media_ingestion/adapters/orchestrators.py:534` — TikTok dispatcher branch
- `media_summarizer/workers/instagram_ingestion_worker.py:261` — Instagram worker entry

These three sites must be aligned with the refactor. The task-175 commit message explicitly states `EXTRACTING` is the generic stage covering content extraction — `mark_extracting()` is the right replacement.

Any DynamoDB rows already carrying `job_status="downloading"` will keep crashing the API on read; the rollout should also cover that data (either a one-shot migration script or tolerant deserialisation that maps the legacy value).
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 The three `mark_downloading()` calls in orchestrators.py and instagram_ingestion_worker.py are replaced with `mark_extracting()`
- [ ] #2 `grep -rn 'mark_downloading' media_summarizer/` returns zero results outside test fixtures or worktrees
- [ ] #3 Existing rows with `job_status="downloading"` no longer crash `GET /api/media/{id}` (either via data fix or backwards-compatible deserialisation — pick one and document the choice)
- [ ] #4 `tests/e2e/test_phase4_other_sources.py::test_instagram_ingestion` passes against AWS dev (job reaches `completed`)
- [ ] #5 Manual smoke check on TikTok and Instagram image-post ingestion still queues to the right downstream queue
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Merged via cherry-pick on main as commit de61e02 (2026-06-10). Files changed: media_summarizer/core/media_ingestion/adapters/orchestrators.py, media_summarizer/core/models/processing_job.py, media_summarizer/workers/instagram_ingestion_worker.py.
<!-- SECTION:NOTES:END -->
