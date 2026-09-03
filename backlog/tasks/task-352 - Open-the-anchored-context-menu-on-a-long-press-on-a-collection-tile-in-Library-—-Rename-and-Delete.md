---
id: task-352
title: >-
  Open the anchored context menu on a long press on a collection tile in Library
  — Rename and Delete
status: To Do
assignee: []
created_date: '2026-09-03 14:30'
labels:
  - mobile
  - feature
dependencies: []
priority: medium
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
## What is there today

In the Library tab (`mobile/app/(tabs)/search.tsx` — the file is still named `search`, the tab is the library), a long press on a media row opens the anchored context menu built by task-346: `mobile/src/components/MediaContextMenu.tsx` for the surface, `mobile/src/hooks/useMediaActions.ts` for the behaviour, `mobile/src/components/MediaRenameDialog.tsx` for the rename field. Three actions: Move, Rename, Delete.

The collection tiles of the same screen have nothing. `CollectionTile` (local to `search.tsx`, ~line 945) carries `onPress` only. A collection can be created (`OrganizationService.createCollection`) but never renamed or deleted from anywhere in the app — `grep -rn "api/folders" mobile/src` returns the `GET` and the `POST` and nothing else.

## What is asked

A long press on a collection tile in the Library tab opens **the same menu**, anchored to the tile that was pressed, offering **Rename** and **Delete** — two actions, not three.

**Except on the default collection.** The tile pinned first in the grid, shown as "Unsorted" (`DEFAULT_COLLECTION_LABEL`) and tinted with `DEFAULT_COLLECTION_TINT`, is the system bin for unsorted media: `folder_service.update_folder` and `folder_service.delete_folder` both refuse it outright (`Cannot modify the default folder`). It gets no long press at all — not a menu with greyed-out rows, and no long-press accessibility hint either.

The grid is rendered by the same `CollectionTile` in both bodies of the screen — the idle library and the name-filtered list a typed query shows. The long press therefore works in both, which is intended: it is one component and one gesture.

## The route: generalize the menu, do not clone it

`MediaContextMenu` is typed on `MediaListItem` and hardcodes three rows (`MENU_HEIGHT = ROW_HEIGHT * 3 + …`). It must become the anchored-menu shell for both targets — an ordered list of rows plus a `renderPreview`, with the card height derived from the number of rows and dividers instead of a constant tied to three. A second file duplicating the blur backdrop, the lifted preview and the up/down geometry is the failure mode to avoid: the whole reason `useMediaActions` exists is that the two Library surfaces share one implementation of the destructive path.

Same for the rename field. `MediaRenameDialog` is one input, Cancel/Save and an inline error; only its heading, placeholder and `MAX_TITLE_LENGTH` are about media. Parameterize those three — a collection name is bounded at **255** by `UpdateFolderRequest`, not 120.

The behaviour belongs in a sibling of `useMediaActions` (which media/collection is targeted, the confirmation, the calls, the local state patch), not inside the tile.

## Backend: already there, with one gap

Nothing has to be built. `PUT /api/folders/{folder_id}` renames and `DELETE /api/folders/{folder_id}` deletes (`media_summarizer/api/endpoints/folders.py:138` and `:184`), both already deployed. `OrganizationService` needs the two matching methods.

Two facts the client must get right:

- **The rename body carries `name` only.** `update_folder` decides "move to root" from `payload.model_fields_set`, so sending `parent_folder_id: null` alongside the name would silently reparent the collection.
- **A delete is not scoped to the one collection.** `folder_service.delete_folder` collects the whole descendant subtree, moves every media of every folder in it to the default folder, then deletes all of them. Media are never destroyed; sub-collections are. The confirmation has to say exactly that, and the client already knows the subtree size — `buildCollectionTree` returns `children`.

The gap: `UpdateFolderRequest.name` is `min_length=1`, and the service does `folder.name = name.strip()`. So `"   "` passes validation and stores an empty name. Close it, the same way task-346 did for the media title.

## Out of scope

