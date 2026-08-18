---
id: task-281
title: >-
  Meter audio quota per user and per content, never twice for a media the user
  already holds
status: Done
assignee: []
created_date: '2026-08-17 22:20'
updated_date: '2026-08-18 02:50'
labels:
  - ingestion
  - backend
  - quota
dependencies:
  - task-280
priority: medium
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
## Rule

Saving a media a second time must never cost the user audio minutes again. If the media is already in their library — **any collection, any folder** — the save is free. A user filing the same podcast into two collections pays once.

The converse is the case the current code gets wrong in the other direction, see below.

## Where the debit happens today

The debit is taken at submission, before any provider minute is spent: `audio_quota_gate` establishes the duration, asks `quota_enforcer`, debits once, and forwards `quota_debited_minutes` in the SQS payload so `deepgram_worker` only settles the difference with the duration Deepgram actually billed.

That gate sits on the path that creates a processing job. The idempotence short-circuit in `orchestrators.py` returns at lines 198-214, **before** the gate — so today a deduplicated save debits nothing at all. Two consequences:

- **The rule above happens to hold**, but by accident: it holds because no job runs, not because anyone checked whether this user already has the content. Once task-280 makes each save its own row, that accident must become an explicit, per-user check.
- **A leak in the other direction.** Idempotence is global across users. When another user has already processed a media, the *first* save by this user is deduplicated too — and is therefore never debited, even though it is their first copy of that content. They get the minutes for free.

## Scope

Move the decision from "did a job run?" to "does this user already hold this content?": before debiting, look up the user's library for a non-deleted row carrying the same `media_key`. If one exists, skip the debit; if none does, debit as usual — including when the pipeline is skipped because someone else already processed the media.

The lookup is per user and across all collections. It must not be confused with the global idempotence reservation, which stays exactly as it is and keeps answering a different question: whether the *pipeline* needs to run.

**Default applied for the leak, open to the owner's override.** This task implements "debit on the user's first save even when the content is globally deduplicated", on the grounds that the quota measures the user's entitlement to consume audio, not our provider bill. If the owner prefers the quota to track real provider cost, the rule flips to "never debit a deduplicated save at all" and only the first branch of the check changes.

## Notes to the owner

- DEPLOY CHECK — after merge, save one media, note the minutes debited, then save the same media into a second collection and confirm the balance does not move.
- Deleted items: the task treats a row the user has deleted as no longer held, so a re-save after deletion debits again. Say so if you want the grace window before purge to count as still held.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 Before any audio debit, the ingestion path checks whether the requesting user already holds a non-deleted library row with the same media_key, across every folder and collection
- [x] #2 A save of a media the user already holds debits zero minutes, whether or not a processing job runs for it
- [x] #3 A user's first save of a media debits normally even when the pipeline is skipped because another user already processed that content
- [x] #4 The per-user check is separate from the global idempotence reservation, which keeps deciding only whether the pipeline runs and is not repurposed as a quota signal
- [x] #5 A redelivered or retried submission cannot debit the same save twice: the existing per-job idempotency token still governs the debit and its settlement
- [x] #6 The settlement in the transcription worker still applies only the difference with what the gate debited, and a skipped debit does not make it settle a full duration
- [x] #7 The rule implemented for a media the user previously deleted is stated in the code and matches what the description records
- [x] #8 ruff and mypy are clean
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
## What was built

`durable_media_service.user_holds_media(user_id, media_key, exclude_media_item_id)` is the new
single answer to "does this user already hold this content?". It reads
`user_media_store.list_for_user_by_media_key`, which queries the **owner's own partition**
(`user_id`) with a consistent read and filters on `media_key` — deliberately *not* the
cross-user `media-key-index`, see the dev finding below. Every folder and collection counts;
soft-deleted rows do not. `exclude_media_item_id` removes the save being made, because the
durable row is written before the quota gate runs (task-218 §4.3) and would otherwise exempt
itself.

Three call sites now ask it before any audio debit:

- `audio_quota_gate.gate_audio_transcription` — the shared gate, so all six producers
  (orchestrator staged-audio and direct-URL paths, TikTok, YouTube, podcast resolution, RSS
  poll) get the rule at once. It excludes `media_item_id`, defaulting to `job.media_item_id`,
  so no producer needed a signature change.
- `orchestrators._build_duplicate_outcome` — the deduplicated-save path, which returned before
  the gate and therefore debited nothing at all.
