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
 * `app/media/collections/[id].tsx`, made general:
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
 */

import React, { type ReactNode } from "react";
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
