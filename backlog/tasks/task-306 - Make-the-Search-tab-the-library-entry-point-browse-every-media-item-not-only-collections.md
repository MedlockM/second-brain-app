---
id: task-306
title: >-
  Make the Search tab the library entry point: browse every media item, not only
  collections
status: Done
assignee: []
created_date: '2026-08-20 16:17'
updated_date: '2026-08-20 18:45'
labels:
  - mobile
  - ui
  - search
  - phase-6
dependencies: []
priority: high
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
The Inbox is currently the only screen in the app that lists **every** media item: `mobile/app/(tabs)/inbox.tsx` renders a `FlatList` over `useMediaPolling()`. The Home redesign that follows this task removes that list — the owner's reference screenshot has two horizontal rows and nothing else — so the exhaustive library has to live somewhere first. This task moves it, **before** the Inbox stops carrying it, so no state of `main` ever leaves the library unreachable.

## Current state of the Search tab

`mobile/app/(tabs)/search.tsx` has a floating glassy search pill and two mutually exclusive bodies: with no query typed it renders `CollectionsState` — **collections only** — and once a query is typed it renders Algolia hits through `SearchService`. Collections come from `OrganizationService.getUserCollections()` reshaped by `buildCollectionTree`. There is no way to see a flat list of everything you saved, and no way to reach a media item that has not been indexed for search yet.

## What to build

The idle state (no query typed) becomes a real library: **the collections *and* the full list of saved media, newest first**. `MediaService.listMedia()` (`mobile/src/services/mediaService.ts:74`) takes no parameters and returns the whole library already sorted `saved_at` DESC server-side (`core/services/media_search_service.py:107`), so no new endpoint is needed.

Decide how the two coexist and state the reason in the code: one scroll with a collections section above a media section, or a two-way segmented control — `mobile/src/components/ScreenTabs.tsx` already exists for exactly that split and is the design-system answer if you choose it.

Rows reuse `mobile/src/components/MediaListCard.tsx`, which is **dead code today**: it is imported nowhere, and the only mention of it is a comment at `mobile/app/media/collections/[id].tsx:49` explaining it is deliberately not used there. Either it becomes the row this screen renders, or it gets deleted — an unused component must not survive this task (`AGENTS.md`, "Nothing is deployed yet"). It already reads `item.media_image`; render that image when the field is non-empty and fall back to the media-type icon otherwise. That field is now actually populated — task-304 shipped covers and `creator_name` for every source on 2026-08-20 and installed `expo-image` — so use `expo-image` here too rather than React Native's `Image`, and show the creator on the row if it fits the layout. This task still does not depend on that one: an imageless row degrades to the icon.

Behaviour the screen must have: pull-to-refresh, a refetch when the tab regains focus (it already does this for collections via `useFocusEffect`), an empty state that says the library is empty rather than showing a blank area, and an error state with a retry that does not wipe whichever half loaded successfully.

## Constraints

- **Do not touch the Inbox.** Its list stays exactly as it is until the Home redesign removes it. Two tasks editing `inbox.tsx` in parallel worktrees is a merge conflict for nothing.
- **Four Maestro anchors in `mobile/.maestro/06_search.yaml` must keep working**: the `search-tab-button` tab id, the placeholder text `Search your library...`, the `search-input` id and the `search-result-card` id. If the tab's visible label becomes "Library", the `tabBarButtonTestID` still stays `search-tab-button`.
- The search behaviour itself is unchanged: typing still shows Algolia hits, clearing the query still returns to the idle state — which now shows the library instead of only collections.
- Give the new list a `testID` in the style of the neighbouring ones so a flow can assert it later.
- Amber Clarity tokens only (`mobile/src/constants/theme.ts`): no new colour, no hardcoded hex, no new shadow recipe.
- No automated tests unless the owner asks (`AGENTS.md`). `cd mobile && npm run typecheck && npm run lint` clean.

## Owner notes (not acceptance criteria)

