---
id: task-122
title: Fix on-demand artifact generation pipeline (API↔worker contract mismatch + missing media_artifacts table + missing quiz worker) — discovered during Phase 4
status: To Do
assignee: []
created_date: '2026-06-09 00:00'
labels:
  - bug
  - backend
  - infrastructure
dependencies: []
priority: high
dispatchable: true
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
## Context

Discovered during Phase 4 re-test on AWS dev (V1 launch plan §4) **after task-121 was merged**. The summarization worker now works (`POST /api/media/{id}/artifacts` with `summary` succeeds end-to-end). But triggering `notes`, `flashcards`, or `quiz` reveals **three distinct broken pieces of the on-demand artifact pipeline**.

## Bug 1 — API↔worker contract mismatch on `artifact_id` (HIGH)

The API endpoint `POST /api/media/{media_item_id}/artifacts` (in `media_summarizer/api/endpoints/artifacts.py:104-113`) sends this SQS message:

```python
message_body = {
    "job_id": job.id,
    "media_item_id": job.id,
    "artifact_type": artifact_type,
    "user_id": current_user.id,
    "transcript_s3_key": job.transcription_s3_key,
}
```

But the workers `notes` and `flashcards` (and almost certainly `quiz` if it existed) expect `artifact_id` as a top-level field:

- `media_summarizer/workers/notes/worker.py:233-253`: reads `body.get("artifact_id")`, raises `ValueError("Missing fields for notes generation")` if absent.
- `media_summarizer/workers/flashcards/worker.py:288`: same pattern.

The summarization worker **doesn't** require `artifact_id` (which is why task-121's fix unblocked it), but the others do.

The API also returns `artifact_id=job.id` in the response — implying the design conflates "media item ID" and "artifact ID" — but this conflation isn't propagated to the SQS message under the field name `artifact_id`.

### Decision needed

Option A — **API generates an `artifact_id`, persists to `media_artifacts` table, then enqueues with the new ID**. This requires Bug 2 (table) to be fixed first.

Option B — **API sends `media_item_id` as `artifact_id`** (cheap conflation, what the response already does). Workers would then read `artifact_id` from the message and use it to look up state. But persistence still requires the `media_artifacts` table to exist.

Probably Option A is the proper fix since the codebase already has `mark_artifact_generating`, `fail_artifact_generation`, and `media_artifacts.get_media_artifact_by_id` — these all assume each artifact has its own row.

## Bug 2 — `media_artifacts` DynamoDB table not created by Terraform (CRITICAL)

`media_summarizer/utils/media_artifacts.py:20` reads `MEDIA_ARTIFACTS_TABLE = os.environ.get("MEDIA_ARTIFACTS_TABLE", "media_artifacts")`. The table is referenced in:

- `core/services/artifact_service.py:681` — `fail_artifact_generation` does a `get_media_artifact_by_id` lookup
- `mark_artifact_generating` (called by every worker before processing)
- `update_artifact_with_s3_key` (called on success)

But **no Terraform resource creates this table**. `aws dynamodb list-tables --region eu-west-3` returns 19 tables, none of them `media_artifacts`.

Result: every artifact worker that tries to `mark_artifact_generating` or `fail_artifact_generation` gets `ResourceNotFoundException` → cascade failure even on the success path of the worker logic.

### Fix

Add `aws_dynamodb_table.media_artifacts` in a new file or in `dynamodb_core_tables.tf`. Schema needs investigation:

- Hash key: presumably `id` (artifact_id, UUID)
- Probable secondary index: by `media_item_id` to list artifacts for a media item (`GET /api/media/{id}/artifacts`)
- Attributes likely needed: `id`, `media_item_id`, `user_id`, `artifact_type`, `status`, `s3_key`, `s3_bucket`, `created_at`, `updated_at`, `error_message`, `parameters` (JSON)

Read the actual access patterns in `media_summarizer/utils/media_artifacts.py` and `core/services/artifact_service.py` to confirm GSIs needed.

## Bug 3 — `quiz` artifact has no queue and no worker (HIGH)

`POST /api/media/{id}/artifacts` with `{"artifact_type":"quiz"}` returns `500: "Failed to queue artifact generation"` because `QueueDoesNotExist`.

Investigation:

- `lambda_workers.tf` declares 13 workers: podcastindex_resolution, article_extraction, x_ingestion, youtube_ingestion, tiktok_ingestion, deepgram_transcription, summarization, document_parsing, search_indexing, rss_feed_poll, media_completed_events, flashcards, notes — **no `quiz`**.
- `sqs.tf` (or wherever queues are defined) similarly has no `quiz-queue`.
- But the API `artifacts.py` lists `quiz` as a valid `artifact_type` in `_ALLOWED_ARTIFACT_TYPES` (line 87 — to verify exact list).
- And there's a `QUIZ_BUCKET` env var injected by Terraform (post task-120) — implying the bucket is provisioned but not the queue/worker.

