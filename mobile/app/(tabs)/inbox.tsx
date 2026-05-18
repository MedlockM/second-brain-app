import React, { useCallback } from "react";
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
import { useRouter } from "expo-router";
import { useAuth } from "../../src/contexts/AuthContext";
import { useMediaPolling } from "../../src/hooks/useMediaPolling";
import { InboxItem } from "../../src/contexts/InboxContext";
import {
  Colors,
  Typography,
  Spacing,
  BorderRadius,
  Shadows,
} from "../../src/constants/theme";
import type {
  MediaStatusResponse,
  MediaType,
  ProcessingJobLifecycleStatus,
} from "../../src/types/media";

/**
 * Inbox screen - displays shared media items with processing states and polling.
 *
 * Layout follows the inbox_daily_digest_button_ux mockup:
 * - Greeting header
 * - Daily Digest button
 * - "Ready for Review" section with media item cards
 * - Processing items shown with status badges
 *
 * Features:
 * - Live polling (every 5s) for items in non-terminal states
 * - Pull-to-refresh
 * - Loading, error, and empty states
 * - Optimistic UI: shows locally-shared items before backend confirms
 */
export default function InboxScreen() {
  const { user } = useAuth();
  const router = useRouter();
  const {
    items,
    pendingLocalItems,
    isLoading,
    isRefreshing,
    error,
    refresh,
    retry,
  } = useMediaPolling();

  const greeting = getGreeting(user?.email?.split("@")[0]);

  const completedCount = items.filter(
    (item) => item.processing_job.status === "completed",
  ).length;

  const handleDigestPress = useCallback(() => {
    router.push("/(tabs)/digest");
  }, [router]);

  const handleItemPress = useCallback(
    (mediaItemId: string) => {
      // Navigate to media detail - route will be implemented in a future task
      // For now, just log for navigation readiness
    },
    [],
  );

  // Loading state
  if (isLoading) {
    return (
      <SafeAreaView style={styles.container} edges={["top"]}>
        <View style={styles.header}>
          <Text style={styles.greeting}>{greeting}</Text>
        </View>
        <View style={styles.centeredContainer}>
          <ActivityIndicator size="large" color={Colors.primary} />
          <Text style={styles.loadingText}>Loading your inbox...</Text>
        </View>
      </SafeAreaView>
    );
  }

  // Error state
  if (error && items.length === 0) {
    return (
      <SafeAreaView style={styles.container} edges={["top"]}>
        <View style={styles.header}>
          <Text style={styles.greeting}>{greeting}</Text>
        </View>
        <View style={styles.centeredContainer}>
          <Ionicons
            name="cloud-offline-outline"
            size={48}
            color={Colors.textMuted}
            style={styles.errorIcon}
          />
          <Text style={styles.errorTitle}>{error}</Text>
          <Pressable style={styles.retryButton} onPress={retry}>
            <Ionicons name="refresh" size={18} color={Colors.onPrimary} />
            <Text style={styles.retryButtonText}>Retry</Text>
          </Pressable>
        </View>
      </SafeAreaView>
    );
  }

  const hasItems = items.length > 0 || pendingLocalItems.length > 0;

  return (
    <SafeAreaView style={styles.container} edges={["top"]}>
      <FlatList
        data={items}
        keyExtractor={(item) => item.media_item.media_item_id}
        renderItem={({ item }) => (
          <MediaItemCard item={item} onPress={handleItemPress} />
        )}
        contentContainerStyle={styles.listContent}
        showsVerticalScrollIndicator={false}
        refreshControl={
          <RefreshControl
            refreshing={isRefreshing}
            onRefresh={refresh}
            tintColor={Colors.primary}
            colors={[Colors.primary]}
          />
        }
        ListHeaderComponent={
          <ListHeader
            greeting={greeting}
            completedCount={completedCount}
            onDigestPress={handleDigestPress}
            pendingLocalItems={pendingLocalItems}
            hasItems={hasItems}
          />
        }
        ListEmptyComponent={
          !hasItems ? <EmptyState /> : null
        }
      />
    </SafeAreaView>
  );
}

// --- Sub-components ---

interface ListHeaderProps {
  greeting: string;
  completedCount: number;
  onDigestPress: () => void;
  pendingLocalItems: InboxItem[];
  hasItems: boolean;
}

