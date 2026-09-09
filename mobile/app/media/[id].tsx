import {
  View,
  Text,
  StyleSheet,
  Pressable,
  ActivityIndicator,
} from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";
import { useLocalSearchParams, useRouter } from "expo-router";
import { Ionicons } from "@expo/vector-icons";
import { useMediaDetailPolling } from "../../src/hooks/useMediaDetailPolling";
import { CompletedDetailView } from "../../src/components/CompletedDetailView";
import { MediaDetailHeader } from "../../src/components/MediaDetailHeader";
import { SourceSupportRequestCard } from "../../src/components/SourceSupportRequestCard";
import {
  Colors,
  Typography,
  Spacing,
  BorderRadius,
  TouchTarget,
} from "../../src/constants/theme";
import { t, useTranslation } from "../../src/i18n";

/**
 * Media Detail Screen.
 *
 * Lifecycle:
 * 1. On mount, uses `useMediaDetailPolling` hook to fetch media status.
 * 2. If the processing job is non-terminal, shows a "Generating text..." placeholder
 *    with a spinner. Polls every 3s until status becomes terminal.
 * 3. On "completed": hands the item to `CompletedDetailView`, the shared page the
 *    Digest pager renders too — with its chrome on, which is this route's own
 *    safe area and title bar.
 * 4. On "failed": shows a failure banner with the error message, plus — when the
 *    failure is one of the eight that mean the source itself is not handled yet —
 *    a card offering to request support for it (`SourceSupportRequestCard`).
 * 5. On 5-minute timeout: stops polling and shows a "taking longer" message.
 *
 * Everything below belongs to the route: the id it reads, the fetch it drives,
 * and the states the item goes through on its way to being readable. The
 * readable item itself lives in `src/components/CompletedDetailView.tsx`.
 *
 * Features:
 * - Contextual processing message based on source_platform
 * - Retry/refresh for failed states
 * - All interactive elements meet 48px minimum touch target
 */
export default function MediaDetailScreen() {
  // Copy resolved on render: redraw when the interface language changes.
  useTranslation();
  const { id } = useLocalSearchParams<{ id: string }>();
  const router = useRouter();

  const {
    state: pollingState,
    mediaData,
    fetchError,
    processingError,
    processingMessage,
    refresh,
  } = useMediaDetailPolling(id);

  // --- Loading state (initial fetch) ---
  if (pollingState === "loading") {
    return (
      <SafeAreaView style={styles.container} edges={["top"]}>
        <MediaDetailHeader onBack={() => router.back()} />
        <View style={styles.centered}>
          <ActivityIndicator size="large" color={Colors.primary} />
        </View>
      </SafeAreaView>
    );
  }

  // --- Fetch error state (network/auth error) ---
  if (pollingState === "error") {
    return (
      <SafeAreaView style={styles.container} edges={["top"]}>
        <MediaDetailHeader onBack={() => router.back()} />
        <View style={styles.centered}>
          <Ionicons
            name="alert-circle-outline"
            size={48}
            color={Colors.error}
          />
          <Text style={styles.errorText}>
            {fetchError || t("media.loadFailed")}
          </Text>
          <Pressable
            style={styles.retryButton}
            onPress={refresh}
            accessibilityLabel={t("media.retryA11y")}
            accessibilityRole="button"
          >
            <Text style={styles.retryButtonText}>{t("common.retry")}</Text>
          </Pressable>
        </View>
      </SafeAreaView>
    );
  }

  // --- Processing state (non-terminal, showing placeholder) ---
  if (pollingState === "processing") {
    return (
      <SafeAreaView style={styles.container} edges={["top"]}>
        <MediaDetailHeader onBack={() => router.back()} />
        <View style={styles.centered}>
          <View style={styles.processingIconContainer}>
            <ActivityIndicator size="large" color={Colors.primary} />
          </View>
          <Text style={styles.processingTitle}>{processingMessage}</Text>
          <Text style={styles.processingSubtitle}>
            {t("media.processingHint")}
          </Text>
        </View>
      </SafeAreaView>
    );
  }

  // --- Timeout state (5 minutes elapsed without completion) ---
  if (pollingState === "timeout") {
    return (
      <SafeAreaView style={styles.container} edges={["top"]}>
        <MediaDetailHeader onBack={() => router.back()} />
        <View style={styles.centered}>
          <Ionicons
            name="time-outline"
            size={48}
            color={Colors.textMuted}
          />
          <Text style={styles.timeoutTitle}>{t("media.timeoutTitle")}</Text>
          <Text style={styles.timeoutSubtitle}>{t("media.timeoutHint")}</Text>
          <Pressable
            style={styles.refreshButton}
            onPress={refresh}
            accessibilityLabel={t("media.refreshA11y")}
            accessibilityRole="button"
          >
            <Ionicons name="refresh" size={18} color={Colors.onPrimary} />
            <Text style={styles.refreshButtonText}>{t("media.refresh")}</Text>
          </Pressable>
        </View>
      </SafeAreaView>
    );
  }

  // --- Failed state (processing failed) ---
  if (pollingState === "failed") {
    return (
      <SafeAreaView style={styles.container} edges={["top"]}>
        <MediaDetailHeader onBack={() => router.back()} />
        <View style={styles.centered}>
          <Ionicons
            name="alert-circle"
            size={48}
            color={Colors.error}
          />
          <Text style={styles.failedTitle}>{t("media.failedTitle")}</Text>
          <Text style={styles.failedMessage}>
            {processingError || t("media.failedFallback")}
          </Text>
          <Pressable
            style={styles.refreshButton}
            onPress={refresh}
            accessibilityLabel={t("media.refreshA11y")}
            accessibilityRole="button"
          >
            <Ionicons name="refresh" size={18} color={Colors.onPrimary} />
            <Text style={styles.refreshButtonText}>{t("media.refresh")}</Text>
          </Pressable>
          {/* Only for the eight codes that actually mean "we don't handle this
              source yet", and identical on iOS and Android. It draws nothing at
              all otherwise, which is why it is unconditional here. */}
          <SourceSupportRequestCard
            mediaItemId={id}
            errorCode={mediaData?.processing_job.error_code}
          />
        </View>
      </SafeAreaView>
    );
  }

  // --- Completed state (full detail view) ---
  if (!mediaData) {
    // Safety check: should not happen after the hook resolves
    return (
      <SafeAreaView style={styles.container} edges={["top"]}>
        <MediaDetailHeader onBack={() => router.back()} />
        <View style={styles.centered}>
          <Text style={styles.errorText}>{t("media.loadFailed")}</Text>
        </View>
      </SafeAreaView>
    );
  }

  return (
    <CompletedDetailView
      mediaData={mediaData}
      onBack={() => router.back()}
    />
  );
}

