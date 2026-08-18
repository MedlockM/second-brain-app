---
id: task-292
title: >-
  Unify the AI tab UI between a collection and a media item behind one shared
  component
status: To Do
assignee: []
created_date: '2026-08-18 16:42'
labels:
  - mobile
  - ui
  - refactor
dependencies: []
priority: medium
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
The AI tab exists twice — `mobile/app/media/[id].tsx` (media item) and `mobile/app/media/collections/[id].tsx` (collection, sub-component `AiTab`). Both render the same three blocks (a `Generate` heading + the five `ArtifactTile`s, an optional refusal banner, a `Generated` heading + the `ArtifactHistoryRow` history), but each one re-declares its own copy of the layout, so they have visibly drifted. The owner reports them as looking different; **they must be strictly identical**, with exactly one intended exception: the source count under an artifact title, which only makes sense for a collection.

## The divergences found (audit, not exhaustive by construction)

| Aspect | media `[id].tsx` | collection `[id].tsx` |
| --- | --- | --- |
| `sectionTitle` | `Typography.headline`, `Colors.textMain`, mixed case | `Typography.label`, weight `700`, `Colors.textMuted`, `textTransform: uppercase`, `letterSpacing: 0.5` |
| Horizontal gutter | `Spacing.lg`, inherited once from `scrollContent` | `Spacing.md`, re-applied per block (`tilePile`, `historyList`, `aiInlineState`, `sectionTitle`) |
| Refusal banner top margin | `Spacing.md` | `Spacing.lg` |
| History loading state | bare `ActivityIndicator` | `ActivityIndicator` + "Loading..." label |
| History load error | not rendered at all | message + `Retry` button |
| Empty-state copy | "Nothing generated yet. Pick a format above to create one." | "…create one from every source in this collection." |
| Inline state container | `historyState` (no `gap`) | `aiInlineState` (`gap: Spacing.sm`) |
| Source count | `showSourceCount={false}` | default `true` |

The two headings' styles are the most visible: identical text rendered as a large dark title on one screen and as a small muted uppercase caption on the other.

## Scope

Extract the whole tab into **one shared component** (e.g. `mobile/src/components/ArtifactsPanel.tsx`, alongside the already-shared `ArtifactTile` and `ArtifactHistoryRow`) and have both screens render it. Duplicated styling is the cause of the drift, so deleting the duplication is the fix — copying one screen's styles onto the other would just drift again.

The component owns the layout and the presentational states (headings, tile stack, refusal banner, loading / error / empty / populated history). Each screen keeps owning its data: fetching, polling, `tileStates`, `handleGenerate` and the refusal message stay where they are and are passed in. Both screens must keep their existing `testID`s (`media-ai-refusal`, `media-ai-history-empty`, `collection-ai-tab`, `collection-ai-refusal`, `collection-ai-history-empty`) so the Maestro flows keep resolving; scope-specific ones become props.

Resolve each divergence to a single value rather than parameterising it — a prop per difference reproduces the drift inside the component. Decisions to apply:

- **Headings**: keep the media screen's treatment (`Typography.headline`, `Colors.textMain`, mixed case) — a large title reads as a section opener; the uppercase muted caption is the style used for the collection's *Sources* list header and should stay confined to it.
- **Gutter**: one value applied by the component, matching the surrounding screen content.
- **Loading / error states**: keep the richer collection behaviour on both — labelled spinner, and a real error state with `Retry`. The media screen currently has no history-error branch; wiring the error through is part of the task.
- **Empty copy**: a single sentence for both scopes.
- **Refusal banner**: one top margin.

The only permitted scope-dependent behaviour is `showSourceCount`: `false` for a media item (a single source has nothing to say), `true` for a collection. `ArtifactHistoryRow` already takes that prop and needs no change.

Nothing is deployed: delete the now-dead styles from both screens (`sectionTitle`, `historyTitle`, `artifactsList`, `historyList`, `historyState`, `historyStateText`, `refusalBanner`, `refusalText` on the media side; `aiContent`, `tilePile`, `aiHistoryTitle`, `historyList`, `aiInlineState`, `aiInlineStateText`, `refusalBanner`, `refusalText` on the collection side) rather than leaving them behind. `sectionTitle` is also used by the collection's *Sources* list header — keep that one.

