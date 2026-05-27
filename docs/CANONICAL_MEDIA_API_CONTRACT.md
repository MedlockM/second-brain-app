# Canonical Media API Contract (Frozen)

Frozen on February 24, 2026 for task-19.

This document is the contract baseline for:
- backend implementation tasks (`task-10`, `task-20`, `task-21`, `task-22`, `task-33`)
- mobile/web client implementation tasks (`task-39`, `task-7`)

Pre-production policy for this roadmap:
- canonical API paths are unversioned
- no runtime fallback to legacy podcast-specific contracts in target state

## Scope

This freeze defines:
- canonical request/response contracts for ingestion, status, artifact creation, and artifact reads
- domain types and statuses for `MediaItem`, `MediaArtifact`, and processing lifecycle usage
- stable error payload and error code catalog for client handling

## Source of truth in code

Backend contract models:
- `media_summarizer/api/models/media_contracts.py`

Frontend contract types:
- `front/src/types/media.ts`

## Runtime implementation status

`task-10` implements the canonical ingestion entrypoint:
- `POST /api/media/ingest-url` in `media_summarizer/api/endpoints/media.py`
- authenticated with the same bearer auth context used by existing API endpoints
- wired to the hexagonal ingestion core (`build_default_ingest_url_use_case`)

Operational behavior now implemented in runtime:
- deterministic URL normalization via canonical media identity derivation
- deduplication by canonical `media_key` (equivalent links reuse existing processing/media ids)
- response returns both `media_item_id` and `processing_job.job_id` for client tracking
- invalid/unsupported URL errors are explicit and stable (`INVALID_URL`, `UNSUPPORTED_URL`)

`task-22` implements the canonical media status read entrypoint:
- `GET /api/media/{media_item_id}` in `media_summarizer/api/endpoints/media.py`
- authenticated with ownership checks against the current user

Operational behavior now implemented in runtime:
- status response is built from current `ProcessingJob` state with canonical lifecycle mapping
- terminal state details are surfaced through `processing_job.completed_at`, `error_code`, and `error_message`
- stable not-found and unauthorized errors are returned as `MEDIA_NOT_FOUND` (404) and `NOT_AUTHORIZED` (403)
- media status responses include canonical artifact metadata from `media_artifacts` when available
- transcript metadata (`language`, `segments_count`, `duration_seconds`) is surfaced when the runtime has persisted it from transcription or article extraction
- the response remains sufficient for transcript-first clients to poll a media item and render per-artifact progress snapshots

`task-11` implements canonical on-demand artifact requests on top of transcript-ready media:
- `POST /api/media/{media_item_id}/artifacts` in `media_summarizer/api/endpoints/media.py`
- authenticated with ownership checks against the current user

Operational behavior now implemented in runtime:
- artifact requests are available for `summary`, `quiz`, and `notes`
- equivalent requests are idempotent through canonical request fingerprints and shared generation cache
- each artifact type follows its own `queued | generating | ready | failed` lifecycle without blocking other artifact types
- `task-33` implements dedicated authenticated artifact reads through `GET /api/media/{media_item_id}/artifacts` and `GET /api/artifacts/{artifact_id}`, with detail content loaded from canonical artifact storage

`task-23` purges legacy ingestion/completion compatibility from active canonical paths:
- canonical runtime idempotence/watchers use `media_key` only (no legacy episode-guid fallback reads/writes)
- worker completion events and fan-out finalization rely on `media_key`/`canonical_job_id` identity only
- legacy episode-guid table/env references are removed from canonical runtime config and migration docs

## Canonical endpoints

1. `POST /api/media/ingest-url`
2. `GET /api/media/{media_item_id}`
3. `POST /api/media/{media_item_id}/artifacts`
4. `GET /api/media/{media_item_id}/artifacts`
5. `GET /api/artifacts/{artifact_id}`

Authentication:
- all endpoints require authenticated user context

## Request and response contracts

### 1) POST /api/media/ingest-url

Request (`IngestUrlRequest`):
```json
{
  "url": "https://open.spotify.com/episode/6rqhFgbbKwnb9MLmUQDhG6",
  "source_app": "android.share_sheet",
  "locale": "fr-FR",
  "idempotency_key": "mobile-share-4b7e8d"
}
```

Response (`IngestUrlResponse`):
```json
{
  "media_item": {
    "media_item_id": "med_01JQ8X8J5S3H3CXX8V70M9M3K7",
    "media_key": "mkey_v1_4f3b7f1c...",
    "original_url": "https://open.spotify.com/episode/6rqhFgbbKwnb9MLmUQDhG6",
    "normalized_url": "https://open.spotify.com/episode/6rqhFgbbKwnb9MLmUQDhG6",
    "media_type": "podcast_episode",
    "source_platform": "spotify",
    "status": "processing",
    "transcript": {
      "status": "pending"
    },
    "artifact_statuses": {},
    "created_at": "2026-02-24T20:20:00Z",
    "updated_at": "2026-02-24T20:20:00Z"
  },
  "processing_job": {
    "job_id": "job_01JQ8X8J5T9Q5V7Q4TW4N1HY03",
    "status": "pending",
    "progress": {
      "percentage": 0,
      "stage": "pending"
    },
    "created_at": "2026-02-24T20:20:00Z",
    "updated_at": "2026-02-24T20:20:00Z"
  },
  "deduplicated": false
}
```