Moving a collection to another parent (the API supports it, no UI asks for it). The orphaned collections explorer `mobile/app/media/collections/index.tsx`, which is declared in `_layout.tsx` and reachable from nothing. `CollectionPickerView`. `/api/folders` is absent from `docs/CANONICAL_MEDIA_API_CONTRACT.md` and stays absent — this task adds no endpoint.

## Notes for the owner (not acceptance criteria)

- **The mobile half works against the deployed dev API immediately** — `PUT`/`DELETE /api/folders` have been live for a long time. Only the blank-name rejection waits for `main` to be pushed and the Lambda image redeployed.
- The visual match is yours to judge. The interesting case is a tile in the **third column**: the menu card is 240pt wide against a tile of about a third of the screen, so it will be pulled back inside the gutter by the existing clamp rather than left-aligned on the tile. Check a tile on the **last row** too, for the upward flip. And check Android, which renders the same menu by construction.
- Deleting a collection that has sub-collections is the one destructive path worth trying by hand on dev: the sub-collections go, the media come back in Unsorted.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 A long press on a collection tile in the Library tab opens the anchored context menu, positioned from a `measureInWindow` of the pressed tile, with a copy of that tile lifted above the blurred backdrop.
- [x] #2 The tile of the default collection (`is_default === true`) has no long-press handler and no long-press accessibility hint: pressing it long does nothing at all, rather than opening a menu with disabled rows.
- [x] #3 The collection menu offers exactly two actions, Rename then Delete, separated by the hairline divider, with Delete tinted `Colors.error` from `mobile/src/constants/theme`.
- [x] #4 One anchored-menu component serves both targets: no second file in `mobile/src/components/` duplicates the blur backdrop, the lifted preview or the below/above placement logic, and the card height is derived from the rows it was given instead of the `ROW_HEIGHT * 3` constant.
- [x] #5 One rename dialog component serves both targets, with its heading, placeholder and maximum length passed in: 255 for a collection name (the bound of `UpdateFolderRequest`), 120 for a media title.
- [x] #6 `OrganizationService` gains a rename and a delete for collections, calling `PUT /api/folders/:id` and `DELETE /api/folders/:id`; the rename body carries `name` only, with no `parent_folder_id` key, so the backend reads no parent change.
- [x] #7 The delete confirmation names the collection and states what the backend actually does — its sub-collections are deleted and every media inside moves to Unsorted, none is deleted — and it states how many sub-collections are involved when there are any.
- [x] #8 Once the API confirms a rename, the tile shows the new name without leaving the screen; once it confirms a delete, the tile is gone and both halves of the screen are refetched, since the media of the deleted subtree changed collection and its sub-collections no longer exist.
- [x] #9 A failed rename keeps the dialog open with the typed name and the old name on the tile, and a failed delete leaves the grid untouched; both report a translated message from `mobile/src/i18n`, never a raw HTTP or provider string.
- [x] #10 `PUT /api/folders/{folder_id}` refuses a blank or whitespace-only name with a 4xx instead of storing an empty name, and the bound is stated in the field definition.
- [x] #11 Every i18n key introduced by the collection menu, its rename dialog and its delete confirmation exists in all eleven catalogs under `mobile/src/i18n/` (ar, de, en, es, fr, hi, it, ja, nl, pt, zh).
- [x] #12 `npx tsc --noEmit` and `npm run lint` in `mobile/` report no error, and `ruff check media_summarizer` plus `mypy media_summarizer` are clean.
- [x] #13 Run through `folder_service` against the real `-dev` tables on a throwaway collection holding one media and one sub-collection: after the rename the row carries the new name, after the delete the whole subtree is gone and the media points at the default folder, and both operations are refused on the default folder.
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
### What the generalization produced

`MediaContextMenu` and `MediaRenameDialog` are gone, renamed in place (no compatibility shim, no re-export):

