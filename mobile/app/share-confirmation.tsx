import { useCallback, useEffect, useRef, useState } from "react";
import {
  View,
  Text,
  StyleSheet,
  Pressable,
  ActivityIndicator,
  AppState,
} from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";
import { useFocusEffect, useRouter } from "expo-router";
import { Ionicons } from "@expo/vector-icons";
import { useAuth } from "../src/contexts/AuthContext";
import {
  useShareIntake,
  type ShareContentType,
  type ShareSelectedFolder,
  type ShareSelectedTag,
  type ShareIntakeState,
} from "../src/contexts/ShareIntentContext";
import {
  getQuotaErrorTitle,
  quotaErrorOffersUpgrade,
} from "../src/lib/quotaError";
import { formatUploadSize, type LocalUploadFile } from "../src/types/upload";
import {
  Colors,
  Typography,
  Spacing,
  BorderRadius,
  Shadows,
  TouchTarget,
} from "../src/constants/theme";
import { t, type TranslationKey, useTranslation } from "../src/i18n";
import { ScreenHeader, HeaderIconButton } from "../src/components/ScreenHeader";

const TOP_BAR_TITLE_KEYS: Record<ShareContentType, TranslationKey> = {
  url: "share.title.url",
  text: "share.title.text",
  audio: "share.title.audio",
  file: "share.title.file",
  photo: "share.title.photo",
};

/**
 * Confirmation screen for every incoming save: the collection and tags are
 * chosen here, and Save is what actually sends the content.
 *
 * Reached from the system share sheet (Android share intent / iOS share
 * extension) and, since task-264, from the inbox "add" gesture.
 *
 * Supports five content types:
 * - URL: via ingest-url
 * - Text: WhatsApp text messages via ingest-shared-content
 * - Audio: WhatsApp voice messages via ingest-shared-content
 * - File: document, image or audio imported from the device via the upload
 *   endpoints
 * - Photo: a shot just taken with the camera, same upload path
 *
 * Layout follows the design reference (confirmation_de_partage_version_finale):
 * - Top bar: close button (left), title (center), save button (right)
 * - Content preview card
 * - Feedback states: submitting, success, error
 */
