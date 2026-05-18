import { useState, useEffect, useCallback, useRef } from "react";
import {
  View,
  Text,
  TextInput,
  TouchableOpacity,
  StyleSheet,
  Animated,
  ActivityIndicator,
  Keyboard,
} from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";
import { useRouter, useLocalSearchParams } from "expo-router";
import { Ionicons } from "@expo/vector-icons";
import { Colors, Typography, Spacing, BorderRadius, Shadows, TouchTarget } from "../src/constants/theme";
import { useAuth } from "../src/contexts/AuthContext";
import { useInbox } from "../src/contexts/InboxContext";
import { useIsOnline } from "../src/hooks/useNetworkStatus";
import { MediaService } from "../src/services/mediaService";
import { OfflineQueue } from "../src/services/offlineQueue";
import { validateShareInput } from "../src/lib/urlValidation";
import { getFriendlyErrorMessage } from "../src/lib/getFriendlyErrorMessage";

type SubmitState = "idle" | "submitting" | "success" | "queued" | "error";

/**
 * Share Confirmation Screen.
 * Shown as a modal when a URL is shared from an external app.
 * Design follows mobile-design-mockups/confirmation_de_partage_version_finale/.
 *
 * Layout: Close (X) | Title | Save button
 *         URL preview card with note field
 *         Folder selector
 *         Tags selector
 *
 * Offline behavior (AC#6): When device is offline, the URL is queued
 * in persistent storage and will be submitted when connectivity returns.
 */
