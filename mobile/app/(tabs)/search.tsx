import { useState, useEffect, useCallback, useMemo, type ReactNode } from "react";
import {
  View,
  Text,
  StyleSheet,
  TextInput,
  FlatList,
  ActivityIndicator,
  Platform,
  Pressable,
  RefreshControl,
  type StyleProp,
  type ViewStyle,
} from "react-native";
import {
  SafeAreaView,
  useSafeAreaInsets,
} from "react-native-safe-area-context";
import { BlurView } from "expo-blur";
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
  DEFAULT_COLLECTION_LABEL,
  DEFAULT_COLLECTION_TINT,
  type CollectionNode,
} from "../../src/lib/collectionTree";
import { parseHighlightSnippet } from "../../src/lib/highlightSnippet";
import { MediaListCard } from "../../src/components/MediaListCard";
import {
  Colors,
  Typography,
  Spacing,
  BorderRadius,
  Shadows,
  TouchTarget,
} from "../../src/constants/theme";
import type { MediaListItem } from "../../src/types/media";

// --- Layout constants ---

/**
 * The search bar floats above the content instead of sitting in the flow, so
 * the space it occupies has to be given back to the lists as top padding.
 */
const SEARCH_BAR_HEIGHT = TouchTarget.minimum;
const SEARCH_BAR_TOP = Spacing.sm;
const CONTENT_TOP_INSET = SEARCH_BAR_TOP + SEARCH_BAR_HEIGHT + Spacing.md;

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

/**
 * The library tab: everything the user saved, plus the search over it.
 *
 * Two bodies, mutually exclusive, switched by the query in the floating pill.
 * With nothing typed it shows the library — the collections *and* every media
 * item, newest first. Typing hands the screen over to Algolia; clearing the
 * query gives it back.
 *
 * The tab keeps its `search-tab-button` id whatever its label reads.
 */
