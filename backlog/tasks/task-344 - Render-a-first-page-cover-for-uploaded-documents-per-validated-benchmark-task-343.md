---
id: task-344
title: >-
  Render a first-page cover for uploaded documents per validated benchmark
  (task-343)
status: To Do
assignee: []
created_date: '2026-09-03 09:12'
updated_date: '2026-09-03 09:12'
labels:
  - ingestion
  - backend
  - mobile
  - phase-6
dependencies:
  - task-343
priority: high
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Give every uploaded document a cover showing its first page, instead of the media-type glyph it falls back to today.

**Read `docs/research/task-343-*/README.md` first, and follow the owner's `Decision` field under `Owner Validation`** — including any complement files it references. The owner's decision may differ from the benchmark's initial recommendation; the README is authoritative, this description is not. Do not pick a rasteriser, a render location or a crop strategy from what is written below.

## What is fixed regardless of the benchmark's outcome

Two things were settled by the owner on 2026-09-03, before the benchmark ran, and the README's decision is expected to respect them:

- **All formats**: PDF, DOCX, PPTX, XLSX. Leaving Office documents on the glyph does not close this task unless the owner's `Decision` explicitly says so.
- **16:9 tile, cropped to the top of the page**, not centred — a centre crop of a portrait page drops the header, logo and title.

## Where this lands in the existing code

The plumbing from `task-304` is already in place and must be reused rather than duplicated:

- `media_summarizer/workers/document_parsing/worker.py:347-367` — the branch that already writes a cover for image formats by calling `cover_capture.capture_from_s3` on the object the user uploaded. The comment at `:358-360` states the current absence and is now stale.
- `media_summarizer/core/services/cover_capture.py` — the shared fetch → downscale → PUT helper, `covers/{media_item_id}.jpg`, best-effort by contract (`:9-13`): a failure degrades to the type icon and never fails an ingestion.
- `job.media_image` → mirrored onto the durable row by `durable_media_service.mirror_job` via the `("media_image", "thumbnail_url")` pair, returned by the list endpoint as `media_image`, read by `mobile/src/components/MediaListCard.tsx:100`. No schema change and no new field: task-302 §11 rejects a second image field beside `thumbnail_url`.
- If the crop is applied client-side, every component that renders a cover needs it, not just the list row: `MediaListCard`, `ArtifactTile`, `HomeTile`, and the search result card that shares `MediaListCard`'s cover.

Mind the runtime the benchmark had to work against: the worker image is `public.ecr.aws/lambda/python:3.11-arm64` (Amazon Linux 2, glibc 2.26, arm64). A dependency without an arm64 `manylinux_2_17` wheel silently falls back to an sdist and dies at build time — `pyproject.toml:41-48` records how that shipped `task-304` to `main` without it ever running in a Lambda.

## Owner notes — not acceptance criteria

- **A deploy is required before anything is visible.** The document parsing worker runs from the worker container image; the code path cannot be exercised until the image is rebuilt and deployed, which happens on push to `main`.
- **Owner check after that deploy**: upload a PDF, a DOCX, a PPTX and an XLSX from the app, then confirm in the inbox that each tile shows its first page, top-aligned and legible at tile size. Then a deliberately broken file (a renamed `.zip`, an encrypted PDF) to confirm the tile degrades to the type glyph and the ingestion still completes.
- The existing `-dev` rows keep their glyph — no backfill (task-302 §11).
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 The architecture implemented is the one in the owner's Decision field of docs/research/task-343-*/README.md, and any deviation from it is recorded in the Implementation Notes with its reason
- [ ] #2 Every format the owner's Decision covers produces a stored cover object through the existing cover_capture path, writing covers/{media_item_id}.jpg and setting job.media_image — no new image field, no second bucket
- [ ] #3 The rendered page is framed 16:9 aligned to the top of the page, and the code that does it is wired for every component that renders a cover, not only the library list row
- [ ] #4 A render failure — unreadable, encrypted, corrupt or 0-page file — degrades to the media-type glyph and never fails the ingestion, matching cover_capture's best-effort contract
- [ ] #5 The cover render does not debit the user's minute quota a second time on top of the parse
- [ ] #6 Every dependency added is pinned with an arm64 manylinux wheel compatible with public.ecr.aws/lambda/python:3.11-arm64, or the system binary is added to the worker image, and the choice is verified rather than assumed
- [ ] #7 The stale comment at workers/document_parsing/worker.py:358-360 and the task-302 §4 row 8 claim that a document cover is structurally impossible are both updated to match what now exists
- [ ] #8 ruff and mypy are clean on the backend, npm run lint and npm run typecheck are clean in mobile/, and terraform validate passes if any infrastructure file changed
<!-- AC:END -->
