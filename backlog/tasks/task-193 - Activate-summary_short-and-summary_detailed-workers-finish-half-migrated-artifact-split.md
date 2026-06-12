---
id: task-193
title: Activate summary_short and summary_detailed workers (finish half-migrated artifact split)
status: To Do
assignee: []
created_date: '2026-06-12 14:30'
labels:
  - feature
  - backend
  - infrastructure
dependencies: []
priority: medium
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
## Context

The split of summary into two artifact kinds (`summary_short` for digest/newsletter, `summary_detailed` for learning) is **already wired through 90 % of the codebase** but never activated end-to-end. Today the only summary worker that actually runs is the legacy `summarization_worker.py` which produces a single `summary` artifact — meanwhile the digest service (`digest_service.py`) is asking for `summary_short` artifacts that no producer creates, and the API contract (`ArtifactType`) exposes `summary_short` / `summary_detailed` to the mobile app.

## What's already in place

- Enum `MediaArtifactType.SUMMARY_SHORT` / `.SUMMARY_DETAILED` ([core/models/media_artifact.py:25-26](media_summarizer/core/models/media_artifact.py))
- API contract `ArtifactType.SUMMARY_SHORT` / `.SUMMARY_DETAILED` ([api/models/media_contracts.py:94-100](media_summarizer/api/models/media_contracts.py))
- `get_artifact_bucket()` and `get_artifact_queue()` map both types to dedicated buckets/queues ([core/services/artifact_service.py:200-221](media_summarizer/core/services/artifact_service.py))
- S3 buckets `summary_short` + `summary_detailed` provisioned in Terraform (referenced in [iam_lambda.tf](infrastructure/terraform/iam_lambda.tf))
- Pricing config differentiates the two models ([core/services/pricing_config_service.py:159-160](media_summarizer/core/services/pricing_config_service.py))
- `ARTIFACT_TYPES_ALLOWED` config lists both ([core/config.py:59](media_summarizer/core/config.py))
- **The worker code itself is written and unit-coherent** in `media_summarizer/workers/summary/worker.py` (459 lines): per-type prompts, distinct LLM models per type, Pydantic schema validators (`SummaryShortContent`, `SummaryDetailedContent`), routes from `body.artifact_type` → model + prompt + validator. It just has no Lambda handler and the queues it expects (`summary-short-queue`, `summary-detailed-queue`) don't exist.

## What's missing

1. **Provision two SQS queues + DLQs** in `infrastructure/terraform/sqs.tf`: `summary-short-queue` and `summary-detailed-queue` (mirror the flashcards/notes/quiz pattern: `visibility_timeout_seconds = 1800`, `maxReceiveCount = 3`).
2. **Provision two Lambda functions + event source mappings** in `infrastructure/terraform/lambda_workers.tf` by adding two entries to `local.workers` (model after `flashcards`/`notes`/`quiz`: `memory_size = 512`, `timeout = 300`).
3. **Add two Lambda handlers** in `media_summarizer/workers/lambda_handlers.py` pointing at `media_summarizer.workers.summary.worker` — one for short, one for detailed. Either two handlers using the same `process_message` (queue identity disambiguates the artifact type via the message body), or split per main entry point.
4. **Add IAM permissions** in `infrastructure/terraform/iam_lambda.tf` for the new queues' ARNs (lambda_worker policy: receive/delete/send).
5. **Verify end-to-end** by submitting a media item, requesting both artifact kinds, asserting both reach `status=ready` with the expected pydantic-validated schemas, written to the right buckets.
6. **Mobile parity check** — confirm whether the UI already exposes both kinds (the contract enum suggests yes) or whether a follow-up mobile task is needed to render them.

## Notes

- The worker code in `summary/worker.py` is good: keep it. Don't rewrite it from scratch.
- Existing `summary` artifacts in DynamoDB stay readable (the legacy enum value remains in `MediaArtifactType` for backward compat). No backfill required for V1; old items just won't have short/detailed unless re-requested.
- Once this task ships and runs in prod long enough to confirm correctness, task-194 removes the legacy `summarization_worker.py` and its queue.

## Out of scope

- Removing legacy `summarization_worker.py` / `summarization-queue` → task-194 (depends on this).
- Changing the schemas of `SummaryShortContent` / `SummaryDetailedContent` (already validated by owner via task-72 benchmark).
- Mobile UI rework if it doesn't yet render both kinds — track separately.

## References

- task-72 (benchmark that picked the two distinct LLM models)
- task-123 (canonical artifact_id contract — both summary workers use it)
- `media_summarizer/workers/summary/worker.py` (the code to wire up)
- `media_summarizer/workers/summarization/summarization_worker.py` (the legacy to keep running until this is live)
- `media_summarizer/core/services/digest_service.py` (consumer that today silently misses summary_short)
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 Two new SQS queues `summary-short-queue` and `summary-detailed-queue` (+ DLQs) provisioned in `sqs.tf`, mirroring the flashcards pattern
- [ ] #2 Two new Lambda functions provisioned in `lambda_workers.tf` (`memory_size=512`, `timeout=300`), each with its event source mapping and dynamic discovery picks them up automatically in `deploy-lambda.yml`
- [ ] #3 IAM policies updated in `iam_lambda.tf` to grant access to the two new queues
- [ ] #4 Two new Lambda handlers in `lambda_handlers.py` invoking `media_summarizer.workers.summary.worker.process_message`
- [ ] #5 `terraform apply` clean (only the new queues/lambdas, no Lambda image_uri churn thanks to ignore_changes)
- [ ] #6 Lambda images redeployed via `deploy-lambda.yml` so the new functions get the worker code
- [ ] #7 End-to-end: submitting a podcast and requesting `summary_short` + `summary_detailed` produces two artifacts with the expected Pydantic-validated content shape, written to `summary_short` / `summary_detailed` S3 buckets
- [ ] #8 `digest_service.py` flow that depends on `summary_short` produces a non-empty digest for at least one fixture media item
- [ ] #9 Legacy `summarization-queue` and `summarization_worker.py` left untouched (removed in task-194 once this is stable)
<!-- AC:END -->
