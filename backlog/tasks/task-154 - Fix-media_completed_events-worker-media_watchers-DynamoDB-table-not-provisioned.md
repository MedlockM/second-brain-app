---
id: task-154
title: Fix media_completed_events worker — media_watchers DynamoDB table not provisioned
status: Done
assignee: []
created_date: '2026-06-09 23:00'
labels:
  - bug
  - infrastructure
  - backend
dependencies: []
priority: high
dispatchable: true
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
## Context

After task-147 (event_type alignment between producer and consumer of completion events), the `media_completed_events` worker now processes the message correctly. **But it then fails when trying to query the `media_watchers` DynamoDB table** because that table doesn't exist in AWS dev.

## Symptom

`pytest -m e2e tests/e2e/test_phase4_other_sources.py::test_document_upload` times out at `transcribing` 50% (no transition to `completed`).

CloudWatch `/aws/lambda/media-summarizer-worker-media_completed_events`:

```
"message": "Failed to read media watchers for doc:<user>:sample.pdf:639:
            An error occurred (ResourceNotFoundException) when calling
            the Query operation: Requested resource not found"
"message": "No watchers for media key doc:<user>:sample.pdf:639"
```

The worker logs the second message after the first as a graceful "no watchers, nothing to fan out". But the upstream callsite of the watcher query likely doesn't progress the job to `completed` because of the exception, and the test sees `transcribing` 50% forever.

## Root cause

`media_summarizer/utils/media_watchers.py` (or wherever the watcher table is read) targets a DynamoDB table named `media_watchers`. List of tables in AWS dev (per `aws dynamodb list-tables --region eu-west-3`):

- ✅ `media_artifacts` (created by task-122)
- ✅ `media_idempotence`
- ❌ `media_watchers` — **not created**

Either:

A. The table was renamed somewhere between code and Terraform (e.g. `episode_watchers` exists; the code targets `media_watchers`)
B. The table was supposed to be created by Terraform but the resource was never added

Investigation step:
```bash
grep -rnE "media_watchers|MEDIA_WATCHERS|episode_watchers" \
  media_summarizer/ infrastructure/terraform/*.tf
```

## Fix

**Option A — Rename mismatch.**
- Confirm the existing table covers the use case (e.g. `episode_watchers` schema matches).
- Update the code to use the existing table name.
- No infra changes needed.

**Option B — Missing table.**
- Add `aws_dynamodb_table.media_watchers` to `infrastructure/terraform/dynamodb_core_tables.tf`.
- Schema needs investigation: hash key probably `media_key` (string), range key probably `user_id`. GSIs needed for inverse lookups (find all media a user watches).
- `terraform apply`.

After fixing: also verify the **upstream caller** doesn't crash on the query — it should treat the empty result as "no watchers, no fan-out" cleanly, and progress the job to `completed` regardless.

## Reproduction

```bash
.venv/bin/pytest -m e2e tests/e2e/test_phase4_other_sources.py::test_document_upload -v
```

Wait at `transcribing` 50%. CloudWatch on `media_completed_events` shows the ResourceNotFoundException.

## Out of scope

- Implementing the watcher fan-out feature (probably already coded; this task is about provisioning, not feature work)
- Mobile-side UX for watch notifications
- Other DynamoDB tables that may also be missing (only known mismatch is `media_watchers`)

## References

- task-122 (created `media_artifacts` table similarly missing before)
- task-143 (queue mismatch fix at SQS layer)
- task-147 (event_type fix at message-body layer — now uncovered this DynamoDB-layer bug)
- `media_summarizer/utils/media_watchers.py` (likely caller of the missing table)
- `media_summarizer/workers/events/media_completed_worker.py` (worker that triggers the read)
- CloudWatch `/aws/lambda/media-summarizer-worker-media_completed_events` 2026-06-09 ~22:50 UTC
- `tests/e2e/test_phase4_other_sources.py::test_document_upload`
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 Investigation done: confirmed whether `media_watchers` is a rename mismatch (Option A) or a missing table (Option B). Decision documented.
- [ ] #2 Fix applied per the chosen option (rename or provision)
- [ ] #3 If provisioning: `terraform apply` clean; `aws dynamodb list-tables --region eu-west-3` shows `media_watchers`
- [ ] #4 Lambda image rebuilt + redeployed if needed
- [ ] #5 `pytest -m e2e tests/e2e/test_phase4_other_sources.py::test_document_upload` passes (job reaches `completed`)
- [ ] #6 No regression on the 11 already-passing tests
- [ ] #7 The watcher-fan-out logic is verified to actually fire (not just silently skipped) for at least one source — this is the V1 feature that depends on the table
<!-- AC:END -->
