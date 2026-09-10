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
  buildFolderTree,
  DEFAULT_FOLDER_LABEL,
  DEFAULT_FOLDER_TINT,
  type FolderNode,
} from "../../src/lib/folderTree";
import { filterFoldersByName } from "../../src/lib/folderSearch";
import { t, tCount, useTranslation } from "../../src/i18n";
import {
  MediaListCard,
  type MediaCardItem,
} from "../../src/components/MediaListCard";
import {
  AnchoredContextMenu,
  type AnchorRect,
} from "../../src/components/AnchoredContextMenu";
import { RenameDialog } from "../../src/components/RenameDialog";
import { GlassSurface } from "../../src/components/GlassSurface";
import { useMediaActions } from "../../src/hooks/useMediaActions";
import { useFolderActions } from "../../src/hooks/useFolderActions";
import {
  Colors,
  Typography,
  Spacing,
  BorderRadius,
  Shadows,
  TouchTarget,
} from "../../src/constants/theme";
import type { MediaListItem } from "../../src/types/media";
import type { Folder } from "../../src/types/organization";

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
const noopOpenFolder = () => {};

/**
 * One media row of either list this screen holds: a library row, or a search hit
 * read as one.
 *
 * Both are drawn by `MediaListCard` and both are acted on by one `useMediaActions`
 * (task-375), so they are one type here rather than two shapes each list converts
 * at its own render. The two extras only a hit ever carries travel *on* the row
 * rather than beside it, because the context menu is handed the target and
 * nothing else — that is what lets it redraw the pressed vignette, excerpt
 * included, instead of a shorter copy of it.
 */
type MediaRow = MediaCardItem & {
  /** Where the media is filed, so "Move" opens on its current folder. */
  folder_id?: string | null;
  /** The matched transcript, `<mark>`-tagged. Search hits only. */
  excerpt?: string | null;
  /**
   * The index kept this hit after the media was deleted: nothing is left to
   * rename, move or delete, so the row is offered no long press. Absent on a
   * library row, which exists by definition.
   */
  isOrphan?: boolean;
};

/**
 * A search hit, read as the library row it is a hit on.
 *
 * Every field but the excerpt comes from `user_media` server-side, which is why
 * this is a plain projection and not a conversion: the hit already *is* the row,
 * plus where in the transcript the query matched.
 */
function hitToRow(hit: SearchHit): MediaRow {
  return {
    media_item_id: hit.media_item_id,
    title: hit.title,
    creator_name: hit.creator_name,
    media_type: hit.media_type,
    source_url: hit.source_url,
    media_image: hit.media_image,
    created_at: hit.created_at,
    updated_at: hit.updated_at,
    folder_id: hit.folder_id,
    // The first excerpt, which is the transcript match whenever there is one:
    // the backend orders the transcript snippet ahead of the title highlight.
    excerpt: hit.highlights.length > 0 ? hit.highlights[0].snippet : null,
    isOrphan: !hit.in_library,
  };
}

// --- Main Screen Component ---

