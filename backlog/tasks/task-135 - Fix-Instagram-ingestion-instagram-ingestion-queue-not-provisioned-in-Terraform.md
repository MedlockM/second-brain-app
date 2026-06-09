---
id: task-135
title: Fix Instagram ingestion — instagram-ingestion-queue not provisioned in Terraform
status: To Do
assignee: []
created_date: '2026-06-09 16:50'
labels:
  - bug
  - infrastructure
  - ingestion
dependencies: []
priority: high
dispatchable: true
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
## Context

Discovered during E2E re-run after task-133 was merged. task-133 mentioned changing the Instagram fixture URL but the actual blocker is infra : the Instagram-specific SQS queue does not exist in AWS.

## Symptom

`pytest -m e2e tests/e2e/test_phase4_other_sources.py::test_instagram_ingestion` fails immediately at the `POST /api/media/ingest-url` step (HTTP 500).

CloudWatch `/aws/lambda/media-summarizer-api`:

```
QueueDoesNotExist: An error occurred (AWS.SimpleQueueService.NonExistentQueue)
when calling the GetQueueUrl operation: The specified queue does not exist.
  at media.py:337 → sqs.send_message(queue_name=INSTAGRAM_INGESTION_QUEUE, ...)
```

`INSTAGRAM_INGESTION_QUEUE = "instagram-ingestion-queue"` (from env / `.env`). The queue is referenced by:

- `media_summarizer/api/endpoints/media.py:337` (API enqueues here when `source_platform == "instagram"`)
- Likely an `instagram_ingestion_worker.py` consumer that we'd expect to be wired to this queue

But `infrastructure/terraform/sqs.tf` does NOT declare this queue. There's also no `instagram_ingestion` entry in `lambda_workers.tf` (so even if the queue existed, no worker would process the messages).

## Root cause

Instagram support was probably added before a full infra audit. The API code expects the queue + worker, but Terraform was never updated to provision them. Sibling pattern to task-122 Bug 3 (`quiz` queue/worker missing) and the YouTube Apify migration which had to add things to Terraform.

## Fix

Two options:

**A. Provision the missing infra (preferred for V1 since Instagram is a declared V1 source).**
- Add `aws_sqs_queue.instagram_ingestion` + `aws_sqs_queue.instagram_ingestion_dlq` in `sqs.tf`.
- Add `instagram_ingestion` worker entry in `lambda_workers.tf` (memory 512, timeout 120, queue_arn = above, handler `media_summarizer.workers.lambda_handlers.instagram_ingestion_handler`).
- Add `instagram-ingestion-queue` ARN to the worker IAM `sqs:Receive*/Delete*` policy and the API IAM `sqs:SendMessage` policy in `iam_lambda.tf`.
- Verify `media_summarizer/workers/instagram_ingestion_worker.py` (and its handler in `lambda_handlers.py`) exists; if not, create them.
- `terraform apply` and redeploy.

**B. Remove Instagram from the dispatch path** if the worker doesn't exist and won't ship for V1. Update `_detect_platform` to fall back to a generic resolver, or fail fast at the API with a clear "not yet supported" 400.

The V1 launch plan §0 explicitly lists Instagram as supported. So option A.

## Reproduction

```bash
.venv/bin/pytest -m e2e tests/e2e/test_phase4_other_sources.py::test_instagram_ingestion -v
```

```bash
# Confirm queue does not exist:
aws sqs list-queues --region eu-west-3 | grep instagram
# (returns nothing)
```

## Out of scope

- Other source-specific bugs (TikTok episode_url, document Algolia key, podcast Decimal) — separate tasks 134, 136, 137

## References

- task-122 Bug 3 (sibling: quiz queue + worker missing)
- task-129 (sibling: YouTube migration required new infra)
- `media_summarizer/api/endpoints/media.py:337`
- `infrastructure/terraform/sqs.tf` (where the queue should be declared)
- `infrastructure/terraform/lambda_workers.tf` (where the worker should be declared)
- `infrastructure/terraform/iam_lambda.tf` (where the IAM grants should be added)
- `tests/e2e/test_phase4_other_sources.py::test_instagram_ingestion`
- CloudWatch `/aws/lambda/media-summarizer-api` 2026-06-09 ~14:42 UTC
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 `instagram_ingestion` SQS queue + DLQ provisioned in `sqs.tf`
- [ ] #2 `instagram_ingestion` Lambda worker declared in `lambda_workers.tf` with appropriate memory/timeout/handler
- [ ] #3 IAM policies updated in `iam_lambda.tf` (worker `sqs:Receive*/Delete*` + API `sqs:SendMessage` on the new queue ARN)
- [ ] #4 If `media_summarizer/workers/instagram_ingestion_worker.py` doesn't exist, it's created (model on `tiktok_ingestion_worker.py` post-task-134)
- [ ] #5 `terraform apply` clean, `aws sqs list-queues` shows `instagram-ingestion-queue`
- [ ] #6 Lambda image rebuilt + redeployed
- [ ] #7 `pytest -m e2e tests/e2e/test_phase4_other_sources.py::test_instagram_ingestion` passes (job reaches `completed`)
- [ ] #8 No regression on the 9 already-passing tests
<!-- AC:END -->
