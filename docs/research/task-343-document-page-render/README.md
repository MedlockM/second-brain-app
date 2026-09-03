---
owner_decision: pending   # pending | ok | abandoned | redo | more
---

# Benchmark: first-page rendering for uploaded documents on the arm64 AL2 Lambda image

## Owner Validation

**Decision**: _(à remplir par l'owner après relecture)_
**Validated at**: _(date ISO à remplir par l'owner)_

---

## Recommendation

**Render page 1 inside the existing `document_parsing` worker, with two rasterisers and one shared framing step — and no new infrastructure, no new provider, no new secret, no second quota debit.**

| Format | Mechanism | Verified how | Added cost |
|---|---|---|---|
| **PDF** | `pypdfium2` 5.13.0 in the `worker` extra, rendered in-process | aarch64 wheel tag + ELF glibc symbols + `uv` resolution against the AL2 arm64 target | +3.5 MiB image (compressed), 3–6 ms/page |
| **DOCX, PPTX** | the `full_page_screenshot` **the current LlamaParse job already produces**, fetched with two extra GETs on the job the worker has just polled | live API calls with *exactly* the fields the resolver sends today | 0 credits, ~1.4–1.6 s wall time |
| **XLSX** | a synthesised first-sheet grid preview drawn from the parse output with Pillow | measured prototype, and 4 live LlamaParse configurations proving no provider on this path rasterises a spreadsheet | 29 ms, no dependency |
| **all three** | one shared framing helper: crop the render to its **top 16:9 band**, downscale to 640×360, JPEG q80, store at `covers/{media_item_id}.jpg` | measured on real files | 10–45 KB stored |

What the owner would be validating, in five statements:

1. **`pypdfium2` is the only PDF rasteriser that clears the runtime gate today.** Its wheel is `pypdfium2-5.13.0-py3-none-manylinux_2_17_aarch64.manylinux2014_aarch64.whl` — 3.5 MiB download, 8.3 MiB unpacked — and the `libpdfium.so` it bundles is AArch64, requires **`GLIBC_2.17` and nothing above it**, and links only `libc`, `libm`, `libpthread`, `libgcc_s` and `ld-linux-aarch64`. No `libstdc++`, no `libfontconfig`, no `yum install`, no compiler. The base image is glibc **2.26** (`glibc-2.26-64.amzn2.0.6` in the Amazon Linux 2 aarch64 core repo), so 2.17 clears it with nine minor versions of margin. The tag is `py3-none`: no CPython ABI coupling, so a future move to python 3.12/3.13 or to the AL2023 base cannot break it. Licence BSD-3-Clause / Apache-2.0 — no copyleft question. Every release from 5.4.0 to 5.13.0 carries the same aarch64 tag, so this is a stable property of the project and not a lucky snapshot.

2. **Office documents come free, from an artefact we are already paying for.** LlamaParse renders every page of a DOCX/PPTX to a JPEG and exposes it on the job we already poll. Verified live on 2026-09-03 against `https://api.cloud.llamaindex.ai/api/parsing` — the exact base URL in `llamaparse_resolver.py:34` — with the exact form fields of `_upload_file` (`result_type=markdown`, `language=en`, **no** screenshot flag): the DOCX job returned `pages[0].images = [{"name": "page_1.jpg", "type": "full_page_screenshot", "original_width": 2263, "original_height": 3200}]` and `GET …/job/{id}/result/image/page_1.jpg` answered **HTTP 200 `image/jpeg`, 236 KB**; the PPTX job returned the same shape at 3000×2250 and 176 KB. The screenshot therefore exists *before* we ask for anything: no new request parameter, no new credit line, no second parse. This also means the cover for Office documents is only as available as the primary parser — see the honest limitation in §5.4.

3. **XLSX is the one format nobody on this path renders, and buying a real render costs disproportionately more than drawing one.** Four live configurations (v1 default = the worker's own fields, v1 `premium_mode`, v1 `parse_mode=parse_page_with_agent`, v2 `tier=agentic` with `images_to_save=["screenshot"]` **and** `save_output_pdf=true`) all returned zero images for the same spreadsheet; the v2 schema says it outright for the PDF option — *"Not produced for spreadsheet, plain-text, or audio inputs"* — and the price list bills spreadsheets **per sheet, not per page**, which is the same fact stated in money: LlamaParse has no pagination model for a grid. Neither does pdfium, nor Poppler. The two ways to buy a genuine spreadsheet page are an 877 MB **x86_64-only** LibreOffice image (§3.4) or an external conversion API at ~$0.01–0.02 per file with a new provider, a new secret and a new failure mode — for the rarest of the four formats. The recommendation instead **draws the sheet**: parse the first table of the markdown the worker already has and render it as a 640×360 grid with Pillow's bundled scalable default font. Measured: **29 ms, 9.8 KB**, no new dependency, no font package. It is legible at tile size (§6.3) — arguably more legible than a real print-layout page 1, which is a printer-driven artefact that often shows a fragment of column headers.

4. **The 16:9 top crop is applied server-side**, in `cover_capture`, and the stored derivative becomes **640×360 JPEG q80** (measured 17.8 KB for a text page, 44.4 KB for a dense one). This yields on task-302's "the crop to the tile's ratio is the client's job" principle for one reason that does not generalise: for a re-hosted photo or an Instagram cover we are *re-framing someone else's image* and have no right to choose; for a document page **we author the image** — choosing which raster region to draw *is* the render, and there is no neutral original to preserve. The pay-off is that **not one line of mobile code changes**: a 16:9 derivative in a 16:9 box makes `contentFit="cover"` an exact fit, whereas the client-side option needs `contentPosition="top"` gated on media type at **5 `contentFit="cover"` render sites across 4 files** (`MediaListCard.tsx:138`, `HomeTile.tsx:188` and `:243`, `search.tsx:1054`, `unsorted-review.tsx:592`, plus the two component docstrings that state the invariant at `MediaListCard.tsx:27` and `HomeTile.tsx:22`), each of which silently regresses to a centre band the day someone adds a sixth.

5. **The cover is best-effort and never bills twice.** The quota is debited once, before the cover branch, by `_record_document_consumption` with `idempotency_token=quota_enforcer.gate_token(job_id)` (`worker.py:200-214`); the render adds no billed API call for PDF and XLSX and only reads results of an already-billed job for DOCX/PPTX, so **no second minute is debited and `document_pages_per_minute` is untouched**. Every failure path returns `None` and the tile falls back to its media-type glyph: an encrypted PDF, a corrupt file, a zero-page document, a `.pdf` that is really a zip, a 200-page scan and an unreachable screenshot were each exercised (§7).

**All-in cost.** Compute: ~0.2–0.5 s of extra worker wall time for a PDF and ~1.4–1.6 s for a DOCX/PPTX at 512 MB on arm64 in `eu-west-3` ($0.0000133334 per GB-s) = **$0.0000033 and $0.0000113 per document**, i.e. **$0.003 and $0.011 per thousand documents**. Storage: 10–45 KB per cover, inside the $0.04/month task-302 §5.4 already budgeted for the whole cover corpus at 100 users. Image: +3.5 MiB compressed on a worker image that is **391 MiB** in ECR today (+0.9 %), and +30 ms of one-off lazy import per warm container. **There is no meaningful euro cost. The cost of this feature is code, and the recommendation is the variant that writes the least of it while covering all four formats.**

---

## 1. The gate every candidate has to clear, and how it was checked

### 1.1 The runtime, stated precisely

`infrastructure/docker/lambda.Dockerfile:6` builds every worker `FROM public.ecr.aws/lambda/python:3.11-arm64`. That is **Amazon Linux 2 on aarch64**, and its glibc is **2.26** — read from the distribution's own repository metadata rather than from a blog post: `glibc-2.26-64.amzn2.0.6.aarch64` is the newest glibc in the AL2 aarch64 core repo (`http://amazonlinux.us-east-1.amazonaws.com/2/core/latest/aarch64/mirror.list` → `repodata/primary.xml.gz`). Under PEP 600 naming, a wheel tagged `manylinux_2_17_aarch64` (or its `manylinux2014_aarch64` alias) declares "glibc ≥ 2.17" and **installs**; a wheel tagged `manylinux_2_27_aarch64` or `manylinux_2_28_aarch64` declares "glibc ≥ 2.27 / 2.28" and is **invisible** to the resolver on this image.

The consequence is not theoretical, and this repository already carries the scar. `pyproject.toml:41-48` pins `pillow>=11.0.0,<12.3` with the failure written out: Pillow 12.3.0 is the first release to ship `manylinux_2_27+` only, uv then finds no compatible wheel, **falls back to the 47 MB sdist**, and the build dies on missing libjpeg headers — which is how task-304 reached `main` without ever running in a Lambda. The dangerous part of that sequence is the silence: `uv pip install` does not refuse an incompatible wheel, it quietly switches to source.

The Dockerfile makes one thing easier: it already runs `yum install -y gcc python3-devel libxml2-devel libxslt-devel`, so `libgcc_s.so.1` and a compiler are present in the image. That is *why* the sdist fallback gets far enough to fail on headers instead of failing fast, and it is also why the `libgcc_s` dependency of pdfium is a non-issue.

### 1.2 Verification method — and what could not be verified

The host has no arm64 emulation available (`docker run --platform linux/arm64 alpine uname -m` → `exec format error`: no `binfmt_misc` handler registered, and registering one requires a privileged container and changes host state). **No candidate was executed on aarch64 for this benchmark.** Rather than assert compatibility, three independent static checks were used, each of which would have caught the task-304 failure:

1. **Platform-targeted resolution.** `uv pip compile --python-platform aarch64-manylinux_2_17 --python-version 3.11 --only-binary :all:` — the `--only-binary` flag turns the silent sdist fallback into an error, and the explicit `aarch64-manylinux_2_17` target is required: the friendlier-looking `aarch64-unknown-linux-gnu` alias resolves to `aarch64-manylinux_2_28` in uv and *wrongly accepts* wheels this image cannot use.
2. **ELF inspection of the shipped binary.** Download the aarch64 wheel, unpack it, and read the native library's own requirements: `readelf -h` (machine), `readelf -d` (`NEEDED` list), `readelf -V` (versioned glibc symbol references). A `manylinux_2_17` tag is a *claim*; the symbol versions are the fact.
3. **Distribution metadata for anything that would be `yum install`ed**, from the AL2 aarch64 core repo index, giving package version, rpm size and installed size.

Functional behaviour (render output, timings, failure modes) was measured on x86_64 with the same source versions. Timings therefore transfer only as orders of magnitude — pdfium is a pure-CPU rasteriser and a Graviton2 vCPU at 512 MB of Lambda memory is slower than a laptop core, so read the millisecond figures below as "single-digit to low-tens of milliseconds", not as a promise.

---

## 2. Candidate verdicts at the gate

| Candidate | arm64 / AL2 verdict | Weight | Licence | Formats | Verdict |
|---|---|---|---|---|---|
| **`pypdfium2` 5.13.0** | ✅ `py3-none-manylinux_2_17_aarch64.manylinux2014_aarch64`; bundled `libpdfium.so` is AArch64 and needs `GLIBC_2.17` only, no `libstdc++`, no fontconfig | 3.5 MiB wheel / 8.3 MiB unpacked, 0 system packages | BSD-3-Clause + Apache-2.0 | PDF | **Recommended for PDF** |
| **PyMuPDF** | ❌ twice: AGPL-3.0-or-commercial, **and** from 1.26.3 the only aarch64 wheel is `manylinux_2_28` | 24 MiB wheel / 71–84 MiB sdist | AGPL-3.0-only or Artifex commercial | PDF, and XPS/EPUB | **Rejected** |
| **`pdf2image` + Poppler** | ⚠️ possible: `poppler-utils` exists for AL2 aarch64 — but at version **0.26.5**, released 2014 | ~9.6 MB installed closure (+12 MB if `poppler-data`), plus a font package | GPL-2.0 binary invoked as a subprocess; `pdf2image` MIT | PDF | **Rejected** (see §3.3) |
| **LibreOffice headless** | ❌ **zero `libreoffice*` packages** in the AL2 aarch64 core repo; the reference Lambda base image is **x86_64-only** | 877 MB image | MPL-2.0 | PDF + all Office | **Rejected** (see §3.4) |
| **LlamaParse page images** | ✅ nothing to install: an HTTPS GET on a job the worker already created | 0 | commercial API already in use | PDF, DOCX, PPTX — **not XLSX** | **Recommended for DOCX/PPTX** |
| **Third-party thumbnailer** (Cloudinary, ConvertAPI, CloudConvert, Zamzar) | ✅ technically, ❌ economically for what remains | 0 | commercial | all | **Rejected** (see §3.6) |
| **Ghostscript / ImageMagick** (added candidates) | ⚠️ both exist for AL2 aarch64 (`ghostscript 9.54.0`, `ImageMagick 6.9.10.97`) | 0.25 MiB + 14.8 MiB installed | AGPL-3.0 / ImageMagick licence | PDF | **Rejected**: AGPL for Ghostscript, and ImageMagick's PDF delegate *is* Ghostscript |
| **`wkhtmltoimage` + `xlsx2html`** (added candidate for XLSX) | ❌ needs a patched-Qt binary; no AL2 aarch64 build is published | ~50 MB + Qt deps | LGPL-3.0 | XLSX via HTML | **Rejected**: same class of problem as LibreOffice |
| **Pillow-drawn sheet preview** (added candidate for XLSX) | ✅ Pillow is already in the `worker` extra; `ImageFont.load_default(size=…)` ships a scalable font inside Pillow, so no font rpm | 0 | already present | XLSX | **Recommended for XLSX** |

---

## 3. The evidence, candidate by candidate

### 3.1 `pypdfium2` — the wheel that fits

pdfium is the PDF engine inside Chrome; `pypdfium2` is a ctypes binding that ships the prebuilt library, so there is nothing to compile and no CPython ABI to match.

```
$ uv pip compile pypdfium2 --python-platform aarch64-manylinux_2_17 --python-version 3.11 --only-binary :all:
Resolved 1 package in 109ms
pypdfium2==5.13.0
```

The wheel that satisfies that target, and what is inside it:

```
pypdfium2-5.13.0-py3-none-manylinux_2_17_aarch64.manylinux2014_aarch64.whl   3.51 MiB
  pypdfium2_raw/libpdfium.so                                                 7.50 MiB
  unpacked total                                                             8.30 MiB

$ readelf -h libpdfium.so   → ELF64, Machine: AArch64
$ readelf -d libpdfium.so   → NEEDED: libpthread.so.0, libm.so.6, libgcc_s.so.1,
                                      libc.so.6, ld-linux-aarch64.so.1
$ readelf -V libpdfium.so | grep -o 'GLIBC_[0-9.]*' | sort -uV
GLIBC_2.17
```

That third line is the whole verdict: the only versioned glibc symbols the library references are `GLIBC_2.17`, against an image that provides 2.26. There is no `libstdc++` dependency (so no `yum install libstdc++`), and no `libfontconfig` — pdfium carries its own fallback fonts, which matters because the Lambda base image ships **no** font packages at all.

Stability of the property, not just today's release:

```
pypdfium2 5.4.0 … 5.13.0   aarch64 tag = manylinux_2_17_aarch64.manylinux2014_aarch64   (12/12 releases)
```

Measured behaviour (x86_64, same version, Pillow 12.3):

| Input | Pages | Open | Render p1 @1280 px | `to_pil` | Top-16:9 crop + JPEG | Stored 640×360 |
|---|---|---|---|---|---|---|
| 1-page text A4 | 1 | 0 ms | 5 ms | 5 ms | 12 ms | **17.8 KB** |
| 201-page A4 | 201 | 0 ms | 3 ms | 5 ms | 10 ms | **44.4 KB** |
| 201-page, warm | 201 | 0 ms | 6 ms | 5 ms | 10 ms | 44.4 KB |

Two things this table settles. **Page count is irrelevant** — pdfium parses the cross-reference table and the one page requested, so a 200-page document costs the same as a 1-page one (the answer to "what happens to a 200-page document" in question 4). And **peak RSS for rendering page 1 of the 201-page file is 41 MiB**, against a 512 MB worker: rendering is not what would make this worker run out of memory. Lazy import cost, paid once per warm container: **`import pypdfium2` = 30 ms**, `from PIL import Image` = 6 ms.

### 3.2 PyMuPDF — disqualified twice, and the second reason is the task-304 trap replayed

**Licence first, as the task asks.** PyMuPDF is distributed under **AGPL-3.0-only**, with a commercial licence sold by Artifex as the alternative. The AGPL's §13 network clause is triggered by "interacting with users remotely through a computer network" — which is precisely what a mobile app talking to this backend does. Using it in a closed-source commercial product without buying the Artifex licence is not a grey area. Cost of the commercial licence is quote-only (Artifex does not publish a price), which for a feature whose entire euro cost is $0.003 per thousand documents ends the discussion before the wheel question.

**And the wheel question ends it again.** The regression is the same shape as Pillow's:

```
pymupdf 1.26.0  aarch64 wheel: manylinux2014_aarch64.manylinux_2_17_aarch64   sdist 71.1 MiB
pymupdf 1.26.3  aarch64 wheel: manylinux_2_28_aarch64                          sdist 72.5 MiB
pymupdf 1.26.4  aarch64 wheel: manylinux_2_28_aarch64                          sdist 79.2 MiB
pymupdf 1.28.2  aarch64 wheel: manylinux_2_28_aarch64                          sdist 83.8 MiB   (latest)
```

Reproduced live, and note which of the two commands matches what the Dockerfile actually does:

```
$ uv pip compile pymupdf --python-platform aarch64-manylinux_2_17 --python-version 3.11
pymupdf==1.28.2          ← sdist. This is the Dockerfile's behaviour. 83.8 MiB of MuPDF C
                           sources compiled inside the build, or a failure, exactly like Pillow 12.3.

$ uv pip compile pymupdf --python-platform aarch64-manylinux_2_17 --python-version 3.11 --only-binary :all:
pymupdf==1.26.0          ← the last version with a usable wheel: a pin frozen in 2026-05,
                           on an AGPL library, to work around the runtime.
```

### 3.3 `pdf2image` + Poppler — available, and still the wrong trade

`pdf2image` 1.17.0 itself is an 11.6 KB MIT-licensed wheel of pure Python that shells out to `pdftoppm`. The system side does exist for this image, which is worth recording precisely because the task-302 rejection assumed it might not:

```
AL2 aarch64 core repo
poppler                0.26.5-43.amzn2.1.7   rpm 0.79 MB   installed  2.76 MB
poppler-utils          0.26.5-43.amzn2.1.7   rpm 0.17 MB   installed  0.92 MB
poppler-data           (noarch)                            installed 12.01 MB
+ closure: fontconfig 1.23 MB, freetype 0.83 MB, libjpeg-turbo 0.46 MB, libpng 0.64 MB,
  cairo 1.94 MB, lcms2 0.42 MB, openjpeg2 0.42 MB
+ a font package, because the base image has none: liberation-sans-fonts 0.58 MB
                                                   (or dejavu-sans-fonts 5.40 MB)
≈ 9.6 MB installed without poppler-data, ≈ 21.6 MB with it
```

So it is roughly the same weight as pypdfium2 and it is rejected on three other grounds:

1. **Poppler 0.26.5 was released in 2014.** It is what AL2 froze, and it will never move. Twelve years of PDF fixes — encryption revisions, malformed-xref recovery, CJK and colour-space handling — are simply absent. pdfium ships as a `pip` dependency and follows Chrome's release train.
2. **It needs `subprocess`** in an async worker: a process spawn per document, a temp file, a timeout to manage, and a failure mode (non-zero exit, partial output) that has to be mapped back onto `cover_capture`'s "return `None`" contract by hand. pdfium raises a Python exception.
3. **Fonts become our problem.** `pdftoppm` resolves non-embedded fonts through fontconfig; with no font rpm installed it renders blanks. That is a second package, a `fonts.conf` and a class of "the tile is empty for this one document" bug that pdfium's built-in fallbacks avoid.

### 3.4 LibreOffice headless — the only Python-free Office path, and it does not exist on this architecture

Two independent facts kill it, before any discussion of cold start:

1. **There is no LibreOffice for Amazon Linux 2 on aarch64.** The core repo index contains **zero** packages whose name contains `libreoffice` (or `openoffice`, or `soffice`). There is nothing to `yum install`; the option means building LibreOffice from source for aarch64 inside our image, or vendoring a foreign build and hoping its glibc floor is ≤ 2.26.
2. **The reference prebuilt image is x86_64-only.** `shelfio/libreoffice-lambda-base-image`, the de-facto standard for this on Lambda, publishes `26.2-python3.14-x86_64`, `26.2-python3.13-x86_64`, `26.2-python3.12-x86_64` … — *every* published tag carries the `x86_64` suffix, and the project describes itself as "LibreOffice 26.2 base image for Lambda Node.js 20/22/24 x86_64 and Python 3.12/3.13/3.14 x86_64". Its size is **877 MB**.

Taking it therefore means one of:

| Way to have LibreOffice | What it costs |
|---|---|
| Move the whole worker image to x86_64 | Gives up the 20 % Graviton discount the Dockerfile's own comment claims, on **every** worker, for one cover format. And a 877 MB base against 391 MiB today. |
| A second, x86_64 Lambda just for Office covers | A new function, a new image, a new queue or invoke path, new Terraform, new alarms — and a synchronous cross-function call inside the document worker. |
| Build LibreOffice for aarch64 ourselves | Days of build engineering for a dependency nobody upstream publishes for this platform, then owning it. |

For reference, the *compute* would have been cheap: a 2 GB × 4 s conversion is 8 GB-s = **$0.000107** per document. The price of this option is image weight, architecture and maintenance — not euros. It is disproportionate for one format whose alternative (§3.7) costs 29 ms.

### 3.5 LlamaParse page images — verified against the live API, twice

Full transcript in §4. Summary: the screenshot is already produced by the request the worker sends today, for PDF, DOCX and PPTX; it is **never** produced for XLSX, in any mode or tier tried.

### 3.6 A third-party thumbnailing service — priced, and out of proportion

Only relevant for what the two recommended mechanisms leave uncovered, i.e. XLSX. Published prices, for a format that will be a single-digit percentage of uploads:

| Service | Entry price | What it buys |
|---|---|---|
| Cloudinary | Free plan 25 credits/month; **Plus $99/month** for paid add-ons | 1 credit = 1,000 transformations; Office→image goes through a paid add-on, i.e. the $99 tier |
| ConvertAPI | 250 conversions free on signup, then a monthly Developer plan | 1,000 conversions/month at the entry tier |
| CloudConvert / Zamzar | per-conversion or per-minute packages, ~$0.01–0.02 per file at small volume | one XLSX→PDF, then we still rasterise the PDF |

At a plausible launch volume (task-65's 100-user scale, ~600 documents/month, XLSX ≈ 10 % of them) that is **~$1/month for ~60 spreadsheet covers** — five percent of the whole 19 €/month infra line, for the least informative cover of the four formats, plus a new provider, a new secret to rotate, a new outbound dependency in the ingestion path and a new alarm. Rejected on proportion, not on feasibility. If the owner nevertheless wants a *genuine* print-layout page 1 for spreadsheets, this is the cheapest way to buy one and ConvertAPI's free 250 conversions covers four months of it — that is the "how to pay for it" answer the task asks for.

### 3.7 Drawing the spreadsheet ourselves — the measured alternative

The worker already holds the parsed content of the sheet: LlamaParse returns the first sheet as a table (`<table><tr><td>Region</td><td>Q1</td>…` in v2, a markdown pipe table in v1). Rendering that table as an image needs no new dependency: Pillow is already in the `worker` extra, and since Pillow 10.1 `ImageFont.load_default(size=…)` returns a **scalable** FreeType font bundled inside Pillow itself — verified on the pinned range — so no font rpm and no fontconfig either.

Measured on the real parse output of a 4×5 sheet: **29 ms** to parse the table, draw a header-banded grid at 1280×720 and encode the 640×360 JPEG q80 → **9.8 KB**. The result is a legible grid of the first rows and columns at tile size. Two honest caveats: it is a *preview of the data*, not a photograph of a page — a chart-only sheet or a heavily formatted dashboard renders as its underlying cells, and merged cells flatten. Against the alternative of 877 MB or $1/month, and against a real print-layout page 1 that is itself an artefact of the print area and scaling settings, that is the better trade.

---

## 4. LlamaParse, verified against the live API (2026-09-03)

The task requires this to be checked against the API, not the docs, because the parse is already billed on this path. Calls were made with the project's own LlamaParse key, read from the untracked local `.env`; no credential appears in this document or in any tracked file. Job identifiers are omitted deliberately.

### 4.1 The screenshot already exists on the request the worker sends today

The control that matters: not "can the API produce a screenshot if asked", but "does the request `llamaparse_resolver._upload_file` already sends produce one". Same base URL as `llamaparse_resolver.py:34` (`https://api.cloud.llamaindex.ai/api/parsing`, no `/v1`), same fields (`result_type=markdown`, `language=en`), **no** `take_screenshot`, **no** `save_images`:

```
[DOCX, worker's exact fields]  status=SUCCESS  parse latency 13.1 s
  pages = 1
  pages[0].images = [{"name": "page_1.jpg", "height": 841.89, "width": 595.304,
                      "x": 0, "y": 0, "original_width": 2263, "original_height": 3200,
                      "rotation": 0, "type": "full_page_screenshot"}]
  GET  …/job/{id}/result/image/page_1.jpg   → HTTP 200  image/jpeg  236.1 KB  in 828 ms

[PPTX, worker's exact fields, on the resolver's own base URL]  status=SUCCESS  15.1 s
  pages = 2
  pages[0].images = [{"name": "page_1.jpg", …, "original_width": 3000,
                      "original_height": 2250, "type": "full_page_screenshot"}]
  GET  …/job/{id}/result/json               → HTTP 200  518 ms   (keys: pages, job_metadata)
  GET  …/job/{id}/result/image/page_1.jpg   → HTTP 200  image/jpeg  175.7 KB  in 1087 ms
```

A PDF job returns the same artefact (checked in the same session) — irrelevant to the recommendation, since pdfium renders PDFs locally in 5 ms without a network round trip, but it means the LlamaParse route is a *fallback* for PDF if the owner ever wants to drop the dependency.

Two negative results worth recording: `GET …/job/{id}/result/pdf` answers **HTTP 404** on the v1 API for every job, so "ask LlamaParse for a PDF and rasterise it locally" is not available there; and `parse_mode=parse_page_with_lvm` now answers **HTTP 410 Gone**, the API itself pointing at the `tier` values or the v2 endpoint.

### 4.2 XLSX returns no image, in every configuration tried

| API | Configuration | Result |
|---|---|---|
| v1 `/api/parsing/upload` | `result_type=markdown, language=en` (the worker's own fields) | `SUCCESS` in 5.6 s, `pages[0].images = []` |
| v1 | `premium_mode=true` | `pages[0].images = []` |
| v1 | `parse_mode=parse_page_with_agent` | `pages[0].images = []` |
| v1 | `parse_mode=parse_page_with_lvm` | HTTP 410 Gone (mode retired) |
| v2 `/api/v2/parse/upload` | `tier=agentic`, `version=2026-08-19`, `output_options.images_to_save=["screenshot"]`, `output_options.save_output_pdf=true` | `status=COMPLETED`, `images_content_metadata = {"total_count": 0, "images": []}`, and **no** `output_pdf_content_metadata` in the expanded response |

The live OpenAPI schema (`https://api.cloud.llamaindex.ai/api/openapi.json`) explains it in its own words. `LlamaParseOutputOptions.images_to_save` is documented as *"Image categories to save: 'screenshot' (full page renders), 'embedded' …"*, and `save_output_pdf` as *"Save a PDF copy of the parsed document … **Not produced for spreadsheet, plain-text, or audio inputs**"*. The price list states the same thing in money: parsing is billed per page for documents but **"Spreadsheet: 1 credit per sheet"** — a spreadsheet is ingested as a grid, and a grid has no page to photograph. This is not a missing feature to wait for; it is a modelling choice, and it matches the fact that a spreadsheet has no page 1 until a print layout is computed from print area, scaling and margins.

### 4.3 What the two extra GETs cost

Nothing in credits. LlamaCloud's price list bills parsing, indexing, extraction, splitting, classification and retained file storage; **retrieving a job's results is not a priced operation**, and in this case the artefact is generated whether or not we fetch it (§4.1 was run *without* asking for it). For scale, the parse itself — which we already pay — is 3 credits/page at `cost_effective`, 10 at `agentic`, at **$1.25 per 1,000 credits**, with 10,000 credits/month on the free plan. The cover adds **$0.00** of provider cost and two HTTPS round trips (~0.5 s + ~1 s measured) inside a worker that already spends 5–15 s in the parse.

---

## 5. Where the render runs, what it costs, and what it does not debit

### 5.1 Inside the existing worker, at the branch that already exists

`workers/document_parsing/worker.py:347-367` is the right place and needs no restructuring: the image branch already calls `cover_capture.capture_from_s3(bucket=DOCUMENT_BUCKET, key=document_s3_key, media_item_id=job.media_item_id)` and assigns `job.media_image = cover_locator` before `mark_completed()`. Three properties of that position matter:

- **The file is already ours.** It sits in the `documents` bucket; nothing is fetched from a third party, and `cover_capture.capture_from_s3` already downloads it into memory and hands the bytes to `_downscale_to_jpeg` — which is exactly the seam a page-render step slots into (PDF magic bytes → render page 1 → then the existing downscale/encode path).
- **The parse is finished and the quota already debited** (`worker.py:200-214`), so the cover cannot influence billing, and a cover failure cannot cost a re-parse.
- **The temp directory holding the downloaded document is already closed** by the time this branch runs (`with tempfile.TemporaryDirectory()` spans `worker.py:268-286`), which is why the render must read from S3 rather than reuse the local file — again, what `capture_from_s3` already does.

### 5.2 It fits the worker's budget with room to spare

| Budget | Ceiling today | What the render adds |
|---|---|---|
| Memory | 512 MB (`lambda_workers.tf`, `document_parsing`) | peak RSS **41 MiB** to render page 1 of a 201-page PDF at 1280 px. Worst case is the 50 MB upload ceiling (`MAX_UPLOAD_SIZE_BYTES`) held in memory plus ~20 MB of bitmap → ~150 MB. |
| Timeout | 600 s (`timeout = 600`, SQS visibility 600) | +0.2–0.5 s (PDF), +1.4–1.6 s (DOCX/PPTX network), +0.03 s (XLSX) |
| Cold start | container image 391 MiB in ECR | +3.5 MiB compressed (+0.9 %); `import pypdfium2` 30 ms, paid once per warm container and only on document jobs (lazy import, like Pillow today) |
| Retries | `max_retries=3` | the cover never raises, so it never triggers one |

One implementation note for task-344 rather than a benchmark finding: `COVER_MAX_SOURCE_BYTES` (12 MB) is enforced only on the HTTP fetch path (`cover_capture.py:112-136`), not on `capture_from_s3`, which reads the object unbounded. With documents accepted up to 50 MB, the render path should bound its own read.

### 5.3 Euros

`eu-west-3`, arm64, first pricing tier: **$0.0000133334 per GB-second**, $0.20 per million requests (values read from the AWS price list API for `EUW3-Lambda-GB-Second-ARM`, and 400,000 GB-s/month are free).

| Format | Added wall time | GB-s at 512 MB | Added compute cost | Per 1,000 documents |
|---|---|---|---|---|
| PDF | ~0.5 s | 0.25 | $0.0000033 | **$0.003** |
| DOCX / PPTX | ~1.7 s | 0.85 | $0.0000113 | **$0.011** |
| XLSX | ~0.03 s | 0.015 | $0.0000002 | $0.0002 |

Storage and delivery: 10–45 KB per cover in the existing covers bucket, at $0.023/GB-month with PUTs at $0.005/1,000 — the model task-302 §5.4 already validated, which reaches **$0.04/month for the entire cover corpus at 100 users**. Egress stays inside AWS's free 100 GB/month. No provider fee (§4.3). **The euro line of this feature rounds to zero at any volume this app will see before it needs a different benchmark.**

### 5.4 The quota is debited exactly once — and the honest limitation

The debit happens in `_record_document_consumption` → `quota_enforcer.record_document_parse(user_id, page_count=…, idempotency_token=quota_enforcer.gate_token(job_id))`, at one minute per five pages (`document_pages_per_minute = 5`). The cover:

- makes **no** billed provider call (PDF, XLSX) and only reads the results of the already-billed job (DOCX, PPTX);
- passes through no quota code path, so **no second debit, and the idempotency token is untouched**;
- must not be given its own quota gate either: a cover is a display detail, and a user who has run out of minutes has already been stopped at the parse.

The limitation to state out loud: because the Office mechanism reads a LlamaParse artefact, **a DOCX or PPTX parsed by the Unstructured fallback gets no cover.** `parse_document_with_fallback` (`worker.py:88-150`) tries LlamaParse first and falls back to Unstructured on a retryable or API error, and Unstructured returns markdown only. That path already degrades the transcript quality, and it degrades the cover to the media-type glyph — which is the same best-effort contract, not a new failure mode. PDFs are immune to it, because pdfium runs locally regardless of which parser produced the text.

---

## 6. The 16:9 top-aligned framing

### 6.1 The geometry, measured on real renders

| Source | Page/slide raster | Top 16:9 band | Fraction of the page kept |
|---|---|---|---|
| PDF A4 portrait, rendered by pdfium at 1280 px wide | 1280×1811 | 1280×720 | **top 39.8 %** |
| DOCX A4 portrait, LlamaParse screenshot | 2263×3200 | 2263×1273 | **top 39.8 %** |
| PPTX 4:3 slide, LlamaParse screenshot | 3000×2250 | 3000×1688 | **top 75 %** |
| XLSX synthesised sheet preview | drawn at 1280×720 | — | header row + first ~4 data rows |

Top 39.8 % of an A4 page is the letterhead, the logo, the title, the addressee block and the first lines of body text — i.e. everything that makes the document identifiable in the owner's Files-app screenshots. A centre crop of the same page keeps a horizontal band of body text and drops all of it, which is the failure the owner ruled out.

### 6.2 Server-side, and why the "crop is the client's job" principle yields here

**Decision: crop server-side in `cover_capture`, store 640×360.**

| | Server-side (recommended) | Client-side `contentPosition="top"` |
|---|---|---|
| Stored derivative | **640×360** JPEG q80 — measured **17.8 KB** (text A4), **44.4 KB** (dense A4), **9.8 KB** (sheet preview) | 452×640 portrait — measured 10.7 KB / 65.1 KB |
| Mobile changes | **none**: a 16:9 image in a 16:9 box makes `contentFit="cover"` an exact fit | a media-type-conditional `contentPosition` at `MediaListCard.tsx:138`, `HomeTile.tsx:188` and `:243`, `search.tsx:1054`, `unsorted-review.tsx:592` |
| Failure mode over time | a new tile component inherits the framing for free | a new tile component inherits a **centre** crop, silently, and nobody notices until an owner looks at a screenshot |
| Fidelity to the source | the stored image is the top band only; the rest of the page is not kept anywhere (the original document is, of course, untouched in the `documents` bucket) | the stored image is the whole page |
| Resolution served | 640×360 covers `MediaListCard` at 112×63 and `HomeTile` at 200×113 up to a 3× display (600×338) | same visible band, from ~2× the pixels |

`cover_capture.py:14-18` states the principle being set aside: *"The crop to the tile's ratio is the client's job (`contentFit: "cover"`), which keeps this side free of any layout decision."* That principle was written for **re-hosted third-party covers and user photos**, where the image already exists with someone else's framing and cropping it destroys information we did not create. A document page is the opposite case: **there is no pre-existing image at all** — we choose the raster region, the scale and the encoding, so "choosing the framing" is not an extra layout decision bolted onto a neutral asset, it *is* the render. Refusing to decide server-side does not keep the service layout-free; it just moves the same decision into five components and guarantees the sixth gets it wrong.

The clean-choice rule applies too: nothing is deployed, there are no stored document covers to migrate, so there is no value in keeping a "neutral" full-page derivative for reversibility. If the owner later prefers a full page, the covers are regenerated by re-ingesting — which task-302 §11 already settled for backfills.

### 6.3 What it actually looks like — the honest part

Rendered and inspected at the real tile size (112×63) and at 3× for reading:

- **A slide or a branded cover page**: recognisable. On the renders produced here, a PPTX title slide's title reads at 3× and the slide is unmistakable at 112×63. An **ID document or a form** belongs to the same class — that is the owner's Files-app evidence, not re-tested here.
- **A page of dense body text with no letterhead**: a grey block of text lines, exactly as task-302 §11 predicted for the *centre*-cropped case. Top-aligning does not fix a page that has nothing distinctive at the top; it fixes every page that does.
- **`HomeTile` at 200×113 is where this pays off most** — roughly 3× the pixel area of the list thumbnail, enough for a title line to be read rather than merely recognised.

No rendering choice changes the dense-text case: it is a property of the document, not of the rasteriser. The relevant comparison is "grey text block" versus "generic paperclip glyph", and the owner has settled that the page wins. Recording it here so the next reader does not rediscover it as a defect.

---

## 7. The degraded path — same contract, exercised

`cover_capture` is best-effort by contract (`cover_capture.py:9-13`): every entry point returns `None` instead of raising, logs the reason, and the tile falls back to its media-type glyph (task-302 §6.3: never an empty grey box). The render obeys the same rule, and pdfium makes that easy — every malformed input raises **one** catchable Python exception (`pypdfium2.PdfiumError`) rather than crashing the process or hanging. Measured against real inputs:

| Input | Observed behaviour | Cover outcome |
|---|---|---|
| **Encrypted PDF, no password** | `PdfiumError: Failed to load document (PDFium: Incorrect password error)` | `None` → glyph. Never attempt a password. |
| Encrypted PDF, correct password supplied | opens and renders normally (1 page, 596×842) — noted only to show the failure above is the password check, not a parse bug | n/a |
| **Corrupt / truncated PDF** | `PdfiumError: … (PDFium: Data format error)` | `None` → glyph |
| **Empty (0-byte) file** | `PdfiumError: … (PDFium: Data format error)` | `None` → glyph |
| **Zip renamed `.pdf`** (and a DOCX handed to pdfium) | `PdfiumError: … (PDFium: Data format error)` | `None` → glyph |
| **0-page document** | the synthetic case failed at load with `Data format error`; a file pdfium *does* accept with no pages would give `len(doc) == 0`, so the guard is explicit rather than implied | `None` → glyph |
| **200-page document** | page 1 renders in 3–6 ms, peak RSS 41 MiB: page count is not a factor | normal cover |
| **DOCX/PPTX screenshot GET fails** (non-200, timeout, expired result) | HTTP error caught like any other cover fetch | `None` → glyph |
| **Office document parsed by the Unstructured fallback** | no LlamaParse artefact exists (§5.4) | `None` → glyph |
| **XLSX whose parse output has no table** (chart-only sheet) | nothing to draw → return early | `None` → glyph |
| Pillow or pypdfium2 missing from the image (API image) | already handled: the lazy import in `_downscale_to_jpeg` logs and returns `None` | `None` → glyph |

In every row the ingestion completes: `job.media_image` simply stays unset, `mark_completed()` runs, the transcript and the artifacts are unaffected. **No render failure can fail an ingestion, and none can trigger an SQS retry** (`process_message_with_retry(..., max_retries=3)` never sees an exception from this branch).

---

## 8. Cost and effort comparison of the end-to-end options

| # | Option | Formats covered | Image delta | Provider cost | Added latency / doc | Mobile changes | New infra | Effort |
|---|---|---|---|---|---|---|---|---|
| **A** | **pdfium (PDF) + LlamaParse screenshot (DOCX/PPTX) + drawn sheet (XLSX)**, server-side top-16:9 | **4/4** | +3.5 MiB (+0.9 %) | $0 | 0.5 s / 1.7 s / 0.03 s | **none** | none | **1 dependency pin, 1 render helper, 1 resolver method, 1 branch in the worker** |
| B | LlamaParse screenshot for **all** of PDF/DOCX/PPTX + drawn sheet (XLSX) | 4/4 | **0** | $0 | 1.7 s for every document | none | none | slightly less than A (no wheel, no pin) — but every PDF cover then depends on LlamaParse winning over the Unstructured fallback, pays 1.7 s and downloads ~240 KB where 5 ms of local CPU would do |
| C | pdfium only, Office on the glyph | 1/4 | +3.5 MiB | $0 | 0.5 s | none | none | smallest — **but does not satisfy the owner's fixed decision** that all four formats are in scope |
| D | LibreOffice headless for everything | 4/4 | **+877 MB, x86_64 only** | $0 | 2–4 s + cold start | none | a second x86_64 Lambda, or the whole worker image moved off Graviton | days of build/infra work, then owning a LibreOffice build |
| E | pdfium (PDF) + external conversion API (DOCX/PPTX/XLSX) | 4/4 | +3.5 MiB | ~$0.01–0.02 per Office file (~$1/month at launch volume) | 2–5 s (third-party round trip) | none | new provider, new secret, new alarm, new outbound dependency | moderate, and pays for what option A gets free |
| F | Any of the above with the crop **client-side** | same | same | same | same | **`contentPosition` branch at 5 render sites, 4 files** | none | more code, in the layer where a regression is invisible from the backend |

**Recommendation: option A.** It is the only one that covers all four formats without buying anything, without a new provider, without touching the mobile app and without giving up arm64 — and its two mechanisms are each verified against the actual runtime rather than assumed. Option B is the fallback if the owner would rather add no dependency at all to the image; the price is that PDF covers become as reliable as the primary parser and every PDF pays a network round trip for a 5 ms local job. Option E is the answer if, and only if, the owner rejects the synthesised sheet preview and wants a genuine print-layout page 1 for spreadsheets — ConvertAPI's 250 free conversions covers several months at launch volume, which is the cheapest way to find out whether spreadsheet covers are worth anything at all.

---

## 9. Open questions the owner may want to settle in the `Decision` field

1. **XLSX**: accept the synthesised first-sheet preview (§3.7, 29 ms, 9.8 KB, no dependency), or keep spreadsheets on the glyph, or buy a real print-layout page 1 through a conversion API (§3.6, ~$1/month at launch volume)? The recommendation assumes the first.
2. **Photos of documents**: an uploaded image (a passport photographed with the camera) already gets a cover today, stored full-frame, bounded to 640 px on its longest edge, and **centre**-cropped by the client. The owner's Files-app evidence included exactly that kind of item. Should the top-16:9 framing apply to uploaded images too — which would make the document and photo paths consistent, at the cost of framing every user photo from the top? Out of this benchmark's stated scope, one line to change if the answer is yes.
3. **Nothing is backfilled**: existing `-dev` document rows keep their glyph unless re-ingested, per the task's own owner note and task-302 §11.

---

## 10. Scope of this benchmark

No production code, contract, Terraform file, `pyproject.toml`, Dockerfile or mobile component was modified (AC #9). The only files added are this README and the `Implementation Notes` entry on task-343. Everything measured here was run from throwaway scripts and a scratch virtualenv outside the repository, against real files and the live LlamaParse API. The implementation — the `pypdfium2` pin, the render helper, the resolver method that fetches `page_1.jpg`, the worker branch and the correction of the now-stale comment at `worker.py:358-360` — belongs to **task-344**, which defers to whatever the owner writes in the `Decision` field above.

---

## 11. Sources

**Runtime and packaging**
- AWS Lambda Python container base images (`public.ecr.aws/lambda/python`) — https://docs.aws.amazon.com/lambda/latest/dg/python-image.html · https://gallery.ecr.aws/lambda/python
- PEP 600, manylinux platform tags (glibc floor semantics) — https://peps.python.org/pep-0600/
- Amazon Linux 2 aarch64 core repository index (glibc 2.26, poppler, fonts, and the absence of LibreOffice) — http://amazonlinux.us-east-1.amazonaws.com/2/core/latest/aarch64/mirror.list → `repodata/primary.xml.gz`
- uv platform-targeted resolution (`--python-platform`, `--only-binary`) — https://docs.astral.sh/uv/pip/compatibility/ · https://docs.astral.sh/uv/reference/cli/#uv-pip-compile

**PDF rasterisers**
- pypdfium2 on PyPI (wheel tags, sizes, `BSD-3-Clause, Apache-2.0`) — https://pypi.org/project/pypdfium2/ · project — https://github.com/pypdfium2-team/pypdfium2
- pdfium (Chrome's PDF engine) — https://pdfium.googlesource.com/pdfium/
- PyMuPDF on PyPI (aarch64 wheel tags per release, sdist sizes) — https://pypi.org/project/PyMuPDF/
- PyMuPDF licensing: AGPL-3.0-only or Artifex commercial — https://pymupdf.readthedocs.io/en/latest/about.html#license-and-copyright · https://artifex.com/licensing/
- pdf2image (MIT, subprocess wrapper around `pdftoppm`) — https://pypi.org/project/pdf2image/
- Poppler — https://poppler.freedesktop.org/
- Ghostscript licensing (AGPL) — https://www.ghostscript.com/licensing/

**Office rendering**
- shelfio LibreOffice Lambda base image — x86_64-only tags, 877 MB — https://github.com/shelfio/libreoffice-lambda-base-image
- LlamaCloud OpenAPI schema (`images_to_save`, `save_output_pdf` — "Not produced for spreadsheet, plain-text, or audio inputs", `tier` enum) — https://api.cloud.llamaindex.ai/api/openapi.json
- LlamaParse credit pricing per tier and per spreadsheet sheet — https://developers.llamaindex.ai/python/cloud/pricing
- LlamaIndex plan pricing (1,000 credits = $1.25; 10K free credits/month) — https://www.llamaindex.ai/pricing
- Live API verification: `https://api.cloud.llamaindex.ai/api/parsing/upload`, `/job/{id}/result/json`, `/job/{id}/result/image/{name}`, `https://api.cloud.llamaindex.ai/api/v2/parse/upload` (measured 2026-09-03, §4)

**Thumbnailing / conversion services**
- Cloudinary pricing (Free 25 credits/month; Plus $99/month for paid add-ons) — https://cloudinary.com/pricing
- ConvertAPI pricing (250 free conversions, Developer plan 1,000 conversions/month) — https://www.convertapi.com/prices
- CloudConvert pricing — https://cloudconvert.com/pricing
- Zamzar developer pricing — https://developers.zamzar.com/pricing

**Costs**
- AWS Lambda pricing, and the `eu-west-3` price list used for `EUW3-Lambda-GB-Second-ARM` = $0.0000133334/GB-s — https://aws.amazon.com/lambda/pricing/ · https://pricing.us-east-1.amazonaws.com/offers/v1.0/aws/AWSLambda/current/eu-west-3/index.json
- Amazon S3 pricing (storage, PUT, egress) — https://aws.amazon.com/s3/pricing/

**Client rendering**
- `expo-image` `contentPosition` (CSS `object-position` equivalent, default `center`) — https://docs.expo.dev/versions/latest/sdk/image/#contentposition · installed types at `mobile/node_modules/expo-image/build/Image.types.d.ts:150`
- Pillow `ImageFont.load_default(size=…)` returning a bundled scalable font (Pillow ≥ 10.1) — https://pillow.readthedocs.io/en/stable/reference/ImageFont.html#PIL.ImageFont.load_default

**Repository context**
- `docs/research/task-302-media-cover-and-creator/README.md` — §4 row 8, §5.4 cost model, §6.3 degraded state, §6.4 the 16:9 ratio, §11 the original rejection and §11.1 the owner's 2026-09-03 override
- `docs/research/task-90-document-parser-benchmark/README.md` — the LlamaParse/Unstructured choice this path already implements
