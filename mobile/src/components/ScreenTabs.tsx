/**
 * Intra-screen tabs: the segmented control of the Amber Clarity design system,
 * used to split one screen's content into a few sibling views.
 *
 * This is *not* navigation: it never touches the router, so it composes with the
 * bottom tab bar of `app/(tabs)/_layout.tsx` instead of competing with it. The
 * caller owns the selected key, which keeps every piece of state behind a tab
 * (a poll in flight, a fetched body) alive while another tab is displayed.
 *
 * Generic over the key type so a screen can drive it from its own union
 * (`"reader" | "ai"`, `"sources" | "ai"`, …) and get an exhaustive switch on the
 * other side.
 */

import React from "react";
import { Pressable, StyleSheet, Text, View } from "react-native";
import { Ionicons } from "@expo/vector-icons";
import {
  BorderRadius,
  Colors,
  Spacing,
  TouchTarget,
  Typography,
} from "../constants/theme";

export interface ScreenTab<K extends string = string> {
  /** Stable identifier handed back to `onChange`. */
  key: K;
  /** Visible, human-readable label. */
  label: string;
  /** Optional glyph rendered before the label. */
  icon?: keyof typeof Ionicons.glyphMap;
}

interface ScreenTabsProps<K extends string> {
  tabs: readonly ScreenTab<K>[];
  activeKey: K;
  onChange: (key: K) => void;
  /** Names the group for screen readers, e.g. "Media sections". */
  accessibilityLabel?: string;
}

export function ScreenTabs<K extends string>({
  tabs,
  activeKey,
  onChange,
  accessibilityLabel,
}: ScreenTabsProps<K>): React.JSX.Element {
  return (
    <View
      style={styles.container}
      accessibilityRole="tablist"
      accessibilityLabel={accessibilityLabel}
    >
      {tabs.map((tab) => {
        const selected = tab.key === activeKey;
        return (
          <Pressable
            key={tab.key}
            style={[styles.tab, selected && styles.tabSelected]}
            onPress={() => onChange(tab.key)}
            accessibilityRole="tab"
            accessibilityLabel={tab.label}
            accessibilityState={{ selected }}
          >
            {tab.icon ? (
              <Ionicons
                name={tab.icon}
                size={18}
                color={selected ? Colors.onPrimary : Colors.textMuted}
              />
            ) : null}
            <Text style={[styles.tabLabel, selected && styles.tabLabelSelected]}>
              {tab.label}
            </Text>
          </Pressable>
        );
      })}
    </View>
  );
}

const styles = StyleSheet.create({
  // A pill of `surfaceContainerLow` on the page background: the sectioning is a
  // tonal shift, not a stroke ("No-Line rule").
  container: {
    flexDirection: "row",
    backgroundColor: Colors.surfaceContainerLow,
    borderRadius: BorderRadius.full,
    padding: Spacing.xs,
  },
  tab: {
    flex: 1,
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "center",
    gap: Spacing.sm,
    paddingHorizontal: Spacing.md,
    borderRadius: BorderRadius.full,
    minHeight: TouchTarget.minimum,
  },
  tabSelected: {
    backgroundColor: Colors.primary,
  },
  tabLabel: {
    fontSize: Typography.label.fontSize,
    fontWeight: Typography.label.fontWeight,
    color: Colors.textMuted,
  },
  tabLabelSelected: {
    color: Colors.onPrimary,
    fontWeight: "600",
  },
});
