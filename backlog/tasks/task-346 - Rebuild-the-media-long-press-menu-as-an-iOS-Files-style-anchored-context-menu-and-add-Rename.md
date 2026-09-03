---
id: task-346
title: >-
  Rebuild the media long-press menu as an iOS Files style anchored context menu,
  and add Rename
status: To Do
assignee: []
created_date: '2026-09-03 12:10'
labels:
  - mobile
  - feature
dependencies: []
priority: medium
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
## What is there today

A long press on a media vignette opens `mobile/src/components/MediaActionsSheet.tsx`: a bottom sheet sliding up from the bottom edge, with an eyebrow ("Gérer la source"), the media title, two large rows carrying an icon in a circle, a label, a description line and a trailing chevron, then a Cancel button. Two actions: Move and Delete. `mobile/src/hooks/useMediaActions.ts` owns the behaviour (which media is targeted, the destructive confirmation, the navigation to the collection picker); the sheet is the surface only. Three surfaces feed it: `mobile/app/(tabs)/search.tsx`, `mobile/app/media/collections/[id].tsx`, and `mobile/src/components/MediaListCard.tsx` which carries the `onLongPress` prop.

The owner does not want a bottom sheet. He wants the menu of the **iOS Files app**.

## The target

Three reference screenshots were reviewed with the owner. What defines the look, and what must be reproduced:

- **The menu is anchored to the pressed item, not to the bottom of the screen.** It appears next to the vignette that was long-pressed and stays there; it does not slide up from the bottom edge.
- **The rest of the screen is blurred and dimmed**, and the pressed vignette is **lifted above that blur** at a slightly larger scale — it is the only sharp thing besides the menu. In the screenshots the underlying list and the tab bar are legible but heavily blurred.
- **The menu is a single rounded, translucent dark card**, corner radius around 14pt, with the platform vibrancy look, not a flat opaque surface.
- **Rows are compact and single-line**: an icon on the left, then the label, nothing else. **No description line, no circled icon background, no trailing chevron** except where an action opens a submenu. This is the biggest departure from the current sheet, which is roughly twice as tall per row.
- **Rows are grouped into sections separated by a hairline divider** running the full width of the card.
- **There is no Cancel button and no drag handle.** Dismissal is a tap outside, on the blurred backdrop.

Two deliberate differences from the screenshots, decided with the owner:

- **No palette row of icons at the top** (the `Copier / Déplacer / Partager` row). It is not wanted.
- **Exactly three actions**: `Déplacer`, `Renommer`, `Supprimer`. `Supprimer` is destructive and tinted accordingly, and sits in its own section at the bottom.

## The technical route, already decided — do not re-open it

The menu is **reimplemented in JS**, with no new native dependency. Route weighed against `zeego` / `react-native-ios-context-menu` and rejected in favour of this one on 2026-09-03, for reasons that hold: the visual fidelity is required on **both** platforms and Android is the project's current shipping path, a system `UIMenu` cannot be styled, and `mobile/package.json` carries **neither `react-native-reanimated` nor `react-native-gesture-handler`** — adding either on RN 0.83 with the New Architecture is a risk this menu does not need.

The pieces to build with:

- `expo-blur` (`~55.0.17`) is **already a dependency** — it provides the backdrop.
- The `Animated` API of React Native core is enough. The animation is a scale + opacity on the lifted vignette and on the menu card; there is no continuous drag gesture here, which is the only thing that would have justified Reanimated.
- Anchoring is `measureInWindow` on the pressed row, taken at long-press time and handed to the overlay. The menu opens **downwards from the vignette when there is room below, upwards otherwise** — a vignette near the bottom of the list must not push the menu off screen. The same measurement positions the lifted copy of the vignette.
- `expo-haptics` may be added if a press feedback is wanted on open; it is an Expo module with no configuration cost. Nothing else new.

The three call sites keep handing a `MediaListItem` to `useMediaActions().open` — the controller API does not have to change shape, but the sheet component is replaced, not kept alongside. There is no installed base: delete `MediaActionsSheet.tsx` and its now-unused i18n keys (`mediaActions.*.description`, `mediaActions.eyebrow`) in the same run rather than leaving them behind.

## Rename is new, and it goes all the way down

`Renommer` does not exist anywhere today. It needs the full vertical slice:

