---
id: task-329
title: Reject content-provider UUIDs as photo titles on local import
status: To Do
assignee: []
created_date: '2026-09-01 16:41'
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
- [ ] #1 A fileName carrying no meaning — a content-provider UUID, with or without dashes, in either case — is treated as absent so the default photo name applies instead of becoming the title
- [ ] #2 A genuinely informative fileName (a document name the user chose, for instance) is still used as the title exactly as today
- [ ] #3 The rejection lives in the local import path itself, so every caller that builds an item name from a picker asset benefits from it without repeating the check
- [ ] #4 npm run typecheck and ESLint pass on the changed mobile files
<!-- AC:END -->
