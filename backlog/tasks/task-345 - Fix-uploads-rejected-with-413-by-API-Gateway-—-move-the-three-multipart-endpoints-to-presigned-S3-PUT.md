---
id: task-345
title: >-
  Fix uploads rejected with 413 by API Gateway — move the three multipart
  endpoints to presigned S3 PUT
status: To Do
assignee: []
created_date: '2026-09-03 09:27'
labels:
  - bug
  - mobile
  - ingestion
dependencies: []
priority: high
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
## Problem

Saving a file from the mobile app fails as soon as the file is bigger than **~4.5 MiB**. The owner hit it on 2026-09-03 with a `.docx`: two `POST /api/media/upload` attempts at 09:15:21 and 09:16:15 UTC were answered `413 {"message":"Request Entity Too Large"}` by **API Gateway itself**, with `errorResponseType: REQUEST_TOO_LARGE` in the access log of `/aws/lambda/media-summarizer-api-dev` and **no matching `START RequestId`** in the Lambda stream. The request never reached FastAPI, so there is no application log, no `media.upload.failed` event, and nothing the backend can shape into a usable message.

The ceiling is not `.docx`-specific and not adjustable. It is Lambda's **6 MiB synchronous invocation payload limit**: API Gateway base64-encodes the binary body into the Lambda event, so a raw HTTP body of `6 MiB × 3/4 = 4 718 592 bytes` is the hard wall, multipart envelope and headers included. Measured on dev against the real gateway (unauthenticated probe — the size refusal happens before auth, so nothing was written):

| Raw body | Result |
|---|---|
| 4 715 000 bytes | `401` — reaches the app |
| 4 718 592 bytes (4.5 MiB) | `413 Request Entity Too Large` |
| 6 / 9 / 11 MiB | `413` |

**All three endpoints that carry binary in the request body are capped identically** (each verified by probing dev with a 6 MiB body — all three answered `413`):

- `POST /api/media/upload` — advertises `MAX_UPLOAD_SIZE_BYTES` = 50 MB
- `POST /api/media/upload-audio` — same constant, 50 MB
- `POST /api/media/ingest-shared-content` — `MAX_SHARED_AUDIO_SIZE_BYTES` = 25 MB

Those three ceilings are fiction: the code that enforces them (`media_summarizer/api/endpoints/media.py:921`, `:1113`, `:1438`) is unreachable above 4.5 MiB. The mobile guard `MAX_UPLOAD_SIZE_BYTES` in `mobile/src/types/upload.ts:85` advertises 50 MB too, so it lets through everything that is about to be refused. Audio is the worst hit: an MP3 at 128 kbps crosses the wall at **~4 min 55 s**.

What the user sees is the gateway's own body. `parseErrorResponse` (`mobile/src/lib/httpError.ts:83-88`) reads `data.message`, and API Gateway's error payload has exactly that shape, so the untranslated English string `Request Entity Too Large` lands in the error banner of the share confirmation screen.

This was anticipated and never verified: `docs/research/task-105-lambda-migration/README.md:477` lists the risk verbatim ("File upload > 6MB request body"), assumes presigned URLs are already the flow, and asks to "verify this is the current flow for document ingestion. If direct upload to API exists, refactor to presigned URL pattern."

## What to build

Move the three endpoints to the presigned-PUT flow **already implemented in this repo** for bug report attachments — `media_summarizer/api/endpoints/bug_reports.py`, whose module docstring states the invariant to reproduce: *"Upload: presigned PUT URL — binary never transits through this API."* Read that file first; it is the reference, not an inspiration:

- `POST /api/bug-reports/upload-url` (`:116-176`) validates size, extension and content type, then presigns a PUT on a key namespaced `{user_id}/{uuid}/{filename}` via `s3_utils.generate_presigned_url(..., http_method="PUT")` (`media_summarizer/utils/s3.py:354`).
- The submit endpoint then receives only the S3 key, and `_validate_attachment` (`:223`) re-checks it server-side: **the key must start with `{user_id}/`** (otherwise `403`), the extension must be allowed, and a `head_object` must confirm the object exists and carries an acceptable content type.

That ownership-prefix check is not optional. A client-supplied S3 key without it lets any authenticated user ingest another user's object.

The size ceilings should become truthful rather than decorative: the value the API refuses on and the value the mobile app refuses on must be the same number, and that number must actually be reachable.

## Notes for the owner (not acceptance criteria)