- `mobile/src/components/AnchoredContextMenu.tsx` — generic over the target (`AnchoredContextMenu<T>`), driven by an ordered `actions: MenuAction[]` array plus `renderPreview(target)`. The card height is `ROW_HEIGHT * actions.length + CARD_PADDING_VERTICAL * 2 + hairline * dividers`, and the divider count is derived from the same `destructive` flag the renderer uses, so geometry and rendering cannot drift. The up/down flip still needs the height in the frame the gesture is handled, which is why it is computed rather than measured.
- `mobile/src/components/RenameDialog.tsx` — `heading`, `placeholder`, `maxLength` and `testIDPrefix` are props. 120 for a media title, 255 for a collection name (the `UpdateFolderRequest` bound).
- Call sites updated: `mobile/app/(tabs)/search.tsx`, `mobile/app/media/collections/[id].tsx`, `mobile/src/components/MediaListCard.tsx` (its `AnchorRect` import).

`mobile/src/hooks/useCollectionActions.ts` is the sibling of `useMediaActions`: it owns the target, the confirmation, the two service calls and the local patch. The tile knows nothing about any of it.

The default-collection exclusion lives in exactly one place, inside `CollectionTile`: `const longPress = isDefault ? undefined : onLongPress;`. Both grids (idle library and filtered list) pass the handler unconditionally, so neither can forget the rule, and the `accessibilityHint` is bound to the same `longPress` value.

The measured element is the tile's outer slot `View` (`collapsable={false}`, required or Android flattens it away), and the lifted preview re-renders the same `CollectionTile` with `collectionTilePreview` (`width: "100%"`, `marginBottom: 0`) so the copy lands exactly on the measured rect.

A delete is not patched like a rename: the confirmed subtree ids are removed from the flat `folders` state at once (the tile disappears immediately) and *then* both halves are refetched, because only the server knows the new `media_count` of Unsorted and the new `folder_id` of the moved media.

`testIDPrefix` moved from `media-actions`/`media-rename` on the media surface to `collection-actions`/`collection-rename` on the collection one. No Maestro flow and no doc referenced the old ids.

### Backend gap (AC #10)

`normalize_folder_name` in `folder_service` is the folder twin of `media_rename_service.normalize_title`: it trims, collapses inner runs of whitespace, and refuses blank or over-255. It is called by both `create_folder` and `update_folder`, which is the layer that matters — pydantic field validators run on *construction*, and a rename assigns the attribute of an already-built `Folder`. `CreateFolderRequest.name` and `UpdateFolderRequest.name` also got a `field_validator` so the API answers 422 rather than 500, and `MAX_FOLDER_NAME_LENGTH` is now the single source of the bound.

### Verification

- `tsc --noEmit`: clean. `eslint . --ext .ts,.tsx`: 0 errors, 2 warnings, both pre-existing in files this task did not touch (`app/(tabs)/digest.tsx:36`, `src/services/purchaseService.ts:98`). `ruff check media_summarizer`: all checks passed. `mypy media_summarizer`: no issues in 180 source files.
- AC #11 is proven by `tsc` itself: `TranslationKey = keyof typeof en`, so a key present in `en.ts` and missing from any of the ten other catalogs is a compile error. `ar.ts` also carries the `two`/`few`/`many` plural entries for `collectionActions.deleteSubCollections` (no `zero`: the sentence only renders for a count of 1 or more). `pseudo.ts` is derived at runtime and needs nothing.
- AC #13 ran against the real `-dev` DynamoDB tables (`user_folders-dev`, `user_media-dev`, `eu-west-3`) through `folder_service`, on a synthetic user id, from a throwaway script kept outside the repository and deleted after the run. Every assertion passed: creation collapses `"   Throwaway    collection   "` to `"Throwaway collection"`; the rename re-read from DynamoDB carries the new name; a `"   "` rename and a 256-character rename are both refused and leave the stored name untouched; rename and delete are both refused on the default folder; deleting the parent returned `deleted_folders: 2, moved_media_count: 2`, both folder rows are gone, and both media rows point at the default folder. The script hard-deleted everything it created and a filtered scan of both tables confirms zero residue.

### Left to the owner

The visual checks the description already flagged, none of which is an acceptance criterion: a third-column tile (the 240pt card gets clamped back inside the gutter), a last-row tile (upward flip), and Android. The 422 on a blank name only reaches the dev API once `main` is pushed and the Lambda image is rebuilt — the equivalent was verified at the service layer instead.
<!-- SECTION:NOTES:END -->
