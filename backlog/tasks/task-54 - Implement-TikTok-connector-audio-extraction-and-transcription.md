---
id: task-54
title: Implement TikTok connector (audio extraction and transcription)
status: Done
assignee:
  - '@codex'
created_date: '2026-03-16 21:00'
updated_date: '2026-03-16 22:08'
labels:
  - backend
  - ingestion
  - tiktok
  - transcription
dependencies:
  - task-20
  - task-21
priority: high
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Implement the TikTok connector path that extracts audio and feeds it through transcription for share-first ingestion. Reference ADR: `docs/ADR/social-video-and-youtube-ingestion-fallback-strategy.md`. The implementation must follow the TikTok-specific ingestion strategy defined there, including `yt-dlp` method A with `audio_only` fallback and TikTok rate-limiting constraints.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 TikTok URLs can be processed to obtain transcribable audio.
- [x] #2 Extracted audio is routed through the shared transcription pipeline.
- [x] #3 Connector handles extraction failures, rate limits, and unsupported content with stable errors.
- [x] #4 Connector output conforms to shared ingestion contract fields.
<!-- AC:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
1. Separate TikTok routing and resolver wiring from generic social video handling.
2. Extend ingestion orchestration with TikTok queue-first submission and extracting lifecycle state.
3. Implement TikTok ingestion worker with native-subtitles-first flow and Deepgram URL fallback.
4. Add reusable global rate limiter support for TikTok and stable TikTok user-facing errors.
5. Wire dependencies, environment, docker-compose, and infrastructure queue/scaling support.
6. Run targeted verification (AST/compile and focused smoke checks) and capture results.
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
User confirmed the TikTok fallback must never download/upload audio artifacts; Deepgram must receive a direct remote media URL extracted from yt-dlp. Existing repo state already includes queue-first YouTube ingestion and separated Instagram routing, so TikTok implementation will follow the YouTube worker pattern while remaining TikTok-only.

Implemented TikTok-specific routing and resolver wiring (`tiktok.default`) with queue-first orchestration and runtime `extracting`/`transcribing` lifecycle support. Added dedicated `tiktok_ingestion_worker` that tries native subtitles via `yt-dlp` first, uploads only transcript text to `TRANSCRIPT_BUCKET`, and otherwise sends a direct remote media URL to `DEEPGRAM_TRANSCRIPTION_QUEUE` without downloading or uploading audio artifacts.

Added reusable distributed Redis/local rate-limiter primitives plus TikTok limiter wrapper, stable TikTok user-facing error mappings, TikTok env vars, docker-compose worker wiring, and Terraform/localstack/scaling/monitoring queue support for `tiktok-ingestion-queue`.

Verification: Python AST parsing passed for all touched application/scaling modules; `docker-compose -f docker-compose.dev.yml --env-file .env.dev config` passed; targeted grep confirmed TikTok worker only uploads transcript text and does not perform audio S3 upload/presign fallback. `terraform fmt -check ...` could not be run because `terraform` is not installed in this environment.
<!-- SECTION:NOTES:END -->
