import { useCallback, useEffect } from "react";
import {
  View,
  Text,
  StyleSheet,
  Pressable,
  ActivityIndicator,
} from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";
import { useRouter } from "expo-router";
import { Ionicons } from "@expo/vector-icons";
import {
  useShareIntake,
  type ShareSelectedFolder,
  type ShareSelectedTag,
  type ShareIntakeState,
} from "../src/contexts/ShareIntentContext";
import {
  getQuotaErrorTitle,
  quotaErrorOffersUpgrade,
} from "../src/lib/quotaError";
import {
  Colors,
  Typography,
  Spacing,
  BorderRadius,
  Shadows,
  TouchTarget,
} from "../src/constants/theme";

/**
 * Share confirmation screen.
 * Displayed when content is shared into the app via Android share intent
 * or iOS share extension.
 *
 * Supports three content types:
 * - URL: existing flow via ingest-url
 * - Text: WhatsApp text messages via ingest-shared-content
 * - Audio: WhatsApp voice messages via ingest-shared-content
 *
 * Layout follows the design reference (confirmation_de_partage_version_finale):
 * - Top bar: close button (left), title (center), save button (right)
 * - Content preview card
 * - Feedback states: submitting, success, error
 */
export default function ShareConfirmationScreen() {
  const router = useRouter();
  const {
    intake,
    selectedFolder,
    selectedTags,
    submitUrl,
    submitSharedContent,
    dismiss,
    retry,
  } = useShareIntake();

  const handleClose = useCallback(() => {
    dismiss();
    if (router.canGoBack()) {
      router.back();
    } else {
      router.replace("/(tabs)/inbox");
    }
  }, [dismiss, router]);

  // Auto-dismiss on success after a brief delay
  useEffect(() => {
    if (intake.status === "success") {
      const timer = setTimeout(() => {
        handleClose();
      }, 2000);
      return () => clearTimeout(timer);
    }
  }, [handleClose, intake.status]);

  const handleSave = () => {
    if (intake.contentType === "url") {
      submitUrl();
    } else {
      submitSharedContent();
    }
  };

  const handleRetry = () => {
    retry();
  };

  const handleOpenCollection = () => {
    router.push("/media/collection?mode=share");
  };

  const handleOpenTags = () => {
    router.push("/media/tags?mode=share");
  };

  // Offered when the backend refused the submission for a tier allowance. The
  // share intake is left untouched so the user can Save again once subscribed.
  const handleOpenPaywall = () => {
    router.push("/paywall");
  };

  const canSave = intake.status === "ready" || intake.status === "error";

  const topBarTitle =
    intake.contentType === "audio"
      ? "Save Audio"
      : intake.contentType === "text"
        ? "Save Text"
        : "Save Link";

  return (
    <SafeAreaView style={styles.container} edges={["top", "bottom"]}>
      {/* Top Bar - matching design: close (left), title (center), save (right) */}
      <View style={styles.topBar}>
        <Pressable
          style={styles.closeButton}
          onPress={handleClose}
          accessibilityLabel="Close"
          accessibilityRole="button"
        >
          <Ionicons name="close" size={24} color={Colors.textMain} />
        </Pressable>

        <Text style={styles.topBarTitle}>{topBarTitle}</Text>

        <Pressable
          style={[styles.saveButton, !canSave && styles.saveButtonDisabled]}
          onPress={handleSave}
          disabled={!canSave}
          accessibilityLabel="Save"
          accessibilityRole="button"
        >
          {intake.status === "submitting" ? (
            <ActivityIndicator size="small" color={Colors.textMain} />
          ) : (
            <Text style={styles.saveButtonText}>Save</Text>
          )}
        </Pressable>
      </View>

      {/* Content */}
      <View style={styles.content}>
        <ShareContent
          intake={intake}
          selectedFolder={selectedFolder}
          selectedTags={selectedTags}
          onOpenCollection={handleOpenCollection}
          onOpenTags={handleOpenTags}
          onRetry={handleRetry}
          onOpenPaywall={handleOpenPaywall}
        />
      </View>
    </SafeAreaView>
  );
}

/**
 * Renders the appropriate content based on the current share intake state.
 */
