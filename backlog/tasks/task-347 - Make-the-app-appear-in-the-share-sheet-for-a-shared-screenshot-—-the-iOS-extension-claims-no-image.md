---
id: task-347
title: >-
  Make the app appear in the share sheet for a shared screenshot — the iOS
  extension claims no image
status: To Do
assignee: []
created_date: '2026-09-03 12:02'
labels:
  - mobile
  - bug
dependencies: []
priority: high
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
## What the owner sees

Take a screenshot on iOS, tap the preview, open the share sheet from it, look for the app in the row of apps: it is not there. Nothing to scroll to, nothing to search — the entry does not exist. Reported for iOS; Android was not tested.

## Root cause on iOS: the extension never claims images

`mobile/app.config.ts:242-246` configures `expo-share-intent` with three activation predicates:

- `NSExtensionActivationSupportsWebURLWithMaxCount: 1`
- `NSExtensionActivationSupportsText: true`
- `NSExtensionActivationSupportsFileWithMaxCount: 1`

Those predicates are exactly what iOS evaluates to decide whether a share extension is offered for the current items. `…SupportsFile…` matches a *file* attachment; it does not match an **image** attachment (`public.image`), which is what the screenshot editor — like Photos — hands to the share sheet. Apple has a separate key for that, `NSExtensionActivationSupportsImageWithMaxCount`, and it is missing, so the rule never matches and the row is never rendered.

