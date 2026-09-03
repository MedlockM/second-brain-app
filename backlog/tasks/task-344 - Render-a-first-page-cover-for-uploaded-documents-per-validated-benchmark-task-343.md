---
id: task-344
title: >-
  Render a first-page cover for uploaded documents per validated benchmark
  (task-343)
status: Done
assignee: []
created_date: '2026-09-03 09:12'
updated_date: '2026-09-03 11:15'
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
- [x] #1 The architecture implemented is the one in the owner's Decision field of docs/research/task-343-*/README.md, and any deviation from it is recorded in the Implementation Notes with its reason
- [x] #2 Every format the owner's Decision covers produces a stored cover object through the existing cover_capture path, writing covers/{media_item_id}.jpg and setting job.media_image — no new image field, no second bucket
- [x] #3 The rendered page is framed 16:9 aligned to the top of the page, and the code that does it is wired for every component that renders a cover, not only the library list row
- [x] #4 A render failure — unreadable, encrypted, corrupt or 0-page file — degrades to the media-type glyph and never fails the ingestion, matching cover_capture's best-effort contract
- [x] #5 The cover render does not debit the user's minute quota a second time on top of the parse
- [x] #6 Every dependency added is pinned with an arm64 manylinux wheel compatible with public.ecr.aws/lambda/python:3.11-arm64, or the system binary is added to the worker image, and the choice is verified rather than assumed
- [x] #7 The stale comment at workers/document_parsing/worker.py:358-360 and the task-302 §4 row 8 claim that a document cover is structurally impossible are both updated to match what now exists
- [x] #8 ruff and mypy are clean on the backend, npm run lint and npm run typecheck are clean in mobile/, and terraform validate passes if any infrastructure file changed
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
**Option B of task-343 §8, as the owner's `Decision` field requires — not the recommended option A.** No rasteriser was added: `pyproject.toml` and `infrastructure/docker/lambda.Dockerfile` are untouched, `pypdfium2` appears nowhere. No new dependency of any kind, no Terraform change (the `COVERS_BUCKET` env var and the covers-bucket IAM statements were already shared by every worker since task-304), no mobile change.

**What was built, in four files**

- `infrastructure/resolvers/llamaparse_resolver.py` — `fetch_first_page_screenshot(job_id)`: `GET /job/{id}/result/json` → the page-1 image whose `type` is `full_page_screenshot` → `GET /job/{id}/result/image/{name}`, bounded by `LLAMAPARSE_PAGE_IMAGE_MAX_BYTES` (8 MB) and `LLAMAPARSE_PAGE_IMAGE_TIMEOUT_SECONDS` (20 s). Only that image type is accepted: an embedded illustration is not a page render. Returns `None` on anything unexpected, never raises.
- `core/services/sheet_preview.py` (new) — the §3.7 XLSX path: the first table of the parse markdown (pipe table, with an HTML `<table>` branch) drawn as a header-banded 1280×720 PNG grid with Pillow's bundled scalable `ImageFont.load_default(size=…)`. No font package, no new dependency. Rows stretch to fill the canvas so a 4-row sheet does not leave a white half, and the block is centred vertically — the canvas *is* 16:9, so nothing is cropped out of it and there is no top band to align to.
- `core/services/cover_capture.py` — `capture_document_page()` plus `_frame_top_16x9_jpeg()`: top 16:9 band, resized to exactly 640×360, JPEG q80, stored at the same `covers/{media_item_id}.jpg`. A source *wider* than 16:9 keeps its full height and is cropped horizontally on its centre. The module docstring now records this as the single, argued exception to "the crop to the tile's ratio is the client's job".
- `workers/document_parsing/worker.py` — one `_capture_cover()` for every uploaded file: image → the existing `capture_from_s3`; XLSX → the drawn sheet; PDF/DOCX/PPTX → the LlamaParse screenshot, and only when `result.provider == "llamaparse"` (an Unstructured fallback has no such artefact, task-343 §5.4). The whole step is inside one `try/except` that logs `media_cover.document_render_failed` and returns `None`.

