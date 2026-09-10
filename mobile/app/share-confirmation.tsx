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
import { t, useTranslation } from "../src/i18n";
import { ScreenHeader, HeaderIconButton } from "../src/components/ScreenHeader";

/**
 * What the user sees for every incoming save: one sentence and one question.
 *
 * Reached from the system share sheet (Android share intent / iOS share
 * extension), from the inbox "add" gesture since task-264, and from a URL typed
 * in the "+" menu since task-379. All three start their ingestion on arrival
 * (task-389), so by the time this screen draws, the save exists — there is
 * nothing to confirm, no content to preview and no title to give it. The only
 * thing still undecided is where it should live:
 *
 *     Your media is being saved to your second brain.
 *     Would you also like to file it in a folder?
 *                                   [ No ]  [ Yes ]
 *
 * Yes opens the folder picker, where a tap on a destination *is* the filing —
 * `selectFolder` patches the save straight away, so the choice lands even if this
 * screen is gone — and coming back from it ends the modal. No closes, and deletes
 * nothing: the question is about filing, so neither answer means "throw it away".
 * A media shared by mistake is removed from the inbox, like any other.
 *
 * The other face of this screen is failure, and it is the only place several
 * failures can be read at all: a quota refusal with its route to the paywall, a
 * transfer that never reached the backend, and content the app cannot save. Each
 * one reads as one sentence naming what to do next — the step a transfer died on
 * is a fact for the logs, not for the person holding the phone.
 */
