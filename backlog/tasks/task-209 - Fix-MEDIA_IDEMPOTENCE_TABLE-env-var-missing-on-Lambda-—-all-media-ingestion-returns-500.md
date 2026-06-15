---
id: task-209
title: >-
  Fix MEDIA_IDEMPOTENCE_TABLE env var missing on Lambda — all media ingestion
  returns 500
status: Done
assignee: []
created_date: '2026-06-15 16:27'
labels:
  - backend
  - infrastructure
  - bug
  - critical
dependencies: []
priority: high
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
## Context

Since task-208 (commit `2821f86`) migrated `/api/media/ingest-url` to `IngestUrlUseCase` / `Orchestrator.submit`, **every media ingestion attempt returns HTTP 500** — YouTube, TikTok, Instagram, X, articles, shared text, shared audio. All sources are broken.

## Root cause

CloudWatch logs (`/aws/lambda/media-summarizer-api`) show:

```
ResourceNotFoundException: An error occurred when calling the GetItem operation: Requested resource not found
  at media_summarizer/core/media_ingestion/adapters/orchestrators.py:169
    existing = await episode_idempotence.already_processed(media_key=resolved.media_key)
  at media_summarizer/utils/media_idempotence.py:43
    resp = await table.get_item(Key={...})
```

Mismatch between code and infra:

- Code (`media_summarizer/utils/media_idempotence.py:21`):
  ```python
  MEDIA_IDEMPOTENCE_TABLE = os.environ.get("MEDIA_IDEMPOTENCE_TABLE", "media_idempotence")
  ```
- Real DynamoDB table (`infrastructure/terraform/dynamodb_core_tables.tf:131`): **`episode_idempotence`** (kept this name historically; renamed in code via task-49 but table never renamed in AWS).
- Lambda env vars on `media-summarizer-api` (verified via `aws lambda get-function-configuration`): `MEDIA_IDEMPOTENCE_TABLE` is **absent**. Only `ARTIFACT_IDEMPOTENCE_TABLE` and `TRANSLATION_IDEMPOTENCE_TABLE` are wired in `infrastructure/terraform/lambda_api.tf:75-76` and `lambda_workers.tf:140-141`.

Code falls back to default `"media_idempotence"` which doesn't exist in AWS → `ResourceNotFoundException` → 500.

The legacy `/api/media/ingest-url` path didn't go through `Orchestrator.submit`, which is why the bug only surfaced after task-208's migration. The shared-content endpoint already used the orchestrator, so it would have hit the same issue if the env var had ever been set elsewhere.

## Scope

Fix the **infrastructure** path (option 1 from investigation): wire `MEDIA_IDEMPOTENCE_TABLE` to the existing `episode_idempotence` DynamoDB table in Terraform. Do **not** rename the DynamoDB resource — only expose it via the env var. Do **not** change the Python default; leave it as a safety net.

## Files to modify

- `infrastructure/terraform/lambda_api.tf` — add `MEDIA_IDEMPOTENCE_TABLE = aws_dynamodb_table.episode_idempotence_v1.name` next to the existing `ARTIFACT_IDEMPOTENCE_TABLE` / `TRANSLATION_IDEMPOTENCE_TABLE` lines.
- `infrastructure/terraform/lambda_workers.tf` — same addition next to lines 140-141.

Verify the IAM role attached to the API Lambda already has DynamoDB read/write permission on `episode_idempotence` (it should — workers already use it). If not, extend the IAM policy.

## Acceptance Criteria
<!-- AC:BEGIN -->
- `terraform plan` shows only env var additions on `aws_lambda_function.media-summarizer-api` and the relevant worker Lambdas (no DynamoDB resource changes).
- After deploy, hitting `POST /api/media/ingest-url` with a YouTube URL returns 202 (not 500).
- Sharing text and audio via the share extension also succeeds end-to-end.
- CloudWatch logs no longer show `ResourceNotFoundException` on `episode_idempotence` / `media_idempotence` GetItem calls.
<!-- SECTION:DESCRIPTION:END -->

- [ ] #1 terraform plan shows MEDIA_IDEMPOTENCE_TABLE=episode_idempotence added to media-summarizer-api and all worker Lambdas, with no DynamoDB resource changes
- [ ] #2 After deploy, POST /api/media/ingest-url with a YouTube URL returns 202 instead of 500
- [ ] #3 Sharing text and audio via the share extension succeeds end-to-end (no 500)
- [ ] #4 CloudWatch logs show no ResourceNotFoundException on idempotence GetItem calls
- [ ] #5 IAM role on media-summarizer-api confirmed to have read/write on episode_idempotence (extend policy if missing)
<!-- AC:END -->
