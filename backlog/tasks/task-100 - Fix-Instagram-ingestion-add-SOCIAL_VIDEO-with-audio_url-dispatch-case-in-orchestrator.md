---
id: task-100
title: >-
  Fix Instagram ingestion: add SOCIAL_VIDEO with audio_url dispatch case in
  orchestrator
status: Done
assignee: []
created_date: '2026-05-19 21:31'
labels:
  - ingestion
dependencies: []
priority: high
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Instagram URL ingestion is broken. The classifier and resolver work correctly, but the orchestrator never dispatches Instagram jobs to any queue, so jobs silently stall.

## Root cause
`media_summarizer/core/media_ingestion/adapters/orchestrators.py` (around lines 337-417) has dispatch cases for X (`resolver_key == "x.default"`), TikTok (`resolver_key == "tiktok.default"`), articles (`media_family == ARTICLE`), YouTube, podcasts, and direct `audio_s3_key`/`audio_url`. But there is **no case** for `MediaFamily.SOCIAL_VIDEO` with `audio_url` — which is exactly what `InstagramResolver` returns after extracting the audio URL from GetInsaver.

The Instagram resolver in `media_summarizer/core/media_ingestion/adapters/resolvers.py` (lines 463-503) successfully:
1. Calls GetInsaver API with the Instagram URL
2. Extracts an `audio_url` for video/audio content (reels, posts, IGTV)
3. Returns a `ResolvedMedia` with `media_family=SOCIAL_VIDEO` and `audio_url=<extracted_url>`

But the orchestrator falls through without enqueuing → job stuck in `pending` forever.

## What to implement

### 1. Fix the orchestrator dispatch
In `Orchestrator.submit()` in `orchestrators.py`, add a new dispatch case **before** the article/youtube/podcast generic handlers:

```python
elif resolved.media_family == MediaFamily.SOCIAL_VIDEO and resolved.audio_url:
    # Instagram (and any future social video provider that returns a remote audio URL)
    await sqs_client.send_message(
        queue_name=self._deepgram_transcription_queue,
        message_body={
            "job_id": job.job_id,
            "user_id": job.user_id,
            "media_item_id": media_item.media_item_id,
            "audio_url": resolved.audio_url,
            "source_platform": resolved.source_platform.value,
            ...
        },
    )
```

The exact field set should match what's already sent for the `audio_url`-only path (look at the existing code that handles `if resolved.audio_url:` to be consistent).

### 2. Job state transition
Mark the job as `transcribing` when enqueued (same pattern as TikTok worker when it falls back to Deepgram). Use the `JobStateService` already imported in the orchestrator.

### 3. Verify Deepgram worker handles the URL path
Confirm `media_summarizer/workers/transcription/deepgram_worker.py` already supports being given a remote `audio_url` (vs only S3 keys). If not, add that path. From a quick look this should already work since TikTok's fallback uses the same queue.

### 4. Add a brief test
Create a unit test in `media_summarizer/tests/unit/core/media_ingestion/` that:
- Mocks `InstagramResolver` to return a `ResolvedMedia` with `media_family=SOCIAL_VIDEO` and `audio_url="https://example.com/audio.mp3"`
- Calls `orchestrator.submit()` with the mock
- Asserts that `sqs_client.send_message` was called with the Deepgram queue and a body containing the audio_url

## Verification
- Submit an Instagram reel URL via `POST /api/media/ingest` in dev
- Check that the job transitions: `pending` → `extracting` → `transcribing` → `completed`
- Verify the transcript appears in S3
- The artifact pipeline (summary, notes, flashcards) should then run as for any other completed media

## Why this is a V1 blocker
Instagram is one of the three priority social platforms for V1 (alongside X and TikTok). Without this fix, every Instagram share results in a stuck job and a broken UX.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 Orchestrator has a case for MediaFamily.SOCIAL_VIDEO with audio_url that enqueues to Deepgram transcription queue
- [ ] #2 Job state transitions to transcribing when Instagram URL is dispatched
- [ ] #3 Unit test covers the new dispatch case
- [ ] #4 Submitting an Instagram reel URL end-to-end completes successfully (pending → extracting → transcribing → completed)
- [ ] #5 Existing X and TikTok dispatch paths remain unchanged
<!-- AC:END -->