function ShareContent({
  intake,
  selectedFolder,
  selectedTags,
  onOpenCollection,
  onOpenTags,
  onRetry,
  onOpenPaywall,
}: {
  intake: ShareIntakeState;
  selectedFolder: ShareSelectedFolder | null;
  selectedTags: ShareSelectedTag[];
  onOpenCollection: () => void;
  onOpenTags: () => void;
  onRetry: () => void;
  onOpenPaywall: () => void;
}) {
  switch (intake.status) {
    case "idle":
    case "validating":
      return (
        <View style={styles.centerContent}>
          <ActivityIndicator size="large" color={Colors.primary} />
          <Text style={styles.statusText}>Processing shared content...</Text>
        </View>
      );

    case "invalid":
      return (
        <View style={styles.centerContent}>
          <View style={styles.errorIcon}>
            <Ionicons name="alert-circle" size={48} color={Colors.error} />
          </View>
          <Text style={styles.errorTitle}>Cannot save this content</Text>
          <Text style={styles.errorMessage}>{intake.message}</Text>
        </View>
      );

    case "ready":
      if (intake.contentType === "audio" && intake.audioFile) {
        return (
          <>
            <AudioPreviewCard
              fileName={intake.audioFile.fileName}
              mimeType={intake.audioFile.mimeType}
              fileSize={intake.audioFile.fileSize}
            />
            <OrganizationControls
              selectedFolder={selectedFolder}
              selectedTags={selectedTags}
              onOpenCollection={onOpenCollection}
              onOpenTags={onOpenTags}
            />
          </>
        );
      }
      if (intake.contentType === "text" && intake.rawText) {
        return (
          <>
            <TextPreviewCard text={intake.rawText} />
            <OrganizationControls
              selectedFolder={selectedFolder}
              selectedTags={selectedTags}
              onOpenCollection={onOpenCollection}
              onOpenTags={onOpenTags}
            />
          </>
        );
      }
      return (
        <>
          <UrlPreviewCard url={intake.url!} />
          <OrganizationControls
            selectedFolder={selectedFolder}
            selectedTags={selectedTags}
            onOpenCollection={onOpenCollection}
            onOpenTags={onOpenTags}
          />
        </>
      );

    case "submitting":
      if (intake.contentType === "audio" && intake.audioFile) {
        return (
          <>
            <AudioPreviewCard
              fileName={intake.audioFile.fileName}
              mimeType={intake.audioFile.mimeType}
              fileSize={intake.audioFile.fileSize}
              isSubmitting
            />
            <OrganizationControls
              selectedFolder={selectedFolder}
              selectedTags={selectedTags}
              onOpenCollection={onOpenCollection}
              onOpenTags={onOpenTags}
              disabled
            />
          </>
        );
      }
      if (intake.contentType === "text" && intake.rawText) {
        return (
          <>
            <TextPreviewCard text={intake.rawText} isSubmitting />
            <OrganizationControls
              selectedFolder={selectedFolder}
              selectedTags={selectedTags}
              onOpenCollection={onOpenCollection}
              onOpenTags={onOpenTags}
              disabled
            />
          </>
        );
      }
      return (
        <>
          <UrlPreviewCard url={intake.url!} isSubmitting />
          <OrganizationControls
            selectedFolder={selectedFolder}
            selectedTags={selectedTags}
            onOpenCollection={onOpenCollection}
            onOpenTags={onOpenTags}
            disabled
          />
        </>
      );

    case "success":
      return (
        <View style={styles.centerContent}>
          <View style={styles.successIcon}>
            <Ionicons name="checkmark-circle" size={48} color={Colors.primary} />
          </View>
          <Text style={styles.successTitle}>Saved!</Text>
          <Text style={styles.successMessage}>
            {intake.response?.deduplicated
              ? "This content was already in your inbox."
              : intake.contentType === "audio"
                ? "Audio saved. Transcription will begin shortly."
                : intake.contentType === "text"
                  ? "Text saved to your inbox."
                  : "Link added to your inbox. Processing will begin shortly."}
          </Text>
        </View>
      );

    case "error": {
      // A quota refusal is not a failure the user can retry into success: it is
      // a limit, so it reads as one. The message comes straight from the quota
      // enforcer and already names the limit that was reached.
      const quotaErrorCode = intake.quotaErrorCode ?? null;
      const offersUpgrade =
        quotaErrorCode !== null && quotaErrorOffersUpgrade(quotaErrorCode);

      return (
        <View style={styles.centerContent} testID="share-error-state">
          <View style={styles.errorIcon}>
            <Ionicons
              name={quotaErrorCode ? "lock-closed" : "alert-circle"}
              size={48}
              color={quotaErrorCode ? Colors.primary : Colors.error}
            />
          </View>
          <Text style={styles.errorTitle}>
            {quotaErrorCode ? getQuotaErrorTitle(quotaErrorCode) : "Save failed"}
          </Text>
          <Text testID="share-error-message" style={styles.errorMessage}>
            {intake.message}
          </Text>
          {offersUpgrade && (
            <Pressable
              testID="share-quota-upgrade-button"
              style={({ pressed }) => [
                styles.upgradeButton,
                pressed && styles.upgradeButtonPressed,
              ]}
              onPress={onOpenPaywall}
              accessibilityLabel="See plans"
              accessibilityRole="button"
            >
              <Ionicons name="sparkles" size={18} color={Colors.onPrimary} />
              <Text style={styles.upgradeButtonText}>See plans</Text>
            </Pressable>
          )}
          <Pressable
            style={styles.retryButton}
            onPress={onRetry}
            accessibilityLabel="Try again"
            accessibilityRole="button"
          >
            <Ionicons name="refresh" size={18} color={Colors.textMain} />
            <Text style={styles.retryButtonText}>Try again</Text>
          </Pressable>
        </View>
      );
    }

    default:
      return null;
  }
}

