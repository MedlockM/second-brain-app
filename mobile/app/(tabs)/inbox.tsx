import { View, Text, StyleSheet, FlatList, TouchableOpacity } from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";
import { Ionicons } from "@expo/vector-icons";
import { Colors, Typography, Spacing, BorderRadius, Shadows } from "../../src/constants/theme";
import { useInbox, InboxItem } from "../../src/contexts/InboxContext";

/**
 * Inbox screen - displays shared media items and their processing status.
 * Items are added via the iOS share extension flow.
 */
export default function InboxScreen() {
  const { items } = useInbox();

  return (
    <SafeAreaView style={styles.container} edges={["top"]}>
      <View style={styles.header}>
        <Text style={styles.title}>Inbox</Text>
      </View>

      {items.length === 0 ? (
        <View style={styles.emptyState}>
          <Ionicons
            name="share-outline"
            size={48}
            color={Colors.textMuted}
            style={styles.emptyIcon}
          />
          <Text style={styles.placeholder}>
            Your shared media will appear here.
          </Text>
          <Text style={styles.hint}>
            Share a link from any app to get started.
          </Text>
        </View>
      ) : (
        <FlatList
          data={items}
          keyExtractor={(item) => item.localId}
          renderItem={({ item }) => <InboxItemCard item={item} />}
          contentContainerStyle={styles.listContent}
          showsVerticalScrollIndicator={false}
        />
      )}
    </SafeAreaView>
  );
}

/**
 * Card component for a single inbox item showing URL and processing status.
 */
function InboxItemCard({ item }: { item: InboxItem }) {
  const statusConfig = getStatusConfig(item);

  return (
    <View style={styles.card}>
      <View style={styles.cardHeader}>
        <View style={styles.cardTitleRow}>
          <Text style={styles.cardUrl} numberOfLines={2}>
            {item.url}
          </Text>
          <View
            style={[styles.statusBadge, { backgroundColor: statusConfig.bgColor }]}
          >
            <Ionicons
              name={statusConfig.icon as any}
              size={12}
              color={statusConfig.color}
            />
            <Text style={[styles.statusText, { color: statusConfig.color }]}>
              {statusConfig.label}
            </Text>
          </View>
        </View>
        <Text style={styles.cardDomain}>{getDomainFromUrl(item.url)}</Text>
      </View>

      {/* Progress indicator for active items */}
      {(item.state === "submitting" || item.state === "submitted") &&
        item.processingStatus &&
        !isTerminalStatus(item.processingStatus) && (
          <View style={styles.progressBar}>
            <View
              style={[
                styles.progressFill,
                { width: `${getProgressPercentage(item.processingStatus)}%` },
              ]}
            />
          </View>
        )}

      {/* Error message */}
      {item.state === "failed" && item.errorMessage && (
        <Text style={styles.errorText}>{item.errorMessage}</Text>
      )}

      {/* Dedup indicator */}
      {item.deduplicated && (
        <Text style={styles.dedupText}>Already in your library</Text>
      )}

      <Text style={styles.cardTimestamp}>{formatRelativeTime(item.createdAt)}</Text>
    </View>
  );
}

function getDomainFromUrl(url: string): string {
  try {
    const parsed = new URL(url);
    return parsed.hostname.replace(/^www\./, "");
  } catch {
    return "";
  }
}

function isTerminalStatus(status: string): boolean {
  return status === "completed" || status === "failed" || status === "cancelled";
}

function getProgressPercentage(status: string): number {
  const progressMap: Record<string, number> = {
    pending: 10,
    classifying: 20,
    resolving: 30,
    downloading: 45,
    extracting: 60,
    transcribing: 75,
    ready_for_artifacts: 90,
    completed: 100,
  };
  return progressMap[status] ?? 0;
}

interface StatusConfig {
  label: string;
  icon: string;
  color: string;
  bgColor: string;
}

