---
id: task-331
title: >-
  Raise the Android tab bar above the system navigation bar: the OS buttons
  overlap the four tabs
status: To Do
assignee: []
created_date: '2026-09-01 17:11'
labels:
  - mobile
  - ui
  - bug
  - android
dependencies: []
priority: high
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
On Android the system navigation bar is drawn on top of the app's own tab bar. Owner screenshot (Samsung device, 2026-09-01 19:00, Home screen): the Back / Home / Recents buttons of the 3-button navigation sit inside the same strip as the four tab icons (Home, Search, Digest, Account) — the tab labels are hidden behind them and each system button lands inside a tab touch target, so the four tabs are partly unusable.

**Cause.** `mobile/app/(tabs)/_layout.tsx` declares `tabBarStyle` with `height: TouchTarget.large` (64) and `paddingTop: 4`, and nothing else. Two things follow:

- An explicit `height` in `tabBarStyle` replaces the height `@react-navigation/bottom-tabs` would otherwise compute from the bottom safe-area inset, so the bar reserves nothing for the system bar.
- Under Expo SDK 55 / React Native 0.83 (`mobile/package.json`), Android edge-to-edge is the platform behaviour and can no longer be turned off, so the app window extends under the navigation bar. Without the inset the two surfaces share the same 64 dp.

**Fix.** Read `useSafeAreaInsets()` in the tabs layout and let the bar carry the inset: declared height `TouchTarget.large + insets.bottom`, `paddingBottom: insets.bottom`. The inset is *added* to the 64 dp, never taken out of it, so the icon+label block keeps its full comfortable height above the system bar. No platform branch: on an iPhone with a home indicator `insets.bottom` is non-zero too and the fixed 64 dp is cramping the bar there as well, so the same formula is the fix on both.

The repo already handles this inset everywhere else a surface is bottom-anchored — `mobile/src/components/AddSourceSheet.tsx:87`, `MediaActionsSheet.tsx:108` and `CollectionSaveSheet.tsx:193` all add `insets.bottom` to their bottom padding, and `mobile/app/media/unsorted-review.tsx:91` floors it with `initialWindowMetrics`. The tab bar is the one surface that was missed.

Nothing should be needed on the four tab screens: they all mount `SafeAreaView edges={["top"]}` and let the navigator inset their content above the bar, so a taller bar shrinks the content area on its own. Two values in `mobile/app/(tabs)/inbox.tsx` do restate the old bar height by hand and must be checked against the taller bar — `scrollContent.paddingBottom: TouchTarget.large + Spacing.xl` and `fabStack.bottom: Spacing.lg`; the camera and `+` floating buttons must still clear it.

**Owner note (not an AC):** only the owner can confirm the result visually — an Android device with 3-button navigation, then the same with gesture navigation (where `insets.bottom` is small but non-zero), plus an iPhone with a home indicator to check the bar did not grow oddly there.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 `mobile/app/(tabs)/_layout.tsx` reads the bottom safe-area inset via `useSafeAreaInsets()` from `react-native-safe-area-context` and feeds it into `tabBarStyle`.
- [x] #2 The bar's declared `height` is `TouchTarget.large + insets.bottom` and its `paddingBottom` is `insets.bottom`, so the icon+label block keeps at least `TouchTarget.large` of height above the system bar.
- [x] #3 No `Platform.OS` branch gates that inset: the same formula applies on iOS and on Android.
- [x] #4 The four `Tabs.Screen` entries are untouched — same names, titles, icons and `tabBarButtonTestID` values (`search-tab-button`, `account-tab-button`).
- [x] #5 `mobile/app/(tabs)/inbox.tsx` is reviewed against the taller bar and the implementation notes state whether `scrollContent.paddingBottom` and `fabStack.bottom` needed to change, with the reason.
- [x] #6 `npm run typecheck` and `npm run lint` both pass from `mobile/`.
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
### What changed

One file, `mobile/app/(tabs)/_layout.tsx`:

- `useSafeAreaInsets()` is read next to the other hooks, before the three guards
  (loading / unauthenticated / language onboarding), so the hook order is stable
  whichever branch renders.
- `tabBarStyle` now declares `height: TouchTarget.large + insets.bottom` and
  `paddingBottom: insets.bottom`. No `Platform.OS` anywhere.

The four `Tabs.Screen` blocks, the tint colours, `paddingTop: 4`, the hairline
top border and `tabBarLabelStyle` are byte-for-byte unchanged, test ids included.

### Why the flat height was the bug

Confirmed in the installed `@react-navigation/bottom-tabs@7.17.2`:
`getTabBarHeight()` (`src/views/BottomTabBar.tsx`) short-circuits on a numeric
`height` in `tabBarStyle` and returns it as-is, skipping the
`TABBAR_HEIGHT_UIKIT + inset` it computes otherwise. The bar's own view does set
`paddingBottom: insets.bottom` by default — but that padding was being taken out
of the flat 64 dp rather than added to it, so on a 3-button Samsung the icon+label
row was squeezed into `64 - 48 - 4 = 12` dp and collapsed into the system
buttons' strip. Adding the inset to the height restores the full 60 dp of content
(64 minus the existing `paddingTop: 4`) *above* the navigation bar.

### AC #5 — `inbox.tsx` needed no change

Reviewed, left untouched. `BottomTabView` renders the bar as a sibling of the
screen container in a flex column (`position: 'absolute'` only when the bar is
hidden), so the screen's coordinate space **ends at the top edge of the bar** and
shrinks by exactly the amount the bar grows. Both values are measured from that
edge, so they keep their meaning:

- `fabStack.bottom: Spacing.lg` — 24 dp of clearance above the bar's top edge,
  whatever `insets.bottom` is. Raising the bar pushes both floating buttons up
  with it; they never sit over it.
- `scrollContent.paddingBottom: TouchTarget.large + Spacing.xl` (96) — still
  covers the 64 dp buttons anchored 24 dp up (they occupy 24→88 of the content
  area), so the last tile row never ends under them.

Deliberately no `insets.bottom` added on this screen: that would double-count the
inset the bar now owns and leave a 48 dp gap on Android. Nothing else in the app
restates the bar height — `TouchTarget.large` appears in `inbox.tsx` only for the
two 64 dp round buttons, and no screen calls `useBottomTabBarHeight()`.

### Verification

`npm run typecheck` clean. `npm run lint`: 0 errors, 2 warnings, both
pre-existing and in files this task did not touch (`digest.tsx` unused
`CARD_WIDTH`, `purchaseService.ts` explicit `any`).

Not verifiable from the worktree, and left to the owner as the task's description
already states: the visual result on an Android device with 3-button navigation,
then with gesture navigation, and on an iPhone with a home indicator.
<!-- SECTION:NOTES:END -->
