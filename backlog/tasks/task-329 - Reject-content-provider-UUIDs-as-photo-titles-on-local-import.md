---
id: task-329
title: Reject content-provider UUIDs as photo titles on local import
status: Done
assignee: []
created_date: '2026-09-01 16:41'
updated_date: '2026-09-01 17:26'
labels:
  - bug
  - mobile
dependencies: []
priority: medium
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
## Observed

On 2026-09-01, a document imported from Android landed in the library titled `3f599e8d 3dc6 4bb2 a4a1 dd21001d4d3f`. On 2026-08-29, `4E49414A EBCD 41A8 ABC0 6D9324E2A4C6`. Another photo from the same day is titled correctly: `Photo — 01 Sep 2026`.

## Cause

`mobile/src/lib/localImport.ts:163`:

```ts
name: asset.fileName || defaultPhotoName(asset.uri, asset.mimeType),
```

The fallback only fires when `fileName` is **absent**. The Android gallery does supply a `fileName` — the content provider's UUID — so it is non-empty, the `||` short-circuits, and the UUID becomes the title. iOS produces the same shape in upper case.

The name is carried as-is into `processing_jobs`, so it becomes the media's displayed title with no later chance to correct it.

## Scope

Treat a `fileName` that carries no meaning as absent, so `defaultPhotoName()` applies. Keep using a genuinely informative filename.

## Owner notes

- Worth re-checking on a real Android device, importing from the **gallery** and from the **camera** — the two sources do not hand back the same `fileName`, and only one of them is broken today.
- The two media items already stored with UUID titles on `-dev` keep them; rename them from the app if they get in the way.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 A fileName carrying no meaning — a content-provider UUID, with or without dashes, in either case — is treated as absent so the default photo name applies instead of becoming the title
- [x] #2 A genuinely informative fileName (a document name the user chose, for instance) is still used as the title exactly as today
- [x] #3 The rejection lives in the local import path itself, so every caller that builds an item name from a picker asset benefits from it without repeating the check
- [x] #4 npm run typecheck and ESLint pass on the changed mobile files
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
### What changed

One file, `mobile/src/lib/localImport.ts`:

- `isMeaningfulFileName()` — drops the extension, removes dashes, underscores and
  spaces, and refuses a stem that is hex only and 16 characters or longer, or
  empty. A canonical UUID compacts to 32 hex characters and a dash-free one is
  already 32, so both shapes are caught in either case (the regex is `/i`), while
  nothing built out of words can match.
- `photoName(asset)` — the reported `asset.fileName` is used only when it survives
  that check; otherwise the code falls through to `defaultPhotoName()` exactly as
  it did when the picker reported no name at all. This replaces the
  `asset.fileName || defaultPhotoName(...)` of the bug report.
- `defaultPhotoName()` hardened for the same reason. The old code returned the
  last URI segment whenever it contained a dot, and that segment is a UUID too:
  `expo-image-picker` names its own cache copy after a fresh UUID
  (`MediaHandler.kt`: `fileName = fileData?.fileName ?: outputFile.name`, the
  asset `uri` being that very file). It now keeps the URI's **extension** — the
  backend routes on it, and keeping it verbatim leaves every accept/refuse
  decision of `classifyUploadFile` unchanged, `.webp` included — but replaces an
  opaque stem with `photo-<epoch>`.

Both photo gestures (`capturePhotoToImport`, `pickPhotoFromLibrary`) already
funnel through `toImportResult`, so the check is written once and applies to
every caller that builds an item name from a picker asset (AC#3). Callers only
ever see the finished `LocalUploadFile`, so nothing outside this module repeats
the test.

### Why this is enough to fix the title

The server-side derivation needs no change. `photo-1756742400000.jpeg` reaches
`normalize_title_candidate(from_file_name=True)`, loses its extension, and is
then rejected by the existing `_DEVICE_NAME_RES` rule
`^(img|...|photo|...)[-_ ]*\d` in
`media_summarizer/core/media_ingestion/title_derivation.py`, which lands on
`fallback_title()` — the `Photo — 01 Sep 2026` the owner already observed on the
photo that worked.

### Decisions

- **The document path (`pickFileToImport`) is untouched.** Its name is the only
  carrier of the extension for a PDF or an audio file, and there is no
  equivalent default to fall back to, so nulling an opaque name there would turn
  a valid import into an "unsupported format" refusal. Scope was the photo path.
- **The threshold is 16 hex characters, mirroring the backend's own
  `^[0-9a-f]{16,}$` device-name rule** rather than a strict UUID grammar: same
  line drawn in both places, and a shorter numeric id (a MediaStore row number,
  `20260901_143000`) keeps being handled by the backend rules that already cover
  it.
- **No automated tests added**, per the project rule; none of the ACs asked for
  any.

### Verified / not verified

`npm run typecheck` clean; `npm run lint` reports 0 errors and the 2 pre-existing
warnings in untouched files (`app/(tabs)/digest.tsx`,
`src/services/purchaseService.ts`).

The owner's re-check on a real Android device — importing from the gallery and
from the camera, which do not hand back the same `fileName` — is out of reach
from a worktree: it needs a dev build on a device.

Noted while reading, out of scope: the backend `is_rejected_title` misses a
**dashed** UUID, because `from_file_name` normalisation turns the dashes into
spaces before the hex rule runs (`3f599e8d 3dc6 4bb2 ...` matches nothing). Any
other producer that uploads a dashed-UUID filename — a document picked from
Files, a share-extension payload — would still title a media that way. Worth its
own task if the owner wants the belt as well as the braces.
<!-- SECTION:NOTES:END -->
