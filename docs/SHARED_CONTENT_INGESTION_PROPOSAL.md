# Shared Content Ingestion Proposal

Status: proposed for `task-61` on 2026-03-20

Related tasks:
- `task-37` Android share intake
- `task-38` iOS share extension intake
- `task-39` share-first inbox/detail screens
- `task-61` WhatsApp shared text and audio ingestion

## Why this proposal exists

The active canonical ingestion runtime is URL-first:
- `POST /api/media/ingest-url`
- resolver routing based on canonical HTTP(S) URL classification
- direct audio path assumes a remote `audio_url`

WhatsApp share flows break that assumption:
- a forwarded text message may contain plain text, not a URL
- a forwarded audio message is shared as local content from the mobile OS, not as a public remote URL

For this reason, WhatsApp support should not be implemented as a new URL resolver alone. The clean extension point is a second canonical ingestion entrypoint for shared content.

## Goals

1. Accept shared text and shared audio from mobile share entrypoints.
2. Reuse existing media item, processing job, transcript, artifact, and inbox semantics.
3. Keep the existing frozen URL-ingestion contract intact.
4. Minimize runtime churn by reusing Deepgram and current processing job infrastructure.

## Non-goals

1. Replacing `POST /api/media/ingest-url`
2. Renaming existing frozen URL models in the same task
3. Generalizing every future shared-content source beyond the minimal WhatsApp-first shape

## Proposed canonical endpoint

Add a second authenticated endpoint:

- `POST /api/media/ingest-shared-content`

This endpoint is canonical for non-URL share payloads received by the mobile app.

## Request contract

Use `multipart/form-data` so the same endpoint can handle both text and audio shares.

### Fields

- `share_type`: required, enum `text | audio`
- `source_platform`: required, enum initially `whatsapp`
- `source_app`: optional, example `android.share_sheet` or `ios.share_extension`
- `locale`: optional
- `idempotency_key`: optional
- `text`: required when `share_type=text`
- `audio_file`: required when `share_type=audio`
- `content_mime_type`: optional but recommended
- `original_name`: optional
- `content_size_bytes`: optional

### Validation rules

- exactly one payload family is allowed per request
- `text` shares must provide non-empty `text`
- `audio` shares must provide a non-empty file and an accepted audio MIME family
- if both `text` and `audio_file` are provided, reject with `BAD_REQUEST`
- oversized payloads reject with `VALIDATION_ERROR`
- unsupported MIME types reject with `BAD_REQUEST`

### Example: WhatsApp text share

```http
POST /api/media/ingest-shared-content
Content-Type: multipart/form-data
Authorization: Bearer <token>
```

Form fields:

```text
share_type=text
source_platform=whatsapp
source_app=android.share_sheet
locale=fr-FR
idempotency_key=wa-text-9d6d6e
text=Je te transfere ce vocal demain matin.
```

### Example: WhatsApp audio share

```http
POST /api/media/ingest-shared-content
Content-Type: multipart/form-data
Authorization: Bearer <token>
```

Form fields:

```text
share_type=audio
source_platform=whatsapp
source_app=ios.share_extension
locale=fr-FR
idempotency_key=wa-audio-3bd31a
content_mime_type=audio/mp4
original_name=PTT-20260320-WA0001.m4a
```

File part:

```text
audio_file=<binary>
```

## Response contract

Return the existing ingestion response shape unchanged:

- `IngestUrlResponse`

This keeps inbox/detail clients on the same response model already defined by:
- `media_summarizer/api/models/media_contracts.py`
- `front/src/types/media.ts`

### Important compatibility note

For shared-content ingestion, `media_item.original_url` and `media_item.normalized_url` remain populated even though the source is not an HTTP URL.

For task-61, they should carry deterministic opaque locators:
- text: `share://whatsapp/text/<content-hash>`
- audio: `share://whatsapp/audio/<content-hash>`

This is intentionally pragmatic. It avoids widening every existing contract in the same task while still keeping:
- deterministic `media_key`
- deduplication
- a stable locator value for status reads

A future cleanup task can rename URL-centric fields into more general `source_locator` names once more than one non-URL source exists.