- **Backend.** `PATCH /api/media/{media_id}` exists (`media_summarizer/api/endpoints/media.py:1726`) but its `PatchMediaRequest` (`:270`) carries only `folder_id`, and the handler routes everything to `folder_service.assign_folder_to_media`. It has to accept a title as well, and dispatch: a title update goes to `user_media.update_attributes` (`media_summarizer/utils/user_media.py:604`), which already does attribute-level `SET` and does not list `title` among `_IMMUTABLE_ATTRS` — so the storage path exists and needs no new primitive. Ownership is the `(user_id, media_item_id)` key itself, as for the folder move.
- **Search index.** The title is **denormalized into every transcript chunk** in Algolia (`media_summarizer/core/services/search_indexing.py:158`, and it is both a searchable and a highlighted attribute at `:315` / `:321`). A rename that does not refresh those chunks leaves the search results showing the old name and matching on it. Update the `title` attribute on that media's chunks (they are selectable by `filters: media_item_id:<id>`, the same predicate `_delete_chunks_for_media` already uses at `:189`).
- **Mobile.** An input surface for the new name, prefilled with the current title, and the renamed title visible without a manual refresh on the surface the rename was triggered from.

Keep it a plain rename of the user-facing title. Nothing about identity, dedup keys, `media_key` or the artifacts is in scope.

## Notes for the owner (not acceptance criteria)

- The visual match is yours to judge: the implementing agent cannot see the running app. Compare the built app against your three screenshots on a real device, in both the library list and inside a collection, and on a vignette at the very bottom of the list to check the upward flip.
- The rename only reaches the API once `main` is pushed and the Lambda image is redeployed. Until then the mobile side will get a `422` from the deployed API on the new field.
- Android will render the same menu, by construction — check it there too, since it is the platform your internal builds go to.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 `mobile/src/components/MediaActionsSheet.tsx` no longer exists; the long press on a media vignette opens a new anchored context-menu component, and `grep -rn "MediaActionsSheet" mobile/` returns nothing.
- [ ] #2 The menu is positioned from a `measureInWindow` of the pressed vignette rather than pinned to the bottom of the screen, and the code chooses between opening below and opening above depending on the room left under the vignette.
- [ ] #3 The backdrop is an `expo-blur` view over the screen, and a copy of the pressed vignette is drawn above it at an enlarged scale, so the pressed item is the only unblurred content besides the menu card.
- [ ] #4 The menu card is a single rounded translucent surface whose rows are single-line — icon plus label only, with no description text, no circled icon container and no trailing chevron — and the destructive row is separated from the others by a hairline divider.
- [ ] #5 There is no Cancel button and no drag handle in the menu; a press on the backdrop dismisses it, and that dismissal target carries an accessibility label.
- [ ] #6 The menu offers exactly three actions — Move, Rename, Delete — with Delete tinted with the destructive colour of `mobile/src/constants/theme`.
- [ ] #7 No new native dependency is added: `mobile/package.json` gains neither `react-native-reanimated` nor `react-native-gesture-handler` nor any context-menu library; the animation uses the `Animated` API of React Native core.
- [ ] #8 `PatchMediaRequest` in `media_summarizer/api/endpoints/media.py` accepts an optional title, and `patch_media` writes it through `user_media.update_attributes` while still routing a `folder_id` to `folder_service.assign_folder_to_media`; a request carrying neither field is refused with a 4xx rather than silently succeeding.
- [ ] #9 A blank or whitespace-only title is refused by the API, and the accepted length bound is stated in the field definition rather than left implicit.
- [ ] #10 Renaming updates the denormalized `title` on that media's Algolia chunks, selected by the `media_item_id` filter, so a subsequent search matches and displays the new name.
- [ ] #11 The mobile rename entry point prefills the current title and, once the API confirms, the new title is shown on the originating surface without requiring the user to leave and come back.
- [ ] #12 A failed rename leaves the displayed title unchanged and surfaces a translated message from `mobile/src/i18n`, never a raw provider or HTTP string.
- [ ] #13 Every i18n key the new menu introduces exists in all catalogs under `mobile/src/i18n/` (ar, de, en, es, fr, hi, it, ja, nl, pt, zh), and the keys the removed sheet no longer uses — including `mediaActions.eyebrow` and the `*.description` entries — are deleted from all of them.
- [ ] #14 `ruff check media_summarizer` and `mypy media_summarizer` are clean, and `npx tsc --noEmit` plus `npm run lint` in `mobile/` report no error.
- [ ] #15 A `PATCH` carrying a new title, issued against the real `-dev` API or applied through the same code path onto the `-dev` DynamoDB table, is readable back on the `user_media` row with the new title and an unchanged `media_key` and `saved_at`.
- [ ] #16 `docs/CANONICAL_MEDIA_API_CONTRACT.md` documents the title field of `PATCH /api/media/{media_id}` and its validation, and `docs/CANONICAL_MEDIA_API_OPENAPI.yaml` matches.
<!-- AC:END -->
