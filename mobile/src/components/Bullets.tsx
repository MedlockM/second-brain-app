/**
 * A bulleted list, either dotted or ticked.
 *
 * Extracted from the artifact screen, which is where it grew and where it is
 * still used the most: the triage card of "Tri des non classés" renders the same
 * kind of list, and two hand-rolled bullet styles drifting apart is exactly what
 * a design system exists to prevent.
 *
 * `numberOfLines` is what the triage screen adds: there the card must fit the
 * screen with no scroll of its own, so a bullet that runs long is clipped rather
 * than allowed to push the action bar away. It is a safety net — the prompt bounds
 * bullet length upstream — and the artifact screen, which scrolls freely, leaves
 * it unset. The cap is the caller's to work out, not this component's: the triage
 * card measures what its box can hold and passes the answer down.
 */
import { Ionicons } from "@expo/vector-icons";
import React from "react";
import { StyleSheet, Text, View } from "react-native";

import { Colors, Spacing, Typography } from "../constants/theme";

/**
 * The one gap this list uses, between a dot and its text and between two rows
 * alike. `Spacing` has no 10 and the two have always been the same value, so it is
 * named once here rather than spelled `Spacing.sm + 2` twice.
 */
const BULLET_GAP = Spacing.sm + 2;

export function Bullets({
  items,
  variant = "dot",
  numberOfLines,
}: {
  items: string[];
  variant?: "dot" | "check";
  numberOfLines?: number;
}): React.JSX.Element {
  return (
    <View style={styles.list}>
      {items.map((item, i) => (
        <View key={`bullet-${i}`} style={styles.bulletRow}>
          {variant === "check" ? (
            <Ionicons
              name="checkmark-circle"
              size={18}
              color={Colors.primary}
              style={styles.bulletCheck}
            />
          ) : (
            <View style={styles.bulletDot} />
          )}
          <Text style={styles.bulletText} numberOfLines={numberOfLines}>
            {item}
          </Text>
        </View>
      ))}
    </View>
  );
}

const styles = StyleSheet.create({
  /**
   * `rowGap` on the list rather than a `marginBottom` on every row.
   *
   * React Native has no `:last-child`, so a per-row margin also hangs under the
   * last bullet: the list measured 10 pt taller than the text it draws, and the
   * space it added below itself belonged to no one. Harmless on the artifact
   * screen, which scrolls; not harmless on the triage card, which sizes this list
   * against the room its box has left and needs the two numbers to agree.
   */
  list: {
    rowGap: BULLET_GAP,
  },
  bulletRow: {
    flexDirection: "row",
    alignItems: "flex-start",
    columnGap: BULLET_GAP,
  },
  bulletDot: {
    width: 6,
    height: 6,
    borderRadius: 3,
    backgroundColor: Colors.primary,
    marginTop: 9,
  },
  bulletCheck: {
    marginTop: 2,
  },
  bulletText: {
    flex: 1,
    fontSize: Typography.body.fontSize,
    color: Colors.textMain,
    lineHeight: 24,
  },
});
