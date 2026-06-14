import { useCallback, useMemo, useState } from "react";
import {
  View,
  Text,
  StyleSheet,
  FlatList,
  ActivityIndicator,
  Pressable,
} from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";
import { Ionicons } from "@expo/vector-icons";
import { useRouter, useLocalSearchParams, useFocusEffect } from "expo-router";
import { useAuth } from "../../../src/contexts/AuthContext";
import { OrganizationService } from "../../../src/services/organizationService";
import { MediaListCard } from "../../../src/components/MediaListCard";
import { getFriendlyErrorMessage } from "../../../src/lib/getFriendlyErrorMessage";
import {
  buildCollectionTree,
  type CollectionNode,
} from "../../../src/lib/collectionTree";
import {
  Colors,
  Typography,
  Spacing,
  BorderRadius,
  Shadows,
  TouchTarget,
} from "../../../src/constants/theme";
import type { MediaListItem } from "../../../src/types/media";

/**
 * Collections explorer — single collection view.
 *
 * Renders the sub-collections (folders) of the opened collection, followed by
 * the media stored directly inside it. Sub-folders drill deeper into the same
 * screen; media rows open the shared media detail (AC#3, AC#4).
 *
 * Handles loading / error / empty states (AC#5).
 */

interface FolderListRow {
  kind: "folder";
  node: CollectionNode;
}

interface MediaListRow {
  kind: "media";
  media: MediaListItem;
}

type Row = FolderListRow | MediaListRow;

export default function CollectionDetailScreen() {
  const router = useRouter();
  const { token } = useAuth();
  const params = useLocalSearchParams<{ id: string; name?: string }>();
  const collectionId = params.id;

  const [childFolders, setChildFolders] = useState<CollectionNode[]>([]);
  const [media, setMedia] = useState<MediaListItem[]>([]);
  const [title, setTitle] = useState<string>(params.name ?? "Collection");
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    if (!token || !collectionId) return;
    setError(null);
    try {
      const [collections, folderMedia] = await Promise.all([
        OrganizationService.getUserCollections(token),
        OrganizationService.getCollectionMedia(token, collectionId),
      ]);

      // Direct children = collections whose parent is this collection.
      const { nodeById } = buildCollectionTree(collections);
      const current = nodeById.get(collectionId);
      if (current) {
        setTitle(current.name);
        setChildFolders(
          [...current.children].sort((a, b) => a.name.localeCompare(b.name)),
        );
      } else {
        setChildFolders([]);
      }

      // The backend folder filter includes descendants; keep only the media
      // stored directly in this collection so sub-folders own their own items.
      setMedia(
        folderMedia.filter((item) => item.folder_id === collectionId),
      );
    } catch (err) {
      setError(
        getFriendlyErrorMessage(err, {
          fallback: "Unable to load this collection. Please try again.",
        }),
      );
    }
  }, [token, collectionId]);

  useFocusEffect(
    useCallback(() => {
      let active = true;
      setIsLoading(true);
      load().finally(() => {
        if (active) setIsLoading(false);
      });
      return () => {
        active = false;
      };
    }, [load]),
  );

  const handleBack = useCallback(() => {
    if (router.canGoBack()) router.back();
  }, [router]);

  const handleOpenFolder = useCallback(
    (node: CollectionNode) => {
      router.push({
        pathname: "/media/collections/[id]",
        params: { id: node.id, name: node.name },
      });
    },
    [router],
  );

  const handleOpenMedia = useCallback(
    (mediaItemId: string) => {
      router.push(`/media/${mediaItemId}`);
    },
    [router],
  );

  const handleRetry = useCallback(() => {
    setIsLoading(true);
    load().finally(() => setIsLoading(false));
  }, [load]);

  const rows = useMemo<Row[]>(() => {
    return [
      ...childFolders.map((node): Row => ({ kind: "folder", node })),
      ...media.map((m): Row => ({ kind: "media", media: m })),
    ];
  }, [childFolders, media]);

  return (
    <SafeAreaView style={styles.container} edges={["top", "bottom"]}>
      <View style={styles.header}>
        <Pressable
          style={styles.backButton}
          onPress={handleBack}
          accessibilityLabel="Go back"
          accessibilityRole="button"
        >
          <Ionicons name="arrow-back" size={22} color={Colors.textMain} />
        </Pressable>
        <Text style={styles.headerTitle} numberOfLines={1}>
          {title}
        </Text>
        <View style={styles.headerSpacer} />
      </View>

      {isLoading ? (
        <View style={styles.centered}>
          <ActivityIndicator size="large" color={Colors.primary} />
          <Text style={styles.centeredText}>Loading...</Text>
        </View>
      ) : error ? (
        <View style={styles.centered}>
          <Ionicons
            name="cloud-offline-outline"
            size={48}
            color={Colors.textMuted}
            style={styles.centeredIcon}
          />
          <Text style={styles.centeredTitle}>{error}</Text>
          <Pressable
            style={styles.retryButton}
            onPress={handleRetry}
            accessibilityLabel="Retry loading collection"
            accessibilityRole="button"
          >
            <Ionicons name="refresh" size={18} color={Colors.onPrimary} />
            <Text style={styles.retryButtonText}>Retry</Text>
          </Pressable>
        </View>
      ) : (
        <FlatList
          data={rows}
          keyExtractor={(row) =>
            row.kind === "folder" ? `folder:${row.node.id}` : `media:${row.media.media_item_id}`
          }
          renderItem={({ item }) =>
            item.kind === "folder" ? (
              <FolderRow node={item.node} onPress={handleOpenFolder} />
            ) : (
              <MediaListCard item={item.media} onPress={handleOpenMedia} />
            )
          }
          contentContainerStyle={styles.listContent}
          showsVerticalScrollIndicator={false}
          ListEmptyComponent={<EmptyState />}
        />
      )}
    </SafeAreaView>
  );
}

