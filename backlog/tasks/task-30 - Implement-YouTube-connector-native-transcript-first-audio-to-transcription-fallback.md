---
id: task-30
title: >-
  Implement YouTube connector (native transcript first, audio-to-transcription
  fallback)
status: Done
assignee:
  - '@codex'
created_date: '2026-02-24 11:03'
updated_date: '2026-03-16 21:58'
labels: []
dependencies:
  - task-20
  - task-21
priority: high
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Implement YouTube connector that prioritizes native transcript retrieval and falls back to audio transcription when needed. Reference ADR: `docs/ADR/social-video-and-youtube-ingestion-fallback-strategy.md`. The implementation must follow the fallback strategy defined there, including the YouTube cascade and transcript-source expectations.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 YouTube URLs use native transcript retrieval when available.
- [x] #2 Fallback path to audio transcription works when native transcript is unavailable.
- [x] #3 Connector reports transcript source consistently in output metadata.
- [x] #4 Connector handles timeout and unavailable-content failures safely.
<!-- AC:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
1. Keep `youtube.default` resolver lightweight and queue-first: return normalized YouTube payload with queued worker metadata only, no inline provider calls.
2. Extend `ProcessingJobSubmissionOrchestrator` to enqueue `youtube-ingestion-queue` for `MediaFamily.YOUTUBE`, mark the job started, and expose queue metadata without changing public media endpoints.
3. Add a dedicated `youtube_ingestion_worker` that extracts the canonical YouTube video id, runs transcript fallback `manual -> auto`, uploads successful native transcript text to S3, persists transcript/extraction metadata, and publishes canonical completion events.
4. When native transcripts are unavailable, use `yt-dlp` as a Python library to resolve a remote audio stream URL and enqueue the existing Deepgram pipeline with fallback metadata; do not download media locally or add Whisper paths.
5. Add internal runtime wiring for `YOUTUBE_INGESTION_QUEUE`, `YOUTUBE_TRANSCRIPT_TIMEOUT_SECONDS`, and `YTDLP_TIMEOUT_SECONDS` across env/config/local runtime/scaling, plus required Python dependencies `youtube-transcript-api` and `yt-dlp`.
6. Normalize YouTube `/live/{id}` URLs into canonical `/watch?v={id}` form so routing and media-key deduplication stay aligned across supported YouTube URL formats.
7. Update ingestion architecture/mobile docs to describe the queue-first YouTube runtime and Deepgram-only audio fallback, then run targeted validation (compile/import plus manual flow checks where feasible).
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Implemented queue-first YouTube ingestion end to end. `youtube.default` now returns queued-worker metadata only, `ProcessingJobSubmissionOrchestrator` enqueues `youtube-ingestion-queue`, and a dedicated `youtube_ingestion_worker` executes the YouTube cascade `manual -> auto -> audio` without any inline provider call on `POST /api/media/ingest-url`.

Native transcript path: the worker extracts the canonical video id, uses `youtube-transcript-api` in manual-first then auto-generated order, uploads normalized transcript text to S3, persists `transcription_metadata.provider=native_transcript` plus `source_detail`, and publishes canonical completion events.

Fallback path: when no native transcript exists, the worker resolves a remote audio stream URL with `yt-dlp` as a Python library and forwards the job to the existing Deepgram queue with `audio_duration_seconds` when available. `extraction_metadata.selected_strategy` now distinguishes `native_transcript` vs `audio_fallback`, keeping transcript source traceable in the existing media status API contract.

Runtime/config/docs: added `youtube-transcript-api` and `yt-dlp`, wired `YOUTUBE_INGESTION_QUEUE`, `YOUTUBE_TRANSCRIPT_TIMEOUT_SECONDS`, and `YTDLP_TIMEOUT_SECONDS` through config/example env/local docker runtime, updated ingestion architecture/mobile/scaling docs, and aligned YouTube canonicalization so `/live/{id}` normalizes to `/watch?v={id}` like other accepted YouTube URL forms.

Validation performed: `uv lock`, AST parsing on touched Python files, import checks for `youtube_transcript_api` + `yt_dlp`, use-case import smoke, `docker-compose.dev.yml` YAML parse, canonicalization smoke for `watch/youtu.be/shorts/live`, and targeted in-memory worker smoke checks covering native transcript success, Deepgram fallback enqueue, and terminal unavailable failure publishing.

Residual risk: the repository already had pre-existing gaps in the ephemeral scaling runtime outside this task (for example the shared ephemeral worker path is not fully locally verifiable here). I updated the YouTube queue/scaling wiring by following the existing pattern, but I did not run an end-to-end production-style scaling test in this environment.
<!-- SECTION:NOTES:END -->
