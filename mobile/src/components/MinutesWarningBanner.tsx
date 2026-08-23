import React, { useEffect, useState } from "react";
import { View, Text, Pressable, StyleSheet } from "react-native";
import { Ionicons } from "@expo/vector-icons";
import { useRouter } from "expo-router";
import {
  Colors,
  Typography,
  Spacing,
  BorderRadius,
  TouchTarget,
} from "../constants/theme";
import { usePurchases } from "../contexts/PurchasesContext";
import { formatResetDate, getUsageRatio } from "../lib/subscriptionDisplay";
import { UsageWarningDismissal } from "../lib/usageWarningDismissal";
import { t } from "../i18n";

/**
 * The one warning the app gives before the wall: an inline notice, at the top of
 * the inbox, when most of the period's minutes are spent.
 *
 * The threshold belongs to the backend (`usage_gauge.warning_threshold_pct` in
 * `pricing_config`), which is why this reads `warning_threshold_reached` instead of
 * comparing numbers itself: the percentage the user is told about and the
 * percentage that triggered the notice are then the same one.
 *
 * Deliberately not a modal and never repeated once dismissed — it carries no
 * decision, only the two facts that let the user make one (how much is left, what
 * happens on the date) plus a way to see the plans.
 */
export function MinutesWarningBanner(): React.JSX.Element | null {
  const router = useRouter();
  const { entitlementStatus } = usePurchases();
  const resetsAt = entitlementStatus?.resets_at ?? null;
  const shouldWarn = entitlementStatus?.warning_threshold_reached === true;

  // Starts hidden: the dismissal is on disk, and flashing the banner for one
  // frame before reading it would defeat "not repeated".
  const [isDismissed, setIsDismissed] = useState(true);

  useEffect(() => {
    if (!shouldWarn) return;
    let isCurrent = true;
    void UsageWarningDismissal.isDismissed(resetsAt).then((dismissed) => {
      if (isCurrent) setIsDismissed(dismissed);
    });
    return () => {
      isCurrent = false;
    };
  }, [shouldWarn, resetsAt]);

  if (!entitlementStatus || !shouldWarn || isDismissed) {
    return null;
  }

  const usedPercent = Math.round(getUsageRatio(entitlementStatus) * 100);
  const resetDate = formatResetDate(resetsAt);
  const message = buildMessage(
    usedPercent,
    resetDate,
    entitlementStatus.is_free_trial,
  );

  const handleDismiss = (): void => {
    setIsDismissed(true);
    void UsageWarningDismissal.dismiss(resetsAt);
  };

  return (
    <View testID="minutes-warning-banner" style={styles.banner}>
      <Ionicons name="timer-outline" size={20} color={Colors.textMain} />

      <View style={styles.content}>
        <Text style={styles.message}>{message}</Text>
        <Pressable
          testID="minutes-warning-see-plans"
          style={({ pressed }) => [styles.link, pressed && styles.linkPressed]}
          onPress={() => router.push("/paywall?reason=running_low")}
          accessibilityLabel={t("quota.seePlans")}
          accessibilityRole="button"
        >
          <Text style={styles.linkText}>{t("quota.seePlans")}</Text>
        </Pressable>
      </View>

      <Pressable
        testID="minutes-warning-dismiss"
        style={({ pressed }) => [styles.dismiss, pressed && styles.linkPressed]}
        onPress={handleDismiss}
        accessibilityLabel={t("quota.dismissWarning")}
        accessibilityRole="button"
      >
        <Ionicons name="close" size={20} color={Colors.textMuted} />
      </Pressable>
    </View>
  );
}

/**
 * The banner's sentence. A trial allowance is a single window that never
 * refills (task-300), so telling a trial user their minutes "reset on" that
 * date was false on this surface too — the date is when the trial closes, and
 * the wording now says which of the two it is.
 */
function buildMessage(
  usedPercent: number,
  resetDate: string | null,
  isFreeTrial: boolean,
): string {
  // Each case is one whole sentence in the catalogue rather than a stem the
  // code glues a clause onto: the two halves do not keep their order, or even
  // their boundary, once translated.
  if (resetDate === null) {
    return isFreeTrial
      ? t("quota.warning.trial", { percent: usedPercent })
      : t("quota.warning.monthly", { percent: usedPercent });
  }
  return isFreeTrial
    ? t("quota.warning.trialWithDate", { percent: usedPercent, date: resetDate })
    : t("quota.warning.monthlyWithDate", {
        percent: usedPercent,
        date: resetDate,
      });
}

const styles = StyleSheet.create({
  banner: {
    flexDirection: "row",
    alignItems: "flex-start",
    gap: Spacing.sm,
    marginHorizontal: Spacing.md,
    marginTop: Spacing.md,
    paddingVertical: Spacing.sm,
    paddingStart: Spacing.md,
    paddingEnd: Spacing.xs,
    borderRadius: BorderRadius.lg,
    backgroundColor: Colors.surfaceContainerHigh,
  },
  content: {
    flex: 1,
    // Balances the icon's optical centre against the first line of text without
    // pushing the whole row down.
    paddingTop: Spacing.xs / 2,
  },
  message: {
    ...Typography.small,
    color: Colors.textMain,
  },
  link: {
    alignSelf: "flex-start",
    justifyContent: "center",
    minHeight: TouchTarget.minimum,
    paddingEnd: Spacing.md,
  },
  linkText: {
    ...Typography.label,
    fontWeight: "600",
    color: Colors.textMain,
    textDecorationLine: "underline",
  },
  linkPressed: {
    opacity: 0.6,
  },
  dismiss: {
    alignItems: "center",
    justifyContent: "center",
    minHeight: TouchTarget.minimum,
    minWidth: TouchTarget.minimum,
    borderRadius: BorderRadius.full,
  },
});
