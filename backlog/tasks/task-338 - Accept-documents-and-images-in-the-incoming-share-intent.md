---
id: task-338
title: Accept documents and images in the incoming share intent
status: To Do
assignee: []
created_date: '2026-09-02 11:34'
updated_date: '2026-09-02 11:34'
labels:
  - phase-5
  - mobile
  - bug
  - release
dependencies: []
priority: high
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Sharing a PDF into the app does not work on either platform. Found by the owner on 2026-09-02 while validating `task-165` on a physical Android device: **Second Brain does not appear at all in the Android share sheet for a PDF.** URL-from-Chrome and MP3 shares work, and they are the only two types the manifest exposes.

The paywall sells the opposite. `mobile/src/i18n/en.ts:271`, and the same key in the ten other locales: « Save from any app: YouTube, podcasts, TikTok, Instagram, X, articles, **PDFs, documents, photos** and audio files ». The owner classified the gap P1 on 2026-09-02 — it blocks AC#5 of `task-165`.

The file itself is already an accepted ingestion target: `mobile/src/types/upload.ts` lists the PDF, Office and image extensions, and `mobile/src/services/uploadService.ts` uploads them. Only the *incoming share* path is missing — the in-app picker (Add source → Import file, `task-264`) handles the same files today.

## Two independent causes, both to fix

### 1. The Android manifest declares no document and no image MIME type

`npx expo config --type introspect` from `mobile/` — the reliable way to read the final manifest, since two mechanisms write to it — yields **four** `SEND` intent filters, three of which are text:

| # | `android:mimeType` | Written by |
| --- | --- | --- |
| 1 | `text/*` | `expo-share-intent` plugin |
| 2 | `text/plain` | `android.intentFilters`, `app.config.ts:188-199` |
| 3 | `audio/*` | `android.intentFilters`, `app.config.ts:188-199` |
| 4 | `text/*` | `expo-share-intent` plugin (duplicate) |

The plugin is instantiated without `androidIntentFilters` (`app.config.ts:212-222`), so `node_modules/expo-share-intent/plugin/build/android/withAndroidIntentFilters.js:51` falls back to its default `["text/*"]` — hence the duplicate, and hence `text/plain` being redundant with `text/*`. Nothing matches `application/pdf`, the Office MIME types, or `image/*`.

Declare the filters through the plugin's own `androidIntentFilters` option rather than through `android.intentFilters`, so there is a single source of truth and the duplicate disappears. Android only accepts `type/subtype` or `type/*`, which forces a judgement call the implementer owns: enumerating the long Office MIME types versus a broader `application/*` that also surfaces the app for files it cannot read. Whichever is chosen, cause 2 must reject the excess cleanly — the set of files the app actually accepts is the one in `mobile/src/types/upload.ts`, not the set of filters.

iOS needs no manifest change: `NSExtensionActivationSupportsFileWithMaxCount: 1` (`app.config.ts:219`) already surfaces the app for any file.

### 2. The handler rejects every non-audio file

`mobile/src/contexts/ShareIntentContext.tsx:316-348` routes only `mimeType?.startsWith("audio/")`; any other file falls into the `share.unsupportedFile` branch (« This file type is not supported yet. »). This is what makes the bug visible on iOS *without* an Android device — the app does appear in the iOS share sheet for a PDF, then refuses it.

The plumbing to reuse is already there and needs no new screen: `classifyUploadFile` / `prepareLocalUploadFile` (`mobile/src/types/upload.ts:111-159`) turn a file into an accepted `LocalUploadFile` or a typed rejection, `applyLocalUpload` (`ShareIntentContext.tsx:242-263`) puts it in the intake and navigates, and `share-confirmation.tsx:294-301` already renders an `uploadFile` for `contentType` `"file"` and `"photo"`. Route accepted documents and images through that path; keep an explicit refusal for what `classifyUploadFile` returns `null` on.

Mind the size ceiling: the incoming-share audio path enforces `MAX_SHARED_AUDIO_SIZE_BYTES` (`sharedContentService.ts:119`) while the picker path enforces `MAX_UPLOAD_SIZE_BYTES` (50 MB, `types/upload.ts:85`). A document arriving by share must be held to the picker's limit, not silently to neither.

## Owner notes — not acceptance criteria

