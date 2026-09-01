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
- every successful save gets a fresh opaque `media_item_id`, even when the same user
  saves an equivalent URL several times
- processing and transcription are globally deduplicated by canonical `media_key`;
  equivalent links share the content job without sharing a library row
- response returns both `media_item_id` and `processing_job.job_id` for client tracking
- invalid/unsupported URL errors are explicit and stable (`INVALID_URL`, `UNSUPPORTED_URL`)

`task-22` implements the canonical media status read entrypoint:
- `GET /api/media/{media_item_id}` in `media_summarizer/api/endpoints/media.py`
- authenticated with ownership checks against the current user

Operational behavior now implemented in runtime:
- status response is built from current `ProcessingJob` state with canonical lifecycle mapping
- terminal state details are surfaced through `processing_job.completed_at`, `error_code`, and `error_message`
- stable not-found and unauthorized errors are returned as `MEDIA_NOT_FOUND` (404) and `NOT_AUTHORIZED` (403)
- the media status response carries **no** artifact projection (task-270): artifacts are a per-scope, append-only history, so "the artifact of this type" no longer exists as a concept
- transcript metadata (`language`, `segments_count`, `duration_seconds`) is surfaced when the runtime has persisted it from transcription or article extraction

`task-270` makes artifact generation **scope-addressed** and its storage **append-only**:
- one set of routes under `/api/artifacts` serves a single media (`scope="media"`) and a collection (`scope="folder"`); the per-media routes are gone, with no alias
- a collection covers the folder **and all its descendants**, exactly like `GET /api/media?folder_id=`
- every generation writes a **new immutable entry** carrying a snapshot of the sources it read; nothing is overwritten, nothing is invalidated, and adding or removing a media from a collection changes no existing entry
- an existing entry is reused **permanently** (task-322): the `artifact_id` is a hash of (user, scope, scope_id, type, parameters, sorted source ids) with no time component, so a request whose source set already produced an artifact returns that artifact, whatever the delay, without a second generation and without debiting quota. A media therefore gets one artifact per type and per `parameters`; a collection regenerates only when its contents changed. The generator version is recorded on the entry but excluded from the key, so bumping a prompt does not reopen a right to regenerate
- ownership is checked by comparing the entry's `user_id`, not by resolving a media item — a collection artifact has none
- a media-scoped request still accepts a user-owned `media_item_id`, but storage and
  history use `(user_id, media_key)` internally, so the same user's saves of one
  content item share their artifact history
- ceilings are 25 sources and 120 000 estimated tokens; beyond them the API refuses and never truncates

`task-23` purges legacy ingestion/completion compatibility from active canonical paths:
- canonical runtime idempotence/watchers use `media_key` only (no legacy episode-guid fallback reads/writes)
- worker completion events and fan-out finalization rely on `media_key`/`canonical_job_id` identity only
- legacy episode-guid table/env references are removed from canonical runtime config and migration docs

## Canonical endpoints

1. `POST /api/media/ingest-url`
2. `GET /api/media/{media_item_id}`
3. `POST /api/artifacts`
4. `GET /api/artifacts?scope=&scope_id=`
5. `GET /api/artifacts/{artifact_id}`
6. `GET /api/artifacts/{artifact_id}/content`
7. `DELETE /api/media/{media_item_id}`

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
  "transcript_language": "fr",
  "idempotency_key": "mobile-share-4b7e8d",
  "folder_id": "folder_01JQ8X8J5S3H3CXX8V70M9M3K7",
  "tag_ids": ["tag_01JQ8X8J5S3H3CXX8V70M9M3K7"]
}
```

`transcript_language`, `folder_id`, and `tag_ids` are optional. When `folder_id` is omitted or `null`,
the backend assigns the user's default Uncategorized folder. Provided folder and
tag IDs must belong to the authenticated user.

`transcript_language` is a **per-submission override**. When omitted, the backend defaults to the
authenticated user's `reading_language` preference (set during onboarding, editable in Settings via
`PATCH /api/auth/me`). Clients should therefore send it only when the user explicitly wants a
different language for this one item (e.g. keeping an English video's original transcript while
their reading language is French). The value is normalized to a bare lowercase ISO 639-1 code
(`"fr-FR"` → `"fr"`) and travels to the ingestion worker, which asks the transcript provider for
that language. If the video has no captions in that language, the provider returns its default
track and the downstream translation step brings the transcript back to the user's
`reading_language`.

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
    "title": "LE MEILLEUR DE BOUVARD - La blague de Carlos",
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
  }
}
```