/**
 * Preview card showing the URL being saved.
 * Matches the design mockup's media card layout.
 */
function UrlPreviewCard({
  url,
  isSubmitting = false,
}: {
  url: string;
  isSubmitting?: boolean;
}) {
  let displayDomain: string;
  try {
    const parsed = new URL(url);
    displayDomain = parsed.hostname.replace(/^www\./, "");
  } catch {
    displayDomain = url;
  }

  return (
    <View style={[styles.previewCard, isSubmitting && styles.previewCardMuted]}>
      <View style={styles.previewCardContent}>
        <View style={styles.previewTextSection}>
          <Text style={styles.previewUrl} numberOfLines={3}>
            {url}
          </Text>
          <Text style={styles.previewDomain}>{displayDomain}</Text>
        </View>
        <View style={styles.previewIconContainer}>
          <Ionicons name="link" size={24} color={Colors.textMuted} />
        </View>
      </View>
      {isSubmitting && (
        <View style={styles.previewSubmitting}>
          <ActivityIndicator size="small" color={Colors.primary} />
          <Text style={styles.previewSubmittingText}>Saving...</Text>
        </View>
      )}
    </View>
  );
}

/**
 * Preview card for shared plain text (WhatsApp text message).
 */
function TextPreviewCard({
  text,
  isSubmitting = false,
}: {
  text: string;
  isSubmitting?: boolean;
}) {
  return (
    <View style={[styles.previewCard, isSubmitting && styles.previewCardMuted]}>
      <View style={styles.previewCardContent}>
        <View style={styles.previewTextSection}>
          <Text style={styles.previewUrl} numberOfLines={5}>
            {text}
          </Text>
          <Text style={styles.previewDomain}>WhatsApp text message</Text>
        </View>
        <View style={styles.previewIconContainer}>
          <Ionicons name="chatbubble-outline" size={24} color={Colors.textMuted} />
        </View>
      </View>
      {isSubmitting && (
        <View style={styles.previewSubmitting}>
          <ActivityIndicator size="small" color={Colors.primary} />
          <Text style={styles.previewSubmittingText}>Saving...</Text>
        </View>
      )}
    </View>
  );
}

/**
 * Preview card for shared audio file (WhatsApp voice message).
 */
