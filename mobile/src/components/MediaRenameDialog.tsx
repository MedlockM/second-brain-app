/**
 * Where a rename is typed: one field, prefilled with the title the media has
 * now, and the two answers a naming prompt can get.
 *
 * A centred dialog rather than a full screen. The rename is a one-field edit
 * reached from a context menu, and pushing a route for it would take the user
 * away from the list they were filing — the list stays visible behind the scrim,
 * which is what makes the new name land somewhere recognisable.
 *
 * A failure is reported *inside* the dialog rather than through an alert: the
 * field keeps what was typed, so retrying is one tap and nothing has to be
 * typed twice. The message is handed down already translated by
 * `useMediaActions`, which owns the call.
 */

import {
  ActivityIndicator,
  KeyboardAvoidingView,
  Modal,
  Platform,
  Pressable,
  StyleSheet,
  Text,
  TextInput,
  View,
} from "react-native";
import {
  BorderRadius,
  Colors,
  Shadows,
  Spacing,
  TouchTarget,
  Typography,
} from "../constants/theme";
import { t } from "../i18n";

/**
 * The server's own ceiling (`MAX_TITLE_LENGTH` in
 * `media_summarizer/core/media_ingestion/title_derivation.py`), mirrored here so
 * the field stops accepting characters the `PATCH` would reject.
 */
const MAX_TITLE_LENGTH = 120;

export interface MediaRenameDialogProps {
  visible: boolean;
  /**
   * What the field shows. Held by `useMediaActions`, which seeds it with the
   * media's current title when the dialog is opened — so every opening starts
   * from the stored name rather than from a draft left over from a cancelled
   * rename, and no state here has to be resynchronised behind the props.
   */
  value: string;
  onChangeText: (value: string) => void;
  /** The `PATCH` is in flight: the field is locked and Save shows a spinner. */
  isSaving: boolean;
  /** Translated failure of the last attempt, or `null`. */
  errorMessage: string | null;
  onClose: () => void;
  onSubmit: (title: string) => void;
}

export function MediaRenameDialog({
  visible,
  value,
  onChangeText,
  isSaving,
  errorMessage,
  onClose,
  onSubmit,
}: MediaRenameDialogProps): React.JSX.Element {
  const trimmed = value.trim();
  const canSubmit = trimmed.length > 0 && !isSaving;

  const handleSubmit = () => {
    if (!canSubmit) return;
    onSubmit(trimmed);
  };

  return (
    <Modal
      visible={visible}
      transparent
      animationType="fade"
      statusBarTranslucent
      onRequestClose={isSaving ? undefined : onClose}
    >
      <View style={styles.root}>
        {/* Scrim. The design system has no scrim token, so this is textMain at
            35% — the only literal colour in this file, kept in sync with the
            context menu. */}
        <Pressable
          style={styles.backdrop}
          onPress={onClose}
          disabled={isSaving}
          accessibilityLabel={t("common.dismiss")}
          accessibilityRole="button"
        />

        <KeyboardAvoidingView
          style={styles.centering}
          behavior={Platform.OS === "ios" ? "padding" : undefined}
          pointerEvents="box-none"
        >
          <View style={styles.card} testID="media-rename-dialog">
            <Text style={styles.title}>{t("mediaActions.rename.title")}</Text>

            <TextInput
              style={styles.input}
              value={value}
              onChangeText={onChangeText}
              placeholder={t("mediaActions.rename.placeholder")}
              placeholderTextColor={Colors.textMuted}
              autoFocus
              selectTextOnFocus
              editable={!isSaving}
              maxLength={MAX_TITLE_LENGTH}
              returnKeyType="done"
              onSubmitEditing={handleSubmit}
              accessibilityLabel={t("mediaActions.rename.title")}
              testID="media-rename-input"
            />

            {errorMessage ? (
              <Text style={styles.error} testID="media-rename-error">
                {errorMessage}
              </Text>
            ) : null}

            <View style={styles.actions}>
              <Pressable
                style={({ pressed }) => [
                  styles.secondaryButton,
                  pressed && styles.secondaryButtonPressed,
                ]}
                onPress={onClose}
                disabled={isSaving}
                accessibilityLabel={t("common.cancel")}
                accessibilityRole="button"
                testID="media-rename-cancel"
              >
                <Text style={styles.secondaryLabel}>{t("common.cancel")}</Text>
              </Pressable>

              <Pressable
                style={({ pressed }) => [
                  styles.primaryButton,
                  pressed && styles.primaryButtonPressed,
                  !canSubmit && styles.primaryButtonDisabled,
                ]}
                onPress={handleSubmit}
                disabled={!canSubmit}
                accessibilityLabel={t("common.save")}
                accessibilityRole="button"
                accessibilityState={{ disabled: !canSubmit }}
                testID="media-rename-save"
              >
                {isSaving ? (
                  <ActivityIndicator size="small" color={Colors.onPrimary} />
                ) : (
                  <Text style={styles.primaryLabel}>{t("common.save")}</Text>
                )}
              </Pressable>
            </View>
          </View>
        </KeyboardAvoidingView>
      </View>
    </Modal>
  );
}

const styles = StyleSheet.create({
  root: {
    flex: 1,
  },
  backdrop: {
    ...StyleSheet.absoluteFillObject,
    backgroundColor: "rgba(43, 45, 66, 0.35)",
  },
  centering: {
    flex: 1,
    justifyContent: "center",
    paddingHorizontal: Spacing.lg,
  },
  card: {
    backgroundColor: Colors.surface,
    borderRadius: BorderRadius.xl,
    padding: Spacing.lg,
    gap: Spacing.md,
    ...Shadows.soft,
  },
  title: {
    fontSize: Typography.headline.fontSize,
    fontWeight: Typography.headline.fontWeight,
    color: Colors.textMain,
  },
  // A tonal shift instead of a border: the field reads as a recessed surface,
  // which is how the design system separates without lines.
  input: {
    minHeight: TouchTarget.minimum,
    backgroundColor: Colors.surfaceContainerLow,
    borderRadius: BorderRadius.lg,
    paddingHorizontal: Spacing.md,
    paddingVertical: Spacing.sm,
    fontSize: Typography.body.fontSize,
    color: Colors.textMain,
  },
  error: {
    fontSize: Typography.small.fontSize,
    color: Colors.error,
  },
  actions: {
    flexDirection: "row",
    justifyContent: "flex-end",
    gap: Spacing.sm,
  },
  secondaryButton: {
    minHeight: TouchTarget.minimum,
    paddingHorizontal: Spacing.md,
    alignItems: "center",
    justifyContent: "center",
    borderRadius: BorderRadius.lg,
  },
  secondaryButtonPressed: {
    backgroundColor: Colors.surfaceContainerLow,
  },
  secondaryLabel: {
    fontSize: Typography.label.fontSize,
    fontWeight: Typography.label.fontWeight,
    color: Colors.textSubtle,
  },
  primaryButton: {
    minHeight: TouchTarget.minimum,
    minWidth: TouchTarget.large,
    paddingHorizontal: Spacing.lg,
    alignItems: "center",
    justifyContent: "center",
    borderRadius: BorderRadius.lg,
    backgroundColor: Colors.primary,
  },
  primaryButtonPressed: {
    opacity: 0.9,
  },
  primaryButtonDisabled: {
    opacity: 0.5,
  },
  primaryLabel: {
    fontSize: Typography.label.fontSize,
    fontWeight: "600",
    color: Colors.onPrimary,
  },
});