## Proposed public contract additions

The smallest coherent additions are:

### Backend and frontend enums

- `SourcePlatform.WHATSAPP = "whatsapp"`
- `MediaFamily.TEXT = "text"`
- `MediaType.SHARED_TEXT = "shared_text"`

No new artifact or transcript statuses are required.

### New request model

```python
class SharedContentType(str, Enum):
    TEXT = "text"
    AUDIO = "audio"


class IngestSharedContentRequest(BaseModel):
    share_type: SharedContentType
    source_platform: SourcePlatform
    source_app: Optional[str] = None
    locale: Optional[str] = None
    idempotency_key: Optional[str] = None
    text: Optional[str] = None
    content_mime_type: Optional[str] = None
    original_name: Optional[str] = None
    content_size_bytes: Optional[int] = Field(default=None, ge=0)
```

The file itself is carried by multipart form-data and should not be embedded into the Pydantic contract model.

## Minimal domain diff

The current domain already contains one useful field:
- `ResolvedMedia.raw_text`

The minimal changes are:

### 1. Add shared-content request types

```python
@dataclass(frozen=True)
class IngestSharedContentRequest:
    share_type: SharedContentType
    source_platform: SourcePlatform
    source_app: Optional[str] = None
    locale: Optional[str] = None
    idempotency_key: Optional[str] = None
    text: Optional[str] = None
    content_mime_type: Optional[str] = None
    original_name: Optional[str] = None
    content_size_bytes: Optional[int] = None
    staged_audio_s3_key: Optional[str] = None


@dataclass(frozen=True)
class IngestSharedContentCommand:
    user: UserContext
    request: IngestSharedContentRequest
```

`staged_audio_s3_key` is the key design choice here. The API adapter stages uploaded audio before handing control to the core. This avoids passing raw bytes through the core.

### 2. Extend `ResolvedMedia`

Add one field:

```python
audio_s3_key: Optional[str] = None
```

Resulting semantics:
- `audio_url`: remote HTTP(S) audio already supported today
- `audio_s3_key`: internal uploaded/staged audio for Deepgram file-based transcription
- `raw_text`: text content that can become transcript text directly

### 3. Add shared-content use-case

Do not overload `IngestUrlUseCase`.

Add a sibling use-case:
- `IngestSharedContentUseCase`

This keeps URL classification separate from shared-content handling and avoids inventing fake HTTP URLs at the router boundary.

## Proposed backend execution path

### Text share

1. Mobile submits `share_type=text` with `text`
2. API builds a deterministic content hash from normalized text plus `source_platform`
3. API generates:
   - `media_key`
   - `original_url = share://whatsapp/text/<hash>`
   - `normalized_url = share://whatsapp/text/<hash>`
4. Use-case returns `ResolvedMedia` with:
   - `media_family=text`
   - `media_type=shared_text`
   - `source_platform=whatsapp`
   - `raw_text=<submitted text>`
5. Orchestrator creates `ProcessingJob`
6. Instead of enqueueing download/transcription, orchestrator uploads transcript text directly to transcript storage and marks the job `ready_for_artifacts`

### Audio share

1. Mobile submits `share_type=audio` with `audio_file`
2. API validates MIME family and file size
3. API computes a content hash from file bytes plus `source_platform`
4. API uploads the file to S3 staging or directly to the audio bucket
5. API generates:
   - `media_key`
   - `original_url = share://whatsapp/audio/<hash>`
   - `normalized_url = share://whatsapp/audio/<hash>`
6. Use-case returns `ResolvedMedia` with:
   - `media_family=audio`
   - `media_type=audio_file`
   - `source_platform=whatsapp`
   - `audio_s3_key=<uploaded key>`
7. Orchestrator enqueues Deepgram with `audio_s3_key`
8. Deepgram worker downloads the S3 object and calls Deepgram using file-bytes mode instead of remote URL mode

## Minimal orchestrator changes

Current priority order is effectively:
- `audio_url`
- X article path
- article extraction
- TikTok worker
- YouTube worker
- podcast resolution worker