export default function SearchScreen() {
  const { isAuthenticated } = useAuth();
  const router = useRouter();
  const insets = useSafeAreaInsets();

  // Search state
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<SearchHit[]>([]);
  const [totalResults, setTotalResults] = useState(0);
  const [isLoading, setIsLoading] = useState(false);
  const [hasSearched, setHasSearched] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Library state. The two halves are fetched by two independent requests and
  // carry their own loading and error flags: one failing must leave the other
  // rendered, with its own retry.
  const [collections, setCollections] = useState<CollectionNode[]>([]);
  const [defaultCollection, setDefaultCollection] =
    useState<CollectionNode | null>(null);
  const [collectionsLoading, setCollectionsLoading] = useState(true);
  const [collectionsError, setCollectionsError] = useState<string | null>(null);
  const [media, setMedia] = useState<MediaListItem[]>([]);
  const [mediaLoading, setMediaLoading] = useState(true);
  const [mediaError, setMediaError] = useState<string | null>(null);
  const [isRefreshing, setIsRefreshing] = useState(false);

  // Debounce the search query
  const debouncedQuery = useDebounce(query, 300);

  // Execute search when debounced query or filter changes
  useEffect(() => {
    if (!isAuthenticated) return;

    // Algolia requires a non-empty query (min_length=1).
    // Do not search with only a filter and no text query.
    if (!debouncedQuery.trim()) {
      return;
    }

    const performSearch = async () => {
      setIsLoading(true);
      setError(null);

      try {
        const response = await SearchService.searchTranscripts(debouncedQuery);

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
  }, [debouncedQuery, isAuthenticated]);

  // Neither loader throws: each one owns its error state, so the caller can
  // always await both and only has its own spinner to clear.
  const loadCollections = useCallback(async () => {
    if (!isAuthenticated) return;

    try {
      const folders = await OrganizationService.getUserCollections();
      const tree = buildCollectionTree(folders);
      setCollections(tree.roots);
      setDefaultCollection(tree.defaultCollection);
      setCollectionsError(null);
    } catch (err) {
      setCollectionsError(
        getFriendlyErrorMessage(err, {
          fallback: "Unable to load your collections.",
        }),
      );
    }
  }, [isAuthenticated]);

  const loadMedia = useCallback(async () => {
    if (!isAuthenticated) return;

    try {
      const response = await MediaService.listMedia();
      // Rendered in the order the endpoint returns: `GET /api/media` already
      // sorts the whole library `saved_at` DESC server-side, so a client-side
      // re-sort could only disagree with it.
      setMedia(response.items);
      setMediaError(null);
    } catch (err) {
      setMediaError(
        getFriendlyErrorMessage(err, {
          fallback: "Unable to load your library.",
        }),
      );
    }
  }, [isAuthenticated]);

  // Refetch on every focus, so a media saved from the share sheet or the inbox
  // is here on the way back. The two loading flags are only ever cleared: they
  // belong to the first load, and a later focus refetches silently under the
  // content already on screen.
  useFocusEffect(
    useCallback(() => {
      let active = true;
      void loadCollections().finally(() => {
        if (active) setCollectionsLoading(false);
      });
      void loadMedia().finally(() => {
        if (active) setMediaLoading(false);
      });
      return () => {
        active = false;
      };
    }, [loadCollections, loadMedia]),
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

  const handleOpenMedia = useCallback(
    (mediaItemId: string) => {
      router.push(`/media/${mediaItemId}`);
    },
    [router],
  );

  // The default folder holds every media saved without an explicit collection.
  // It is excluded from `roots` by `buildCollectionTree`, so pin it in front
  // under its display label -- same pattern as the collections explorer.
  const sortedCollections = useMemo(() => {
    const sorted = [...collections].sort((a, b) =>
      a.name.localeCompare(b.name),
    );
    if (!defaultCollection) return sorted;
    return [
      { ...defaultCollection, name: DEFAULT_COLLECTION_LABEL },
      ...sorted,
    ];
  }, [collections, defaultCollection]);

  const handleRetryCollections = useCallback(() => {
    setCollectionsLoading(true);
    void loadCollections().finally(() => setCollectionsLoading(false));
  }, [loadCollections]);

  const handleRetryMedia = useCallback(() => {
    setMediaLoading(true);
    void loadMedia().finally(() => setMediaLoading(false));
  }, [loadMedia]);

  // Pull-to-refresh reloads both halves: the gesture is on the one scroll that
  // carries them, so refreshing only one of them would be a lie.
  const handleRefresh = useCallback(() => {
    setIsRefreshing(true);
    void Promise.all([loadCollections(), loadMedia()]).finally(() =>
      setIsRefreshing(false),
    );
  }, [loadCollections, loadMedia]);

  return (
    <View style={styles.container}>
      {/* Results Area -- scrolls underneath the floating search bar */}
      <SafeAreaView style={styles.resultsArea} edges={["top"]}>
        {isLoading ? (
          <LoadingState />
        ) : error ? (
          <ErrorState message={error} />
        ) : !hasSearched ? (
          <LibraryState
            collections={sortedCollections}
            collectionsLoading={collectionsLoading}
            collectionsError={collectionsError}
            onRetryCollections={handleRetryCollections}
            onOpenCollection={handleOpenCollection}
            media={media}
            mediaLoading={mediaLoading}
            mediaError={mediaError}
            onRetryMedia={handleRetryMedia}
            onOpenMedia={handleOpenMedia}
            isRefreshing={isRefreshing}
            onRefresh={handleRefresh}
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
      </SafeAreaView>

      {/* Floating glassy search bar, overlaid on top of the content.
          It sits outside the SafeAreaView on purpose: Yoga does not offset an
          absolutely positioned child by its parent's padding, so anchoring it
          there would have pinned the pill over the status bar. */}
      <View
        style={[styles.searchBarOverlay, { top: insets.top + SEARCH_BAR_TOP }]}
        pointerEvents="box-none"
      >
        <GlassSurface style={styles.searchBar}>
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
        </GlassSurface>
      </View>
    </View>
  );
}

// --- Sub-components ---

/**
 * Translucent backdrop of the search pill.
 *
 * iOS renders the real native blur. Android's blur support is uneven across
 * devices and vendors -- and silently degrades when the system disables
 * animations -- so it falls back to a semi-opaque tint, which keeps the pill
 * readable over any scrolling content instead of risking a broken surface.
 */
function GlassSurface({
  children,
  style,
}: {
  children: ReactNode;
  style: StyleProp<ViewStyle>;
}) {
  if (Platform.OS === "ios") {
    return (
      <BlurView intensity={60} tint="light" style={style}>
        {children}
      </BlurView>
    );
  }

  return (
    <View style={[style, styles.searchBarAndroidFallback]}>{children}</View>
  );
}

interface LibraryStateProps {
  collections: CollectionNode[];
  collectionsLoading: boolean;
  collectionsError: string | null;
  onRetryCollections: () => void;
  onOpenCollection: (collection: CollectionNode) => void;
  media: MediaListItem[];
  mediaLoading: boolean;
  mediaError: string | null;
  onRetryMedia: () => void;
  onOpenMedia: (mediaItemId: string) => void;
  isRefreshing: boolean;
  onRefresh: () => void;
}

/**
 * The library: the collections and every saved media item, in **one vertical
 * scroll** — the collections grid rides in the list header, the media rows are
 * the list.
 *
 * Chosen over `ScreenTabs`, the other shape the design system offers, for two
 * reasons. First, the two halves come from two independent requests, and the
 * requirement is that a failure of one leaves the other usable: side by side in
 * one scroll, the error card sits *next to* the half that worked instead of
 * hiding behind a tab nobody has a reason to open. Second, a segmented control
 * would be a second bar of chrome directly under the floating search pill,
 * spending the top of the screen on navigation on a screen whose whole job is to
 * show what you saved. The cost of this choice is that a user with many
 * collections scrolls past them to reach the media — acceptable, because the
 * grid is three tiles wide and the list is what the scroll is for.
 */
function LibraryState({
  collections,
  collectionsLoading,
  collectionsError,
  onRetryCollections,
  onOpenCollection,
  media,
  mediaLoading,
  mediaError,
  onRetryMedia,
  onOpenMedia,
  isRefreshing,
  onRefresh,
}: LibraryStateProps) {
  // What stands in for the media rows while there are none: its own spinner on
  // the first load, its own error card with a retry, or the empty library.
  const mediaPlaceholder = mediaLoading ? (
    <View style={styles.sectionLoadingRow}>
      <ActivityIndicator color={Colors.primary} />
    </View>
  ) : mediaError ? (
    <InlineErrorCard
      message={mediaError}
      onRetry={onRetryMedia}
      retryAccessibilityLabel="Retry loading your library"
    />
  ) : (
    <EmptyLibraryState />
  );

  return (
    <FlatList
      testID="library-media-list"
      data={media}
      keyExtractor={(item) => item.media_item_id}
      keyboardShouldPersistTaps="handled"
      renderItem={({ item }) => (
        <MediaListCard
          item={item}
          onPress={onOpenMedia}
          testID="library-media-card"
        />
      )}
      contentContainerStyle={styles.libraryListContent}
      showsVerticalScrollIndicator={false}
      refreshControl={
        <RefreshControl
          refreshing={isRefreshing}
          onRefresh={onRefresh}
          tintColor={Colors.primary}
          colors={[Colors.primary]}
          // The list starts below the floating pill, so the spinner has to as
          // well -- otherwise it appears underneath it.
          progressViewOffset={CONTENT_TOP_INSET}
        />
      }
      ListHeaderComponent={
        <LibraryHeader
          collections={collections}
          collectionsLoading={collectionsLoading}
          collectionsError={collectionsError}
          onRetryCollections={onRetryCollections}
          onOpenCollection={onOpenCollection}
          mediaCount={media.length}
        />
      }
      ListEmptyComponent={mediaPlaceholder}
      // Rows already on screen are never dropped for an error, so a refresh that
      // fails says so at the end of the list instead of silently keeping stale
      // rows.
      ListFooterComponent={
        mediaError && media.length > 0 ? (
          <InlineErrorCard
            message={mediaError}
            onRetry={onRetryMedia}
            retryAccessibilityLabel="Retry loading your library"
          />
        ) : null
      }
    />
  );
}

function LibraryHeader({
  collections,
  collectionsLoading,
  collectionsError,
  onRetryCollections,
  onOpenCollection,
  mediaCount,
}: {
  collections: CollectionNode[];
  collectionsLoading: boolean;
  collectionsError: string | null;
  onRetryCollections: () => void;
  onOpenCollection: (collection: CollectionNode) => void;
  mediaCount: number;
}) {
  return (
    <View style={styles.libraryHeader}>
      <Text style={styles.sectionTitle}>Collections</Text>

      {collectionsLoading ? (
        <View style={styles.sectionLoadingRow}>
          <ActivityIndicator color={Colors.primary} />
        </View>
      ) : collectionsError ? (
        <InlineErrorCard
          message={collectionsError}
          onRetry={onRetryCollections}
          retryAccessibilityLabel="Retry loading collections"
        />
      ) : collections.length === 0 ? (
        <Text style={styles.sectionHint}>
          No collections yet. Organize media into collections when you save them.
        </Text>
      ) : (
        // Laid out by wrapping rather than by a nested FlatList: a vertical
        // virtualized list inside another one is unsupported, and the number of
        // collections a user can own is bounded by the backend folder cap.
        <View style={styles.collectionsGrid}>
          {collections.map((collection) => (
            <CollectionTile
              key={collection.id}
              collection={collection}
              isDefault={collection.is_default === true}
              onPress={onOpenCollection}
            />
          ))}
        </View>
      )}

      <View style={styles.mediaSectionHeader}>
        <Text style={styles.sectionTitle}>All media</Text>
        {mediaCount > 0 ? (
          <Text style={styles.mediaSectionCount}>
            {mediaCount} {mediaCount === 1 ? "item" : "items"}
          </Text>
        ) : null}
      </View>
    </View>
  );
}

/**
 * A half that failed, stated where that half would have been. A tonal card, no
 * stroke, so it reads as a slot of the page and not as an alert dialog.
 */
function InlineErrorCard({
  message,
  onRetry,
  retryAccessibilityLabel,
}: {
  message: string;
  onRetry: () => void;
  retryAccessibilityLabel: string;
}) {
  return (
    <View style={styles.inlineErrorCard}>
      <Ionicons
        name="cloud-offline-outline"
        size={28}
        color={Colors.textMuted}
      />
      <Text style={styles.inlineErrorText}>{message}</Text>
      <Pressable
        style={styles.retryButton}
        onPress={onRetry}
        accessibilityLabel={retryAccessibilityLabel}
        accessibilityRole="button"
      >
        <Ionicons name="refresh" size={18} color={Colors.onPrimary} />
        <Text style={styles.retryButtonText}>Retry</Text>
      </Pressable>
    </View>
  );
}

function EmptyLibraryState() {
  return (
    <View style={styles.emptyLibraryContainer}>
      <Ionicons
        name="albums-outline"
        size={48}
        color={Colors.textMuted}
        style={styles.emptyIcon}
      />
      <Text style={styles.emptyTitle}>Your library is empty</Text>
      <Text style={styles.emptyHint}>
        Share a link from any app, or import a file from the Inbox, and it shows
        up here.
      </Text>
    </View>
  );
}

function CollectionTile({
  collection,
  isDefault,
  onPress,
}: {
  collection: CollectionNode;
  /** The system default folder, tinted apart from the user's own collections. */
  isDefault: boolean;
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
          <Ionicons
            name="folder"
            size={42}
            color={isDefault ? DEFAULT_COLLECTION_TINT : Colors.primary}
          />
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

  // Floating search bar - minimum height meets touch target
  searchBarOverlay: {
    position: "absolute",
    left: Spacing.md,
    right: Spacing.md,
    zIndex: 10,
    // Shadow lives on the wrapper: the pill itself clips its children.
    ...Shadows.soft,
  },
  searchBar: {
    flexDirection: "row",
    alignItems: "center",
    borderRadius: BorderRadius.full,
    borderWidth: StyleSheet.hairlineWidth,
    borderColor: Colors.outlineVariant,
    height: SEARCH_BAR_HEIGHT,
    paddingHorizontal: Spacing.md,
    // Required for the blur to be clipped by the pill radius on iOS.
    overflow: "hidden",
  },
  searchBarAndroidFallback: {
    // Android fallback: a tint opaque enough to stay legible without blur.
    backgroundColor: "rgba(252, 249, 246, 0.92)",
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
    paddingTop: CONTENT_TOP_INSET,
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

  // Library (idle state): one scroll, the collections grid in the list header
  // and the media rows below. `MediaListCard` brings its own horizontal margin,
  // so the gutter lives on the header instead of on the content container.
  libraryListContent: {
    paddingTop: CONTENT_TOP_INSET,
    paddingBottom: Spacing.xxl,
  },
  libraryHeader: {
    paddingHorizontal: Spacing.md,
  },
  sectionTitle: {
    fontSize: Typography.headline.fontSize,
    fontWeight: "700",
    color: Colors.textMain,
    marginBottom: Spacing.md,
  },
  sectionHint: {
    fontSize: Typography.body.fontSize,
    color: Colors.textSubtle,
    lineHeight: Typography.body.lineHeight,
    marginBottom: Spacing.lg,
  },
  sectionLoadingRow: {
    alignItems: "center",
    justifyContent: "center",
    paddingVertical: Spacing.xl,
  },
  collectionsGrid: {
    flexDirection: "row",
    flexWrap: "wrap",
  },
  mediaSectionHeader: {
    flexDirection: "row",
    alignItems: "baseline",
    justifyContent: "space-between",
    gap: Spacing.sm,
  },
  mediaSectionCount: {
    fontSize: Typography.small.fontSize,
    color: Colors.textSubtle,
    marginBottom: Spacing.md,
  },

  // One half of the library failed to load. Tonal surface, no stroke: it is a
  // slot of the page, not an alert.
  inlineErrorCard: {
    alignItems: "center",
    gap: Spacing.sm,
    backgroundColor: Colors.surfaceContainer,
    borderRadius: BorderRadius.xl,
    padding: Spacing.lg,
    marginHorizontal: Spacing.md,
    marginBottom: Spacing.lg,
  },
  inlineErrorText: {
    fontSize: Typography.body.fontSize,
    color: Colors.textMain,
    textAlign: "center",
    lineHeight: Typography.body.lineHeight,
  },
  emptyLibraryContainer: {
    alignItems: "center",
    paddingHorizontal: Spacing.xl,
    paddingTop: Spacing.xl,
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
    paddingTop: CONTENT_TOP_INSET,
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
