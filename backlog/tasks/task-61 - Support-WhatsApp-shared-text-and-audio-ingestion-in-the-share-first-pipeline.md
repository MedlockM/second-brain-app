---
id: task-61
title: Support WhatsApp shared text and audio ingestion in the share-first pipeline
status: In Progress
assignee:
  - '@codex'
created_date: '2026-03-20 21:50'
updated_date: '2026-05-18 20:29'
labels:
  - mobile
  - backend
  - ingestion
  - whatsapp
dependencies:
  - task-37
  - task-38
  - task-93
  - task-41
priority: high
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Support end-to-end ingestion of content shared from WhatsApp so a user can forward either a text message or an audio message from WhatsApp into Media Summarizer and obtain a trackable media item in the share-first flow. The feature must cover the real payload shapes delivered by mobile share surfaces instead of assuming a URL-only entrypoint.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 Android and iOS share entrypoints can receive WhatsApp text shares and WhatsApp audio-file shares and preserve enough source metadata for downstream handling.
- [ ] #2 A shared WhatsApp text message can create a media item without requiring a URL and makes the source text available to the transcript-first product flow.
- [ ] #3 A shared WhatsApp audio message can create a media item from a local shared file payload and route it through the shared transcription pipeline without assuming a remote audio URL.
- [ ] #4 Unsupported, oversized, or malformed shared payloads fail safely with stable user-facing errors and without creating duplicate processing records.
- [ ] #5 Device validation documents the actual payload shapes observed from real WhatsApp text and audio shares on Android and iOS, including share type, MIME/content type, and filename or original name when available.
<!-- AC:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
1. Extend canonical media contracts with shared-content request/enum additions while keeping the URL-ingestion response shape unchanged.
2. Add a backend endpoint `POST /api/media/ingest-shared-content` that accepts multipart text/audio payloads, stages audio uploads to S3, and builds a shared-content command.
3. Add shared-content domain/use-case wiring and minimal enum/model changes (`whatsapp`, `text`, `shared_text`, `audio_s3_key`) without disturbing URL router behavior.
4. Extend the transitional orchestrator to handle `raw_text` immediate transcript completion and `audio_s3_key` queueing alongside the existing `audio_url` path.
5. Extend the Deepgram worker so it can transcribe either a remote `audio_url` or a staged S3 audio object, then run targeted compile/smoke validation without adding new tests.
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Research snapshot captured on 2026-03-20:
- Current runtime is URL-first (`POST /api/media/ingest-url`) with resolver routing based on canonical URL classification.
- There is no current canonical product endpoint for shared raw text or uploaded audio files.
- Current Deepgram worker uses remote URL transcription; WhatsApp audio support will likely require either a file-upload transcription mode or an internal upload/store step before transcription.
- Existing mobile roadmap tasks (`task-37`, `task-38`, `task-39`) cover generic share-first inbox flow and are prerequisites for end-user delivery.
- Real WhatsApp payload shape must be verified on devices and treated as runtime input, not hardcoded from assumptions about file extension.

Added design artifact `docs/SHARED_CONTENT_INGESTION_PROPOSAL.md` capturing the proposed canonical endpoint `POST /api/media/ingest-shared-content`, the minimal domain diff (`SourcePlatform.WHATSAPP`, `MediaFamily.TEXT`, `MediaType.SHARED_TEXT`, `ResolvedMedia.audio_s3_key`), and the recommended Deepgram file-backed path for WhatsApp audio. The proposal intentionally keeps the frozen URL-ingestion baseline untouched and scopes task-61 to a parallel shared-content flow.

Backend shared-content slice implemented on 2026-03-24. Added canonical `POST /api/media/ingest-shared-content` endpoint for multipart text/audio payloads, shared-content domain/use-case/wiring, enum expansions (`whatsapp`, `text`, `shared_text`), staged-audio S3 path, and Deepgram byte-upload transcription fallback via `audio_s3_key` in addition to existing remote `audio_url`.

Shared text path now stores the transcript immediately, marks the job completed locally, and publishes the standard `episode_completion_status` success event so watcher/minute/idempotence finalization stays aligned with other native ingestion paths.

Validation completed with targeted backend smoke checks only: `PYTHONPYCACHEPREFIX=/tmp/pycache .venv/bin/python -m py_compile media_summarizer/api/endpoints/media.py media_summarizer/core/media_ingestion/adapters/orchestrators.py media_summarizer/workers/transcription/deepgram_worker.py media_summarizer/core/media_ingestion/use_cases.py media_summarizer/core/media_ingestion/domain.py media_summarizer/api/models/media_contracts.py` and `.venv/bin/ruff check ... --select F401,I` both passed.

Remaining scope for full task closure: mobile Android/iOS share entrypoints (`task-37`, `task-38`, `task-39`) and device validation capturing real WhatsApp text/audio payload shapes, MIME types, filenames, and platform differences.
<!-- SECTION:NOTES:END -->
