---
id: task-142
title: Add audio file upload endpoint and pipeline (MP3/M4A/WAV) from mobile app
status: To Do
assignee: []
created_date: '2026-06-09 18:50'
labels:
  - feature
  - backend
  - infrastructure
  - ingestion
dependencies: []
priority: high
dispatchable: true
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
## Context

The V1 launch plan §0 lists "Audio file (upload direct) | OK" as a supported source. The expected user flow is: user picks an audio file (MP3, M4A, WAV, etc.) from their iOS Files / Android Files picker → uploads to the backend → backend transcribes via Deepgram → artifacts can be generated.

**Discovery 2026-06-09**: this flow is **not actually implemented** in the backend. The codebase has:

- `POST /api/media/ingest-url` — accepts a URL pointing to an audio file (e.g. `https://example.com/podcast.mp3`). Routes to Deepgram via URL mode.
- `POST /api/media/upload` — multipart upload, but **only accepts PDF/DOCX/PPTX** (`DocumentFormat.supported_extensions()` in `media_summarizer/core/ports/document_parser.py:53`).
- No `POST /api/media/upload-audio` endpoint or equivalent.

The URL mode has limitations:
- The user needs the audio to be already hosted somewhere with a public URL
- Deepgram fetches the URL from its own servers — many podcast hosts and CDNs (TikTok, etc.) block cloud SaaS IPs and return 403 (cf. task-139)

So a real user who picks an audio file from their phone has no working flow today.

## Goal

Add an audio file upload pipeline that mirrors the document upload pattern but routes to the Deepgram worker instead of LlamaParse, with audio files stored in the existing `audio` S3 bucket.

## Architecture

User flow:

1. Mobile app file picker (iOS Files / Android Storage Access Framework) → user selects audio file
2. Mobile uploads file as `multipart/form-data` to `POST /api/media/upload-audio`
3. Backend validates extension (must be in `_AUDIO_EXTENSIONS`), reads bytes, uploads to S3 `audio` bucket (key like `<media_item_id>.<ext>`)
4. Backend creates a `ProcessingJob` (status `pending`), allocates minute pool hold
5. Backend generates a pre-signed S3 GET URL (~10 min validity, default 600s)
6. Backend enqueues message in `deepgram-transcription-queue` with the **pre-signed S3 URL** as `audio_url`
7. Deepgram fetches from S3 (S3 doesn't block cloud IPs), transcribes, stores transcript in `transcripts` bucket
8. Downstream artifact pipeline triggered on demand

Why pre-signed S3 URL rather than push-mode binary upload to Deepgram? Pre-signed URLs are zero new code (we already have the audio in S3), avoid loading large audio files into the Lambda's memory, and bypass the cloud-IP block at the source platform level. Push-mode would be needed if Deepgram couldn't fetch S3 either, which is not the case.

## Backend changes

1. **New endpoint** `POST /api/media/upload-audio` in `media_summarizer/api/endpoints/media.py`:
   - Accepts `UploadFile = File(...)` plus optional `tag_ids` JSON body
   - Validates file extension against `_AUDIO_EXTENSIONS` (already defined in the module)
   - Reads bytes, checks `len(content) <= MAX_UPLOAD_SIZE_BYTES`
   - Creates a `ProcessingJob` with `source_platform="audio"`
   - Uploads to S3 `audio` bucket with key `<job_id>.<ext>`
   - Generates pre-signed S3 GET URL (~10 min)
   - Enqueues to `DEEPGRAM_TRANSCRIPTION_QUEUE` with the pre-signed URL
   - Returns `202 + {media_item_id, status: "pending"}`

2. **Quota enforcement**: same pattern as `/upload` (call `check_submission_allowed(source_platform="audio", duration_seconds=0)`).

3. **Reuse existing S3 helpers** in `media_summarizer/utils/s3.py`. If a `presigned_url_for_get` helper doesn't exist, add one (boto3's `client.generate_presigned_url("get_object", ...)`).