**Owner note (not an AC):** only the owner can confirm the visual parity, by opening the AI tab of a media item and of a collection on a simulator/device and comparing them side by side — including the empty history, an in-flight generation and a `ready` artifact.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 A shared component (e.g. `mobile/src/components/ArtifactsPanel.tsx`) renders the complete AI tab: the `Generate` heading, the `ARTIFACT_TILES` stack, the refusal banner, the `Generated` heading and the history in its loading / error / empty / populated states.
- [x] #2 `mobile/app/media/[id].tsx` and `mobile/app/media/collections/[id].tsx` both render that component and no longer contain any of their own JSX for those blocks.
- [x] #3 Neither screen declares layout or typography styles for the AI tab any more: the styles listed in the description are deleted from both `StyleSheet.create` blocks, except the `sectionTitle` still used by the collection's Sources list header.
- [x] #4 The `Generate` and `Generated` headings use `Typography.headline` with `Colors.textMain` and no `textTransform`, and render identically on both screens.
- [x] #5 The history error state (message + `Retry`) and the labelled loading spinner exist on both screens, including the media screen, which has no error branch today.
- [x] #6 The empty-history copy is one single string shared by both scopes.
- [x] #7 The only scope-dependent difference in the rendered tab is `showSourceCount`, passed to `ArtifactHistoryRow` as `false` from the media screen and `true` from the collection screen.
- [x] #8 The existing testIDs `collection-ai-tab`, `media-ai-refusal`, `collection-ai-refusal`, `media-ai-history-empty` and `collection-ai-history-empty` are still emitted with the same values; grep confirms each appears in the rendered tree.
- [x] #9 `npx tsc --noEmit` and the lint command declared in `mobile/package.json` both pass from `mobile/`.
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
`mobile/src/components/ArtifactsPanel.tsx` now owns the whole AI tab. Both screens
pass data only: `tileStates`, `sourceReady`, `onGenerate`, `refusal`, `history`,
`historyLoading`, `historyError`, `onRetryHistory`, `onOpenArtifact`, plus the two
scope `testID`s and `showSourceCount`. No prop parameterises a visual difference.

Resolutions applied to the divergences:

- headings: `Typography.headline` / `Colors.textMain` / mixed case, `marginBottom`
  `Spacing.md`, and `Spacing.lg` of air above the second one only;
- gutter: `Spacing.lg`, applied once by the panel. On the media screen it was
  removed from `scrollContent` and pushed onto `heroSection`, `tabsBar` and the new
  `readerContent` so it is not applied twice; `tabContent` is gone. On the
  collection screen `tabsContainer`, `sectionTitle` and `sourceRow` moved from
  `Spacing.md` to `Spacing.lg` — the screen's header was already at `lg`, and
  leaving the tab bar at `md` would have stepped 8px against the tiles below it;
- refusal banner: one `marginTop: Spacing.md`;
- loading: labelled spinner ("Loading...") on both;
- error: message + `Retry` (amber button, `Colors.onPrimary` label) on both. The
  media screen had no error branch: its artifact fetch used to swallow the failure
  in an empty `catch`, so a network error read as "nothing generated yet". It now
  mirrors the collection — `refreshArtifacts` sets `historyError` via
  `getFriendlyErrorMessage` and clears it on success, `historyLoaded` became
  `historyLoading`, and the polling loop and `handleGenerate` reuse the same call;
- empty copy: `EMPTY_HISTORY_COPY` in the panel, "Nothing generated yet. Pick a
  format above to create one." for both scopes.

Dead styles deleted: media `sectionTitle`, `historyTitle`, `artifactsList`,
`historyList`, `historyState`, `historyStateText`, `refusalBanner`, `refusalText`,
`tabContent`; collection `aiContent`, `tilePile`, `aiHistoryTitle`, `historyList`,
`aiInlineState`, `aiInlineStateText`, `refusalBanner`, `refusalText`. The
collection keeps `sectionTitle` for its Sources list header (the uppercase muted
caption now lives only there) and `retryButton` / `retryButtonText` for the
collection-load error state.

`sourceReady` stays a per-screen input rather than a style knob: a media item still
being transcribed cannot be generated from, a collection's sources always can.

Checks: `npm run typecheck` clean, `npm run lint` 0 errors (8 pre-existing warnings,
none in the touched files). No automated tests added, per the project rule.

Not verifiable from the worktree: the visual side-by-side parity of the two tabs
(empty history, in-flight generation, `ready` artifact) — that is the owner note in
the description and needs a simulator/device.
<!-- SECTION:NOTES:END -->
