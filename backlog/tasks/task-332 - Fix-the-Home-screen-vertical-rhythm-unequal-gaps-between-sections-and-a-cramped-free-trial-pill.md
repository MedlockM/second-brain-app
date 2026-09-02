---
id: task-332
title: >-
  Fix the Home screen vertical rhythm: unequal gaps between sections and a
  cramped free-trial pill
status: To Do
assignee: []
created_date: '2026-09-01 17:11'
labels:
  - mobile
  - ui
  - bug
dependencies: []
priority: medium
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Three spacing defects on Home, all in the same vertical column, all visible on the owner's 2026-09-01 19:00 Android screenshot. The screen is `mobile/app/(tabs)/inbox.tsx`.

**1. The gap between two sections is not constant.** Between the "Tri des non classés" card and the "Ajouts récents" heading the gap reads as one size; between the "Ajouts récents" row and the "Reprendre" heading it reads as clearly larger. The *declared* values are the same on both sides — `section.marginBottom: Spacing.lg` (`inbox.tsx:668`) — but that margin is measured from the bottom of the **tallest tile in the row**, and tiles in a row are not the same height: a collection tile renders a subtitle under its title (`mobile/src/components/HomeTile.tsx:378`, `marginTop: Spacing.xs` plus a `Typography.small` line, ≈ 20 dp) while a media tile renders only the title. On the screenshot "Ajouts récents" holds one media tile ("Photo — 01 Sep 2026") next to one collection tile ("Photos ordi" / "1 élément"), so the row box follows the collection tile and the void under the media tile is ~20 dp deeper than the 24 dp declared — "Reprendre" looks pushed away.

Fix at the tile, not at the section margin: every tile in a row must occupy the same vertical space, so the row box stops depending on which kinds it happens to hold. Reserve the subtitle line on tiles that have none, or give the tile a fixed height.

**2. The review card writes its own rhythm.** `reviewButton` (`inbox.tsx:614`) carries `marginTop: Spacing.md` *and* `marginBottom: Spacing.lg`, while every `section` carries only `marginBottom: Spacing.lg` and its heading adds `paddingBottom: Spacing.md` (`inbox.tsx:671`). So the gap above the first heading is produced by a different pair of values than the gap above the second, and the column silently changes shape when the card is absent — it renders nothing at count 0 (`inbox.tsx:350`). Drive the inter-block gap from one token, following the convention task-290 settled on for the media and collection screens: each block owns the space above itself, none declares space below.

**3. The free-trial pill is cramped.** `FreeTrialNotice` (`mobile/src/components/FreeTrialNotice.tsx:68`) declares `marginTop: Spacing.md` and no bottom margin. Above it, `scrollContent.paddingTop: Spacing.md` (`inbox.tsx:568`) adds 16 more, so the pill sits 32 dp below the safe area; below it the next block contributes only its own `marginTop: Spacing.md` = 16. The pill therefore hugs the card (or the minutes banner) under it — visibly too tight whenever a trial is running. `MinutesWarningBanner` (`mobile/src/components/MinutesWarningBanner.tsx:131`) has the same shape and stacks right after it, so treat the head of the screen (pill, banner, card) as one rhythm rather than nudging the pill alone.

**Owner note (not an AC):** the result is owner-verifiable only, and needs three passes on a device — a trial account (pill visible) with unsorted items and both rows populated; the same without the pill; and a row mixing a media tile with a collection tile, which is what exposes defect 1.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 Every tile rendered in a Home row occupies the same vertical space whatever its kind: `mobile/src/components/HomeTile.tsx` reserves the subtitle line (or fixes the tile height) so a media tile and a collection tile side by side in the same row have identical height.
- [ ] #2 The gap between the unsorted-review card and the first row heading and the gap between the first row and the second row heading resolve to the same declared value in `mobile/app/(tabs)/inbox.tsx`.
- [ ] #3 `reviewButton` no longer declares a vertical-margin pair that differs from a `section`: each block on Home declares the space above itself and none declares space below it, so removing the card (count 0) or the trial pill (no trial) leaves the gap between the remaining blocks unchanged.
- [ ] #4 `FreeTrialNotice` and `MinutesWarningBanner` are separated from the block below them by the same declared gap as any other pair of Home blocks, and the pill is no longer closer to the block below it than to the top of the scroll content.
- [ ] #5 Render conditions are untouched: the pill still appears only on `is_free_trial`, the review card only at count > 0, and each `TileRow` only when it has tiles — no block gained an empty placeholder to hold space.
- [ ] #6 The row `testID`s (`home-recently-added-row`, `home-continue-learning-row`), `home-unsorted-review-button` and `free-trial-notice` are unchanged.
- [ ] #7 `npm run typecheck` and `npm run lint` both pass from `mobile/`.
<!-- AC:END -->