function AudioPreviewCard({
  fileName,
  mimeType,
  fileSize,
  isSubmitting = false,
}: {
  fileName: string | null;
  mimeType: string;
  fileSize: number | null;
  isSubmitting?: boolean;
}) {
  const displayName = fileName ?? "Voice message";
  const displaySize = fileSize
    ? fileSize > 1024 * 1024
      ? `${(fileSize / (1024 * 1024)).toFixed(1)} MB`
      : `${Math.round(fileSize / 1024)} KB`
    : mimeType;

  return (
    <View style={[styles.previewCard, isSubmitting && styles.previewCardMuted]}>
      <View style={styles.previewCardContent}>
        <View style={styles.previewTextSection}>
          <Text style={styles.previewUrl} numberOfLines={2}>
            {displayName}
          </Text>
          <Text style={styles.previewDomain}>{displaySize}</Text>
        </View>
        <View style={styles.previewIconContainer}>
          <Ionicons name="mic-outline" size={24} color={Colors.textMuted} />
        </View>
      </View>
      {isSubmitting && (
        <View style={styles.previewSubmitting}>
          <ActivityIndicator size="small" color={Colors.primary} />
          <Text style={styles.previewSubmittingText}>Uploading audio...</Text>
        </View>
      )}
    </View>
  );
}

