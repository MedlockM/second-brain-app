---
id: task-6
title: Finalize structured logging for the canonical share-first pipeline
status: Done
assignee:
  - '@codex'
created_date: '2026-01-14 22:34'
updated_date: '2026-04-23 08:58'
labels: []
dependencies:
  - task-10
  - task-11
  - task-12
  - task-22
  - task-24
  - task-25
  - task-26
  - task-27
  - task-28
  - task-29
  - task-30
  - task-31
  - task-33
  - task-34
  - task-51
  - task-54
priority: high
ordinal: 3000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Finalize the application logging system defined in `docs/LOGGING_SYSTEM.md` for the current canonical share-first codebase. The task covers `/api/media/*` and `/api/artifacts/*`, the canonical media ingestion/resolution/transcription flow, and the active artifact workers. Logging must align with the post-legacy architecture: Deepgram is the active audio transcription path, artifacts are first-class (`summary`, `quiz`, `notes`), and email/Whisper/episode-centric completion paths are no longer the target runtime behavior. Platform-specific coverage must include podcast resolution, article extraction, YouTube fallback cascade, Instagram ingestion via `getinsaver`, and TikTok ingestion via `yt-dlp` with `audio_only` fallback, while preserving low-noise structured logs and redaction guarantees.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 `docs/LOGGING_SYSTEM.md` is implemented through a single shared logging setup used by canonical API entrypoints and active workers, without relying on scattered ad hoc `logging.basicConfig` calls in the target runtime paths.
- [x] #2 Canonical API surfaces (`POST /api/media/ingest-url`, `GET /api/media/{media_item_id}`, `POST /api/media/{media_item_id}/artifacts`, `GET /api/media/{media_item_id}/artifacts`, `GET /api/artifacts/{artifact_id}`) emit structured JSON logs with the required fields and stable event names for failures and key lifecycle transitions.
- [x] #3 Active share-first workers and services log resolver outcomes, transcription progress, and artifact lifecycle consistently, including provider/fallback metadata where applicable (`transcript_source`, strategy level, platform/provider, queue, attempt, `error_code`, `error_type`).
- [x] #4 Logging behavior follows the current environment and security rules: prod/test do not rely on LocalStack endpoint overrides, secrets and PII are redacted, and prod noise is limited to high-signal events, warnings, errors, and slow-path logging.

- [x] #5 No active logging coverage assumes legacy email notifications, Whisper runtime, or episode-centric completion as the primary target path; Deepgram and first-class artifacts (`summary`, `quiz`, `notes`) are covered explicitly.
<!-- AC:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
1. Refactor `media_summarizer/utils/logging_config.py` into the single shared logging/config entrypoint for JSON formatting, env normalization (`development|production` -> `dev|prod`), redaction, stable event helpers, request/worker context binding, and one-time `AWS_ENDPOINT_URL` policy warnings.
2. Reuse existing FastAPI integration points in `media_summarizer/api/main.py` and `media_summarizer/api/error_handling.py`: initialize shared logging at app startup, keep `request_id_middleware` as the canonical request context source, and align exception logging to stable spec events rather than adding a parallel mechanism.
3. Update canonical API handlers in `media_summarizer/api/endpoints/media.py` and `media_summarizer/api/endpoints/artifacts.py` to emit stable lifecycle events for canonical success paths (`media.ingest.accepted`, `media.ingest.duplicate_reused`, `media.status.read`, `artifact.requested`) with structured context.
4. Replace ad hoc `logging.basicConfig(...)` usage in active canonical workers/services with shared setup and instrument canonical worker/runtime events for resolver outcomes, transcription enqueue/completion/failure, retry scheduling, fallback/provider decisions, and artifact lifecycle (`summary`, `quiz`, `notes`).
5. Treat `AWS_ENDPOINT_URL` as shared runtime config plus logging work: update at minimum `media_summarizer/utils/s3.py`, `media_summarizer/utils/sqs.py`, and `media_summarizer/utils/database_async.py` so test/prod ignore LocalStack endpoint overrides with warning, while dev remains LocalStack-compatible.
6. Reduce noise in shared helper layers by removing generic INFO success chatter for low-level SQS/S3/Dynamo operations in canonical runtime paths while keeping structured error logging and DEBUG detail where useful in dev/test.
7. Apply global prod-noise controls for the FastAPI process, including suppressing noisy access logs by default in prod while preserving error and slow-path visibility.
8. Validate with targeted import/AST/compile/config checks and log-shape review, then record implementation notes and acceptance progress back into Backlog.
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Implemented shared structured logging foundation in `media_summarizer/utils/logging_config.py` with JSON schema, context binding, redaction, env normalization, `setup_logging()`, and one-time `AWS_ENDPOINT_URL` ignore warnings outside dev.

Removed import-time `AWS_ENDPOINT_URL` dependence from canonical shared AWS helpers by routing S3, SQS, and DynamoDB client creation through runtime helpers (`media_summarizer/utils/s3.py`, `media_summarizer/utils/sqs.py`, `media_summarizer/utils/database_async.py`). Reduced low-value INFO success chatter and converted helper failures to structured `external_call.failed` logs.

Reused existing FastAPI hooks instead of adding parallel mechanisms: `request_id_middleware` in `media_summarizer/api/main.py` now binds request context and slow-request events; `media_summarizer/api/error_handling.py` now emits structured `api.request_error` / `api.validation_error` events; canonical endpoints in `media_summarizer/api/endpoints/media.py` and `media_summarizer/api/endpoints/artifacts.py` now bind entity context and emit stable success events.

Instrumented canonical orchestration/runtime surfaces with stable events and shared setup: resolver/orchestrator layers, podcast/article/YouTube/TikTok/Deepgram workers, artifact service lifecycle, summary/quiz/notes/flashcards workers, and the active completion-events consumer. Replaced remaining target-worker `logging.basicConfig(...)` bootstraps with `setup_logging(...)`.

Final pass (2026-04-23):
- Removed all `logging.basicConfig()` calls from `media_summarizer/workers/transcription/worker.py` (Whisper legacy path) and `media_summarizer/workers/transcription/http_server.py`
- Added structured logging with `transcript_source="whisper"` to differentiate Whisper from canonical Deepgram path
- Updated folder operations in `database_async.py` to use `_dynamodb_client_kwargs()` and structured `_log_dynamodb_*` helpers
- Updated `media_completed_worker.py` to emit stable `worker.started` event
- Added `flashcards` to artifact types in `docs/LOGGING_SYSTEM.md`
- All canonical workers now use `setup_logging()` in their `main()` or `__main__` blocks

Validation completed: `py_compile` passed for all touched files; `docker compose -f docker-compose.dev.yml config` passed. No `logging.basicConfig` calls remain in `media_summarizer/` directory.

Dispatch 2026-04-23: Implémentation complétée par agent-task-6. Merged dans second-brain-project.
<!-- SECTION:NOTES:END -->
