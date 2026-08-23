import React from "react";
import { View, Text, StyleSheet } from "react-native";
import { Colors, Typography, Spacing, BorderRadius } from "../constants/theme";
import { usePurchases } from "../contexts/PurchasesContext";
import { getDaysUntil } from "../lib/subscriptionDisplay";
import { t, tCount } from "../i18n";

/**
 * The one place the app says a free trial is running: a small centred notice at
 * the top of the inbox, counting the days left.
 *
 * Until task-301 nothing on any screen contained the word trial — `is_free_trial`
 * was declared on the entitlement payload and read by no one — so a trial looked
 * exactly like a paid plan whose "period ends" on a date the user read as the day
 * their access stopped. It is that date; the fix is to say so.
 *
 * The notice reports, it never decides. Whether a trial is running is
 * `is_free_trial` from the backend and never a date comparison made here; the
 * countdown is presentation of `resets_at`, which after task-300 is the trial's
 * closing instant. The app is not told when the trial opened and does not try to
 * reconstruct its length: one date in, one countdown out.
 */
export function FreeTrialNotice(): React.JSX.Element | null {
  const { entitlementStatus } = usePurchases();

  // Nothing to say while the payload is missing, loading or errored, and nothing
  // once the backend stops calling it a trial (subscribed, or trial over).
  if (!entitlementStatus?.is_free_trial) {
    return null;
  }

  const message = buildTrialMessage(entitlementStatus.resets_at);

  return (
    <View style={styles.row}>
      <View testID="free-trial-notice" style={styles.pill}>
        <Text style={styles.text}>{message}</Text>
      </View>
    </View>
  );
}

/**
 * The owner's wording, `Free Trial - X days left`, with two cases it cannot
 * state truthfully:
 *
 * - **The last day.** `getDaysUntil` counts local midnight boundaries, so it
 *   returns 0 for a trial closing today — and "0 days left" would be false while
 *   access is still granted, exactly as "1 day left" would be for the eleven
 *   hours before the close. That day says "last day" instead, which is true for
 *   the whole of it. Every other figure is a real number of days: 1 means the
 *   trial closes tomorrow.
 * - **No date.** `resets_at` is nullable on the payload. The trial is still
 *   running — the backend said so — so the notice stays, without a countdown it
 *   would have to invent.
 */
function buildTrialMessage(resetsAt: string | null): string {
  const daysLeft = getDaysUntil(resetsAt);
  if (daysLeft === null) return t("trial.badge");
  if (daysLeft === 0) return t("trial.lastDay");
  return tCount("trial.daysLeft", daysLeft);
}

const styles = StyleSheet.create({
  // The pill sizes to its text and the row centres it, so the notice reads as a
  // small badge rather than a full-width banner — the minutes warning below it
  // is the full-width one, and the two must not look like the same alert.
  row: {
    alignItems: "center",
    marginTop: Spacing.md,
    paddingHorizontal: Spacing.md,
  },
  pill: {
    paddingVertical: Spacing.xs,
    paddingHorizontal: Spacing.md,
    borderRadius: BorderRadius.full,
    backgroundColor: Colors.highlight,
  },
  text: {
    ...Typography.small,
    fontWeight: "600",
    color: Colors.onHighlight,
    textAlign: "center",
  },
});
