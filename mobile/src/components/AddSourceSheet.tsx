/**
 * Bottom sheet offering the two browse-and-choose ways into the inbox
 * (task-264): importing a file, or picking a photo from the gallery. Taking a
 * photo is a button of its own on the inbox — it needs no choice beforehand.
 *
 * Kept as a plain RN Modal rather than a router screen: it is a two-line choice,
 * and the gesture it triggers already presents its own full-screen surface right
 * after.
 */

import { useRef } from "react";
import { Modal, Platform, Pressable, StyleSheet, Text, View } from "react-native";
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

interface AddSourceSheetProps {
  visible: boolean;
  onClose: () => void;
  onImportFile: () => void;
  onImportPhoto: () => void;
}

export function AddSourceSheet({
  visible,
  onClose,
  onImportFile,
  onImportPhoto,
}: AddSourceSheetProps) {
  const insets = useSafeAreaInsets();
  const pendingAction = useRef<(() => void) | null>(null);

  /**
   * iOS presents a system picker on the topmost view controller. Asking for one
   * while this modal is still sliding out attaches it to a controller that is
   * about to disappear: the picker never shows and its promise never settles,
   * so the next attempt is refused as "picking already in progress". Deferring
   * to `onDismiss` guarantees the modal is gone first. Android has no such
   * conflict — the pickers are activities, and `onDismiss` never fires there.
   */
  const runAfterClose = (action: () => void) => {
    if (Platform.OS === "ios") {
      pendingAction.current = action;
      onClose();
      return;
    }
    onClose();
    action();
  };

  const handleDismissed = () => {
    const action = pendingAction.current;
    pendingAction.current = null;
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
            35% — the only literal colour in this file, kept in sync with it. */}
        <Pressable
          style={styles.backdrop}
          onPress={onClose}
          accessibilityLabel={t("common.dismiss")}
          accessibilityRole="button"
        />

        <View
          style={[
            styles.sheet,
            { paddingBottom: insets.bottom + Spacing.lg },
          ]}
        >
          <View style={styles.handle} />
          <Text style={styles.title}>{t("addSource.title")}</Text>

          <SourceRow
            icon="document-attach-outline"
            label={t("addSource.importFile.label")}
            description={t("addSource.importFile.description")}
            onPress={() => runAfterClose(onImportFile)}
          />
          <SourceRow
            icon="images-outline"
            label={t("addSource.importPhoto.label")}
            description={t("addSource.importPhoto.description")}
            onPress={() => runAfterClose(onImportPhoto)}
          />
        </View>
      </View>
    </Modal>
  );
}

function SourceRow({
  icon,
  label,
  description,
  onPress,
}: {
  icon: keyof typeof Ionicons.glyphMap;
  label: string;
  description: string;
  onPress: () => void;
}) {
  return (
    <Pressable
      style={({ pressed }) => [styles.row, pressed && styles.rowPressed]}
      onPress={onPress}
      accessibilityLabel={label}
      accessibilityRole="button"
    >
      <View style={styles.rowIcon}>
        <Ionicons name={icon} size={22} color={Colors.textMain} />
      </View>
      <View style={styles.rowTextSection}>
        <Text style={styles.rowLabel}>{label}</Text>
        <Text style={styles.rowDescription}>{description}</Text>
      </View>
      <Ionicons name="chevron-forward" size={20} color={Colors.textMuted} />
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
  title: {
    fontSize: Typography.headline.fontSize,
    fontWeight: Typography.headline.fontWeight,
    color: Colors.textMain,
    marginBottom: Spacing.xs,
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
  rowIcon: {
    width: TouchTarget.minimum,
    height: TouchTarget.minimum,
    borderRadius: BorderRadius.full,
    backgroundColor: Colors.surfaceContainerHigh,
    alignItems: "center",
    justifyContent: "center",
  },
  rowTextSection: {
    flex: 1,
    gap: Spacing.xs,
  },
  rowLabel: {
    fontSize: Typography.body.fontSize,
    fontWeight: "600",
    color: Colors.textMain,
  },
  rowDescription: {
    fontSize: Typography.small.fontSize,
    color: Colors.textMuted,
  },
});
