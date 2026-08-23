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
import { filterCollectionsByName } from "../../src/lib/collectionSearch";
import { formatDate, t, tCount, useTranslation } from "../../src/i18n";
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
      return t("mediaType.unknownSource");
  }
}

function formatTimestamp(unixTimestamp: number): string {
  if (!unixTimestamp) return "";

  const date = new Date(unixTimestamp * 1000);
  const now = new Date();
  const diffMs = now.getTime() - date.getTime();
  const diffDays = Math.floor(diffMs / (1000 * 60 * 60 * 24));

  if (diffDays === 0) return t("time.today");
  if (diffDays === 1) return t("time.yesterday");
  if (diffDays < 7) return tCount("time.daysAgo", diffDays);

  // The active UI locale, never a hardcoded language tag: a French reader gets
  // 12 sept. where an English one gets Sep 12.
  return formatDate(date, { month: "short", day: "numeric" });
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
  // Subscribes the screen to the interface language: the copy below is resolved
  // at render time, so the tree has to redraw when the language changes.
  useTranslation();
  const router = useRouter();
  const insets = useSafeAreaInsets();

  // Search state. `settledQuery` is the query the hits on screen answer: it
  // stays behind what is typed while a request is in flight, which is what
  // tells the `All media` slot to show its spinner rather than a stale
  // "no matches".
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<SearchHit[]>([]);
  const [totalResults, setTotalResults] = useState(0);
  const [isLoading, setIsLoading] = useState(false);
  const [settledQuery, setSettledQuery] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [searchAttempt, setSearchAttempt] = useState(0);

  // Library state. The two halves are fetched by two independent requests and
  // carry their own loading and error flags: one failing must leave the other
  // rendered, with its own retry.
  const [collections, setCollections] = useState<CollectionNode[]>([]);
  const [defaultCollection, setDefaultCollection] =
    useState<CollectionNode | null>(null);
  // Every node of the tree, roots and children alike: the search filter matches
  // a nested collection like any other, which the roots-only list cannot do.
  const [allCollections, setAllCollections] = useState<CollectionNode[]>([]);
  const [collectionsLoading, setCollectionsLoading] = useState(true);
  const [collectionsError, setCollectionsError] = useState<string | null>(null);
  const [media, setMedia] = useState<MediaListItem[]>([]);
  const [mediaLoading, setMediaLoading] = useState(true);
  const [mediaError, setMediaError] = useState<string | null>(null);
  const [isRefreshing, setIsRefreshing] = useState(false);

  // Debounce the search query
  const debouncedQuery = useDebounce(query, 300);

  // Execute search when the debounced query changes, and on every retry the
  // `All media` slot asks for: bumping the attempt replays the effect on the
  // query already typed, which is the only thing a retry has to do.
  useEffect(() => {
    if (!isAuthenticated) return;

    // Algolia requires a non-empty query (min_length=1).
    const searchQuery = debouncedQuery.trim();
    if (!searchQuery) {
      return;
    }

    const performSearch = async () => {
      setIsLoading(true);
      setError(null);

      try {
        const response = await SearchService.searchTranscripts(searchQuery);

        setResults(response.hits);
        setTotalResults(response.found);
      } catch (err: unknown) {
        const message =
          err instanceof Error ? err.message : t("search.failed");
        setError(message);
        setResults([]);
        setTotalResults(0);
      } finally {
        setSettledQuery(searchQuery);
        setIsLoading(false);
      }
    };

    performSearch();
  }, [debouncedQuery, isAuthenticated, searchAttempt]);

  // Neither loader throws: each one owns its error state, so the caller can
  // always await both and only has its own spinner to clear.
  const loadCollections = useCallback(async () => {
    if (!isAuthenticated) return;

    try {
      const folders = await OrganizationService.getUserCollections();
      const tree = buildCollectionTree(folders);
      setCollections(tree.roots);
      setDefaultCollection(tree.defaultCollection);
      setAllCollections(Array.from(tree.nodeById.values()));
      setCollectionsError(null);
    } catch (err) {
      setCollectionsError(
        getFriendlyErrorMessage(err, {
          fallback: t("search.collectionsLoadFailed"),
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
          fallback: t("search.libraryLoadFailed"),
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
    setSettledQuery(null);
    setError(null);
  }, []);

  const handleQueryChange = useCallback((nextQuery: string) => {
    setQuery(nextQuery);
    if (!nextQuery.trim()) {
      setResults([]);
      setTotalResults(0);
      setSettledQuery(null);
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

  // Matched against what is typed, not against the debounced query: the filter
  // is a pass over a list already in memory, so it has no reason to wait on the
  // network round-trip the hits need.
  const matchingCollections = useMemo(
    () => filterCollectionsByName(allCollections, query),
    [allCollections, query],
  );

  const handleRetrySearch = useCallback(() => {
    setSearchAttempt((attempt) => attempt + 1);
  }, []);

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
        {!query.trim() ? (
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
        ) : (
          <SearchResultsState
            collections={matchingCollections}
            collectionsLoading={collectionsLoading}
            collectionsError={collectionsError}
            onRetryCollections={handleRetryCollections}
            onOpenCollection={handleOpenCollection}
            results={results}
            totalResults={totalResults}
            isPending={isLoading || settledQuery !== query.trim()}
            error={error}
            onRetrySearch={handleRetrySearch}
            query={debouncedQuery}
            onOpenMedia={handleOpenMedia}
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
            placeholder={t("search.placeholder")}
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
              accessibilityLabel={t("search.clearA11y")}
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
      retryAccessibilityLabel={t("search.retryLibraryA11y")}
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
            retryAccessibilityLabel={t("search.retryLibraryA11y")}
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
      <Text style={styles.sectionTitle}>{t("search.collections")}</Text>

      {collectionsLoading ? (
        <View style={styles.sectionLoadingRow}>
          <ActivityIndicator color={Colors.primary} />
        </View>
      ) : collectionsError ? (
        <InlineErrorCard
          message={collectionsError}
          onRetry={onRetryCollections}
          retryAccessibilityLabel={t("search.retryCollectionsA11y")}
        />
      ) : collections.length === 0 ? (
        <Text style={styles.sectionHint}>{t("search.noCollections")}</Text>
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
        <Text style={styles.sectionTitle}>{t("search.allMedia")}</Text>
        {mediaCount > 0 ? (
          <Text style={styles.mediaSectionCount}>
            {tCount("common.itemCount", mediaCount)}
          </Text>
        ) : null}
      </View>
    </View>
  );
}

interface SearchResultsStateProps {
  collections: CollectionNode[];
  collectionsLoading: boolean;
  collectionsError: string | null;
  onRetryCollections: () => void;
  onOpenCollection: (collection: CollectionNode) => void;
  results: SearchHit[];
  totalResults: number;
  /** The hits on screen do not answer what is typed yet. */
  isPending: boolean;
  error: string | null;
  onRetrySearch: () => void;
  /** The debounced query, so the "no matches" line names what was searched. */
  query: string;
  onOpenMedia: (mediaItemId: string) => void;
}

/**
 * What a typed query shows: the collections whose name matches it, then the
 * media the search engine returned — the same two headings as the library, in
 * the same single scroll.
 *
 * The two halves are answered by two different things, and that is the whole
 * point of the shape: the collections are filtered locally and are on screen
 * before the keystroke is over, while the hits are a debounced network call.
 * So neither the spinner nor the failure of that call is allowed to take the
 * screen any more — both are confined to the `All media` slot, and the
 * collections stay put underneath them. The full-height states are kept for
 * the one case where there is genuinely nothing else to show.
 */
function SearchResultsState({
  collections,
  collectionsLoading,
  collectionsError,
  onRetryCollections,
  onOpenCollection,
  results,
  totalResults,
  isPending,
  error,
  onRetrySearch,
  query,
  onOpenMedia,
}: SearchResultsStateProps) {
  // A folder list still loading, or one that failed, is not "zero matches": it
  // keeps its heading and states its own situation, exactly as in the library.
  const showCollections =
    collectionsLoading || collectionsError !== null || collections.length > 0;

  if (!showCollections && !isPending) {
    if (error) return <ErrorState message={error} />;
    if (results.length === 0) return <NoResultsState query={query} />;
  }

  // What stands in for the hits while there are none: the spinner of the
  // request in flight, the failure of that request with its retry, or the
  // statement that the search came back empty.
  const resultsPlaceholder = isPending ? (
    <View style={styles.sectionLoadingRow}>
      <ActivityIndicator color={Colors.primary} />
    </View>
  ) : error ? (
    <InlineErrorCard
      message={error}
      onRetry={onRetrySearch}
      retryAccessibilityLabel={t("search.retrySearchA11y")}
      style={styles.inlineErrorCardFlush}
    />
  ) : (
    <Text style={styles.slotHint}>{t("search.noMatches", { query })}</Text>
  );

  return (
    <FlatList
      testID="search-results-list"
      data={isPending ? [] : results}
      keyExtractor={(item) => item.media_item_id}
      keyboardShouldPersistTaps="handled"
      renderItem={({ item }) => (
        <ResultCard
          hit={item}
          onPress={() => onOpenMedia(item.media_item_id)}
        />
      )}
      contentContainerStyle={styles.resultsList}
      showsVerticalScrollIndicator={false}
      ListHeaderComponent={
        <SearchResultsHeader
          collections={collections}
          collectionsLoading={collectionsLoading}
          collectionsError={collectionsError}
          onRetryCollections={onRetryCollections}
          onOpenCollection={onOpenCollection}
          showCollections={showCollections}
          resultCount={!isPending && !error ? totalResults : null}
        />
      }
      ListEmptyComponent={resultsPlaceholder}
      ListFooterComponent={
        !isPending && !error && results.length > 0 ? (
          <Text style={styles.endOfResults}>{t("search.endOfResults")}</Text>
        ) : null
      }
    />
  );
}

function SearchResultsHeader({
  collections,
  collectionsLoading,
  collectionsError,
  onRetryCollections,
  onOpenCollection,
  showCollections,
  resultCount,
}: {
  collections: CollectionNode[];
  collectionsLoading: boolean;
  collectionsError: string | null;
  onRetryCollections: () => void;
  onOpenCollection: (collection: CollectionNode) => void;
  showCollections: boolean;
  /** `null` while the count would not describe what is on screen. */
  resultCount: number | null;
}) {
  return (
    <View>
      {showCollections ? (
        <>
          <Text style={styles.sectionTitle}>{t("search.collections")}</Text>

          {collectionsLoading ? (
            <View style={styles.sectionLoadingRow}>
              <ActivityIndicator color={Colors.primary} />
            </View>
          ) : collectionsError ? (
            <InlineErrorCard
              message={collectionsError}
              onRetry={onRetryCollections}
              retryAccessibilityLabel={t("search.retryCollectionsA11y")}
              style={styles.inlineErrorCardFlush}
            />
          ) : (
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
        </>
      ) : null}

      <View style={styles.mediaSectionHeader}>
        <Text style={[styles.sectionTitle, styles.searchSectionHeading]}>
          {t("search.allMedia")}
        </Text>
        {resultCount !== null && resultCount > 0 ? (
          <Text style={[styles.mediaSectionCount, styles.searchSectionHeading]}>
            {tCount("search.resultCount", resultCount)}
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
  style,
}: {
  message: string;
  onRetry: () => void;
  retryAccessibilityLabel: string;
  /** Set by callers whose container already carries the horizontal gutter. */
  style?: StyleProp<ViewStyle>;
}) {
  return (
    <View style={[styles.inlineErrorCard, style]}>
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
        <Text style={styles.retryButtonText}>{t("common.retry")}</Text>
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
      <Text style={styles.emptyTitle}>{t("search.emptyLibrary")}</Text>
      <Text style={styles.emptyHint}>{t("search.emptyLibraryHint")}</Text>
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
        accessibilityLabel={t("search.openCollectionA11y", {
          name: collection.name,
        })}
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
      <Text style={styles.emptyTitle}>{t("search.noResultsTitle")}</Text>
      <Text style={styles.emptyHint}>{t("search.noMatches", { query })}</Text>
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
      <Text style={styles.emptyTitle}>{t("common.somethingWentWrong")}</Text>
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
    marginEnd: Spacing.sm,
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
    marginStart: Spacing.sm,
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
  // The search body's content container spaces its children itself, so the
  // heading above the hits drops the bottom margin it carries in the library.
  searchSectionHeading: {
    marginBottom: 0,
  },
  slotHint: {
    fontSize: Typography.body.fontSize,
    color: Colors.textMuted,
    textAlign: "center",
    lineHeight: Typography.body.lineHeight,
    paddingVertical: Spacing.xl,
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
  // Same card inside a container that is already inset, where the card's own
  // horizontal margin would double the gutter.
  inlineErrorCardFlush: {
    marginHorizontal: 0,
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
