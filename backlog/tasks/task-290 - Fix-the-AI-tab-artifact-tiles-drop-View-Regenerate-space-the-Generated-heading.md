---
id: task-290
title: >-
  Fix the AI tab artifact tiles: drop View/Regenerate, space the Generated
  heading
status: To Do
assignee: []
created_date: '2026-08-18 16:25'
labels:
  - mobile
  - ui
  - bug
dependencies: []
priority: medium
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Two UI defects visible on the AI tab, both in `mobile/src/components/ArtifactTile.tsx` and its two host screens (`mobile/app/media/[id].tsx` and `mobile/app/media/collections/[id].tsx`).

**1. Unreadable label once an artifact is ready.** When a generation completes, the tile shows *two* buttons side by side ("View" + "Regenerate"). The action row takes so much width that the label column collapses and the text wraps mid-word — an owner screenshot shows "Detailed summary" broken as "Det / aile / d / su / m / ma / ry".

The fix is to remove both buttons rather than to squeeze the layout:

- **No "View" button.** Opening a generated artifact is the job of the `Generated` section below (`ArtifactHistoryRow`), which already routes to `/artifacts/<id>`. The tile duplicates it.
- **No "Regenerate" label.** Once generation is done the tile simply goes back to its original `Generate` button. Artifacts stay append-only — tapping `Generate` again still adds a new entry; only the wording changes.

Concretely: drop the `viewButton` branch and the `generateLabel` variable (`state.status === "idle" ? "Generate" : "Regenerate"`) so a `ready` tile renders the same `Generate` button as an `idle` one. The `onView` prop becomes unused — delete it from `ArtifactTileProps` and from both call sites; nothing is deployed, so no fallback or transition shape is kept. The `queued` / `generating` / `failed` (`Retry`) / `Processing...` states are unchanged.

**2. The `Generated` heading is glued to the Generate section.** In both screens the second `sectionTitle` sits directly under the last tile with no top spacing, which reads as unpolished. Add vertical separation above it (a `marginTop` on the heading, or a dedicated style — the existing `sectionTitle` is shared with the first heading, so do not add top margin that would also push the first one down).

Both fixes must land for the media AI tab **and** the collection AI tab.

**Owner note (not an AC):** the visual result can only be confirmed by the owner running the app on a simulator/device — check a media item with at least one `ready` artifact (long label like "Detailed summary") and the same on a collection.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 `mobile/src/components/ArtifactTile.tsx` no longer renders a "View" button in any state: the `viewButton`/`viewButtonText` styles and the `isReady` branch are gone from the file.
- [ ] #2 `ArtifactTile` never renders the word "Regenerate": the `generateLabel` variable is removed and a tile whose state is `ready` renders the same `Generate` button (same style, same testID pattern) as a tile whose state is `idle`.
- [ ] #3 The `onView` prop is removed from `ArtifactTileProps` and from both call sites (`mobile/app/media/[id].tsx`, `mobile/app/media/collections/[id].tsx`); grep for `onView` in `mobile/` returns no hit tied to `ArtifactTile`.
- [ ] #4 The `queued`, `generating`, `failed` (Retry) and `!sourceReady` (`Processing...`) states are behaviourally unchanged.
- [ ] #5 The `Generated` heading has explicit vertical spacing above it in both `mobile/app/media/[id].tsx` and `mobile/app/media/collections/[id].tsx`, without adding top spacing to the `Generate` heading that precedes the tiles.
- [ ] #6 `npx tsc --noEmit` and the lint command declared in `mobile/package.json` both pass from `mobile/`.
<!-- AC:END -->
