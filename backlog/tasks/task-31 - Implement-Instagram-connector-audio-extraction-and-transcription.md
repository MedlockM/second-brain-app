---
id: task-31
title: Implement Instagram connector (audio extraction and transcription)
status: Done
assignee:
  - '@codex'
created_date: '2026-02-24 11:03'
updated_date: '2026-03-16 21:47'
labels: []
dependencies:
  - task-20
  - task-21
priority: high
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Implement the Instagram connector path that extracts audio and feeds it through transcription for share-first ingestion. Reference ADR: `docs/ADR/social-video-and-youtube-ingestion-fallback-strategy.md`. The implementation must follow the Instagram-specific ingestion strategy defined there, including Instagram via `getinsaver`.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 Instagram URLs can be processed to obtain transcribable audio.
- [x] #2 Extracted audio is routed through the shared transcription pipeline.
- [x] #3 Connector handles extraction failures and unsupported content with stable errors.
- [x] #4 Connector output conforms to shared ingestion contract fields.
<!-- AC:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
1. Split Instagram routing from the shared social resolver by introducing an internal `instagram.default` resolver while keeping TikTok on `social.default`.
2. Implement inline Instagram resolution against `getinsaver` (`POST /download/instagram`) with stable media-type mapping (`reel|post|igtv`), extraction of the first usable `downloads[].url`, and minimal normalized metadata.
3. Add provider-resolution error types so unsupported Instagram URL formats still map to `UNSUPPORTED_URL`, non-retryable provider payload/content failures map to `BAD_REQUEST`, and transient/provider availability failures map to `INTERNAL_ERROR` with stable user-facing messages.
4. Reuse the existing orchestration path unchanged so resolved Instagram `audio_url` values enqueue directly to the Deepgram transcription queue.
5. Add runtime configuration for `GETINSAVER_API_BASE_URL`, `GETINSAVER_API_KEY`, and `GETINSAVER_TIMEOUT_SECONDS`, propagate them through local env/dev runtime docs, and update ingestion/share-first architecture docs for the new `instagram.default` path.
6. Validate with targeted compile/lint checks and a smoke review of the API routing/error path; do not add automated tests for this task unless explicitly requested.
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Implemented a dedicated `instagram.default` resolver backed by `getinsaver` inline provider resolution and routed Instagram URLs away from `social.default` while leaving TikTok on the shared resolver path.

Added provider-resolution error taxonomy and API mapping so unsupported Instagram URL formats still surface as `UNSUPPORTED_URL`, provider payload/content failures surface as `BAD_REQUEST`, and transient/provider availability failures surface as safe `INTERNAL_ERROR` responses.

Reused the existing Deepgram queue orchestration path by returning `ResolvedMedia.audio_url` from the Instagram resolver; no new worker or queue was added.

Propagated `GETINSAVER_API_BASE_URL`, `GETINSAVER_API_KEY`, and `GETINSAVER_TIMEOUT_SECONDS` through runtime config/env docs and updated ingestion/share-first architecture docs for `instagram.default`.

Validation completed with `.venv/bin/python -m py_compile` on touched Python modules, targeted `ruff check` on ingestion files, a mocked Instagram resolver smoke test, and a safe-message HTTP handler smoke test. No live provider call was executed in this environment.
<!-- SECTION:NOTES:END -->
