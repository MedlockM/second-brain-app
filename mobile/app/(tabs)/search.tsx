import { useState, useEffect, useCallback, useMemo } from "react";
import {
  View,
  Text,
  StyleSheet,
  TextInput,
  FlatList,
  ActivityIndicator,
  Pressable,
} from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";
import { Ionicons } from "@expo/vector-icons";
import { useRouter, useFocusEffect } from "expo-router";
import { useAuth } from "../../src/contexts/AuthContext";
import { useDebounce } from "../../src/hooks/useDebounce";
import {
  SearchService,
  type SearchHit,
} from "../../src/services/searchService";
import { OrganizationService } from "../../src/services/organizationService";
import { MediaService } from "../../src/services/mediaService";
import { getFriendlyErrorMessage } from "../../src/lib/getFriendlyErrorMessage";
import {
  buildCollectionTree,
  type CollectionNode,
} from "../../src/lib/collectionTree";
import { parseHighlightSnippet } from "../../src/lib/highlightSnippet";
import {
  Colors,
  Typography,
  Spacing,
  BorderRadius,
  Shadows,
  TouchTarget,
} from "../../src/constants/theme";
import type { MediaListItem } from "../../src/types/media";

// --- Helper functions ---

function getSourceIcon(
  platform: string | null,
): keyof typeof Ionicons.glyphMap {
  switch (platform) {
    case "spotify":
    case "apple_podcasts":
    case "deezer":
    case "rss":
    case "podcast_index":
      return "mic-outline";
    case "youtube":
      return "logo-youtube";
    case "instagram":
    case "tiktok":
      return "videocam-outline";
    case "web":
    case "direct_url":
      return "globe-outline";
    case "x":
      return "chatbox-outline";
    default:
      return "link-outline";
  }
}

function getSourceLabel(platform: string | null): string {
  switch (platform) {
    case "spotify":
      return "Spotify";
    case "apple_podcasts":
      return "Apple Podcasts";
    case "deezer":
      return "Deezer";
    case "rss":
      return "RSS";
    case "podcast_index":
      return "Podcast Index";
    case "youtube":
      return "YouTube";
    case "instagram":
      return "Instagram";
    case "tiktok":
      return "TikTok";
    case "x":
      return "X";
    case "whatsapp":
      return "WhatsApp";
    case "web":
      return "Web";
    case "direct_url":
      return "Direct URL";
    default:
      return "Unknown";
  }
}

function formatTimestamp(unixTimestamp: number): string {
  if (!unixTimestamp) return "";

  const date = new Date(unixTimestamp * 1000);
  const now = new Date();
  const diffMs = now.getTime() - date.getTime();
  const diffDays = Math.floor(diffMs / (1000 * 60 * 60 * 24));

  if (diffDays === 0) return "Today";
  if (diffDays === 1) return "Yesterday";
  if (diffDays < 7) return `${diffDays}d ago`;

  return date.toLocaleDateString("en-US", { month: "short", day: "numeric" });
}

// --- Main Screen Component ---

