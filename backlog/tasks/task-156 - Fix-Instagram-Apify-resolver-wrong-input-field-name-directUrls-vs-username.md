---
id: task-156
title: Fix Instagram Apify resolver — wrong input field name (directUrls vs username)
status: Done
assignee: []
created_date: '2026-06-10 00:00'
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

After task-153 pushed the Apify Instagram credentials to Secrets Manager, the Instagram E2E test still fails with `apify_non_retryable: Unable to resolve transcribable media from this Instagram URL`. The worker contacts Apify, but Apify returns an empty result list.

Direct test of the Apify actor `apify~instagram-reel-scraper` confirms the bug: the actor's input schema requires the field name `username` (containing the Reel URL), not `directUrls`. The worker is using `directUrls` (cf. `instagram_apify_resolver.py:410`).

## Symptom

`pytest -m e2e tests/e2e/test_phase4_other_sources.py::test_instagram_ingestion` fails. Job lands in `failed` ~10s with:

```
"error_code": "unsupported_content"
"detail": "apify_non_retryable:Unable to resolve transcribable media from this Instagram URL."
```

CloudWatch shows the worker calls Apify successfully (no auth error) but `_run_actor` returns an empty list:

```python
# instagram_apify_resolver.py:408-411
results = await self._run_actor(
    actor_id=self._reel_actor_id,
    input_data={"directUrls": [context.normalized_url]},  # <-- wrong field name
)
if not results:
    raise NonRetryableProviderResolutionError(...)
```

## Empirical proof

Calling the actor directly via curl with `directUrls` returns:

```json
{ "error": { "type": "invalid-input", "message": "Input is not valid: Field input.username is required" } }
```

Calling the same actor with `username` instead returns a valid result item containing the Reel's caption, videoUrl, videoDuration, but no native transcript:

```json
[{
  "inputUrl": "...",
  "caption": "...",
  "transcript": null,
  "videoUrl": "https://scontent-iad6-1.cdninstagram.com/o1/v/...",
  "downloadedVideo": null,
  "videoDuration": 16.466,
  "type": "Video"
}]
```

So:
1. The actor accepts `username` (despite the misleading name — the field actually accepts a list of URLs OR a list of usernames)
2. With the correct input, the actor returns a result that the worker's downstream logic can handle: `videoUrl` is present → Deepgram fallback should fire (covered by task-150 once it lands)

## Root cause

The Apify actor `apify~instagram-reel-scraper` changed its input schema at some point, or the resolver was written against a different actor version. The field `directUrls` likely worked for an older version. Today, the actor strictly requires `username` (which can contain URLs).

## Fix

In `media_summarizer/infrastructure/resolvers/instagram_apify_resolver.py`:

1. Find the 3 `_run_actor` call sites (Reel, Post, Comment scrapers — lines ~410, ~490, ~565). Verify each actor's expected input field by:
   ```bash
   TOKEN=$APIFY_INSTAGRAM_API_TOKEN
   curl -sS -X POST "https://api.apify.com/v2/acts/<actor_slug>/run-sync-get-dataset-items?token=${TOKEN}" \
     -H "Content-Type: application/json" \
     -d '{"username":["<test_url>"],"resultsLimit":1}' -m 90
   ```
2. Replace `{"directUrls": [url]}` with `{"username": [url], "resultsLimit": 1}` in each call site (or whatever the canonical field is per actor).
3. Confirm by re-running each scraper's call manually before redeploying.
4. Rebuild + push Lambda image, redeploy `media-summarizer-worker-instagram_ingestion`.
5. Retest: `pytest -m e2e tests/e2e/test_phase4_other_sources.py::test_instagram_ingestion -v`.

After this fix, the test should still fail at the Deepgram fallback step (because the Reel has no native transcript and the worker needs to fall back to Deepgram on `videoUrl`). That's task-150's scope. So the AC for task-156 is "Apify call succeeds and returns a result" — not "test passes end-to-end".

## Reproduction

```bash
TOKEN=<APIFY_INSTAGRAM_API_TOKEN>   # cf. .env racine
curl -sS -X POST "https://api.apify.com/v2/acts/apify~instagram-reel-scraper/run-sync-get-dataset-items?token=${TOKEN}" \
  -H "Content-Type: application/json" \
  -d '{"directUrls":["https://www.instagram.com/reel/DZXolnGNeAG/"],"resultsLimit":1}' -m 60
# → "Field input.username is required"

# Then with username:
curl -sS -X POST "https://api.apify.com/v2/acts/apify~instagram-reel-scraper/run-sync-get-dataset-items?token=${TOKEN}" \
  -H "Content-Type: application/json" \
  -d '{"username":["https://www.instagram.com/reel/DZXolnGNeAG/"],"resultsLimit":1}' -m 60
# → returns 1 item with caption, videoUrl, videoDuration
```

## Out of scope

- Fixing the broader Deepgram fallback path (covered by task-150)
- Migrating to a different Instagram scraper actor
- Mobile UX for "instagram unavailable" errors

## References

- task-127 (Apify per-source split — introduced the actor IDs)
- task-146 (Instagram migration to Apify — wired the resolver)
- task-153 (pushed credentials to Secrets Manager)
- task-150 (planned: Instagram Apify→Deepgram fallback E2E test)
- `media_summarizer/infrastructure/resolvers/instagram_apify_resolver.py:410, 490, 565` (the 3 call sites to fix)
- Apify console: https://console.apify.com/actors/apify~instagram-reel-scraper/input-schema
- CloudWatch `/aws/lambda/media-summarizer-worker-instagram_ingestion` 2026-06-10 ~00:00 UTC
- `tests/e2e/test_phase4_other_sources.py::test_instagram_ingestion`
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 Each of the 3 Apify Instagram actor calls (Reel, Post, Comment) verified manually via curl and the correct input field name documented per actor
- [ ] #2 `instagram_apify_resolver.py` updated to use the correct input field for each actor
- [ ] #3 Lambda image rebuilt + `media-summarizer-worker-instagram_ingestion` redeployed
- [ ] #4 Re-running `pytest -m e2e tests/e2e/test_phase4_other_sources.py::test_instagram_ingestion` shows the worker successfully receives Apify results (CloudWatch log "Apify resolution started" → followed by either a transcript-extraction step or a Deepgram-fallback enqueue, NOT "Unable to resolve transcribable media")
- [ ] #5 The test itself may still fail at the Deepgram step (task-150) — that's expected and out of scope here
- [ ] #6 No regression on the 11 already-passing tests
<!-- AC:END -->
