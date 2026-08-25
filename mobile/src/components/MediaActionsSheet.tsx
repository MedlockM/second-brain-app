/**
 * What a long press on a media vignette in Library opens: the two things that
 * can be done to that one source — move it to another collection, or delete it.
 *
 * Shared verbatim by the two Library surfaces (the `All media` list of the
 * library tab and the sources list inside a collection) so the gesture answers
 * the same way wherever the vignette lives. The orchestration — which media is
 * targeted, the destructive confirmation, the network calls — belongs to
 * `useMediaActions`; this file is the surface only.
 *
 * A plain RN `Modal` on the `AddSourceSheet` pattern rather than a bottom-sheet
 * library: it is a two-line choice, and adding a gesture-driven dependency for
 * it would be paying an animation budget for a menu.
 *
 * The header carries the media's own title. A destructive action needs its
 * target named: "Delete" over an unlabelled sheet is a bet on the user having
 * pressed the row they meant to.
 */

import { useRef } from "react";
import {
  ActivityIndicator,
  Modal,
  Platform,
  Pressable,
  StyleSheet,
  Text,
  View,
} from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { Ionicons } from "@expo/vector-icons";
import {
  BorderRadius,
  Colors,
  Shadows,
  Spacing,
  TouchTarget,
  Typography,
} from "../constants/theme";
import { t } from "../i18n";

export interface MediaActionsSheetProps {
  visible: boolean;
  /** Title of the media the long press landed on, shown in the header. */
  title: string;
  /** A deletion is in flight: the rows are inert and Delete shows a spinner. */
  isDeleting: boolean;
  onClose: () => void;
  onMove: () => void;
  onDelete: () => void;
}

export function MediaActionsSheet({
  visible,
  title,
  isDeleting,
  onClose,
  onMove,
  onDelete,
}: MediaActionsSheetProps): React.JSX.Element {
  const insets = useSafeAreaInsets();
  const pendingMove = useRef<(() => void) | null>(null);

  /**
   * Moving pushes the collection picker, and a modal still on screen sits over
   * whatever the router pushes underneath it. On iOS the dismissal is animated,
   * so the navigation waits for `onDismiss` — otherwise the picker slides in
   * behind a sheet that is still there. Android fires no `onDismiss`, and its
   * modal is gone by the time the handler returns.
   */
  const handleMovePress = () => {
    if (Platform.OS === "ios") {
      pendingMove.current = onMove;
      onClose();
      return;
    }
    onClose();
    onMove();
  };

  const handleDismissed = () => {
    const action = pendingMove.current;
    pendingMove.current = null;
    action?.();
  };

  return (
    <Modal
      visible={visible}
      transparent
      animationType="slide"
      onRequestClose={onClose}
      onDismiss={handleDismissed}
      statusBarTranslucent
    >
      <View style={styles.root}>
        {/* Scrim. The design system has no scrim token, so this is textMain at
            35% — the only literal colour in this file, kept in sync with the
            add-source sheet. */}
        <Pressable
          style={styles.backdrop}
          onPress={onClose}
          accessibilityLabel={t("common.dismiss")}
          accessibilityRole="button"
        />

        <View
          style={[styles.sheet, { paddingBottom: insets.bottom + Spacing.lg }]}
        >
          <View style={styles.handle} />

          <View style={styles.header}>
            <Text style={styles.eyebrow}>{t("mediaActions.eyebrow")}</Text>
            <Text style={styles.title} numberOfLines={2}>
              {title}
            </Text>
          </View>

          <ActionRow
            icon="folder-outline"
            label={t("mediaActions.move.label")}
            description={t("mediaActions.move.description")}
            onPress={handleMovePress}
            disabled={isDeleting}
            testID="media-actions-move"
          />
          <ActionRow
            icon="trash-outline"
            label={t("mediaActions.delete.label")}
            description={t("mediaActions.delete.description")}
            onPress={onDelete}
            disabled={isDeleting}
            isBusy={isDeleting}
            destructive
            testID="media-actions-delete"
          />

          <Pressable
            style={({ pressed }) => [
              styles.cancelButton,
              pressed && styles.cancelButtonPressed,
            ]}
            onPress={onClose}
            disabled={isDeleting}
            accessibilityLabel={t("common.cancel")}
            accessibilityRole="button"
            testID="media-actions-cancel"
          >
            <Text style={styles.cancelLabel}>{t("common.cancel")}</Text>
          </Pressable>
        </View>
      </View>
    </Modal>
  );
}

