---
id: task-351
title: >-
  Swap the two glassy surfaces from expo-blur to the real Liquid Glass material
  (GlassView)
status: To Do
assignee: []
created_date: '2026-09-03 13:16'
labels:
  - mobile
  - ui
dependencies:
  - task-350
priority: medium
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
## What the owner wants

The app has exactly two surfaces that reach for a modern translucent iOS look: the floating search pill on the library screen, and the card of the media context menu. Both draw an `expo-blur` `BlurView` — which is already a native `UIVisualEffectView`, but with a `UIBlurEffect`, the iOS 18 material. Next to the Liquid Glass tab bar that task-350 installs, that blur will read as the old thing.

So this is not a native-versus-custom question and no architecture moves: the two surfaces keep their shape, their placement and their behaviour, and only their **material** changes to `GlassView` from `expo-glass-effect`.

## Why this depends on task-350

Two reasons, both concrete. `search.tsx` is edited by both tasks (task-350 fixes the stale `search-tab-button` comment at `:165`, this one rewrites `GlassSurface` at `:514-541`), so running them in parallel worktrees would collide. And the tab bar is the reference the two surfaces are being matched against — there is no point tuning them before it exists.

## The shared component

`GlassSurface` (`mobile/app/(tabs)/search.tsx:514-541`) is a local helper with a two-way fork: `BlurView` on iOS, a tinted `View` elsewhere. It moves to `mobile/src/components/GlassSurface.tsx`, keeps its `{ children, style }` shape, and grows a third branch:

1. **`GlassView`** with `glassEffectStyle="regular"` when `isLiquidGlassAvailable()` and `isGlassEffectAPIAvailable()` are both true. The second one is not redundant: the module's own doc states some iOS 26 beta builds lack the API and calling into it can crash ([expo/expo#40911](https://github.com/expo/expo/issues/40911)).
2. **`BlurView`** with today's parameters on any other iOS — iOS 18 and earlier get exactly the current appearance, which is the intended outcome, not a regression.
3. **A tinted `View`** elsewhere. The literal `rgba(252, 249, 246, 0.92)` currently in `styles.searchBarAndroidFallback` (`search.tsx:1184-1187`) travels with the component; the comment explaining why Android does not blur (uneven vendor support, silent degradation when animations are off) travels with it too.

**Reduce transparency is part of that fork, not an extra.** The doc comment on `isLiquidGlassAvailable` says so itself: the function only reports component availability and "may also be `true` if the user has enabled accessibility settings that limit the Liquid Glass effect", and points at `AccessibilityInfo.isReduceTransparencyEnabled()`. So the component reads that flag and subscribes to `reduceTransparencyChanged`, falling back to branch 3 — a glass pill under reduce-transparency is exactly the unreadable surface the Android fallback was written to avoid.

## The two call sites

**The search pill** (`search.tsx:469`) imports the shared component and loses its local copy, its `BlurView` import and `styles.searchBarAndroidFallback`. Nothing else on that screen moves: `SEARCH_BAR_HEIGHT`, `CONTENT_TOP_INSET`, `searchBarOverlay` and the pill's own layout are untouched. `overflow: "hidden"` stays — the radius has to clip the material whichever branch renders.

**The menu card** (`MediaContextMenu.tsx:272-309`) renders through the same component. `cardVeil` (`:281`, and `styles.cardVeil` at `:396-400` — `Colors.surface` at 78 % opacity) is deleted: it was an ersatz vibrancy, and the real material provides it.

**The backdrop stays a `BlurView`.** `:219-224` blurs the whole screen behind the menu at `intensity={40}` under a 35 % scrim. iOS blurs the background behind its own context menu too — it does not glass a full-screen panel, and there is nothing for a glass material to be a *panel of* here. Leave it, and say so in a comment so the next reader does not treat it as a surface that was missed.

## The trap that lands exactly on this file

`expo-glass-effect` documents a known issue: `opacity: 0` on the glass view **or on any of its ancestors** stops the effect rendering at all. `MediaContextMenu` animates `opacity: progress` on `cardWrapper` (`:265`), which is the card's ancestor, and `progress` is explicitly reset to `0` before every open (`:132`, `:138`). A literal swap therefore produces a menu card whose glass never appears.

The documented way out is to animate the wrapper's opacity while switching `glassEffectStyle` to `'none'` at low opacity values (iOS 26.1+), rather than relying on opacity alone. Whichever shape is chosen, the entry animation must still be the one scale-and-fade it is today — `PREVIEW_SCALE`, `OPEN_DURATION`, `CLOSE_DURATION`, `useNativeDriver: true` and the `requestClose` contract with `useMediaActions` do not change — and the known issue gets a comment naming it, because the failure mode (a card that renders as a plain view) looks like a styling mistake rather than a documented constraint.

## One comment to correct while in this file

`MediaContextMenu.tsx:13-18` justifies the JS rebuild (task-346) with three reasons. One is no longer true and must not stay: "a context-menu library would drag in `react-native-reanimated` / `react-native-gesture-handler`". `Link.Menu` and `Link.Preview` ship inside `expo-router`, and `node_modules/expo-router/build/link/LinkWithPreview.js` imports only `react`, `react-native` and router internals — neither of those two packages.