/**
 * The library tab: everything the user saved, plus the search over it.
 *
 * Two bodies, mutually exclusive, switched by the query in the floating pill.
 * With nothing typed it shows the library — the folders *and* every media
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
  // Held as rows, not as hits: the list is patched in place by a rename and by a
  // deletion, exactly as `media` is, and a screen holding one list of hits and
  // one of rows would need two patches for each.
  const [results, setResults] = useState<MediaRow[]>([]);
  const [totalResults, setTotalResults] = useState(0);
  const [isLoading, setIsLoading] = useState(false);
  const [settledQuery, setSettledQuery] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [searchAttempt, setSearchAttempt] = useState(0);

  // Library state. The two halves are fetched by two independent requests and
  // carry their own loading and error flags: one failing must leave the other
  // rendered, with its own retry.
  //
  // The folders are held as the flat list the endpoint returns, not as the
  // three pieces of a built tree: a rename then patches one string in one array
  // and the grid, the filter and the subfolder counts all follow from it,
  // where three states would have to be kept in agreement by hand.
  const [folders, setFolders] = useState<Folder[]>([]);
  const [foldersLoading, setFoldersLoading] = useState(true);
  const [foldersError, setFoldersError] = useState<string | null>(null);
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

        setResults(response.hits.map(hitToRow));
        setTotalResults(response.found);
      } catch (err: unknown) {
        // `err.message` here is whatever the search API put in its `detail`, in
        // English and written for us. The reader gets a sentence from the
        // catalogue instead.
        setError(getFriendlyErrorMessage(err, { fallback: t("search.failed") }));
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
  const loadFolders = useCallback(async () => {
    if (!isAuthenticated) return;

    try {
      setFolders(await OrganizationService.getUserFolders());
      setFoldersError(null);
    } catch (err) {
      setFoldersError(
        getFriendlyErrorMessage(err, {
          fallback: t("search.foldersLoadFailed"),
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
      void loadFolders().finally(() => {
        if (active) setFoldersLoading(false);
      });
      void loadMedia().finally(() => {
        if (active) setMediaLoading(false);
      });
      return () => {
        active = false;
      };
    }, [loadFolders, loadMedia]),
  );

  // Rebuilt from the flat list rather than stored: the parent links, the
  // alphabetical order and the subfolder counts all come from one pass, so a
  // renamed folder lands in its new place in the grid on the next render.
  const folderTree = useMemo(() => buildFolderTree(folders), [folders]);

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

  const handleOpenFolder = useCallback(
    (folder: FolderNode) => {
      router.push({
        pathname: "/media/folders/[id]",
        params: { id: folder.id, name: folder.name },
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

  // Both lists at once, and that is the point: they show the same media, so a
  // deletion confirmed from a search hit must not be undone by clearing the
  // query. Only ever called once the backend has answered — a network failure
  // leaves the media where it is, in both lists.
  const handleMediaDeleted = useCallback((mediaItemId: string) => {
    setMedia((current) =>
      current.filter((item) => item.media_item_id !== mediaItemId),
    );
    setResults((current) =>
      current.filter((row) => row.media_item_id !== mediaItemId),
    );
  }, []);

  // Patched in place rather than refetched: the rename already returned the
  // stored title, and reloading the whole list to learn one string would also
  // scroll the user's position out from under them. Both lists again, for the
  // same reason as above.
  const handleMediaRenamed = useCallback(
    (mediaItemId: string, title: string) => {
      setMedia((current) =>
        current.map((item) =>
          item.media_item_id === mediaItemId ? { ...item, title } : item,
        ),
      );
      setResults((current) =>
        current.map((row) =>
          row.media_item_id === mediaItemId ? { ...row, title } : row,
        ),
      );
    },
    [],
  );

  // The long-press menu of a media row, whichever list it was pressed in. A move
  // needs nothing here: a moved media stays in both lists whatever folder it
  // lands in, and the focus refetch above already brings its new folder back.
  const mediaActions = useMediaActions<MediaRow>({
    onDeleted: handleMediaDeleted,
    onRenamed: handleMediaRenamed,
  });

  // The copy of the pressed row the menu lifts above its blur. Same component
  // as the list row, with the list margins dropped: it is laid out on the rect
  // the row was measured at, which margins sit outside of. The excerpt is passed
  // back too — without it the copy would be shorter than the vignette under it,
  // and the mismatch is exactly what the lift is supposed to hide.
  const renderMediaPreview = useCallback(
    (row: MediaRow) => (
      <MediaListCard
        item={row}
        excerpt={row.excerpt}
        onPress={noopOpenMedia}
        style={styles.mediaPreviewCard}
      />
    ),
    [],
  );

  // Patched in place rather than refetched: the rename already returned the
  // stored name, and rebuilding the tree from `folders` puts the tile back in
  // alphabetical order without a round trip and without moving the scroll.
  const handleFolderRenamed = useCallback(
    (folderId: string, name: string) => {
      setFolders((current) =>
        current.map((folder) =>
          folder.id === folderId ? { ...folder, name } : folder,
        ),
      );
    },
    [],
  );

  // A delete cannot be patched the same way: the backend took the whole subtree
  // and moved every source it held to the default folder. So the tiles that
  // are certainly gone leave at once — the deletion is confirmed, and keeping
  // them up for the length of a request would show folders that no longer
  // exist — and both halves are then refetched for what only the server knows:
  // the new media counts, and which folder each moved source now points at.
  const handleFolderDeleted = useCallback(
    (folderId: string) => {
      const deleted = new Set<string>([folderId]);
      const collect = (node: FolderNode) => {
        for (const child of node.children) {
          deleted.add(child.id);
          collect(child);
        }
      };
      const node = folderTree.nodeById.get(folderId);
      if (node) collect(node);

      setFolders((current) =>
        current.filter((folder) => !deleted.has(folder.id)),
      );
      void Promise.all([loadFolders(), loadMedia()]);
    },
    [folderTree, loadFolders, loadMedia],
  );

  // The long-press menu of a folder tile. Two rows, no Move: reparenting a
  // folder has no picker anywhere in the app.
  const folderActions = useFolderActions({
    onDeleted: handleFolderDeleted,
    onRenamed: handleFolderRenamed,
  });

  // The copy of the pressed tile the menu lifts above its blur. Same component
  // as the grid tile, laid out on the rect the slot was measured at — hence the
  // full width and the dropped bottom margin, which that rect excludes.
  const renderFolderPreview = useCallback(
    (folder: FolderNode) => (
      <FolderTile
        folder={folder}
        isDefault={folder.is_default === true}
        onPress={noopOpenFolder}
        style={styles.folderTilePreview}
      />
    ),
    [],
  );

  // The default folder holds every media saved without an explicit folder.
  // It is excluded from `roots` by `buildFolderTree` (which sorts them), so
  // pin it in front under its display label -- same pattern as the folders
  // explorer.
  const sortedFolders = useMemo(() => {
    const { roots, defaultFolder } = folderTree;
    if (!defaultFolder) return roots;
    return [{ ...defaultFolder, name: DEFAULT_FOLDER_LABEL }, ...roots];
  }, [folderTree]);

  // Matched against what is typed, not against the debounced query: the filter
  // is a pass over a list already in memory, so it has no reason to wait on the
  // network round-trip the hits need. Every node of the tree, roots and children
  // alike: a nested folder matches like any other, which a roots-only list
  // cannot do.
  const matchingFolders = useMemo(
    () =>
      filterFoldersByName(folderTree.nodeById.values(), query),
    [folderTree, query],
  );

  const handleRetrySearch = useCallback(() => {
    setSearchAttempt((attempt) => attempt + 1);
  }, []);

  const handleRetryFolders = useCallback(() => {
    setFoldersLoading(true);
    void loadFolders().finally(() => setFoldersLoading(false));
  }, [loadFolders]);

  const handleRetryMedia = useCallback(() => {
    setMediaLoading(true);
    void loadMedia().finally(() => setMediaLoading(false));
  }, [loadMedia]);

  // Pull-to-refresh reloads both halves: the gesture is on the one scroll that
  // carries them, so refreshing only one of them would be a lie.
  const handleRefresh = useCallback(() => {
    setIsRefreshing(true);
    void Promise.all([loadFolders(), loadMedia()]).finally(() =>
      setIsRefreshing(false),
    );
  }, [loadFolders, loadMedia]);

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
            folders={sortedFolders}
            foldersLoading={foldersLoading}
            foldersError={foldersError}
            onRetryFolders={handleRetryFolders}
            onOpenFolder={handleOpenFolder}
            onLongPressFolder={folderActions.open}
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
            folders={matchingFolders}
            foldersLoading={foldersLoading}
            foldersError={foldersError}
            onRetryFolders={handleRetryFolders}
            onOpenFolder={handleOpenFolder}
            onLongPressFolder={folderActions.open}
            results={results}
            totalResults={totalResults}
            isPending={isLoading || settledQuery !== query.trim()}
            error={error}
            onRetrySearch={handleRetrySearch}
            query={debouncedQuery}
            onOpenMedia={handleOpenMedia}
            onLongPressMedia={mediaActions.open}
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
        {...folderActions.menuProps}
        renderPreview={renderFolderPreview}
      />
      <RenameDialog {...folderActions.renameProps} />
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
  folders: FolderNode[];
  foldersLoading: boolean;
  foldersError: string | null;
  onRetryFolders: () => void;
  onOpenFolder: (folder: FolderNode) => void;
  /** Opens the tile's actions menu. Ignored on the default folder's tile. */
  onLongPressFolder: (
    folder: FolderNode,
    anchor: AnchorRect,
  ) => void;
  media: MediaRow[];
  mediaLoading: boolean;
  mediaError: string | null;
  onRetryMedia: () => void;
  onOpenMedia: (mediaItemId: string) => void;
  /** Opens the row's actions menu — the same one the search results open. */
  onLongPressMedia: (item: MediaRow, anchor: AnchorRect) => void;
  isRefreshing: boolean;
  onRefresh: () => void;
}

