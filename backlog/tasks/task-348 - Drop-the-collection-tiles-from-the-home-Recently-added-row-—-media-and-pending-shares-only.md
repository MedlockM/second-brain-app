---
id: task-348
title: >-
  Drop the collection tiles from the home "Recently added" row — media and
  pending shares only
status: To Do
assignee: []
created_date: '2026-09-03 12:32'
labels:
  - mobile
  - ui
dependencies: []
priority: medium
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
## What the owner sees

Save a media, and from the confirmation screen create a collection to file it into. Back on the home screen, the "Recently added" row shows **two** tiles for that one action: the media, and a tile for the collection that was just created. The owner does not want collections in that row at all — "Recently added" is about what just arrived to read, and a folder is not that. The row must list media (and the shares still uploading), nothing else.

## Where the tile comes from

`mobile/app/(tabs)/inbox.tsx:478-528`, `buildRecentlyAdded`, merges three sources into one row: the pending local shares at the head, then the media items and the user's collections interleaved on their `created_at`. The collections arrive from `useHomeSections` (`mobile/src/hooks/useHomeSections.ts:57-71`), which fetches them for two independent reasons — this merge, and the `media_count` behind the unsorted review button (`inbox.tsx:193-196`). Only the first one goes away.

Each collection tile also draws a mosaic of covers borrowed from the media list already in hand, built by `indexCoversByCollection` (`inbox.tsx:539-552`) under the `MAX_COLLECTION_PREVIEWS` cap (`inbox.tsx:85`). That helper exists for this row and nothing else.

## What to change

`buildRecentlyAdded` takes the media list and the pending shares only: pending tiles first (unchanged — that head position is what makes a fresh share visible on return from the confirmation screen), then the media newest-first on `created_at`, capped at `RECENTLY_ADDED_LIMIT`. No collection enters the row, whatever its age or its item count.

## Dead code to delete in the same run

- `indexCoversByCollection` and `MAX_COLLECTION_PREVIEWS` in `inbox.tsx`. The collection tiles of "Continue learning" take their previews from the server (`entry.preview_images`, `inbox.tsx:449`), never from this helper, so it has no other caller.
- The `collections` parameter of `buildRecentlyAdded` and the matching `useMemo` dependency (`inbox.tsx:179-182`).
- `Collection.created_at` (`mobile/src/types/organization.ts:18`) and the line that fills it in `toCollection` (`mobile/src/services/organizationService.ts:65`): `inbox.tsx:511` is its only reader in the entire app. `FolderResponse.created_at` (`organizationService.ts:36`) stays — it describes the server payload, not the UI model.
- The comments that describe the merge, which become false the moment it is gone: the header of `buildRecentlyAdded` (`inbox.tsx:465-477`), the one on `indexCoversByCollection` (`inbox.tsx:530-538`), the screen header (`inbox.tsx:51-75`) where it mentions the two sources feeding that row, and the `collections` field doc in `useHomeSections.ts:22-24` and `:29-33` — which must keep stating that the collections are fetched for the unsorted count, and stop stating that they feed "Recently added".

`toTimestamp` (`inbox.tsx:554-557`) stays: the media side of the row keeps sorting on `created_at`.

## What stays, deliberately

- **"Continue learning" keeps its collection tiles.** A collection lands in that row when the user reads a collection-scoped artifact (`mobile/app/artifacts/[artifactId].tsx:195-197` reports `kind: "collection"`), and picking that reading back up is exactly the row's purpose. So `HomeTileItem`'s `collection` variant, its renderer in `mobile/src/components/HomeTile.tsx:207-260` and the `collection` branch of `handleTilePress` (`inbox.tsx:135-137`) are all still live, and nothing on the backend side is touched — `KIND_COLLECTION`, `_hydrate_collections` and the preview hydration in `media_summarizer/core/services/engagement_service.py` are out of scope.
- The unsorted review button keeps reading its count off the `collections` that `useHomeSections` fetches.

## Owner notes (deliberately not acceptance criteria)

- Visual check on a dev build or a Metro reload: save a media, create a collection from the confirmation screen, come back to the home — the row shows the new media and no collection tile. Then open a collection summary artifact and confirm the collection still appears under "Continue learning".
- `mobile/.maestro/03_inbox_visibility.yaml` asserts the "Recently added" heading and the pending-share tile only, never a collection tile, so that flow keeps its meaning unchanged.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 `buildRecentlyAdded` in `mobile/app/(tabs)/inbox.tsx` takes only the media list and the pending shares, and no code path builds a `kind: "collection"` tile for the "Recently added" row
- [x] #2 The row still puts the pending shares at the head, then the media newest-first on `created_at`, capped at `RECENTLY_ADDED_LIMIT`
- [x] #3 `indexCoversByCollection` and `MAX_COLLECTION_PREVIEWS` are deleted from `inbox.tsx` and no reference to either remains in `mobile/`
- [x] #4 `Collection.created_at` is deleted from `mobile/src/types/organization.ts` and from `toCollection` in `mobile/src/services/organizationService.ts`, while `FolderResponse.created_at` is left as is
- [x] #5 `useHomeSections` still fetches the collections and the unsorted review button still reads `media_count` off them; the hook's doc comment no longer says they feed "Recently added"
- [x] #6 The `collection` variant of `HomeTileItem`, its renderer in `mobile/src/components/HomeTile.tsx` and the `collection` branch of `handleTilePress` are unchanged, and no file under `media_summarizer/` is modified
- [x] #7 `npm run lint` and `npm run typecheck` are clean in `mobile/`
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
`buildRecentlyAdded` is now `(media, pending)`. The pending tiles keep the head
position, the media are mapped, sorted desc on `toTimestamp(created_at)` and the
concatenation is sliced at `RECENTLY_ADDED_LIMIT` — the two-source `dated` array
became a single chained map/sort/map over the media list, since only one kind of
tile is dated now. `toTimestamp` stays, it is what that sort reads.

Deleted in the same run: `indexCoversByCollection`, `MAX_COLLECTION_PREVIEWS`,
the `collections` argument and its `useMemo` dependency, the `Collection` type
import in `inbox.tsx` (nothing else in the file named the type), `Collection.created_at`
and the line filling it in `toCollection`. `FolderResponse.created_at` is
untouched: it declares the `GET /api/folders` payload. A grep over `mobile/` for
`created_at` confirms `inbox.tsx` held the only read of the collection field, and
`toCollection` is the only place a `Collection` is constructed, so removing the
field breaks no literal.

Comments corrected rather than left lying: the `buildRecentlyAdded` header, the
screen header paragraph on the two sources (it now says `useHomeSections` brings
the engagement row and the collections behind the unsorted count, not a row of
tiles), and both `collections` doc blocks in `useHomeSections.ts`. `HomeTile.tsx`
is untouched — its "one component for both rows alike" and its fixed-height
rationale mentioning a collection tile beside a media tile both stay true, since
"Continue learning" still mixes the two kinds.

Not verified here, by construction: the visual check on a dev build (owner note
in the description) and the Maestro flow. Nothing under `media_summarizer/` was
modified, and no automated test was added.
<!-- SECTION:NOTES:END -->