`media_item.title` is the `title` attribute of the durable `user_media` row, i.e. the exact value
`GET /api/media` returns for the same item — the detail header and the list vignette read one field,
not two. It is nullable (a row whose metadata has not resolved yet has none); clients degrade to the
source URL, never to a URL path segment, which used to surface raw provider ids such as a Spotify
episode id as a title.

### 3) POST /api/artifacts

Request:
```json
{
  "scope": "folder",
  "scope_id": "c4ef2e55-8449-4a71-be46-bcf1a6eeca3e",
  "artifact_type": "summary_detailed",
  "parameters": {
    "language": "fr"
  }
}
```

`202` when a generation was queued, `200` when the response is an entry that
already existed. Response is the shape of `GET /api/artifacts/{artifact_id}` plus
`generation_outcome`, which names the four cases the caller must be able to tell
apart:

| `generation_outcome` | Status | Meaning | Quota |
|---|---|---|---|
| `created` | `202` | First request for this source set: entry written and queued | debited |
| `retried` | `202` | The entry for this key had `failed`, so it is reclaimed and queued again | debited (idempotent on `artifact_id`, so a retry of the same id charges nothing extra) |
| `reused` | `200` | An artifact already covers this source set; nothing is queued | untouched |
| `collapsed` | `200` | A concurrent identical request won the conditional write; this one hands back the winner | untouched |

`reused` and `collapsed` are deliberately distinct: the first says "this content
was already generated, possibly days ago", the second says "this was the same
tap". Both leave every quota counter untouched, and both are logged under their
own event (`artifact.reused`, `artifact.collapsed`).

Typed refusals:

| Situation | Status | `error_code` | Retryable |
|---|---|---|---|
| No source with a usable transcript | `422` | `scope_empty` | no |
| More than 25 sources, or more than 120 000 estimated tokens | `422` | `scope_too_large` | no |
| A source is still being transcribed or translated | `409` | `sources_not_ready` | **yes, as-is** |
| Every source lost its translation permanently | `409` | `translation_failed` | no, not until the provider works again |
| Out of minutes (collection scope only) | `403` | `out_of_minutes` | next period, or on upgrade |
| Artifact type disabled | `400` | — | no |
| Generation disabled globally | `503` | — | no |

`scope_too_large` carries the four numbers the client displays, so it computes
nothing: `source_count`, `max_sources`, `estimated_tokens`, `max_tokens`.
`sources_not_ready` carries `pending_count` and `pending_titles`; the call that
returned it has already kicked off the missing translations, so retrying it
unchanged is the remedy.

The two `409`s are the same status and the opposite instruction, so both carry a
`terminal` boolean — `false` on `sources_not_ready`, `true` on
`translation_failed` — and a client decides whether to keep polling from that flag
alone. `translation_failed` carries `failed_count` and `failed_titles`, and means
the LLM provider refused the translation for a reason a retry cannot change (no
credit left, a rejected key, an unknown model): the sources were excluded from the
corpus with `excluded_reason: "translation_failed"`, and here there was nothing
left. A source that keeps a usable transcript in another language is not refused —
it is dropped from the corpus and recorded in the snapshot, and the generation
runs on the rest. The lock behind it stops being terminal after an hour, so the
refusal lifts on its own once the provider answers again (task-327).

A generation over a **single item** is free — its LLM cost is already inside what
the item cost to ingest — so `out_of_minutes` can only ever come back on
`scope=folder`, where the cost scales with the sources behind it (one minute per
five sources). Its `message` names the figures and the app shows it verbatim.