export default function ShareConfirmationScreen() {
  // Copy resolved on render: redraw when the interface language changes.
  useTranslation();
  const router = useRouter();
  const {
    isAuthenticated,
    isLoading,
    revalidateSession,
  } = useAuth();
  const {
    intake,
    selectedFolder,
    selectedTags,
    submitUrl,
    submitSharedContent,
    submitUpload,
    parkCurrentIntakeForAuth,
    dismiss,
    retry,
  } = useShareIntake();
  const [isSessionReady, setIsSessionReady] = useState(false);
  const guardInFlightRef = useRef<Promise<void> | null>(null);
  const redirectingRef = useRef(false);

  const redirectToLogin = useCallback(() => {
    setIsSessionReady(false);
    parkCurrentIntakeForAuth();
    if (redirectingRef.current) return;
    redirectingRef.current = true;
    router.replace("/(auth)/login");
  }, [parkCurrentIntakeForAuth, router]);

  const guardSession = useCallback((): Promise<void> => {
    if (isLoading) return Promise.resolve();
    if (guardInFlightRef.current) return guardInFlightRef.current;
    if (!isAuthenticated) {
      redirectToLogin();
      return Promise.resolve();
    }

    const operation = (async () => {
      const valid = await revalidateSession();
      if (valid) {
        redirectingRef.current = false;
        setIsSessionReady(true);
      } else {
        redirectToLogin();
      }
    })();

    guardInFlightRef.current = operation;
    void operation.finally(() => {
      if (guardInFlightRef.current === operation) {
        guardInFlightRef.current = null;
      }
    });
    return operation;
  }, [isAuthenticated, isLoading, redirectToLogin, revalidateSession]);

  useFocusEffect(
    useCallback(() => {
      void guardSession();
    }, [guardSession]),
  );

  useEffect(() => {
    const subscription = AppState.addEventListener("change", (nextState) => {
      if (nextState === "active") {
        setIsSessionReady(false);
        void guardSession();
      }
    });
    return () => subscription.remove();
  }, [guardSession]);

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
    } else if (
      intake.contentType === "file" ||
      intake.contentType === "photo"
    ) {
      submitUpload();
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
  // The reason travels with the push so the paywall can open on the refusal the
  // user is standing in rather than on a generic pitch.
  const handleOpenPaywall = () => {
    router.push("/paywall?reason=out_of_minutes");
  };

  const canSave = intake.status === "ready" || intake.status === "error";

  const topBarTitle = t(TOP_BAR_TITLE_KEYS[intake.contentType]);

  if (!isSessionReady || isLoading || !isAuthenticated) {
    return (
      <SafeAreaView style={styles.container} edges={["top", "bottom"]}>
        <View style={styles.centerContent}>
          <ActivityIndicator size="large" color={Colors.primary} />
        </View>
      </SafeAreaView>
    );
  }

  return (
    <SafeAreaView style={styles.container} edges={["top", "bottom"]}>
      {/* Top Bar - matching design: close (left), title (center), save (right) */}
      <ScreenHeader
        title={topBarTitle}
        leading={
          <HeaderIconButton
            icon="close"
            onPress={handleClose}
            accessibilityLabel={t("common.close")}
          />
        }
        trailing={
          <Pressable
            style={[styles.saveButton, !canSave && styles.saveButtonDisabled]}
            onPress={handleSave}
            disabled={!canSave}
            accessibilityLabel={t("common.save")}
            accessibilityRole="button"
          >
            {intake.status === "submitting" ? (
              <ActivityIndicator size="small" color={Colors.textMain} />
            ) : (
              <Text style={styles.saveButtonText}>{t("common.save")}</Text>
            )}
          </Pressable>
        }
      />

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
          <Text style={styles.statusText}>{t("share.processing")}</Text>
        </View>
      );

    case "invalid":
      return (
        <View style={styles.centerContent}>
          <View style={styles.errorIcon}>
            <Ionicons name="alert-circle" size={48} color={Colors.error} />
          </View>
          <Text style={styles.errorTitle}>{t("share.invalid")}</Text>
          <Text style={styles.errorMessage}>{intake.message}</Text>
        </View>
      );

    case "ready":
      if (
        (intake.contentType === "file" || intake.contentType === "photo") &&
        intake.uploadFile
      ) {
        return (
          <>
            <FilePreviewCard
              file={intake.uploadFile}
              isPhoto={intake.contentType === "photo"}
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
      if (
        (intake.contentType === "file" || intake.contentType === "photo") &&
        intake.uploadFile
      ) {
        return (
          <>
            <FilePreviewCard
              file={intake.uploadFile}
              isPhoto={intake.contentType === "photo"}
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
          <Text style={styles.successTitle}>{t("share.saved")}</Text>
          <Text style={styles.successMessage}>{getSuccessMessage(intake)}</Text>
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
            {quotaErrorCode
              ? getQuotaErrorTitle(quotaErrorCode)
              : t("share.saveFailed")}
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
              accessibilityLabel={t("quota.seePlans")}
              accessibilityRole="button"
            >
              <Ionicons name="sparkles" size={18} color={Colors.onPrimary} />
              <Text style={styles.upgradeButtonText}>{t("quota.seePlans")}</Text>
            </Pressable>
          )}
          {/* No retry on a limit: the same submission would be refused for the
              same reason. The top bar keeps Save enabled and the intake intact,
              so it is one tap away for a user who comes back from the paywall. */}
          {quotaErrorCode === null && (
            <Pressable
              style={styles.retryButton}
              onPress={onRetry}
              accessibilityLabel={t("paywall.tryAgain")}
              accessibilityRole="button"
            >
              <Ionicons name="refresh" size={18} color={Colors.textMain} />
              <Text style={styles.retryButtonText}>{t("paywall.tryAgain")}</Text>
            </Pressable>
          )}
        </View>
      );
    }

    default:
      return null;
  }
}

