import { useState, useEffect, useCallback } from "react";
import {
  View,
  Text,
  StyleSheet,
  FlatList,
  ActivityIndicator,
  Pressable,
  RefreshControl,
} from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";
import { Ionicons } from "@expo/vector-icons";
import { useAuth } from "../../src/contexts/AuthContext";
import { useShareIntake } from "../../src/contexts/ShareIntentContext";
import {
  Colors,
  Typography,
  Spacing,
  BorderRadius,
  Shadows,
} from "../../src/constants/theme";
import type { IngestUrlResponse } from "../../src/types/media";

/**
 * Inbox screen - shows shared media items from both Android share intent
 * and iOS share extension flows.
 * Displays recently shared URLs and their processing status.
 * Acts as the destination for items saved via the share intent flow.
 */
export default function InboxScreen() {
  const { intake } = useShareIntake();
  const [recentItems, setRecentItems] = useState<IngestUrlResponse[]>([]);

  // When a URL is successfully saved, add it to the top of the local list
  useEffect(() => {
    if (intake.status === "success" && intake.response) {
      setRecentItems((prev) => {
        // Avoid duplicates
        const exists = prev.some(
          (item) =>
            item.media_item.media_item_id ===
            intake.response!.media_item.media_item_id,
        );
        if (exists) return prev;
        return [intake.response!, ...prev];
      });
    }
  }, [intake.status, intake.response]);

  return (
    <SafeAreaView style={styles.container} edges={["top"]}>
      <View style={styles.header}>
        <Text style={styles.title}>Inbox</Text>
      </View>

      {recentItems.length === 0 ? (
        <EmptyState />
      ) : (
        <FlatList
          data={recentItems}
          keyExtractor={(item) => item.media_item.media_item_id}
          renderItem={({ item }) => <InboxItemCard item={item} />}
          contentContainerStyle={styles.listContent}
          showsVerticalScrollIndicator={false}
        />
      )}
    </SafeAreaView>
  );
}

/**
 * Empty state when no items have been shared yet.
 */
function EmptyState() {
  return (
    <View style={styles.emptyContainer}>
      <Ionicons
        name="share-outline"
        size={48}
        color={Colors.textMuted}
        style={styles.emptyIcon}
      />
      <Text style={styles.emptyTitle}>Your shared media will appear here.</Text>
      <Text style={styles.emptyHint}>
        Share a link from any app to get started.
      </Text>
    </View>
  );
}

/**
 * Card component for an inbox item.
 */
function InboxItemCard({ item }: { item: IngestUrlResponse }) {
  const { media_item, processing_job, deduplicated } = item;

  let displayDomain: string;
  try {
    const parsed = new URL(media_item.original_url);
    displayDomain = parsed.hostname.replace(/^www\./, "");
  } catch {
    displayDomain = media_item.original_url;
  }

  const statusLabel = getStatusLabel(processing_job.status);
  const statusColor = getStatusColor(processing_job.status);

  return (
    <View style={styles.card}>
      <View style={styles.cardContent}>
        <View style={styles.cardTextSection}>
          <Text style={styles.cardUrl} numberOfLines={2}>
            {media_item.original_url}
          </Text>
          <Text style={styles.cardDomain}>{displayDomain}</Text>
        </View>
        <View style={styles.cardIconContainer}>
          <Ionicons name="link" size={20} color={Colors.textMuted} />
        </View>
      </View>

      <View style={styles.cardFooter}>
        <View style={[styles.statusBadge, { backgroundColor: statusColor }]}>
          <Text style={styles.statusText}>{statusLabel}</Text>
        </View>
        {deduplicated && (
          <Text style={styles.deduplicatedText}>Already in library</Text>
        )}
      </View>
    </View>
  );
}

function getStatusLabel(status: string): string {
  switch (status) {
    case "pending":
      return "Pending";
    case "classifying":
      return "Classifying";
    case "resolving":
      return "Resolving";
    case "downloading":
      return "Downloading";
    case "extracting":
      return "Extracting";
    case "transcribing":
      return "Transcribing";
    case "ready_for_artifacts":
      return "Ready";
    case "completed":
      return "Done";
    case "failed":
      return "Failed";
    case "cancelled":
      return "Cancelled";
    default:
      return "Processing";
  }
}

function getStatusColor(status: string): string {
  switch (status) {
    case "completed":
    case "ready_for_artifacts":
      return "#e8f5e9";
    case "failed":
    case "cancelled":
      return Colors.errorContainer;
    default:
      return Colors.surfaceContainerHigh;
  }
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
  listContent: {
    paddingHorizontal: Spacing.lg,
    paddingBottom: Spacing.xl,
    gap: Spacing.md,
  },
  // Empty state
  emptyContainer: {
    flex: 1,
    justifyContent: "center",
    alignItems: "center",
    paddingHorizontal: Spacing.xl,
  },
  emptyIcon: {
    marginBottom: Spacing.md,
  },
  emptyTitle: {
    fontSize: Typography.headline.fontSize,
    fontWeight: Typography.headline.fontWeight,
    color: Colors.textMain,
    textAlign: "center",
  },
  emptyHint: {
    fontSize: Typography.body.fontSize,
    color: Colors.textMuted,
    textAlign: "center",
    marginTop: Spacing.sm,
  },
  // Card
  card: {
    backgroundColor: Colors.surfaceContainerLow,
    borderRadius: BorderRadius.xl,
    padding: Spacing.md,
    borderWidth: StyleSheet.hairlineWidth,
    borderColor: Colors.outlineVariant,
    ...Shadows.soft,
  },
  cardContent: {
    flexDirection: "row",
    gap: Spacing.md,
  },
  cardTextSection: {
    flex: 1,
    gap: Spacing.xs,
  },
  cardUrl: {
    fontSize: Typography.body.fontSize,
    fontWeight: "500",
    color: Colors.textMain,
    lineHeight: 22,
  },
  cardDomain: {
    fontSize: Typography.small.fontSize,
    color: Colors.textMuted,
  },
  cardIconContainer: {
    width: 36,
    height: 36,
    borderRadius: BorderRadius.md,
    backgroundColor: Colors.surfaceContainerHigh,
    alignItems: "center",
    justifyContent: "center",
  },
  cardFooter: {
    flexDirection: "row",
    alignItems: "center",
    gap: Spacing.sm,
    marginTop: Spacing.md,
    paddingTop: Spacing.sm,
    borderTopWidth: StyleSheet.hairlineWidth,
    borderTopColor: Colors.outlineVariant,
  },
  statusBadge: {
    paddingHorizontal: Spacing.sm,
    paddingVertical: 2,
    borderRadius: BorderRadius.sm,
  },
  statusText: {
    fontSize: Typography.small.fontSize,
    fontWeight: Typography.label.fontWeight,
    color: Colors.textMain,
  },
  deduplicatedText: {
    fontSize: Typography.small.fontSize,
    color: Colors.textMuted,
    fontStyle: "italic",
  },
});
