---
id: task-32
title: Disable automatic summary/quiz generation in processing pipeline
status: Done
assignee: []
created_date: '2026-02-24 11:03'
updated_date: '2026-02-24 20:36'
labels: []
dependencies:
  - task-14
priority: high
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Ensure the default processing pipeline ends at transcript availability and no longer auto-triggers summary or quiz generation.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 Summary generation is no longer auto-triggered during baseline processing completion.
- [x] #2 Quiz generation is no longer auto-triggered during baseline processing completion.
- [x] #3 Pipeline completion semantics remain correct after auto-generation removal.
- [x] #4 On-demand artifact flow remains available for explicit user requests.
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Validated and tightened transcript-first baseline behavior.

Runtime baseline orchestration remains download -> transcription only (no automatic summary queueing):
- `core/services/episode_submission.py` enqueues only `audio-download-queue`.
- `workers/download_worker.py` forwards only to `transcription-queue`.
- `workers/transcription/worker.py` publishes `episode_completion_status(status=success)` directly with `transcription_s3_key` and `minutes_used`.

Removed remaining automatic quiz chaining from summarization flow:
- `workers/summarization/summarization_worker.py` no longer enqueues `QUIZ_QUEUE` from summary completion.
- Legacy env-controlled auto-quiz trigger path (`ENABLE_QUIZ_GENERATION` / `ENABLE_QUIZ_EMAIL`) removed from runtime behavior.

Pipeline completion semantics remain event-driven and deterministic through `episode_completion_status` + `workers/events/episode_completed_worker.py` finalization.

On-demand artifact capability remains available as explicit worker flows (summarization/quiz workers still present, but no baseline auto-trigger).

Adjusted `workers/summarization/summarization_worker.py` validation so `email` is no longer required in summarization messages; only `job_id` + `transcript_s3_key` remain mandatory, aligning with explicit on-demand artifact requests without email coupling.
<!-- SECTION:NOTES:END -->
