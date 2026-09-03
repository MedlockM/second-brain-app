/**
 * The translucent backdrop of the two surfaces in the app that ask for one: the
 * floating search pill of the library screen and the card of the media context
 * menu.
 *
 * Three branches, and none of them is a degradation of the one above — each is
 * the best material the platform can actually draw:
 *
 * 1. **Liquid Glass** (`GlassView`, `glassEffectStyle="regular"`), the iOS 26
 *    material, and the one the system tab bar these surfaces sit next to draws
 *    since task-350. Both availability checks have to pass, and the second is
 *    not redundant: `isLiquidGlassAvailable()` only reports that the app is
 *    drawing the Liquid Glass design, while `isGlassEffectAPIAvailable()`
 *    reports that the API exists on this device — some iOS 26 betas ship without
 *    it and calling into it crashes (expo/expo#40911).
 * 2. **The iOS 18 blur** (`BlurView`, light) on any other iOS. That is the
 *    material those versions have and the appearance they are meant to keep, not
 *    a fallback for a glass that failed. The two call sites had drifted apart
 *    before they shared this component — the pill blurred at 60, the menu card at
 *    80 under a white veil standing in for vibrancy — and one setting is now what
 *    both of them get.
 * 3. **An opaque tint** everywhere else. Android blur support is uneven across
 *    devices and vendors — and silently degrades when the system disables
 *    animations — so Android takes the tint rather than risk a surface that
 *    renders as nothing over scrolling content. It therefore never reaches
 *    branch 2, which is why nothing here configures `experimentalBlurMethod`.
 *    iOS lands here too when the user has asked for less transparency: the doc
 *    of `isLiquidGlassAvailable` states that it reports component availability
 *    only and stays `true` when an accessibility setting limits the effect,
 *    pointing at `AccessibilityInfo.isReduceTransparencyEnabled()` for the rest.
 *    A glass pill under reduce transparency is exactly the unreadable surface
 *    this branch exists to avoid, so that flag sends both iOS branches here.
 *
 * The caller owns the shape: the radius, the height and the padding all come
 * from the `style` it passes, and that style has to keep `overflow: "hidden"` so
 * the radius clips whichever material renders.
 */

import { useEffect, useState, type ReactNode } from "react";
import {
  AccessibilityInfo,
  Platform,
  StyleSheet,
  View,
  type StyleProp,
  type ViewStyle,
} from "react-native";
import { BlurView } from "expo-blur";
import {
  GlassView,
  isGlassEffectAPIAvailable,
  isLiquidGlassAvailable,
} from "expo-glass-effect";

/** What the pre-26 blur has always been set to on both call sites. */
const BLUR_INTENSITY = 60;

interface GlassSurfaceProps {
  children: ReactNode;
  style: StyleProp<ViewStyle>;
}

export function GlassSurface({
  children,
  style,
}: GlassSurfaceProps): React.JSX.Element {
  const reduceTransparency = useReduceTransparency();

  if (Platform.OS === "ios" && !reduceTransparency) {
    if (isLiquidGlassAvailable() && isGlassEffectAPIAvailable()) {
      return (
        <GlassView glassEffectStyle="regular" style={style}>
          {children}
        </GlassView>
      );
    }

    return (
      <BlurView intensity={BLUR_INTENSITY} tint="light" style={style}>
        {children}
      </BlurView>
    );
  }

  return <View style={[style, styles.opaqueTint]}>{children}</View>;
}

/**
 * Whether the user has asked the system for less transparency.
 *
 * Read once on mount and then kept live, because the setting is a toggle the
 * user can flip while the app is on screen and the surface has to follow it.
 * Both calls are safe on Android — React Native resolves the query to `false`
 * and hands back an inert subscription — so this needs no platform guard.
 *
 * It starts at `false`, which is the only thing an asynchronous query allows: a
 * device with the setting on renders one frame of glass before swapping to the
 * tint.
 */
function useReduceTransparency(): boolean {
  const [reduceTransparency, setReduceTransparency] = useState(false);

  useEffect(() => {
    let active = true;
    void AccessibilityInfo.isReduceTransparencyEnabled()
      // Rejects where there is no native accessibility manager to ask — web, in
      // practice. The default then stands, which is the answer Android gives.
      .catch(() => false)
      .then((enabled) => {
        if (active) setReduceTransparency(enabled);
      });
    const subscription = AccessibilityInfo.addEventListener(
      "reduceTransparencyChanged",
      setReduceTransparency,
    );

    return () => {
      active = false;
      subscription.remove();
    };
  }, []);

  return reduceTransparency;
}

const styles = StyleSheet.create({
  opaqueTint: {
    // The one literal colour in this file: `Colors.background` at 92 %, opaque
    // enough that the surface stays legible with no blur under it at all. The
    // design system has no token for a partially transparent background, and
    // inventing one would put a value only this fallback uses in the palette.
    backgroundColor: "rgba(252, 249, 246, 0.92)",
  },
});
