---
id: task-350
title: >-
  Adopt the native iOS 26 Liquid Glass tab bar — migrate the tabs layout to
  NativeTabs
status: Done
assignee: []
created_date: '2026-09-03 13:07'
updated_date: '2026-09-03 13:43'
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
- [x] #1 `mobile/app/(tabs)/_layout.tsx` renders `NativeTabs` from `expo-router/unstable-native-tabs` with four `NativeTabs.Trigger` in the order `inbox`, `search`, `digest`, `account`, and no `Tabs`, `screenOptions`, `tabBarStyle` or `Tabs.Screen` remains anywhere in `mobile/app/`
- [x] #2 Each trigger declares a `NativeTabs.Trigger.Icon` carrying both `sf` (`tray`, `books.vertical`, `sparkles`, `person.crop.circle`) and `src={<NativeTabs.Trigger.VectorIcon family={Ionicons} name=... />}` with today's Ionicons names, so Android keeps its current glyphs
- [x] #3 Labels are rendered through `NativeTabs.Trigger.Label` from the unchanged i18n keys `tabs.home`, `tabs.search`, `tabs.digest`, `account.title`, and `useTranslation()` is still called in the layout so the bar redraws on a language change
- [x] #4 `Colors.tabActive` and `Colors.tabInactive` are still the only source of the bar's colours, mapped through `tintColor` and `iconColor`, and neither token is removed from `mobile/src/constants/theme.ts`
- [x] #5 `minimizeBehavior` is set to `never`, and no `backgroundColor`, `blurEffect`, `shadowColor` or `disableTransparentOnScrollEdge` is passed to `NativeTabs`
- [x] #6 The loading state and the two guards (`isAuthenticated`, then `needsLanguageOnboarding`) are unchanged and still return before any tab is rendered; the `useSafeAreaInsets` call, the `TouchTarget` and `Platform` imports, the Android height/padding branch, the `tabBarStyle` comment block and both `tabBarButtonTestID` lines are deleted
- [x] #7 The FAB stack and `scrollContent.paddingBottom` in `mobile/app/(tabs)/inbox.tsx` both clear the floating tab bar through a single named constant or derivation, with a comment stating what it reserves and that `NativeTabs` exposes no measurable bar height
- [x] #8 In each of the four tab screens the primary vertical scrollable is either the direct child of the screen root or sits under a wrapper carrying `collapsable={false}`, so UIKit's automatic content insets and scroll-edge effect attach
- [x] #9 `mobile/app/(tabs)/digest.tsx` performs its initial digest fetch from `useFocusEffect` instead of `useEffect`, so an unopened tab issues no request under eager mounting
- [x] #10 The comment at `mobile/app/(tabs)/search.tsx:165` no longer states that the tab keeps a `search-tab-button` id, and `mobile/package.json` gains no dependency
- [x] #11 `npm run lint` and `npm run typecheck` are clean in `mobile/` (typecheck is what validates the four SF Symbol names against `sf-symbols-typescript`)
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
### The layout

`mobile/app/(tabs)/_layout.tsx` now renders `NativeTabs` from
`expo-router/unstable-native-tabs` with four `NativeTabs.Trigger`
(`inbox`, `search`, `digest`, `account`), each carrying a compound
`NativeTabs.Trigger.Icon` with `sf` for iOS and a
`NativeTabs.Trigger.VectorIcon family={Ionicons}` on the `src` side for Android,
plus a `NativeTabs.Trigger.Label` on the unchanged i18n keys. Colours are
`tintColor={Colors.tabActive}` and
`iconColor={{ default: Colors.tabInactive, selected: Colors.tabActive }}`;
`minimizeBehavior="never"`; nothing sets `backgroundColor`, `blurEffect`,
`shadowColor`, `disableTransparentOnScrollEdge` or `labelStyle`. Deleted:
`useSafeAreaInsets`, the `TouchTarget` / `Platform` imports, the whole
`tabBarStyle` block and its Android 64 dp comment, both `tabBarButtonTestID`
lines. The loading state and the two guards are byte-identical.

The four SF Symbol names were checked against the installed
`sf-symbols-typescript` before writing and are all present in its union;
`npm run typecheck` is the standing proof.

On AC #1's literal wording: two `screenOptions` blocks remain under `mobile/app/`
— `app/_layout.tsx:44` and `app/(auth)/_layout.tsx:28` — and both belong to a
`Stack`, not to a tab bar. The only remaining textual matches for `tabBar*` are
prose in two comments that explain the removal.

### AC #7 — the bottom-clearance constant

One constant in `inbox.tsx`, feeding both consumers:

```ts
const TAB_BAR_CLEARANCE =
  Platform.OS === "ios" ? TouchTarget.large + Spacing.lg : Spacing.lg;
```

- `fabStack.bottom = TAB_BAR_CLEARANCE` (was `Spacing.lg`).
- `scrollContent.paddingBottom = TAB_BAR_CLEARANCE + TouchTarget.large + Spacing.sm`
  (was `TouchTarget.large + Spacing.xl`) — a derivation of the same constant, not
  a second figure. The added terms are the FAB row's own height and the 8 pt gap
  the previous pair of values already produced (64 + 32 against a 24 pt offset).

