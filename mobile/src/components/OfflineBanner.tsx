import React from "react";
import { View, Text, StyleSheet, Pressable } from "react-native";
import { Ionicons } from "@expo/vector-icons";
import { Colors, Typography, Spacing, BorderRadius } from "../constants/theme";

interface OfflineBannerProps {
  /** Number of items queued for sync when back online */
  queuedCount?: number;
  /** Whether a sync is currently in progress */
  isSyncing?: boolean;
  /** Callback to manually trigger sync */
  onSyncPress?: () => void;
}

/**
 * Banner displayed when the device is offline.
 * Shows a persistent indicator with the number of queued items
 * and a sync button when applicable.
 *
 * Implements AC#6: Offline/poor network behavior is defined and
 * implemented for shared-link queue and sync.
 */
export function OfflineBanner({
  queuedCount = 0,
  isSyncing = false,
  onSyncPress,
}: OfflineBannerProps) {
  return (
    <View style={styles.container}>
      <View style={styles.content}>
        <Ionicons
          name="cloud-offline-outline"
          size={18}
          color={Colors.textMain}
        />
        <View style={styles.textContainer}>
          <Text style={styles.title}>You are offline</Text>
          {queuedCount > 0 && (
            <Text style={styles.subtitle}>
              {queuedCount} link{queuedCount > 1 ? "s" : ""} queued for sync
            </Text>
          )}
          {queuedCount === 0 && (
            <Text style={styles.subtitle}>
              Shared links will be saved and synced when you reconnect
            </Text>
          )}
        </View>
        {isSyncing && (
          <Text style={styles.syncingText}>Syncing...</Text>
        )}
        {!isSyncing && onSyncPress && queuedCount > 0 && (
          <Pressable
            style={styles.syncButton}
            onPress={onSyncPress}
            hitSlop={{ top: 8, bottom: 8, left: 8, right: 8 }}
          >
            <Ionicons name="sync-outline" size={16} color={Colors.primary} />
          </Pressable>
        )}
      </View>
    </View>
  );
}

/**
 * Compact banner shown when syncing after coming back online.
 */
export function SyncingBanner({ count }: { count: number }) {
  if (count === 0) return null;

  return (
    <View style={styles.syncingContainer}>
      <Ionicons name="sync-outline" size={14} color={Colors.primary} />
      <Text style={styles.syncingBannerText}>
        Syncing {count} queued link{count > 1 ? "s" : ""}...
      </Text>
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    marginHorizontal: Spacing.md,
    marginBottom: Spacing.md,
    backgroundColor: Colors.surfaceContainerHigh,
    borderRadius: BorderRadius.lg,
    borderWidth: StyleSheet.hairlineWidth,
    borderColor: Colors.outlineVariant,
  },
  content: {
    flexDirection: "row",
    alignItems: "center",
    gap: Spacing.sm,
    paddingHorizontal: Spacing.md,
    paddingVertical: Spacing.sm + 4,
  },
  textContainer: {
    flex: 1,
  },
  title: {
    fontSize: Typography.label.fontSize,
    fontWeight: Typography.label.fontWeight,
    color: Colors.textMain,
  },
  subtitle: {
    fontSize: Typography.small.fontSize,
    color: Colors.textMuted,
    marginTop: 2,
  },
  syncButton: {
    width: 36,
    height: 36,
    borderRadius: BorderRadius.full,
    backgroundColor: Colors.surfaceContainerLow,
    alignItems: "center",
    justifyContent: "center",
  },
  syncingText: {
    fontSize: Typography.small.fontSize,
    color: Colors.textMuted,
    fontStyle: "italic",
  },
  syncingContainer: {
    flexDirection: "row",
    alignItems: "center",
    gap: Spacing.xs,
    marginHorizontal: Spacing.md,
    marginBottom: Spacing.sm,
    paddingHorizontal: Spacing.md,
    paddingVertical: Spacing.sm,
    backgroundColor: "rgba(255, 203, 5, 0.1)",
    borderRadius: BorderRadius.md,
  },
  syncingBannerText: {
    fontSize: Typography.small.fontSize,
    color: Colors.textMain,
  },
});
