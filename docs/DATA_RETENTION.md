# Data retention

Who is allowed to destroy what, and after how long. Authoritative for the
backend; the user-facing wording lives in `docs/compliance/privacy-policy.md`.

Source: §6.1 and §6.4 of
`docs/research/task-218-durable-media-library-persistence/README.md`
(owner-validated Option A). Implemented by task-243.

## 1. The rule that matters

**A user's library has no retention clock. Only the user can end its life.**

The incident that produced the `user_media` table was a *processing* retention
clock (`processing_jobs.expire_at`) applied to *user-owned* data: expiring a job
row deleted the user's media entry, its folder and its tags, because every
library read resolved through that job. Two months of saves disappeared.

So the two clocks are now separate, structurally and not by convention:

| | Owns | Clock | Who may write it |
|---|---|---|---|
| **Library** (`user_media`) | what the user saved | none, except a purge the user asked for | `user_media.mark_deleted` only, reached only from `core/services/media_deletion_service.py` |
| **Processing** (`processing_jobs`) | how a save was executed | 30-90 days after the last transition (Phase 4, task-239 keeps it frozen off until reads move) | the pipeline |

`scripts/check_purge_at_writers.py` fails CI if a second writer of `purge_at` or
`deleted_at` appears anywhere in `media_summarizer/` or `scripts/`. That guard is
the enforcement; the table comment in
`infrastructure/terraform/modules/platform/dynamodb_user_media.tf` is the
explanation.

## 2. Per-store retention

| Store | Retention | What ends it |
|---|---|---|
| `user_media` | **indefinite** | user deletion (§3) or account deletion (§4). Nothing else. |
| `media_artifacts` + their S3 objects | lifetime of the user's final retained save row for that `media_key` | purge cascade (`core/services/media_purge_service.py`) |
| Transcripts, audio, documents in S3 | lifetime of the final retained save row for that `media_key` | same cascade, by job-id prefix |
| Algolia documents | lifetime of their `user_media` row | deleted at soft-delete time, re-deleted by the cascade |
| `processing_jobs` | 30-90 days after the last status transition — **TTL currently frozen off** (task-239) until no read path depends on it | TTL on `expire_at`, Phase 4 |
| `media_idempotence` | lifetime of the final visible save for that content | final content purge (conditional on the recorded job id) |
| `artifact_idempotence` / `translation_idempotence` | lifetime of the artifact they lock | purge cascade |
| Job archives in S3 (`archives` bucket) | GLACIER_IR at day 0, expire at 365 days | bucket lifecycle rule in `archiving.tf` |
| Library snapshots (AWS Backup) | 90 days | backup plan lifecycle (§5) |
| Library exports (S3, DYNAMODB_JSON) | 365 days | same bucket lifecycle rule as job archives |

## 3. User deletion of one item

`DELETE /api/media/{media_item_id}` → `core/services/media_deletion_service.py`.

1. **Soft delete.** `deleted_at = now`, `purge_at = now + 30 days`. Idempotent:
   deleting twice does not push the purge date out.
2. **Invisible immediately.** `utils/user_media.get_user_media` returns `None`
   for a soft-deleted row unless the caller explicitly asks for it, and the
   Algolia chunks are deleted synchronously — a "deleted" item that still answers
   a search is still visible.
3. **Purged after 30 days.** DynamoDB TTL removes the row (best effort, within
   ~48h of `purge_at`). The stream `REMOVE` drives
   `workers/cleanup/media_lifecycle.py`, which destroys the artifacts, the S3
   objects and the search records.

The 30 days are a recovery window, not a legal one. Each re-save receives a new
`media_item_id`; it never revives or collides with the soft-deleted row. When TTL
finally removes that row, the cascade retains content-scoped artifacts and
transcript objects while another retained row still references the same
`media_key`. Support can undo a deletion inside the window by clearing
`deleted_at` and `purge_at`.

## 4. Account deletion

Implemented by task-224 in `core/services/account_deletion_service.py`, not by
the path above: an erasure request removes the rows now
(`user_media.delete_all_for_user`) instead of scheduling them 30 days out.
Soft-deleted rows still waiting for their TTL are taken with everything else,
because the purge enumerates the whole `user_id` partition.

The per-media cascade is shared with the TTL purge
(`core/services/media_purge_service.py`) so the two paths cannot drift: whatever
one deletes, the other deletes.

## 5. Backup and restore windows

Three tiers, three explicit windows
(`infrastructure/terraform/modules/platform/backup_library.tf`):

| Tier | Window | Covers | Restore path |
|---|---|---|---|
| PITR (continuous) | **35 days** | a bad write, to the second | `restore-table-to-point-in-time` → new table |
| AWS Backup snapshots (weekly) | **90 days** | the table itself lost or corrupted beyond PITR; a mistake noticed a month later | `start-restore-job` from vault `media-summarizer-library-<env>` → new table |
| S3 exports (monthly, DYNAMODB_JSON) | **365 days** | the vault lost; readable without DynamoDB (Athena); monthly audit copy | re-import or query in place |

Covered stores: `user_media`, `user_folders`, `user_tags`, `media_artifacts` —
the user-owned ones. The operational tables are deliberately excluded: losing
them costs a re-run, not a library.

**A restore is never transparent.** DynamoDB restores into a *new* table and the
restored table does **not** carry the TTL configuration over. Re-enabling the
`purge_at` TTL is a mandatory step of every restore; the
`user-media-purge-overdue` alarm is what catches it being forgotten. Full
procedure: `infrastructure/observability/runbooks/durable-media.md#restore`.

## 6. Known conflict with the published privacy policy — OWNER ACTION

`docs/compliance/privacy-policy.md` §7 currently tells users that copies of
deleted data held in infrastructure backups "expire automatically within 35
days". That was true when PITR was the only tier. With the 90-day snapshots and
the 365-day monthly exports mandated by §6.4 of the benchmark, the accurate
statement is:

- live systems: erased immediately on account deletion;
- backup snapshots: up to **90 days**;
- cold monthly exports: up to **365 days**.

Backups are not individually editable, so an erasure request is not propagated
into them — it is honoured by their expiry. The wording is a legal decision, so
task-243 leaves the policy text untouched and flags it here instead: the owner
should either update §7 of the privacy policy or shorten
`library_backup_retention_days` / the archives bucket lifecycle to match what is
published.
