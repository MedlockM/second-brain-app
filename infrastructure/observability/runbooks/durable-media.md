# Durable Media Library Runbook

Operational runbook for the `user_media` durable library table (task-240, Phase 1 of
the task-218 benchmark). Alarms are defined in
`infrastructure/terraform/modules/platform/durable_media_alerts.tf`.

Replace `<env>` with `dev`, `staging` or `prod` in every command below.

---

## Table of Contents

- [Write Failed](#write-failed)
- [Unexplained TTL Deletions](#unexplained-ttl)
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

## Unexplained TTL Deletions

**Alarm:** `media-summarizer-user-media-ttl-deletions-<env>`
**Severity:** Critical
**Threshold:** `TimeToLiveDeletedItemCount > 0` over 24 hours on `user_media-<env>`

### Why this is critical

`purge_at` is the only TTL attribute on this table and only a user-initiated
deletion may ever write it (task-218 invariant I2). No user-deletion use case ships
in Phase 1, so the correct value of this metric today is exactly **zero**. A
non-zero value means something started expiring library rows — the exact regression
that reintroduces the original data loss, one row at a time and silently.

### Investigation

1. Confirm which rows went away and when:
   ```
   CloudWatch Logs Insights is useless here (TTL deletes leave no application log).
   Use the stream instead: the table has NEW_AND_OLD_IMAGES enabled, and TTL
   deletions arrive with userIdentity.principalId = "dynamodb.amazonaws.com".
   ```

2. Find who is writing `purge_at`. It must be nobody:
   ```bash
   grep -rn "purge_at" media_summarizer/
   ```
   The only legitimate hits are `core/models/user_media.py` (the field), and
   `utils/user_media.py` (which *rejects* it in `update_attributes`). Any other
   writer is the bug.

3. Check CloudTrail for `UpdateTimeToLive` on the table: someone may have pointed
   the TTL at a different attribute.

### First response

1. Disable the TTL immediately to stop the bleeding — it protects nothing today:
   ```bash
   aws dynamodb update-time-to-live \
     --table-name user_media-<env> \
     --time-to-live-specification 'Enabled=false,AttributeName=purge_at' \
     --region eu-west-3
   ```
2. Recover the deleted rows from PITR into a side table and reconcile. PITR is on
   from table creation precisely for this:
   ```bash
   aws dynamodb restore-table-to-point-in-time \
     --source-table-name user_media-<env> \
     --target-table-name user_media-<env>-restore \
     --restore-date-time <ISO8601 before the deletions> \
     --region eu-west-3
   ```
   Never restore over the live table.
3. Remove the illegitimate writer, then re-enable the TTL through Terraform.

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
