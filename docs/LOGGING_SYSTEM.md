# Logging System

## Overview

All application logs are emitted as structured JSON via a single shared formatter. The entry point is `media_summarizer/utils/logging_config.py`, which provides `setup_logging()`, `log_event()`, `bind_log_context()`, and redaction helpers.

## Setup

Every process (API, worker) calls `setup_logging(service, *, env, version)` exactly once at startup:

```python
from media_summarizer.utils.logging_config import setup_logging
setup_logging("api", version="0.1.0")
setup_logging("worker-download")
setup_logging("worker-summarization")
```

The function is idempotent (same signature → no-op). It installs a single `JsonFormatter` on the root logger and suppresses noisy third-party loggers (`botocore`, `boto3`, `httpx`, `urllib3`, `aiobotocore`).

Workers must **not** call `logging.basicConfig(...)` at module level. It must be called only inside `main()`.

## JSON Schema

Every log record conforms to this schema. Fields absent from context are serialized as `null`.

| Field | Type | Description |
|---|---|---|
| `timestamp` | ISO 8601 Z | UTC time of the log record |
| `level` | string | `DEBUG`, `INFO`, `WARNING`, `ERROR`, `CRITICAL` |
| `service` | string | Process name: `api`, `worker-download`, `worker-summarization`, etc. |
| `env` | string | `dev`, `test`, `prod` |
| `event` | string | Stable dot-namespaced event name (see below) |
| `message` | string | Human-readable description (redacted) |
| `request_id` | string | HTTP request UUID, bound by middleware |
| `user_id` | string | Authenticated user ID |
| `job_id` | string | Processing job UUID |
| `media_item_id` | string | Canonical media item ID (same as job_id in current model) |
| `media_type` | string | `audio`, `article`, `video` |
| `source_platform` | string | `youtube`, `tiktok`, `instagram`, `audio`, `web`, `rss` |
| `resolver_key` | string | Active resolver: `youtube`, `tiktok`, `apify`, `deepgram`, `article` |
| `provider` | string | External provider: `deepgram`, `dynamodb`, `s3`, `sqs`, `openai` |
| `transcript_source` | string | `deepgram` (canonical active path), `whisper` (legacy path) |
| `fallback_strategy` | string | Strategy level used when primary path unavailable |
| `artifact_id` | string | Artifact identifier |
| `artifact_type` | string | `summary`, `notes`, `quiz`, `flashcards` |
| `queue` | string | SQS queue name |
| `attempt` | int | SQS delivery attempt count |
| `duration_ms` | int | Elapsed time in milliseconds |
| `error_code` | string | Machine-readable error identifier |
| `error_type` | string | Exception class name |
| `path` | string | HTTP path |
| `method` | string | HTTP method |
| `status` | int | HTTP status code |
| `version` | string | Application version |

## Emitting Events

Use `log_event()` to attach a stable `event` name:

```python
from media_summarizer.utils.logging_config import log_event

log_event(
    logger,
    logging.INFO,
    "media.ingest.created",
    "Media item created and queued",
    media_item_id=job.id,
    source_platform="youtube",
    queue="youtube-ingestion-queue",
)
```

Never emit events with `logger.info(f"...")` in canonical paths — that produces unstable `event: "log.record"` payloads.

## Request Context

The API middleware (`request_id_middleware` in `main.py`) binds `request_id`, `path`, and `method` for every request. Endpoints bind additional context (`user_id`, `media_item_id`, etc.) using `bind_log_context()` and restore it with `reset_log_context(token)` in a `finally` block.

## Stable Event Names

### API Surface — `media.*`

| Event | Level | Description |
|---|---|---|
| `media.ingest.started` | INFO | URL received, platform detected |
| `media.ingest.created` | INFO | Job created and queued to resolver |
| `media.ingest.failed` | ERROR | Ingest could not be created |
| `media.get.succeeded` | INFO | Media item status returned |
| `media.get.not_found` | WARNING | Media item ID unknown |
| `media.get.forbidden` | WARNING | User does not own media item |
| `media.get.failed` | ERROR | Unexpected failure fetching media item |

### API Surface — `artifact.*`

| Event | Level | Description |
|---|---|---|
| `artifact.create.requested` | INFO | Artifact generation queued |
| `artifact.create.invalid_type` | WARNING | Unknown artifact_type in request |
| `artifact.create.failed` | ERROR | Failed to queue artifact |
| `artifact.list.succeeded` | INFO | Artifact list returned |
| `artifact.list.failed` | ERROR | Unexpected failure listing artifacts |
| `artifact.get.succeeded` | INFO | Artifact returned |
| `artifact.get.not_found` | WARNING | Artifact not found |
| `artifact.get.failed` | ERROR | Unexpected failure fetching artifact |

### API Error Handling — `api.*`