function ListHeader({
  greeting,
  completedCount,
  onDigestPress,
  pendingLocalItems,
  hasItems,
}: ListHeaderProps) {
  return (
    <View>
      {/* Greeting */}
      <View style={styles.header}>
        <Text style={styles.greeting}>{greeting}</Text>
      </View>

      {/* Daily Digest Button */}
      <Pressable
        style={({ pressed }) => [
          styles.digestButton,
          pressed && styles.digestButtonPressed,
        ]}
        onPress={onDigestPress}
      >
        <View style={styles.digestIconContainer}>
          <Ionicons name="book-outline" size={22} color={Colors.primary} />
        </View>
        <Text style={styles.digestButtonLabel}>Daily Digest</Text>
        <View style={styles.digestButtonRight}>
          {completedCount > 0 && (
            <Text style={styles.digestCount}>{completedCount}</Text>
          )}
          <Ionicons name="chevron-forward" size={20} color={Colors.primary} />
        </View>
      </Pressable>

      {/* Pending local items (optimistic) */}
      {pendingLocalItems.length > 0 && (
        <View style={styles.section}>
          <Text style={styles.sectionTitle}>SUBMITTING</Text>
          {pendingLocalItems.map((localItem) => (
            <PendingLocalItemCard key={localItem.localId} item={localItem} />
          ))}
        </View>
      )}

      {/* Section header for backend items */}
      {hasItems && (
        <View style={styles.sectionHeaderRow}>
          <Text style={styles.sectionTitle}>READY FOR REVIEW</Text>
        </View>
      )}
    </View>
  );
}

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

interface MediaItemCardProps {
  item: MediaStatusResponse;
  onPress: (mediaItemId: string) => void;
}

function MediaItemCard({ item, onPress }: MediaItemCardProps) {
  const { media_item, processing_job } = item;

  let displayDomain: string;
  try {
    const parsed = new URL(media_item.original_url);
    displayDomain = parsed.hostname.replace(/^www\./, "");
  } catch {
    displayDomain = media_item.original_url;
  }

  const mediaTypeLabel = getMediaTypeLabel(media_item.media_type);
  const mediaTypeBgColor = getMediaTypeBgColor(media_item.media_type);
  const timeAgo = getRelativeTime(media_item.created_at);
  const statusLabel = getStatusLabel(processing_job.status);
  const statusColor = getStatusColor(processing_job.status);
  const isProcessing = !isTerminal(processing_job.status);

  return (
    <Pressable
      style={({ pressed }) => [
        styles.card,
        pressed && styles.cardPressed,
      ]}
      onPress={() => onPress(media_item.media_item_id)}
    >
      <View style={styles.cardContent}>
        {/* Thumbnail placeholder */}
        <View style={styles.thumbnailContainer}>
          <Ionicons
            name={getMediaTypeIcon(media_item.media_type)}
            size={28}
            color={Colors.textMuted}
          />
        </View>

        {/* Text content */}
        <View style={styles.cardTextSection}>
          {/* Type badge + time */}
          <View style={styles.cardMeta}>
            <View
              style={[styles.typeBadge, { backgroundColor: mediaTypeBgColor }]}
            >
              <Text style={styles.typeBadgeText}>{mediaTypeLabel}</Text>
            </View>
            <Text style={styles.timeText}>{timeAgo}</Text>
          </View>

          {/* Title / URL */}
          <Text style={styles.cardTitle} numberOfLines={2}>
            {media_item.original_url}
          </Text>

          {/* Source domain */}
          <Text style={styles.cardDomain}>{displayDomain}</Text>
        </View>
      </View>

      {/* Processing status indicator */}
      {isProcessing && (
        <View style={styles.cardFooter}>
          <View style={[styles.statusBadge, { backgroundColor: statusColor }]}>
            {isProcessing && (
              <ActivityIndicator
                size={10}
                color={Colors.textMain}
                style={styles.statusSpinner}
              />
            )}
            <Text style={styles.statusText}>{statusLabel}</Text>
          </View>
        </View>
      )}
    </Pressable>
  );
}

interface PendingLocalItemCardProps {
  item: InboxItem;
}

function PendingLocalItemCard({ item }: PendingLocalItemCardProps) {
  let displayDomain: string;
  try {
    const parsed = new URL(item.url);
    displayDomain = parsed.hostname.replace(/^www\./, "");
  } catch {
    displayDomain = item.url;
  }

  const isFailed = item.state === "failed";

  return (
    <View style={[styles.card, isFailed && styles.cardFailed]}>
      <View style={styles.cardContent}>
        <View style={styles.thumbnailContainer}>
          {isFailed ? (
            <Ionicons name="alert-circle" size={28} color={Colors.error} />
          ) : (
            <ActivityIndicator size={20} color={Colors.primary} />
          )}
        </View>
        <View style={styles.cardTextSection}>
          <Text style={styles.cardTitle} numberOfLines={2}>
            {item.url}
          </Text>
          <Text style={styles.cardDomain}>{displayDomain}</Text>
          {isFailed && item.errorMessage && (
            <Text style={styles.errorMessage}>{item.errorMessage}</Text>
          )}
        </View>
      </View>
      <View style={styles.cardFooter}>
        <View
          style={[
            styles.statusBadge,
            {
              backgroundColor: isFailed
                ? Colors.errorContainer
                : Colors.surfaceContainerHigh,
            },
          ]}
        >
          <Text style={styles.statusText}>
            {isFailed ? "Failed" : "Submitting..."}
          </Text>
        </View>
      </View>
    </View>
  );
}

