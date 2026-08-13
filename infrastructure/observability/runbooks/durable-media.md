# Durable Media Library Runbook

Operational runbook for the `user_media` durable library table (task-240, Phase 1 of
the task-218 benchmark), its Phase 2 backfill (task-241) and its deletion /
backup lifecycle (task-243, §6.2 + §6.4 + §6.5). Alarms are defined in
`infrastructure/terraform/modules/platform/durable_media_alerts.tf`.

Retention policy and the windows quoted below:
[`docs/DATA_RETENTION.md`](../../../docs/DATA_RETENTION.md).

Replace `<env>` with `dev`, `staging` or `prod` in every command below.

---

## Table of Contents

- [Write Failed](#write-failed)
- [Deletion Failed](#deletion-failed)
- [Unexplained TTL Deletions](#unexplained-ttl)
- [Purge Cascade Failed](#purge-cascade-failed)
- [TTL Sweeps Without a Cascade](#ttl-without-cascade)
- [Purge Overdue](#purge-overdue)
- [Orphan Artifacts](#orphan-artifacts)
- [Reconciliation Stopped](#reconciliation-stopped)
- [Restoring the Library](#restore)
- [Phase 2 Backfill](#backfill)
- [Emergency Rollback](#rollback)

---

## Write Failed

**Alarm:** `media-summarizer-durable-media-write-failed-<env>`
**Severity:** Critical
**Threshold:** any occurrence of the `durable_media.write_failed` log event in 5 minutes

### Why this is critical

`user_media` is the source of truth for a user's library. A failed write means either
a save that produced no library row, or a library row whose denormalised snapshot
has drifted from its processing job. The incident behind task-218 stayed invisible
for two months because nothing watched the *outcome* of the writes — only that the
Lambdas reported no errors. There is no acceptable background rate here.

### Investigation

1. Find the failures and their reason:
   ```
   CloudWatch Logs Insights, log group /aws/lambda/media-summarizer-api-<env>
   (and the worker groups):

   fields @timestamp, user_id, media_item_id, media_key, job_id, error_type, message
   | filter event = "durable_media.write_failed"
   | sort @timestamp desc
   | limit 50
   ```

2. Read `error_type`:
   - `RuntimeError` mentioning `USER_MEDIA_TABLE` — the environment variable is not
     injected. Check that the Lambda's configuration carries it (Terraform sets it
     from `runtime_env.tf`); a redeploy from a stale plan is the usual cause.
   - `ClientError` / `AccessDeniedException` — the Lambda role lost DynamoDB access
     to the table. The policy is scoped by suffix (`table/*-<env>`), so this points
     at a table created outside the module or in the wrong environment.
   - `ClientError` / `ProvisionedThroughputExceededException` or throttling — the
     table is PAY_PER_REQUEST, so this means a partition hot spot: one `user_id`
     receiving a burst. Check whether a backfill or a load test is running.
   - `ValueError` on identity — a save reached the service with an empty `user_id`
     or `media_key`. That is a caller bug; find the endpoint from the log context.

3. Quantify the gap. During Phase 1 the API still reads `processing_jobs`, so a
   failed durable write is invisible to users but leaves a job with no library row:
   ```bash
   aws dynamodb get-item \
     --table-name user_media-<env> \
     --key '{"user_id":{"S":"<user_id>"},"media_item_id":{"S":"<media_item_id>"}}' \
     --region eu-west-3
   ```

### First response

- The user's save itself did **not** fail during Phase 1 (see
  `try_save_media_for_user` in `media_summarizer/core/services/durable_media_service.py`):
  the pipeline ran and the item is visible. Do not tell the user to re-save.
- Fix the cause, then reconcile the missing rows with the Phase 2 backfill
  (task-241) rather than by hand: it is idempotent and derives the same
  deterministic ids.
- If failures are continuous and noisy, set `DURABLE_MEDIA_ENABLED=0` (see
  [Rollback](#rollback)) to stop the write attempts while investigating. The table
  is not read yet, so this costs nothing but the drift the backfill will repair.

---

## Deletion Failed

**Alarm:** `media-summarizer-user-media-delete-failed-<env>`
**Severity:** Critical
**Threshold:** any occurrence of `user_media.delete_failed` in 5 minutes

### Why this is critical

The user asked for an item to leave their library and it did not. Unlike a failed
save (which Phase 1 hides behind `processing_jobs`), this is immediately visible:
the item is still there after the app said it was gone.

### Investigation

```
CloudWatch Logs Insights, log group /aws/lambda/media-summarizer-api-<env>:

fields @timestamp, user_id, media_item_id, error_type, message
| filter event = "user_media.delete_failed"
| sort @timestamp desc
| limit 50
```

`error_type` reads the same way as in [Write Failed](#write-failed): a missing
`USER_MEDIA_TABLE`, an `AccessDeniedException` on the table, or a throttle.

A `media.delete.not_found` event instead means the client sent an id that resolves
to no row of that user. During Phase 1 the API still hands out **job** ids, so
`media_deletion_service._resolve_row` bridges job id → durable id; a 404 on an item
the user can see means that bridge failed (the job row is gone *and* the durable
row was never created). Reconcile with the [backfill](#backfill).

### First response

- Retrying the deletion is always safe: `mark_deleted` is conditional and
  idempotent, so a second call cannot extend the purge date.
- Nothing was destroyed by the failure. A failed soft delete leaves the item
  intact, which is the safe direction.

---

## Unexplained TTL Deletions

**Alarm:** `media-summarizer-user-media-unexplained-purge-<env>`
**Severity:** Critical
**Threshold:** any occurrence of `user_media.unexplained_purge` in 5 minutes

### Why this is critical

`purge_at` is the only TTL attribute on this table and only the user-initiated
deletion use case may ever write it (task-218 invariant I2). This alarm fires when
the TTL swept a row that carries **no `deleted_at`** — i.e. a row nobody ever
deleted was given an expiry date. That is the exact regression that reintroduces
the original data loss, one row at a time and silently.

The lifecycle worker deliberately does **not** cascade those rows: the library row
is already gone, but its artifacts, S3 objects and search records are still there,
so the content is recoverable while you investigate.

### Investigation

1. The event carries everything the OldImage had:
   ```
   CloudWatch Logs Insights, log group
   /aws/lambda/media-summarizer-worker-media-lifecycle-<env>:

   fields @timestamp, user_id, media_item_id, purge_at, last_job_id
   | filter event = "user_media.unexplained_purge"
   | sort @timestamp desc
   ```

2. Find the illegitimate writer. CI runs this on every PR, so a hit means the
   guard was bypassed or the write comes from outside the repo:
   ```bash
   python scripts/check_purge_at_writers.py
   ```

3. Check CloudTrail for `UpdateTimeToLive` on the table (someone may have pointed
   the TTL at a different attribute) and for `UpdateItem` calls by an identity
   other than the API and the lifecycle worker.

### First response

1. Disable the TTL immediately to stop the bleeding. Deletions keep working — the
   only consequence is that purges stop happening, which is the safe direction:
   ```bash
   aws dynamodb update-time-to-live \
     --table-name user_media-<env> \
     --time-to-live-specification 'Enabled=false,AttributeName=purge_at' \
     --region eu-west-3
   ```
2. Recover the deleted rows from PITR into a side table and reconcile — see
   [Restoring the Library](#restore). The window is 35 days from the deletion.
3. Remove the illegitimate writer, then re-enable the TTL through Terraform.

---

## Purge Cascade Failed

**Alarm:** `media-summarizer-user-media-purge-cascade-failed-<env>`
**Severity:** Critical
**Threshold:** any occurrence of `user_media.purge_cascade_failed` in 5 minutes

### Why this is critical

The library row is gone and part of what it owned is not. Because
`media_item_id` is `sha256(user_id|media_key)`, a user who re-saves the same URL
lands on the *same* id and would inherit the surviving artifacts — a stale summary
presented as fresh content.

### Investigation

```
log group /aws/lambda/media-summarizer-worker-media-lifecycle-<env>:

fields @timestamp, user_id, media_item_id, last_job_id, error_type, message
| filter event = "user_media.purge_cascade_failed"
| sort @timestamp desc
```

The stream mapping retries 5 times and bisects the batch, so a transient S3 or
DynamoDB error resolves itself; a repeated failure on the same `media_item_id` is a
code or permissions problem. Every step of
`core/services/media_purge_service.py` is a delete, so replaying is always safe.

### First response

1. Re-run the cascade for the affected item, from a shell with the environment of
   `<env>`:
   ```python
   from media_summarizer.workers.cleanup import media_lifecycle
   import asyncio
   asyncio.run(media_lifecycle.purge_media_item(
       user_id="<user_id>", media_item_id="<media_item_id>", last_job_id="<job_id>"))
   ```
2. Confirm with the next reconciliation run that
   `artifact_rows_orphaned_recent` returns to 0.

---

## TTL Sweeps Without a Cascade

**Alarm:** `media-summarizer-user-media-ttl-without-cascade-<env>`
**Severity:** Critical
**Threshold:** DynamoDB's own `TimeToLiveDeletedItemCount` exceeds
(`UserMediaPurgeCompleted` + `UserMediaUnexplainedPurge`) two days in a row

### Why this is critical

This is the alarm for the failure modes that produce **no log line at all**,
because the code never runs: the event source mapping disabled, the stream
permissions revoked, records ageing out of the stream's 24h retention. Rows are
being destroyed and nothing is cleaning up after them — the §1.5 blind spot of the
original incident, transposed to the library.

Two consecutive days are required because a sweep at 23:59 whose cascade lands at
00:01 straddles the daily boundary.

### Investigation

```bash
# Is the consumer even attached and enabled?
aws lambda list-event-source-mappings \
  --function-name media-summarizer-worker-media-lifecycle-<env> \
  --region eu-west-3 \
  --query 'EventSourceMappings[].[State,StateTransitionReason,LastProcessingResult]'
```

`State` must be `Enabled` and `LastProcessingResult` must not be an error. A
`PROBLEM: ...` in `StateTransitionReason` is usually the IAM policy
(`media-summarizer-media-lifecycle-stream-policy-<env>`) or a stream that was
disabled and re-created with a new ARN — re-apply Terraform in that case.

### First response

1. Re-enable or re-create the mapping (`terraform apply` is the supported path).
2. The rows already swept cannot be recovered from the stream once past its 24h
   retention: list the orphans with the reconciliation gauges and purge them with
   `purge_media_item` (see above) per affected `media_item_id`, recovering the ids
   from PITR if needed.

---

## Purge Overdue

**Alarm:** `media-summarizer-user-media-purge-overdue-<env>`
**Severity:** Warning
**Threshold:** `library_rows_overdue_purge > 0` (rows whose `purge_at` passed more
than 48h ago and that are still present)

### Why this matters

DynamoDB sweeps TTLs within ~48h. Past that, a surviving row means the TTL is not
active. **The most common cause is a restore**: a restored table does not carry the
TTL configuration over, so every scheduled purge silently stops. The second cause is
someone having disabled the TTL during an incident (see above) and not re-enabled it.

### First response

```bash
aws dynamodb describe-time-to-live --table-name user_media-<env> --region eu-west-3
```

If `TimeToLiveStatus` is not `ENABLED` on `purge_at`, re-enable it through
Terraform (`dynamodb_user_media.tf` owns it) or, if the table is a fresh restore,
with `update-time-to-live` as part of the [restore procedure](#restore).

---

## Orphan Artifacts

**Alarm:** `media-summarizer-user-media-recent-orphan-artifacts-<env>`
**Severity:** Warning
**Threshold:** `artifact_rows_orphaned_recent > 0` — an artifact created in the last
48h whose `media_item_id` has no `user_media` row

### Why the window

Only *recent* orphans are alarmed. Dev carries a permanent standing drift from the
task-241 backfill (artifact rows whose owner could not be established were
quarantined, never guessed), so an alarm on the total would be permanently
breaching and therefore ignored. `UserMediaOrphanArtifactsTotal` is published as a
gauge for that historical drift.

A *recent* orphan means one of two live bugs:

- a save is creating artifacts without a library row (a durable write failure that
  was swallowed — cross-check [Write Failed](#write-failed)), or
- a purge deleted the library row and left the artifacts (cross-check
  [Purge Cascade Failed](#purge-cascade-failed)).

### Investigation

```
log group /aws/lambda/media-summarizer-worker-media-lifecycle-<env>:

fields @timestamp, library_rows, artifact_rows, artifact_rows_orphaned,
       artifact_rows_orphaned_recent, library_rows_overdue_purge,
       library_max_rows_per_user, pointers_checked, pointers_dangling
| filter event = "user_media.reconciliation_completed"
| sort @timestamp desc
| limit 14
```

`pointers_dangling` is informational: `last_job_id` is *allowed* to dangle
(invariant I3) because jobs expire and library rows do not. Never "repair" it by
recreating jobs.

---

## Reconciliation Stopped

**Alarm:** `media-summarizer-user-media-reconciliation-stopped-<env>`
**Severity:** Warning
**Threshold:** fewer than one `user_media.reconciliation_completed` in 48h
(`treat_missing_data = breaching`)

### Why this exists

Every gauge-based alarm above depends on the daily reconciliation running. A silent
watchdog looks exactly like a healthy system, which is precisely how the task-218
incident stayed invisible for two months. "No data" is therefore the failure being
detected, not the absence of one.

### First response

```bash
# Run it now, out of band:
aws lambda invoke \
  --function-name media-summarizer-worker-media-lifecycle-<env> \
  --payload '{"source":"manual"}' --cli-binary-format raw-in-base64-out \
  --region eu-west-3 /dev/stdout

# And check the schedule is still enabled:
aws events describe-rule \
  --name media-summarizer-media-lifecycle-reconciliation-<env> --region eu-west-3
```

A `user_media.reconciliation_failed` event in the log group means the job ran and
threw — read `error_type`; a scan-level `AccessDeniedException` points at the
worker policy, everything else is usually a table name missing from the Lambda
environment.

---

## Restoring the Library

The three restore windows, what each covers and where they come from are in
[`docs/DATA_RETENTION.md`](../../../docs/DATA_RETENTION.md#5-backup-and-restore-windows):
PITR 35 days, AWS Backup snapshots 90 days, S3 exports 365 days.

**Never restore over the live table.** Every path below creates a new table.

### 1. PITR (35 days, second-level precision)

```bash
aws dynamodb restore-table-to-point-in-time \
  --source-table-name user_media-<env> \
  --target-table-name user_media-<env>-restore \
  --restore-date-time <ISO8601 just before the damage> \
  --region eu-west-3
```

### 2. AWS Backup snapshot (90 days, weekly granularity)

```bash
aws backup list-recovery-points-by-backup-vault \
  --backup-vault-name media-summarizer-library-<env> --region eu-west-3 \
  --query 'RecoveryPoints[].[RecoveryPointArn,CreationDate,ResourceArn]'

aws backup start-restore-job \
  --recovery-point-arn <arn> \
  --iam-role-arn arn:aws:iam::<account>:role/media-summarizer-backup-library-<env> \
  --metadata '{"targetTableName":"user_media-<env>-restore"}' \
  --region eu-west-3
```

### 3. Monthly S3 export (365 days, cold)

```bash
aws s3 ls s3://media-summarizer-archives-<account>-<env>/dynamodb-exports/user_media-<env>/
```

DYNAMODB_JSON under GLACIER_IR (instant retrieval). Query it with Athena, or
re-import it with `aws dynamodb import-table`. This tier is the audit copy and the
last resort, not the first thing to reach for.

### Mandatory steps after ANY restore

1. **Re-enable the TTL.** A restored table does *not* carry it over, so every
   scheduled purge stops silently until you do this:
   ```bash
   aws dynamodb update-time-to-live \
     --table-name user_media-<env>-restore \
     --time-to-live-specification 'Enabled=true,AttributeName=purge_at' \
     --region eu-west-3
   ```
   ([Purge Overdue](#purge-overdue) is the alarm that catches forgetting it.)
2. **Compare counts** before trusting anything:
   ```bash
   aws dynamodb describe-table --table-name user_media-<env>-restore \
     --region eu-west-3 --query 'Table.ItemCount'
   ```
   `ItemCount` is updated every ~6h, so use a `select COUNT` scan for an exact
   figure on a small table.
3. **Reconcile rather than swap, if only some rows were lost.** The restored table
   is a *source* for the [backfill](#backfill), which is idempotent and writes only
   missing attributes; that keeps the rows created since the damage. Swapping
   `USER_MEDIA_TABLE` to the restored table is the last-resort path for a total
   loss, and it also means re-pointing PITR, the backup selection, the stream
   consumer and the export schedules, all of which name the table explicitly in
   Terraform.
4. **Streams and PITR are off on a restored table.** Both must be re-enabled before
   the restored table can serve as the live one.

---

## Backfill

`scripts/backfill_user_media.py` reconstructs library rows that were lost before the
durable table existed, from the five surviving sources in §5.3 of the benchmark. It is
idempotent and re-runnable: run it whenever the write-failed alarm has left a gap, or
after restoring anything.

### Running it

```bash
# 1. Always dry-run first. Writes nothing, prints one line per row.
scripts/backfill_user_media.py --suffix=-dev

# 2. Read the two reports it prints the path of, in particular the quarantine one.
# 3. Then apply.
scripts/backfill_user_media.py --suffix=-dev --apply

# 4. Re-run to prove convergence: everything must come back as NOOP.
scripts/backfill_user_media.py --suffix=-dev --apply
```

`--suffix` only accepts `-dev` and `-staging`; prod is deliberately unreachable from
the script. `--user-id <uuid>` restricts a run to one account, `--no-algolia` /
`--no-s3` skip a source that is unavailable.

### What it writes, and what it must never write

- Writes: `user_media<env>` (conditional `PutItem` for new rows, attribute-level
  `UpdateItem` that only fills *missing* attributes on rows that already exist) and
  `media_idempotence<env>` (unsticking reservations, see below).
- Reads only: `processing_jobs`, `media_artifacts`, `user_media_submissions`,
  `user_folders`, `users`, Algolia and S3. The script contains no write call against
  any of them, so artifact rows, search records and S3 objects keep their existing
  `media_item_id` and every deep link stays valid.
- Reconstructed rows keep their **legacy** `media_item_id` (a job uuid) verbatim,
  because that is the id `media_artifacts` and the Algolia `objectID`s already use.
  Only new saves get the deterministic `mi_…` id. Both formats coexist; the id is
  opaque and nothing may parse it.

### Reading the output

Per-row actions: `CREATE` (new row), `UPDATE` (existing row, missing attributes
filled — `filled=` lists them), `NOOP` (nothing to do). Ledger actions: `KEEP`
(reservation is legitimate, its job is alive), `PROCESSED` (job gone but the content
and a library row survive), `RESET` (reservation released so the media can be
re-ingested), `SKIP_RACE` (the row changed under the backfill and was left alone).

Both reports land in `--report-dir` (default `tmp/backfill-user-media`, gitignored):
a JSON file with per-row provenance, and a markdown quarantine file for owner review.

### Quarantine

Anything whose owner cannot be established from a job, a submission or an Algolia
record is **quarantined, never guessed** — ownership is never inferred from an
environment happening to have a single real user, and never from an artifact or an S3
object, which carry no `user_id`. Quarantined entries are reported and left alone.
Deciding them is a human job: identify the account, then re-run with `--user-id`.

### Ledger repair

Reservations frozen at `reserved` whose job has been deleted are what makes
re-submitting a URL return a `media_item_id` that 404s. The backfill advances such a
row to `processed` only when the content survives **and** a library row now carries
that id; otherwise it releases the reservation (a conditional delete, exactly like
`media_idempotence.release_reservation`) so the media can be re-ingested. Both writes
are conditioned on `status = reserved AND job_id = <the value that was read>`, so a
submission that re-reserved the key in the meantime is never disturbed. When
`--apply` is used, the pre-image of the ledger is dumped to the report dir *before*
any deletion.

### Undoing a backfill

```bash
scripts/backfill_user_media.py --suffix=-dev --rollback           # dry run
scripts/backfill_user_media.py --suffix=-dev --rollback --apply
```

This deletes exactly the rows the backfill created, identified by `backfilled_from`,
which a live save never writes. Rows that already existed and were only enriched carry
`backfill_enriched_from` instead: the rollback lists them and refuses to delete them,
because a real user save created them. To undo an enrichment, strip the attributes
listed under `filled` in that run's JSON report.

The ledger repair is **not** rolled back: released reservations are gone (re-ingesting
is the intended path) and repaired ones are legitimately `processed`.

---

## Rollback

Phase 1 writes `user_media` but does not read it, so the rollback is a flag flip and
nothing has to be undone. Orphan rows are inert.

Immediate, no redeploy (the flag is read at call time):

```bash
aws lambda update-function-configuration \
  --function-name media-summarizer-api-<env> \
  --environment "Variables={...,DURABLE_MEDIA_ENABLED=0}" \
  --region eu-west-3
```

Beware: `update-function-configuration` replaces the whole environment map. Fetch it
first with `aws lambda get-function-configuration` and edit the single key, or the
function loses every other variable.

Durable across applies (preferred as soon as the incident is contained), in
`infrastructure/terraform/envs/<env>`:

```hcl
module "platform" {
  # ...
  durable_media_enabled = false
}
```

Do **not** delete the table to roll back: it carries `prevent_destroy` and
`deletion_protection_enabled`, and it is the only copy of the library rows created
since the flag went on.
