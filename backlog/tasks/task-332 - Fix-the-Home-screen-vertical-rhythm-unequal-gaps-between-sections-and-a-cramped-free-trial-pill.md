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
- [x] #1 Every tile rendered in a Home row occupies the same vertical space whatever its kind: `mobile/src/components/HomeTile.tsx` reserves the subtitle line (or fixes the tile height) so a media tile and a collection tile side by side in the same row have identical height.
- [x] #2 The gap between the unsorted-review card and the first row heading and the gap between the first row and the second row heading resolve to the same declared value in `mobile/app/(tabs)/inbox.tsx`.
- [x] #3 `reviewButton` no longer declares a vertical-margin pair that differs from a `section`: each block on Home declares the space above itself and none declares space below it, so removing the card (count 0) or the trial pill (no trial) leaves the gap between the remaining blocks unchanged.
- [x] #4 `FreeTrialNotice` and `MinutesWarningBanner` are separated from the block below them by the same declared gap as any other pair of Home blocks, and the pill is no longer closer to the block below it than to the top of the scroll content.
- [x] #5 Render conditions are untouched: the pill still appears only on `is_free_trial`, the review card only at count > 0, and each `TileRow` only when it has tiles — no block gained an empty placeholder to hold space.
- [x] #6 The row `testID`s (`home-recently-added-row`, `home-continue-learning-row`), `home-unsorted-review-button` and `free-trial-notice` are unchanged.
- [x] #7 `npm run typecheck` and `npm run lint` both pass from `mobile/`.
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
**One token, one side, three files.** The inter-block gap is now
`HOME_BLOCK_GAP` in the new `mobile/src/constants/homeRhythm.ts` — an alias of
`Spacing.lg` (24), never a value of its own. It got its own module because three
files declare it: the screen, for the review card and both `TileRow`s, and the two
notices that only ever render at the top of Home. A shared import is what stops a
later edit to one of them from silently desynchronising the head of the screen
from its body, which is the shape the bug already had.

The convention is task-290's, verbatim: **each block owns the space above itself,
none declares space below it.** So `reviewButton` lost `marginBottom: Spacing.lg`
and its `marginTop` went from `Spacing.md` to `HOME_BLOCK_GAP`; `section` flipped
from `marginBottom: Spacing.lg` to `marginTop: HOME_BLOCK_GAP`;
`FreeTrialNotice.row` and `MinutesWarningBanner.banner` went from
`marginTop: Spacing.md` to `HOME_BLOCK_GAP`. `scrollContent.paddingTop:
Spacing.md` is gone — it was the second value producing the head of the screen's
gap, and with it removed whichever block comes first carries the whole 24 itself.

Declared gaps, before → after: top of scroll to pill 32 → 24, pill to banner
16 → 24, banner (or pill) to review card 16 → 24, review card to first heading
24 → 24, first row to second heading 24 → 24. Every pair is one value now, and the
pill sits the same 24 from the top of the content as from the block below it
(AC #4). Because no block declares space below itself, removing the card at count 0
or the pill without a trial changes nothing for the blocks that remain (AC #3).
Render conditions and every `testID` are untouched — neither appears in the diff.

**Defect 1 fixed with a fixed tile height, not a reserved subtitle.** The task
offered either; a reserved subtitle line only fixes half of it. Tiles disagree on
height for two reasons, not one: a collection tile always carries a subtitle where
a media tile without a creator carries none (~20 dp), *and* `numberOfLines={3}` on
the title means a three-line title stands 40 dp taller than a one-line one — twice
the reported error, and it survives any subtitle-only fix. So `HomeTile` now
declares `height: TILE_HEIGHT`, reserving the worst case:
`TILE_COVER_HEIGHT + Spacing.sm + 3 * TILE_TITLE_LINE_HEIGHT + Spacing.xs +
TILE_SUBTITLE_LINE_HEIGHT` = 203. The two line heights became named constants
because a height computed like that is only exact if the text cannot pick its own
leading — the title already hardcoded `lineHeight: 20`, the subtitle had none and
now declares 18. Text stays top-aligned, so a short tile carries its slack at the
bottom where it is identical across the row, and the subtitle is still rendered
conditionally: the fixed height reserves the line, no placeholder element does.
`minHeight: TouchTarget.minimum` went away with it (203 clears the 48 floor on the
cover alone), which left `TouchTarget` unused in that file and it was dropped from
the import.

**Left alone for task-331**, dispatched in parallel on the same screen:
`app/(tabs)/_layout.tsx`, `scrollContent.paddingBottom` and `fabStack.bottom` are
untouched. One knock-on worth stating: with `section.marginBottom` gone, the space
under the last row is now the `paddingBottom` alone (96) instead of 24 + 96. That
is the convention working as intended, and the reserve for the tab bar and the
floating buttons is exactly as task-331 finds it.

Checks from `mobile/`: `npm run typecheck` exits 0; `npm run lint` reports 0 errors
and 2 warnings, both pre-existing and in files this task did not touch
(`app/(tabs)/digest.tsx`, `src/services/purchaseService.ts`). No automated test was
added, per the repo rule. The visual result is owner-verifiable only, on a device,
in the three passes the description lists — the mixed media/collection row being
the one that exposes defect 1.
<!-- SECTION:NOTES:END -->
