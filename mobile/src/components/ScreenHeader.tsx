/**
 * The screen title bar, in one place.
 *
 * Native headers are off everywhere (`headerShown: false` in every `_layout`),
 * so each screen used to rebuild this row by hand — fourteen copies that had
 * drifted apart, most of them with a title that could not shrink. A title
 * without `flex` refuses to compress in a flex row: it runs *under* the action
 * button rather than being clipped, which is what "Save photo" did the moment
 * French turned "Save" into "Enregistrer".
 *
 * The contract here is the one that already worked in
 * `app/media/folders/[id].tsx`, made general:
 *
 *     [ leading: fixed ][ title: flex 1, centred, one line ][ trailing: intrinsic ]
 *
 * The title is the only element allowed to shrink, and it truncates rather
 * than wrapping — a header that grows a second line pushes the whole screen
 * down. Everything else keeps its natural width, so a long translation costs
 * an ellipsis and never a collision.
 *
 * On the optical centring: the title is centred in the space *left over*, so a
 * trailing button wider than the leading one shifts it by a few pixels. That
 * is deliberate. Measuring the trailing button with `onLayout` to mirror it
 * would buy those pixels for an extra render pass and a width that is wrong on
 * the first frame — and it is exactly the reasoning that produced the
 * hard-coded `width: 88` placeholder this component replaces, a number correct
 * in English and wrong in German.
 *
 * The two controls that fill those slots live here as well: `HeaderIconButton`
 * for a back or close, and `HeaderMenuButton` for the trailing `…`. The second
 * one is exported for the media screen too, whose header is still hand-built —
 * one component is what keeps the actions button at the same place and the same
 * size on both, without that screen having to move to `ScreenHeader` first.
 */

import React, { useRef, type ReactNode } from "react";
import {
  Pressable,
  StyleSheet,
  Text,
  View,
  type StyleProp,
  type TextStyle,
  type ViewStyle,
} from "react-native";
import { Ionicons } from "@expo/vector-icons";
import {
  BorderRadius,
  Colors,
  Spacing,
  Typography,
  TouchTarget,
} from "../constants/theme";
import type { AnchorRect } from "./AnchoredContextMenu";

/**
 * The width of a leading slot, and of the spacer that balances it.
 *
 * 40pt is the visual size the design uses for the round back/close buttons.
 * The tappable area is brought up to `TouchTarget.minimum` with `hitSlop`
 * rather than by growing the circle, which would make every header taller.
 */
const SLOT_SIZE = 40;
const SLOT_HIT_SLOP = (TouchTarget.minimum - SLOT_SIZE) / 2;

interface ScreenHeaderProps {
  /** Omitted on the headers that carry only icons. */
  title?: string;
  /** Usually a `HeaderIconButton`; back or close. */
  leading?: ReactNode;
  /** The screen's primary action, at its natural width. */
  trailing?: ReactNode;
  style?: StyleProp<ViewStyle>;
  titleStyle?: StyleProp<TextStyle>;
  testID?: string;
}

export function ScreenHeader({
  title,
  leading,
  trailing,
  style,
  titleStyle,
  testID,
}: ScreenHeaderProps): React.JSX.Element {
  return (
    <View style={[styles.header, style]} testID={testID}>
      {leading ?? <View style={styles.spacer} />}

      {title === undefined ? (
        <View style={styles.titleFill} />
      ) : (
        <Text style={[styles.title, titleStyle]} numberOfLines={1}>
          {title}
        </Text>
      )}

      {/* Balances the leading slot so the title reads as centred. */}
      {trailing ?? <View style={styles.spacer} />}
    </View>
  );
}

interface HeaderIconButtonProps {
  icon: keyof typeof Ionicons.glyphMap;
  onPress: () => void;
  /** Required: an icon-only control has no visible label to fall back on. */
  accessibilityLabel: string;
  /** `filled` is the round tonal button; `plain` is the bare glyph. */
  variant?: "filled" | "plain";
  disabled?: boolean;
  testID?: string;
}