### 2) GET /api/media/{media_item_id}

Response (`MediaStatusResponse`):
```json
{
  "media_item": {
    "media_item_id": "med_01JQ8X8J5S3H3CXX8V70M9M3K7",
    "media_key": "mkey_v1_4f3b7f1c...",
    "original_url": "https://open.spotify.com/episode/6rqhFgbbKwnb9MLmUQDhG6",
    "normalized_url": "https://open.spotify.com/episode/6rqhFgbbKwnb9MLmUQDhG6",
    "media_type": "podcast_episode",
    "source_platform": "spotify",
    "status": "ready_for_artifacts",
    "transcript": {
      "status": "ready",
      "transcription_s3_key": "job_01JQ8X8J5T9Q5V7Q4TW4N1HY03.txt",
      "source": "deepgram",
      "language": "fr",
      "segments_count": 583,
      "duration_seconds": 3540.1
    },
    "artifact_statuses": {
      "summary": {
        "status": "ready",
        "updated_at": "2026-02-24T20:37:10Z",
        "artifact_id": "art_01JQ8Y7BBEGWQ9VJ24M4S0C9H4"
      }
    },
    "created_at": "2026-02-24T20:20:00Z",
    "updated_at": "2026-02-24T20:37:10Z"
  },
  "processing_job": {
    "job_id": "job_01JQ8X8J5T9Q5V7Q4TW4N1HY03",
    "status": "ready_for_artifacts",
    "progress": {
      "percentage": 100,
      "stage": "ready_for_artifacts"
    },
    "created_at": "2026-02-24T20:20:00Z",
    "updated_at": "2026-02-24T20:35:30Z",
    "started_at": "2026-02-24T20:20:04Z",
    "completed_at": "2026-02-24T20:35:30Z"
  },
  "artifacts": []
}
```

### 3) POST /api/media/{media_item_id}/artifacts

Request (`ArtifactCreateRequest`):
```json
{
  "artifact_type": "summary",
  "parameters": {
    "language": "fr",
    "style": "structured"
  },
  "idempotency_key": "summary-med_01JQ8X8J5S3H3CXX8V70M9M3K7-v1"
}
```

Response (`ArtifactCreateResponse`):
```json
{
  "artifact": {
    "artifact_id": "art_01JQ8Y7BBEGWQ9VJ24M4S0C9H4",
    "media_item_id": "med_01JQ8X8J5S3H3CXX8V70M9M3K7",
    "artifact_type": "summary",
    "status": "queued",
    "parameters": {
      "language": "fr",
      "style": "structured"
    },
    "created_at": "2026-02-24T20:36:04Z",
    "updated_at": "2026-02-24T20:36:04Z"
  },
  "reused_existing": false
}
```

### 4) GET /api/media/{media_item_id}/artifacts

Response (`ArtifactListResponse`):
```json
{
  "media_item_id": "med_01JQ8X8J5S3H3CXX8V70M9M3K7",
  "items": [
    {
      "artifact_id": "art_01JQ8Y7BBEGWQ9VJ24M4S0C9H4",
      "media_item_id": "med_01JQ8X8J5S3H3CXX8V70M9M3K7",
      "artifact_type": "summary",
      "status": "ready",
      "parameters": {
        "language": "fr",
        "style": "structured"
      },
      "created_at": "2026-02-24T20:36:04Z",
      "updated_at": "2026-02-24T20:37:10Z",
      "completed_at": "2026-02-24T20:37:10Z"
    }
  ],
  "count": 1
}
```

### 5) GET /api/artifacts/{artifact_id}

Response (`ArtifactDetailResponse`):
```json
{
  "artifact": {
    "artifact_id": "art_01JQ8ZNOTESGWQ9VJ24M4S0C9H4",
    "media_item_id": "med_01JQ8X8J5S3H3CXX8V70M9M3K7",
    "artifact_type": "notes",
    "status": "ready",
    "parameters": {
      "language": "fr",
      "audience": "study"
    },
    "content": {
      "artifact_id": "art_01JQ8ZNOTESGWQ9VJ24M4S0C9H4",
      "media_item_id": "med_01JQ8X8J5S3H3CXX8V70M9M3K7",
      "artifact_type": "notes",
      "generated_at": "2026-02-24T20:37:10Z",
      "source": {
        "transcript_s3_key": "job_01JQ8X8J5T9Q5V7Q4TW4N1HY03.txt",
        "generator_version": "notes:gpt-4o-mini-2024-07-18:prompt-v1"
      },
      "content": {
        "objectives": [
          "..."
        ],
        "concepts": [
          {
            "term": "...",
            "explanation": "...",
            "importance": "core"
          }
        ],
        "key_points": [
          "..."
        ],
        "action_items": [
          "..."
        ],
        "glossary": [
          {
            "term": "...",
            "definition": "..."
          }
        ]
      }
    },
    "created_at": "2026-02-24T20:36:04Z",
    "updated_at": "2026-02-24T20:37:10Z",
    "completed_at": "2026-02-24T20:37:10Z"
  }
}
```