// --- Helper functions ---

function getGreeting(name?: string | null): string {
  const hour = new Date().getHours();
  let timeOfDay: string;
  if (hour < 12) {
    timeOfDay = "Morning";
  } else if (hour < 18) {
    timeOfDay = "Afternoon";
  } else {
    timeOfDay = "Evening";
  }

  if (name) {
    return `Good ${timeOfDay}, ${name}`;
  }
  return `Good ${timeOfDay}`;
}

function getRelativeTime(isoDate: string): string {
  const now = Date.now();
  const date = new Date(isoDate).getTime();
  const diffMs = now - date;
  const diffMins = Math.floor(diffMs / 60000);
  const diffHours = Math.floor(diffMs / 3600000);
  const diffDays = Math.floor(diffMs / 86400000);

  if (diffMins < 1) return "Just now";
  if (diffMins < 60) return `${diffMins}m ago`;
  if (diffHours < 24) return `${diffHours}h ago`;
  if (diffDays === 1) return "Yesterday";
  if (diffDays < 7) return `${diffDays}d ago`;
  return new Date(isoDate).toLocaleDateString(undefined, {
    month: "short",
    day: "numeric",
  });
}

function getMediaTypeLabel(type: MediaType): string {
  switch (type) {
    case "podcast_episode":
      return "PODCAST";
    case "article":
      return "ARTICLE";
    case "youtube_video":
      return "VIDEO";
    case "short_video":
      return "SHORT";
    case "audio_file":
      return "AUDIO";
    case "shared_text":
      return "TEXT";
    default:
      return "LINK";
  }
}

function getMediaTypeBgColor(type: MediaType): string {
  switch (type) {
    case "podcast_episode":
      return Colors.primary;
    case "youtube_video":
    case "short_video":
      return "#ffe0e0";
    case "article":
      return Colors.surfaceContainerHigh;
    default:
      return Colors.surfaceContainerHigh;
  }
}

function getMediaTypeIcon(
  type: MediaType,
): React.ComponentProps<typeof Ionicons>["name"] {
  switch (type) {
    case "podcast_episode":
      return "headset-outline";
    case "article":
      return "document-text-outline";
    case "youtube_video":
    case "short_video":
      return "play-circle-outline";
    case "audio_file":
      return "musical-notes-outline";
    case "shared_text":
      return "text-outline";
    default:
      return "link-outline";
  }
}

