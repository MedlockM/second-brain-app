---
id: task-306
title: >-
  Make the Search tab the library entry point: browse every media item, not only
  collections
status: To Do
assignee: []
created_date: '2026-08-20 16:17'
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
- [ ] #1 With no query typed, the Search tab shows the user's collections and a list of every saved media item, newest first, both reachable without typing anything
- [ ] #2 The media list is fed by MediaService.listMedia() with no new endpoint added, and the Implementation Notes state how collections and media coexist on the screen and why that layout was chosen
- [ ] #3 MediaListCard is either the component rendering the library rows or it is deleted — no unused component named MediaListCard remains in mobile/src/components
- [ ] #4 A row renders the stored cover image when media_image is non-empty and falls back to the media-type icon otherwise, with no empty grey placeholder in either case
- [ ] #5 The screen supports pull-to-refresh and refetches on focus, and a failure loading one half (collections or media) leaves the other half rendered with a retry available
- [ ] #6 An empty library renders an explicit empty state rather than a blank area
- [ ] #7 search-tab-button, the 'Search your library...' placeholder, search-input and search-result-card are all still present and unchanged, so mobile/.maestro/06_search.yaml still resolves every anchor it uses
- [ ] #8 Typing a query still renders Algolia hits and clearing it returns to the library view — the search path itself is unchanged
- [ ] #9 mobile/app/(tabs)/inbox.tsx is not modified by this task
- [ ] #10 The new list carries a testID consistent with the existing ones, uses only theme.ts tokens, and cd mobile && npm run typecheck && npm run lint are clean
<!-- AC:END -->