- The fix only becomes real once `main` is pushed and the API Lambda image is redeployed. The implementing agent cannot deploy.
- The proof that matters is your own manual E2E run afterwards: one `.docx` well over 5 MB, and one MP3 longer than 5 minutes. Both should reach `processing` in the library instead of erroring at Save.
- `docs/CANONICAL_MEDIA_API_CONTRACT.md:564-565` documents the current `413` semantics of `/api/media/upload` and will need to match whatever contract lands.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 No route in `media_summarizer/api/endpoints/media.py` declares an `UploadFile`/`File(...)` parameter any more: `POST /api/media/upload`, `POST /api/media/upload-audio` and `POST /api/media/ingest-shared-content` receive an S3 key instead of the bytes, so no binary transits through the API.
- [x] #2 An endpoint issues a presigned S3 PUT URL for each of the three flows, on the `bug_reports.py` pattern: the key is namespaced under the caller's user id, and the URL is produced by `s3_utils.generate_presigned_url(..., http_method="PUT")`.
- [x] #3 A client-supplied S3 key that does not start with the caller's user id is refused `403` before any S3 read, and a key whose object is absent from the bucket is refused with a 4xx that names the missing upload — both checked in the same helper, for all three flows.
- [x] #4 `MAX_UPLOAD_SIZE_BYTES` (`media_summarizer/api/endpoints/media.py`) and `MAX_UPLOAD_SIZE_BYTES` (`mobile/src/types/upload.ts`) hold the same value, and that value is enforced when the presigned URL is requested rather than after the bytes have moved.
- [x] #5 The mobile upload path (`mobile/src/services/uploadService.ts`, `mobile/src/contexts/ShareIntentContext.tsx`) requests a URL, PUTs the file straight to S3, then calls the ingestion endpoint with the returned key — `apiUpload` is no longer used to carry file bytes.
- [x] #6 A failure of the direct-to-S3 PUT surfaces a translated message from `mobile/src/i18n`, not a raw provider or gateway string; no user-facing path can render `Request Entity Too Large`.
- [x] #7 `ruff check media_summarizer` and `mypy media_summarizer` are clean, and `npx tsc --noEmit` in `mobile/` reports no error.
- [x] #8 A presigned PUT generated against the real `-dev` document bucket accepts an object larger than 6 MiB, verified with the AWS CLI, and the resulting object is readable by `head_object` — proving the payload ceiling is gone from the upload path.
- [x] #9 `docs/CANONICAL_MEDIA_API_CONTRACT.md` describes the presigned flow for the three endpoints, states the real size ceiling, and no longer claims the removed `413`-on-body behaviour; `docs/CANONICAL_MEDIA_API_OPENAPI.yaml` matches.
- [x] #10 The document parsing, audio transcription and shared-content workers still read their input from the same bucket and key shape they read today, or the change to that shape is applied in the workers in the same run.
<!-- AC:END -->

## Implementation Notes
<!-- SECTION:NOTES:BEGIN -->
All 10 acceptance criteria are met. No binary reaches the API any more, on any route.

### The new flow

`POST /api/media/upload-url` is the single presigning endpoint for the three
entrypoints, discriminated by `target` (`document` / `audio` / `shared_audio`).
It validates the extension (or the MIME type, for `shared_audio`, whose format
check has always been MIME-based) and the declared `file_size` against that
target's ceiling **before signing anything**, then returns a presigned PUT on

    uploads/{user_id}/{uuid4hex}/{filename}

One directory per request, so two uploads of the same file name never collide
and no object can be reached by guessing a file name. The client PUTs the raw
bytes to that URL — no form encoding, no `Authorization` header, the signature
is in the query string — and submits `upload_key` as a small JSON field.

`_resolve_staged_upload` is the single helper the three ingestion endpoints call.
Its first statement is the ownership gate, decided on the string alone:

    if not key.startswith(f"{UPLOAD_STAGING_PREFIX}/{user_id}/"):
        raise HTTPException(403, "This upload does not belong to you.")

so a forged key costs zero S3 calls. Only then does it `head_object`, which
yields the four facts the API used to read from the bytes it no longer sees:
exact size (`ContentLength`), MIME type (`ContentType`), the content
fingerprint (`ETag`), and — for audio — a duration probed over a presigned GET.
A missing object is `422 "No uploaded file found at '<key>'. Send the file to
the presigned URL before submitting it."`, which also covers a replayed key,
since the staged object is consumed by the submission that accepts it.

### Why a staging prefix and a server-side copy, not a direct write

