---
id: task-343
title: >-
  Benchmark first-page rendering for uploaded documents on the arm64 AL2 Lambda
  image
status: To Do
assignee: []
created_date: '2026-09-03 09:12'
updated_date: '2026-09-03 10:42'
labels:
  - benchmark
  - ingestion
  - backend
  - phase-6
dependencies: []
priority: high
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
An uploaded document shows no cover in the library: the tile falls back to the media-type glyph with a paperclip. The owner asked on 2026-09-03 for the first page of the document instead, as Apple's Files app renders it.

## This reverses a validated decision — read why before re-arguing it

`docs/research/task-302-media-cover-and-creator/README.md` **§11 Rejected alternatives** rejects exactly this feature:

> **A PDF first-page thumbnail for documents** — Needs a rasteriser (PyMuPDF or Poppler) in the Lambda image, and produces a grey rectangle of text that identifies nothing. The type icon carries more information at a glance.

That decision was validated by the owner and shipped; the code carries its trace at `media_summarizer/workers/document_parsing/worker.py:358-360` — « A PDF or a DOCX gets no cover: `ParseResult` carries no image and there is no page rasteriser in this runtime. » §4 row 8 of the same README calls the cover "structurally impossible" for this source.

**The owner overrode the product half of that reasoning on 2026-09-03, on visual evidence**: in Apple's Files app a passport, a carte Vitale, a driving licence and a dark-blue branded cover page are each identifiable at thumbnail size. "A grey rectangle of text" is false as a general claim. This benchmark therefore does **not** re-litigate whether the feature is worth having — it is wanted. It answers *how*, under a runtime constraint the original rejection named but did not cost out.

## Already decided by the owner — do not re-open

1. **Every uploaded document format is in scope, without exception**: PDF, DOCX, PPTX, XLSX. A recommendation that covers PDF and leaves Office documents on the glyph does not satisfy the ask. If Office rendering turns out to be disproportionately expensive, say so with numbers and propose how to pay for it — do not silently narrow the scope.
2. **The framing is 16:9, aligned to the top of the page.** The owner settled this on 2026-09-03: an A4 portrait page centre-cropped to 16:9 keeps only a horizontal middle band and drops the header, logo and title — which is what makes the documents recognisable in the Files screenshot, and what would have vindicated §11. The tile ratio itself stays 16:9 (task-302 §6.4, still valid: a ragged column is rejected). What is open is only *where* the top-aligned crop is applied, which is question 3 below.

## What this benchmark must answer

**1. How to render page 1 of each format, against the actual runtime.** The worker image is `public.ecr.aws/lambda/python:3.11-arm64` — Amazon Linux 2, glibc 2.26, arm64. This is not a footnote: it is why `task-304` reached `main` without ever running in a Lambda, documented at `pyproject.toml:41-48` (Pillow 12.3 drops the `manylinux_2_17_aarch64` wheel, uv falls back to a 47 MB sdist, the build dies on missing libjpeg headers). Any candidate must be qualified against that image, not against a developer laptop. State for each: wheel availability for `manylinux_2_17_aarch64`, or the binary that has to be baked into the image and its size.

Candidates to cover at minimum — add others if they exist:

| Candidate | Points to verify |
|---|---|
| `pypdfium2` | arm64 manylinux wheel, licence (Apache-2.0 / BSD-3), image size delta, PDF only |
| `PyMuPDF` | **AGPL-3.0** — qualify the licence for a commercial closed-source app before anything else, then the wheel |
| `pdf2image` + Poppler | Poppler is a system binary: size added to the image, and whether AL2 arm64 packages exist |
| LibreOffice headless | The only Python-free path to Office rendering. Image weight, cold start, whether it fits a Lambda at all versus needing another compute shape |
| LlamaParse page images | **Already paid for on this path.** The parse is already billed per page (`workers/document_parsing/worker.py:301-308`); if the API can return a page render, Office comes free of new infrastructure. Verify against the live API, not the docs alone |
| A third-party thumbnailing service | Only if the above fail. Cost at the pricing-benchmark volumes |

Note the asymmetry to resolve: PDF has several viable Python-only answers; DOCX/PPTX/XLSX have essentially none. The recommendation may well be **two mechanisms**, and that is an acceptable outcome if argued.

