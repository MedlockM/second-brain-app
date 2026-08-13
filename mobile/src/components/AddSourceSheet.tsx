/**
 * Bottom sheet offering the two device-side ways into the inbox (task-264):
 * importing a file, or taking a photo.
 *
 * Kept as a plain RN Modal rather than a router screen: it is a two-line choice,
 * and the gesture it triggers (file browser, camera) already presents its own
 * full-screen surface right after. The sheet closes before that happens so the
 * system picker is never stacked on top of a modal.
 */

import { Modal, Pressable, StyleSheet, Text, View } from "react-native";
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

interface AddSourceSheetProps {
  visible: boolean;
  onClose: () => void;
  onImportFile: () => void;
  onTakePhoto: () => void;
}

export function AddSourceSheet({
  visible,
  onClose,
  onImportFile,
  onTakePhoto,
}: AddSourceSheetProps) {
  const insets = useSafeAreaInsets();

  return (
    <Modal
      visible={visible}
      transparent
      animationType="slide"
      onRequestClose={onClose}
      statusBarTranslucent
    >
      <View style={styles.root}>
        {/* Scrim. The design system has no scrim token, so this is textMain at
            35% — the only literal colour in this file, kept in sync with it. */}
        <Pressable
          style={styles.backdrop}
          onPress={onClose}
          accessibilityLabel="Dismiss"
          accessibilityRole="button"
        />

        <View
          style={[
            styles.sheet,
            { paddingBottom: insets.bottom + Spacing.lg },
          ]}
        >
          <View style={styles.handle} />
          <Text style={styles.title}>Add to your inbox</Text>

          <SourceRow
            icon="document-attach-outline"
            label="Import a file"
            description="A PDF, an Office document, an image or an audio file from your phone."
            onPress={onImportFile}
          />
          <SourceRow
            icon="camera-outline"
            label="Take a photo"
            description="Capture a page or a whiteboard and send it in straight away."
            onPress={onTakePhoto}
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