function getStatusLabel(status: ProcessingJobLifecycleStatus): string {
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
      return "Generating summary";
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

function getStatusColor(status: ProcessingJobLifecycleStatus): string {
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

function isTerminal(status: ProcessingJobLifecycleStatus): boolean {
  return (
    status === "completed" || status === "failed" || status === "cancelled"
  );
}

// --- Styles ---

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: Colors.background,
  },
  header: {
    paddingHorizontal: Spacing.lg,
    paddingTop: Spacing.md,
    paddingBottom: Spacing.sm,
  },
  greeting: {
    fontSize: 28,
    fontWeight: "700",
    color: Colors.textMain,
    letterSpacing: -0.5,
  },
  listContent: {
    paddingBottom: Spacing.xl,
  },
  centeredContainer: {
    flex: 1,
    justifyContent: "center",
    alignItems: "center",
    paddingHorizontal: Spacing.xl,
  },
  loadingText: {
    fontSize: Typography.body.fontSize,
    color: Colors.textMuted,
    marginTop: Spacing.md,
  },

  // Error state
  errorIcon: {
    marginBottom: Spacing.md,
  },
  errorTitle: {
    fontSize: Typography.body.fontSize,
    color: Colors.textMain,
    textAlign: "center",
    marginBottom: Spacing.lg,
    lineHeight: 24,
  },
  retryButton: {
    flexDirection: "row",
    alignItems: "center",
    gap: Spacing.sm,
    backgroundColor: Colors.primary,
    paddingHorizontal: Spacing.lg,
    paddingVertical: Spacing.sm + 4,
    borderRadius: BorderRadius.lg,
  },
  retryButtonText: {
    fontSize: Typography.label.fontSize,
    fontWeight: Typography.label.fontWeight,
    color: Colors.onPrimary,
  },

  // Daily Digest button
  digestButton: {
    flexDirection: "row",
    alignItems: "center",
    backgroundColor: Colors.surface,
    marginHorizontal: Spacing.md,
    marginTop: Spacing.md,
    marginBottom: Spacing.lg,
    padding: Spacing.md + 4,
    borderRadius: BorderRadius.xl,
    borderWidth: StyleSheet.hairlineWidth,
    borderColor: Colors.outlineVariant,
    ...Shadows.soft,
  },
  digestButtonPressed: {
    transform: [{ scale: 0.98 }],
    opacity: 0.9,
  },
  digestIconContainer: {
    width: 40,
    height: 40,
    borderRadius: BorderRadius.lg,
    backgroundColor: "rgba(255, 203, 5, 0.1)",
    alignItems: "center",
    justifyContent: "center",
  },
  digestButtonLabel: {
    flex: 1,
    fontSize: Typography.body.fontSize,
    fontWeight: "700",
    color: Colors.textMain,
    marginLeft: Spacing.md,
  },
  digestButtonRight: {
    flexDirection: "row",
    alignItems: "center",
    gap: Spacing.sm,
  },
  digestCount: {
    fontSize: Typography.body.fontSize,
    fontWeight: Typography.label.fontWeight,
    color: Colors.textMuted,
  },

  // Section
  section: {
    paddingHorizontal: Spacing.md,
    marginBottom: Spacing.md,
    gap: Spacing.sm,
  },
  sectionHeaderRow: {
    paddingHorizontal: Spacing.lg,
    paddingTop: Spacing.sm,
    paddingBottom: Spacing.md,
  },
  sectionTitle: {
    fontSize: Typography.small.fontSize,
    fontWeight: "700",
    color: Colors.textMuted,
    letterSpacing: 0.8,
  },

  // Card
  card: {
    backgroundColor: Colors.surface,
    borderRadius: BorderRadius.xl,
    padding: Spacing.sm + 4,
    marginHorizontal: Spacing.md,
    marginBottom: Spacing.md,
    ...Shadows.soft,
  },
  cardPressed: {
    transform: [{ scale: 0.98 }],
    opacity: 0.9,
  },
  cardFailed: {
    borderWidth: 1,
    borderColor: Colors.errorContainer,
  },
  cardContent: {
    flexDirection: "row",
    alignItems: "center",
    gap: Spacing.md,
  },
  thumbnailContainer: {
    width: 72,
    height: 72,
    borderRadius: BorderRadius.lg,
    backgroundColor: Colors.surfaceContainerLow,
    alignItems: "center",
    justifyContent: "center",
  },
  cardTextSection: {
    flex: 1,
    paddingVertical: Spacing.xs,
    gap: 2,
  },
  cardMeta: {
    flexDirection: "row",
    alignItems: "center",
    gap: Spacing.sm,
    marginBottom: Spacing.xs,
  },
  typeBadge: {
    paddingHorizontal: Spacing.sm,
    paddingVertical: 2,
    borderRadius: BorderRadius.md,
  },
  typeBadgeText: {
    fontSize: 11,
    fontWeight: "700",
    color: Colors.textMain,
    letterSpacing: 0.5,
  },
  timeText: {
    fontSize: 11,
    color: Colors.textMuted,
  },
  cardTitle: {
    fontSize: Typography.body.fontSize,
    fontWeight: "700",
    color: Colors.textMain,
    lineHeight: 22,
  },
  cardDomain: {
    fontSize: Typography.small.fontSize,
    color: Colors.textMuted,
  },
  errorMessage: {
    fontSize: Typography.small.fontSize,
    color: Colors.error,
    marginTop: Spacing.xs,
  },

  // Card footer (processing status)
  cardFooter: {
    flexDirection: "row",
    alignItems: "center",
    gap: Spacing.sm,
    marginTop: Spacing.sm,
    paddingTop: Spacing.sm,
    borderTopWidth: StyleSheet.hairlineWidth,
    borderTopColor: Colors.outlineVariant,
  },
  statusBadge: {
    flexDirection: "row",
    alignItems: "center",
    paddingHorizontal: Spacing.sm,
    paddingVertical: 3,
    borderRadius: BorderRadius.sm,
    gap: Spacing.xs,
  },
  statusSpinner: {
    marginRight: 2,
  },
  statusText: {
    fontSize: Typography.small.fontSize,
    fontWeight: Typography.label.fontWeight,
    color: Colors.textMain,
  },

  // Empty state
  emptyContainer: {
    paddingTop: 100,
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
});
