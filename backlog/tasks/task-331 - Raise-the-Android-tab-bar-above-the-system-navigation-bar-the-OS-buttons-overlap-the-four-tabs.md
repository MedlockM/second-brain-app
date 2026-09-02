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
- [ ] #1 `mobile/app/(tabs)/_layout.tsx` reads the bottom safe-area inset via `useSafeAreaInsets()` from `react-native-safe-area-context` and feeds it into `tabBarStyle`.
- [ ] #2 The bar's declared `height` is `TouchTarget.large + insets.bottom` and its `paddingBottom` is `insets.bottom`, so the icon+label block keeps at least `TouchTarget.large` of height above the system bar.
- [ ] #3 No `Platform.OS` branch gates that inset: the same formula applies on iOS and on Android.
- [ ] #4 The four `Tabs.Screen` entries are untouched — same names, titles, icons and `tabBarButtonTestID` values (`search-tab-button`, `account-tab-button`).
- [ ] #5 `mobile/app/(tabs)/inbox.tsx` is reviewed against the taller bar and the implementation notes state whether `scrollContent.paddingBottom` and `fabStack.bottom` needed to change, with the reason.
- [ ] #6 `npm run typecheck` and `npm run lint` both pass from `mobile/`.
<!-- AC:END -->