Extend it to:
- `raw_text`
- `audio_s3_key`
- `audio_url`
- existing branch order

### `raw_text` branch

- upload transcript text to transcript bucket
- persist `transcription_s3_key`
- persist `transcription_metadata.provider = "shared_text"`
- publish success completion event immediately

### `audio_s3_key` branch

- enqueue `deepgram-transcription-queue` with `audio_s3_key`
- keep the rest of the job lifecycle identical to the current transcription path

## Minimal Deepgram worker changes

Today the active worker only accepts remote URLs.

Add a second path:

- if message has `audio_s3_key`:
  - download bytes from S3
  - determine MIME type from stored metadata or original name
  - call Deepgram file-bytes mode
- else:
  - keep current `audio_url` path unchanged

This reuses the same queue and completion flow and avoids introducing a second transcription worker.

## Mobile payload mapping

### Android

Expected OS-level share patterns:
- text shares via `ACTION_SEND` with `text/plain`
- binary shares via `ACTION_SEND` with `EXTRA_STREAM` and MIME type

Mobile handler mapping:
- `contentType=website` or `shareType=url` -> existing `POST /api/media/ingest-url`
- `contentType=text` -> `POST /api/media/ingest-shared-content` with `share_type=text`
- `contentType=audio` -> `POST /api/media/ingest-shared-content` with `share_type=audio`
- `contentType=file` and `contentMimeType` starts with `audio/` -> treat as `share_type=audio`

### iOS

Expected share extension payloads:
- text via activation rule `supportsText`
- files via activation rule `supportsFileWithMaxCount`

Mobile handler mapping is the same as Android.

### Runtime caveat

`expo-sharing` is currently documented by Expo as experimental for receiving shared content, and the iOS behavior is explicitly called out as not officially supported by Apple. `task-61` must therefore include real-device validation before implementation is considered stable.

## Why this is smaller than a generic "new resolver"

Adding a fake WhatsApp URL resolver would not solve:
- plain-text messages without URLs
- local audio files with no public URL
- file-backed transcription

The smallest clean boundary is:
- one new canonical endpoint
- one new shared-content use-case
- one new `audio_s3_key` branch in the existing transcription pipeline

## Recommended implementation sequence

1. Mobile intake:
   - extend `task-37` and `task-38` implementation scope in `task-61` work to map text/audio payloads
2. Backend contracts:
   - add `IngestSharedContentRequest`
   - add endpoint `POST /api/media/ingest-shared-content`
3. Domain:
   - add `SourcePlatform.WHATSAPP`
   - add `MediaFamily.TEXT`
   - add `MediaType.SHARED_TEXT`
   - add `audio_s3_key` to `ResolvedMedia`
   - add shared-content command/use-case
4. Orchestration:
   - implement `raw_text` completion path
   - implement `audio_s3_key` enqueue path
5. Transcription:
   - extend Deepgram worker to accept staged S3 audio files
6. Validation:
   - capture real payload metadata from WhatsApp text and audio shares on Android and iOS

## Open questions to resolve on real devices

1. Whether WhatsApp audio arrives as `audio/mp4`, `audio/aac`, `audio/ogg`, or another MIME type on Android
2. Whether iOS delivers the WhatsApp audio share as `contentType=audio` or generic `file`
3. Whether WhatsApp text shares ever contain both text and attachment in one share action for the targeted user flow
4. Exact maximum accepted file size for first release

## References

- Current frozen URL contract:
  - `docs/CANONICAL_MEDIA_API_CONTRACT.md`
  - `docs/CANONICAL_MEDIA_API_OPENAPI.yaml`
- Relevant runtime code:
  - `media_summarizer/core/media_ingestion/domain.py`
  - `media_summarizer/core/media_ingestion/adapters/orchestrators.py`
  - `media_summarizer/core/media_ingestion/adapters/resolvers.py`
  - `media_summarizer/workers/transcription/deepgram_worker.py`
- External references used for this proposal:
  - Expo Sharing docs
  - Android sharing docs
  - Apple app extension activation keys
  - Deepgram pre-recorded audio docs