Canonical `notes` content shape for client rendering:
```json
{
  "artifact_id": "art_...",
  "media_item_id": "med_...",
  "artifact_type": "notes",
  "generated_at": "ISO-8601",
  "source": {
    "transcript_s3_key": "...",
    "generator_version": "notes:...:prompt-v1"
  },
  "content": {
    "objectives": [
      "..."
    ],
    "concepts": [
      {
        "term": "...",
        "explanation": "...",
        "importance": "core"
      }
    ],
    "key_points": [
      "..."
    ],
    "action_items": [
      "..."
    ],
    "glossary": [
      {
        "term": "...",
        "definition": "..."
      }
    ]
  }
}
```

Malformed `notes` model output is handled with strict validation:
- strip optional markdown fences
- parse JSON
- validate required sections and item shapes
- mark artifact `failed` with `VALIDATION_ERROR` if validation fails
- never persist a degraded fallback payload as `ready`

## Domain enums (locked)

`MediaItem`:
- `status`: `ingested | resolving | processing | ready_for_artifacts | failed | cancelled`
- `transcript.status`: `pending | extracting | transcribing | ready | failed`

`MediaArtifact`:
- `artifact_type`: `summary | quiz | notes`
- `status`: `queued | generating | ready | failed`

`ProcessingJob` lifecycle usage:
- `pending | classifying | resolving | downloading | extracting | transcribing | ready_for_artifacts | completed | failed | cancelled`

## Transitional status mapping (legacy -> canonical)

When reading existing `ProcessingJob.status` values during migration:
- `pending` -> `pending`
- `rss_resolving` -> `resolving`
- `downloading` -> `downloading`
- `transcribing` -> `transcribing`
- `summarizing` -> `ready_for_artifacts`
- `notifying` -> `completed`
- `completed` -> `completed`
- `failed` -> `failed`
- `cancelled` -> `cancelled`

## Error contract (stable)

Canonical error response:
```json
{
  "error": {
    "code": "INVALID_URL",
    "message": "The provided URL is invalid.",
    "request_id": "0d4b1c81-a8d1-4ff2-88f9-8af0c1fdf6ba"
  },
  "detail": "Invalid URL"
}
```

Stable error codes:
- `BAD_REQUEST`
- `INVALID_URL`
- `UNSUPPORTED_URL`
- `SESSION_EXPIRED`
- `NOT_AUTHORIZED`
- `NOT_FOUND`
- `MEDIA_NOT_FOUND`
- `ARTIFACT_NOT_FOUND`
- `CONFLICT`
- `VALIDATION_ERROR`
- `RATE_LIMITED`
- `PAYMENT_REQUIRED`
- `QUOTA_EXCEEDED`
- `INSUFFICIENT_MINUTES`
- `INTERNAL_ERROR`

HTTP mapping rules:
- `400`: input/URL errors (`BAD_REQUEST`, `INVALID_URL`, `UNSUPPORTED_URL`)
- `401`: `SESSION_EXPIRED`
- `403`: `NOT_AUTHORIZED`
- `404`: not-found family (`NOT_FOUND`, `MEDIA_NOT_FOUND`, `ARTIFACT_NOT_FOUND`)
- `409`: `CONFLICT`
- `422`: `VALIDATION_ERROR`
- `429`: `RATE_LIMITED`
- `402`: `PAYMENT_REQUIRED`, `INSUFFICIENT_MINUTES`, `QUOTA_EXCEEDED`
- `500`: `INTERNAL_ERROR` (user-safe message only)

## Contract invariants

- `media_key` must be deterministic from canonical URL normalization.
- Ingestion is idempotent for equivalent normalized URLs.
- Artifact creation is idempotent for equivalent `(media_item_id, artifact_type, parameters, idempotency_key)` requests.
- Timestamps use ISO-8601 UTC strings.
- `request_id` must be returned in error payload and response header.

## Relationship to existing runtime APIs

Current runtime still exposes legacy paths under `/api/v1/*`:
- `/api/v1/podcast-search/*`
- `/api/v1/jobs/*`
- `/api/v1/episodes/my-episodes`

These legacy paths are not the canonical target contract and must not drive new mobile share-first implementation once canonical endpoints are implemented.
