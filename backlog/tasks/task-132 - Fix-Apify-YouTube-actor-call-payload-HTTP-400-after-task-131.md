---
id: task-132
title: Fix Apify YouTube actor call payload — HTTP 400 — discovered after task-131
status: To Do
assignee: []
created_date: '2026-06-09 12:50'
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

Discovered during Phase 4 E2E re-run on AWS dev **after task-131 was merged**. task-131 fixed Bug 2 (`_publish_failure_event` queue missing) and either fixed or worked around Bug 1 (the original Apify actor URL `404`). The worker no longer cascades through a second crash.

But **Apify still rejects the actor call**, this time with HTTP 400 instead of 404.

## Symptom

CloudWatch logs `/aws/lambda/media-summarizer-worker-youtube_ingestion`:

```
{
  "level": "ERROR",
  "event": "transcription.failed",
  "message": "YouTube ingestion failed",
  "queue": "youtube-ingestion-queue",
  "resolver_key": "youtube.default",
  "source_platform": "youtube",
  "error_code": "apify_actor_failed",
  "detail": "http_400"
}
```

Reaching the actor's URL is now possible (no 404) but Apify rejects the request body. Possible causes:

- **Wrong input schema**: the worker probably posts a JSON body to the actor's `run-sync` or `runs` endpoint, but the body shape doesn't match what the actor declares it accepts. Each Apify actor has a documented input schema (e.g. `{"videoUrl": "..."}` vs `{"url": "..."}` vs `{"videos": [...]}` etc.)
- **Missing required field**: Apify 400 typically points at a missing `startUrls` / `videoUrls` / etc.
- **Malformed payload**: maybe the URL is double-quoted, or sent as a string instead of an array.

## Reproduction

```bash
API=https://jji077bi8e.execute-api.eu-west-3.amazonaws.com
TOKEN=<...>

curl -X POST "${API}/api/media/ingest-url" \
  -H "Authorization: Bearer ${TOKEN}" -H "Content-Type: application/json" \
  -d '{"url":"https://www.youtube.com/watch?v=arj7oStGLkU"}'
```

## Fix

1. **Read the actor's online documentation as the source of truth.** The actor
   slug currently configured is `scrape-creators/best-youtube-transcripts-scraper`
   (env var `APIFY_YOUTUBE_TRANSCRIPT_ACTOR_ID`). Its public Apify Store page —
   `https://apify.com/scrape-creators/best-youtube-transcripts-scraper` — has
   the canonical "Input" schema with required and optional fields, plus example
   payloads. Read that page first; it's authoritative and current.

   Cross-check with the API:
   ```bash
   curl -H "Authorization: Bearer ${APIFY_YOUTUBE_API_TOKEN}" \
     "https://api.apify.com/v2/acts/scrape-creators~best-youtube-transcripts-scraper/input-schema"
   ```
   (Apify uses `~` as separator inside URL paths, NOT `/`.)
2. Compare with what `_fetch_apify_transcript` (in `youtube_ingestion_worker.py`)
   actually posts. The body builder is around the same line as the `httpx.post`
   call. Identify exactly which field is missing or malformed.
3. Adjust the payload to match the schema. Re-deploy. Verify with the E2E test.

## Out of scope

- Switching to a different Apify actor (already done in task-126 / task-129).
- Adding retry logic for actor cold-starts (separate concern).

## References

- task-126 (YouTube benchmark recommending Apify)
- task-129 (Migration to Apify)
- task-131 (Fixed Apify URL 404 + failure queue)
- `media_summarizer/workers/youtube_ingestion_worker.py` (`_fetch_apify_transcript`)
- CloudWatch `/aws/lambda/media-summarizer-worker-youtube_ingestion` 2026-06-09
- `tests/e2e/test_phase4_other_sources.py::test_youtube_ingestion`
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 Read the actor's online documentation at `https://apify.com/scrape-creators/best-youtube-transcripts-scraper`. Documented the actor's actual input schema (required + optional fields, example payload) in this task's notes (or in `docs/research/task-126-youtube-extraction/README.md`)
- [ ] #2 `_fetch_apify_transcript` payload matches the schema; specific changes documented
- [ ] #3 Lambda image rebuilt + redeployed
- [ ] #4 `pytest -m e2e tests/e2e/test_phase4_other_sources.py::test_youtube_ingestion` passes (job reaches `completed`, transcript on S3)
- [ ] #5 Trigger summary artifact on the YouTube media item; reaches `ready` with S3 key
- [ ] #6 No regression on the 7 article happy-path tests
<!-- AC:END -->
