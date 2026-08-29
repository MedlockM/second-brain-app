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
 * it unset.
 */
import { Ionicons } from "@expo/vector-icons";
import React from "react";
import { StyleSheet, Text, View } from "react-native";

import { Colors, Spacing, Typography } from "../constants/theme";

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
    <View>
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
  bulletRow: {
    flexDirection: "row",
    alignItems: "flex-start",
    marginBottom: Spacing.sm + 2,
    gap: Spacing.sm + 2,
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