- Whether the label of that tab should read "Search" or "Library" is a call only you can make on a simulator; the implementer keeps the id stable either way, so switching the word later is a one-line change.
- The visual density of a long library list next to the collections cards cannot be judged from the code. The implementer will put its layout choice and the component's style block in the Implementation Notes so you can read it without building.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 With no query typed, the Search tab shows the user's collections and a list of every saved media item, newest first, both reachable without typing anything
- [x] #2 The media list is fed by MediaService.listMedia() with no new endpoint added, and the Implementation Notes state how collections and media coexist on the screen and why that layout was chosen
- [x] #3 MediaListCard is either the component rendering the library rows or it is deleted — no unused component named MediaListCard remains in mobile/src/components
- [x] #4 A row renders the stored cover image when media_image is non-empty and falls back to the media-type icon otherwise, with no empty grey placeholder in either case
- [x] #5 The screen supports pull-to-refresh and refetches on focus, and a failure loading one half (collections or media) leaves the other half rendered with a retry available
- [x] #6 An empty library renders an explicit empty state rather than a blank area
- [x] #7 search-tab-button, the 'Search your library...' placeholder, search-input and search-result-card are all still present and unchanged, so mobile/.maestro/06_search.yaml still resolves every anchor it uses
- [x] #8 Typing a query still renders Algolia hits and clearing it returns to the library view — the search path itself is unchanged
- [x] #9 mobile/app/(tabs)/inbox.tsx is not modified by this task
- [x] #10 The new list carries a testID consistent with the existing ones, uses only theme.ts tokens, and cd mobile && npm run typecheck && npm run lint are clean
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
### Layout: one scroll, not a segmented control (AC #2)

The idle body of the tab is a single `FlatList` over the media, with the collections grid riding in its `ListHeaderComponent` — `LibraryState` / `LibraryHeader` in `mobile/app/(tabs)/search.tsx`. `ScreenTabs` was the other candidate and was rejected for two reasons, both written in the component's doc comment:

1. **The failure requirement decides it.** The two halves come from two independent requests and the screen must keep one usable when the other fails. Side by side in one scroll, the error card sits *next to* the half that loaded; behind a segmented control it would sit behind a tab the user has no reason to open, and a user who never taps "Collections" would never learn that half is broken.
2. **The chrome budget.** The search pill already floats over the top of this screen. A segmented control underneath it would be a second bar of navigation on a screen whose entire job is to show what you saved.

The accepted cost: a user with many collections scrolls past the grid to reach the media. The grid is three tiles wide, so it stays compact, and the scroll is what the screen is for. Section order is Collections → All media, each under a `Typography.headline` title; the media heading carries a muted `N items` count on its right, omitted at zero.

### Data (AC #1, #2)

Two loaders, two flag pairs, no new endpoint:

- `loadCollections()` → `OrganizationService.getUserCollections()` → `buildCollectionTree`. The `MediaService.listMedia()` call that used to sit inside it only computed `directCountById`, which this screen never displayed; that dead computation is gone, and the counts still work where they *are* displayed (`app/media/collections/index.tsx`).
- `loadMedia()` → `MediaService.listMedia()`, rendered in the order returned. `GET /api/media` already sorts the whole library `saved_at` DESC server-side (`core/services/media_search_service.py`), so there is no client-side sort to disagree with it.

Neither loader throws — each owns its error state — so callers can await both and only have their own spinner to clear.

### Refresh, focus and independent failure (AC #5)

- `useFocusEffect` fires both loaders on every focus. The two loading flags are only ever *cleared*: they belong to the first load, so a later focus refetches silently under the content already on screen instead of flashing a spinner over it (the previous code set `collectionsLoading = true` on every focus, which blanked the screen each time the tab regained focus).
- `RefreshControl` on the one scroll reloads both halves, with `progressViewOffset={CONTENT_TOP_INSET}` so the spinner is not drawn underneath the floating pill.
- Collections fail → an `InlineErrorCard` with a Retry replaces the grid, the media list below is untouched. Media fail → the same card takes the place of the rows via `ListEmptyComponent`, the grid above is untouched. Rows already fetched are never dropped for an error: if a *refresh* fails with rows on screen, the card is appended as `ListFooterComponent` so the failure is stated instead of leaving stale rows silently.
- `InlineErrorCard` is a `surfaceContainer` block with no stroke (No-Line rule), not an alert.