4. **Reuse existing minute pool allocation** like `/upload` does.

5. **No new SQS queue** — use the existing `deepgram-transcription-queue`.

6. **No new IAM** — Lambda API role already has `s3:PutObject` and `sqs:SendMessage` on these resources.

## Mobile-side stub (out of scope for THIS task)

The mobile app changes (adding a file picker button on the inbox screen) are **out of scope** for task-142. Track in a separate mobile task once backend is ready.

## E2E test

Add `test_audio_upload` to `tests/e2e/test_phase4_other_sources.py`:

- Local MP3 fixture in `tests/e2e/fixtures/sample.mp3`
- Multipart POST to `/api/media/upload-audio`
- Polls until `completed`
- Asserts transcript exists in S3

Fixture: a short (~5–10s) public-domain spoken-word MP3, embedded in the repo so the test is fully self-contained. Suggestion: use the existing LibriVox `count_of_monte_cristo_001_dumas_64kb.mp3` snippet but trimmed to first 5 seconds (~50KB), or generate a synthetic TTS audio at test setup time.

## Constraints

- Multipart upload size limit: respect existing `MAX_UPLOAD_SIZE_BYTES` (likely 100 MB; verify before building UX expectations).
- Deepgram 60-min hard limit per request: V1 minute pool already enforces this via tier caps; just propagate `audio_duration_seconds` once known.
- The audio S3 bucket lifecycle policy should clean up uploads older than X days for free tier users (out of scope; existing lifecycle on `archives` bucket may already cover, verify).

## Out of scope

- Mobile app UI changes (separate task)
- Audio format conversion (Deepgram supports the common formats natively)
- Streaming transcription (Deepgram websocket) — V1 uses batch
- Direct push-mode binary upload to Deepgram — pre-signed S3 URL is simpler and sufficient

## References

- V1 launch plan §0 ("Audio file (upload direct) | OK" — currently inaccurate)
- `media_summarizer/api/endpoints/media.py:406` (existing `/upload` for documents — reference pattern)
- `media_summarizer/api/endpoints/media.py:43` (`_AUDIO_EXTENSIONS` already defined)
- `media_summarizer/api/endpoints/podcasts.py:230-240` (existing flow that enqueues Deepgram from a direct audio URL — different pattern, no S3 upload)
- `media_summarizer/utils/s3.py` (existing S3 helpers)
- `media_summarizer/utils/sqs.py` (existing SQS helpers)
- `tests/e2e/test_phase4_other_sources.py::test_podcast_via_direct_audio_url` (existing test that hits the Deepgram URL-mode path; this new test exercises the upload-then-S3-pre-signed-URL path)
- `tests/e2e/test_phase4_other_sources.py::test_document_upload` (reference E2E pattern for multipart upload)
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 New endpoint `POST /api/media/upload-audio` implemented in `media_summarizer/api/endpoints/media.py` accepting MP3/M4A/AAC/OGG/WAV/FLAC/OPUS via multipart
- [ ] #2 Audio file uploaded to S3 `audio` bucket with key `<media_item_id>.<ext>`
- [ ] #3 Pre-signed S3 GET URL generated (10 min validity) and passed to the Deepgram worker via SQS
- [ ] #4 Quota enforcement applied (`source_platform="audio"`); minute pool hold allocated
- [ ] #5 Endpoint returns `202` with `{media_item_id, status: "pending", source_platform: "audio"}`
- [ ] #6 New E2E test `test_audio_upload` in `tests/e2e/test_phase4_other_sources.py` with a local fixture (`tests/e2e/fixtures/sample.mp3`) and reaches `completed` within 30s
- [ ] #7 No regression on the 10 already-passing tests
- [ ] #8 V1 launch plan §0 line "Audio file (upload direct) | OK" is genuinely true — confirmed by the new test passing
<!-- AC:END -->
