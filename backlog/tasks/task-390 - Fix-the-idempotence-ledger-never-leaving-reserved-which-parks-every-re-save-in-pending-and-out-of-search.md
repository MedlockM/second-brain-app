---
id: task-390
title: >-
  Fix the idempotence ledger never leaving reserved, which parks every re-save
  in pending and out of search
status: Done
assignee: []
created_date: '2026-09-09 21:44'
updated_date: '2026-09-10 08:33'
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
- [x] #1 The path that completes a media marks the content's idempotence ledger entry as processed, and no successful completion leaves it at reserved
- [x] #2 A save deduplicated against already-processed content is persisted with that content's real title, creator and cover rather than the placeholder derived at submission time
- [x] #3 A save deduplicated against already-processed content is submitted for search indexing under its own media item id, reusing the existing transcript with no re-extraction and no LLM call
- [x] #4 A ledger entry left at reserved whose referenced job has reached a terminal state does not park a new save in pending; the save resolves from the job's actual state
- [x] #5 The reserved rows in media_idempotence-dev whose content is in fact processed are reconciled to processed, verified by reading the table back with the AWS CLI
- [x] #6 The claim in the search hit documentation that a deletion does not unindex a transcript is corrected to match what the deletion path actually does
- [x] #7 ruff and mypy are clean
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
### Root cause, confirmed

`media_idempotence.mark_processed()` had zero call sites, so no row ever left `reserved`. `orchestrators.py` short-circuits into the duplicate branch on any ledger row carrying a `job_id`, and `reserved` mapped to `PENDING` — so every re-save of an already-ingested URL was persisted pending, waiting on a job that had finished. Nothing was wrong with the reservation, the transcript or the artifacts; only the ledger's terminal write was missing.

### What changed

- `media_summarizer/utils/media_idempotence.py` — `mark_processed` / `mark_failed` now share one guarded writer. The update is conditional on `attribute_exists(media_key)` and, when a `job_id` is given, on the row still belonging to that job (or to none). A stale redelivered completion therefore cannot stamp a newer reservation, and a missing row returns `False` instead of raising.
- `media_summarizer/workers/events/media_completed_worker.py` — this consumer is the single join point every ingestion path publishes to, so it is where the ledger is closed: `processed` on success (before the indexing fan-out, so a save landing mid-event reads the truthful ledger), `failed` on the failure branch. The write re-raises on error on purpose — SQS redelivers, and a persistent failure surfaces on the existing DLQ-depth alarm for `EPISODE_COMPLETED_EVENTS_QUEUE` (`pipeline_alerts.tf`), so no new alarm and no Terraform change were needed.
- `media_summarizer/core/services/search_index_dispatch.py` (new) — the worker-local `_enqueue_search_indexing` became a shared service, now the single writer of `SEARCH_INDEXING_QUEUE`, used by both the completion worker and the deduplicated save path. The message body is unchanged.
- `media_summarizer/core/services/durable_media_service.py` — new `display_attributes_from_job` shared by `mirror_job` and `finalize_deduplicated_save` (the mapping was duplicated inline). `finalize_deduplicated_save` now takes the content job, rehydrates title/creator/cover/duration/source from it, only claims `owned_job_id` when the job belongs to the saving user, and enqueues transcript indexing under the new `media_item_id` when the save resolves `ready`.
- `media_summarizer/core/media_ingestion/adapters/orchestrators.py` — `_status_from_idempotence` (a pure string map) is deleted. The duplicate branch now loads the referenced job and resolves the save from the ledger *and* the job's real state, reconciling a stranded `reserved` row on the way. The audio-quota debit reuses that same job instead of re-fetching it.
- `media_summarizer/core/services/media_submission.py` — the podcast dedup branch loads the content job and passes it through, so an episode re-save is finalised like every other.
- `media_summarizer/api/endpoints/search.py` — AC #6. `media_deletion_service.delete_media_for_user` *does* call `search_indexing.delete_document` synchronously; the docstring said the opposite. Corrected to what actually happens: the removal is immediate but best-effort, retried by the 30-day purge cascade, and an `in_library: false` hit is a chunk set that outlived a failed index cleanup.
- `media_summarizer/scripts/reconcile_media_idempotence.py` (new) — one-off reconciliation, dry-run by default, `MEDIA_IDEMPOTENCE_RECONCILE_APPLY=true` to write.

### Dev reconciliation (eu-west-3, AC #5)

Census before: 70 rows in `media_idempotence-dev`, 64 `reserved` / 6 `processed`. Of the 64 reserved: 44 jobs completed, 5 failed, 15 jobs no longer in `processing_jobs-dev` (swept by the 90-day TTL).

Applied: `marked_processed: 44`, `marked_failed: 5`, `job_missing: 15`, `skipped_status_processed: 6`. Read back with the AWS CLI: 50 `processed`, 5 `failed`, 15 `reserved` — and a per-row `get-item` on `processing_jobs-dev` confirms all 15 remaining reserved rows point at jobs that no longer exist (0 alive).

### Deliberate scope decisions

- **`reserved` + job gone resolves to `FAILED`, not to a fresh ingestion.** 14 of those 15 contents still have a `{job_id}.txt` transcript in the transcripts bucket, but the pointer to it lived on the job row that expired, so nothing can resolve it. Making expired-job content re-ingestable means re-spending provider quota on a save the user expects to be free, which is a separate decision — left for a follow-up rather than smuggled into a bug fix.
- **A save deduplicated against an *in-flight* job is still not search-indexed by this change.** That fan-out is watcher-based and happens when the canonical job completes; `mirror_job` fixes the row's status and metadata at that point. Pre-existing gap, unchanged here, documented rather than half-fixed.
- **No automated tests were added**, per the project rule forbidding them. Nothing under `tests/` referenced the changed signatures, so nothing broke.

### Verification

- `ruff check media_summarizer/` — all checks passed.
- `uv run --extra dev mypy media_summarizer/` — success, 185 source files.
- Direct AWS CLI reads against `media_idempotence-dev` and `processing_jobs-dev` in `eu-west-3` (see above).
- No Terraform file changed, so no `terraform validate` run was needed.

### Out of reach from the worktree

The `DEPLOY CHECK` in the description (delete a media, re-save the same URL, confirm the row opens on its transcript with the real title and cover and is findable by a word from its text) cannot be done here: the deploy happens on push to `main`, after this run ends. It stays an owner check.
<!-- SECTION:NOTES:END -->