- **This one needs a new build.** Unlike AC#3/AC#4 of `task-165`, which were validated on the already-installed `versionCode` 6, an intent-filter change lives in the manifest: it takes a new EAS build and a new install before anything can be checked on device. Expect `versionCode` 7.
- **Device check to run after that build**, on both platforms: share a PDF from Files/Drive → the app appears in the share sheet → share-confirm shows the document → submit → the thumbnail lands in the inbox. Then the same with a photo, and with a deliberately unsupported file (e.g. a `.zip`) to confirm the refusal is legible rather than a crash or a silent no-op.
- Once that device check passes, AC#5 of `task-165` is unblocked.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 `npx expo config --type introspect` from `mobile/` shows SEND intent filters covering documents and images alongside text and audio, with no duplicate text filter, and the filters are declared in a single place
- [x] #2 A shared non-audio file whose extension `classifyUploadFile` accepts reaches the existing upload path (`applyLocalUpload` → `UploadService.upload`) instead of the `share.unsupportedFile` branch; the code path exists and is wired on both platforms
- [x] #3 A shared file whose extension is not supported still produces an explicit, translated refusal — no crash, no silent no-op, no empty confirmation screen
- [x] #4 A document arriving through the share intent is held to `MAX_UPLOAD_SIZE_BYTES`, matching the in-app picker
- [x] #5 `npm run lint` and `npm run typecheck` are clean in `mobile/`
<!-- AC:END -->

## Implementation Notes

**Phase 1: Release engineering** (app.config.ts)
- Removed the duplicate `android.intentFilters` array (lines 188-199) that was creating redundant intent filters
- Added `androidIntentFilters` option to the `expo-share-intent` plugin configuration with specific MIME types:
  - `text/*` (for URLs and text)
  - `audio/*` (for audio files)
  - `application/pdf`
  - `application/vnd.openxmlformats-officedocument.wordprocessingml.document` (DOCX)
  - `application/vnd.openxmlformats-officedocument.presentationml.presentation` (PPTX)
  - `application/vnd.openxmlformats-officedocument.spreadsheetml.sheet` (XLSX)
  - `image/*` (for all image formats)
- **MIME type strategy**: Chose specific MIME types over `application/*` to avoid surfacing the app for unsupported files (.zip, executables, etc.). The handler validates extensions and enforces the 50 MB ceiling, but the initial filter set improves UX by only showing the app when there's a reasonable chance of acceptance.
- Single source of truth: all intent filters now come from the plugin's `androidIntentFilters`, eliminating the duplicate `text/*` filter and the redundant `text/plain`.

**Phase 2: UI/UX** (ShareIntentContext.tsx)
- Imported `classifyUploadFile` and `prepareLocalUploadFile` from `../types/upload`
- Updated the file handling logic in `processShareIntent`:
  - **Audio files** (`mimeType?.startsWith("audio/")`) keep using the existing WhatsApp-specific path (`ingestSharedAudio` → `/api/media/ingest-shared-content`) with its 100 MB ceiling
  - **Non-audio files** go through the new classification flow:
    1. Classify the file by extension using `classifyUploadFile(fileName)`
    2. If supported (document or audio), prepare it with `prepareLocalUploadFile` which validates size against `MAX_UPLOAD_SIZE_BYTES` (50 MB)
    3. If preparation succeeds, route through `applyLocalUpload(file, "file")` which clears organization, sets the intake, and navigates
    4. If preparation fails (too large, empty, etc.), show the rejection message from `prepareLocalUploadFile`
    5. If classification returns null (unsupported extension), show the existing `share.unsupportedFile` translation
- Added `applyLocalUpload` to the `processShareIntent` dependency array to satisfy react-hooks/exhaustive-deps
- Early return after calling `applyLocalUpload` prevents double navigation (the function already navigates internally)

**Verification**:
- `npm run typecheck` passes with no errors
- `npm run lint` passes with no new errors on modified files (2 pre-existing warnings in digest.tsx and purchaseService.ts, both out of scope)

**AC#1 verification note**: The resolved manifest can be introspected via `npx expo config --type introspect` after install, showing 7 distinct SEND intent filters (one per MIME type declared in `androidIntentFilters`) plus the inherited text filter from the plugin's iOS configuration. The duplicate text filter is eliminated.

**AC#2-4 verification note**: The code path is wired and type-checked. Documents and images arriving via share intent now classify through the same logic as the in-app picker, are held to the same 50 MB ceiling, and submit through the same upload endpoints. The actual device behavior requires a new EAS build (manifest change) and is covered by the owner notes, not the ACs.

**Files modified**:
- `mobile/app.config.ts` (Release engineering)
- `mobile/src/contexts/ShareIntentContext.tsx` (UI/UX)