export default function SearchScreen() {
  const { token } = useAuth();
  const router = useRouter();

  // Search state
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<SearchHit[]>([]);
  const [totalResults, setTotalResults] = useState(0);
  const [isLoading, setIsLoading] = useState(false);
  const [hasSearched, setHasSearched] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [collections, setCollections] = useState<CollectionNode[]>([]);
  const [collectionsLoading, setCollectionsLoading] = useState(true);
  const [collectionsError, setCollectionsError] = useState<string | null>(null);

  // Debounce the search query
  const debouncedQuery = useDebounce(query, 300);

  // Execute search when debounced query or filter changes
  useEffect(() => {
    if (!token) return;

    // Algolia requires a non-empty query (min_length=1).
    // Do not search with only a filter and no text query.
    if (!debouncedQuery.trim()) {
      return;
    }

    const performSearch = async () => {
      setIsLoading(true);
      setError(null);

      try {
        const response = await SearchService.searchTranscripts(
          token,
          debouncedQuery,
        );

        setResults(response.hits);
        setTotalResults(response.found);
        setHasSearched(true);
      } catch (err: unknown) {
        const message =
          err instanceof Error ? err.message : "Search failed";
        setError(message);
        setResults([]);
        setTotalResults(0);
        setHasSearched(true);
      } finally {
        setIsLoading(false);
      }
    };

    performSearch();
  }, [debouncedQuery, token]);

  const loadCollections = useCallback(async () => {
    if (!token) return;
    setCollectionsError(null);

    try {
      const [folders, mediaResponse] = await Promise.all([
        OrganizationService.getUserCollections(token),
        MediaService.listMedia(token),
      ]);

      const directCountById = new Map<string, number>();
      for (const media of mediaResponse.items as MediaListItem[]) {
        if (!media.folder_id) continue;
        directCountById.set(
          media.folder_id,
          (directCountById.get(media.folder_id) ?? 0) + 1,
        );
      }

      const tree = buildCollectionTree(folders, directCountById);
      setCollections(tree.roots);
    } catch (err) {
      setCollectionsError(
        getFriendlyErrorMessage(err, {
          fallback: "Unable to load your collections.",
        }),
      );
    }
  }, [token]);

  useFocusEffect(
    useCallback(() => {
      let active = true;
      setCollectionsLoading(true);
      loadCollections().finally(() => {
        if (active) setCollectionsLoading(false);
      });
      return () => {
        active = false;
      };
    }, [loadCollections]),
  );

  const handleClearQuery = useCallback(() => {
    setQuery("");
    setResults([]);
    setTotalResults(0);
    setHasSearched(false);
    setError(null);
  }, []);

  const handleQueryChange = useCallback((nextQuery: string) => {
    setQuery(nextQuery);
    if (!nextQuery.trim()) {
      setResults([]);
      setTotalResults(0);
      setHasSearched(false);
      setError(null);
    }
  }, []);

  const handleOpenCollection = useCallback(
    (collection: CollectionNode) => {
      router.push({
        pathname: "/media/collections/[id]",
        params: { id: collection.id, name: collection.name },
      });
    },
    [router],
  );

  const sortedCollections = useMemo(
    () => [...collections].sort((a, b) => a.name.localeCompare(b.name)),
    [collections],
  );

  const handleRetryCollections = useCallback(() => {
    setCollectionsLoading(true);
    loadCollections().finally(() => setCollectionsLoading(false));
  }, [loadCollections]);

  return (
    <SafeAreaView style={styles.container} edges={["top"]}>
      {/* Header with search input */}
      <View style={styles.header}>
        <Text style={styles.title}>Search</Text>

        {/* Search Input */}
        <View style={styles.searchBarContainer}>
          <Ionicons
            name="search"
            size={20}
            color={Colors.textMuted}
            style={styles.searchIcon}
          />
          <TextInput
            testID="search-input"
            style={styles.searchInput}
            placeholder="Search your library..."
            placeholderTextColor={Colors.textMuted}
            value={query}
            onChangeText={handleQueryChange}
            autoCapitalize="none"
            autoCorrect={false}
            returnKeyType="search"
          />
          {query.length > 0 && (
            <Pressable
              onPress={handleClearQuery}
              style={styles.clearButton}
              hitSlop={8}
              accessibilityLabel="Clear search query"
              accessibilityRole="button"
            >
              <Ionicons name="close" size={18} color={Colors.textMuted} />
            </Pressable>
          )}
        </View>
      </View>

      {/* Results Area */}
      <View style={styles.resultsArea}>
        {isLoading ? (
          <LoadingState />
        ) : error ? (
          <ErrorState message={error} />
        ) : !hasSearched ? (
          <CollectionsState
            collections={sortedCollections}
            isLoading={collectionsLoading}
            error={collectionsError}
            onRetry={handleRetryCollections}
            onOpenCollection={handleOpenCollection}
          />
        ) : results.length === 0 ? (
          <NoResultsState query={debouncedQuery} />
        ) : (
          <FlatList
            data={results}
            keyExtractor={(item) => item.media_item_id}
            keyboardShouldPersistTaps="handled"
            renderItem={({ item }) => (
              <ResultCard
                hit={item}
                onPress={() => router.push(`/media/${item.media_item_id}`)}
              />
            )}
            contentContainerStyle={styles.resultsList}
            showsVerticalScrollIndicator={false}
            ListHeaderComponent={
              <Text style={styles.resultsCount}>
                {totalResults} {totalResults === 1 ? "result" : "results"} found
              </Text>
            }
            ListFooterComponent={
              results.length > 0 ? (
                <Text style={styles.endOfResults}>End of results</Text>
              ) : null
            }
          />
        )}
      </View>
    </SafeAreaView>
  );
}