export default function ShareConfirmationScreen() {
  // Copy resolved on render: redraw when the interface language changes.
  useTranslation();
  const router = useRouter();
  const { isAuthenticated, isLoading, revalidateSession } = useAuth();
  const { intake, dismissIntake, parkCurrentIntakeForAuth, retry } =
    useShareIntake();
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

  const leaveScreen = useCallback(() => {
    if (router.canGoBack()) {
      router.back();
    } else {
      router.replace("/(tabs)/inbox");
    }
  }, [router]);

  /**
   * "No", and the close button: let the intake go and leave. No network call, so
   * nothing can fail and nothing has to be waited for.
   */
  const handleDismiss = useCallback(() => {
    dismissIntake();
    leaveScreen();
  }, [dismissIntake, leaveScreen]);

  /**
   * Back from the folder picker: whatever happened there, this modal is done.
   *
   * "Yes" is a one-way door, and it has to be, because the picker answers the
   * question in more ways than a folder id can carry. A tap on a folder lands in
   * `selectedFolder`; a tap on "Unsorted" lands as `null`, which is
   * indistinguishable from never having gone; and backing out is the user saying
   * "no folder after all". All three are answers, and all three leave the save
   * exactly where the user wants it — so the trip itself is the signal rather
   * than what it brought back.
   *
   * The filing does not depend on this screen surviving: `selectFolder` patches
   * the save from the provider the moment a destination is tapped.
   */
  const visitedPickerRef = useRef(false);

  useFocusEffect(
    useCallback(() => {
      if (!visitedPickerRef.current) return;
      handleDismiss();
    }, [handleDismiss]),
  );

  const handleOpenFolder = () => {
    visitedPickerRef.current = true;
    router.push("/media/folder?mode=share");
  };

  const handleRetry = () => {
    retry();
  };

  // Offered when the backend refused the submission for a tier allowance. The
  // reason travels with the push so the paywall can open on the refusal the user
  // is standing in rather than on a generic pitch.
  const handleOpenPaywall = () => {
    router.push("/paywall?reason=out_of_minutes");
  };

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
      {/* Close on the left and nothing else: there is no content to name and no
          action to offer up here — the answer is given in the body. */}
      <ScreenHeader
        leading={
          <HeaderIconButton
            icon="close"
            onPress={handleDismiss}
            accessibilityLabel={t("common.close")}
          />
        }
      />

      <View style={styles.content}>
        <ShareContent
          intake={intake}
          onOpenFolder={handleOpenFolder}
          onDismiss={handleDismiss}
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
  onOpenFolder,
  onDismiss,
  onRetry,
  onOpenPaywall,
}: {
  intake: ShareIntakeState;
  onOpenFolder: () => void;
  onDismiss: () => void;
  onRetry: () => void;
  onOpenPaywall: () => void;
}) {
  switch (intake.status) {
    // "ready" belongs here and not with the question: the submission has been
    // fired but has not left yet, and it lasts a frame. Saying "is being saved"
    // before that would be a promise the screen cannot keep.
    case "idle":
    case "validating":
    case "ready":
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

    // The save is on its way, or landed. One layout for both, because the
    // difference does not concern the user: what is asked of them is the same,
    // and the answer applies to a save that exists either way.
    case "submitting":
    case "success":
      return (
        <FolderQuestion
          deduplicated={intake.deduplicated === true}
          onYes={onOpenFolder}
          onNo={onDismiss}
        />
      );

    case "error": {
      // A quota refusal is not a failure the user can retry into success: it is
      // a limit, so it reads as one. The sentence is built from this app's
      // catalogue out of the figures the backend sent, and names the limit that
      // was reached.
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
              <Text style={styles.upgradeButtonText}>
                {t("quota.seePlans")}
              </Text>
            </Pressable>
          )}
          {/* No retry on a limit: the same submission would be refused for the
              same reason. Someone who subscribes on the paywall sends the content
              again from the app it came from. */}
          {quotaErrorCode === null && (
            <Pressable
              style={styles.retryButton}
              onPress={onRetry}
              accessibilityLabel={t("paywall.tryAgain")}
              accessibilityRole="button"
            >
              <Ionicons name="refresh" size={18} color={Colors.textMain} />
              <Text style={styles.retryButtonText}>
                {t("paywall.tryAgain")}
              </Text>
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
 * The whole modal, in the nominal case: what is happening, and the one question
 * left.
 *
 * Text and two buttons, nothing else. The ingestion needs no progress bar — it
 * outlives this screen — and the content needs no preview: the user just picked
 * it in another app, one second ago.
 *
 * `deduplicated` swaps the first sentence for the one case where it would be
 * false: the backend recognised content it already holds, so nothing is being
 * saved. The question still stands — a media already in the library can still be
 * filed.
 */
function FolderQuestion({
  deduplicated,
  onYes,
  onNo,
}: {
  deduplicated: boolean;
  onYes: () => void;
  onNo: () => void;
}) {
  return (
    <View style={styles.questionContent}>
      <Text style={styles.questionBody}>
        {deduplicated
          ? t("share.inProgress.duplicate")
          : t("share.inProgress.body")}
      </Text>
      <Text style={styles.questionPrompt}>
        {t("share.inProgress.question")}
      </Text>

      <View style={styles.answers}>
        <Pressable
          testID="share-folder-no"
          style={({ pressed }) => [
            styles.answerButton,
            styles.answerNo,
            pressed && styles.answerNoPressed,
          ]}
          onPress={onNo}
          accessibilityLabel={t("common.no")}
          accessibilityRole="button"
        >
          <Text style={styles.answerNoLabel}>{t("common.no")}</Text>
        </Pressable>

        <Pressable
          testID="share-folder-yes"
          style={({ pressed }) => [
            styles.answerButton,
            styles.answerYes,
            pressed && styles.answerYesPressed,
          ]}
          onPress={onYes}
          accessibilityLabel={t("common.yes")}
          accessibilityRole="button"
        >
          <Text style={styles.answerYesLabel}>{t("common.yes")}</Text>
        </Pressable>
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: Colors.background,
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
  // The question, centred in the sheet. No card and no rule: two sentences on
  // the page are their own hierarchy.
  questionContent: {
    flex: 1,
    justifyContent: "center",
    paddingHorizontal: Spacing.sm,
    paddingBottom: Spacing.xxl,
    gap: Spacing.md,
  },
  questionBody: {
    fontSize: Typography.body.fontSize,
    lineHeight: Typography.body.lineHeight,
    color: Colors.textSubtle,
    textAlign: "center",
  },
  questionPrompt: {
    fontSize: Typography.headline.fontSize,
    fontWeight: Typography.headline.fontWeight,
    color: Colors.textMain,
    textAlign: "center",
  },
  answers: {
    flexDirection: "row",
    gap: Spacing.md,
    marginTop: Spacing.lg,
  },
  // Both answers carry the same weight of target — the labels are two or three
  // letters, and neither is a destructive action.
  answerButton: {
    flex: 1,
    minHeight: TouchTarget.comfortable,
    alignItems: "center",
    justifyContent: "center",
    paddingHorizontal: Spacing.lg,
    borderRadius: BorderRadius.full,
  },
  answerNo: {
    backgroundColor: Colors.surfaceContainer,
  },
  answerNoPressed: {
    backgroundColor: Colors.surfaceContainerHigh,
  },
  answerNoLabel: {
    fontSize: Typography.label.fontSize,
    fontWeight: "600",
    color: Colors.textMain,
  },
  answerYes: {
    backgroundColor: Colors.primary,
    ...Shadows.soft,
  },
  answerYesPressed: {
    opacity: 0.85,
  },
  answerYesLabel: {
    fontSize: Typography.label.fontSize,
    fontWeight: "700",
    color: Colors.onPrimary,
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