The key is a supported option of the plugin (`iosActivationRules`, documented in `expo-share-intent`'s README) and lands in the `NSExtensionActivationRule` of the generated `ShareExtension-Info.plist` at prebuild (`node_modules/expo-share-intent/plugin/build/ios/writeIosShareExtensionFiles.js:80`).

Do **not** add `NSExtensionActivationSupportsMovieWithMaxCount` alongside it: video has no backend route, and claiming it would put the app in the share sheet for content it can only refuse.

## Second cause, same symptom: the row is not named after the app

`iosShareExtensionName: "ShareMedia"` (`mobile/app.config.ts:241`) becomes the extension's `CFBundleDisplayName` (`writeIosShareExtensionFiles.js:72`), so the label under the icon reads **"ShareMedia"** while the app is called "Media Summarizer" (`app.config.ts:99`). Even with the image rule fixed, the owner would be scanning for the app's name. Align the label on the app name.

Renaming is safe on Apple's side: the extension's bundle id is derived from the app's, `<appId>.share-extension` (`node_modules/expo-share-intent/plugin/build/ios/constants.js:22`), not from this name — so no new App ID and no new provisioning profile. Only the Xcode target name and the generated `ios/<Name>/` directory change, and `ios/` is gitignored.

## Android: the filter is already there, the handler is what to check

`androidIntentFilters` already lists `image/*` (`app.config.ts:261`), so a shared screenshot does reach the app on Android. What can fail on both platforms is the handler below.

## Handler: an image share must reach the upload path, and look like a photo

`mobile/src/contexts/ShareIntentContext.tsx:328-392`, the `file`/`media` branch, calls `classifyUploadFile(file.fileName ?? "file")`. Two things:

- The extension is the only discriminant (`mobile/src/types/upload.ts:114`) and the `"file"` fallback has none, so it lands on `share.unsupportedFile`. The nominal case survives — iOS reports `uuid + extension`, Android the provider's `DISPLAY_NAME` — but when the reported name carries no usable extension, derive it from the `path` and then from the `mimeType` instead of refusing an image the backend knows how to OCR (`png`, `jpg`, `jpeg`, `heic`, `heif`, `tiff`, `bmp` are already in `DOCUMENT_UPLOAD_EXTENSIONS`).
- The branch hands `applyLocalUpload(result.file, "file")` for everything. An image should go through as `"photo"`: `mobile/app/share-confirmation.tsx:294-301` uses that to show the image preview (`isPhoto`) rather than a generic file card, the same surface the camera capture of task-264 already uses.

## Legacy to delete in the same run

`mobile/ios-share-extension/` (`Info.plist` + `ShareViewController.swift`) has been dead since task-188 removed the custom `withShareExtension.js` plugin: `expo-share-intent` generates its own target from `node_modules`, and nothing in the build reads that directory. It is actively misleading for this task — its `Info.plist:27-35` holds a **second copy** of the activation rules, which someone can fix with no effect whatsoever, and a `CFBundleIdentifier` of `com.secondbrainlabs.core.ShareMedia` that the build never produces. Delete the directory, drop the line that checks it in `scripts/mobile_release_check.sh:181` (the bundle-id check keeps `mobile/app.config.ts`), and follow the mentions in `docs/V1_LAUNCH_PLAN.md:754`, `mobile/MOBILE_CI_CD.md:504` and `mobile/E2E_TESTING.md:178`.

Careful: `"ios-share-extension"` is **also** an ingestion `source` value sent to the backend (`ShareIntentContext.tsx:545,598,642`, `sharedContentService.ts:80,132`). That string is part of the API contract and must not be touched — only the file-path references go.

## Owner notes (deliberately not acceptance criteria)

- This is a native change: the activation rules live in the extension's `Info.plist`, not in the JS bundle, so no OTA update can deliver it. A fresh iOS dev build is required, then the real check is manual — screenshot → share sheet → the app shows up under its own name → the confirmation screen shows the image preview → ingestion starts.
- If the row still does not appear on that build, open the share sheet, scroll the app row to the end, tap **"Autres" / "More" → "Modifier les actions…" / "Edit Actions…"** and confirm the app is enabled there; iOS sometimes keeps a freshly installed extension off by default.
- task-186 (rebranding) lists `mobile/plugins/withShareExtension.js` and `mobile/ios-share-extension/Info.plist` among the places to rename. The first was already deleted by task-188; after this task the second is gone too, and the share-sheet label lives in `mobile/app.config.ts` under `iosShareExtensionName`.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 `iosActivationRules` in `mobile/app.config.ts` declares `NSExtensionActivationSupportsImageWithMaxCount: 1` next to the three existing predicates, and no Movie key is added
- [x] #2 `iosShareExtensionName` carries the app name as declared in `expo.name`, so the share-sheet row is no longer labelled "ShareMedia"
- [x] #3 In `ShareIntentContext`, a shared image whose reported `fileName` has no usable extension is classified from its `path` or its `mimeType` and no longer reaches the `share.unsupportedFile` branch
- [x] #4 A shared image reaches the confirmation screen with `contentType: "photo"` (image preview); other shared files keep `"file"`
- [x] #5 `mobile/ios-share-extension/` is deleted, and no file-path reference to it remains in `scripts/`, `mobile/` or `docs/` — while the `source: "ios-share-extension"` values sent to the backend are left untouched
- [x] #6 `bash scripts/mobile_release_check.sh` exits 0 and no longer names the deleted plist
- [x] #7 `npm run lint` and `npm run typecheck` are clean in `mobile/`
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Three commits, in the order the causes stack up.

**iOS activation rules and the row label** (`mobile/app.config.ts`).
`NSExtensionActivationSupportsImageWithMaxCount: 1` sits with the three existing
predicates; no Movie key. The plugin types `iosActivationRules` as an open record
and writes it verbatim into the `NSExtensionActivationRule` of the generated
`ShareExtension-Info.plist`, so nothing else was needed. The app name is now a
single `appName` constant read by both `expo.name` and `iosShareExtensionName`,
which is what closes AC #2 permanently: the share-sheet label cannot drift from
the app name again, and task-186 has one string to change instead of two.

**Handler** (`mobile/src/types/upload.ts`, `mobile/src/contexts/ShareIntentContext.tsx`).
`resolveUploadFileName({ fileName, path, mimeType })` recovers an extension from
the copied file's path first, then from the MIME type, and returns the reported
name untouched when it already routes — an unsupported format still reaches its
refusal. The MIME map that recovery needs was the local map inside
`defaultMimeTypeFor`; it is now the module-level `EXTENSION_MIME_TYPES`, read in
both directions, plus the aliases the platforms really send (`image/x-ms-bmp` is
what the iOS extension's own MIME table returns for a bitmap). A shared image goes
through `applyLocalUpload(…, "photo")`, decided by `isImageUpload` on the MIME type
*or* the extension, because either can be the only usable one (a HEIC share is
reported as `application/octet-stream`).

**The card** (`mobile/app/share-confirmation.tsx`). The task assumed `isPhoto`
already produced an image preview — it did not: it swapped the icon for
`camera-outline` and pushed a hardcoded, untranslated `"Camera capture"` subtitle,
which becomes plainly false for a shared screenshot. The icon slot now renders the
picture itself through `expo-image` (already a dependency, already wired by its
config plugin), with the icon kept as the fallback when the URI cannot be read
back, and the `isPhoto` prop is gone. The photo/file distinction survives where it
belongs: the top bar title (`Save Photo` / `Import File`) and the success message
(`Photo imported. Text extraction will begin shortly.`).

**Legacy.** `mobile/ios-share-extension/` deleted, its line dropped from
`scripts/mobile_release_check.sh` (the bundle-id check is down to
`mobile/app.config.ts`, the single place it is declared), and the three doc
mentions updated. Two occurrences of the string survive on purpose and are not
live references: a tombstone in the script's comment and one in
`docs/V1_LAUNCH_PLAN.md`, both saying the directory was deleted by this task —
the same guard task-188 left for `withShareExtension.js`, which is precisely what
kept anyone from writing it back. The five `source: "ios-share-extension"` values
in `ShareIntentContext.tsx` and `sharedContentService.ts` are untouched.

**Verified here.** `bash scripts/mobile_release_check.sh` exits 0 (AC #6),
`npm run typecheck` clean, `npm run lint` clean — the two remaining warnings are
pre-existing (`digest.tsx` CARD_WIDTH, `purchaseService.ts` any) and untouched.

**Not verified here, by construction.** The activation rules live in a native
plist, so nothing about the share-sheet row can be observed from this worktree:
the fingerprint runtime version moves, an OTA update cannot carry it, and the
check is a fresh iOS dev build followed by the manual run listed under
`Owner follow-up:` in the first commit (screenshot → share sheet → row labelled
"Media Summarizer" → image preview → Save → ingestion). Android is worth the same
pass: the `image/*` intent filter was already declared, so the handler changes are
the only variable there.
<!-- SECTION:NOTES:END -->