**2. Where the render runs, and what it costs.** The natural insertion point is `workers/document_parsing/worker.py:347-367`, where the image branch already calls `cover_capture.capture_from_s3` — the file is already in the `documents` bucket, nothing is fetched from a third party. Say whether the render fits inside that worker's existing budget (memory ceiling, timeout, cold start) or needs a separate step, and what a document costs in added seconds and euros. State explicitly whether this touches the user's minute quota: the parse already debits 1 minute per 5 pages (`pricing_config_service.py`, `document_pages_per_minute`) and a cover must not add a second debit.

**3. Where the top-aligned crop is applied.** Two candidates, pick one and justify it:
- **Server side**, in `cover_capture`: crop the page to 16:9 from the top before storing. Contradicts task-302's stated principle that "the crop to the tile's ratio is the client's job … which keeps this side free of any layout decision" (`core/services/cover_capture.py:14-18`), so if this wins, say why the principle should yield.
- **Client side**, via `expo-image`'s `contentPosition` — confirmed present in the installed expo-image 55.0.11 (`build/Image.types.d.ts:150`) — conditioned on the document media type. Keeps the stored derivative neutral and is reversible, at the cost of a per-type branch in `MediaListCard` and every other tile that renders a cover (`ArtifactTile`, `HomeTile`, the search result card).

Whichever wins, state what the stored derivative looks like: `COVER_MAX_EDGE` is 640 on both edges (`cover_capture.py:51`), so a portrait A4 page stores as roughly 452×640.

**4. The degraded state.** `cover_capture` is best-effort by contract — "a timeout, a 404, an unreadable payload or a missing bucket must degrade to *this tile shows its media-type icon*, never to a failed ingestion" (`cover_capture.py:9-13`). Confirm the render obeys the same rule, and name what happens to an encrypted PDF, a corrupt file, a 0-page document and a 200-page one.

**5. A single recommendation**, stated as what the owner would be validating, with the cost and effort comparison behind it.

## Owner note

Existing `-dev` rows will not gain a cover retroactively — zero users, zero production data (`AGENTS.md`). Re-ingest or leave them, as task-302 §11 already settled for backfills.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 docs/research/task-343-<short-description>/README.md exists with owner_decision: pending in its front-matter and an Owner Validation section whose Decision and Validated at fields are empty
- [ ] #2 Every candidate is qualified against public.ecr.aws/lambda/python:3.11-arm64 specifically — arm64 manylinux wheel availability or the system binary and its size — with the task-304 Pillow failure named as the precedent
- [ ] #3 PDF and Office (DOCX, PPTX, XLSX) rendering are each answered; if the recommendation uses two mechanisms or leaves a format uncovered, the reason is argued with numbers rather than asserted
- [ ] #4 The LlamaParse page-image option is verified against the live API rather than assumed from documentation, since the parse is already billed on this path
- [ ] #5 The README states where the render runs, its added latency and cost per document, and whether it debits the user's minute quota a second time
- [ ] #6 The top-aligned 16:9 crop is placed either server-side or client-side with a stated reason, including what the stored derivative looks like at COVER_MAX_EDGE 640
- [ ] #7 The degraded path is specified for a render failure, an encrypted PDF, a corrupt file and a 0-page document, and it never fails the ingestion
- [ ] #8 A cost and effort comparison of the candidate options ends in a single recommendation stated as what the owner would be validating
- [ ] #9 No production code, contract or Terraform file is modified by this task
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
**Mode: initial** (no `docs/research/task-343-*` directory existed, so this is a first pass — not a redo, not a complement).

