/**
 * Design system tokens from "Amber Clarity" design system.
 * Source: mobile-design-mockups/my_design_system/DESIGN.md
 */
export const Colors = {
  primary: "#ffcb05",
  onPrimary: "#1c1b1a",

  background: "#fcf9f6",
  surface: "#ffffff",
  surfaceContainer: "#f1edea",
  surfaceContainerHigh: "#ebe7e5",
  surfaceContainerLow: "#f7f3f0",

  textMain: "#2b2d42",
  textMuted: "#8d99ae",
  /**
   * Secondary text that still has to be *read*, not merely glanced at.
   *
   * `textMuted` measures 2.75:1 on `background` and 2.88:1 on `surface`, well
   * under the 4.5:1 WCAG AA asks for below 18.66px — which made every small
   * grey line on the paywall (the per-import ceiling, the whole legal block, the
   * close button) formally unreadable. This is the same blue-grey hue darkened
   * to 5.3:1 on `background` and 5.6:1 on `surface`.
   *
   * `textMuted` is kept for what it is genuinely good at — inactive icons, tab
   * bar glyphs, decoration — and the two are not interchangeable: anything the
   * user has to read uses this one. Generalising the swap to the rest of the app
   * is a design-system pass of its own.
   */
  textSubtle: "#5c6880",

  outline: "#78776f",
  outlineVariant: "#c8c7bd",

  /** Background of a search match inside a snippet */
  highlight: "#fff0b3",
  onHighlight: "#1c1b1a",

  error: "#ba1a1a",
  onError: "#ffffff",
  errorContainer: "#ffdad6",

  // Tab bar
  tabActive: "#ffcb05",
  tabInactive: "#8d99ae",
} as const;

export const Typography = {
  display: {
    fontSize: 32,
    fontWeight: "700" as const,
    letterSpacing: -0.5,
  },
  headline: {
    fontSize: 20,
    fontWeight: "600" as const,
  },
  body: {
    fontSize: 16,
    fontWeight: "400" as const,
    lineHeight: 25.6, // 1.6x
  },
  label: {
    fontSize: 14,
    fontWeight: "500" as const,
  },
  small: {
    fontSize: 13,
    fontWeight: "400" as const,
  },
} as const;

export const Spacing = {
  xs: 4,
  sm: 8,
  md: 16,
  lg: 24,
  xl: 32,
  xxl: 48,
} as const;

export const BorderRadius = {
  sm: 4,
  md: 8,
  lg: 12,
  xl: 16,
  full: 9999,
} as const;

export const Shadows = {
  soft: {
    shadowColor: "#2b2d42",
    shadowOffset: { width: 0, height: 8 },
    shadowOpacity: 0.04,
    shadowRadius: 24,
    elevation: 2,
  },
} as const;

/**
 * Touch target size constraints per platform accessibility guidelines.
 * iOS: minimum 44pt, Android: minimum 48dp.
 * We use 48px as the floor for both platforms (AC#2).
 */
export const TouchTarget = {
  /** Absolute minimum for any interactive element (48px) */
  minimum: 48,
  /** Comfortable touch target for primary actions (56px) */
  comfortable: 56,
  /** Large touch target for hero/CTA buttons (64px) */
  large: 64,
} as const;
