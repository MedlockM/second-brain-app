import { useState, useEffect, useCallback, useMemo, useRef } from "react";
import {
  View,
  Text,
  StyleSheet,
  TextInput,
  FlatList,
  ActivityIndicator,
  Pressable,
  RefreshControl,
  type StyleProp,
  type ViewStyle,
} from "react-native";
import {
  SafeAreaView,
  useSafeAreaInsets,
} from "react-native-safe-area-context";
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
import {
  MediaListCard,
  COVER_WIDTH,
  COVER_HEIGHT,
} from "../../src/components/MediaListCard";
import {
  AnchoredContextMenu,
  type AnchorRect,
} from "../../src/components/AnchoredContextMenu";
import { RenameDialog } from "../../src/components/RenameDialog";
import { GlassSurface } from "../../src/components/GlassSurface";
import { useMediaActions } from "../../src/hooks/useMediaActions";
import { useCollectionActions } from "../../src/hooks/useCollectionActions";
import { getMediaTypeIcon } from "../../src/lib/mediaTypeDisplay";
import { Image } from "expo-image";
import {
  Colors,
  Typography,
  Spacing,
  BorderRadius,
  Shadows,
  TouchTarget,
} from "../../src/constants/theme";
import type { MediaListItem } from "../../src/types/media";
import type { Collection } from "../../src/types/organization";

// --- Layout constants ---

/**
 * The search bar floats above the content instead of sitting in the flow, so
 * the space it occupies has to be given back to the lists as top padding.
 */
const SEARCH_BAR_HEIGHT = TouchTarget.minimum;
const SEARCH_BAR_TOP = Spacing.sm;
const CONTENT_TOP_INSET = SEARCH_BAR_TOP + SEARCH_BAR_HEIGHT + Spacing.md;

// --- Helper functions ---

/**
 * The lifted copy of a pressed row or tile is inert — the context menu draws it
 * with `pointerEvents="none"` — but both components require a tap handler, so
 * these are the ones they get.
 */
