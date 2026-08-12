import React from "react";
import {
  View,
  Text,
  Pressable,
  ActivityIndicator,
  StyleSheet,
} from "react-native";
import { Ionicons } from "@expo/vector-icons";
import {
  Colors,
  Typography,
  Spacing,
  BorderRadius,
  Shadows,
  TouchTarget,
} from "../constants/theme";
import type { EntitlementStatus } from "../contexts/PurchasesContext";
import {
  formatPeriodEnd,
  getPeriodEndLabel,
  getStatusNote,
  getTierLabel,
  includesAudioMinutes,
} from "../lib/subscriptionDisplay";

/**
 * Read-only summary of the subscription state the backend reports on
 * `GET /api/v1/entitlements/status`: tier, audio minutes left this month and
 * period end.
 *
 * The card never gates anything — it only reports. Four states are rendered,
 * and the difference between them matters:
 * - loading (first load, nothing cached yet)
 * - unavailable (`entitlement === null`): the request failed, so the plan is
 *   *unknown*. It is deliberately not rendered as "no plan"/"free tier", which
 *   would be a claim the app cannot back.
 * - no active plan (`is_active === false`): the backend said so, that one is
 *   authoritative.
 * - active: tier plus the two figures.
 */
interface SubscriptionStatusCardProps {
  /** Backend entitlement payload, `null` while unknown or after a failure. */
  entitlement: EntitlementStatus | null;
  /** True while an entitlements request is in flight. */
  isLoading: boolean;
  /** Re-runs the entitlements request (used by the unavailable state). */
  onRetry: () => void;
}

export function SubscriptionStatusCard({
  entitlement,
  isLoading,
  onRetry,
}: SubscriptionStatusCardProps): React.JSX.Element {
  return (
    <View testID="account-plan-card" style={styles.card}>
      <Text style={styles.sectionLabel}>YOUR PLAN</Text>
      <CardBody
        entitlement={entitlement}
        isLoading={isLoading}
        onRetry={onRetry}
      />
    </View>
  );
}

function CardBody({
  entitlement,
  isLoading,
  onRetry,
}: SubscriptionStatusCardProps): React.JSX.Element {
  // Only the very first load shows a spinner. Once a payload is on screen, a
  // background refresh (tab focus, post-purchase) keeps showing the figures
  // instead of flickering back to a placeholder.
  if (entitlement === null && isLoading) {
    return (
      <View style={styles.inlineRow}>
        <ActivityIndicator size="small" color={Colors.primary} />
        <Text style={styles.bodyText}>Checking your plan...</Text>
      </View>
    );
  }

  if (entitlement === null) {
    return (
      <View testID="account-plan-unavailable">
        <View style={styles.inlineRow}>
          <Ionicons
            name="cloud-offline-outline"
            size={20}
            color={Colors.textMuted}
          />
          <Text style={styles.planName}>Plan status unavailable</Text>
        </View>
        <Text style={styles.bodyText}>
          We could not load your subscription details. Your plan itself is
          unaffected.
        </Text>
        <Pressable
          testID="account-plan-retry-button"
          style={({ pressed }) => [
            styles.retryButton,
            pressed && styles.retryButtonPressed,
          ]}
          onPress={onRetry}
          disabled={isLoading}
          accessibilityLabel="Retry loading plan details"
          accessibilityRole="button"
        >
          {isLoading ? (
            <ActivityIndicator size="small" color={Colors.textMain} />
          ) : (
            <>
              <Ionicons name="refresh" size={16} color={Colors.textMain} />
              <Text style={styles.retryButtonText}>Retry</Text>
            </>
          )}
        </Pressable>
      </View>
    );
  }

  if (!entitlement.is_active) {
    return (
      <View testID="account-plan-inactive">
        <Text style={styles.planName}>No active plan</Text>
        <Text style={styles.bodyText}>
          Your audio minutes and renewal date appear here once a subscription is
          active.
        </Text>
      </View>
    );
  }

  const tier = entitlement.subscription_tier;
  const tierLabel = getTierLabel(tier);
  const statusNote = getStatusNote(entitlement.subscription_status);
  const periodEnd = formatPeriodEnd(entitlement.period_end);
  const periodEndLabel = getPeriodEndLabel(entitlement);
  const minutesRemaining = String(entitlement.minutes_remaining);

  return (
    <View>
      <View style={styles.titleRow}>
        {/* An active subscription on a tier this build does not know still says
            something true rather than nothing. */}
        <Text testID="account-plan-tier" style={styles.planName}>
          {tierLabel ?? "Active plan"}
        </Text>
        {statusNote !== null && (
          <View style={styles.statusChip}>
            <Text style={styles.statusChipText}>{statusNote}</Text>
          </View>
        )}
      </View>

      <View style={styles.metricRow}>
        <Metric
          testID="account-plan-minutes"
          value={minutesRemaining}
          label="AUDIO MIN LEFT"
          accessibilityLabel={`${minutesRemaining} audio minutes left this month`}
        />
        <Metric
          testID="account-plan-period-end"
          value={periodEnd ?? "Unknown"}
          label={periodEndLabel}
          accessibilityLabel={
            periodEnd
              ? `${periodEndLabel.toLowerCase()} ${periodEnd}`
              : "Period end date unknown"
          }
        />
      </View>

      {!includesAudioMinutes(tier) && (
        <Text style={styles.hintText}>
          Reader covers text only, so it comes without audio minutes.
        </Text>
      )}
    </View>
  );
}

