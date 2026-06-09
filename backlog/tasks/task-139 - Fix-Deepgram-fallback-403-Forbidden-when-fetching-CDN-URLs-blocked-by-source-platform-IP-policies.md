---
id: task-139
title: Fix Deepgram fallback — 403 Forbidden when fetching CDN URLs blocked by source platform IP policies
status: To Do
assignee: []
created_date: '2026-06-09 17:30'
labels:
  - bug
  - backend
  - ingestion
dependencies: []
priority: medium
dispatchable: true
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
## Context

Discovered while validating the TikTok E2E test (`tests/e2e/test_phase4_other_sources.py::test_tiktok_ingestion`). The TikTok worker's happy path works (yt-dlp from Lambda is **not** blocked by TikTok), and when native subtitles are missing the worker correctly enqueues a Deepgram fallback message. **But Deepgram itself fails with HTTP 403** when it tries to fetch the audio URL from the source platform's CDN.

This is a generic problem affecting **any source whose CDN refuses requests from cloud SaaS IP ranges** when we hand them a direct URL. It will likely affect Instagram, X (when video posts are tested), and direct podcast audio URLs from podcast hosting platforms with anti-scraping measures.

## Symptom

`pytest -m e2e tests/e2e/test_phase4_other_sources.py::test_tiktok_ingestion` times out at `transcribing` (progress 50%).

CloudWatch `/aws/lambda/media-summarizer-worker-deepgram_transcription`:

```
"event": "transcription.failed"
"error_code": "deepgram_non_retryable"
"detail": "Deepgram non-retryable HTTP 400: {
  \"err_code\":\"REMOTE_CONTENT_ERROR\",
  \"err_msg\":\"The remote server hosting the media returned a client error: 403 Forbidden.\",
  \"request_id\":\"019ead07-a270-7e70-ac78-0ca18b8fb429\"
}"
```

The worker correctly handed the TikTok CDN URL to Deepgram, Deepgram tried to GET it, TikTok returned 403. The transcription pipeline ends there.

## Root cause

Deepgram's pull-mode (we send a URL, Deepgram fetches it) is convenient but exposes us to cloud-vs-cloud IP blocking by source platforms. TikTok's CDN explicitly blocks known cloud SaaS provider IPs. Same dynamic as YouTube blocking AWS Lambda IPs (which led to task-126 / task-129 Apify migration), but at a different layer:

- **YouTube**: blocks Lambda directly → fixed with Apify (different IP space)
- **TikTok**: allows Lambda but blocks Deepgram → a Lambda-side download + Deepgram push-mode would dodge it

Push-mode (we POST the binary audio to Deepgram) is supported by Deepgram and bypasses the issue entirely because Deepgram never fetches the URL. The Lambda runtime can fetch the CDN URL successfully (proven by the working TikTok happy path).

## Fix

Modify the Deepgram worker to **download the audio in Lambda, then push the binary to Deepgram** instead of passing a URL.

Concrete changes likely needed in `media_summarizer/workers/transcription/deepgram_worker.py` (or wherever the Deepgram client is invoked):

1. Check current invocation: probably uses `deepgram.listen.rest.v("1").transcribe_url(...)` (URL mode).
2. Switch to a streaming/binary path:
   - Lambda: `httpx.get(audio_url, stream=True)` to download to /tmp or buffer
   - Deepgram: `deepgram.listen.rest.v("1").transcribe_file(buffer, options=...)` (push mode)
3. Handle large files: Lambda has 512 MB ephemeral storage by default and 6 MB SQS message size limit, but the audio file can be 50–500 MB for long podcasts. Either:
   - Stream-download to /tmp (if size < 512 MB)
   - Or upload to S3 dev bucket then use Deepgram's URL mode against the S3 URL (requires bucket public-read or pre-signed URL — check Deepgram supports auth headers for the URL)
4. Keep the URL-mode path as a fallback for sources where push-mode is overkill (article extraction shouldn't change).

### Alternative: use S3 pre-signed URL

If push-mode adds too much complexity, a middle ground:
- Lambda downloads CDN audio
- Lambda uploads to `audio` S3 bucket
- Lambda generates a pre-signed S3 URL valid for ~10 minutes
- Lambda hands the S3 URL to Deepgram (Deepgram fetches from S3, which doesn't block cloud IPs)

This still requires the Lambda-side download but avoids changing the Deepgram client invocation. Trade-off: extra S3 storage + bandwidth, but simpler code change.

## Affected sources

Confirmed affected:
- TikTok (via direct CDN URL fallback when native subtitles absent)

Likely affected (not yet tested):
- Instagram (Apify provides downloaded video URLs that may be CDN-protected)
- X (video tweets fetched via X API)
- Some podcast hosts with anti-scraping (less common)

Not affected:
- Article extraction (no audio)
- Document parsing (no audio)
- YouTube (Apify already handles transcript without audio download)
- Self-hosted MP3s (e.g. archive.org, libsyn — they don't block cloud IPs)

## Reproduction

```bash
.venv/bin/pytest -m e2e tests/e2e/test_phase4_other_sources.py::test_tiktok_ingestion -v
```

Pick a TikTok URL whose video has no auto-captions, or any CDN-blocked source. The job stalls at `transcribing` progress 50%, then times out.

## Out of scope

- Adding new transcription backends beyond Deepgram (separate concern)
- Optimizing audio file size before Deepgram (separate concern)
- Refactoring the entire transcription pipeline (this is a targeted fix)

## References

- task-126 (sibling: YouTube IP block from Lambda → Apify)
- task-129 (sibling: YouTube migration implementation)
- Deepgram REST API docs (`transcribe_file` vs `transcribe_url`)
- `media_summarizer/workers/transcription/deepgram_worker.py`
- `tests/e2e/test_phase4_other_sources.py::test_tiktok_ingestion`
- CloudWatch `/aws/lambda/media-summarizer-worker-deepgram_transcription` 2026-06-09 ~15:36 UTC
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 Decision recorded in this task: push-mode (binary upload) vs S3 pre-signed URL workaround
- [ ] #2 Deepgram worker modified to handle CDN-blocked URLs without 403
- [ ] #3 Lambda image rebuilt + `media-summarizer-worker-deepgram_transcription` redeployed
- [ ] #4 `pytest -m e2e tests/e2e/test_phase4_other_sources.py::test_tiktok_ingestion` passes when fed a TikTok URL with no native captions (forces Deepgram fallback path)
- [ ] #5 No regression on the 9 already-passing tests
- [ ] #6 Cost impact documented (extra Lambda execution time for download, optional S3 storage)
<!-- AC:END -->