Deliverable: `docs/research/task-343-document-page-render/README.md`, `owner_decision: pending`, `Decision` and `Validated at` left empty for the owner. No production code, contract, Terraform file, `pyproject.toml`, Dockerfile or mobile component was touched (AC #9).

What the benchmark establishes, and how it was verified:

- **The runtime gate** (AC #2). glibc 2.26 read from the Amazon Linux 2 **aarch64** core repo index rather than asserted; the task-304 Pillow failure at `pyproject.toml:41-48` is named as the precedent and its mechanism (silent `uv` sdist fallback) is what the verification method is built to catch. The host has no arm64 emulation available, so nothing was executed on aarch64 — stated explicitly in §1.2 — and three static checks were used instead: platform-targeted `uv pip compile --python-platform aarch64-manylinux_2_17 --only-binary :all:`, `readelf` inspection of the shipped `.so` (machine, `NEEDED`, versioned GLIBC symbols), and AL2 aarch64 repo metadata for anything that would be `yum install`ed.
- **PDF**: `pypdfium2` 5.13.0 clears the gate — `manylinux_2_17_aarch64` wheel (3.5 MiB / 8.3 MiB unpacked), bundled `libpdfium.so` is AArch64 and references `GLIBC_2.17` only, no `libstdc++`, no fontconfig, `py3-none` tag, BSD-3/Apache-2.0, same tag on all 12 releases from 5.4.0. Page 1 renders in 3–6 ms independently of page count, peak RSS 41 MiB.
- **PyMuPDF rejected twice**: AGPL-3.0-or-Artifex-commercial for a closed-source app, and from 1.26.3 its only aarch64 wheel is `manylinux_2_28` — the task-304 trap reproduced live (unconstrained resolution picks 1.28.2 as an 83.8 MiB sdist; `--only-binary` backs off to 1.26.0).
- **Poppler** exists for AL2 aarch64 but at **0.26.5 (2014)** and needs a subprocess plus a font package; **LibreOffice does not exist at all** on this platform (zero `libreoffice*` packages in the repo index) and the reference Lambda base image is **x86_64-only at 877 MB**.
- **LlamaParse verified against the live API** (AC #4), not the docs: with the exact fields `llamaparse_resolver._upload_file` sends today and **no** screenshot flag, a DOCX job returns `pages[0].images[0] = {"name": "page_1.jpg", "type": "full_page_screenshot", 2263×3200}` and the image GET answers HTTP 200 `image/jpeg` 236 KB; PPTX likewise at 3000×2250 / 176 KB on the resolver's own base URL. **XLSX returns zero images in four configurations** (v1 default, `premium_mode`, `parse_mode=parse_page_with_agent`, and v2 `tier=agentic` with `images_to_save=["screenshot"]` + `save_output_pdf=true`), which the live OpenAPI schema and the per-sheet pricing corroborate.
- **All four formats answered** (AC #3): PDF locally, DOCX/PPTX from the already-billed parse, and for XLSX a measured Pillow-drawn first-sheet preview (29 ms, 9.8 KB, no new dependency) with the two priced ways to buy a genuine print-layout page instead (877 MB x86_64 LibreOffice, or ~$1/month of conversion API at launch volume).
- **Where it runs, cost, quota** (AC #5): the existing branch at `worker.py:347-367`, inside the 512 MB / 600 s budget, +$0.003 per 1,000 PDFs and +$0.011 per 1,000 Office documents at the `eu-west-3` arm64 rate; **no second minute debit** — the single debit stays at `worker.py:200` with its job-keyed idempotency token.
- **Framing** (AC #6): server-side top-16:9 crop in `cover_capture`, stored 640×360 JPEG q80 (measured 17.8–44.4 KB), which keeps the mobile app unchanged; the client-side `contentPosition` alternative is compared and rejected with the five render sites it would have to touch.
- **Degraded path** (AC #7): a table of ten exercised cases — encrypted, corrupt, truncated, empty, zip-renamed, 0-page, 200-page, failed screenshot GET, Unstructured fallback, missing Pillow — all returning `None` to the media-type glyph, none failing an ingestion or triggering an SQS retry.
- **Single recommendation** (AC #8): option A of a six-row cost/effort comparison, with options B and E named as the owner's alternatives.

Three open questions are listed in §9 for the owner to settle in the `Decision` field (XLSX treatment, whether uploaded photos should adopt the same top framing, and the no-backfill confirmation).

**The recommendation awaits the owner's validation.** The task stays `To Do` and the README front-matter stays `owner_decision: pending`; implementation is task-344, which must follow whatever the owner writes in the `Decision` field.
<!-- SECTION:NOTES:END -->
