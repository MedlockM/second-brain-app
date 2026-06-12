---
id: task-194
title: Remove legacy summarization worker and queue after short/detailed rollout
status: Done
assignee: []
created_date: '2026-06-12 14:30'
labels:
  - cleanup
  - backend
  - infrastructure
dependencies:
  - task-193
priority: low
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
## Context

Once task-193 ships and `summary_short` / `summary_detailed` workers are running in prod for long enough to be trusted, the legacy single-summary path becomes dead weight: the worker `summarization_worker.py`, the queue `summarization-queue`, the bucket `summaries`, and the `MediaArtifactType.SUMMARY` enum value all exist solely to serve `summary` artifacts that no client should request anymore.

This is a follow-up cleanup, scheduled separately so a regression in task-193 doesn't take down the only summary path in prod.

## Scope

1. **Worker code** — delete `media_summarizer/workers/summarization/` (the package, including `summarization_worker.py` and `__init__.py`).
2. **Lambda handler** — remove `summarization_handler` from `media_summarizer/workers/lambda_handlers.py`.
3. **Terraform** — remove the `summarization` entry from `local.workers` in `lambda_workers.tf`, and the `summarization` + `summarization_dlq` resources from `sqs.tf`. Remove the corresponding queue ARN from `iam_lambda.tf` policies. Update the `queue_urls` output in `sqs.tf`.
4. **Enum + contract** — drop `MediaArtifactType.SUMMARY` and `ArtifactType.SUMMARY` (legacy values). Audit any `if artifact_type == MediaArtifactType.SUMMARY` branches and decide per-call site whether to remove or remap to `SUMMARY_SHORT` (the most likely fallback for legacy callers).
5. **Bucket** — keep `aws_s3_bucket.summaries` for now (still holds historical artifacts). Add a deprecation comment + a follow-up task to backfill or expire (out of scope here).
6. **`ARTIFACT_TYPES_ALLOWED`** — remove `summary` from the default list in `core/config.py`.
7. **`get_artifact_bucket` / `get_artifact_queue`** — remove the `MediaArtifactType.SUMMARY` mappings in `core/services/artifact_service.py`.
8. **Apply** — `terraform apply` then a CI deploy. Verify nothing in the system tries to send to `summarization-queue` afterwards (CloudWatch metric: `NumberOfMessagesSent` should stay at 0 for 24 h).
9. **CI guard** — add a grep guard in `pr.yml` (similar to the `episode-completion-events` one from task-143) that fails the build if `summarization-queue` or `SUMMARIZATION_QUEUE` resurfaces in `media_summarizer/` or `infrastructure/terraform/`.

## Pre-conditions before starting

- task-193 deployed and running in prod for at least 1 week without incident
- No active `summary` artifact requests in the last 7 days (verify via DynamoDB scan or CloudWatch on `summarization-queue.NumberOfMessagesSent`)
- Mobile clients all requesting `summary_short` and/or `summary_detailed`, never `summary`

## Out of scope

- Migrating historical `summary` artifacts to `summary_short` / `summary_detailed` (separate decision: backfill, expire, or leave readable). Track in a follow-up task if needed.
- Removing or renaming the `summaries` S3 bucket (separate task, requires a retention policy decision).
- Mobile-side cleanup of any code paths still aware of the legacy `summary` type (track if mobile audit reveals any).

## References

- task-193 (the activation that supersedes this worker)
- task-143 / `pr.yml` for the CI guard pattern (regression prevention)
- `media_summarizer/workers/summarization/summarization_worker.py` (the file to delete)
- `media_summarizer/core/models/media_artifact.py:24` (the `SUMMARY = "summary"  # Legacy` line to remove)
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 task-193 has been deployed in prod for ≥1 week with no incident, and `summarization-queue` has had `NumberOfMessagesSent=0` for the last 7 days (evidence attached)
- [ ] #2 `media_summarizer/workers/summarization/` package deleted
- [ ] #3 `summarization_handler` removed from `lambda_handlers.py`
- [ ] #4 `summarization` worker entry removed from `local.workers` in `lambda_workers.tf`; `summarization` + `summarization_dlq` resources and the matching ARN in `iam_lambda.tf` removed; `queue_urls` output cleaned
- [ ] #5 `MediaArtifactType.SUMMARY` and `ArtifactType.SUMMARY` enum values removed; all references audited and either removed or remapped
- [ ] #6 `summary` removed from `ARTIFACT_TYPES_ALLOWED` default
- [ ] #7 `get_artifact_bucket` / `get_artifact_queue` mappings for `MediaArtifactType.SUMMARY` removed
- [ ] #8 CI guard added in `pr.yml` failing on `summarization-queue` or `SUMMARIZATION_QUEUE` reappearing in source
- [ ] #9 `terraform apply` clean and Lambda redeploy successful
- [ ] #10 No producer code path still sends to the deleted queue (verified via grep + CloudWatch idle for another 24 h post-apply)
- [ ] #11 The `summaries` S3 bucket retention decision tracked as a separate follow-up task
<!-- AC:END -->
