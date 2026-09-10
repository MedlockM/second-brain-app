---
id: task-390
title: >-
  Fix the idempotence ledger never leaving reserved, which parks every re-save
  in pending and out of search
status: To Do
assignee: []
created_date: '2026-09-09 21:44'
labels:
  - bug
  - ingestion
  - backend
  - search
dependencies: []
priority: high
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
## Problem

Saving a URL that was saved before parks the new library row in `pending` forever: no pipeline runs, no transcript is produced, and the media never reaches the search index. Searching a word that is in its own text returns nothing.

Reproduced on dev 2026-09-09 with `https://www.mister-garden.com/notre-carte`, saved 2026-09-08 11:22:39, deleted 51 seconds later, saved again 2026-09-09 18:34:49. The second save `mi_d51f15dc63fc43839f3635a499c326f3` was the only one of the user's 76 rows in `pending`, and querying `media_items_dev` for "Mister Garden" returned 0 hits — while "salade" appears five times in the transcript that had been sitting in S3 since the day before.

## Cause

`media_idempotence.mark_processed()` (`media_summarizer/utils/media_idempotence.py:108`) is **never called**. Zero call sites in the repository. The only other occurrence of the string is an unrelated watcher error label at `media_summarizer/workers/events/media_completed_worker.py:345`, in a module that does not even import the ledger.

The ledger therefore never leaves `reserved`. On dev, 65 of 70 rows in `media_idempotence-dev` were `reserved` with `updated_at == created_at`; the only 5 `processed` rows were all written by a one-off backfill on 2026-08-12 at 19:02.

The orchestrator reads the ledger before doing anything (`orchestrators.py:369`) and short-circuits into `_build_duplicate_outcome` as soon as a row with a `job_id` exists. `_status_from_idempotence("reserved")` maps to `PENDING` (`orchestrators.py:76`), so the row is persisted as pending and waits for a job that finished long ago.

This is precisely the branch task-279 left open. Its delivery note reads "only an actual reserved ledger entry remains pending", which is correct only if `reserved` means "in flight". Because `mark_processed` is never called, `reserved` is permanent and that branch is the normal case rather than the exception — so task-279's AC #4 ("no code path can leave a library row in pending when no job exists and none is going to run") is in fact violated on every re-save.

## Two further gaps in the deduplicated path

Everything needed to complete such a save survives. Verified on dev for the case above: job `662737ff-…` intact and completed, its transcript in S3 (3707 bytes), and both artifacts (`review_blurb`, `quiz`) already resolvable because `scope_key` is `user_id#media#media_key` and is identical across saves — the quiz was in fact generated successfully against the stuck row. Even once the ledger is truthful, two things are still missing:

- `finalize_deduplicated_save` writes only `processing_status` and `last_job_id` (`durable_media_service.py:291-293`). Title, creator and cover are never rehydrated, so the row keeps its submit-time placeholder — here "Article — 09 Sep 2026" with no creator and no cover, while the reused job carries the real title and "Mister Garden".
- The deduplicated path never enqueues search indexing. Algolia records are keyed `objectID = {media_item_id}_chunk_{i}` and every save gets a fresh `media_item_id`, so a deduplicated save is absent from search until indexed. Reusing the previous save's records is not an option: `load_display_details` resolves a hit's `media_item_id` against the library row, and a deleted row yields `in_library: false` with no title, no cover and no possible action — a dead hit pointing at the deleted item. Indexing costs one `save_objects` over a transcript that already exists: no re-fetch, no LLM call, no quota.

## Scope

Make the ledger tell the truth about what has been processed, and make a deduplicated save arrive complete: terminal status, the content's real display metadata, and an entry in the search index. Reconcile the ledger rows already stranded on dev, since the fix alone does not retrofit them.

Deduplication must keep saving the expensive half of the work — extraction, transcript, LLM artifacts. Only the per-save indexing is re-done, because the index is keyed by save and not by content.

## Notes to the owner

- The dev row `mi_d51f15dc63fc43839f3635a499c326f3` was repaired by hand on 2026-09-09: ledger set to `processed`, row set to `ready` with the job's title/creator/cover, and an indexing message enqueued and consumed. The media is now the first hit for "salade". It is no longer part of this task's scope.
- Keying the index by `media_key` rather than by `media_item_id` would make a deduplicated save need no indexing at all. It was considered and set aside: tenant isolation is today a single `user_id:X` filter and deletion a trivially correct `delete_by`, and both would become materially harder to keep correct in exchange for one avoided `save_objects`. Reopen it only as a deliberate index restructure.
- DEPLOY CHECK — after merge: delete a saved media, save the same URL again, and confirm the new row opens on its transcript, shows the real title and cover, and is findable by a word taken from its text.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 The path that completes a media marks the content's idempotence ledger entry as processed, and no successful completion leaves it at reserved
- [ ] #2 A save deduplicated against already-processed content is persisted with that content's real title, creator and cover rather than the placeholder derived at submission time
- [ ] #3 A save deduplicated against already-processed content is submitted for search indexing under its own media item id, reusing the existing transcript with no re-extraction and no LLM call
- [ ] #4 A ledger entry left at reserved whose referenced job has reached a terminal state does not park a new save in pending; the save resolves from the job's actual state
- [ ] #5 The reserved rows in media_idempotence-dev whose content is in fact processed are reconciled to processed, verified by reading the table back with the AWS CLI
- [ ] #6 The claim in the search hit documentation that a deletion does not unindex a transcript is corrected to match what the deletion path actually does
- [ ] #7 ruff and mypy are clean
<!-- AC:END -->