/**
 * What the user reads once the save went through. Every content type says what
 * happens next, because the processing that follows is asynchronous.
 */
function getSuccessMessage(intake: ShareIntakeState): string {
  if (intake.response?.deduplicated) {
    return t("share.success.duplicate");
  }
  switch (intake.contentType) {
    case "audio":
      return t("share.success.audio");
    case "text":
      return t("share.success.text");
    case "photo":
      return t("share.success.photo");
    case "file":
      return intake.uploadFile?.kind === "audio"
        ? t("share.success.audioFile")
        : t("share.success.file");
    case "url":
      return t("share.success.url");
  }
}

/**
 * Preview card for a file picked from the device or a photo just taken.
 * Shows what is about to be sent — name, size and where it is headed — so the
 * user confirms the right thing before Save.
 */
function FilePreviewCard({
  file,
  isPhoto,
  isSubmitting = false,
}: {
  file: LocalUploadFile;
  isPhoto: boolean;
  isSubmitting?: boolean;
}) {
  const isImage = file.mimeType.startsWith("image/");
  const iconName = isPhoto
    ? "camera-outline"
    : file.kind === "audio"
      ? "musical-notes-outline"
      : isImage
        ? "image-outline"
        : "document-text-outline";

  const subtitleParts: string[] = [];
  if (isPhoto) {
    subtitleParts.push("Camera capture");
  }
  const extension = file.name.split(".").pop();
  if (!isPhoto && extension) {
    subtitleParts.push(`.${extension.toLowerCase()}`);
  }
  if (file.size !== null) {
    subtitleParts.push(formatUploadSize(file.size));
  }

  return (
    <View style={[styles.previewCard, isSubmitting && styles.previewCardMuted]}>
      <View style={styles.previewCardContent}>
        <View style={styles.previewTextSection}>
          <Text style={styles.previewUrl} numberOfLines={2}>
            {file.name}
          </Text>
          <Text style={styles.previewDomain}>
            {subtitleParts.join(" · ") || file.mimeType}
          </Text>
        </View>
        <View style={styles.previewIconContainer}>
          <Ionicons name={iconName} size={24} color={Colors.textMuted} />
        </View>
      </View>
      {isSubmitting && (
        <View style={styles.previewSubmitting}>
          <ActivityIndicator size="small" color={Colors.primary} />
          <Text style={styles.previewSubmittingText}>
            {file.kind === "audio"
              ? t("share.uploadingAudio")
              : t("share.uploadingFile")}
          </Text>
        </View>
      )}
    </View>
  );
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
          <Text style={styles.previewSubmittingText}>{t("share.saving")}</Text>
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
          <Text style={styles.previewDomain}>{t("share.whatsappText")}</Text>
        </View>
        <View style={styles.previewIconContainer}>
          <Ionicons name="chatbubble-outline" size={24} color={Colors.textMuted} />
        </View>
      </View>
      {isSubmitting && (
        <View style={styles.previewSubmitting}>
          <ActivityIndicator size="small" color={Colors.primary} />
          <Text style={styles.previewSubmittingText}>{t("share.saving")}</Text>
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
          <Text style={styles.previewSubmittingText}>
            {t("share.uploadingAudio")}
          </Text>
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
      : t("share.tags");

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
        accessibilityLabel={t("share.chooseCollection")}
        accessibilityRole="button"
      >
        <View style={styles.organizationRowLeft}>
          <Ionicons
            name="folder-open-outline"
            size={20}
            color={Colors.textMuted}
          />
          <Text style={styles.organizationRowLabel} numberOfLines={1}>
            {selectedFolder?.path ?? t("collectionPicker.unsorted")}
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
        accessibilityLabel={t("share.chooseTags")}
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
    marginEnd: Spacing.sm,
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
