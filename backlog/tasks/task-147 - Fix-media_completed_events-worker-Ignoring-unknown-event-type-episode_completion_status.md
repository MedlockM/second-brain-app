---
id: task-147
title: Fix media_completed_events worker — "Ignoring unknown event type: episode_completion_status"
status: Done
assignee: []
created_date: '2026-06-09 21:30'
labels:
  - bug
  - backend
dependencies: []
priority: high
dispatchable: true
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
## Context

Discovered while re-running E2E tests after task-143 (queue mismatch fix) was merged. The queue mismatch is now resolved: messages reach the `media_completed_events` worker. **But the worker rejects them** with the log:

```
"message": "Ignoring unknown event type: episode_completion_status"
```

Result: the document parsing pipeline (and any other source that emits this event type) reaches `transcribing` 50%, the search indexing succeeds, but the job is never marked `completed` because the consumer silently drops the lifecycle event.

This is a producer/consumer **schema mismatch on the `event_type` field** of the lifecycle message — analogous to the queue name mismatch task-143 fixed at the SQS level, but at the message body schema level instead.

## Symptom

`pytest -m e2e tests/e2e/test_phase4_other_sources.py::test_document_upload` times out at `transcribing` 50%.

CloudWatch `/aws/lambda/media-summarizer-worker-media_completed_events`:

```
"event": "log.record"
"message": "Ignoring unknown event type: episode_completion_status"
```

The producer side, `media_summarizer/workers/document_parsing/worker.py:268`:

```python
message_body = {
    "event_type": "episode_completion_status",
    "status": "success",
    ...
}
```

The consumer side, `media_summarizer/workers/events/media_completed_worker.py` — needs grep — has a dispatcher that only accepts certain `event_type` values (probably `episode_completed` or `media_completed`).

## Root cause

When task-124 split `finalize_usage` and the lifecycle event publication out of the summarization worker, the producer was renamed from `episode_completed` to `episode_completion_status` (more accurate semantically: "here's the status of episode completion"). The consumer's dispatcher was never updated to accept the new value. So messages flow through the queue (post-task-143) but get silently dropped at the body validation step.

## Fix

Two converging options as in task-143:

**Option A — Keep `episode_completion_status` (newer name, semantically accurate).**
- Update `media_completed_worker.py` event dispatcher to recognize `episode_completion_status` as the canonical event type.
- Audit all producers; normalize them all to emit `episode_completion_status`.

**Option B — Revert producer to old name.**
- Update `document_parsing/worker.py:268` (and any other producer) to emit `event_type=episode_completed` (or whatever the consumer currently accepts).
- Cheaper but moves backwards on naming.

Recommendation: **Option A**. The producer name better reflects intent ("status of completion") and matches the queue name `episode-completion-events` that task-143 likely settled on.

After picking: verify the producer also emits a `status` field (`success` / `failed`) that the consumer expects.

## Affected sources

Confirmed affected:
- Document parsing (test_document_upload fails at this exact step)

Likely affected (silent failure — worker fan-out missing):
- Article extraction (test passes because the test only checks `status=completed` from a direct DB update)
- TikTok / YouTube / X / Podcast direct audio (same pattern — they "appear" to pass but watcher fan-out never runs)

The only ingestion path that DOESN'T emit this event is probably the on-demand artifact pipeline (which has its own lifecycle).

## Reproduction

```bash
.venv/bin/pytest -m e2e tests/e2e/test_phase4_other_sources.py::test_document_upload -v
```

Test stays at `transcribing` 50%. CloudWatch on `media-summarizer-worker-media_completed_events` shows the "Ignoring unknown event type" log.

## Out of scope

- Refactoring the watcher fan-out logic (post-V1 cleanup)
- Adding new event types
- Other queue/schema mismatches not related to `event_type`

## References

- task-124 (likely introduced the producer rename)
- task-143 (sibling: fixed queue name mismatch at SQS level)
- `media_summarizer/workers/document_parsing/worker.py:268` (producer)
- `media_summarizer/workers/events/media_completed_worker.py` (consumer, line of the rejection log)
- CloudWatch `/aws/lambda/media-summarizer-worker-media_completed_events` 2026-06-09 ~21:16 UTC
- `tests/e2e/test_phase4_other_sources.py::test_document_upload`
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 Decision recorded: keep new name `episode_completion_status` (Option A) or revert (Option B)
- [ ] #2 Producer and consumer aligned on the same `event_type` value
- [ ] #3 All producers across `media_summarizer/workers/` audited for the event_type they emit; normalized
- [ ] #4 Lambda image rebuilt + `media-summarizer-worker-media_completed_events` redeployed
- [ ] #5 `pytest -m e2e tests/e2e/test_phase4_other_sources.py::test_document_upload` passes (job reaches `completed`)
- [ ] #6 No regression on the 11 already-passing tests; confirm at least one of them (e.g. article) actually triggers the watcher fan-out (not just direct DB update)
<!-- AC:END -->