/** The leading control of a header: back, close, or a single screen action. */
export function HeaderIconButton({
  icon,
  onPress,
  accessibilityLabel,
  variant = "filled",
  disabled = false,
  testID,
}: HeaderIconButtonProps): React.JSX.Element {
  return (
    <Pressable
      style={[
        styles.iconButton,
        variant === "filled" && styles.iconButtonFilled,
        disabled && styles.iconButtonDisabled,
      ]}
      onPress={onPress}
      disabled={disabled}
      hitSlop={SLOT_HIT_SLOP}
      accessibilityLabel={accessibilityLabel}
      accessibilityRole="button"
      testID={testID}
    >
      <Ionicons name={icon} size={24} color={Colors.textMain} />
    </Pressable>
  );
}

/**
 * The glyph of the actions button. `ellipsis-horizontal` and not the vertical
 * one: a horizontal `…` is what a top bar carries on both platforms, and the
 * vertical variant reads as an Android overflow menu pinned to the bar's corner.
 */
const MENU_GLYPH = "ellipsis-horizontal" as const;

interface HeaderMenuButtonProps {
  /**
   * Opens the actions menu, with this button's own window rect —
   * `AnchoredContextMenu` hangs its card off the control that opened it.
   */
  onPress: (anchor: AnchorRect) => void;
  /** Required: an icon-only control has no visible label to fall back on. */
  accessibilityLabel: string;
  testID?: string;
}

/**
 * The trailing `…` of a screen that shows one thing, and the way to rename or
 * delete that thing without going back to the list it came from.
 *
 * It measures itself when pressed rather than on layout: the rect is only needed
 * on the frame the menu opens, and a header that has just been laid out under a
 * notch or behind a toast reports a stale position.
 *
 * One component for both screens that carry it — a media item and a folder —
 * which is what makes the button land at the same place and offer the same 48pt
 * target on a header built by hand and on one built by `ScreenHeader`. The bare
 * glyph rather than the tonal circle of `HeaderIconButton`: this is a secondary
 * affordance sitting next to a primary navigation control, and the filled disc
 * would give it more weight than the back button it follows.
 */
export function HeaderMenuButton({
  onPress,
  accessibilityLabel,
  testID,
}: HeaderMenuButtonProps): React.JSX.Element {
  const buttonRef = useRef<View>(null);

  const handlePress = () => {
    buttonRef.current?.measureInWindow((x, y, width, height) => {
      onPress({ x, y, width, height });
    });
  };

  return (
    <Pressable
      ref={buttonRef}
      style={styles.iconButton}
      onPress={handlePress}
      hitSlop={SLOT_HIT_SLOP}
      accessibilityLabel={accessibilityLabel}
      accessibilityRole="button"
      testID={testID}
    >
      <Ionicons name={MENU_GLYPH} size={24} color={Colors.textMain} />
    </Pressable>
  );
}

/**
 * The same glyph on the same slot, inert: what `AnchoredContextMenu` redraws on
 * the measured rect so the button that opened the menu stays sharp above the
 * blurred page, exactly as the pressed row does in Library. The menu requires a
 * preview because it is what names its target — a header button has no row to
 * lift, so it lifts itself.
 */
export function HeaderMenuGlyph(): React.JSX.Element {
  return (
    <View style={styles.iconButton}>
      <Ionicons name={MENU_GLYPH} size={24} color={Colors.textMain} />
    </View>
  );
}

const styles = StyleSheet.create({
  header: {
    flexDirection: "row",
    alignItems: "center",
    paddingHorizontal: Spacing.lg,
    paddingVertical: Spacing.md,
    gap: Spacing.md,
  },
  title: {
    // The only shrinkable element in the row, and the reason this component
    // exists.
    flex: 1,
    textAlign: "center",
    fontSize: Typography.headline.fontSize,
    fontWeight: "700",
    color: Colors.textMain,
    letterSpacing: -0.3,
  },
  // Holds the row open on the icon-only headers, where there is no title to
  // claim the free space.
  titleFill: {
    flex: 1,
  },
  spacer: {
    width: SLOT_SIZE,
  },
  iconButton: {
    width: SLOT_SIZE,
    height: SLOT_SIZE,
    alignItems: "center",
    justifyContent: "center",
  },
  iconButtonFilled: {
    borderRadius: BorderRadius.full,
    backgroundColor: Colors.surfaceContainerHigh,
  },
  iconButtonDisabled: {
    opacity: 0.5,
  },
});