// --- Sub-components ---

function CollectionsState({
  collections,
  isLoading,
  error,
  onRetry,
  onOpenCollection,
}: {
  collections: CollectionNode[];
  isLoading: boolean;
  error: string | null;
  onRetry: () => void;
  onOpenCollection: (collection: CollectionNode) => void;
}) {
  if (isLoading) {
    return (
      <View style={styles.emptyContainer}>
        <ActivityIndicator size="large" color={Colors.primary} />
        <Text style={[styles.emptyHint, { marginTop: Spacing.md }]}>
          Loading collections...
        </Text>
      </View>
    );
  }

  if (error) {
    return (
      <View style={styles.emptyContainer}>
        <Ionicons
          name="cloud-offline-outline"
          size={48}
          color={Colors.textMuted}
          style={styles.emptyIcon}
        />
        <Text style={styles.emptyTitle}>{error}</Text>
        <Pressable
          style={styles.retryButton}
          onPress={onRetry}
          accessibilityLabel="Retry loading collections"
          accessibilityRole="button"
        >
          <Ionicons name="refresh" size={18} color={Colors.onPrimary} />
          <Text style={styles.retryButtonText}>Retry</Text>
        </Pressable>
      </View>
    );
  }

  if (collections.length === 0) {
    return (
      <View style={styles.emptyContainer}>
        <Ionicons
          name="folder-open-outline"
          size={48}
          color={Colors.textMuted}
          style={styles.emptyIcon}
        />
        <Text style={styles.emptyTitle}>No collections yet</Text>
        <Text style={styles.emptyHint}>
          Organize media into collections when you save them.
        </Text>
      </View>
    );
  }

  return (
    <FlatList
      data={collections}
      keyExtractor={(item) => item.id}
      numColumns={3}
      renderItem={({ item }) => (
        <CollectionTile collection={item} onPress={onOpenCollection} />
      )}
      contentContainerStyle={styles.collectionsGridContent}
      showsVerticalScrollIndicator={false}
      ListHeaderComponent={
        <Text style={styles.collectionsTitle}>Collections</Text>
      }
    />
  );
}

function CollectionTile({
  collection,
  onPress,
}: {
  collection: CollectionNode;
  onPress: (collection: CollectionNode) => void;
}) {
  return (
    <View style={styles.collectionTileSlot}>
      <Pressable
        style={({ pressed }) => [
          styles.collectionTile,
          pressed && styles.collectionTilePressed,
        ]}
        onPress={() => onPress(collection)}
        accessibilityLabel={`Open collection ${collection.name}`}
        accessibilityRole="button"
      >
        <View style={styles.collectionIcon}>
          <Ionicons name="folder" size={42} color={Colors.primary} />
        </View>
        <Text style={styles.collectionName} numberOfLines={2}>
          {collection.name}
        </Text>
      </Pressable>
    </View>
  );
}

