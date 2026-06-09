---
id: task-143
title: Fix mismatch between EPISODE_COMPLETION_EVENTS_QUEUE (producer) and EPISODE_COMPLETED_EVENTS_QUEUE (consumer)
status: Done
assignee: []
created_date: '2026-06-09 19:30'
labels:
  - bug
  - backend
  - infrastructure
dependencies: []
priority: high
dispatchable: true
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
## Context

Discovered while validating the `test_document_upload` E2E test after task-136 (Algolia key fix). The document upload pipeline reaches `transcribing` status (50%) and stays there forever, never transitioning to `completed`. The cause is a **queue name mismatch** between the producer of the completion event and the consumer that finalizes the job.

The Algolia key fix (task-136) was successful — search indexing works. The new bug is that the completion event publishes to one queue while the consumer reads from another, so the job is never marked completed.

## Symptom

`pytest -m e2e tests/e2e/test_phase4_other_sources.py::test_document_upload` times out at status `transcribing` (progress 50%).

CloudWatch confirms each step works in isolation:

- ✅ `document_parsing` worker: parses PDF via LlamaParse (`event: worker.document_parsing.completed`)
- ✅ `search_indexing` worker: indexes transcript in Algolia (`event: search_indexing.completed`)
- ❌ `media_completed_events` worker: **no logs at all** (worker never invoked, queue empty)

## Root cause

`media_summarizer/workers/document_parsing/worker.py:265-282` publishes the completion event to:

```python
EPISODE_COMPLETION_EVENTS_QUEUE   # value: "episode-completion-events"
```

`media_summarizer/workers/events/media_completed_worker.py:25` reads from:

```python
EPISODE_COMPLETED_EVENTS_QUEUE    # value: "episode-completed-events"
```

Note the typo: `_completion_` (producer) vs `_completed_` (consumer). They are two distinct queues, both provisioned by Terraform (`infrastructure/terraform/sqs.tf:335` and `366`), but messages sent to one are never consumed by the worker tied to the other.

The `media_completed_events` Lambda is wired (in Terraform) to `episode-completed-events` (the `_completed_` one), so events sent to `_completion_` accumulate without being processed. Eventually they go to the DLQ.

This is likely a regression introduced when task-124 split the lifecycle event publication out of the summarization worker. The producer was renamed `_completion_` (more accurate semantically: "the document parsing has completed") but the consumer queue was kept as `_completed_` for backward compatibility, and the wiring was never reconciled.

## Affected pipelines

The same mismatch likely affects every worker that emits a completion event:

- `document_parsing/worker.py` (confirmed)
- `summarization/summarization_worker.py` (probably — check what task-124 renamed)
- `tiktok_ingestion_worker.py`, `instagram_ingestion_worker.py`, `youtube_ingestion_worker.py`, `x_ingestion_worker.py` (check)
- Any post-Deepgram completion path

If TikTok, Instagram, YouTube, X all publish to `_completion_` and only `_completed_` is consumed, then **none of those pipelines actually reach `completed` status either** — except they happen to update `processing_jobs.status` directly elsewhere in the worker, so the test sees `completed` even though the watcher fan-out (the real purpose of the `media_completed_events` worker) never runs.

This means the existing 9 passing tests (including TikTok, YouTube, X, article, and the 4 artifacts) probably observe `status=completed` from a direct DynamoDB update **without the watcher fan-out being triggered**. That's a latent bug for V1 (shared media keys with watchers will never get notified).

## Fix

Pick one of the two names and converge:

**Option A — Keep `_completion_` (semantically correct producer name).**
- Update `media_completed_worker.py:25` env default to `"episode-completion-events"`
- Update env var in Lambda config (Terraform `lambda_workers.tf` `media_completed_events` worker entry) to set `EPISODE_COMPLETED_EVENTS_QUEUE=episode-completion-events`, OR rename the Terraform var to `EPISODE_COMPLETION_EVENTS_QUEUE`
- Update event source mapping to point at `aws_sqs_queue.episode_completion_events.arn`
- Delete the unused `episode-completed-events` queue + DLQ

**Option B — Keep `_completed_` (backward-compat name).**
- Update producer (`document_parsing/worker.py` and any sibling worker) to publish to `EPISODE_COMPLETED_EVENTS_QUEUE`
- Delete the unused `episode-completion-events` queue + DLQ

Both options work; B is less risky (fewer Lambda config changes). The owner should validate which naming convention to keep.

After picking: audit all workers in `media_summarizer/workers/` for `EPISODE_COMPLETION_EVENTS_QUEUE` and `EPISODE_COMPLETED_EVENTS_QUEUE` references, normalize.

## Reproduction

```bash
.venv/bin/pytest -m e2e tests/e2e/test_phase4_other_sources.py::test_document_upload -v
```

Stays at `transcribing` 50% forever. Logs from `document_parsing` and `search_indexing` show success; `media_completed_events` Lambda is never invoked.

## Out of scope

- Refactoring the watcher fan-out logic (post-V1)
- Changing the lifecycle event schema
- Other queue naming inconsistencies elsewhere in the codebase

## References

- task-124 (introduced the producer rename probably)
- `media_summarizer/workers/document_parsing/worker.py:266` (offending producer queue name)
- `media_summarizer/workers/events/media_completed_worker.py:25` (consumer)
- `infrastructure/terraform/sqs.tf:335, 345, 366` (two queues exist)
- CloudWatch `/aws/lambda/media-summarizer-worker-document_parsing` 2026-06-09 ~19:00 UTC
- CloudWatch `/aws/lambda/media-summarizer-worker-search_indexing` 2026-06-09 ~19:00 UTC
- CloudWatch `/aws/lambda/media-summarizer-worker-media_completed_events` 2026-06-09 (silent — no logs)
- `tests/e2e/test_phase4_other_sources.py::test_document_upload`
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 Decision recorded: keep `_completion_` (Option A) or `_completed_` (Option B)
- [ ] #2 Producer and consumer aligned on the same queue name; only ONE queue remains in `sqs.tf` (the other deleted)
- [ ] #3 All workers audited for `EPISODE_COMPLET*_EVENTS_QUEUE` references; aligned with the chosen name
- [ ] #4 `terraform apply` clean
- [ ] #5 Lambda image rebuilt + redeployed
- [ ] #6 `pytest -m e2e tests/e2e/test_phase4_other_sources.py::test_document_upload` passes (job reaches `completed`)
- [ ] #7 Existing 9 passing tests continue to pass; verify `media_completed_events` worker is now actually invoked for at least one of them (TikTok, YouTube, X, or article)
- [ ] #8 If a regression on existing tests is introduced (e.g. job status no longer updates), the cause is documented and a follow-up task created
<!-- AC:END -->