| Event | Level | Description |
|---|---|---|
| `api.request_error` | WARNING/ERROR | HTTP 4xx/5xx response |
| `api.validation_error` | WARNING | 422 request body validation failure |
| `api.request_slow` | WARNING | Request exceeded `API_SLOW_REQUEST_THRESHOLD_MS` |

### Workers — `worker.*`

| Event | Level | Description |
|---|---|---|
| `worker.started` | INFO | Worker process started |
| `worker.completed` | INFO | One-shot worker finished |
| `worker.download.started` | INFO | Audio download started |
| `worker.download.completed` | INFO | Audio downloaded, queued to Deepgram |
| `worker.download.failed` | ERROR | Audio download error |
| `worker.batch_received` | INFO | Batch of messages received from queue |
| `worker.poll_error` | ERROR | Error polling SQS queue |
| `worker.message_completed` | DEBUG | Message processed and deleted |
| `worker.retry_scheduled` | WARNING | Message failed, will be retried by SQS |
| `worker.failed` | ERROR | Message exhausted retries, going to DLQ |

### External Calls — `external_call.*`

| Event | Level | Description |
|---|---|---|
| `external_call.succeeded` | DEBUG | AWS/external call succeeded |
| `external_call.failed` | ERROR | AWS/external call failed |

### Runtime — `runtime.*`

| Event | Level | Description |
|---|---|---|
| `runtime.aws_endpoint_ignored` | WARNING | `AWS_ENDPOINT_URL` set but ignored outside dev |

### Notifications — `notification.*`

| Event | Level | Description |
|---|---|---|
| `notification.failed` | ERROR | Failed to enqueue notification |
| `notification.skipped` | WARNING | Notification path disabled |

## Platform-Specific Logging

### Deepgram (active transcription path)

Workers that consume from `deepgram-transcription-queue` should include:

```python
log_event(logger, logging.INFO, "worker.transcription.started", "Deepgram transcription started",
          job_id=job_id, transcript_source="deepgram", provider="deepgram")

log_event(logger, logging.INFO, "worker.transcription.completed", "Deepgram transcription done",
          job_id=job_id, transcript_source="deepgram", duration_ms=elapsed_ms)

log_event(logger, logging.ERROR, "worker.transcription.failed", "Deepgram transcription failed",
          job_id=job_id, transcript_source="deepgram", error_code="DEEPGRAM_ERROR",
          error_type=type(exc).__name__, exc_info=exc)
```

### YouTube resolver

```python
log_event(logger, logging.INFO, "resolver.youtube.started", "YouTube transcript fetch started",
          job_id=job_id, source_platform="youtube", resolver_key="youtube")

log_event(logger, logging.WARNING, "resolver.youtube.fallback", "YouTube transcript unavailable, falling back to yt-dlp",
          job_id=job_id, source_platform="youtube", fallback_strategy="ytdlp_audio")
```

### Instagram via Apify

```python
log_event(logger, logging.INFO, "resolver.instagram.started", "Instagram Apify resolution started",
          job_id=job_id, source_platform="instagram", resolver_key="instagram.default", provider="apify")
```

### TikTok via yt-dlp

```python
log_event(logger, logging.INFO, "resolver.tiktok.started", "TikTok download started",
          job_id=job_id, source_platform="tiktok", resolver_key="tiktok")

log_event(logger, logging.WARNING, "resolver.tiktok.fallback", "TikTok video download failed, trying audio_only",
          job_id=job_id, source_platform="tiktok", fallback_strategy="audio_only")
```

## Security and Redaction

The formatter automatically redacts:

- Fields named: `access_token`, `api_key`, `apify_api_token`, `authorization`, `cookie`, `deepgram_api_key`, `jwt`, `openai_api_key`, `password`, `refresh_token`, `secret`, `token`
- Fields named `email` or `user_email` → masked to `u***r@domain.com`
- URL query params with keys: `access_token`, `api_key`, `auth`, `code`, `password`, `secret`, `token`
- Bearer/Token authorization header values in string fields
- Email addresses appearing in free-form strings

Never log raw user-supplied PII, credentials, or secrets in message strings.

## Log Levels by Environment

| Env | Default Level | `uvicorn.access` | Notes |
|---|---|---|---|
| `dev` + `DEBUG=true` | DEBUG | enabled | Full verbosity |
| `dev` | INFO | enabled | Standard development |
| `test` | INFO | enabled | Same as dev |
| `prod` | INFO | disabled | Only high-signal: INFO, WARNING, ERROR |

Override with `LOG_LEVEL=DEBUG|INFO|WARNING|ERROR`.

## AWS Endpoint Override

`AWS_ENDPOINT_URL` (LocalStack) is only active in `env=dev`. Outside dev, the env var is silently ignored and a one-time `runtime.aws_endpoint_ignored` warning is emitted. This prevents accidental LocalStack usage in test/prod environments.