/**
 * The library: the folders and every saved media item, in **one vertical
 * scroll** — the folders grid rides in the list header, the media rows are
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
 * folders scrolls past them to reach the media — acceptable, because the
 * grid is three tiles wide and the list is what the scroll is for.
 */
function LibraryState({
  folders,
  foldersLoading,
  foldersError,
  onRetryFolders,
  onOpenFolder,
  onLongPressFolder,
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
      contentContainerStyle={styles.listContent}
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
          folders={folders}
          foldersLoading={foldersLoading}
          foldersError={foldersError}
          onRetryFolders={onRetryFolders}
          onOpenFolder={onOpenFolder}
          onLongPressFolder={onLongPressFolder}
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
  folders,
  foldersLoading,
  foldersError,
  onRetryFolders,
  onOpenFolder,
  onLongPressFolder,
  mediaCount,
}: {
  folders: FolderNode[];
  foldersLoading: boolean;
  foldersError: string | null;
  onRetryFolders: () => void;
  onOpenFolder: (folder: FolderNode) => void;
  onLongPressFolder: (
    folder: FolderNode,
    anchor: AnchorRect,
  ) => void;
  mediaCount: number;
}) {
  return (
    <View style={styles.listHeader}>
      <Text style={styles.sectionTitle}>{t("search.folders")}</Text>

      {foldersLoading ? (
        <View style={styles.sectionLoadingRow}>
          <ActivityIndicator color={Colors.primary} />
        </View>
      ) : foldersError ? (
        <InlineErrorCard
          message={foldersError}
          onRetry={onRetryFolders}
          retryAccessibilityLabel={t("search.retryFoldersA11y")}
        />
      ) : folders.length === 0 ? (
        <Text style={styles.sectionHint}>{t("search.noFolders")}</Text>
      ) : (
        // Laid out by wrapping rather than by a nested FlatList: a vertical
        // virtualized list inside another one is unsupported, and the number of
        // folders a user can own is bounded by the backend folder cap.
        <View style={styles.foldersGrid}>
          {folders.map((folder) => (
            <FolderTile
              key={folder.id}
              folder={folder}
              isDefault={folder.is_default === true}
              onPress={onOpenFolder}
              onLongPress={onLongPressFolder}
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
  folders: FolderNode[];
  foldersLoading: boolean;
  foldersError: string | null;
  onRetryFolders: () => void;
  onOpenFolder: (folder: FolderNode) => void;
  /** Opens the tile's actions menu. Ignored on the default folder's tile. */
  onLongPressFolder: (
    folder: FolderNode,
    anchor: AnchorRect,
  ) => void;
  results: MediaRow[];
  totalResults: number;
  /** The hits on screen do not answer what is typed yet. */
  isPending: boolean;
  error: string | null;
  onRetrySearch: () => void;
  /** The debounced query, so the "no matches" line names what was searched. */
  query: string;
  onOpenMedia: (mediaItemId: string) => void;
  /** Opens the row's actions menu — the same one the library rows open. */
  onLongPressMedia: (item: MediaRow, anchor: AnchorRect) => void;
}

/**
 * What a typed query shows: the folders whose name matches it, then the
 * media the search engine returned — the same two headings as the library, in
 * the same single scroll.
 *
 * The two halves are answered by two different things, and that is the whole
 * point of the shape: the folders are filtered locally and are on screen
 * before the keystroke is over, while the hits are a debounced network call.
 * So neither the spinner nor the failure of that call is allowed to take the
 * screen any more — both are confined to the `All media` slot, and the
 * folders stay put underneath them. The full-height states are kept for
 * the one case where there is genuinely nothing else to show.
 *
 * A hit is rendered by the very component the library rows are, with the very
 * long-press menu (task-375): the two lists show the same media, and a media
 * found by searching is as much an object to file as one found by scrolling.
 */
function SearchResultsState({
  folders,
  foldersLoading,
  foldersError,
  onRetryFolders,
  onOpenFolder,
  onLongPressFolder,
  results,
  totalResults,
  isPending,
  error,
  onRetrySearch,
  query,
  onOpenMedia,
  onLongPressMedia,
}: SearchResultsStateProps) {
  // A folder list still loading, or one that failed, is not "zero matches": it
  // keeps its heading and states its own situation, exactly as in the library.
  const showFolders =
    foldersLoading || foldersError !== null || folders.length > 0;

  if (!showFolders && !isPending) {
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
        <MediaListCard
          item={item}
          excerpt={item.excerpt}
          onPress={onOpenMedia}
          // Everything but a media the index outlived: there is nothing to
          // rename, move or delete on a row the library no longer holds.
          onLongPress={item.isOrphan ? undefined : onLongPressMedia}
          testID="search-result-card"
        />
      )}
      contentContainerStyle={styles.listContent}
      showsVerticalScrollIndicator={false}
      ListHeaderComponent={
        <SearchResultsHeader
          folders={folders}
          foldersLoading={foldersLoading}
          foldersError={foldersError}
          onRetryFolders={onRetryFolders}
          onOpenFolder={onOpenFolder}
          onLongPressFolder={onLongPressFolder}
          showFolders={showFolders}
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
  folders,
  foldersLoading,
  foldersError,
  onRetryFolders,
  onOpenFolder,
  onLongPressFolder,
  showFolders,
  resultCount,
}: {
  folders: FolderNode[];
  foldersLoading: boolean;
  foldersError: string | null;
  onRetryFolders: () => void;
  onOpenFolder: (folder: FolderNode) => void;
  onLongPressFolder: (
    folder: FolderNode,
    anchor: AnchorRect,
  ) => void;
  showFolders: boolean;
  /** `null` while the count would not describe what is on screen. */
  resultCount: number | null;
}) {
  return (
    <View style={styles.listHeader}>
      {showFolders ? (
        <>
          <Text style={styles.sectionTitle}>{t("search.folders")}</Text>

          {foldersLoading ? (
            <View style={styles.sectionLoadingRow}>
              <ActivityIndicator color={Colors.primary} />
            </View>
          ) : foldersError ? (
            <InlineErrorCard
              message={foldersError}
              onRetry={onRetryFolders}
              retryAccessibilityLabel={t("search.retryFoldersA11y")}
              style={styles.inlineErrorCardFlush}
            />
          ) : (
            <View style={styles.foldersGrid}>
              {folders.map((folder) => (
                <FolderTile
                  key={folder.id}
                  folder={folder}
                  isDefault={folder.is_default === true}
                  onPress={onOpenFolder}
                  onLongPress={onLongPressFolder}
                />
              ))}
            </View>
          )}
        </>
      ) : null}

      <View style={styles.mediaSectionHeader}>
        <Text style={styles.sectionTitle}>{t("search.allMedia")}</Text>
        {resultCount !== null && resultCount > 0 ? (
          <Text style={styles.mediaSectionCount}>
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

function FolderTile({
  folder,
  isDefault,
  onPress,
  onLongPress,
  style,
}: {
  folder: FolderNode;
  /** The system default folder, tinted apart from the user's own folders. */
  isDefault: boolean;
  onPress: (folder: FolderNode) => void;
  /**
   * Opens the tile's actions menu, with the slot's own window rect: the menu is
   * anchored to it and redraws the tile there.
   *
   * Never wired on the default folder, whatever the caller passes — the
   * backend refuses to rename or delete it, so the gesture is dropped here rather
   * than in each of the two grids, and the tile says nothing about a long press
   * it does not answer.
   */
  onLongPress?: (folder: FolderNode, anchor: AnchorRect) => void;
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
      longPress(folder, { x, y, width, height });
    });
  };

  return (
    /* `collapsable={false}`: this view exists only to place the tile in the grid,
       and Android flattens such a view out of the hierarchy — where
       `measureInWindow` then has nothing to measure. */
    <View
      ref={slotRef}
      style={[styles.folderTileSlot, style]}
      collapsable={false}
    >
      <Pressable
        style={({ pressed }) => [
          styles.folderTile,
          pressed && styles.folderTilePressed,
        ]}
        onPress={() => onPress(folder)}
        onLongPress={longPress ? handleLongPress : undefined}
        // The gesture is invisible, so a screen reader is told about it — and
        // only where it exists. `Pressable` keeps the tap and the long press
        // exclusive, so opening the menu never also opens the folder.
        accessibilityHint={
          longPress ? t("folderActions.longPressHint") : undefined
        }
        accessibilityLabel={t("search.openFolderA11y", {
          name: folder.name,
        })}
        accessibilityRole="button"
      >
        <View style={styles.folderIcon}>
          <Ionicons
            name="folder"
            size={42}
            color={isDefault ? DEFAULT_FOLDER_TINT : Colors.primary}
          />
        </View>
        <Text style={styles.folderName} numberOfLines={2}>
          {folder.name}
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
  endOfResults: {
    fontSize: Typography.small.fontSize,
    color: Colors.textMuted,
    textAlign: "center",
    marginTop: Spacing.lg,
    paddingHorizontal: Spacing.md,
  },

  // One content container for both bodies, because both are the same scroll of
  // the same vignette: the folders grid in the list header, media rows below.
  // No horizontal padding and no `gap` — `MediaListCard` brings its own margins,
  // and a container adding to them doubled the gutter on the results side.
  listContent: {
    paddingTop: CONTENT_TOP_INSET,
    paddingBottom: Spacing.xxl,
  },
  // The row as the context menu redraws it: the list margins are what the
  // measured rect already excludes, so keeping them would shift the copy.
  mediaPreviewCard: {
    marginHorizontal: 0,
    marginBottom: 0,
  },
  // The gutter the rows carry themselves, applied to whichever header rides
  // above them.
  listHeader: {
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
  // The grid owns the space *between* its rows, and separately the space after
  // its last one -- two gaps a per-tile bottom margin used to conflate, which is
  // what made the rows drift apart: the margin had to be large enough to break
  // from the next section heading, so every row inherited a section-sized gap.
  //
  // Only `rowGap`: the columns are sized in percentages, so a `columnGap` would
  // push 3 x 33.333% + 2 x gap past the line and wrap the third tile away. The
  // column gutter stays the slot's own horizontal padding.
  foldersGrid: {
    flexDirection: "row",
    flexWrap: "wrap",
    rowGap: Spacing.sm,
    marginBottom: Spacing.xl,
  },
  slotHint: {
    fontSize: Typography.body.fontSize,
    color: Colors.textMuted,
    textAlign: "center",
    lineHeight: Typography.body.lineHeight,
    paddingVertical: Spacing.xl,
    paddingHorizontal: Spacing.md,
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
  folderTileSlot: {
    width: "33.333%",
    paddingHorizontal: 6,
  },
  // The tile as the context menu redraws it: it fills the rect the slot was
  // measured at, which the grid's own row gap falls outside of.
  folderTilePreview: {
    width: "100%",
  },
  // No height of its own: the box hugs the icon and the label, so a name that
  // fits on one line no longer leaves the height of a second one empty beneath
  // it, and a name that needs two still gets them. Tiles of the same row keep
  // aligning -- each slot stretches to the tallest tile of its row and holds its
  // content at the top.
  folderTile: {
    alignItems: "center",
    paddingVertical: Spacing.sm,
  },
  folderTilePressed: {
    opacity: 0.75,
    transform: [{ scale: 0.97 }],
  },
  folderIcon: {
    width: 64,
    height: 58,
    alignItems: "center",
    justifyContent: "center",
    marginBottom: Spacing.xs,
  },
  folderName: {
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
});
