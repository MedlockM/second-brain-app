---
id: task-342
title: Give the iOS tab bar UIKit's native height instead of Android's 64 dp block
status: To Do
assignee: []
created_date: '2026-09-03 08:34'
labels:
  - mobile
  - ui
  - bug
  - ios
dependencies: []
priority: medium
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Follow-up to task-331 (Done, commit `c45ede6`). That task fixed a real Android bug — the 3-button system navigation was drawn inside the app's own tab bar strip — by declaring `height: TouchTarget.large + insets.bottom` in `tabBarStyle` (`mobile/app/(tabs)/_layout.tsx:71-78`). Its AC #3 explicitly forbade a platform branch, so iOS got the same 64 dp content block. Owner observation (2026-09-03): the tab bar now sits visibly too high on iOS.

**The measurement.** Verified in the installed `@react-navigation/bottom-tabs@7.17.2`: `getTabBarHeight()` (`lib/module/views/BottomTabBar.js:77-100`) short-circuits on a numeric `height` in `tabBarStyle` and returns it as-is; otherwise it returns `TABBAR_HEIGHT_UIKIT + inset`, with `TABBAR_HEIGHT_UIKIT = 49`. The bar's own view then applies `height: tabBarHeight` and `paddingBottom: insets.bottom`, and spreads `tabBarStyle` **last**, so anything the layout declares wins and anything it omits keeps the library default. On an iPhone with a home indicator (`insets.bottom` = 34):

| | total height | icon+label block |
|---|---|---|
| before task-331 | 64 pt | 26 pt (the inset was taken *out* of the 64) |
| today | 98 pt | 60 pt |
| UIKit native | 83 pt | 49 pt |

So iOS is 15 pt taller than the platform's own tab bar. Reverting to the pre-task-331 value is not the fix — that state was the cramped 26 pt bar.

**The fix.** Keep the inset on both platforms (an iPhone home indicator needs it as much as the Android navigation bar) and branch only the **content** height. The cleanest form declares nothing on iOS and lets the library compute `49 + inset`, i.e. exactly the native bar, rather than restating 49 by hand:

```ts
tabBarStyle: {
  backgroundColor: Colors.surface,
  borderTopColor: Colors.outlineVariant,
  borderTopWidth: StyleSheet.hairlineWidth,
  ...(Platform.OS === "android"
    ? {
        paddingTop: 4,
        height: TouchTarget.large + insets.bottom,
        paddingBottom: insets.bottom,
      }
    : null),
},
```

`paddingTop: 4` leaves the shared object on purpose: on iOS it would eat into the 49 pt UIKit block, and the library already spaces the icon+label row itself. `useSafeAreaInsets()` stays where it is — the Android branch still needs it.

Note that a platform branch is available and used all over this app; task-331's AC #3 was a scoping decision, not a constraint. `Platform.OS` already gates behaviour in `mobile/src/services/purchaseService.ts:38`, `src/hooks/useGoogleSignIn.ts:41`, `src/constants/legal.ts:28`, `app/onboarding/language.tsx:216` (a bottom padding, same shape as this one). Metro's per-platform file suffixes and `app.config.ts`'s `ios:` / `android:` sections are the two other levels, neither needed here.

**Accessibility.** 49 pt minus nothing is above iOS's 44 pt minimum touch target, so shrinking the iOS bar does not push any tab below the floor. Android keeps 64 dp, itself under Material 3's 80 dp navigation-bar content spec — the conservative value the app already chose.

**Owner note (not an AC):** only the owner can confirm the result visually — an iPhone with a home indicator (the bar should now line up with a native iOS tab bar), plus a re-check on Android with 3-button navigation and then with gesture navigation to confirm task-331's fix is untouched.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 `mobile/app/(tabs)/_layout.tsx` declares no numeric `height` in `tabBarStyle` on iOS: the `height` / `paddingBottom` / `paddingTop` triple sits behind a `Platform.OS === "android"` branch (spread or `Platform.select`), so `getTabBarHeight()` falls back to the library's `TABBAR_HEIGHT_UIKIT + insets.bottom` there.
- [ ] #2 The Android values are unchanged: `height: TouchTarget.large + insets.bottom`, `paddingBottom: insets.bottom`, `paddingTop: 4`, all still fed by `useSafeAreaInsets()`.
- [ ] #3 No `49` (or any other restatement of the UIKit tab bar height) is hardcoded in the layout — the iOS height comes from the library default.
- [ ] #4 The comment above `tabBarStyle` is rewritten: the current one asserts "No platform branch: an iPhone with a home indicator reports a bottom inset too", which this task makes false. The new comment records why iOS takes the library default (49 pt UIKit + inset = the native bar, still above iOS's 44 pt touch-target floor) and why Android forces 64 dp above the system navigation bar.
- [ ] #5 The four `Tabs.Screen` entries are untouched — same names, titles, icons and `tabBarButtonTestID` values (`search-tab-button`, `account-tab-button`) — and so are the tint colours and `tabBarLabelStyle`.
- [ ] #6 `mobile/app/(tabs)/inbox.tsx` is reviewed against the now-shorter iOS bar and the implementation notes state whether `scrollContent.paddingBottom` and `fabStack.bottom` needed to change, with the reason; a grep records whether any screen restates the bar height or calls `useBottomTabBarHeight()`.
- [ ] #7 `npm run typecheck` and `npm run lint` both pass from `mobile/`, with any remaining warnings identified as pre-existing and outside the files this task touches.
<!-- AC:END -->