// --- Styles ---

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: Colors.background,
  },
  centered: {
    flex: 1,
    justifyContent: "center",
    alignItems: "center",
    paddingHorizontal: Spacing.xl,
    gap: Spacing.md,
  },

  // Processing placeholder
  processingIconContainer: {
    marginBottom: Spacing.md,
  },
  processingTitle: {
    fontSize: Typography.headline.fontSize,
    fontWeight: Typography.headline.fontWeight,
    color: Colors.textMain,
    textAlign: "center",
  },
  processingSubtitle: {
    fontSize: Typography.body.fontSize,
    color: Colors.textMuted,
    textAlign: "center",
    marginTop: Spacing.xs,
  },

  // Timeout state
  timeoutTitle: {
    fontSize: Typography.headline.fontSize,
    fontWeight: Typography.headline.fontWeight,
    color: Colors.textMain,
    textAlign: "center",
  },
  timeoutSubtitle: {
    fontSize: Typography.body.fontSize,
    color: Colors.textMuted,
    textAlign: "center",
    marginTop: Spacing.xs,
  },

  // Failed state
  failedTitle: {
    fontSize: Typography.headline.fontSize,
    fontWeight: Typography.headline.fontWeight,
    color: Colors.error,
    textAlign: "center",
  },
  failedMessage: {
    fontSize: Typography.body.fontSize,
    color: Colors.textMain,
    textAlign: "center",
    lineHeight: Typography.body.lineHeight,
    marginTop: Spacing.xs,
  },

  // Refresh/Retry button
  refreshButton: {
    flexDirection: "row",
    alignItems: "center",
    gap: Spacing.sm,
    backgroundColor: Colors.primary,
    paddingHorizontal: Spacing.lg,
    paddingVertical: Spacing.sm + 4,
    borderRadius: BorderRadius.lg,
    minHeight: TouchTarget.minimum,
    marginTop: Spacing.md,
  },
  refreshButtonText: {
    fontSize: Typography.label.fontSize,
    fontWeight: Typography.label.fontWeight,
    color: Colors.onPrimary,
  },

  // Error state
  errorText: {
    fontSize: Typography.body.fontSize,
    color: Colors.textMain,
    textAlign: "center",
  },
  retryButton: {
    paddingHorizontal: Spacing.lg,
    paddingVertical: Spacing.sm,
    backgroundColor: Colors.primary,
    borderRadius: BorderRadius.md,
    marginTop: Spacing.sm,
    minHeight: TouchTarget.minimum,
    justifyContent: "center",
    alignItems: "center",
  },
  retryButtonText: {
    fontSize: Typography.label.fontSize,
    fontWeight: "600",
    color: Colors.textMain,
  },
});
