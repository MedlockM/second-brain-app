---
id: task-124
title: Move finalize_usage and episode_completed event out of summarization lifecycle
status: To Do
priority: medium
labels: [bug, backend, tech-debt]
created: 2026-06-09
---

# Move finalize_usage and episode_completed event out of summarization lifecycle

## Context

After task-123 migrated the summarization worker to the canonical `artifact_id` contract, two legacy side-effects were removed from the summarization worker because they do not belong in an artifact generation worker:

1. **`finalize_usage(job_id, minutes_used)`** -- charges the user's minute pool based on audio duration. This is a billing concern tied to *transcription* (the expensive step), not summary generation.

2. **`sqs.send_message(EPISODE_COMPLETED_EVENTS_QUEUE, ...)`** -- publishes an `episode_completed` event that triggers the `media_completed_worker` fan-out (watcher notifications, job finalization for shared media keys).

These were historically in the summarization worker because summarization was the last step before "done". With the new artifact architecture, artifact generation is decoupled from the media processing pipeline -- artifacts are generated on-demand after transcription is complete.

## Current State

- `finalize_usage` is already called in `media_submission.py` for the original submitter.
- `media_completed_worker.py` calls `finalize_usage` for watchers.
- The `episode_completed` event was the trigger for `media_completed_worker`.

**Without the summarization worker publishing `episode_completed`, watchers of shared media keys may never get their jobs finalized.** This needs to be moved to `deepgram_transcription_worker` (after successful transcription upload) or to a new completion step in `media_submission.py`.

## Acceptance Criteria

1. `finalize_usage` for the original submitter is called exactly once at the right lifecycle point (after transcription succeeds, not after summary generation).
2. `episode_completed` / `media_completed` event is published after transcription completes, enabling the `media_completed_worker` fan-out to proceed.
3. No double-charging of minutes (audit all `finalize_usage` call sites).
4. Watchers of shared media keys still get their jobs finalized.
5. The auto-trigger of flashcards generation (previously in summarization worker) is either removed (since artifacts are now on-demand) or moved to a lifecycle hook if still desired.

## Key Files

- `media_summarizer/workers/transcription/deepgram_worker.py` (candidate location for the event publication)
- `media_summarizer/core/services/media_submission.py` (already calls `finalize_usage`)
- `media_summarizer/workers/events/media_completed_worker.py` (consumer of the event)
- `media_summarizer/core/services/minute_pool.py` (defines `finalize_usage`)