### `MediaListCard` becomes the library row (AC #3, #4)

It was imported nowhere; it is now the row this list renders, and it gained the cover:

- `expo-image` (installed by task-304, plugin already registered in `app.config.ts`) with the exact prop set the task-302 README §6.2 specifies: a `source` carrying the URL plus a `cacheKey` of `media_item_id` + `:` + `updated_at`, then `recyclingKey`, `cachePolicy="memory-disk"`, `contentFit="cover"`, `transition={150}`, `priority="low"`, `onError`.
- **16:9, 112×63**, the ratio validated in §6.4. The container is the cover's frame *and* the fallback surface, so a row with a picture and a row without have the same silhouette. No cover, or `onError`: the media-type Ionicon on `surfaceContainerLow`. Never an empty grey rectangle (§6.3).
- The failure is recorded as `failedCoverId` (a media id), not a boolean: a `FlatList` cell can be handed a different item, and a failure recorded for the previous one must not hide the new one's cover.
- Second line = `creator_name`, falling back to the source domain (five sources can never have a creator). The two are never stacked, so the row keeps one metadata line whatever the source. Colour is `Colors.textSubtle` — it is text to read, not decoration.
- The two hardcoded `fontSize: 11` inherited from the inbox vignette are now `Typography.small.fontSize`.

Style block, so the density is readable without a build:

```
card:      surface, BorderRadius.xl, padding Spacing.sm + 4, marginHorizontal Spacing.md,
           marginBottom Spacing.md, minHeight TouchTarget.comfortable, Shadows.soft
cardContent: row, alignItems center, gap Spacing.md
coverContainer: 112 x 63, BorderRadius.lg, surfaceContainerLow, overflow hidden
cardTextSection: flex 1, paddingVertical Spacing.xs, gap 2
cardMeta:  row, gap Spacing.sm, marginBottom Spacing.xs  (type badge + relative time)
cardTitle: Typography.body.fontSize, 700, lineHeight 22, numberOfLines 2
cardSubtitle: Typography.small.fontSize, Colors.textSubtle, numberOfLines 1
```

Row height is therefore driven by the text (~95 px for a one-line title, ~119 px for two), not by the 63 px cover.

### Tab label (owner note)

The visible label is now **Library** with the `library-outline` glyph; `tabBarButtonTestID` stays `search-tab-button`. Reasoning in the comment at the `Tabs.Screen`: the tab holds the library, with the search over it in a pill, so it is named for the content rather than for one of the two ways to reach it. No Maestro flow asserts the label text (checked: `06_search.yaml` only uses the id), and switching the word back is one line.

### Maestro anchors (AC #7, #8)

All four still exist, unchanged, and were verified by reading the code — no run is claimed here (Maestro is owner-triggered): `search-tab-button` (`app/(tabs)/_layout.tsx`), the `Search your library...` placeholder, `search-input` and `search-result-card` (`app/(tabs)/search.tsx`). The search path itself is untouched: same debounce, same `SearchService.searchTranscripts`, same `hasSearched` gate — clearing the query resets `hasSearched` and the library comes back.

### Not done

- **Inbox untouched** (AC #9): `mobile/app/(tabs)/inbox.tsx` is not in the diff. Its list stays until task-307 removes it.
- **No automated tests** (`AGENTS.md`). The new list carries `testID="library-media-list"` and each row `testID="library-media-card"` so a flow can assert them later; no flow was added or edited.
- **No simulator check.** Tile density, the 16:9 crop on square podcast artwork and the vertical cost of the collections grid above a long list can only be judged on a device — hence the style block above.

### Checks

- `cd mobile && npm run typecheck` — clean
- `cd mobile && npm run lint` — 0 errors, 2 pre-existing warnings, both in files this task did not touch (`digest.tsx`, `purchaseService.ts`). The two warnings that *were* in `_layout.tsx` (an unused `Typography` import and an unused `IoniconsName` type) are deleted, since the file was being edited anyway.
<!-- SECTION:NOTES:END -->