// --- Sub-components ---

interface FolderRowProps {
  node: CollectionNode;
  onPress: (node: CollectionNode) => void;
}

function FolderRow({ node, onPress }: FolderRowProps) {
  const childCount = node.children.length;
  const subtitle =
    childCount > 0
      ? `${childCount} ${childCount === 1 ? "collection" : "collections"}`
      : "Collection";

  return (
    <Pressable
      style={({ pressed }) => [styles.folderCard, pressed && styles.folderCardPressed]}
      onPress={() => onPress(node)}
      accessibilityLabel={`Open collection ${node.name}`}
      accessibilityRole="button"
    >
      <View style={styles.folderIconContainer}>
        <Ionicons name="folder" size={24} color={Colors.primary} />
      </View>
      <View style={styles.folderTextSection}>
        <Text style={styles.folderName} numberOfLines={1}>
          {node.name}
        </Text>
        <Text style={styles.folderSubtitle}>{subtitle}</Text>
      </View>
      <Ionicons name="chevron-forward" size={20} color={Colors.textMuted} />
    </Pressable>
  );
}

function EmptyState() {
  return (
    <View style={styles.emptyContainer}>
      <Ionicons
        name="file-tray-outline"
        size={48}
        color={Colors.textMuted}
        style={styles.centeredIcon}
      />
      <Text style={styles.emptyTitle}>This collection is empty</Text>
      <Text style={styles.emptyHint}>
        Media you save into this collection will show up here.
      </Text>
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: Colors.background,
  },
  header: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    paddingHorizontal: Spacing.lg,
    paddingVertical: Spacing.md,
    gap: Spacing.md,
  },
  backButton: {
    width: 40,
    height: 40,
    borderRadius: BorderRadius.full,
    backgroundColor: Colors.surfaceContainerHigh,
    alignItems: "center",
    justifyContent: "center",
  },
  headerTitle: {
    flex: 1,
    textAlign: "center",
    fontSize: Typography.headline.fontSize,
    fontWeight: "700",
    color: Colors.textMain,
    letterSpacing: -0.3,
  },
  headerSpacer: {
    width: 40,
    height: 40,
  },
  listContent: {
    paddingTop: Spacing.sm,
    paddingBottom: Spacing.xxl,
  },

  // Folder row
  folderCard: {
    flexDirection: "row",
    alignItems: "center",
    gap: Spacing.md,
    backgroundColor: Colors.surface,
    borderRadius: BorderRadius.xl,
    padding: Spacing.md,
    marginHorizontal: Spacing.md,
    marginBottom: Spacing.md,
    minHeight: TouchTarget.comfortable,
    ...Shadows.soft,
  },
  folderCardPressed: {
    transform: [{ scale: 0.98 }],
    opacity: 0.9,
  },
  folderIconContainer: {
    width: 48,
    height: 48,
    borderRadius: BorderRadius.lg,
    backgroundColor: Colors.surfaceContainerLow,
    alignItems: "center",
    justifyContent: "center",
  },
  folderTextSection: {
    flex: 1,
    gap: 2,
  },
  folderName: {
    fontSize: Typography.body.fontSize,
    fontWeight: "700",
    color: Colors.textMain,
  },
  folderSubtitle: {
    fontSize: Typography.small.fontSize,
    color: Colors.textMuted,
  },

  // Centered states
  centered: {
    flex: 1,
    justifyContent: "center",
    alignItems: "center",
    paddingHorizontal: Spacing.xl,
  },
  centeredText: {
    fontSize: Typography.body.fontSize,
    color: Colors.textMuted,
    marginTop: Spacing.md,
  },
  centeredIcon: {
    marginBottom: Spacing.md,
  },
  centeredTitle: {
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

  // Empty state
  emptyContainer: {
    paddingTop: 100,
    alignItems: "center",
    paddingHorizontal: Spacing.xl,
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
    lineHeight: Typography.body.lineHeight,
  },
});