The obvious design — sign the PUT straight at the canonical key — breaks
deletion. `media_purge_service` and `workers/cleanup/media_lifecycle.py` sweep
by job id (`purge_job_objects(content_job_id)`) and know nothing else, so an
object living under a user-scoped key would be orphaned in S3 forever. So the
upload lands in `uploads/`, and `_promote_staged_upload` runs an in-S3
`CopyObject` to the key the rest of the system already expects, then deletes the
staged copy:

| Flow | Canonical key (unchanged) |
|---|---|
| document | `{job_id}/{file_name}` in the documents bucket |
| audio | `{job_id}.{ext}` in the audio bucket |
| shared audio | `shared-audio/{user_id}/{content_hash}.{ext}` in the audio bucket |

That is what makes AC#10 true with **zero worker changes**: the document
parsing, transcription and shared-content workers read the same bucket and the
same key shape as before. Abandoned staged objects are collected by a new
lifecycle rule (`expire-abandoned-upload-staging`, prefix `uploads/`, 1 day)
added on both buckets in `modules/platform/s3.tf`.

### Two facts recovered without the bytes

- **Content hash for shared-audio dedup.** The in-API sha256 is gone; the S3
  `ETag` replaces it. Verified on the real dev bucket: a single-part PUT under
  SSE-S3 (`AES256`) returns a plain MD5 ETag, which is a stable fingerprint of
  the object and feeds `_share_locator` → `generate_media_key` exactly as the
  sha256 did.
- **Audio duration before the quota debit.** `probe_duration_seconds_from_bytes`
  is replaced by `probe_duration_seconds_from_url`: at most 3 HTTP Range
  requests over a short-lived presigned GET, a 5 s budget, `None` on failure.
  The pre-storage quota check is byte-for-byte the same decision as before.

`tag_ids` is now a real JSON array instead of a comma-joined form field, so
`_parse_form_tag_ids` is deleted.

### AC#8 — verified against the real dev bucket

The URL was produced by the API's own code path
(`s3.generate_presigned_url(..., http_method="PUT")`, SigV4), the transfer by
`curl -X PUT`, the read-back by the AWS CLI:

    local bytes: 8388608
    curl PUT http=200 sent=8388608
    aws s3api head-object --bucket media-summarizer-documents-125313707865-dev ...
    { "ContentLength": 8388608, "ContentType": "application/pdf",
      "ETag": "\"4390eab7...\"", "SSE": "AES256" }

8 388 608 bytes is 1.78× the 4 718 592-byte gateway wall this task exists to
escape, and the Content-Type survives the transfer, which is what the ingestion
endpoint reads back. The probe object was deleted afterwards.

No IAM change was needed: the API Lambda role already holds
`s3:GetObject`/`PutObject`/`DeleteObject` on both buckets. No CORS change
either — React Native's `fetch` is not a browser and sends no preflight.

### Mobile

`mobile/src/services/presignedUpload.ts` (new) holds the whole direct-upload
step: `stageUpload({target, uri, fileName, mimeType, size})` presigns, reads the
local file as a blob and PUTs it, returning the `upload_key`. Both failure modes
throw `DirectUploadError`, whose message is already
`t("upload.transferFailed")`. That type exists because
`getFriendlyErrorMessage` deliberately collapses anything matching
`/aws|s3|lambda|cloudfront|dynamodb/i` into a generic fallback — a real S3
failure would be swallowed — so `toSubmissionError` in `ShareIntentContext`
matches `DirectUploadError` first and passes its message through verbatim. All
three submission paths go through that function, so no flow can surface a raw
provider string; and since every API request body is now small JSON, API
Gateway can no longer produce `Request Entity Too Large` at all (AC#6).

`apiUpload` is deleted from `apiClient.ts` and `FormData` no longer appears
anywhere under `mobile/src` or `mobile/app`. No npm dependency was added: the
blob-PUT pattern is the one already used by `bugReportService.ts`.

### Checks run

`ruff check media_summarizer` clean · `mypy media_summarizer` clean (178 files)
· `npx tsc --noEmit` clean · `eslint` clean on the 7 touched mobile files ·
`terraform fmt -check -recursive` clean · `terraform validate` on `envs/dev`
Success. The OpenAPI file was parsed and every `$ref` resolved, with no orphan
schema or response component.

### Left to the owner

- **Deploy.** The fix is inert until `main` is pushed and the API Lambda image is
  rebuilt; the new `uploads/` lifecycle rules need `terraform apply` on dev.
- **The E2E run that proves it.** One `.docx` well over 5 MB and one MP3 longer
  than 5 minutes, both expected to reach `processing` in the library. Per repo
  policy no automated test was written for any of this.
<!-- SECTION:NOTES:END -->
