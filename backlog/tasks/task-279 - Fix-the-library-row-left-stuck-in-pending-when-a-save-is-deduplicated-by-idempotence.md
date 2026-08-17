---
id: task-279
title: >-
  Fix the library row left stuck in pending when a save is deduplicated by
  idempotence
status: To Do
assignee: []
created_date: '2026-08-17 22:19'
labels:
  - bug
  - ingestion
  - backend
dependencies: []
priority: high
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
## Problem

Saving a media whose `media_key` was already processed produces a library row that never leaves `pending`. The detail screen shows "Transcribing video..." and spins until the mobile hook gives up after five minutes (`mobile/src/hooks/useMediaDetailPolling.ts:11`), even though the transcript has existed for days.

Reproduced on dev on 2026-08-17 at 21:53:28 with `youtube.com/watch?v=ApYhtsdHbVg`:

- the API logged `media.ingest.duplicate_reused` and reused job `0d7b9533-9725-4acb-9804-92c33cbf3764`, `completed` since 2026-08-09 19:11:10 with its transcript in S3 (165 segments);
- the library row created by that request, `mi_f848dd7a44d4bdaf423a47d9bc9568d1`, still carries `processing_status: pending` and **no `last_job_id`**;
- it is the only one of the user's 25 rows in `pending`, and the only recent one without `last_job_id`.

## Cause

In `orchestrators.py`, the durable library row is created first (line 186) with the default `PENDING`, then the idempotence short-circuit returns at lines 198-214 without ever writing a status back onto the row it just created. No job runs, so `mirror_job` never fires and nothing will correct it later.

The read path then has nothing to work with: `resolve_job_for_record` finds no job (no `last_job_id`, and an `mi_` id is not usable as a job id), so `_canonical_job_status` falls back to the row's own `pending` and the client is told to keep waiting.

Note that `_build_duplicate_outcome` already computes the correct status at `orchestrators.py:91` — the POST response says the item is done at the very moment the row is persisted as pending. The value exists; it is simply never written.

Worth reading: `_canonical_job_status` deliberately resolves an *unknown* status to `COMPLETED` for exactly this reason ("with no job in existence nothing is in flight, and claiming otherwise would tell the client to keep waiting for a pipeline that is not running"). The guard does not fire here because `pending` is an explicit value rather than an absence.

## Scope

Make the deduplicated path leave a row the client can read: the status already computed for the outcome is written onto the row, together with a pointer to the content when the reused job belongs to the requesting user.

The reused job may belong to **another user** — idempotence is global. Handing that job id to this user is the §1.6.1 defect `_build_duplicate_outcome` documents, so the row must reach a terminal status without borrowing a foreign job pointer. How such a row serves its transcript is the structural question, and it belongs to the follow-up task on multiple saves, not here; this task must at minimum stop presenting a finished item as in flight.

This fix stays valid after that follow-up: a deduplicated save will still be the case where no job runs and the row must be completed from what already exists.

## Notes to the owner

- The stuck row on dev is `mi_f848dd7a44d4bdaf423a47d9bc9568d1` for user `4cd1abcb-…`; repairing or deleting it is part of the task so the item stops spinning without waiting for a deploy.
- DEPLOY CHECK — after merge, save an already-saved YouTube video again and confirm the detail screen opens on the transcript instead of the processing spinner.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 On the idempotence short-circuit, the library row created by that same request is persisted with the status already derived for the outcome, instead of being left at the default pending
- [ ] #2 When the reused job belongs to the requesting user, the row carries a pointer to it so the detail read resolves the existing transcript
- [ ] #3 When the reused job belongs to another user, the row still reaches a terminal status and no foreign job id is written onto it or returned to the caller
- [ ] #4 No code path can leave a library row in pending or processing when no processing job exists for it and none is going to run
- [ ] #5 The stuck row mi_f848dd7a44d4bdaf423a47d9bc9568d1 in user_media-dev is repaired or removed, verified by reading the row back with the AWS CLI
- [ ] #6 ruff and mypy are clean
<!-- AC:END -->