export default function ShareConfirmScreen() {
  const router = useRouter();
  const params = useLocalSearchParams<{ url?: string; sourceApp?: string }>();
  const { token } = useAuth();
  const { addItem, markSubmitted, markFailed } = useInbox();
  const isOnline = useIsOnline();

  const [sharedUrl, setSharedUrl] = useState(params.url ?? "");
  const [note, setNote] = useState("");
  const [submitState, setSubmitState] = useState<SubmitState>("idle");
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [validationError, setValidationError] = useState<string | null>(null);

  // Animations
  const successOpacity = useRef(new Animated.Value(0)).current;
  const successScale = useRef(new Animated.Value(0.8)).current;
  const cardOpacity = useRef(new Animated.Value(1)).current;

  // Validate the URL on mount
  useEffect(() => {
    if (sharedUrl) {
      const result = validateShareInput(sharedUrl);
      if (!result.valid) {
        setValidationError(result.error);
      } else {
        setSharedUrl(result.url);
        setValidationError(null);
      }
    }
  }, []);

  const handleClose = useCallback(() => {
    if (router.canGoBack()) {
      router.back();
    } else {
      router.replace("/(tabs)/inbox");
    }
  }, [router]);

  const handleSave = useCallback(async () => {
    Keyboard.dismiss();

    // Re-validate
    const result = validateShareInput(sharedUrl);
    if (!result.valid) {
      setValidationError(result.error);
      return;
    }

    if (!token) {
      setErrorMessage("Please sign in to save links.");
      setSubmitState("error");
      return;
    }

    // Offline behavior (AC#6): queue for later if not connected
    if (!isOnline) {
      await OfflineQueue.enqueue(
        result.url,
        params.sourceApp ?? "ios-share-extension",
      );
      setSubmitState("queued");

      // Animate queued feedback
      Animated.parallel([
        Animated.timing(successOpacity, {
          toValue: 1,
          duration: 300,
          useNativeDriver: true,
        }),
        Animated.spring(successScale, {
          toValue: 1,
          friction: 5,
          useNativeDriver: true,
        }),
        Animated.timing(cardOpacity, {
          toValue: 0.6,
          duration: 300,
          useNativeDriver: true,
        }),
      ]).start();

      // Auto-dismiss after queued confirmation
      setTimeout(() => {
        handleClose();
      }, 1500);
      return;
    }

    setSubmitState("submitting");
    setErrorMessage(null);

    const localId = addItem(result.url, params.sourceApp);

    try {
      const response = await MediaService.ingestUrl(
        token,
        {
          url: result.url,
          source_app: params.sourceApp ?? "ios-share-extension",
          idempotency_key: localId,
        },
      );

      markSubmitted(localId, response);
      setSubmitState("success");

      // Animate success
      Animated.parallel([
        Animated.timing(successOpacity, {
          toValue: 1,
          duration: 300,
          useNativeDriver: true,
        }),
        Animated.spring(successScale, {
          toValue: 1,
          friction: 5,
          useNativeDriver: true,
        }),
        Animated.timing(cardOpacity, {
          toValue: 0.6,
          duration: 300,
          useNativeDriver: true,
        }),
      ]).start();

      // Auto-dismiss after success
      setTimeout(() => {
        handleClose();
      }, 1500);
    } catch (error) {
      const friendlyMessage = getFriendlyErrorMessage(error, {
        fallback: "Failed to save this link. Please try again.",
      });
      markFailed(localId, friendlyMessage);
      setErrorMessage(friendlyMessage);
      setSubmitState("error");
    }
  }, [
    sharedUrl,
    token,
    isOnline,
    params.sourceApp,
    addItem,
    markSubmitted,
    markFailed,
    handleClose,
    successOpacity,
    successScale,
    cardOpacity,
  ]);

  const displayUrl = getDomainFromUrl(sharedUrl);

  return (
    <SafeAreaView style={styles.container} edges={["top", "bottom"]}>
      {/* Header */}
      <View style={styles.header}>
        <TouchableOpacity
          style={styles.closeButton}
          onPress={handleClose}
          accessibilityLabel="Close"
          accessibilityRole="button"
        >
          <Ionicons name="close" size={22} color={Colors.textMain} />
        </TouchableOpacity>

        <Text style={styles.headerTitle}>Collection</Text>

        <TouchableOpacity
          style={[
            styles.saveButton,
            (submitState === "submitting" || !!validationError) &&
              styles.saveButtonDisabled,
          ]}
          onPress={handleSave}
          disabled={submitState === "submitting" || !!validationError}
          accessibilityLabel="Save"
          accessibilityRole="button"
        >
          {submitState === "submitting" ? (
            <ActivityIndicator size="small" color={Colors.onPrimary} />
          ) : (
            <Text style={styles.saveButtonText}>Save</Text>
          )}
        </TouchableOpacity>
      </View>

      {/* Content */}
      <View style={styles.content}>
        {/* URL Preview Card */}
        <Animated.View style={[styles.previewCard, { opacity: cardOpacity }]}>
          <View style={styles.previewContent}>
            <View style={styles.previewTextContainer}>
              <Text style={styles.previewUrl} numberOfLines={3}>
                {sharedUrl || "No URL"}
              </Text>
              <Text style={styles.previewDomain} numberOfLines={1}>
                {displayUrl}
              </Text>
            </View>
          </View>

          {/* Note input */}
          <View style={styles.noteContainer}>
            <TextInput
              style={styles.noteInput}
              placeholder="Note"
              placeholderTextColor={Colors.textMuted}
              value={note}
              onChangeText={setNote}
              returnKeyType="done"
              onSubmitEditing={Keyboard.dismiss}
              maxLength={500}
            />
          </View>
        </Animated.View>

        {/* Validation error */}
        {validationError && (
          <View style={styles.errorBanner}>
            <Ionicons
              name="alert-circle-outline"
              size={18}
              color={Colors.error}
            />
            <Text style={styles.errorText}>{validationError}</Text>
          </View>
        )}

        {/* Submission error */}
        {submitState === "error" && errorMessage && (
          <View style={styles.errorBanner}>
            <Ionicons
              name="alert-circle-outline"
              size={18}
              color={Colors.error}
            />
            <Text style={styles.errorText}>{errorMessage}</Text>
            <TouchableOpacity onPress={handleSave} style={styles.retryButton}>
              <Text style={styles.retryText}>Retry</Text>
            </TouchableOpacity>
          </View>
        )}

        {/* Folder / Tags selectors (UI scaffolding, non-functional for V1) */}
        <View style={styles.organizationSection}>
          <TouchableOpacity style={styles.organizationRow}>
            <View style={styles.organizationRowLeft}>
              <Ionicons
                name="folder-open-outline"
                size={20}
                color={Colors.textMuted}
              />
              <Text style={styles.organizationRowLabel}>Unsorted</Text>
            </View>
            <Ionicons
              name="chevron-forward"
              size={20}
              color={Colors.textMuted}
            />
          </TouchableOpacity>

          <TouchableOpacity style={styles.organizationRow}>
            <View style={styles.organizationRowLeft}>
              <Ionicons
                name="pricetag-outline"
                size={20}
                color={Colors.textMuted}
              />
              <Text style={styles.organizationRowLabel}>Tags</Text>
            </View>
            <Ionicons
              name="chevron-forward"
              size={20}
              color={Colors.textMuted}
            />
          </TouchableOpacity>
        </View>

        {/* Success overlay */}
        {submitState === "success" && (
          <Animated.View
            style={[
              styles.successOverlay,
              {
                opacity: successOpacity,
                transform: [{ scale: successScale }],
              },
            ]}
          >
            <Ionicons
              name="checkmark-circle"
              size={64}
              color={Colors.primary}
            />
            <Text style={styles.successText}>Saved</Text>
          </Animated.View>
        )}

        {/* Queued offline overlay (AC#6) */}
        {submitState === "queued" && (
          <Animated.View
            style={[
              styles.successOverlay,
              {
                opacity: successOpacity,
                transform: [{ scale: successScale }],
              },
            ]}
          >
            <Ionicons
              name="cloud-offline-outline"
              size={64}
              color={Colors.primary}
            />
            <Text style={styles.successText}>Queued for sync</Text>
            <Text style={styles.queuedHint}>
              Will be submitted when you reconnect
            </Text>
          </Animated.View>
        )}
      </View>
    </SafeAreaView>
  );
}

