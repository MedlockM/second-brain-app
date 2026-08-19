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
import { useRouter, useFocusEffect } from "expo-router";
import { useAuth } from "../../../src/contexts/AuthContext";
import { OrganizationService } from "../../../src/services/organizationService";
import { MediaService } from "../../../src/services/mediaService";
import { getFriendlyErrorMessage } from "../../../src/lib/getFriendlyErrorMessage";
import {
  buildCollectionTree,
  DEFAULT_COLLECTION_LABEL,
  DEFAULT_COLLECTION_TINT,
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
 * Collections explorer — root view.
 *
 * Lists the user's collections as folders (file-explorer style). Nested
 * collections are reachable by drilling into a folder via the dedicated
 * `[id]` screen. The default folder is surfaced as a dedicated "Unsorted"
 * entry so unsorted media stay reachable.
 *
 * Handles loading / error / empty states (AC#5).
 */
export default function CollectionsExplorerScreen() {
  const router = useRouter();
  const { isAuthenticated } = useAuth();

  const [roots, setRoots] = useState<CollectionNode[]>([]);
  const [defaultCollection, setDefaultCollection] =
    useState<CollectionNode | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    if (!isAuthenticated) return;
    setError(null);
    try {
      const [collections, mediaResponse] = await Promise.all([
        OrganizationService.getUserCollections(),
        MediaService.listMedia(),
      ]);

      const directCountById = new Map<string, number>();
      for (const media of mediaResponse.items as MediaListItem[]) {
        if (!media.folder_id) continue;
        directCountById.set(
          media.folder_id,
          (directCountById.get(media.folder_id) ?? 0) + 1,
        );
      }

      const tree = buildCollectionTree(collections, directCountById);
      setRoots(tree.roots);
      setDefaultCollection(tree.defaultCollection);
    } catch (err) {
      setError(
        getFriendlyErrorMessage(err, {
          fallback: "Unable to load your collections. Please try again.",
        }),
      );
    }
  }, [isAuthenticated]);

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

  const handleOpenCollection = useCallback(
    (collection: CollectionNode) => {
      router.push({
        pathname: "/media/collections/[id]",
        params: { id: collection.id, name: collection.name },
      });
    },
    [router],
  );

  const handleRetry = useCallback(() => {
    setIsLoading(true);
    load().finally(() => setIsLoading(false));
  }, [load]);

  // Default folder gets pinned to the top of the list, under its display label.
  const listData = useMemo(() => {
    if (!defaultCollection) return roots;
    return [{ ...defaultCollection, name: DEFAULT_COLLECTION_LABEL }, ...roots];
  }, [defaultCollection, roots]);

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
        <Text style={styles.headerTitle}>Collections</Text>
        <View style={styles.headerSpacer} />
      </View>

      {isLoading ? (
        <View style={styles.centered}>
          <ActivityIndicator size="large" color={Colors.primary} />
          <Text style={styles.centeredText}>Loading collections...</Text>
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
            accessibilityLabel="Retry loading collections"
            accessibilityRole="button"
          >
            <Ionicons name="refresh" size={18} color={Colors.onPrimary} />
            <Text style={styles.retryButtonText}>Retry</Text>
          </Pressable>
        </View>
      ) : (
        <FlatList
          data={listData}
          keyExtractor={(item) => item.id}
          renderItem={({ item }) => (
            <FolderRow
              node={item}
              isDefault={item.is_default === true}
              onPress={handleOpenCollection}
            />
          )}
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
  /** The system default folder, tinted apart from the user's own collections. */
  isDefault: boolean;
  onPress: (node: CollectionNode) => void;
}

function FolderRow({ node, isDefault, onPress }: FolderRowProps) {
  const childCount = node.children.length;
  const subtitleParts: string[] = [];
  if (node.directMediaCount > 0) {
    subtitleParts.push(
      `${node.directMediaCount} ${node.directMediaCount === 1 ? "item" : "items"}`,
    );
  }
  if (childCount > 0) {
    subtitleParts.push(
      `${childCount} ${childCount === 1 ? "collection" : "collections"}`,
    );
  }
  const subtitle = subtitleParts.length ? subtitleParts.join(" · ") : "Empty";

  return (
    <Pressable
      style={({ pressed }) => [styles.folderCard, pressed && styles.folderCardPressed]}
      onPress={() => onPress(node)}
      accessibilityLabel={`Open collection ${node.name}`}
      accessibilityRole="button"
    >
      <View
        style={[
          styles.folderIconContainer,
          isDefault && styles.folderIconContainerDefault,
        ]}
      >
        <Ionicons
          name="folder"
          size={26}
          color={isDefault ? DEFAULT_COLLECTION_TINT : Colors.primary}
        />
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
        name="folder-open-outline"
        size={48}
        color={Colors.textMuted}
        style={styles.centeredIcon}
      />
      <Text style={styles.emptyTitle}>No collections yet</Text>
      <Text style={styles.emptyHint}>
        Organize media into collections when you save them to find them here.
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
    paddingHorizontal: Spacing.md,
    paddingTop: Spacing.sm,
    paddingBottom: Spacing.xxl,
  },

  // Folder card
  folderCard: {
    flexDirection: "row",
    alignItems: "center",
    gap: Spacing.md,
    backgroundColor: Colors.surface,
    borderRadius: BorderRadius.xl,
    padding: Spacing.md,
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
  /** Deeper tonal step for the default folder -- a colour block, never a rule. */
  folderIconContainerDefault: {
    backgroundColor: Colors.surfaceContainerHigh,
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

  // Centered states (loading / error)
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
