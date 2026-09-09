import React, { useState } from "react";
import {
  View,
  Text,
  Pressable,
  StyleSheet,
  ActivityIndicator,
  Platform,
} from "react-native";
import Constants from "expo-constants";
import { Ionicons } from "@expo/vector-icons";
import {
  Colors,
  Typography,
  Spacing,
  BorderRadius,
  TouchTarget,
} from "../constants/theme";
import { BugReportService } from "../services/bugReportService";
import {
  getFriendlyErrorMessage,
  isSourceSupportRequestable,
} from "../lib/getFriendlyErrorMessage";
import type { MediaFailureCode } from "../types/media";
import { t } from "../i18n";

/**
 * "This source isn't supported yet — would you like it to be?", under the failure
 * message of a media that could not be imported (task-381).
 *
 * One tap, one `POST /api/bug-reports`, one confirmation. No form, no subject to
 * type, no attachment: the subject and the description are built here from the
 * catalogues, and everything that identifies the media travels as
 * `media_item_id`. The server reads the address off the caller's own library row,
 * which is why nothing here shows a URL — and why nothing here has to ask the
 * reader to copy a reference.
 *
 * The `MediaFailureCode` is not shown either. It is a contract identifier, not a
 * sentence; the reader already has the sentence right above this card.
 *
 * A component of its own, and not a block inside `app/media/[id].tsx`, because it
 * owns state and that route is a chain of early returns: a `useState` at its top
 * would run on the loading, error, processing and completed paths as well, for a
 * button four of them never draw.
 *
 * The "sent" state lives here and dies with the screen. A tester who comes back
 * can post again, which is fine: the hourly limit bounds the volume and the owner
 * de-duplicates by `media_item_id`. Nothing is written to disk for it, and no
 * uniqueness guard is asked of the server.
 */

type RequestState = "idle" | "sending" | "sent";

interface SourceSupportRequestCardProps {
  /** The item whose import failed — the route's own `id`. */
  mediaItemId: string;
  /**
   * The code the job failed with, straight from `mediaData.processing_job`. The
   * card renders nothing at all unless it is one of the eight for which "this
   * source isn't supported yet" is a true statement.
   */
  errorCode?: MediaFailureCode | null;
}

export function SourceSupportRequestCard({
  mediaItemId,
  errorCode,
}: SourceSupportRequestCardProps): React.JSX.Element | null {
  const [state, setState] = useState<RequestState>("idle");
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  // Not `Platform.OS`: the block is the same on both platforms, and the only
  // thing that decides whether it appears is whether its sentence is true.
  if (!isSourceSupportRequestable(errorCode)) {
    return null;
  }

  const handlePress = (): void => {
    if (state !== "idle") return;
    setState("sending");
    setErrorMessage(null);

    void BugReportService.createBugReport({
      subject: t("sourceRequest.reportSubject"),
      description: t("sourceRequest.reportDescription"),
      media_item_id: mediaItemId,
      error_code: errorCode,
      source_app_version: Constants.expoConfig?.version ?? null,
      source_platform: Platform.OS,
    })
      .then(() => setState("sent"))
      .catch((error: unknown) => {
        // Covers the hourly limit for free: a 429 already resolves to
        // `error.rateLimited` through the shared mapping, so there is no new
        // sentence to write for it.
        setErrorMessage(
          getFriendlyErrorMessage(error, {
            fallback: t("bugReport.submitFailed"),
          }),
        );
        setState("idle");
      });
  };

  return (
    <View style={styles.card} testID="source-support-request">
      <Text style={styles.title}>{t("sourceRequest.title")}</Text>
      <Text style={styles.intro}>{t("sourceRequest.intro")}</Text>

      {state === "sent" ? (
        // No longer a `Pressable`: once the request is in, there is nothing left
        // to press, and a disabled button would only invite the tap again.
        <View
          style={styles.confirmation}
          accessibilityRole="text"
          accessibilityLiveRegion="polite"
        >
          <Ionicons
            name="checkmark-circle"
            size={20}
            color={Colors.primary}
          />
          <Text style={styles.confirmationText}>{t("sourceRequest.sent")}</Text>
        </View>
      ) : (
        <Pressable
          testID="source-support-request-button"
          style={({ pressed }) => [
            styles.action,
            pressed && styles.actionPressed,
            state === "sending" && styles.actionBusy,
          ]}
          onPress={handlePress}
          disabled={state === "sending"}
          accessibilityLabel={t("sourceRequest.actionA11y")}
          accessibilityRole="button"
          accessibilityState={{ disabled: state === "sending" }}
        >
          {state === "sending" ? (
            <ActivityIndicator size="small" color={Colors.textMain} />
          ) : (
            <Ionicons name="megaphone-outline" size={18} color={Colors.textMain} />
          )}
          <Text style={styles.actionText}>
            {state === "sending"
              ? t("sourceRequest.sending")
              : t("sourceRequest.action")}
          </Text>
        </Pressable>
      )}

      {errorMessage ? (
        <Text style={styles.error} accessibilityLiveRegion="polite">
          {errorMessage}
        </Text>
      ) : null}
    </View>
  );
}

const styles = StyleSheet.create({
  // A tonal callout, not a bordered box: the surface shift is what separates it
  // from the screen behind it ("No-Line rule").
  card: {
    alignSelf: "stretch",
    gap: Spacing.xs,
    padding: Spacing.md,
    borderRadius: BorderRadius.lg,
    backgroundColor: Colors.surfaceContainer,
    // On top of the column's own gap: a second offer needs to read as separate
    // from the screen's primary action rather than as its second half.
    marginTop: Spacing.sm,
  },
  title: {
    ...Typography.label,
    fontWeight: "600",
    color: Colors.textMain,
    textAlign: "center",
  },
  intro: {
    ...Typography.small,
    color: Colors.textSubtle,
    textAlign: "center",
  },
  // Lighter than the card it sits on, which is what makes it read as raised
  // without a line around it. Not amber: "Refresh" right above already carries
  // the screen's one primary action, and two amber buttons stacked read as a
  // choice between equals.
  action: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "center",
    gap: Spacing.sm,
    minHeight: TouchTarget.minimum,
    paddingHorizontal: Spacing.lg,
    borderRadius: BorderRadius.md,
    backgroundColor: Colors.surface,
    marginTop: Spacing.sm,
  },
  actionPressed: {
    opacity: 0.7,
  },
  actionBusy: {
    opacity: 0.6,
  },
  actionText: {
    ...Typography.label,
    fontWeight: "600",
    color: Colors.textMain,
  },
  // Same height as the button it replaces, so the card does not resize under the
  // reader's thumb when the request goes through.
  confirmation: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "center",
    gap: Spacing.sm,
    minHeight: TouchTarget.minimum,
    marginTop: Spacing.sm,
  },
  confirmationText: {
    ...Typography.label,
    fontWeight: "600",
    color: Colors.textMain,
  },
  error: {
    ...Typography.small,
    color: Colors.error,
    textAlign: "center",
  },
});
