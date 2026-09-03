---
id: task-350
title: >-
  Adopt the native iOS 26 Liquid Glass tab bar — migrate the tabs layout to
  NativeTabs
status: To Do
assignee: []
created_date: '2026-09-03 13:07'
labels:
  - mobile
  - ui
dependencies: []
priority: medium
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
## What the owner wants

The main tab bar must look like the floating glass capsule seen at the bottom of Readwise and WhatsApp on iOS 26: a detached, fully-rounded bar inset from the screen edges, translucent, with the content scrolling underneath it and the selected tab sitting in a filled pill.

That appearance is not a design those apps drew — it *is* `UITabBarController` on iOS 26. So this task does not draw a capsule; it stops drawing a tab bar at all and hands the job to the system.

## Decision already taken

The owner considered a hand-drawn capsule (a custom `tabBar` renderer plus `expo-glass-effect`'s `GlassView`, which is already installed at `55.0.11` as an `expo-router` dependency) and chose the native route instead. Do **not** reopen it. The reasoning to preserve: the system bar brings the scroll-edge effect, Dynamic Type, minimize behaviour and next year's OS appearance for free, and a JS bar would owe all of that forever.

## The migration

`mobile/app/(tabs)/_layout.tsx` is the only navigation file that changes. Today it renders `Tabs` from `expo-router` with a `screenOptions` block (`:59-99`) and four `Tabs.Screen` (`:101-144`). It becomes `NativeTabs` from `expo-router/unstable-native-tabs` with four `NativeTabs.Trigger`, same order: `inbox`, `search`, `digest`, `account`.

The SDK 55 shape is the compound API, and the icon pattern is documented in the installed types (`node_modules/expo-router/build/native-tabs/common/elements.d.ts:143-182`) — `sf` serves iOS, `src` serves Android, and iOS priority is `sf` > `xcasset` > `src`:

```tsx
<NativeTabs.Trigger name="inbox">
  <NativeTabs.Trigger.Icon
    sf="tray"
    src={<NativeTabs.Trigger.VectorIcon family={Ionicons} name="file-tray-outline" />}
  />
  <NativeTabs.Trigger.Label>{t("tabs.home")}</NativeTabs.Trigger.Label>
</NativeTabs.Trigger>
```

The four pairs, SF Symbol first and today's Ionicons name second: `tray` / `file-tray-outline`, `books.vertical` / `library-outline`, `sparkles` / `sparkles-outline`, `person.crop.circle` / `person-outline`. Keeping the Ionicons on the `src` side is what leaves Android pixel-identical to today and adds no icon asset. The `sf` names are typed against `sf-symbols-typescript` (installed), so `npm run typecheck` is what proves they exist.

Colours keep coming from the two existing tokens: `Colors.tabActive` and `Colors.tabInactive` (`mobile/src/constants/theme.ts:45-46`), mapped onto `tintColor` and `iconColor` (which takes `{ default, selected }`). Labels keep the same i18n keys, and `useTranslation()` must still be called for the bar to redraw on a language change.

Everything above the return statement is untouched: the loading state, the `isAuthenticated` guard and the `needsLanguageOnboarding` guard, in that order, still return before any tab exists — that invariant and its comment (`:11-25`) are the point of the file.

Deleted in the same run, because they describe code that no longer exists: the whole `tabBarStyle` comment block (`:63-93`) with its Android 64 dp reasoning, the `useSafeAreaInsets` call and the `TouchTarget` / `Platform` imports it fed, and the two `tabBarButtonTestID` lines. `StyleSheet` stays — `loadingContainer` still uses it.

## Two consequences of the bar no longer occupying its strip

**The home screen's floating buttons.** `inbox.tsx:297` pins the camera and add FABs at `bottom: Spacing.lg` inside a `SafeAreaView edges={["top"]}` (`styles.fabStack`, `:699-709`). That 24 pt used to be measured from just above an opaque bar; with a floating capsule the safe area runs to the screen bottom and the two buttons end up behind the glass. `scrollContent.paddingBottom` (`:574`, `TouchTarget.large + Spacing.xl`) reserves room for those same buttons and shifts with them. Both must clear the capsule through one named constant or one derivation, not two magic numbers — and `NativeTabs` exposes no tab bar height to measure, so whatever is chosen has to be written down and justified in a comment.

**Automatic content insets.** `disableAutomaticContentInsets` defaults to `false`, so UIKit insets the primary scroll view of each tab itself — but only when it can find it. Expo's docs are explicit that transparency and scroll-to-top bugs trace back to a scrollable that is not the first child, and that the fix is `collapsable={false}` on the wrapper. `account.tsx:162-167` puts a header `View` before its `ScrollView`, and `digest.tsx:135-137` puts the segmented control first with only a horizontal carousel below. Both need checking.

**Eager mounting.** `NativeTabs` has no lazy loading: every tab screen mounts on first render. `inbox`, `search` and `account` already load through `useFocusEffect`, so they are safe. `digest.tsx:84` fetches from a plain `useEffect`, which would fire a digest request on every cold start even when the tab is never opened — it moves to `useFocusEffect`.

## Known limitations to work with, not around

Under Liquid Glass the system owns the bar's background: `backgroundColor`, `blurEffect`, `shadowColor` and `disableTransparentOnScrollEdge` only apply on iOS 18 and earlier. Do not set them. `minimizeBehavior` is set to `never`: both reference screenshots show a bar that stays put, and this app is one people switch tabs in rather than read in one long scroll.

`role="search"` is deliberately not used on the `search` trigger. iOS 26 pulls a search-role tab out to the trailing edge of the bar for a genuine search *field*, and that tab is the library screen (`search.tsx` holds every collection and every saved item behind its own floating pill). It also has an open badge-clipping bug ([expo/expo#41573](https://github.com/expo/expo/issues/41573)).

`NativeTabs` is alpha and its API is stated as subject to change; 22 open issues on `expo/expo` mention it. Two are worth a comment in the file so the next reader does not chase them as local bugs: [#44029](https://github.com/expo/expo/issues/44029) (`labelStyle` colours not applying on iOS) and [#39930](https://github.com/expo/expo/issues/39930) (icon tint not refreshing over light/dark content on iOS 26).

## Out of scope

- **No new dependency.** `expo-router` already ships everything needed; `package.json` gains nothing.
- **The `search-tab-button` and `account-tab-button` ids disappear** with `tabBarButtonTestID`. Four Maestro flows reference them (`06_search.yaml`, `07_paywall.yaml`, `utils/sign_out.yaml`, `utils/ensure_logged_out.yaml`); those flows are legacy and are not updated here. The comment at `search.tsx:165` that claims the tab keeps that id is now false and is the one thing to fix.
- No dark mode work, no `NativeTabs.BottomAccessory`, no change to any screen's own layout beyond the bottom-clearance and mount-timing points above.

## Owner notes (deliberately not acceptance criteria)

- Needs a fresh dev build, not a Metro reload: `NativeTabs` and the vector-icon `src` path are native. Check on an iOS 26 device or simulator that the capsule floats, that content passes under it, and that the selected tab gets its pill.
- Then check an iOS 18 device if one is around: there `NativeTabs` renders the classic opaque bar, which is expected, not a regression.
- Judge the yellow. `tabActive` is `#ffcb05` on a near-white background, and on iOS 26 the filled pill already signals selection on its own — so `Colors.textMain` (`#2b2d42`) for the selected glyph may read better than the yellow. That is a design call, and a follow-up task if the answer is yes.
- Android now draws the native Material bottom navigation. The hand-tuned 64 dp bar is gone; confirm the Back/Home/Recents buttons no longer land inside the tab touch targets, which was the reason that 64 dp existed.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 `mobile/app/(tabs)/_layout.tsx` renders `NativeTabs` from `expo-router/unstable-native-tabs` with four `NativeTabs.Trigger` in the order `inbox`, `search`, `digest`, `account`, and no `Tabs`, `screenOptions`, `tabBarStyle` or `Tabs.Screen` remains anywhere in `mobile/app/`
- [ ] #2 Each trigger declares a `NativeTabs.Trigger.Icon` carrying both `sf` (`tray`, `books.vertical`, `sparkles`, `person.crop.circle`) and `src={<NativeTabs.Trigger.VectorIcon family={Ionicons} name=... />}` with today's Ionicons names, so Android keeps its current glyphs
- [ ] #3 Labels are rendered through `NativeTabs.Trigger.Label` from the unchanged i18n keys `tabs.home`, `tabs.search`, `tabs.digest`, `account.title`, and `useTranslation()` is still called in the layout so the bar redraws on a language change
- [ ] #4 `Colors.tabActive` and `Colors.tabInactive` are still the only source of the bar's colours, mapped through `tintColor` and `iconColor`, and neither token is removed from `mobile/src/constants/theme.ts`
- [ ] #5 `minimizeBehavior` is set to `never`, and no `backgroundColor`, `blurEffect`, `shadowColor` or `disableTransparentOnScrollEdge` is passed to `NativeTabs`
- [ ] #6 The loading state and the two guards (`isAuthenticated`, then `needsLanguageOnboarding`) are unchanged and still return before any tab is rendered; the `useSafeAreaInsets` call, the `TouchTarget` and `Platform` imports, the Android height/padding branch, the `tabBarStyle` comment block and both `tabBarButtonTestID` lines are deleted
- [ ] #7 The FAB stack and `scrollContent.paddingBottom` in `mobile/app/(tabs)/inbox.tsx` both clear the floating tab bar through a single named constant or derivation, with a comment stating what it reserves and that `NativeTabs` exposes no measurable bar height
- [ ] #8 In each of the four tab screens the primary vertical scrollable is either the direct child of the screen root or sits under a wrapper carrying `collapsable={false}`, so UIKit's automatic content insets and scroll-edge effect attach
- [ ] #9 `mobile/app/(tabs)/digest.tsx` performs its initial digest fetch from `useFocusEffect` instead of `useEffect`, so an unopened tab issues no request under eager mounting
- [ ] #10 The comment at `mobile/app/(tabs)/search.tsx:165` no longer states that the tab keeps a `search-tab-button` id, and `mobile/package.json` gains no dependency
- [ ] #11 `npm run lint` and `npm run typecheck` are clean in `mobile/` (typecheck is what validates the four SF Symbol names against `sf-symbols-typescript`)
<!-- AC:END -->
