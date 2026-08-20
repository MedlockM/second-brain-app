---
id: task-311
title: Purge last_engaged_at beyond the 90-day window so nothing is stored past it
status: To Do
assignee: []
created_date: '2026-08-20 21:04'
labels:
  - backend
  - phase-6
dependencies:
  - task-305
priority: medium
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
The engagement signal behind the Inbox "Continue learning" row (task-305, Option A of `docs/research/task-303-engagement-recency-model/README.md`) is one attribute, `last_engaged_at`, on `user_media_v1` and `user_folders_v1` rows. The 90-day freshness window is enforced **only at read time** — `engagement_service.list_recent` queries the sparse `engaged-index` with a sort-key range condition — so a stamp written 6 months ago is still stored, and still occupies an entry in the GSI, forever.

The owner has decided there is no reason to keep it: past 90 days the value must be **removed from the row**, not merely hidden. Removing the attribute also removes the row from the sparse GSI, which is the point — the index should hold engaged items, not the whole history of them.

## Why not a TTL

DynamoDB allows one TTL attribute per table, `user_media_v1` already uses it for `purge_at` (user-initiated deletion, invariant I2), and `dynamodb_user_media.tf:126-134` forbids adding a second one. A TTL would also destroy the whole library row, not one attribute — the wrong granularity entirely. The purge is therefore an explicit write.

## Where it goes

The daily reconciliation of the `media_lifecycle` worker (`media_summarizer/workers/cleanup/media_lifecycle.py:343`, `run_reconciliation`, EventBridge `cron(30 3 * * ? *)`) **already scans `user_media` end to end** with a `ProjectionExpression` (`:349-352`). Adding `last_engaged_at` to that projection and issuing the removals from the same pass costs one extra attribute per scanned row and no new schedule, no new Lambda, no new IAM. `user_folders_v1` is **not** scanned today and needs its own pass — that table carries the attribute with no index of its own, by design.

## Scope

- Extend the daily reconciliation to remove every `last_engaged_at` older than the window, on both `user_media_v1` and `user_folders_v1`.
- The window comes from `engagement_service.RECENT_WINDOW_DAYS` — one source of truth, not a second constant that can drift from the read path.
- Report the count in the existing `EVENT_RECONCILED` structured log alongside the other gauges, so a systematic failure is visible in CloudWatch.

## Constraints

- **Conditional write.** The removal must carry a condition on `last_engaged_at` still being older than the cutoff, so an engagement stamped between the scan and the write is never erased.
- **Never through `user_media.update_attributes`.** That helper always appends `updated_at`, and `updated_at` is the cache key of the `expo-image` covers — purging through it would invalidate every cover in the app. Use a targeted `UpdateItem` with `REMOVE`, the way `stamp_engagement` does its `SET`.
- **Do not touch `purge_at`, `deleted_at`, or any other attribute.** `scripts/check_purge_at_writers.py` must stay green (invariant I2).
- Soft-deleted rows (`deleted_at` present) are already excluded from the row at read time; purging their stale stamp too is fine, but must not resurrect or modify anything else about them.
- A failed purge must not fail the reconciliation as a whole — it logs and the run continues, like the other reconciliation gauges.
- No automated tests unless the owner asks. `ruff` and `mypy` clean.
- Nothing is deployed (`AGENTS.md`): no compatibility path, no flag to keep the old behaviour.

## Owner notes (not acceptance criteria)

- Applied on the next deploy of the worker image; the purge then runs at the next 03:30 UTC schedule. Nothing to `terraform apply` is expected — verify with `terraform plan` that this is indeed the case.
- Owner-side check after deploy: invoke the Lambda manually (or wait for the schedule), then confirm with the AWS CLI that no `user_media-dev` or `user_folders-dev` row carries a `last_engaged_at` older than 90 days, and that the `user_media.reconciled` log event reports the count of removals.
- The visible behaviour of "Continue learning" does not change at all — the read path already ignored these values. This task is about what is stored, not what is shown.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 The daily reconciliation removes last_engaged_at from every user_media_v1 row whose value is older than the window, and from every user_folders_v1 row likewise, in the same scheduled run
- [ ] #2 The cutoff is derived from engagement_service.RECENT_WINDOW_DAYS with no second window constant introduced anywhere
- [ ] #3 Each removal is a targeted UpdateItem with a REMOVE expression guarded by a condition on last_engaged_at still being older than the cutoff, and no code path routes it through user_media.update_attributes
- [ ] #4 No attribute other than last_engaged_at is written or removed by the new code, and python scripts/check_purge_at_writers.py exits 0
- [ ] #5 The count of removed stamps is reported in the reconciliation's existing structured log event alongside the other gauges
- [ ] #6 A failure on one removal is logged and does not abort the reconciliation run or raise out of it
- [ ] #7 ruff check . and mypy media_summarizer/ are clean, and terraform validate plus terraform plan exit 0 for the -dev environment with no infrastructure change required by this task
- [ ] #8 A comment at the purge site records why this is an explicit write and not a TTL (one TTL per table, purge_at owns it, wrong granularity), so the next reader does not re-litigate it
<!-- AC:END -->
