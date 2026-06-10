---
id: task-173
title: >-
  Simplify Instagram resolver — drop Comment Scraper and legacy post-video
  branch
status: Done
assignee: []
created_date: '2026-06-10 08:16'
labels:
  - cleanup
  - backend
  - ingestion
dependencies: []
priority: low
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
## Context

After the migration of the Reel resolver to `khadinakbar/video-subtitle-extractor` (native captions only, no Deepgram fallback), the Instagram resolver still carries two pieces of code whose value-to-cost ratio is questionable in 2026:

1. **Comment Scraper invocation** (`_fetch_comments` + `_extract_comments`) — runs on every Reel and every Post. Per the benchmark task-107 cost model, comments dominate the Apify bill (~$17/month for 250 posts × 30 comments vs ~$2-5/month for Reels+Posts alone). The comments are stored in `metadata` but **not surfaced anywhere in the user-facing UX** today.

2. **Legacy "post video" branch in `_resolve_post`** (around lines 530–575 of `media_summarizer/infrastructure/resolvers/instagram_apify_resolver.py`). Since Instagram fused feed videos into Reels in July 2022, no new content reaches `/p/<code>/` as a video. Only pre-2022 archival videos still hit this path. Volume in 2026 is negligible, and the branch's only purpose is to feed Deepgram — which is now inconsistent with the Reel path that has no Deepgram fallback at all.

Removing these two pieces yields a resolver with **two clean branches**:
- `/reel/` and `/tv/` → native transcript via Video Subtitle Extractor (or fail)
- `/p/` → image / carousel via Post Scraper (or fail)

## Scope

### Remove
- `_fetch_comments` and `_extract_comments` helpers in `instagram_apify_resolver.py`
- `APIFY_INSTAGRAM_COMMENT_ACTOR_ID` constant + the `comment_actor_id` constructor parameter + `self._comment_actor_id`
- The `comments` / `comments_count` keys from every metadata dict produced by the resolver
- The "video post" branch of `_resolve_post`: the call to `_extract_video_url_from_post_result`, the `if video_url: ...` block that builds `audio_url` metadata. The helper `_extract_video_url_from_post_result` itself becomes unused — delete it.
- The `Path B` (`audio_url` → Deepgram queue) of `instagram_ingestion_worker.py::process_instagram_message`. With Reels native-only and post-video gone, the resolver never returns `audio_url` for Instagram. Worker should hard-fail when neither `raw_text` nor an image-post payload is present, instead of forwarding to the Deepgram queue.
- `APIFY_INSTAGRAM_COMMENT_ACTOR_ID` from `media_summarizer/core/config.py`
- Any Terraform / SAM env var declaration that references the comment actor ID

### Keep
- `_resolve_reel` flow (Video Subtitle Extractor, native-only) — already correct
- `_resolve_post` flow for images and carousels of images — already correct
- The `IMAGE_POST` resolution path that queues an image-OCR worker

### Test fallout
- Any unit test that mocks `_fetch_comments` or asserts `comments` in metadata — update to drop the assertion
- `tests/e2e/test_phase4_other_sources.py::test_instagram_ingestion` — should still pass because the fixture reel has native captions; verify metadata assertions don't reference removed fields

## Out of scope
- Carousel posts that mix images and videos (rare cross-format case) — leave as-is
- Re-introducing comments later if a UX surfaces them — that would be a fresh feature task, not a regression of this cleanup
- Touching the TikTok / YouTube resolvers

## Why now

The cleanup matches the new architectural rule established by the Reel migration: **Instagram = native-text-or-fail**, no audio fallback. Carrying around the Deepgram-feeding video-post branch and the unused comment scraper hides intent and inflates the Apify bill for nothing.

## References
- `media_summarizer/infrastructure/resolvers/instagram_apify_resolver.py`
- `media_summarizer/workers/instagram_ingestion_worker.py` (`process_instagram_message`, Path B)
- `media_summarizer/core/config.py` (Apify Instagram env vars)
- Benchmark `docs/research/task-107-instagram-extraction-benchmark/README.md` — cost section showing comments dominate the bill
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 #1 `instagram_apify_resolver.py` no longer references `APIFY_INSTAGRAM_COMMENT_ACTOR_ID`, `_fetch_comments`, `_extract_comments`, or `_extract_video_url_from_post_result`; the resolver exposes exactly two resolution paths (Reel/IGTV transcript-only, Post image/carousel)
- [ ] #2 #2 No metadata dict produced by the resolver carries `comments` or `comments_count` keys
- [ ] #3 #3 `process_instagram_message` in `instagram_ingestion_worker.py` raises a `NonRetryableProviderResolutionError`-style failure when the resolver returns neither `raw_text` nor an image-post payload, instead of forwarding to the Deepgram queue; the `DEEPGRAM_TRANSCRIPTION_QUEUE` send-message call is removed from this worker
- [ ] #4 #4 `APIFY_INSTAGRAM_COMMENT_ACTOR_ID` removed from `media_summarizer/core/config.py` and from any Terraform / SAM env var declaration
- [ ] #5 #5 `pytest tests/unit -k instagram` passes with no skipped/xfailed tests caused by the cleanup
- [ ] #6 #6 `pytest -m e2e tests/e2e/test_phase4_other_sources.py::test_instagram_ingestion` passes against a Reel that has native captions
<!-- AC:END -->