function Metric({
  testID,
  value,
  label,
  accessibilityLabel,
}: {
  testID: string;
  value: string;
  label: string;
  accessibilityLabel: string;
}): React.JSX.Element {
  return (
    <View
      testID={testID}
      style={styles.metricTile}
      accessible
      accessibilityLabel={accessibilityLabel}
    >
      <Text style={styles.metricValue} numberOfLines={1}>
        {value}
      </Text>
      <Text style={styles.metricLabel} numberOfLines={2}>
        {label}
      </Text>
    </View>
  );
}

const styles = StyleSheet.create({
  card: {
    marginHorizontal: Spacing.lg,
    marginBottom: Spacing.md,
    padding: Spacing.md,
    backgroundColor: Colors.surface,
    borderRadius: BorderRadius.xl,
    ...Shadows.soft,
  },
  sectionLabel: {
    ...Typography.small,
    fontWeight: "600",
    color: Colors.textMuted,
    letterSpacing: 0.5,
    marginBottom: Spacing.xs,
  },
  inlineRow: {
    flexDirection: "row",
    alignItems: "center",
    gap: Spacing.sm,
  },
  titleRow: {
    flexDirection: "row",
    alignItems: "center",
    gap: Spacing.sm,
  },
  planName: {
    ...Typography.headline,
    color: Colors.textMain,
    flexShrink: 1,
  },
  bodyText: {
    ...Typography.small,
    color: Colors.textMuted,
    marginTop: Spacing.xs,
  },
  hintText: {
    ...Typography.small,
    color: Colors.textMuted,
    marginTop: Spacing.sm,
  },
  statusChip: {
    paddingHorizontal: Spacing.sm,
    paddingVertical: Spacing.xs,
    borderRadius: BorderRadius.full,
    backgroundColor: Colors.surfaceContainerHigh,
  },
  statusChipText: {
    ...Typography.small,
    fontWeight: "600",
    color: Colors.textMain,
  },
  metricRow: {
    flexDirection: "row",
    gap: Spacing.sm,
    marginTop: Spacing.md,
  },
  metricTile: {
    flex: 1,
    paddingVertical: Spacing.sm,
    paddingHorizontal: Spacing.md,
    borderRadius: BorderRadius.lg,
    backgroundColor: Colors.surfaceContainerLow,
  },
  metricValue: {
    ...Typography.headline,
    color: Colors.textMain,
  },
  metricLabel: {
    ...Typography.small,
    color: Colors.textMuted,
    letterSpacing: 0.5,
    marginTop: Spacing.xs,
  },
  retryButton: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "center",
    gap: Spacing.sm,
    alignSelf: "flex-start",
    marginTop: Spacing.md,
    paddingHorizontal: Spacing.md,
    minHeight: TouchTarget.minimum,
    minWidth: TouchTarget.minimum + Spacing.xl,
    borderRadius: BorderRadius.lg,
    backgroundColor: Colors.surfaceContainer,
  },
  retryButtonPressed: {
    backgroundColor: Colors.surfaceContainerHigh,
  },
  retryButtonText: {
    ...Typography.label,
    fontWeight: "600",
    color: Colors.textMain,
  },
});
