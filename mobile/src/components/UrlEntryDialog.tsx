/**
 * Where the URL of a media is typed or pasted (task-379): one field, and the two
 * answers a link prompt can get.
 *
 * A surface of the app rather than a system prompt. `Alert.prompt` is iOS-only —
 * it does not exist on Android — so a dialog of our own is the only shape that can
 * be the same on both platforms. It is a centred card for the same reason
 * `RenameDialog` is: a one-field entry reached from a menu, with the screen it was
 * opened from still visible behind the scrim.
 *
 * Pasting is the keyboard's own paste, which every platform offers on a long press
 * in a text field. There is deliberately no "Paste" button: reading the clipboard
 * needs `expo-clipboard`, and that is a native module and therefore a new build —
 * out of the scope of this entry.
 *
 * Validation and submission belong to the caller. This component only reports what
 * was typed and shows the refusal it is handed back, so the field keeps its
 * content and a correction costs one tap rather than a retype.
 */

import {
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

export interface UrlEntryDialogProps {
  visible: boolean;
  /**
   * What the field shows. Held by the caller, which clears it when the dialog is
   * opened — so every opening starts empty rather than from a draft left over
   * from a cancelled entry.
   */
  value: string;
  onChangeText: (value: string) => void;
  /** Translated refusal of the last attempt, or `null`. */
  errorMessage: string | null;
  onClose: () => void;
  /** The raw text of the field: the caller extracts the URL from it. */
  onSubmit: (text: string) => void;
}

export function UrlEntryDialog({
  visible,
  value,
  onChangeText,
  errorMessage,
  onClose,
  onSubmit,
}: UrlEntryDialogProps): React.JSX.Element {
  const canSubmit = value.trim().length > 0;

  const handleSubmit = () => {
    if (!canSubmit) return;
    onSubmit(value);
  };

  return (
    <Modal
      visible={visible}
      transparent
      animationType="fade"
      statusBarTranslucent
      onRequestClose={onClose}
    >
      <View style={styles.root}>
        {/* Scrim. The design system has no scrim token, so this is textMain at
            35% — the only literal colour in this file, kept in sync with
            RenameDialog and the context menu. */}
        <Pressable
          style={styles.backdrop}
          onPress={onClose}
          accessibilityLabel={t("common.dismiss")}
          accessibilityRole="button"
        />

        <KeyboardAvoidingView
          style={styles.centering}
          behavior={Platform.OS === "ios" ? "padding" : undefined}
          pointerEvents="box-none"
        >
          <View style={styles.card} testID="add-url-dialog">
            <Text style={styles.title}>{t("addUrl.title")}</Text>

            <TextInput
              style={styles.input}
              value={value}
              onChangeText={onChangeText}
              placeholder={t("addUrl.placeholder")}
              placeholderTextColor={Colors.textMuted}
              autoFocus
              // A web address is never capitalised, never a word the dictionary
              // knows, and never one line broken into two.
              keyboardType="url"
              textContentType="URL"
              autoCapitalize="none"
              autoCorrect={false}
              spellCheck={false}
              multiline={false}
              returnKeyType="go"
              onSubmitEditing={handleSubmit}
              // The field is emptied on every opening, so this only ever clears a
              // paste the user wants to redo.
              clearButtonMode="while-editing"
              accessibilityLabel={t("addUrl.title")}
              testID="add-url-input"
            />

            {errorMessage ? (
              <Text style={styles.error} testID="add-url-error">
                {errorMessage}
              </Text>
            ) : (
              <Text style={styles.hint}>{t("addUrl.hint")}</Text>
            )}

            <View style={styles.actions}>
              <Pressable
                style={({ pressed }) => [
                  styles.secondaryButton,
                  pressed && styles.secondaryButtonPressed,
                ]}
                onPress={onClose}
                accessibilityLabel={t("common.cancel")}
                accessibilityRole="button"
                testID="add-url-cancel"
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
                accessibilityLabel={t("addUrl.submit")}
                accessibilityRole="button"
                accessibilityState={{ disabled: !canSubmit }}
                testID="add-url-submit"
              >
                <Text style={styles.primaryLabel}>{t("addUrl.submit")}</Text>
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
    // A URL is stable ASCII, so it stays left-to-right even when the interface
    // language is not: an Arabic UI must not reorder the address being typed.
    textAlign: "left",
    writingDirection: "ltr",
  },
  hint: {
    fontSize: Typography.small.fontSize,
    color: Colors.textSubtle,
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