Why 88 on iOS, and why it is written down: `NativeTabs` exposes no tab bar
height, so there is nothing to measure. `TouchTarget.large` (64) is the strip the
capsule needs and is the very figure the deleted Android branch of `tabBarStyle`
gave a bottom bar; `Spacing.lg` (24) is the gap the capsule floats above the
screen bottom plus the room that keeps the buttons visibly off the glass instead
of tangent to it. Both terms are existing tokens — no new magic number.

Why Android branches back to `Spacing.lg` (24, today's value): Android draws the
opaque Material bottom navigation and `NativeTabs` already wraps each screen in a
`SafeAreaView` with the bottom inset applied
(`expo-router/build/native-tabs/NativeTabsView.js:126-130`), so there is no glass
to clear there and a flat 88 would have left the buttons floating high above the
bar. This is still one named constant, and both consumers read it.

**Owner call this leaves open**: if iOS 26's automatic content inset already
reserves the bar for the scroll view, `scrollContent.paddingBottom` will read as
extra trailing whitespace under the last tile row. The derivation is the one
place to trim it, and the direction of the error was chosen deliberately —
whitespace is cosmetic, a FAB behind glass is not.

### AC #8 — automatic content insets, and a correction to the assumed mechanism

The AC names `collapsable={false}` as the fix. Reading the installed
implementation shows that is only half of it. `react-native-screens` finds the
scrollable with
`RNSScrollViewFinder.findScrollViewInFirstDescendantChainFrom`
(`node_modules/react-native-screens/ios/helpers/scroll-view/RNSScrollViewFinder.mm:5-21`),
which walks `subviews[0]` down from the screen and stops at the first
`UIScrollView`. `RNSScrollViewHelper.mm:6-15` then flips that view's
`contentInsetAdjustmentBehavior` from `Never` to `Automatic`. So the requirement
is *first subview at every level*, not merely "somewhere under the root":
`collapsable={false}` protects a chain that is already first-child all the way
down, but it cannot rescue a scrollable that has a sibling above it.

Per screen:

- **inbox.tsx** — the `ScrollView` is already the screen root's first child; the
  chain reaches it. A comment now says so, and names the finder, so nothing gets
  inserted above it by accident.
- **search.tsx** — the `FlatList` is first-child twice over (root `View` →
  `SafeAreaView` → list). Both wrappers now carry `collapsable={false}` so the
  flattener cannot remove a link of that chain.
- **account.tsx** — the header `View` precedes the `ScrollView`, so the walk
  dead-ends in a `Text` and no inset would ever be applied. Fixed by setting
  `contentInsetAdjustmentBehavior="automatic"` on the `ScrollView` directly:
  that is the exact value `RNSScrollViewHelper` would have set, and it needs no
  layout change (the spec forbids moving the header).
- **digest.tsx** — same situation, same fix, on the two vertical `ScrollView`s
  (error state and empty state). The card carousel is deliberately left alone: it
  scrolls horizontally, and an automatic adjustment there would inset the paging
  axis. Its wrapper gets `collapsable={false}`.

Only the `contentInsetAdjustmentBehavior` flip is lost when the walk fails — the
scroll-edge effect applicator
(`RNSScrollEdgeEffectApplicator.mm`) only *configures* an effect whose iOS 26
default is already `automaticStyle`, so a nil scroll view there is a no-op.

### AC #9 — eager mounting

`digest.tsx`'s initial fetch moved from `useEffect` to `useFocusEffect` (the
`setTimeout(…, 0)` defer is preserved inside it). The `activeTab` dependency
still drives the refetch when the segmented control moves: a new callback
identity re-runs react-navigation's outer effect, and the screen is focused when
the user is tapping it. Side effect, and a wanted one: the digest is now also
refreshed when the user comes back to the tab, matching `inbox`, `search` and
`account`.

### Not done, and why

- **No tests.** This project forbids adding automated tests; none were written.
- **The four Maestro flows** that reference `search-tab-button` /
  `account-tab-button` (`06_search.yaml`, `07_paywall.yaml`, `utils/sign_out.yaml`,
  `utils/ensure_logged_out.yaml`) are untouched, per the "Out of scope" section.
  The only comment corrected is the one in `search.tsx` that claimed the tab kept
  that id.
- **No visual verification.** Every appearance claim here (the capsule floats,
  content passes under it, the selected tab gets its pill, the clearance figure
  is right, the Android bar no longer collides with Back/Home/Recents) needs a
  fresh dev build on an iOS 26 device and is the owner's check, not something
  reachable from this worktree.

**One thing the owner may want as a follow-up**: `digest.tsx`'s insight card is
`flex: 1` inside a `SafeAreaView edges={["top"]}`, so on iOS 26 its bottom edge
will run under the floating capsule. Out of scope here ("no change to any
screen's own layout beyond the bottom-clearance and mount-timing points"), but it
is the one screen whose *content*, not just its floating chrome, meets the glass.
<!-- SECTION:NOTES:END -->