function ActionRow({
  icon,
  label,
  description,
  onPress,
  disabled,
  isBusy = false,
  destructive = false,
  testID,
}: {
  icon: keyof typeof Ionicons.glyphMap;
  label: string;
  description: string;
  onPress: () => void;
  disabled: boolean;
  isBusy?: boolean;
  destructive?: boolean;
  testID: string;
}) {
  const tint = destructive ? Colors.error : Colors.textMain;

  return (
    <Pressable
      style={({ pressed }) => [
        styles.row,
        pressed && styles.rowPressed,
        disabled && styles.rowDisabled,
      ]}
      onPress={onPress}
      disabled={disabled}
      testID={testID}
      accessibilityLabel={label}
      accessibilityRole="button"
      accessibilityState={{ disabled }}
    >
      <View style={[styles.rowIcon, destructive && styles.rowIconDestructive]}>
        <Ionicons name={icon} size={22} color={tint} />
      </View>
      <View style={styles.rowTextSection}>
        <Text style={[styles.rowLabel, { color: tint }]}>{label}</Text>
        <Text style={styles.rowDescription}>{description}</Text>
      </View>
      {isBusy ? (
        <ActivityIndicator color={tint} />
      ) : (
        <Ionicons name="chevron-forward" size={20} color={Colors.textMuted} />
      )}
    </Pressable>
  );
}

const styles = StyleSheet.create({
  root: {
    flex: 1,
    justifyContent: "flex-end",
  },
  backdrop: {
    ...StyleSheet.absoluteFillObject,
    backgroundColor: "rgba(43, 45, 66, 0.35)",
  },
  sheet: {
    backgroundColor: Colors.surface,
    borderTopLeftRadius: BorderRadius.xl,
    borderTopRightRadius: BorderRadius.xl,
    paddingHorizontal: Spacing.lg,
    paddingTop: Spacing.sm,
    gap: Spacing.sm,
    ...Shadows.soft,
  },
  handle: {
    alignSelf: "center",
    width: Spacing.xl,
    height: Spacing.xs,
    borderRadius: BorderRadius.full,
    backgroundColor: Colors.surfaceContainerHigh,
    marginBottom: Spacing.md,
  },
  header: {
    gap: Spacing.xs,
    marginBottom: Spacing.xs,
  },
  eyebrow: {
    fontSize: Typography.small.fontSize,
    fontWeight: "700",
    color: Colors.textMuted,
    textTransform: "uppercase",
    letterSpacing: 0.5,
  },
  title: {
    fontSize: Typography.headline.fontSize,
    fontWeight: Typography.headline.fontWeight,
    color: Colors.textMain,
  },
  row: {
    flexDirection: "row",
    alignItems: "center",
    gap: Spacing.md,
    minHeight: TouchTarget.comfortable,
    paddingHorizontal: Spacing.md,
    paddingVertical: Spacing.md,
    backgroundColor: Colors.surfaceContainerLow,
    borderRadius: BorderRadius.xl,
  },
  rowPressed: {
    backgroundColor: Colors.surfaceContainerHigh,
  },
  rowDisabled: {
    opacity: 0.5,
  },
  rowIcon: {
    width: TouchTarget.minimum,
    height: TouchTarget.minimum,
    borderRadius: BorderRadius.full,
    backgroundColor: Colors.surfaceContainerHigh,
    alignItems: "center",
    justifyContent: "center",
  },
  rowIconDestructive: {
    backgroundColor: Colors.errorContainer,
  },
  rowTextSection: {
    flex: 1,
    gap: Spacing.xs,
  },
  rowLabel: {
    fontSize: Typography.body.fontSize,
    fontWeight: "600",
  },
  rowDescription: {
    fontSize: Typography.small.fontSize,
    color: Colors.textMuted,
  },
  cancelButton: {
    minHeight: TouchTarget.minimum,
    alignItems: "center",
    justifyContent: "center",
    borderRadius: BorderRadius.xl,
    marginTop: Spacing.xs,
  },
  cancelButtonPressed: {
    backgroundColor: Colors.surfaceContainerLow,
  },
  cancelLabel: {
    fontSize: Typography.label.fontSize,
    fontWeight: Typography.label.fontWeight,
    color: Colors.textSubtle,
  },
});