### 4) GET /api/artifacts?scope=&scope_id=

A scope's whole history, **newest first, all types mixed**, several entries of the
same type included. This is also the progress endpoint: in-flight entries appear
with `queued` or `generating`, so a client polls once per scope and never once per
artifact type.

```json
{
  "scope": "folder",
  "scope_id": "c4ef2e55-8449-4a71-be46-bcf1a6eeca3e",
  "artifacts": [
    {
      "artifact_id": "art_9f3c...",
      "artifact_type": "summary_detailed",
      "status": "ready",
      "title": "Les limites du scaling",
      "source_count": 7,
      "created_at": "2026-08-17T09:12:44Z",
      "completed_at": "2026-08-17T09:13:31Z",
      "error_code": null
    },
    {
      "artifact_id": "art_1b70...",
      "artifact_type": "quiz",
      "status": "generating",
      "title": null,
      "source_count": 7,
      "created_at": "2026-08-17T09:12:44Z",
      "completed_at": null,
      "error_code": null
    }
  ],
  "next_cursor": null
}
```

These are exactly the attributes the `scope-index` GSI projects: a page costs one
DynamoDB query, with no read of the base table and no S3 access. `title` is
emitted by the model, which is what tells two entries of the same type apart.
`sources` is **not** in this response — it is only returned when one entry is
opened.

### 5) GET /api/artifacts/{artifact_id}

The same fields plus the scope and the immutable source snapshot:

```json
{
  "artifact_id": "art_9f3c...",
  "artifact_type": "summary_detailed",
  "status": "ready",
  "title": "Les limites du scaling",
  "source_count": 7,
  "created_at": "2026-08-17T09:12:44Z",
  "completed_at": "2026-08-17T09:13:31Z",
  "error_code": null,
  "scope": "folder",
  "scope_id": "c4ef2e55-8449-4a71-be46-bcf1a6eeca3e",
  "sources": [
    {
      "media_item_id": "med_01JQ8X8J...",
      "title": "Scaling laws revisited",
      "language": "fr",
      "excluded": false,
      "excluded_reason": null
    }
  ],
  "s3_key": "summary_detailed/art_9f3c....json"
}
```

A source with `excluded: true` was in the scope but carried no usable transcript:
it is recorded rather than dropped, so the entry stays honest about what it could
not read. The snapshot describes the scope **at generation time** — it is expected
to diverge from the collection's current contents, and that divergence is the
history rather than a defect.

### 6) GET /api/artifacts/{artifact_id}/content

The stored JSON payload, inlined. `409` while the entry is not `ready`, as a typed
refusal whose `error_code` — never the message text — says whether the entry is
still coming (task-328):

```json
{
  "detail": {
    "error_code": "artifact_not_ready",
    "message": "Artifact is still being generated (status: generating). Try again once generation completes.",
    "status": "generating"
  }
}
```

```json
{
  "detail": {
    "error_code": "artifact_failed",
    "message": "Artifact generation failed and will not resume on its own. Request a new generation for this scope and type.",
    "status": "failed",
    "artifact_error_code": "LLM_ERROR",
    "scope": "media",
    "scope_id": "med_01JQ8X8J5S3H3CXX8V70M9M3K7",
    "artifact_type": "notes"
  }
}
```

`artifact_not_ready` resolves on its own, so a client may come back to it.
`artifact_failed` is **terminal**: no worker will pick the entry up again, and a
client that keeps polling it polls forever. The refusal therefore carries the
`scope`, `scope_id` and `artifact_type` a new generation needs, so a failure state
can offer `POST /api/artifacts` without a second round-trip — that request reruns
the entry under its own id (`generation_outcome: "retried"`) and debits nothing
extra.

