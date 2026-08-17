---
id: task-281
title: >-
  Meter audio quota per user and per content, never twice for a media the user
  already holds
status: To Do
assignee: []
created_date: '2026-08-17 22:20'
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
- [ ] #1 Before any audio debit, the ingestion path checks whether the requesting user already holds a non-deleted library row with the same media_key, across every folder and collection
- [ ] #2 A save of a media the user already holds debits zero minutes, whether or not a processing job runs for it
- [ ] #3 A user's first save of a media debits normally even when the pipeline is skipped because another user already processed that content
- [ ] #4 The per-user check is separate from the global idempotence reservation, which keeps deciding only whether the pipeline runs and is not repurposed as a quota signal
- [ ] #5 A redelivered or retried submission cannot debit the same save twice: the existing per-job idempotency token still governs the debit and its settlement
- [ ] #6 The settlement in the transcription worker still applies only the difference with what the gate debited, and a skipped debit does not make it settle a full duration
- [ ] #7 The rule implemented for a media the user previously deleted is stated in the code and matches what the description records
- [ ] #8 ruff and mypy are clean
<!-- AC:END -->
