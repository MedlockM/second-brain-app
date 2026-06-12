---
id: task-197
title: Harden DLQ setup (add missing DLQ, extend retention, add replay tooling)
status: To Do
assignee: []
created_date: '2026-06-12 15:30'
labels:
  - reliability
  - infrastructure
  - observability
dependencies: []
priority: high
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
## Context

Audit of the SQS+DLQ setup found that the basic plumbing is correct (14/15 queues have a `redrive_policy` with `maxReceiveCount = 3`, DLQs are provisioned and currently empty), but **three issues prevent the DLQs from doing their actual job**: catching poison messages, retaining them long enough to debug, and letting an operator replay them after a fix.

Note: DLQ alarms (`enable_alarms`) are intentionally off in dev to save ~$4.20/month. The reactivation for staging/prod is already tracked in the V1 launch plan (Phase 8 — Monitoring & observability, [docs/V1_LAUNCH_PLAN.md:432](docs/V1_LAUNCH_PLAN.md)) and is **out of scope here**.

## The 3 issues

### Issue 1 — `podcastindex-resolution-queue` has no DLQ

`aws_sqs_queue.rss_resolution` ([sqs.tf:8-18](infrastructure/terraform/sqs.tf)) is the only main queue without a `redrive_policy`. A message that fails 3 times here is retried forever (until the 14-day retention expires) with **no DLQ to catch it for debugging**. All other 14 queues have their DLQ properly wired — this one was missed.

### Issue 2 — DLQ retention = 4 days, source retention = 14 days

The DLQ Terraform blocks (e.g. `aws_sqs_queue.flashcards_dlq` at [sqs.tf:366](infrastructure/terraform/sqs.tf)) **do not set `message_retention_seconds`** explicitly, so they use the AWS default of **4 days**. Confirmed via AWS API: every DLQ has `MessageRetentionPeriod = 345600` (4 days), while source queues are at `1209600` (14 days).

This is the inverse of what's needed. A DLQ exists precisely to retain messages for human investigation; if you're away for a week (vacation, weekend + holiday), the message has already vanished by the time you look. The standard recommendation is **DLQ.retention ≥ source.retention**, often longer (e.g. 14 days source → 14 days DLQ minimum, ideally the SQS max of 14 days everywhere or longer-term archival to S3 for prod-grade retention).

### Issue 3 — No tooling to replay messages from a DLQ

After a poison message is fixed (deploy of a bugfix), the messages sitting in the DLQ need to be replayed back onto the source queue. Today there is **no script, no admin endpoint, no Make target** for this. Options today:
- AWS console → "Start DLQ redrive" button (manual, fine for one or two messages, painful for batches)
- Write an ad-hoc bash script per incident

The runbook [infrastructure/observability/runbooks/pipeline-alerts.md](infrastructure/observability/runbooks/pipeline-alerts.md) documents *how to investigate* a DLQ alarm but not *how to recover* afterwards. Add a thin replay tool (script or `make replay-dlq QUEUE=<name>`) using `aws sqs start-message-move-task` (the modern API, which handles back-pressure and reports progress) or a manual loop fallback.

## Proposed fix (per issue)

### Fix 1 — Add DLQ to `podcastindex-resolution-queue`

In `sqs.tf`, add `aws_sqs_queue.rss_resolution_dlq` (mirror the pattern of any sibling DLQ) and add a `redrive_policy` block on `aws_sqs_queue.rss_resolution` with `maxReceiveCount = 3`. Add the DLQ ARN to `iam_lambda.tf` policies if needed for replay/visibility tooling.

### Fix 2 — Set explicit DLQ retention

On every `*_dlq` resource in `sqs.tf`, add:
```hcl
message_retention_seconds = 1209600  # 14 days, matches source queue
```

This is the maximum SQS allows. If longer-term retention is needed (months), document the decision to either:
- Move expired DLQ messages to S3 archive (separate task, out of scope here), or
- Accept 14 days as the operational debug window and document the SLA.

### Fix 3 — Add replay tooling

Add `scripts/replay_dlq.sh` (or a Makefile target) that:
- Takes a queue name (e.g. `flashcards`)
- Resolves source + DLQ URLs
- Calls `aws sqs start-message-move-task --source-arn <DLQ> --destination-arn <source>` (or falls back to a manual receive/send/delete loop if `start-message-move-task` is unavailable)
- Reports progress and message counts
- Refuses to run if `ApproximateNumberOfMessages` on the DLQ is 0 (nothing to replay)
- Documents the standard recovery sequence in the runbook

## Out of scope

- Long-term DLQ archival to S3 (separate task once volume justifies it)
- Per-queue `maxReceiveCount` tuning (handled by task-196 timeouts/retries audit)
- DLQ-specific dashboards in CloudWatch (the existing `pipeline_dashboard.tf` covers most of it)
- Mobile-side error reporting when a job ends up in DLQ (separate task on user-facing failure UX)

## References

- task-196 (timeouts/retries audit — interacts here: `maxReceiveCount` is the same lever as in-app `max_retries`)
- task-143 (the silent-queue regression that motivated this audit — DLQ would not have helped there because the queue was orphaned, but a depth alarm on the source queue would have)
- [pipeline_alerts.tf](infrastructure/terraform/pipeline_alerts.tf)
- [pipeline-alerts.md runbook](infrastructure/observability/runbooks/pipeline-alerts.md)
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 `aws_sqs_queue.rss_resolution_dlq` provisioned and `aws_sqs_queue.rss_resolution` updated with `redrive_policy { maxReceiveCount = 3 }`. Verified end-to-end: a forced failure on a podcastindex resolution message lands in the new DLQ after 3 attempts.
- [ ] #2 Every `*_dlq` resource in `sqs.tf` has `message_retention_seconds = 1209600` set explicitly. AWS API confirms `MessageRetentionPeriod = 1209600` on all 15 DLQs.
- [ ] #3 `scripts/replay_dlq.sh` (or equivalent) exists, scoped to a single queue, uses `start-message-move-task` when available, reports progress, refuses to run on an empty DLQ, and is referenced from the runbook.
- [ ] #4 Runbook section "How to recover a DLQ after a fix" added, describing: investigate → identify root cause → ship fix → run replay tool → confirm zero DLQ depth.
- [ ] #5 `terraform apply` clean; no Lambda churn (image_uri ignore_changes still in effect).
<!-- AC:END -->