function getStatusConfig(item: InboxItem): StatusConfig {
  switch (item.state) {
    case "pending":
      return {
        label: "Pending",
        icon: "time-outline",
        color: Colors.textMuted,
        bgColor: Colors.surfaceContainerHigh,
      };
    case "submitting":
      return {
        label: "Saving",
        icon: "cloud-upload-outline",
        color: "#6366f1",
        bgColor: "#eef2ff",
      };
    case "submitted":
      if (item.processingStatus === "completed") {
        return {
          label: "Ready",
          icon: "checkmark-circle-outline",
          color: "#16a34a",
          bgColor: "#f0fdf4",
        };
      }
      if (item.processingStatus === "failed") {
        return {
          label: "Failed",
          icon: "alert-circle-outline",
          color: Colors.error,
          bgColor: Colors.errorContainer,
        };
      }
      return {
        label: "Processing",
        icon: "sync-outline",
        color: "#6366f1",
        bgColor: "#eef2ff",
      };
    case "failed":
      return {
        label: "Error",
        icon: "alert-circle-outline",
        color: Colors.error,
        bgColor: Colors.errorContainer,
      };
    default:
      return {
        label: "Unknown",
        icon: "help-circle-outline",
        color: Colors.textMuted,
        bgColor: Colors.surfaceContainerHigh,
      };
  }
}

function formatRelativeTime(dateString: string): string {
  const date = new Date(dateString);
  const now = new Date();
  const diffMs = now.getTime() - date.getTime();
  const diffMins = Math.floor(diffMs / 60000);

  if (diffMins < 1) return "Just now";
  if (diffMins < 60) return `${diffMins}m ago`;
  const diffHours = Math.floor(diffMins / 60);
  if (diffHours < 24) return `${diffHours}h ago`;
  return date.toLocaleDateString();
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: Colors.background,
  },
  header: {
    paddingHorizontal: Spacing.lg,
    paddingVertical: Spacing.md,
  },
  title: {
    fontSize: Typography.display.fontSize,
    fontWeight: Typography.display.fontWeight,
    color: Colors.textMain,
    letterSpacing: Typography.display.letterSpacing,
  },
  emptyState: {
    flex: 1,
    justifyContent: "center",
    alignItems: "center",
    paddingHorizontal: Spacing.xl,
  },
  emptyIcon: {
    marginBottom: Spacing.md,
  },
  placeholder: {
    fontSize: Typography.headline.fontSize,
    fontWeight: Typography.headline.fontWeight,
    color: Colors.textMain,
    textAlign: "center",
  },
  hint: {
    fontSize: Typography.body.fontSize,
    color: Colors.textMuted,
    textAlign: "center",
    marginTop: Spacing.sm,
  },
  listContent: {
    paddingHorizontal: Spacing.lg,
    paddingBottom: Spacing.xl,
    gap: Spacing.sm,
  },
  card: {
    backgroundColor: Colors.surfaceContainerLow,
    borderRadius: BorderRadius.xl,
    padding: Spacing.md,
    ...Shadows.soft,
    borderWidth: StyleSheet.hairlineWidth,
    borderColor: Colors.outlineVariant,
  },
  cardHeader: {
    gap: Spacing.xs,
  },
  cardTitleRow: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "flex-start",
    gap: Spacing.sm,
  },
  cardUrl: {
    flex: 1,
    fontSize: Typography.body.fontSize,
    fontWeight: "500",
    color: Colors.textMain,
    lineHeight: 22,
  },
  cardDomain: {
    fontSize: Typography.small.fontSize,
    color: Colors.textMuted,
  },
  statusBadge: {
    flexDirection: "row",
    alignItems: "center",
    gap: 4,
    paddingHorizontal: Spacing.sm,
    paddingVertical: 3,
    borderRadius: BorderRadius.full,
  },
  statusText: {
    fontSize: 11,
    fontWeight: "600",
  },
  progressBar: {
    height: 3,
    backgroundColor: Colors.surfaceContainerHigh,
    borderRadius: BorderRadius.full,
    marginTop: Spacing.sm,
    overflow: "hidden",
  },
  progressFill: {
    height: "100%",
    backgroundColor: "#6366f1",
    borderRadius: BorderRadius.full,
  },
  errorText: {
    marginTop: Spacing.sm,
    fontSize: Typography.small.fontSize,
    color: Colors.error,
  },
  dedupText: {
    marginTop: Spacing.sm,
    fontSize: Typography.small.fontSize,
    color: Colors.textMuted,
    fontStyle: "italic",
  },
  cardTimestamp: {
    marginTop: Spacing.sm,
    fontSize: 11,
    color: Colors.textMuted,
  },
});
