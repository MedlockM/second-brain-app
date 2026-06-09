---
id: task-134
title: Fix TikTok worker — ProcessingJob has no field "episode_url"
status: Done
assignee: []
created_date: '2026-06-09 16:50'
updated_date: '2026-06-09'
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

Discovered during E2E re-run after task-133 was merged. task-133 fixed the `mark_extracting()` call but the TikTok worker still crashes on a sibling Pydantic field assignment a few lines later.

## Symptom

`pytest -m e2e tests/e2e/test_phase4_other_sources.py::test_tiktok_ingestion` fails. CloudWatch `/aws/lambda/media-summarizer-worker-tiktok_ingestion`:

```
File ".../tiktok_ingestion_worker.py", line 773, in process_tiktok_message
    job.episode_url = audio_result["audio_url"]
ValueError: "ProcessingJob" object has no field "episode_url"
```

The chain :
- Line 764: `_fetch_native_subtitles(info)` raises `NativeSubtitlesUnavailable("native_subtitles_absent")` (the test TikTok video has no native captions, fallback to Deepgram is expected).
- Line 773 (in the fallback path): `job.episode_url = audio_result["audio_url"]` — Pydantic rejects because `ProcessingJob` doesn't declare an `episode_url` field.

## Root cause

Same class of bug as task-120 (`extraction_metadata`) and task-133 (`mark_extracting`). The TikTok worker was written against an older `ProcessingJob` schema that had `episode_url`; the schema was tightened/migrated and `episode_url` was removed without auditing all callers.

Likely already covered by `audio_url` field elsewhere in the model — verify before adding a new field.

## Fix

1. Inspect `ProcessingJob` schema (`media_summarizer/core/models/processing_job.py`).
2. Either:
   - Add `episode_url: Optional[str] = None` to the model if it's needed semantically, OR
   - Replace the assignment with the existing equivalent field (e.g. `audio_url`) if that's what the rest of the pipeline reads downstream.
3. Audit other workers (X, Instagram, podcast) for the same pattern — same dead-field assignment likely exists elsewhere.
4. Rebuild + redeploy `media-summarizer-worker-tiktok_ingestion` Lambda.

## Reproduction

```bash
.venv/bin/pytest -m e2e tests/e2e/test_phase4_other_sources.py::test_tiktok_ingestion -v
```

## Out of scope

- Refactoring the whole `ProcessingJob` model
- Other source-specific bugs (Instagram queue, document Algolia key, podcast Decimal) — separate tasks 135, 136, 137

## References

- task-120, task-122, task-123, task-125, task-133 (sibling bugs of the same class)
- `media_summarizer/workers/tiktok_ingestion_worker.py:773`
- `media_summarizer/core/models/processing_job.py` (ProcessingJob schema)
- `tests/e2e/test_phase4_other_sources.py::test_tiktok_ingestion`
- CloudWatch `/aws/lambda/media-summarizer-worker-tiktok_ingestion` 2026-06-09 ~14:39 UTC
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 `ProcessingJob.episode_url` resolved (added to model, or worker switched to existing field — decision documented)
- [ ] #2 Audit other workers for similar dead-field assignments to `ProcessingJob` (grep for `job\.\w+ = `); fix or document follow-ups
- [ ] #3 Lambda image rebuilt + `media-summarizer-worker-tiktok_ingestion` redeployed
- [ ] #4 `pytest -m e2e tests/e2e/test_phase4_other_sources.py::test_tiktok_ingestion` passes (job reaches `completed`)
- [ ] #5 No regression on the 9 already-passing tests
<!-- AC:END -->