### Fix options

Option A — **Add the `quiz` worker + queue + DLQ** in Terraform (`sqs.tf` + `lambda_workers.tf`), and create `media_summarizer/workers/quiz/worker.py` (probably copy from `flashcards/worker.py` with prompt changes).

Option B — **Remove `quiz` from `_ALLOWED_ARTIFACT_TYPES`** if it's not in V1 scope. Cleaner short-term. Mention V1 launch plan §0 — quiz is listed as an artifact type but maybe deferred.

Need owner decision: is quiz V1 scope or post-V1?

## Reproduction

```bash
API=https://jji077bi8e.execute-api.eu-west-3.amazonaws.com
TOKEN=<...>
MEDIA_ID=<an article media that reached completed>

# Bug 3: quiz queue missing
curl -X POST "${API}/api/media/${MEDIA_ID}/artifacts" \
  -H "Authorization: Bearer ${TOKEN}" -H "Content-Type: application/json" \
  -d '{"artifact_type":"quiz"}'
# → 500 "Failed to queue artifact generation"

# Bugs 1+2: notes worker rejects the message
curl -X POST "${API}/api/media/${MEDIA_ID}/artifacts" \
  -H "Authorization: Bearer ${TOKEN}" -H "Content-Type: application/json" \
  -d '{"artifact_type":"notes"}'
# → 202 queued, then worker logs:
#   "Missing fields for notes generation"
#   followed by ResourceNotFoundException on media_artifacts table
```

## Working baseline

- `summary` artifact type works E2E after task-121 fix. The corresponding worker `summarization` doesn't require `artifact_id` (it uses `job_id`) and doesn't call `media_artifacts` persistence functions.
- Article ingestion E2E works (transcript reaches S3, job reaches `completed`).

## Out of scope

- Refactoring artifact generation API contract beyond fixing the contract mismatch
- Adding new artifact types beyond `quiz`
- Cascading auto-generation (V1 spec is on-demand only)

## References

- task-102 (email notification removal)
- task-120 (S3 bucket alignment)
- task-121 (summarization email field)
- V1 launch plan §0 (artifacts list: summary, notes, flashcards, quiz mentioned)
- `media_summarizer/api/endpoints/artifacts.py:73-150` (POST /artifacts)
- `media_summarizer/workers/notes/worker.py:231-253`
- `media_summarizer/workers/flashcards/worker.py:288`
- `media_summarizer/workers/summarization/summarization_worker.py` (working baseline post task-121)
- `media_summarizer/utils/media_artifacts.py` (table access)
- `media_summarizer/core/services/artifact_service.py:681` (`fail_artifact_generation`)
- `infrastructure/terraform/lambda_workers.tf` (no quiz worker)
- `infrastructure/terraform/sqs.tf` (no quiz queue)
- `infrastructure/terraform/dynamodb_*.tf` (no media_artifacts table)
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 Decision recorded in this task: Bug 1 fix Option A (API persists artifact_id) vs B (conflation)
- [ ] #2 Decision recorded in this task: Bug 3 — `quiz` is V1 scope (add worker+queue) or removed from `_ALLOWED_ARTIFACT_TYPES`
- [ ] #3 `media_artifacts` DynamoDB table created in Terraform with the schema needed by `media_summarizer/utils/media_artifacts.py` (hash key, GSIs verified against access patterns)
- [ ] #4 `MEDIA_ARTIFACTS_TABLE` env var injected by Terraform into all worker Lambdas + API Lambda (no hardcoded fallback)
- [ ] #5 API `POST /api/media/{id}/artifacts` and worker SQS message contract aligned per Bug 1 decision; all 4 artifact types reach `completed` end-to-end
- [ ] #6 If `quiz` kept in V1: worker, queue, DLQ, IAM permissions, log group, event source mapping all created in Terraform; worker module written in `media_summarizer/workers/quiz/`
- [ ] #7 Lambda image rebuilt + redeployed; affected Lambdas updated via `aws lambda update-function-code`
- [ ] #8 E2E re-test: ingest article → reaches `completed` → trigger each artifact type allowed in V1 → each reaches `completed` with S3 key in correct bucket
- [ ] #9 At least 1 non-article source tested E2E (YouTube or podcast)
<!-- AC:END -->
