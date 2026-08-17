import React, { useCallback, useState } from "react";
import {
  View,
  Text,
  StyleSheet,
  FlatList,
  ActivityIndicator,
  Alert,
  Pressable,
  RefreshControl,
} from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";
import { Ionicons } from "@expo/vector-icons";
import { useRouter } from "expo-router";
import { useFocusEffect } from "expo-router";
import { useAuth } from "../../src/contexts/AuthContext";
import { useShareIntake } from "../../src/contexts/ShareIntentContext";
import { useMediaPolling } from "../../src/hooks/useMediaPolling";
import { InboxItem } from "../../src/contexts/InboxContext";
import { AddSourceSheet } from "../../src/components/AddSourceSheet";
import {
  capturePhotoToImport,
  pickFileToImport,
  pickPhotoFromLibrary,
  type LocalImportResult,
} from "../../src/lib/localImport";
import {
  Colors,
  Typography,
  Spacing,
  BorderRadius,
  Shadows,
  TouchTarget,
} from "../../src/constants/theme";
import type {
  MediaListItem,
  MediaType,
  SourcePlatform,
} from "../../src/types/media";
import { getMediaTypeIcon } from "../../src/lib/mediaTypeDisplay";
import { getRelativeTime } from "../../src/lib/relativeTime";

/**
 * Inbox screen - displays shared media items as uniform vignettes.
 *
 * V1 design decisions:
 * - No polling: single fetch on mount + pull-to-refresh + refetch on focus
 * - No processing status badges or spinners per item
 * - Optimistic insertion: pending local items appear instantly as placeholders
 * - Tapping an item navigates to detail (which handles its own "Generating text..." state)
 *
 * Also hosts the ingestion gestures (task-264): a camera button that shoots
 * straight away, and an "add" button opening the choice between a file and a
 * gallery photo. All three hand the result to the share confirmation screen,
 * where the collection and tags are picked before sending.
 */
