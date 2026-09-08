import { useCallback, useEffect, useRef, useState } from "react";
import {
  View,
  Text,
  StyleSheet,
  Pressable,
  ActivityIndicator,
  Alert,
  AppState,
} from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";
import { useFocusEffect, useRouter } from "expo-router";
import { Image } from "expo-image";
import { Ionicons } from "@expo/vector-icons";
import { useAuth } from "../src/contexts/AuthContext";
import {
  ingestsOnArrival,
  useShareIntake,
  type ShareCancellation,
  type ShareContentType,
  type ShareSelectedFolder,
  type ShareIntakeState,
} from "../src/contexts/ShareIntentContext";
import {
  getQuotaErrorTitle,
  quotaErrorOffersUpgrade,
} from "../src/lib/quotaError";
import {
  formatUploadSize,
  getFileExtension,
  isImageUpload,
  type LocalUploadFile,
} from "../src/types/upload";
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
 * Confirmation screen for every incoming save: the folder is chosen here.
 *
 * Reached from the system share sheet (Android share intent / iOS share
 * extension), from the inbox "add" gesture since task-264, and from a URL typed
 * in the "+" menu since task-379. The two buttons do not mean the same thing on
 * every journey (task-378), and what splits them is whether the ingestion had
 * already started when the screen opened — `ingestsOnArrival`:
 *
 * - A share, or a URL the user typed, is already being processed when this screen
 *   appears: the ingestion started the moment the content was understood, so the
 *   modal is opened on work in progress. Save *keeps* that save, and the close
 *   button deletes it.
 * - A local import has been sent nowhere yet. Save is what submits it, and
 *   closing submits nothing and so has nothing to delete.
 *
 * Supports five content types:
 * - URL: via ingest-url
 * - Text: a note, whatever app shared it, via ingest-shared-content (task-380)
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
    cancellation,
    selectedFolder,
    submitIntake,
    confirmIntake,
    cancelIntake,
    parkCurrentIntakeForAuth,
    retry,
  } = useShareIntake();
  const [isSessionReady, setIsSessionReady] = useState(false);
  const [isConfirming, setIsConfirming] = useState(false);
  const guardInFlightRef = useRef<Promise<void> | null>(null);
  const redirectingRef = useRef(false);
  const closeInFlightRef = useRef(false);
  // What the two header buttons mean: an intake already under way is confirmed or
  // removed, one that has been sent nowhere is submitted or abandoned.
  const startedOnArrival = ingestsOnArrival(intake.origin);

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

  const leaveScreen = useCallback(() => {
    if (router.canGoBack()) {
      router.back();
    } else {
      router.replace("/(tabs)/inbox");
    }
  }, [router]);

  /**
   * The close button. On anything that started on arrival it removes the save that
   * start created, which is a network call: the screen only leaves once that call
   * succeeded, so a failed removal is never presented as a completed one.
   */
  const handleClose = useCallback(() => {
    if (closeInFlightRef.current) return;
    closeInFlightRef.current = true;
    void cancelIntake().then((removed) => {
      closeInFlightRef.current = false;
      if (removed) leaveScreen();
    });
  }, [cancelIntake, leaveScreen]);

  /**
   * A local import closes itself once it went through — there is nothing left to
   * decide. An intake that started on arrival does not: the end of the transfer is
   * not the user's answer, and closing this screen for them would take away the
   * choice of the folder and of keeping the save at all (task-378).
   */
  useEffect(() => {
    if (startedOnArrival || intake.status !== "success") return;
    const timer = setTimeout(() => {
      handleClose();
    }, 2000);
    return () => clearTimeout(timer);
  }, [handleClose, intake.status, startedOnArrival]);

  /**
   * Save. It sends the content only when nothing has been sent yet — a local
   * import, or an intake whose submission was refused. On one already under way it
   * confirms: the folder the user picked is applied, and the modal closes on the
   * save that already exists rather than creating a second one.
   */
  const handleSave = useCallback(() => {
    if (intake.status === "ready" || intake.status === "error") {
      void submitIntake();
      return;
    }
    if (isConfirming) return;
    setIsConfirming(true);
    void confirmIntake().then((result) => {
      setIsConfirming(false);
      if (result.ok) {
        leaveScreen();
      } else if (result.message) {
        Alert.alert(t("common.error"), result.message);
      }
    });
  }, [confirmIntake, intake.status, isConfirming, leaveScreen, submitIntake]);

  const handleRetry = () => {
    retry();
  };

  const handleOpenFolder = () => {
    router.push("/media/folder?mode=share");
  };

  // Offered when the backend refused the submission for a tier allowance. The
  // share intake is left untouched so the user can Save again once subscribed.
  // The reason travels with the push so the paywall can open on the refusal the
  // user is standing in rather than on a generic pitch.
  const handleOpenPaywall = () => {
    router.push("/paywall?reason=out_of_minutes");
  };

  const isRemoving = cancellation.status === "pending";
  // When the ingestion started on arrival, Save stays available for the whole life
  // of the modal: it is the answer to a save that already exists, so it is offered
  // while the content is still going out and once it has landed. A local import
  // keeps Save for the states it can actually be sent from.
  const canSave =
    !isRemoving &&
    !isConfirming &&
    (startedOnArrival
      ? intake.status === "ready" ||
        intake.status === "submitting" ||
        intake.status === "success" ||
        intake.status === "error"
      : intake.status === "ready" || intake.status === "error");

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
            disabled={isRemoving}
            accessibilityLabel={
              startedOnArrival ? t("share.cancel.action") : t("common.close")
            }
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
            {isConfirming ? (
              <ActivityIndicator size="small" color={Colors.textMain} />
            ) : (
              <Text style={styles.saveButtonText}>{t("common.save")}</Text>
            )}
          </Pressable>
        }
      />

      {/* Content */}
      <View style={styles.content}>
        {cancellation.status === "idle" ? (
          <ShareContent
            intake={intake}
            selectedFolder={selectedFolder}
            onOpenFolder={handleOpenFolder}
            onRetry={handleRetry}
            onOpenPaywall={handleOpenPaywall}
          />
        ) : (
          <CancellationState
            cancellation={cancellation}
            onRetry={handleClose}
          />
        )}
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
  onOpenFolder,
  onRetry,
  onOpenPaywall,
}: {
  intake: ShareIntakeState;
  selectedFolder: ShareSelectedFolder | null;
  onOpenFolder: () => void;
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

    // One layout for the three states a save can be seen in, because when the
    // ingestion started on arrival they are one continuous moment: the content
    // arrives, it is already being sent, and it lands — all of it under the folder
    // row the user came here for. The card's own footer says where it stands.
    case "ready":
    case "submitting":
      return (
        <IntakeChoice
          intake={intake}
          selectedFolder={selectedFolder}
          onOpenFolder={onOpenFolder}
        />
      );

    case "success":
      // A local import is done with: it was sent by Save, so this is the receipt
      // and the screen closes on its own.
      if (!ingestsOnArrival(intake.origin)) {
        return (
          <View style={styles.centerContent}>
            <View style={styles.successIcon}>
              <Ionicons
                name="checkmark-circle"
                size={48}
                color={Colors.primary}
              />
            </View>
            <Text style={styles.successTitle}>{t("share.saved")}</Text>
            <Text style={styles.successMessage}>
              {getSuccessMessage(intake)}
            </Text>
          </View>
        );
      }
      return (
        <IntakeChoice
          intake={intake}
          selectedFolder={selectedFolder}
          onOpenFolder={onOpenFolder}
        />
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
          {/* A failed transfer to S3 leaves no server-side trace — the PUT never
              goes through API Gateway — so the step it died on is only knowable
              from here (task-371). Secondary to the sentence above by design, and
              selectable so it can be quoted in a bug report. Never shown for a
              quota refusal, which the backend already logged. */}
          {quotaErrorCode === null && intake.uploadDiagnostics ? (
            <View style={styles.diagnostics}>
              <Text style={styles.diagnosticsTitle}>
                {t("upload.diagnostics.title")}
              </Text>
              <Text
                testID="share-error-diagnostics"
                style={styles.diagnosticsValue}
                selectable
              >
                {intake.uploadDiagnostics}
              </Text>
              <Text style={styles.diagnosticsHint}>
                {t("upload.diagnostics.hint")}
              </Text>
            </View>
          ) : null}
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
 * The card and the folder row: what the user came to this screen to decide.
 *
 * The folder stays pickable while the content is being sent and once it has landed
 * — the whole point of starting the ingestion on arrival is that these seconds are
 * spent on the choice instead of on a progress bar, and the provider applies a
 * late choice to the save that was already created (task-378). A local import is
 * the one case where it locks: its folder travels inside the upload request, so
 * changing it mid-flight could not be honoured.
 */
function IntakeChoice({
  intake,
  selectedFolder,
  onOpenFolder,
}: {
  intake: ShareIntakeState;
  selectedFolder: ShareSelectedFolder | null;
  onOpenFolder: () => void;
}) {
  const startedOnArrival = ingestsOnArrival(intake.origin);
  const isSubmitting = intake.status === "submitting";
  // Said only once the ingestion is actually under way, which for a share or a
  // typed URL is from the first frame after arrival: claiming it before the
  // submission left would be a promise the screen cannot keep.
  const showHint =
    startedOnArrival && (isSubmitting || intake.status === "success");

  return (
    <>
      <IntakePreview intake={intake} status={previewStatus(intake)} />
      <OrganizationControls
        selectedFolder={selectedFolder}
        onOpenFolder={onOpenFolder}
        disabled={!startedOnArrival && isSubmitting}
      />
      {showHint ? (
        <View style={styles.hintSection}>
          <Text style={styles.hintText}>
            {intake.status === "success"
              ? getSuccessMessage(intake)
              : t("share.autoStart.hint")}
          </Text>
          <Text style={styles.hintText}>{t("share.autoStart.keep")}</Text>
        </View>
      ) : null}
    </>
  );
}

/** The preview card the content type calls for, with its progress footer. */
function IntakePreview({
  intake,
  status,
}: {
  intake: ShareIntakeState;
  status: PreviewStatus | null;
}) {
  if (
    (intake.contentType === "file" || intake.contentType === "photo") &&
    intake.uploadFile
  ) {
    return <FilePreviewCard file={intake.uploadFile} status={status} />;
  }
  if (intake.contentType === "audio" && intake.audioFile) {
    return (
      <AudioPreviewCard
        fileName={intake.audioFile.fileName}
        mimeType={intake.audioFile.mimeType}
        fileSize={intake.audioFile.fileSize}
        status={status}
      />
    );
  }
  if (intake.contentType === "text" && intake.rawText) {
    return <TextPreviewCard text={intake.rawText} status={status} />;
  }
  return <UrlPreviewCard url={intake.url!} status={status} />;
}

/**
 * Where the submission stands, as the footer of a preview card.
 *
 * `done` is the difference between a spinner and a checkmark, and it is all the
 * card needs to know: it never has to close the screen or change what it shows.
 */
interface PreviewStatus {
  label: string;
  done: boolean;
}

function previewStatus(intake: ShareIntakeState): PreviewStatus | null {
  if (intake.status === "submitting") {
    return { label: submissionLabel(intake), done: false };
  }
  if (intake.status === "success") {
    return { label: t("share.autoStart.done"), done: true };
  }
  return null;
}

/**
 * What is happening while the content goes out. A transfer is named for what it
 * is — bytes leaving the device, which is the slow part and the one worth
 * announcing — where a link or a message is just a submission.
 */
function submissionLabel(intake: ShareIntakeState): string {
  switch (intake.contentType) {
    case "audio":
      return t("share.uploadingAudio");
    case "photo":
      return t("share.uploadingFile");
    case "file":
      return intake.uploadFile?.kind === "audio"
        ? t("share.uploadingAudio")
        : t("share.uploadingFile");
    default:
      return t("share.saving");
  }
}

/**
 * The removal of a share the user closed, and its failure.
 *
 * A failure has to be readable and retryable: the save exists on the server, so
 * saying nothing would leave in the library an item the user asked to be rid of.
 * The retry is the same gesture as the close it came from, and Save is still
 * there for someone who would rather keep it after all (task-378).
 */
function CancellationState({
  cancellation,
  onRetry,
}: {
  cancellation: ShareCancellation;
  onRetry: () => void;
}) {
  if (cancellation.status === "pending") {
    return (
      <View style={styles.centerContent}>
        <ActivityIndicator size="large" color={Colors.primary} />
        <Text style={styles.statusText}>{t("share.cancel.inProgress")}</Text>
      </View>
    );
  }

  return (
    <View style={styles.centerContent} testID="share-cancel-error-state">
      <View style={styles.errorIcon}>
        <Ionicons name="alert-circle" size={48} color={Colors.error} />
      </View>
      <Text style={styles.errorTitle}>{t("share.cancel.failedTitle")}</Text>
      <Text testID="share-cancel-error-message" style={styles.errorMessage}>
        {cancellation.message ?? t("share.cancel.failed")}
      </Text>
      <Pressable
        style={styles.retryButton}
        onPress={onRetry}
        accessibilityLabel={t("paywall.tryAgain")}
        accessibilityRole="button"
      >
        <Ionicons name="refresh" size={18} color={Colors.textMain} />
        <Text style={styles.retryButtonText}>{t("paywall.tryAgain")}</Text>
      </Pressable>
      <Text style={styles.cancelKeepHint}>{t("share.cancel.keepHint")}</Text>
    </View>
  );
}

/**
 * What the user reads once the save went through. Every content type says what
 * happens next, because the processing that follows is asynchronous.
 */
function getSuccessMessage(intake: ShareIntakeState): string {
  if (intake.deduplicated) {
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
 * Preview card for anything headed to the upload endpoints: a file picked from
 * the device, a photo just taken, an image or a document handed over by the
 * system share sheet. Shows what is about to be sent — the picture itself for an
 * image, otherwise name, format and size — so the user confirms the right thing
 * before Save.
 */
function FilePreviewCard({
  file,
  status = null,
}: {
  file: LocalUploadFile;
  status?: PreviewStatus | null;
}) {
  // A picture identifies itself far better than any label could, so the icon
  // slot shows the picture itself — a camera capture, a gallery pick or an image
  // shared from the share sheet alike. The icon stays as the fallback for the
  // one case that can fail: a URI the app cannot read back.
  const [thumbnailFailed, setThumbnailFailed] = useState(false);
  const isImage = isImageUpload(file);
  const showThumbnail = isImage && !thumbnailFailed;
  const iconName = isImage
    ? "image-outline"
    : file.kind === "audio"
      ? "musical-notes-outline"
      : "document-text-outline";

  const subtitleParts: string[] = [];
  const extension = getFileExtension(file.name);
  if (extension) {
    subtitleParts.push(`.${extension}`);
  }
  if (file.size !== null) {
    subtitleParts.push(formatUploadSize(file.size));
  }

  return (
    <View style={styles.previewCard}>
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
          {showThumbnail ? (
            <Image
              source={{ uri: file.uri }}
              style={styles.previewThumbnail}
              contentFit="cover"
              onError={() => setThumbnailFailed(true)}
              accessibilityIgnoresInvertColors
            />
          ) : (
            <Ionicons name={iconName} size={24} color={Colors.textMuted} />
          )}
        </View>
      </View>
      <PreviewStatusFooter status={status} />
    </View>
  );
}

/**
 * The progress line of a preview card: a spinner while the content is on its way,
 * a checkmark once the backend has it. Nothing at all before that.
 *
 * The card itself is never dimmed while this shows: on a share it is the one thing
 * on screen the user is being asked about, and the folder row above it is still
 * live.
 */
function PreviewStatusFooter({ status }: { status: PreviewStatus | null }) {
  if (!status) return null;
  return (
    <View style={styles.previewSubmitting}>
      {status.done ? (
        <Ionicons name="checkmark-circle" size={16} color={Colors.primary} />
      ) : (
        <ActivityIndicator size="small" color={Colors.primary} />
      )}
      <Text style={styles.previewSubmittingText}>{status.label}</Text>
    </View>
  );
}

/**
 * Preview card showing the URL being saved.
 * Matches the design mockup's media card layout.
 */
function UrlPreviewCard({
  url,
  status = null,
}: {
  url: string;
  status?: PreviewStatus | null;
}) {
  let displayDomain: string;
  try {
    const parsed = new URL(url);
    displayDomain = parsed.hostname.replace(/^www\./, "");
  } catch {
    displayDomain = url;
  }

  return (
    <View style={styles.previewCard}>
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
      <PreviewStatusFooter status={status} />
    </View>
  );
}

/**
 * Preview card for shared plain text: a note (task-380).
 *
 * Says "Note", not the name of an app, because no platform tells us which app the
 * text came from — and shows a document icon rather than a speech bubble, since
 * what is being saved is a note and not a conversation.
 */
function TextPreviewCard({
  text,
  status = null,
}: {
  text: string;
  status?: PreviewStatus | null;
}) {
  return (
    <View style={styles.previewCard}>
      <View style={styles.previewCardContent}>
        <View style={styles.previewTextSection}>
          <Text style={styles.previewUrl} numberOfLines={5}>
            {text}
          </Text>
          <Text style={styles.previewDomain}>{t("share.noteText")}</Text>
        </View>
        <View style={styles.previewIconContainer}>
          <Ionicons
            name="document-text-outline"
            size={24}
            color={Colors.textMuted}
          />
        </View>
      </View>
      <PreviewStatusFooter status={status} />
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
  status = null,
}: {
  fileName: string | null;
  mimeType: string;
  fileSize: number | null;
  status?: PreviewStatus | null;
}) {
  const displayName = fileName ?? "Voice message";
  const displaySize = fileSize
    ? fileSize > 1024 * 1024
      ? `${(fileSize / (1024 * 1024)).toFixed(1)} MB`
      : `${Math.round(fileSize / 1024)} KB`
    : mimeType;

  return (
    <View style={styles.previewCard}>
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
      <PreviewStatusFooter status={status} />
    </View>
  );
}

function OrganizationControls({
  selectedFolder,
  onOpenFolder,
  disabled = false,
}: {
  selectedFolder: ShareSelectedFolder | null;
  onOpenFolder: () => void;
  disabled?: boolean;
}) {
  return (
    <View style={styles.organizationSection}>
      <Pressable
        style={({ pressed }) => [
          styles.organizationRow,
          pressed && !disabled && styles.organizationRowPressed,
          disabled && styles.organizationRowDisabled,
        ]}
        onPress={onOpenFolder}
        disabled={disabled}
        accessibilityLabel={t("share.chooseFolder")}
        accessibilityRole="button"
      >
        <View style={styles.organizationRowLeft}>
          <Ionicons
            name="folder-open-outline"
            size={20}
            color={Colors.textMuted}
          />
          <Text style={styles.organizationRowLabel} numberOfLines={1}>
            {selectedFolder?.path ?? t("share.folderPlaceholder")}
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
    // The image thumbnail fills this slot edge to edge, so its corners have to
    // be cut by the container rather than by the image itself.
    overflow: "hidden",
  },
  previewThumbnail: {
    width: "100%",
    height: "100%",
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
  // What the two header buttons now mean, said in words under the choice they
  // apply to. No card and no rule around it: it is a caption, not a section.
  hintSection: {
    marginTop: Spacing.md,
    paddingHorizontal: Spacing.md,
    gap: Spacing.xs,
  },
  hintText: {
    fontSize: Typography.small.fontSize,
    color: Colors.textSubtle,
  },
  cancelKeepHint: {
    fontSize: Typography.small.fontSize,
    color: Colors.textSubtle,
    textAlign: "center",
    marginTop: Spacing.md,
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
  // Technical detail block, sectioned by a tonal shift rather than a rule, the
  // same way StartupErrorScreen presents the error it caught.
  diagnostics: {
    alignSelf: "stretch",
    backgroundColor: Colors.surfaceContainer,
    borderRadius: BorderRadius.lg,
    padding: Spacing.md,
    marginBottom: Spacing.lg,
    gap: Spacing.xs,
  },
  diagnosticsTitle: {
    fontSize: Typography.small.fontSize,
    color: Colors.textSubtle,
  },
  diagnosticsValue: {
    fontSize: Typography.label.fontSize,
    fontWeight: Typography.label.fontWeight,
    color: Colors.textMain,
    // The payload is stable ASCII key=value pairs, so it stays left-to-right even
    // when the interface language is not — an Arabic UI must not reorder it.
    textAlign: "left",
    writingDirection: "ltr",
  },
  diagnosticsHint: {
    fontSize: Typography.small.fontSize,
    color: Colors.textSubtle,
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