- `POST /api/media/upload-audio` — its content key is per user and per file, so an identical
  re-upload is the same save twice.

## Two decisions worth recording

**Check kept, debit skipped.** The task says "before debiting … skip the debit", not skip the
check, so `quota_enforcer.gate_audio_submission` gained `debit: bool = True`: an already-held
save still runs `check_submission_allowed` and charges nothing. Free means *the user is not
charged*, not that the pipeline may spend unbounded Deepgram minutes for someone over their
cap — the gate is the last point where that spend can be refused (task-250 Layer 1).

**The leak is closed for terminal content only.** `_debit_deduplicated_audio_save` charges the
user's first save of globally deduplicated content, sized from the content job's
`transcription_metadata.audio_duration_seconds` (never `duration_seconds`, which is the API
call's latency). Audio-metered is decided by `provider == "deepgram"`, so articles, documents,
native subtitles, Apify and shared-text transcripts debit nothing. A save that lands while the
content is *still being processed* has no established duration and is not debited — a narrower
residual leak than the one closed, and it needs two users saving the same media inside one
processing window. Say so if you want it charged provisionally instead.

The debit is taken with `record_submission`, outside the gate: there is no provider spend left
to refuse on that path, so refusing would cost the user their library entry to protect a bill
nobody is about to pay. Overrun follows the settlement's existing policy — the counter stays
true and the next real import is refused naturally.

## Settlement contract

`quota_debit_skipped` joins `quota_debited_minutes` in the Deepgram payload (added to
`deepgram_dispatch.enqueue_deepgram_transcription` and to the five hand-built message bodies).
`deepgram_worker._settle_audio_quota` returns early on it. Without that flag the settlement
would read `quota_debited_minutes == 0` and charge the whole billed duration, undoing the
exemption one step later — which is AC #6.

Idempotency is unchanged where it existed: the gate still debits under `gate_token(job_id)` and
settles under `settlement_token(job_id)`. The new deduplicated debit has no job of its own and
uses `gate_token(media_item_id)`, the save's own library id — the same convention the non-audio
counter in `ingest_url` already uses.

## Verified

- `ruff check media_summarizer/` and `mypy media_summarizer/` clean (169 files).
- All twelve touched modules import cleanly — no cycle from `audio_quota_gate` →
  `durable_media_service`.
- Four scenarios run against the real `user_media-dev` table, with throwaway rows under a
  synthetic user id, all removed afterwards (0 left): first save → not held (debits); second
  save → held (free); another user's save of the same content → not held (their first save
  debits); re-save after a soft delete → not held (debits again, AC #7).

## Owner notes

- DEPLOY CHECK (from the description) — after merge: save one media, note the minutes, save it
  into a second collection, confirm the balance does not move.
- Worth checking too: save a media another account already processed and confirm the minutes
  *are* debited on that first save (the leak this closes).
- **Pre-existing, not fixed here:** `user_media-dev` has **no GSI at all** — `media-key-index`
  is declared in `infrastructure/terraform/modules/platform/dynamodb_user_media.tf` but was
  never applied to dev. So `user_media.list_by_media_key` raises there, and the only caller,
  `durable_media_service.mirror_job`, swallows it ("Could not fan out media_key") — the
  cross-user status/metadata fan-out is silently a no-op on dev. Invisible today with one
  account. It is why this task queries the base table instead, which also made the lookup
  strongly consistent, but the drift itself deserves its own `terraform apply` or task.

## Follow-up after the owner's terraform apply (2026-08-18)

The drift reported above is closed. `media-key-index` is now `ACTIVE` on `user_media-dev` with
`ProjectionType: ALL`, and the backfill is complete: all 8 base-table rows are returned through
the index, so `user_media.list_by_media_key` no longer raises and `mirror_job`'s cross-user
fan-out works on dev. `terraform plan` on `envs/dev` reports **No changes**.

The task-281 lookup was re-verified against dev after the apply and is unaffected — it reads the
user's own partition by design, so it agrees with the index on every row, and the four
behavioural scenarios (first save debits / second save free / another user's first save debits /
re-save after deletion debits) still pass, throwaway rows removed.

Code live on dev: `Deploy Lambda Functions` succeeded for commit `4a0d4c4`, and both the API and
worker Lambdas run the images tagged `api-4a0d4c44…` / `worker-4a0d4c44…`.
<!-- SECTION:NOTES:END -->
