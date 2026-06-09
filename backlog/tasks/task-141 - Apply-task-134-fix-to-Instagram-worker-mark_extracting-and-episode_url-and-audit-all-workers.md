---
id: task-141
title: Apply task-134 fix to Instagram worker (mark_extracting + episode_url) and finalize audit of all workers
status: Done
assignee: []
created_date: '2026-06-09 18:20'
labels:
  - bug
  - backend
  - ingestion
dependencies: []
priority: high
dispatchable: true
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
## Context

Discovered while running `pytest -m e2e tests/e2e/test_phase4_other_sources.py::test_instagram_ingestion` after task-134 / task-135 / task-141 wave was deployed. The Instagram worker has **the exact same `ProcessingJob` schema bugs as TikTok** that task-134 was supposed to fix — but task-134 only patched `tiktok_ingestion_worker.py` and did not apply the same fix across other workers, despite AC #2 of task-134 explicitly mandating an audit:

> #2 Audit other workers for similar dead-field assignments to `ProcessingJob` (grep for `job\.\w+ = `); fix or document follow-ups

This task closes the gap by applying the same fix to Instagram and then verifying no other worker has the same residual bugs.

## Symptom

`pytest -m e2e tests/e2e/test_phase4_other_sources.py::test_instagram_ingestion` times out at `pending` (progress 0). The job never advances because the worker crashes immediately.

CloudWatch `/aws/lambda/media-summarizer-worker-instagram_ingestion`:

```
AttributeError: 'ProcessingJob' object has no attribute 'mark_extracting'
  at instagram_ingestion_worker.py:390 → job.mark_extracting()
```

## Root cause

`media_summarizer/workers/instagram_ingestion_worker.py` has three sites with the same dead-method/dead-field problem fixed for TikTok in task-134:

```
Line 348: job.extraction_metadata = _build_extraction_metadata(...)
Line 353: job.extraction_metadata["failed_at"] = _now_iso_utc()
Line 390: job.mark_extracting()              # <-- AttributeError here
Line 405: job.extraction_metadata = extraction_metadata
Line 406: job.episode_url = download_url      # <-- next ValueError after the AttributeError fix
```

`extraction_metadata` was added back to the model in task-120, so lines 348/353/405 might already work. The two new ones to fix are `mark_extracting()` (line 390) and `episode_url` (line 406).

## Fix

Apply the same decision recorded in task-134 to `instagram_ingestion_worker.py`:

- Line 390: `job.mark_extracting()` → match what TikTok worker now does (probably `update_status(JobStatus.<X>)` or removed entirely).
- Line 406: `job.episode_url = download_url` → match what TikTok worker now does (probably `job.media_url = ...` if the model has `media_url`, or persist via `extraction_metadata` instead).

Then **finalize the audit**:

```bash
# Find all dead-field assignments across all workers
grep -rnE "job\.\w+ *=" media_summarizer/workers/ \
  | grep -vE "job\.id|job\.status|job\.extraction_metadata|job\.media_url|job\.transcription_s3_key|job\.summary_s3_key|job\.user_id|job\.user_email"
```

For each remaining hit, verify the LHS field exists on `ProcessingJob` (in `media_summarizer/core/models/processing_job.py`). Fix or document follow-ups.

## Reproduction

```bash
.venv/bin/pytest -m e2e tests/e2e/test_phase4_other_sources.py::test_instagram_ingestion -v
```

## Out of scope

- Other source-specific bugs (document Algolia, podcast Decimal, podcast routing) — separate tasks 136, 137, 138
- Refactoring the broader worker architecture
- Migration of Instagram to a different Apify actor (task-127 already done)

## References

- task-120 (added extraction_metadata to model)
- task-134 (TikTok fix; AC #2 mandated this audit)
- `media_summarizer/workers/instagram_ingestion_worker.py:390, 406`
- `media_summarizer/core/models/processing_job.py` (canonical schema)
- `media_summarizer/workers/tiktok_ingestion_worker.py` (reference for the fix shape after task-134)
- CloudWatch `/aws/lambda/media-summarizer-worker-instagram_ingestion` 2026-06-09 ~16:18 UTC
- `tests/e2e/test_phase4_other_sources.py::test_instagram_ingestion`
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 `instagram_ingestion_worker.py:390` fixed (mark_extracting replaced or removed, matching task-134's decision for TikTok)
- [ ] #2 `instagram_ingestion_worker.py:406` fixed (episode_url replaced with the existing field used by TikTok post-task-134)
- [ ] #3 Full audit performed across `media_summarizer/workers/` for any residual `job.<dead_field> =` or `job.<dead_method>()` assignments; fixed or documented
- [ ] #4 Lambda image rebuilt + `media-summarizer-worker-instagram_ingestion` redeployed
- [ ] #5 `pytest -m e2e tests/e2e/test_phase4_other_sources.py::test_instagram_ingestion` reaches the next bug or passes (Apify resolution may surface a separate Apify-side issue — that would be a follow-up task)
- [ ] #6 No regression on the 10 already-passing tests
<!-- AC:END -->