function OrganizationControls({
  selectedFolder,
  selectedTags,
  onOpenCollection,
  onOpenTags,
  disabled = false,
}: {
  selectedFolder: ShareSelectedFolder | null;
  selectedTags: ShareSelectedTag[];
  onOpenCollection: () => void;
  onOpenTags: () => void;
  disabled?: boolean;
}) {
  const tagsLabel =
    selectedTags.length > 0
      ? selectedTags.map((tag) => tag.name).join(", ")
      : "Tags";

  return (
    <View style={styles.organizationSection}>
      <Pressable
        style={({ pressed }) => [
          styles.organizationRow,
          pressed && !disabled && styles.organizationRowPressed,
          disabled && styles.organizationRowDisabled,
        ]}
        onPress={onOpenCollection}
        disabled={disabled}
        accessibilityLabel="Choose collection"
        accessibilityRole="button"
      >
        <View style={styles.organizationRowLeft}>
          <Ionicons
            name="folder-open-outline"
            size={20}
            color={Colors.textMuted}
          />
          <Text style={styles.organizationRowLabel} numberOfLines={1}>
            {selectedFolder?.path ?? "Non trié"}
          </Text>
        </View>
        <Ionicons
          name="chevron-forward"
          size={20}
          color={Colors.textMuted}
        />
      </Pressable>

      <Pressable
        style={({ pressed }) => [
          styles.organizationRow,
          pressed && !disabled && styles.organizationRowPressed,
          disabled && styles.organizationRowDisabled,
        ]}
        onPress={onOpenTags}
        disabled={disabled}
        accessibilityLabel="Choose tags"
        accessibilityRole="button"
      >
        <View style={styles.organizationRowLeft}>
          <Ionicons
            name="pricetag-outline"
            size={20}
            color={Colors.textMuted}
          />
          <Text style={styles.organizationRowLabel} numberOfLines={1}>
            {tagsLabel}
          </Text>
        </View>
        <Ionicons
          name="chevron-forward"
          size={20}
          color={Colors.textMuted}
        />
      </Pressable>
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: Colors.background,
  },
  topBar: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    paddingHorizontal: Spacing.md,
    paddingVertical: Spacing.md,
  },
  closeButton: {
    width: 44,
    height: 44,
    borderRadius: BorderRadius.full,
    backgroundColor: Colors.surfaceContainerHigh,
    alignItems: "center",
    justifyContent: "center",
  },
  topBarTitle: {
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
    alignItems: "center",
    justifyContent: "center",
    minHeight: TouchTarget.minimum,
  },
  saveButtonDisabled: {
    opacity: 0.5,
  },
  saveButtonText: {
    fontSize: Typography.label.fontSize,
    fontWeight: "700",
    color: Colors.textMain,
  },
  content: {
    flex: 1,
    paddingHorizontal: Spacing.lg,
    paddingTop: Spacing.lg,
  },
  centerContent: {
    flex: 1,
    justifyContent: "center",
    alignItems: "center",
    paddingHorizontal: Spacing.xl,
  },
  statusText: {
    fontSize: Typography.body.fontSize,
    color: Colors.textMuted,
    marginTop: Spacing.md,
  },
  // Preview card
  previewCard: {
    backgroundColor: Colors.surfaceContainerLow,
    borderRadius: BorderRadius.xl,
    padding: Spacing.lg,
    borderWidth: StyleSheet.hairlineWidth,
    borderColor: Colors.outlineVariant,
    ...Shadows.soft,
  },
  previewCardMuted: {
    opacity: 0.7,
  },
  previewCardContent: {
    flexDirection: "row",
    gap: Spacing.md,
  },
  previewTextSection: {
    flex: 1,
    gap: Spacing.sm,
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
  previewIconContainer: {
    width: 48,
    height: 48,
    borderRadius: BorderRadius.lg,
    backgroundColor: Colors.surfaceContainerHigh,
    alignItems: "center",
    justifyContent: "center",
  },
  previewSubmitting: {
    flexDirection: "row",
    alignItems: "center",
    gap: Spacing.sm,
    marginTop: Spacing.md,
    paddingTop: Spacing.md,
    borderTopWidth: StyleSheet.hairlineWidth,
    borderTopColor: Colors.outlineVariant,
  },
  previewSubmittingText: {
    fontSize: Typography.small.fontSize,
    color: Colors.textMuted,
  },
  organizationSection: {
    marginTop: Spacing.lg,
    gap: Spacing.sm,
  },
  organizationRow: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    minHeight: TouchTarget.comfortable,
    paddingHorizontal: Spacing.md,
    paddingVertical: Spacing.md,
    backgroundColor: Colors.surfaceContainerLow,
    borderRadius: BorderRadius.xl,
  },
  organizationRowPressed: {
    backgroundColor: Colors.surfaceContainerHigh,
  },
  organizationRowDisabled: {
    opacity: 0.6,
  },
  organizationRowLeft: {
    flex: 1,
    flexDirection: "row",
    alignItems: "center",
    gap: Spacing.sm,
    marginRight: Spacing.sm,
  },
  organizationRowLabel: {
    flex: 1,
    fontSize: Typography.body.fontSize,
    fontWeight: "500",
    color: Colors.textMain,
  },
  // Success state
  successIcon: {
    marginBottom: Spacing.md,
  },
  successTitle: {
    fontSize: Typography.headline.fontSize,
    fontWeight: Typography.headline.fontWeight,
    color: Colors.textMain,
    marginBottom: Spacing.sm,
  },
  successMessage: {
    fontSize: Typography.body.fontSize,
    color: Colors.textMuted,
    textAlign: "center",
    lineHeight: Typography.body.lineHeight,
  },
  // Error state
  errorIcon: {
    marginBottom: Spacing.md,
  },
  errorTitle: {
    fontSize: Typography.headline.fontSize,
    fontWeight: Typography.headline.fontWeight,
    color: Colors.textMain,
    marginBottom: Spacing.sm,
  },
  errorMessage: {
    fontSize: Typography.body.fontSize,
    color: Colors.textMuted,
    textAlign: "center",
    lineHeight: Typography.body.lineHeight,
    marginBottom: Spacing.lg,
  },
  upgradeButton: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "center",
    gap: Spacing.sm,
    paddingHorizontal: Spacing.lg,
    paddingVertical: Spacing.md,
    borderRadius: BorderRadius.full,
    backgroundColor: Colors.primary,
    minHeight: TouchTarget.minimum,
    marginBottom: Spacing.sm,
    ...Shadows.soft,
  },
  upgradeButtonPressed: {
    opacity: 0.85,
  },
  upgradeButtonText: {
    fontSize: Typography.label.fontSize,
    fontWeight: "700",
    color: Colors.onPrimary,
  },
  retryButton: {
    flexDirection: "row",
    alignItems: "center",
    gap: Spacing.sm,
    paddingHorizontal: Spacing.lg,
    paddingVertical: Spacing.md,
    borderRadius: BorderRadius.full,
    backgroundColor: Colors.surfaceContainer,
    minHeight: TouchTarget.minimum,
  },
  retryButtonText: {
    fontSize: Typography.label.fontSize,
    fontWeight: Typography.label.fontWeight,
    color: Colors.textMain,
  },
});
