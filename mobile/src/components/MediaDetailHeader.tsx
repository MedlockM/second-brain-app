/**
 * The media screen's own title bar: back on the left, and on the right the two
 * things that can be done to the item — file it, or act on it.
 *
 * Both right-hand slots are optional and both are only filled once the item has
 * resolved. The loading, processing, timeout and failure states carry the back
 * arrow alone: they hold no title to seed a rename field with, and a menu whose
 * first row could not be prefilled is worse than no menu.
 *
 * It lives in its own module because two hosts render it: the route
 * (`app/media/[id].tsx`) for those lifecycle states, and `CompletedDetailView`
 * for the resolved item. The bar stays hand-built rather than moving to
 * `ScreenHeader` — this header carries no title, and its two trailing slots do
 * not map onto that component's single trailing slot.
 */

import React from "react";
import { Pressable, StyleSheet, View } from "react-native";
import { Ionicons } from "@expo/vector-icons";
import {
  BorderRadius,
  Colors,
  Spacing,
  TouchTarget,
} from "../constants/theme";
import { t } from "../i18n";
import { HeaderMenuButton } from "./ScreenHeader";
import type { AnchorRect } from "./AnchoredContextMenu";

export function MediaDetailHeader({
  onBack,
  collectionId,
  onCollectionPress,
  onActionsPress,
}: {
  onBack: () => void;
  collectionId?: string | null;
  onCollectionPress?: () => void;
  /** Opens the rename/delete menu, anchored on the `…` that was tapped. */
  onActionsPress?: (anchor: AnchorRect) => void;
}): React.JSX.Element {
  const hasCollection = !!collectionId;

  return (
    <View style={styles.header}>
      <Pressable
        style={styles.headerButton}
        onPress={onBack}
        accessibilityLabel={t("common.goBack")}
        accessibilityRole="button"
        hitSlop={{ top: 4, bottom: 4, left: 4, right: 4 }}
      >
        <Ionicons name="arrow-back" size={24} color={Colors.textMain} />
      </Pressable>
      <View style={styles.headerRightGroup}>
        {onCollectionPress && (
          <Pressable
            style={styles.headerButton}
            onPress={onCollectionPress}
            accessibilityLabel={t("media.moveToCollectionA11y")}
            accessibilityRole="button"
            hitSlop={{ top: 4, bottom: 4, left: 4, right: 4 }}
          >
            <Ionicons
              name={hasCollection ? "folder" : "folder-outline"}
              size={24}
              color={hasCollection ? Colors.primary : Colors.textMain}
            />
          </Pressable>
        )}
        {onActionsPress && (
          <HeaderMenuButton
            onPress={onActionsPress}
            accessibilityLabel={t("mediaActions.moreA11y")}
            testID="media-header-actions"
          />
        )}
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  // Header - buttons meet 48px with hitSlop
  header: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    paddingHorizontal: Spacing.md,
    paddingVertical: Spacing.sm,
    minHeight: TouchTarget.comfortable,
  },
  headerButton: {
    width: 44,
    height: 44,
    borderRadius: BorderRadius.full,
    justifyContent: "center",
    alignItems: "center",
  },
  headerRightGroup: {
    flexDirection: "row",
    alignItems: "center",
    gap: Spacing.xs,
  },
});