```json
{
  "artifact_id": "art_01JQ8ZNOTES...",
  "artifact_type": "notes",
  "scope": "media",
  "scope_id": "med_01JQ8X8J5S3H3CXX8V70M9M3K7",
  "status": "ready",
  "content": {
    "artifact_id": "art_01JQ8ZNOTES...",
    "artifact_type": "notes",
    "scope": "media",
    "scope_id": "med_01JQ8X8J5S3H3CXX8V70M9M3K7",
    "generated_at": "2026-02-24T20:37:10Z",
    "source_count": 1,
    "sources": [
      {
        "media_item_id": "med_01JQ8X8J5S3H3CXX8V70M9M3K7",
        "title": "LE MEILLEUR DE BOUVARD",
        "language": "fr",
        "transcript_s3_key": "job_01JQ8X8J5T9Q5V7Q4TW4N1HY03.txt"
      }
    ],
    "generator_version": "notes:gpt-5.4-nano-2026-03-17:prompt-v4",
    "llm_usage": {
      "prompt_tokens": 4622,
      "cached_tokens": 0,
      "completion_tokens": 1200,
      "cost_eur": 0.0016
    },
    "content": {
      "title": "...",
      "objectives": ["..."],
      "concepts": [
        {
          "term": "...",
          "explanation": "...",
          "importance": "core"
        }
      ],
      "key_points": ["..."],
      "action_items": ["..."],
      "glossary": [
        {
          "term": "...",
          "definition": "..."
        }
      ]
    }
  }
}
```

Every content schema carries a `title` (3-80 characters) emitted by the model.
`summary_detailed.notable_quotes` is a list of `{text, source_ref}` where
`source_ref` is **required** — a quote is verbatim, so its origin is checkable.
Flashcards and quiz questions carry an **optional** `source_ref`, null when the
entry draws on several sources. `source_ref` is the corpus tag (`"[S2]"`), which
the client resolves through the index in `sources`; the model is never asked to
write a media id.

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

### 6) DELETE /api/media/{media_item_id}

No request body.

Response (`DeleteMediaResponse`):
```json
{
  "status": "success",
  "media_item_id": "mi_9f2c1d0b7a4e5f6081c2d3e4f5a6b7c8",
  "deleted_at": "2026-08-13T09:41:02+00:00",
  "purge_at": 1758620462,
  "grace_days": 30
}
```

Semantics (task-243, §6.2 of the task-218 benchmark):
- the item leaves every read surface immediately: library reads skip soft-deleted rows and the search records are deleted synchronously
- `purge_at` is epoch seconds; after it, the row and its search records are destroyed
  irreversibly by the lifecycle worker; content-scoped artifacts and processing
  objects survive while another retained save row still references the same `media_key`
- inside the grace window a deletion is recoverable by support (clear `deleted_at`/`purge_at`)
- idempotent: deleting an already-deleted item returns `200` with the original `purge_at`, never `404`, and never pushes the purge date out
- re-ingesting the same URL creates a separate visible save with a new `media_item_id`;
  it does not revive or mutate the soft-deleted row
- `media_item_id` in the response is the same durable library id supplied in the path
- unknown or foreign id returns `404 MEDIA_NOT_FOUND`
- this is the only endpoint in the system allowed to schedule a library row for purge; retention rules are in `docs/DATA_RETENTION.md`

## Multipart upload entrypoints (non-canonical, same organization contract)

Two ingestion entrypoints take bytes instead of a URL. They are **not** part of the six canonical
endpoints above and have their own compact response shape, but since task-264 they accept the same
organization fields as `POST /api/media/ingest-url` and `POST /api/media/ingest-shared-content`.
There is one dialect for "where does this save go", implemented once in
`_resolve_media_organization` (`media_summarizer/api/endpoints/media.py`) and shared by all four.

### POST /api/media/upload

`multipart/form-data`:

| Part | Type | Required | Notes |
| --- | --- | --- | --- |
| `file` | file | yes | Extension must be in `DocumentFormat.supported_extensions()`: `pdf`, `docx`, `pptx`, `xlsx`, `jpg`, `jpeg`, `png`, `tiff`, `tif`, `bmp`, `heif`, `heic`. Images go through OCR. |
| `folder_id` | text | no | Destination collection. Omitted or empty means the user's default Uncategorized folder. |
| `tag_ids` | text | no | JSON array of strings, e.g. `["tag_01JQ...","tag_01JR..."]`. Multipart has no native array type, so the array travels encoded. |