/**
 * Extract a display-friendly domain from a URL.
 */
function getDomainFromUrl(url: string): string {
  try {
    const parsed = new URL(url);
    return parsed.hostname.replace(/^www\./, "");
  } catch {
    return url;
  }
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: Colors.background,
  },
  header: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    paddingHorizontal: Spacing.md,
    paddingVertical: Spacing.sm,
  },
  closeButton: {
    width: 44,
    height: 44,
    borderRadius: BorderRadius.full,
    backgroundColor: Colors.surfaceContainerHigh,
    alignItems: "center",
    justifyContent: "center",
  },
  headerTitle: {
    fontSize: Typography.headline.fontSize,
    fontWeight: Typography.headline.fontWeight,
    color: Colors.textMain,
  },
  saveButton: {
    backgroundColor: Colors.primary,
    paddingHorizontal: Spacing.md,
    paddingVertical: Spacing.sm,
    borderRadius: BorderRadius.full,
    minWidth: 80,
    minHeight: TouchTarget.minimum,
    alignItems: "center",
    justifyContent: "center",
  },
  saveButtonDisabled: {
    opacity: 0.5,
  },
  saveButtonText: {
    fontSize: Typography.label.fontSize,
    fontWeight: "700",
    color: Colors.onPrimary,
  },
  content: {
    flex: 1,
    paddingHorizontal: Spacing.lg,
    paddingTop: Spacing.lg,
  },
  previewCard: {
    backgroundColor: Colors.surfaceContainerLow,
    borderRadius: BorderRadius.xl,
    padding: Spacing.lg,
    ...Shadows.soft,
    borderWidth: StyleSheet.hairlineWidth,
    borderColor: Colors.outlineVariant,
  },
  previewContent: {
    flexDirection: "row",
    gap: Spacing.md,
  },
  previewTextContainer: {
    flex: 1,
    gap: Spacing.xs,
  },
  previewUrl: {
    fontSize: Typography.headline.fontSize,
    fontWeight: Typography.headline.fontWeight,
    color: Colors.textMain,
    lineHeight: 26,
  },
  previewDomain: {
    fontSize: Typography.small.fontSize,
    color: Colors.textMuted,
    marginTop: Spacing.xs,
  },
  noteContainer: {
    marginTop: Spacing.md,
    paddingTop: Spacing.md,
    borderTopWidth: StyleSheet.hairlineWidth,
    borderTopColor: Colors.outlineVariant,
  },
  noteInput: {
    fontSize: Typography.body.fontSize,
    color: Colors.textMain,
    padding: 0,
    minHeight: 24,
  },
  errorBanner: {
    flexDirection: "row",
    alignItems: "center",
    gap: Spacing.sm,
    marginTop: Spacing.md,
    paddingHorizontal: Spacing.md,
    paddingVertical: Spacing.sm,
    backgroundColor: Colors.errorContainer,
    borderRadius: BorderRadius.lg,
  },
  errorText: {
    flex: 1,
    fontSize: Typography.small.fontSize,
    color: Colors.error,
  },
  retryButton: {
    paddingHorizontal: Spacing.sm,
    paddingVertical: Spacing.xs,
  },
  retryText: {
    fontSize: Typography.small.fontSize,
    fontWeight: "600",
    color: Colors.error,
  },
  organizationSection: {
    marginTop: Spacing.lg,
    gap: Spacing.sm,
  },
  organizationRow: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    paddingHorizontal: Spacing.md,
    paddingVertical: Spacing.md,
    backgroundColor: Colors.surfaceContainerLow,
    borderRadius: BorderRadius.xl,
    minHeight: TouchTarget.comfortable,
  },
  organizationRowLeft: {
    flexDirection: "row",
    alignItems: "center",
    gap: Spacing.sm,
  },
  organizationRowLabel: {
    fontSize: 15,
    fontWeight: "500",
    color: Colors.textMain,
  },
  successOverlay: {
    position: "absolute",
    top: 0,
    left: 0,
    right: 0,
    bottom: 0,
    alignItems: "center",
    justifyContent: "center",
  },
  successText: {
    marginTop: Spacing.sm,
    fontSize: Typography.headline.fontSize,
    fontWeight: Typography.headline.fontWeight,
    color: Colors.textMain,
  },
  queuedHint: {
    marginTop: Spacing.xs,
    fontSize: Typography.small.fontSize,
    color: Colors.textMuted,
    textAlign: "center",
  },
});
