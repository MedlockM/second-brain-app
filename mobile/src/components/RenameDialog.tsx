/**
 * Where a rename is typed: one field, prefilled with the name the thing has now,
 * and the two answers a naming prompt can get.
 *
 * A centred dialog rather than a full screen. A rename is a one-field edit
 * reached from a context menu, and pushing a route for it would take the user
 * away from the list they were filing — the list stays visible behind the scrim,
 * which is what makes the new name land somewhere recognisable.
 *
 * One dialog for every target. A media title and a collection name differ in
 * three things and nothing else: the heading, the placeholder and the ceiling the
 * field stops at (120 for a title, 255 for a collection name), so all three are
 * props and there is no second copy of this card.
 *
 * A failure is reported *inside* the dialog rather than through an alert: the
 * field keeps what was typed, so retrying is one tap and nothing has to be
 * typed twice. The message is handed down already translated by the hook that
 * owns the call.
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

export interface RenameDialogProps {
  visible: boolean;
  /** Names what is being renamed, e.g. `Rename this collection`. */
  heading: string;
  placeholder: string;
  /**
   * The server's own ceiling for this kind of name, so the field stops accepting
   * characters the write would reject.
   */
  maxLength: number;
  /**
   * What the field shows. Held by the hook, which seeds it with the current name
   * when the dialog is opened — so every opening starts from the stored name
   * rather than from a draft left over from a cancelled rename, and no state here
   * has to be resynchronised behind the props.
   */
  value: string;
  onChangeText: (value: string) => void;
  /** The write is in flight: the field is locked and Save shows a spinner. */
  isSaving: boolean;
  /** Translated failure of the last attempt, or `null`. */
  errorMessage: string | null;
  onClose: () => void;
  onSubmit: (name: string) => void;
  /** Names the dialog and its controls for a flow, e.g. `media-rename`. */
  testIDPrefix: string;
}

export function RenameDialog({
  visible,
  heading,
  placeholder,
  maxLength,
  value,
  onChangeText,
  isSaving,
  errorMessage,
  onClose,
  onSubmit,
  testIDPrefix,
}: RenameDialogProps): React.JSX.Element {
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
          <View style={styles.card} testID={`${testIDPrefix}-dialog`}>
            <Text style={styles.title}>{heading}</Text>

            <TextInput
              style={styles.input}
              value={value}
              onChangeText={onChangeText}
              placeholder={placeholder}
              placeholderTextColor={Colors.textMuted}
              autoFocus
              selectTextOnFocus
              editable={!isSaving}
              maxLength={maxLength}
              returnKeyType="done"
              onSubmitEditing={handleSubmit}
              accessibilityLabel={heading}
              testID={`${testIDPrefix}-input`}
            />

            {errorMessage ? (
              <Text style={styles.error} testID={`${testIDPrefix}-error`}>
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
                testID={`${testIDPrefix}-cancel`}
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
                testID={`${testIDPrefix}-save`}
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