export default function InboxScreen() {
  const { user } = useAuth();
  const router = useRouter();
  const { startLocalUpload } = useShareIntake();
  const [isSourceSheetVisible, setSourceSheetVisible] = useState(false);
  const {
    items,
    pendingLocalItems,
    isLoading,
    isRefreshing,
    error,
    refresh,
    refetch,
    retry,
  } = useMediaPolling();

  const greeting = getGreeting(user?.email?.split("@")[0]);

  // Silent refetch when the screen gains focus (multi-device sync). Uses the
  // non-spinner variant so we don't show the pull-to-refresh indicator just
  // because the user navigated back to this tab.
  useFocusEffect(
    useCallback(() => {
      refetch();
    }, [refetch]),
  );

  const handleDigestPress = useCallback(() => {
    router.push("/(tabs)/digest");
  }, [router]);

  const handleItemPress = useCallback(
    (mediaItemId: string) => {
      router.push(`/media/${mediaItemId}`);
    },
    [router],
  );

  /**
   * Route a picking outcome: a refusal (unsupported format, oversized file,
   * camera permission denied) is stated plainly and the screen stays as it was;
   * an accepted file opens the confirmation screen.
   */
  const handleImportResult = useCallback(
    (result: LocalImportResult, contentType: "file" | "photo") => {
      if (result.status === "cancelled") return;
      if (result.status === "error") {
        Alert.alert(result.title, result.message);
        return;
      }
      startLocalUpload(result.file, contentType);
    },
    [startLocalUpload],
  );

  // Both are fired by the sheet once it has finished closing, so the system
  // picker never has to present itself over a modal on its way out.
  const handleImportFile = useCallback(async () => {
    handleImportResult(await pickFileToImport(), "file");
  }, [handleImportResult]);

  const handleImportPhoto = useCallback(async () => {
    handleImportResult(await pickPhotoFromLibrary(), "photo");
  }, [handleImportResult]);

  const handleTakePhoto = useCallback(async () => {
    handleImportResult(await capturePhotoToImport(), "photo");
  }, [handleImportResult]);

  // Build a unified list: pending local items first, then backend items
  const unifiedItems: UnifiedItem[] = [
    ...pendingLocalItems.map(
      (local): UnifiedItem => ({
        kind: "local",
        key: local.localId,
        local,
      }),
    ),
    ...items.map(
      (backend): UnifiedItem => ({
        kind: "backend",
        key: backend.media_item_id,
        backend,
      }),
    ),
  ];

  // Loading state
  if (isLoading) {
    return (
      <SafeAreaView testID="inbox-screen" style={styles.container} edges={["top"]}>
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
      <SafeAreaView testID="inbox-screen" style={styles.container} edges={["top"]}>
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
          <Pressable
            style={styles.retryButton}
            onPress={retry}
            accessibilityLabel="Retry loading inbox"
            accessibilityRole="button"
          >
            <Ionicons name="refresh" size={18} color={Colors.onPrimary} />
            <Text style={styles.retryButtonText}>Retry</Text>
          </Pressable>
        </View>
      </SafeAreaView>
    );
  }

  const hasItems = unifiedItems.length > 0;

  return (
    <SafeAreaView testID="inbox-screen" style={styles.container} edges={["top"]}>
      <FlatList
        data={unifiedItems}
        keyExtractor={(item) => item.key}
        renderItem={({ item }) => (
          <UnifiedItemCard item={item} onPress={handleItemPress} />
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
            onDigestPress={handleDigestPress}
            hasItems={hasItems}
          />
        }
        ListEmptyComponent={!hasItems ? <EmptyState /> : null}
      />

      {/* box-none: the row now spans the full width, so without this it would
          swallow taps on the list items sitting behind it. */}
      <View style={styles.fabStack} pointerEvents="box-none">
        <Pressable
          testID="inbox-camera-button"
          style={({ pressed }) => [
            styles.cameraButton,
            pressed && styles.addButtonPressed,
          ]}
          onPress={handleTakePhoto}
          accessibilityLabel="Take a photo"
          accessibilityRole="button"
        >
          <Ionicons name="camera" size={24} color={Colors.surface} />
        </Pressable>

        <Pressable
          testID="inbox-add-button"
          style={({ pressed }) => [styles.addButton, pressed && styles.addButtonPressed]}
          onPress={() => setSourceSheetVisible(true)}
          accessibilityLabel="Add to your inbox"
          accessibilityRole="button"
        >
          <Ionicons name="add" size={28} color={Colors.onPrimary} />
        </Pressable>
      </View>

      <AddSourceSheet
        visible={isSourceSheetVisible}
        onClose={() => setSourceSheetVisible(false)}
        onImportFile={handleImportFile}
        onImportPhoto={handleImportPhoto}
      />
    </SafeAreaView>
  );
}

// --- Types ---

interface UnifiedItem {
  kind: "local" | "backend";
  key: string;
  local?: InboxItem;
  backend?: MediaListItem;
}

// --- Sub-components ---

interface ListHeaderProps {
  greeting: string;
  onDigestPress: () => void;
  hasItems: boolean;
}

function ListHeader({ greeting, onDigestPress, hasItems }: ListHeaderProps) {
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
        accessibilityLabel="Open Daily Digest"
        accessibilityRole="button"
      >
        <View style={styles.digestIconContainer}>
          <Ionicons name="book-outline" size={22} color={Colors.primary} />
        </View>
        <Text style={styles.digestButtonLabel}>Daily Digest</Text>
        <View style={styles.digestButtonRight}>
          <Ionicons name="chevron-forward" size={20} color={Colors.primary} />
        </View>
      </Pressable>

      {/* Section header */}
      {hasItems && (
        <View style={styles.sectionHeaderRow}>
          <Text style={styles.sectionTitle}>YOUR MEDIA</Text>
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
        Share a link from any app, or tap + to import a file or take a photo.
      </Text>
    </View>
  );
}

// --- Unified Item Card ---

interface UnifiedItemCardProps {
  item: UnifiedItem;
  onPress: (mediaItemId: string) => void;
}

function UnifiedItemCard({ item, onPress }: UnifiedItemCardProps) {
  if (item.kind === "local" && item.local) {
    return <LocalItemCard item={item.local} />;
  }
  if (item.kind === "backend" && item.backend) {
    return <BackendItemCard item={item.backend} onPress={onPress} />;
  }
  return null;
}

// --- Backend Item Card (no status badge) ---

interface BackendItemCardProps {
  item: MediaListItem;
  onPress: (mediaItemId: string) => void;
}

function BackendItemCard({ item, onPress }: BackendItemCardProps) {
  const sourceUrl = item.source_url ?? "";

  let displayDomain: string;
  try {
    displayDomain = new URL(sourceUrl).hostname.replace(/^www\./, "");
  } catch {
    displayDomain = sourceUrl;
  }

  const mediaType = (item.media_type ?? "unknown") as MediaType;
  const mediaTypeLabel = getMediaTypeLabel(mediaType);
  const mediaTypeBgColor = getMediaTypeBgColor(mediaType);
  const timeAgo = getRelativeTime(item.created_at);
  const icon = getMediaTypeIcon(mediaType);

  // The stored title, as-is: it is derived server-side and never empty
  // (task-266). The URL fallback that used to live here duplicated the domain
  // line rendered right below the title.
  const displayTitle = item.title;

  return (
    <Pressable
      style={({ pressed }) => [styles.card, pressed && styles.cardPressed]}
      onPress={() => onPress(item.media_item_id)}
      accessibilityLabel={`${mediaTypeLabel} from ${displayDomain}`}
      accessibilityRole="button"
    >
      <View style={styles.cardContent}>
        {/* Thumbnail placeholder */}
        <View style={styles.thumbnailContainer}>
          <Ionicons name={icon} size={28} color={Colors.textMuted} />
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
            {displayTitle}
          </Text>

          {/* Source domain */}
          <Text style={styles.cardDomain}>{displayDomain}</Text>
        </View>
      </View>
    </Pressable>
  );
}

// --- Local (optimistic) Item Card ---

interface LocalItemCardProps {
  item: InboxItem;
}

function LocalItemCard({ item }: LocalItemCardProps) {
  let displayDomain: string;
  try {
    const parsed = new URL(item.url);
    displayDomain = parsed.hostname.replace(/^www\./, "");
  } catch {
    displayDomain = item.url;
  }

  const isFailed = item.state === "failed";
  const icon = getSourcePlatformIcon(item.sourcePlatform);

  return (
    <View
      style={[styles.card, isFailed && styles.cardFailed]}
      accessibilityLabel={`Pending link from ${displayDomain}`}
    >
      <View style={styles.cardContent}>
        <View style={styles.thumbnailContainer}>
          {isFailed ? (
            <Ionicons name="alert-circle" size={28} color={Colors.error} />
          ) : (
            <Ionicons name={icon} size={28} color={Colors.textMuted} />
          )}
        </View>
        <View style={styles.cardTextSection}>
          {/* Title = URL */}
          <Text style={styles.cardTitle} numberOfLines={2}>
            {item.url}
          </Text>
          <Text style={styles.cardDomain}>{displayDomain}</Text>
          {isFailed && item.errorMessage && (
            <Text style={styles.errorMessage}>{item.errorMessage}</Text>
          )}
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
    case "audio":
      return "AUDIO";
    case "shared_text":
      return "TEXT";
    case "document":
      return "DOC";
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
      return Colors.errorContainer;
    case "article":
      return Colors.surfaceContainerHigh;
    default:
      return Colors.surfaceContainerHigh;
  }
}


function getSourcePlatformIcon(
  platform?: SourcePlatform,
): React.ComponentProps<typeof Ionicons>["name"] {
  switch (platform) {
    case "spotify":
    case "apple_podcasts":
    case "deezer":
    case "rss":
    case "podcast_index":
      return "headset-outline";
    case "youtube":
      return "play-circle-outline";
    case "instagram":
    case "tiktok":
      return "videocam-outline";
    case "x":
      return "chatbubble-outline";
    default:
      return "link-outline";
  }
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
    ...Typography.display,
    fontSize: 28,
    color: Colors.textMain,
  },
  listContent: {
    // Room for the floating add button so it never covers the last card.
    paddingBottom: TouchTarget.large + Spacing.xl,
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
    minHeight: TouchTarget.minimum,
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
    minHeight: TouchTarget.comfortable,
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

  // Section
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
    minHeight: TouchTarget.comfortable,
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

  // Add button (floating): the entry point for a file import or a photo.
  // The two ingestion controls sit side by side, centred over the list, with the
  // primary one on the right. Both are opaque and carry a filled colour rather
  // than an outline: the background is a pale cream, so a white or near-white
  // button would read as a shadow rather than a control.
  fabStack: {
    position: "absolute",
    left: 0,
    right: 0,
    bottom: Spacing.lg,
    flexDirection: "row",
    justifyContent: "center",
    alignItems: "center",
    gap: Spacing.md,
  },
  addButton: {
    width: TouchTarget.large,
    height: TouchTarget.large,
    borderRadius: BorderRadius.full,
    backgroundColor: Colors.primary,
    alignItems: "center",
    justifyContent: "center",
    ...Shadows.soft,
  },
  cameraButton: {
    width: TouchTarget.large,
    height: TouchTarget.large,
    borderRadius: BorderRadius.full,
    backgroundColor: Colors.textMain,
    alignItems: "center",
    justifyContent: "center",
    ...Shadows.soft,
  },
  addButtonPressed: {
    transform: [{ scale: 0.96 }],
    opacity: 0.9,
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
