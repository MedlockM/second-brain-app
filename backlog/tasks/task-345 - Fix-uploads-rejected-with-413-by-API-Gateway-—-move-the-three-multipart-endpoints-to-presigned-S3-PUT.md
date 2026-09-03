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
- [ ] #1 No route in `media_summarizer/api/endpoints/media.py` declares an `UploadFile`/`File(...)` parameter any more: `POST /api/media/upload`, `POST /api/media/upload-audio` and `POST /api/media/ingest-shared-content` receive an S3 key instead of the bytes, so no binary transits through the API.
- [ ] #2 An endpoint issues a presigned S3 PUT URL for each of the three flows, on the `bug_reports.py` pattern: the key is namespaced under the caller's user id, and the URL is produced by `s3_utils.generate_presigned_url(..., http_method="PUT")`.
- [ ] #3 A client-supplied S3 key that does not start with the caller's user id is refused `403` before any S3 read, and a key whose object is absent from the bucket is refused with a 4xx that names the missing upload — both checked in the same helper, for all three flows.
- [ ] #4 `MAX_UPLOAD_SIZE_BYTES` (`media_summarizer/api/endpoints/media.py`) and `MAX_UPLOAD_SIZE_BYTES` (`mobile/src/types/upload.ts`) hold the same value, and that value is enforced when the presigned URL is requested rather than after the bytes have moved.
- [ ] #5 The mobile upload path (`mobile/src/services/uploadService.ts`, `mobile/src/contexts/ShareIntentContext.tsx`) requests a URL, PUTs the file straight to S3, then calls the ingestion endpoint with the returned key — `apiUpload` is no longer used to carry file bytes.
- [ ] #6 A failure of the direct-to-S3 PUT surfaces a translated message from `mobile/src/i18n`, not a raw provider or gateway string; no user-facing path can render `Request Entity Too Large`.
- [ ] #7 `ruff check media_summarizer` and `mypy media_summarizer` are clean, and `npx tsc --noEmit` in `mobile/` reports no error.
- [ ] #8 A presigned PUT generated against the real `-dev` document bucket accepts an object larger than 6 MiB, verified with the AWS CLI, and the resulting object is readable by `head_object` — proving the payload ceiling is gone from the upload path.
- [ ] #9 `docs/CANONICAL_MEDIA_API_CONTRACT.md` describes the presigned flow for the three endpoints, states the real size ceiling, and no longer claims the removed `413`-on-body behaviour; `docs/CANONICAL_MEDIA_API_OPENAPI.yaml` matches.
- [ ] #10 The document parsing, audio transcription and shared-content workers still read their input from the same bucket and key shape they read today, or the change to that shape is applied in the workers in the same run.
<!-- AC:END -->
