---
id: task-131
title: Fix YouTube ingestion — Apify actor 404 + missing failure event queue — discovered during Phase 4
status: To Do
assignee: []
created_date: '2026-06-09 12:35'
labels:
  - bug
  - backend
  - ingestion
dependencies: []
priority: high
dispatchable: true
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
## Context

Discovered during Phase 4 E2E re-run on AWS dev (V1 launch plan §4) **after task-129 was merged**. The YouTube ingestion worker has been migrated from `youtube-transcript-api` (blocked from Lambda IPs) to Apify. The migration replaces the native transcript fetch with an Apify actor call, but the deployed code fails for two distinct reasons.

## Symptom

Ingesting a YouTube URL via `POST /api/media/ingest-url` enqueues correctly, but the `youtube_ingestion_worker` Lambda fails. The job reaches `status: failed` with the user-facing message:

```
"YouTube transcript retrieval is temporarily unavailable. Please retry."
```

CloudWatch logs `/aws/lambda/media-summarizer-worker-youtube_ingestion`:

```
YouTubeIngestionError: http_404
  at _fetch_apify_transcript (line 262)
  at process_youtube_message (line 623)

# Then the failure-event handler also crashes:
QueueDoesNotExist: An error occurred (AWS.SimpleQueueService.NonExistentQueue)
  at _publish_failure_event (line 512)
  at sqs.get_queue_url (utils/sqs.py:55)
```

## Bug 1 — Apify actor returns 404

`media_summarizer/workers/youtube_ingestion_worker.py:262` raises `YouTubeIngestionError("http_404")`. Apify's API returned 404 on the actor invocation. Possible root causes:

- **Wrong actor ID**: `APIFY_YOUTUBE_TRANSCRIPT_ACTOR_ID=scrape-creators/best-youtube-transcripts-scraper` — this slug may not exist on Apify, or has been renamed, or has been removed. Confirm by hitting `https://api.apify.com/v2/acts/<slug>` directly with the token.
- **Wrong API path**: the worker may be calling the wrong Apify endpoint shape (`/acts/<id>/runs` vs `/acts/<id>/run-sync` vs `/acts/<id>/runs/last`).
- **Wrong token**: `APIFY_YOUTUBE_API_TOKEN=<APIFY_YOUTUBE_API_TOKEN>` — verify the token is valid and has access to that specific actor (it's a different account from `APIFY_INSTAGRAM_API_TOKEN`).
- **Per-account split misconfigured**: task-127 split `APIFY_API_TOKEN` per source. The YouTube account/token may not have been authorized to use the actor.

Confirmed empirically: the token + actor ID are present in Lambda env vars (Secrets Manager has them after task-130 + tfvars update on 2026-06-09), so it's not a missing-config issue.

## Bug 2 — Failure event queue does not exist

Independent of Bug 1, the worker's error-handling path crashes a second time. `_publish_failure_event` (line 512) calls `sqs.send_message(queue_name=..., ...)`, and `get_queue_url` (utils/sqs.py:55) returns `QueueDoesNotExist`.

Need to identify which queue name `_publish_failure_event` is targeting (probably `media-failure-events` or similar that was supposed to be created in Terraform but wasn't). Compare with the similar `EPISODE_COMPLETED_EVENTS_QUEUE` pattern that *does* exist.

This bug pattern is the third one of its kind in the project (cf. task-120 bug 2 on `extraction_metadata` field, task-122 bug 2 on `media_artifacts` table). The error-handling code path is consistently the least-tested.

## Reproduction

```bash
API=https://jji077bi8e.execute-api.eu-west-3.amazonaws.com
TOKEN=<...>

curl -X POST "${API}/api/media/ingest-url" \
  -H "Authorization: Bearer ${TOKEN}" -H "Content-Type: application/json" \
  -d '{"url":"https://www.youtube.com/watch?v=arj7oStGLkU"}'
# → 202 + media_item_id

# Poll the media item: stays pending ~30s, then transitions to failed
# with message "YouTube transcript retrieval is temporarily unavailable. Please retry."
```

CloudWatch confirms the cascade: Apify 404 → caught and re-raised as `YouTubeIngestionError("http_404")` → handler tries to publish failure event → SQS QueueDoesNotExist → cascade failure.

## Fix

1. **Bug 1**: investigate the Apify 404. Test the actor URL manually via `curl`:
   ```bash
   curl -H "Authorization: Bearer ${APIFY_YOUTUBE_API_TOKEN}" \
     "https://api.apify.com/v2/acts/scrape-creators~best-youtube-transcripts-scraper"
   ```
   Note the `~` separator instead of `/` — Apify uses `~` in URL paths. The worker code may be using the wrong separator. Also try alternative public actor slugs (e.g. `topaz_sharingan/Youtube-Transcript-Scraper-1` or whichever was recommended in task-126 benchmark `docs/research/task-126-youtube-extraction/README.md`).
2. **Bug 2**: locate `_publish_failure_event` and the queue it targets. Either:
   - Add the missing queue to `infrastructure/terraform/sqs.tf` + `iam_lambda.tf` (worker IAM policy), then `terraform apply`.
   - Or remove the failure event publication entirely if no consumer exists. A failed job updates DynamoDB directly via `mark_job_failed` already; the SQS event may be vestigial.
3. After fixing, rebuild + push Lambda image (`docker buildx ... --provenance=false --sbom=false`), update `media-summarizer-worker-youtube_ingestion`, re-run the E2E test.

## Out of scope

- Refactoring the YouTube worker beyond fixing these two bugs
- Adding new YouTube-specific features (chapters, comments, etc.)
- Migrating other ingestion workers to Apify

## References

- task-126 (YouTube benchmark — recommended Apify)
- task-127 (Apify token split per account)
- task-129 (YouTube migration to Apify — incomplete)
- task-130 (LocalStack purge — uncovered the regression by re-running E2E with fresh deploy)
- `media_summarizer/workers/youtube_ingestion_worker.py:262` (Apify 404 raise)
- `media_summarizer/workers/youtube_ingestion_worker.py:512` (`_publish_failure_event` SQS call)
- `media_summarizer/utils/sqs.py:55` (`get_queue_url` raises QueueDoesNotExist)
- CloudWatch logs `/aws/lambda/media-summarizer-worker-youtube_ingestion` (real production failure observed 2026-06-09)
- `tests/e2e/test_phase4_other_sources.py::test_youtube_ingestion` (failing test that catches this)
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 Root cause of Apify 404 documented (wrong actor slug, wrong API path, wrong token, or other) and fixed
- [ ] #2 `_publish_failure_event` no longer crashes — either the missing queue is provisioned in Terraform or the publish call is removed
- [ ] #3 If the failure event queue is added: declared in `sqs.tf`, IAM permission added in `iam_lambda.tf` for worker role, `terraform apply` clean
- [ ] #4 Lambda image rebuilt + redeployed, `media-summarizer-worker-youtube_ingestion` running new digest
- [ ] #5 `pytest -m e2e tests/e2e/test_phase4_other_sources.py::test_youtube_ingestion` passes (job reaches `completed`, transcript on S3)
- [ ] #6 Trigger summary artifact on the YouTube media item; reaches `ready` with S3 key
- [ ] #7 No regression on the 7 article happy-path tests (`pytest -m e2e tests/e2e/test_phase4_ingestion.py`)
<!-- AC:END -->