Response (`UploadDocumentResponse`, `202 Accepted`):
```json
{
  "media_item_id": "med_01JQ8X8J5S3H3CXX8V70M9M3K7",
  "status": "processing",
  "source_platform": "document",
  "file_name": "invoice-2026-03.pdf"
}
```

### POST /api/media/upload-audio

`multipart/form-data`:

| Part | Type | Required | Notes |
| --- | --- | --- | --- |
| `file` | file | yes | Extension must be one of `.mp3`, `.m4a`, `.aac`, `.ogg`, `.wav`, `.flac`, `.opus`. Transcribed by Deepgram. |
| `folder_id` | text | no | Same semantics as above. |
| `tag_ids` | text | no | Same semantics as above. |

Response (`UploadAudioResponse`, `202 Accepted`):
```json
{
  "media_item_id": "med_01JQ8X8J5S3H3CXX8V70M9M3K7",
  "status": "processing",
  "source_platform": "audio"
}
```

### Shared semantics

- `folder_id` and `tag_ids` are validated against the caller **before** the quota check, so an
  unusable folder or tag costs nothing to the user's allowance. An id that does not exist or belongs
  to someone else is `400 Folder not found` / `400 Tag(s) not found`, and more than
  `MAX_TAGS_PER_MEDIA` distinct tags is `400` — identical wording and status to `ingest-url`.
- A malformed `tag_ids` (not valid JSON, or valid JSON that is not an array) is `400`; duplicates are
  collapsed.
- Both fields land on the durable library row through `save_media_for_user`, never on the processing
  job — organization belongs to what the user saved, not to the pipeline working for it.
- Rejections that do not depend on the file's content are stable: unsupported extension `400`, empty
  file `400`, over `MAX_UPLOAD_SIZE_BYTES` `413`. Clients are expected to enforce the extension list
  and the size ceiling locally so a refusal costs no upload.
- A consumption refusal carries the `X-Quota-Error-Code` header (`out_of_minutes` or
  `item_too_long`), exactly like the URL and shared-content entrypoints.
- The library row stores `media_type` `document` / `audio`, which the list endpoint returns as-is;
  `GET /api/media/{media_item_id}` normalizes them to the canonical `article` / `audio_file`.

## Domain enums (locked)

`MediaItem`:
- `status`: `ingested | resolving | processing | ready_for_artifacts | failed | cancelled`
- `transcript.status`: `pending | extracting | transcribing | ready | failed`

`MediaArtifact`:
- `scope`: `media | folder` (a folder is what the UI calls a collection)
- `artifact_type`: `summary_short | summary_detailed | notes | quiz | flashcards`
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
- Processing is idempotent for equivalent normalized URLs; saving is intentionally
  non-idempotent and creates a fresh library row on every successful request.
- Artifact creation generates **only** when `(user, scope, scope_id, artifact_type, parameters, sorted source ids)` has no entry yet, or when the entry it has is `failed`. Any other identical request — a double tap or one months later — returns the stored entry, with no new generation and no quota movement. The storage stays an append-only history: a *different* source set writes a new entry next to the older ones, and no request is ever refused for already existing.
- Timestamps use ISO-8601 UTC strings.
- `request_id` must be returned in error payload and response header.

## Relationship to existing runtime APIs

Current runtime still exposes legacy paths:
- `/api/podcast-search/*`
- `/api/jobs/*`

These legacy paths are not the canonical target contract and must not drive new mobile share-first implementation once canonical endpoints are implemented. As of 2026-08-18 neither has a single caller left in `mobile/` — the constraint has held, and what remains is backend surface nothing consumes. `/api/episodes/my-episodes` was listed here too and no longer exists; its router is not mounted.

The paths named above carry no active mobile callers and exist only to prevent breaking pre-existing API integrations (unlikely given zero shipped clients). Whether they should exist at all is out of scope of this API harmonization; that is a separate product decision.