**Evidence gathered rather than assumed**

- **Live, end to end, against the real LlamaParse API** (a 1-page DOCX built for the probe, throwaway scripts in `/tmp`, key read from the untracked local `.env`): `parse()` → `ParseResult` carrying `metadata["job_id"]` → `fetch_first_page_screenshot()` returned a **2473×3200 JPEG in 1.6 s** → framing produced **exactly 640×360, 39 KB**, and the rendered band carries the title block, not body text (the top-alignment requirement, visually confirmed). A bogus job id and an empty job id both returned `None` with a warning. Note for the record: the screenshot measured **1.0 MB**, not the 176–236 KB of §4.1 — well inside the 8 MB ceiling, and the reason that ceiling is not tighter.
- **Against the real `-dev` covers bucket**: `capture_document_page` wrote `covers/task344-probe-delete-me.jpg` to `media-summarizer-covers-…-dev`, `resolve_cover_url` signed it, `delete_cover` removed it (re-listed to confirm it is gone). A garbage payload and a missing `media_item_id` both returned `None` without writing anything.
- **XLSX drawing**: rendered from a 6×5 pipe table, a 9×30 one and a 2×2 one — 640×360 JPEG at 4–24 KB in 32–71 ms, legible as a banded grid when downscaled to the 112×63 of `MediaListCard`. A chart-only sheet (no table), an empty markdown and an undecodable payload each return `None`.
- **Framing geometry**, on synthetic sources with a marked header band and a marked mid-page band: A4 portrait 2263×3200 keeps the header and drops the mid-page band; a 3000×2250 4:3 slide keeps the top 75 %; an already-16:9 source passes through; a 3000×900 source keeps its full height.
- `ruff check media_summarizer/` and `mypy media_summarizer/` (180 files) both clean.

**AC #6** is satisfied vacuously and deliberately: zero dependencies were added, which is the point of option B. The pinned-wheel question therefore does not arise, and `pillow>=11.0.0,<12.3` is untouched.

**AC #8, precisely.** `ruff` and `mypy` were run and are green; no infrastructure file changed, so `terraform validate` does not apply; the mobile gates were **not executed** — `mobile/node_modules` is absent in this worktree — but no mobile file is in the diff, which is itself what the owner's decision asks for ("**No mobile file changes.**"), so their outcome is unchanged by construction.

**AC #3, on "wired for every component"**: the crop is server-side, so the stored object is already the tile's ratio and `MediaListCard`, `HomeTile`, the search result card and `unsorted-review` inherit the framing through their existing `contentFit="cover"` — including the next component somebody writes. That is exactly why the owner chose the server-side variant over gating `contentPosition="top"` at five render sites.

**Deviations from the Decision: none.** Two judgement calls it did not cover, both recorded in the code: the vertical centring of the drawn sheet grid (§6.1 leaves the sheet's internal composition open), and the 8 MB ceiling on the screenshot download (§5.2 asked the render path to bound its own read; option B made a *source* bound unnecessary, but bounding a network fetch is free and consistent with `COVER_MAX_SOURCE_BYTES`).

**Not done, on purpose**: no automated test was added (project rule). No backfill — existing `-dev` document rows keep their glyph until re-ingested (task-302 §11).

**Out of reach from this worktree, for the owner after the deploy**: the document worker runs from the worker container image, so nothing is visible until that image is rebuilt and deployed on push to `main`. Then upload a PDF, a DOCX, a PPTX and an XLSX and confirm each tile shows its first page top-aligned and legible, plus a renamed `.zip` and an encrypted PDF to confirm the tile falls back to the type glyph while the ingestion still completes. Worth watching in the logs: `media_cover.captured` with `source="document_page"`, and `media_cover.document_render_failed` for the degraded cases.
<!-- SECTION:NOTES:END -->