function NoResultsState({ query }: { query: string }) {
  return (
    <View style={styles.emptyContainer}>
      <Ionicons
        name="document-outline"
        size={48}
        color={Colors.textMuted}
        style={styles.emptyIcon}
      />
      <Text style={styles.emptyTitle}>No results found</Text>
      <Text style={styles.emptyHint}>
        No matches for "{query}". Try different keywords.
      </Text>
    </View>
  );
}

function LoadingState() {
  return (
    <View style={styles.emptyContainer}>
      <ActivityIndicator size="large" color={Colors.primary} />
      <Text style={[styles.emptyHint, { marginTop: Spacing.md }]}>
        Searching...
      </Text>
    </View>
  );
}

function ErrorState({ message }: { message: string }) {
  return (
    <View style={styles.emptyContainer}>
      <Ionicons
        name="alert-circle-outline"
        size={48}
        color={Colors.error}
        style={styles.emptyIcon}
      />
      <Text style={styles.emptyTitle}>Something went wrong</Text>
      <Text style={styles.emptyHint}>{message}</Text>
    </View>
  );
}

function ResultCard({ hit, onPress }: { hit: SearchHit; onPress: () => void }) {
  // Indexed titles are derived server-side and are never empty (task-266), so
  // the client no longer invents "Untitled" -- a word that told the user nothing
  // and, being the same for every such hit, made results indistinguishable.
  const displayTitle = hit.title ?? "";
  const sourceLabel = getSourceLabel(hit.source_platform);
  const sourceIcon = getSourceIcon(hit.source_platform);
  const dateLabel = formatTimestamp(hit.created_at);

  // Extract the first highlight snippet for preview text, split into plain
  // and matched segments (Algolia returns it as `<mark>`-tagged HTML).
  const snippetSegments = parseHighlightSnippet(
    hit.highlights.length > 0 ? hit.highlights[0].snippet : "",
  );

  return (
    <Pressable
      testID="search-result-card"
      style={styles.card}
      onPress={onPress}
      accessibilityLabel={`${displayTitle}, ${sourceLabel}`}
      accessibilityRole="button"
    >
      {/* Card Header: source icon + label + date */}
      <View style={styles.cardHeader}>
        <View style={styles.cardSourceRow}>
          <Ionicons name={sourceIcon} size={16} color={Colors.primary} />
          <Text style={styles.cardSourceLabel}>{sourceLabel}</Text>
        </View>
        {dateLabel ? <Text style={styles.cardDate}>{dateLabel}</Text> : null}
      </View>

      {/* Title */}
      <Text style={styles.cardTitle} numberOfLines={2}>
        {displayTitle}
      </Text>

      {/* Highlight snippet (transcript match preview) */}
      {snippetSegments.length > 0 ? (
        <Text style={styles.cardSnippet} numberOfLines={3}>
          {snippetSegments.map((segment, index) => (
            <Text
              key={index}
              style={segment.highlighted ? styles.cardSnippetMatch : undefined}
            >
              {segment.text}
            </Text>
          ))}
        </Text>
      ) : null}
    </Pressable>
  );
}