The two reasons that do hold, and that the corrected comment should carry instead: `LinkMenu` is annotated `@platform ios` in `node_modules/expo-router/build/link/elements.d.ts:195`, so Android would lose the long-press entirely; and a `UIMenu` dismisses on selection, which leaves nowhere for the in-flight spinner on Delete (`:305`, `isDeleting`) to live. The decision to keep this menu in JS is unchanged — only its stated reasons are being made accurate.

## Dependency

`expo-glass-effect` is currently present only as a transitive dependency of `expo-router` (`55.0.11` in `node_modules`). It becomes a declared direct dependency of `mobile/package.json` at the SDK 55 range, because a surface the app renders on purpose must not rely on another package's dependency tree. `expo-blur` stays declared — the backdrop and the iOS 18 branch both still use it.

## Out of scope

- The context menu's placement maths (`opensDown`, `clamp`, `MENU_HEIGHT`), the anchor measurement, `renderPreview`, and every network call in `useMediaActions`.
- `AddSourceSheet`, `CollectionSaveSheet` and `MediaRenameDialog`: none of them attempts a glass effect — no `BlurView`, `animationType="slide"`, design-system shadows. Turning them into native form sheets (`react-native-screens` exposes `sheetAllowedDetents`) is a separate question, and `AddSourceSheet` already carries a written decision to stay a plain RN `Modal`.
- Dark mode, and any change to the design system tokens.

## Owner notes (deliberately not acceptance criteria)

- Fresh dev build, then an iOS 26 device: the search pill and the menu card should read as glass, and the menu card must actually render its material as it fades in — that is the `opacity` trap, and it is the one thing worth looking at twice.
- Prefer hardware over the simulator for this one: the simulator's glass rendering is approximate, and reduce-transparency behaviour is easier to toggle and trust on a device (Settings ▸ Accessibility ▸ Display & Text Size ▸ Reduce Transparency).
- Then an iOS 18 device if one is around: both surfaces fall back to today's blur, which is expected. Android is unchanged by construction.
- Watch [expo/expo#42501](https://github.com/expo/expo/issues/42501) — render artifacts when `expo-glass-effect` and `expo-blur` coexist on SDK 55 / iOS 26. After this task they coexist inside the library screen (glass pill, blurred menu backdrop). If artifacts show up, the first thing to try is dropping the backdrop to its scrim alone.
- Two design calls left open, both follow-ups if the answer is yes: the pill keeps a hairline `outlineVariant` border (`search.tsx:1177-1178`) and a `Shadows.soft` on its wrapper (`:1171`), and Liquid Glass draws its own edge and shadow. If they read as doubled on device, they come off.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 `mobile/src/components/GlassSurface.tsx` exports `GlassSurface` with the same `{ children, style }` shape and resolves in three branches: `GlassView` (`glassEffectStyle="regular"`) when `isLiquidGlassAvailable()` and `isGlassEffectAPIAvailable()` are both true, `BlurView` with today's parameters on any other iOS, and a `View` carrying the opaque tint elsewhere
- [ ] #2 The tint literal `rgba(252, 249, 246, 0.92)` and the comment explaining why Android does not blur live in `GlassSurface.tsx`; `styles.searchBarAndroidFallback` no longer exists in `mobile/app/(tabs)/search.tsx`
- [ ] #3 `GlassSurface` falls back to the opaque tint branch when `AccessibilityInfo.isReduceTransparencyEnabled()` reports true, and re-evaluates on the `reduceTransparencyChanged` event
- [ ] #4 `mobile/app/(tabs)/search.tsx` imports `GlassSurface` from `src/components/`, its local definition is deleted, it no longer imports `BlurView`, and `SEARCH_BAR_HEIGHT`, `CONTENT_TOP_INSET`, `searchBarOverlay` and the pill's own styles are otherwise unchanged (`overflow: "hidden"` included)
- [ ] #5 The menu card in `mobile/src/components/MediaContextMenu.tsx` renders through `GlassSurface`, and `cardVeil` plus its style are deleted
- [ ] #6 The full-screen backdrop stays a `BlurView` at `intensity={40}` with its scrim, and a comment states why it is not a glass surface
- [ ] #7 No ancestor of the glass card animates from `opacity: 0`: the entry and exit animations keep `PREVIEW_SCALE`, `OPEN_DURATION`, `CLOSE_DURATION`, `useNativeDriver: true` and the `requestClose` contract, and a comment names the documented `opacity: 0` issue that forced the change
- [ ] #8 `expo-glass-effect` is a declared direct dependency of `mobile/package.json` at the SDK 55 range, and `expo-blur` is still declared
- [ ] #9 The header comment of `MediaContextMenu.tsx` no longer claims a context-menu library would pull in `react-native-reanimated` or `react-native-gesture-handler`; it states instead that `LinkMenu` is iOS-only and that a `UIMenu` dismisses on selection, leaving no place for the Delete spinner
- [ ] #10 The menu's placement maths (`opensDown`, `clamp`, `MENU_HEIGHT`, `MENU_WIDTH`, `SCREEN_EDGE`, `MENU_GAP`), `renderPreview`, the anchor rect and every call into `useMediaActions` are untouched, and no file outside `mobile/src/components/` and `mobile/app/(tabs)/search.tsx` changes apart from `package.json`
- [ ] #11 `npm run lint` and `npm run typecheck` are clean in `mobile/`
<!-- AC:END -->
