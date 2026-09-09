import React from "react";
import { View, Text, StyleSheet } from "react-native";
import { Ionicons } from "@expo/vector-icons";
import {
  Colors,
  Typography,
  Spacing,
  BorderRadius,
} from "../constants/theme";
import { t } from "../i18n";

/**
 * The one marker that says an import failed, wherever a saved media is drawn as a
 * vignette (task-381).
 *
 * `MediaListItem.status` has always been served by `GET /api/media` and was read
 * nowhere: a media that failed looked exactly like one that succeeded in the
 * Library and on Home, and the only way to find out was to open it. This is what
 * closes that gap, and it is one component for the same reason `getMediaTypeIcon`
 * is one function — two copies of a badge is how the same item ends up looking
 * failed on one screen and fine on the next.
 *
 * Filled `error`, not `errorContainer`. The soft red container is already the
 * background `getMediaTypeBgColor` gives the VIDEO and SHORT type badges, and a
 * second pill of that exact tint sitting beside one of them reads as a second type
 * rather than as an alarm.
 *
 * Both surfaces mark themselves `accessible={false}`: the row and the tile each
 * announce their own failure inside their single label (see `describeWithFailure`),
 * so a screen reader must not also stop on the pill and read "FAILED" twice.
 */
export function MediaFailureBadge(): React.JSX.Element {
  return (
    <View style={styles.badge} accessible={false}>
      <Ionicons
        name="alert-circle"
        size={Typography.small.fontSize}
        color={Colors.onError}
      />
      <Text style={styles.label}>{t("mediaStatus.failedBadge")}</Text>
    </View>
  );
}

/**
 * The library-entry status that earns a marker, and the only one.
 *
 * `pending` and `processing` mean the item is on its way and will change on its
 * own; `ready` is the norm. A row with no status at all is a search hit, which
 * carries none by contract.
 */
export function isFailedLibraryStatus(status?: string | null): boolean {
  return status === "failed";
}

/**
 * The vignette's accessibility label, with the failure folded into it.
 *
 * A wrapper key rather than a comma glued on in code: where the clause goes, and
 * what separates it from what precedes it, is a property of the language. It also
 * keeps the four labels already in the catalogues (`mediaCard.a11yByCreator`,
 * `mediaCard.a11yFromDomain`, `home.tile.a11yByCreator`, `home.tile.a11yFolder`)
 * as the single source of the base sentence — none of them is duplicated into a
 * failed variant.
 */
export function describeWithFailure(label: string, failed: boolean): string {
  return failed ? t("mediaStatus.a11yFailed", { label }) : label;
}

const styles = StyleSheet.create({
  badge: {
    flexDirection: "row",
    alignItems: "center",
    gap: Spacing.xs,
    paddingHorizontal: Spacing.sm,
    // Half a step: the pill has to sit on the same optical line as the type badge
    // beside it, which is padded by the same amount.
    paddingVertical: Spacing.xs / 2,
    borderRadius: BorderRadius.md,
    backgroundColor: Colors.error,
  },
  label: {
    fontSize: Typography.small.fontSize,
    fontWeight: "700",
    color: Colors.onError,
    letterSpacing: 0.5,
  },
});