// --- Styles ---

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: Colors.background,
  },

  // Header
  header: {
    backgroundColor: Colors.surface,
    paddingHorizontal: Spacing.md,
    paddingTop: Spacing.md,
    paddingBottom: Spacing.md,
  },
  title: {
    fontSize: Typography.display.fontSize,
    fontWeight: Typography.display.fontWeight,
    color: Colors.textMain,
    letterSpacing: Typography.display.letterSpacing,
    marginBottom: Spacing.md,
  },

  // Search bar - minimum height meets touch target
  searchBarContainer: {
    flexDirection: "row",
    alignItems: "center",
    backgroundColor: Colors.background,
    borderRadius: BorderRadius.lg,
    borderWidth: 1,
    borderColor: Colors.outlineVariant,
    height: TouchTarget.minimum,
    paddingHorizontal: Spacing.md,
  },
  searchIcon: {
    marginRight: Spacing.sm,
  },
  searchInput: {
    flex: 1,
    fontSize: Typography.body.fontSize,
    fontWeight: Typography.body.fontWeight,
    color: Colors.textMain,
    height: "100%",
    paddingVertical: 0,
  },
  clearButton: {
    marginLeft: Spacing.sm,
    padding: Spacing.xs,
  },

  // Results area
  resultsArea: {
    flex: 1,
  },
  resultsList: {
    paddingHorizontal: Spacing.md,
    paddingTop: Spacing.md,
    paddingBottom: Spacing.xxl,
    gap: Spacing.md,
  },
  resultsCount: {
    fontSize: Typography.small.fontSize,
    fontWeight: Typography.label.fontWeight,
    color: Colors.textMuted,
    textTransform: "uppercase",
    letterSpacing: 0.5,
    marginBottom: Spacing.sm,
  },
  endOfResults: {
    fontSize: Typography.small.fontSize,
    color: Colors.textMuted,
    textAlign: "center",
    marginTop: Spacing.lg,
  },

  // Collections grid
  collectionsGridContent: {
    paddingHorizontal: Spacing.md,
    paddingTop: Spacing.lg,
    paddingBottom: Spacing.xxl,
  },
  collectionsTitle: {
    fontSize: Typography.headline.fontSize,
    fontWeight: "700",
    color: Colors.textMain,
    marginBottom: Spacing.md,
  },
  collectionTileSlot: {
    width: "33.333%",
    paddingHorizontal: 6,
    marginBottom: Spacing.lg,
  },
  collectionTile: {
    alignItems: "center",
    justifyContent: "flex-start",
    minHeight: 112,
    paddingVertical: Spacing.sm,
  },
  collectionTilePressed: {
    opacity: 0.75,
    transform: [{ scale: 0.97 }],
  },
  collectionIcon: {
    width: 64,
    height: 58,
    alignItems: "center",
    justifyContent: "center",
    marginBottom: Spacing.xs,
  },
  collectionName: {
    fontSize: Typography.small.fontSize,
    fontWeight: "600",
    color: Colors.textMain,
    textAlign: "center",
    lineHeight: 17,
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
    marginTop: Spacing.lg,
  },
  retryButtonText: {
    fontSize: Typography.label.fontSize,
    fontWeight: Typography.label.fontWeight,
    color: Colors.onPrimary,
  },

  // Empty states
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
    lineHeight: Typography.body.lineHeight,
  },

  // Result card
  card: {
    backgroundColor: Colors.surface,
    borderRadius: BorderRadius.xl,
    padding: Spacing.md,
    borderWidth: StyleSheet.hairlineWidth,
    borderColor: Colors.outlineVariant,
    ...Shadows.soft,
  },
  cardHeader: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    marginBottom: Spacing.sm,
  },
  cardSourceRow: {
    flexDirection: "row",
    alignItems: "center",
    gap: Spacing.sm,
  },
  cardSourceLabel: {
    fontSize: Typography.small.fontSize,
    fontWeight: Typography.label.fontWeight,
    color: Colors.textMuted,
    textTransform: "uppercase",
    letterSpacing: 0.5,
  },
  cardDate: {
    fontSize: Typography.small.fontSize,
    color: Colors.textMuted,
  },
  cardTitle: {
    fontSize: Typography.body.fontSize,
    fontWeight: "600",
    color: Colors.textMain,
    lineHeight: 22,
    marginBottom: Spacing.xs,
  },
  cardSnippet: {
    fontSize: Typography.small.fontSize,
    color: Colors.textMuted,
    lineHeight: 18,
    marginTop: Spacing.xs,
  },
  cardSnippetMatch: {
    backgroundColor: Colors.highlight,
    color: Colors.onHighlight,
    fontWeight: "600",
  },
});