const noopOpenMedia = () => {};
const noopOpenCollection = () => {};

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
 * The tab bar item itself carries no test id any more: task-350 handed the bar to
 * the system, and `NativeTabs` has no equivalent of `tabBarButtonTestID`.
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
  //
  // The collections are held as the flat list the endpoint returns, not as the
  // three pieces of a built tree: a rename then patches one string in one array
  // and the grid, the filter and the sub-collection counts all follow from it,
  // where three states would have to be kept in agreement by hand.
  const [folders, setFolders] = useState<Collection[]>([]);
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
      setFolders(await OrganizationService.getUserCollections());
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

  // Rebuilt from the flat list rather than stored: the parent links, the
  // alphabetical order and the sub-collection counts all come from one pass, so a
  // renamed collection lands in its new place in the grid on the next render.
  const collectionTree = useMemo(() => buildCollectionTree(folders), [folders]);

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

  const handleMediaDeleted = useCallback((mediaItemId: string) => {
    setMedia((current) =>
      current.filter((item) => item.media_item_id !== mediaItemId),
    );
  }, []);

  // Patched in place rather than refetched: the rename already returned the
  // stored title, and reloading the whole list to learn one string would also
  // scroll the user's position out from under them.
  const handleMediaRenamed = useCallback(
    (mediaItemId: string, title: string) => {
      setMedia((current) =>
        current.map((item) =>
          item.media_item_id === mediaItemId ? { ...item, title } : item,
        ),
      );
    },
    [],
  );

  // The long-press menu of a library row. A move needs nothing here: a moved
  // media stays in `All media` whatever collection it lands in, and the focus
  // refetch above already brings its new folder back.
  const mediaActions = useMediaActions({
    onDeleted: handleMediaDeleted,
    onRenamed: handleMediaRenamed,
  });

  // The copy of the pressed row the menu lifts above its blur. Same component
  // as the list row, with the list margins dropped: it is laid out on the rect
  // the row was measured at, which margins sit outside of.
  const renderMediaPreview = useCallback(
    (item: MediaListItem) => (
      <MediaListCard
        item={item}
        onPress={noopOpenMedia}
        style={styles.mediaPreviewCard}
      />
    ),
    [],
  );

  // Patched in place rather than refetched: the rename already returned the
  // stored name, and rebuilding the tree from `folders` puts the tile back in
  // alphabetical order without a round trip and without moving the scroll.
  const handleCollectionRenamed = useCallback(
    (collectionId: string, name: string) => {
      setFolders((current) =>
        current.map((folder) =>
          folder.id === collectionId ? { ...folder, name } : folder,
        ),
      );
    },
    [],
  );

  // A delete cannot be patched the same way: the backend took the whole subtree
  // and moved every source it held to the default collection. So the tiles that
  // are certainly gone leave at once — the deletion is confirmed, and keeping
  // them up for the length of a request would show collections that no longer
  // exist — and both halves are then refetched for what only the server knows:
  // the new media counts, and which collection each moved source now points at.
  const handleCollectionDeleted = useCallback(
    (collectionId: string) => {
      const deleted = new Set<string>([collectionId]);
      const collect = (node: CollectionNode) => {
        for (const child of node.children) {
          deleted.add(child.id);
          collect(child);
        }
      };
      const node = collectionTree.nodeById.get(collectionId);
      if (node) collect(node);

      setFolders((current) =>
        current.filter((folder) => !deleted.has(folder.id)),
      );
      void Promise.all([loadCollections(), loadMedia()]);
    },
    [collectionTree, loadCollections, loadMedia],
  );

  // The long-press menu of a collection tile. Two rows, no Move: reparenting a
  // collection has no picker anywhere in the app.
  const collectionActions = useCollectionActions({
    onDeleted: handleCollectionDeleted,
    onRenamed: handleCollectionRenamed,
  });

  // The copy of the pressed tile the menu lifts above its blur. Same component
  // as the grid tile, laid out on the rect the slot was measured at — hence the
  // full width and the dropped bottom margin, which that rect excludes.
  const renderCollectionPreview = useCallback(
    (collection: CollectionNode) => (
      <CollectionTile
        collection={collection}
        isDefault={collection.is_default === true}
        onPress={noopOpenCollection}
        style={styles.collectionTilePreview}
      />
    ),
    [],
  );

  // The default folder holds every media saved without an explicit collection.
  // It is excluded from `roots` by `buildCollectionTree` (which sorts them), so
  // pin it in front under its display label -- same pattern as the collections
  // explorer.
  const sortedCollections = useMemo(() => {
    const { roots, defaultCollection } = collectionTree;
    if (!defaultCollection) return roots;
    return [{ ...defaultCollection, name: DEFAULT_COLLECTION_LABEL }, ...roots];
  }, [collectionTree]);

  // Matched against what is typed, not against the debounced query: the filter
  // is a pass over a list already in memory, so it has no reason to wait on the
  // network round-trip the hits need. Every node of the tree, roots and children
  // alike: a nested collection matches like any other, which a roots-only list
  // cannot do.
  const matchingCollections = useMemo(
    () =>
      filterCollectionsByName(collectionTree.nodeById.values(), query),
    [collectionTree, query],
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
    /* `collapsable={false}`: under `NativeTabs` the scrollable UIKit insets and
       hangs the scroll-edge effect on is found by walking the first-subview chain
       down from the screen
       (`RNSScrollViewFinder.findScrollViewInFirstDescendantChainFrom` in
       react-native-screens). The list is two wrappers down that chain — this view,
       then the results area — and a flattened wrapper is one the view hierarchy
       no longer contains, so both are pinned. */
    <View style={styles.container} collapsable={false}>
      {/* Results Area -- scrolls underneath the floating search bar. First child
          on purpose: it holds the list the chain above has to reach. */}
      <SafeAreaView
        style={styles.resultsArea}
        edges={["top"]}
        collapsable={false}
      >
        {!query.trim() ? (
          <LibraryState
            collections={sortedCollections}
            collectionsLoading={collectionsLoading}
            collectionsError={collectionsError}
            onRetryCollections={handleRetryCollections}
            onOpenCollection={handleOpenCollection}
            onLongPressCollection={collectionActions.open}
            media={media}
            mediaLoading={mediaLoading}
            mediaError={mediaError}
            onRetryMedia={handleRetryMedia}
            onOpenMedia={handleOpenMedia}
            onLongPressMedia={mediaActions.open}
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
            onLongPressCollection={collectionActions.open}
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

      {/* Rendered at screen level, outside either body: the menu belongs to the
          screen's state, and mounting it inside a `FlatList` row would tie a
          modal to a cell the virtualizer is free to recycle. Two instances of
          one component, one per kind of target — at most one is ever visible,
          since a long press lands on a row or on a tile. */}
      <AnchoredContextMenu
        {...mediaActions.menuProps}
        renderPreview={renderMediaPreview}
      />
      <RenameDialog {...mediaActions.renameProps} />
      <AnchoredContextMenu
        {...collectionActions.menuProps}
        renderPreview={renderCollectionPreview}
      />
      <RenameDialog {...collectionActions.renameProps} />
    </View>
  );
}

// --- Sub-components ---

/**
 * Dismiss the keyboard as soon as either list is dragged.
 *
 * `on-drag` rather than `interactive`, and the same on both platforms: React
 * Native only implements `interactive` on iOS — on Android it degrades to
 * `none` — so picking it would leave Android with the very behaviour this
 * fixes, on the gesture that *is* this screen. `on-drag` also stays out of the
 * way of the library list's pull-to-refresh: the keyboard leaves on the first
 * movement and the gesture then belongs entirely to the `RefreshControl`,
 * where `interactive` would spend a downward drag re-raising the keyboard.
 *
 * Nothing is lost by closing it: the search field is a floating pill that stays
 * on screen, so one tap brings it back.
 */
const KEYBOARD_DISMISS_MODE = "on-drag" as const;

interface LibraryStateProps {
  collections: CollectionNode[];
  collectionsLoading: boolean;
  collectionsError: string | null;
  onRetryCollections: () => void;
  onOpenCollection: (collection: CollectionNode) => void;
  /** Opens the tile's actions menu. Ignored on the default collection's tile. */
  onLongPressCollection: (
    collection: CollectionNode,
    anchor: AnchorRect,
  ) => void;
  media: MediaListItem[];
  mediaLoading: boolean;
  mediaError: string | null;
  onRetryMedia: () => void;
  onOpenMedia: (mediaItemId: string) => void;
  /** Opens the row's actions menu. Library only — search results have none. */
  onLongPressMedia: (item: MediaListItem, anchor: AnchorRect) => void;
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
  onLongPressCollection,
  media,
  mediaLoading,
  mediaError,
  onRetryMedia,
  onOpenMedia,
  onLongPressMedia,
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
      keyboardDismissMode={KEYBOARD_DISMISS_MODE}
      renderItem={({ item }) => (
        <MediaListCard
          item={item}
          onPress={onOpenMedia}
          onLongPress={onLongPressMedia}
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
          onLongPressCollection={onLongPressCollection}
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
  onLongPressCollection,
  mediaCount,
}: {
  collections: CollectionNode[];
  collectionsLoading: boolean;
  collectionsError: string | null;
  onRetryCollections: () => void;
  onOpenCollection: (collection: CollectionNode) => void;
  onLongPressCollection: (
    collection: CollectionNode,
    anchor: AnchorRect,
  ) => void;
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
              onLongPress={onLongPressCollection}
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
  /** Opens the tile's actions menu. Ignored on the default collection's tile. */
  onLongPressCollection: (
    collection: CollectionNode,
    anchor: AnchorRect,
  ) => void;
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
  onLongPressCollection,
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
      keyboardDismissMode={KEYBOARD_DISMISS_MODE}
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
          onLongPressCollection={onLongPressCollection}
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
  onLongPressCollection,
  showCollections,
  resultCount,
}: {
  collections: CollectionNode[];
  collectionsLoading: boolean;
  collectionsError: string | null;
  onRetryCollections: () => void;
  onOpenCollection: (collection: CollectionNode) => void;
  onLongPressCollection: (
    collection: CollectionNode,
    anchor: AnchorRect,
  ) => void;
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
                  onLongPress={onLongPressCollection}
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
  onLongPress,
  style,
}: {
  collection: CollectionNode;
  /** The system default folder, tinted apart from the user's own collections. */
  isDefault: boolean;
  onPress: (collection: CollectionNode) => void;
  /**
   * Opens the tile's actions menu, with the slot's own window rect: the menu is
   * anchored to it and redraws the tile there.
   *
   * Never wired on the default collection, whatever the caller passes — the
   * backend refuses to rename or delete it, so the gesture is dropped here rather
   * than in each of the two grids, and the tile says nothing about a long press
   * it does not answer.
   */
  onLongPress?: (collection: CollectionNode, anchor: AnchorRect) => void;
  /**
   * Overrides the slot's outer box. Used by the context menu to redraw this tile
   * as a lifted copy on the measured rect — nothing else has a reason to touch it.
   */
  style?: StyleProp<ViewStyle>;
}) {
  const slotRef = useRef<View>(null);
  const longPress = isDefault ? undefined : onLongPress;

  // Measured on the gesture rather than on layout: the grid rides in the header
  // of a scrolling list, so the only rect the menu can trust is the one taken
  // when the press was recognised.
  const handleLongPress = () => {
    if (!longPress) return;
    slotRef.current?.measureInWindow((x, y, width, height) => {
      longPress(collection, { x, y, width, height });
    });
  };

  return (
    /* `collapsable={false}`: this view exists only to place the tile in the grid,
       and Android flattens such a view out of the hierarchy — where
       `measureInWindow` then has nothing to measure. */
    <View
      ref={slotRef}
      style={[styles.collectionTileSlot, style]}
      collapsable={false}
    >
      <Pressable
        style={({ pressed }) => [
          styles.collectionTile,
          pressed && styles.collectionTilePressed,
        ]}
        onPress={() => onPress(collection)}
        onLongPress={longPress ? handleLongPress : undefined}
        // The gesture is invisible, so a screen reader is told about it — and
        // only where it exists. `Pressable` keeps the tap and the long press
        // exclusive, so opening the menu never also opens the collection.
        accessibilityHint={
          longPress ? t("collectionActions.longPressHint") : undefined
        }
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

/**
 * One search result.
 *
 * The head of the card — cover on the left, meta row, title, creator — is
 * deliberately the silhouette of a `MediaListCard` row, down to the 112x63
 * cover it imports from it: the library list and the search results are the
 * same items, and until task-317 they looked like two different apps. The
 * matched transcript excerpt then sits *below* that head, full width.
 *
 * Cover on the left rather than a banner on top, even though this card carries
 * more text than a library row: a banner would make each result twice as tall
 * and put three of them on a screen where the list currently shows six or
 * seven. Search is a scanning surface, and the excerpt is what the user scans —
 * making room for it is worth more than a larger picture.
 *
 * The excerpt keeps its own highlighting (`parseHighlightSnippet`,
 * `cardSnippetMatch`): it is the one thing no other tile in the app has, and
 * the reason this card is allowed to be taller than a library row at all.
 */
function ResultCard({ hit, onPress }: { hit: SearchHit; onPress: () => void }) {
  // Keyed by media id rather than a bare boolean: a `FlatList` cell can be
  // handed a different hit, and a failure recorded for the previous one must
  // not hide the new one's cover.
  const [failedCoverId, setFailedCoverId] = useState<string | null>(null);

  // Indexed titles are derived server-side and are never empty (task-266), so
  // the client no longer invents "Untitled" -- a word that told the user nothing
  // and, being the same for every such hit, made results indistinguishable.
  const displayTitle = hit.title ?? "";
  const sourceLabel = getSourceLabel(hit.source_platform);
  const sourceIcon = getSourceIcon(hit.source_platform);
  const dateLabel = formatTimestamp(hit.created_at);
  const creator = hit.creator_name?.trim() ?? "";

  const coverUrl = hit.media_image?.trim() ?? "";
  const showCover =
    coverUrl.length > 0 && failedCoverId !== hit.media_item_id;

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
      accessibilityLabel={
        creator
          ? `${displayTitle}, ${creator}, ${sourceLabel}`
          : `${displayTitle}, ${sourceLabel}`
      }
      accessibilityRole="button"
    >
      <View style={styles.cardHead}>
        {/* The container is the fallback surface *and* the frame of the cover:
            one tonal rectangle either way, so a result with a picture and one
            without have the same silhouette. Never an empty grey box. */}
        <View style={styles.cardCoverContainer}>
          {showCover ? (
            <Image
              source={{
                uri: coverUrl,
                // The path identifies the picture: a re-hosted cover is signed
                // on read and its query string rotates on every search.
                cacheKey: coverUrl.split("?")[0],
              }}
              recyclingKey={hit.media_item_id}
              cachePolicy="memory-disk"
              contentFit="cover"
              transition={150}
              priority="low"
              style={styles.cardCover}
              onError={() => setFailedCoverId(hit.media_item_id)}
              accessible={false}
            />
          ) : (
            <Ionicons
              name={getMediaTypeIcon(hit.media_type ?? "unknown")}
              size={24}
              color={Colors.textMuted}
            />
          )}
        </View>

        <View style={styles.cardTextSection}>
          <View style={styles.cardHeader}>
            <View style={styles.cardSourceRow}>
              <Ionicons name={sourceIcon} size={14} color={Colors.primary} />
              <Text style={styles.cardSourceLabel}>{sourceLabel}</Text>
            </View>
            {dateLabel ? (
              <Text style={styles.cardDate}>{dateLabel}</Text>
            ) : null}
          </View>

          <Text style={styles.cardTitle} numberOfLines={2}>
            {displayTitle}
          </Text>

          {creator ? (
            <Text style={styles.cardCreator} numberOfLines={1}>
              {creator}
            </Text>
          ) : null}
        </View>
      </View>

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
    // Required for the material to be clipped by the pill radius on iOS.
    overflow: "hidden",
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
  // The row as the context menu redraws it: the list margins are what the
  // measured rect already excludes, so keeping them would shift the copy.
  mediaPreviewCard: {
    marginHorizontal: 0,
    marginBottom: 0,
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
  // The tile as the context menu redraws it: it fills the rect the slot was
  // measured at, and drops the bottom margin that rect already excludes.
  collectionTilePreview: {
    width: "100%",
    marginBottom: 0,
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
  // Cover and text sit side by side, exactly as in a library row; the excerpt
  // is the only thing that hangs below them.
  cardHead: {
    flexDirection: "row",
    gap: Spacing.md,
  },
  cardCoverContainer: {
    width: COVER_WIDTH,
    height: COVER_HEIGHT,
    borderRadius: BorderRadius.lg,
    backgroundColor: Colors.surfaceContainerLow,
    alignItems: "center",
    justifyContent: "center",
    overflow: "hidden",
  },
  cardCover: {
    width: "100%",
    height: "100%",
  },
  cardTextSection: {
    flex: 1,
    gap: 2,
  },
  cardHeader: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    gap: Spacing.sm,
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
  },
  cardCreator: {
    fontSize: Typography.small.fontSize,
    color: Colors.textSubtle,
  },
  cardSnippet: {
    fontSize: Typography.small.fontSize,
    color: Colors.textMuted,
    lineHeight: 18,
    marginTop: Spacing.sm,
  },
  cardSnippetMatch: {
    backgroundColor: Colors.highlight,
    color: Colors.onHighlight,
    fontWeight: "600",
  },
});
