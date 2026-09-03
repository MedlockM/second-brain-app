import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  View,
  Text,
  StyleSheet,
  FlatList,
  ScrollView,
  ActivityIndicator,
  Pressable,
  type StyleProp,
  type ViewStyle,
} from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";
import { Ionicons } from "@expo/vector-icons";
import { useRouter, useLocalSearchParams, useFocusEffect } from "expo-router";
import { useAuth } from "../../../src/contexts/AuthContext";
import { OrganizationService } from "../../../src/services/organizationService";
import {
  ArtifactService,
  type ArtifactSummary,
} from "../../../src/services/artifactService";
import {
  ARTIFACT_TILES,
  type ArtifactTileState,
} from "../../../src/components/ArtifactTile";
import { ArtifactsPanel } from "../../../src/components/ArtifactsPanel";
import {
  AnchoredContextMenu,
  type AnchorRect,
} from "../../../src/components/AnchoredContextMenu";
import { RenameDialog } from "../../../src/components/RenameDialog";
import { ScreenTabs, type ScreenTab } from "../../../src/components/ScreenTabs";
import { useMediaActions } from "../../../src/hooks/useMediaActions";
import { describeArtifactRefusal } from "../../../src/lib/artifactRefusal";
import { mergeArtifactIntoHistory } from "../../../src/lib/artifactHistory";
import { sameSourceSet } from "../../../src/lib/artifactSources";
import { getFriendlyErrorMessage } from "../../../src/lib/getFriendlyErrorMessage";
import { getMediaTypeIcon } from "../../../src/lib/mediaTypeDisplay";
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
import { t, useTranslation } from "../../../src/i18n";
import { ScreenHeader, HeaderIconButton } from "../../../src/components/ScreenHeader";
import type { ArtifactType, MediaListItem, MediaType } from "../../../src/types/media";

/**
 * Collections explorer — single collection view, split in two intra-screen tabs
 * along the NotebookLM reference of task-263.
 *
 * **Sources** is a bare list: one line per entry, an icon and a truncated title,
 * sub-collections before media. The rich `MediaListCard` is deliberately not
 * used here — it belongs to the inbox and to search, where a vignette carries
 * metadata the user is scanning for; inside a collection the user is picking a
 * source out of a list they already know.
 *
 * **AI** generates artifacts over the **whole collection** (sub-collections
 * included, as the backend resolves the folder and all its descendants), then
 * lists what has already been produced. That list is an append-only history:
 * several entries of the same type coexist, each keeping the sources it was
 * generated over even after the collection has changed. Nothing here expires,
 * and nothing is regenerated automatically.
 *
 * A new entry only exists when the sources differ (task-322): an artifact is
 * keyed on the set of sources behind it, so asking again over an unchanged
 * collection answers the entry already stored. That is why the tab compares the
 * collection's current sources with the snapshot of the last artifact of each
 * type and only then offers to generate — a button that could not produce
 * anything would promise what no request delivers.
 */

const ARTIFACT_POLL_INTERVAL_MS = 3000;

/**
 * The lifted copy of a pressed row is inert — the context menu draws it with
 * `pointerEvents="none"` — but `SourceRow` requires a tap handler, so this is
 * the one it gets.
 */
const noopOpenMedia = () => {};

type CollectionTabKey = "sources" | "ai";

const COLLECTION_TABS: readonly ScreenTab<CollectionTabKey>[] = [
  { key: "sources", labelKey: "collection.tab.sources", icon: "documents-outline" },
  { key: "ai", labelKey: "collection.tab.ai", icon: "sparkles-outline" },
];

interface FolderListRow {
  kind: "folder";
  node: CollectionNode;
}

interface MediaListRow {
  kind: "media";
  media: MediaListItem;
}

type Row = FolderListRow | MediaListRow;

function buildInitialArtifactStates(): Record<ArtifactType, ArtifactTileState> {
  return ARTIFACT_TILES.reduce(
    (acc, tile) => {
      acc[tile.type] = { status: "idle", generationAvailable: true };
      return acc;
    },
    {} as Record<ArtifactType, ArtifactTileState>,
  );
}

export default function CollectionDetailScreen() {
  // Copy resolved on render: redraw when the interface language changes.
  useTranslation();
  const router = useRouter();
  const { isAuthenticated } = useAuth();
  const params = useLocalSearchParams<{ id: string; name?: string }>();
  const collectionId = params.id;

  const [activeTab, setActiveTab] = useState<CollectionTabKey>("sources");
  const [childFolders, setChildFolders] = useState<CollectionNode[]>([]);
  const [media, setMedia] = useState<MediaListItem[]>([]);
  // Every media a generation over this collection would read: descendants
  // included, which is exactly the scope the backend resolves. The Sources list
  // below shows only the direct children, so the two cannot share one state.
  const [scopeMediaIds, setScopeMediaIds] = useState<readonly string[]>([]);
  const [title, setTitle] = useState<string>(params.name ?? "Collection");
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    if (!isAuthenticated || !collectionId) return;
    setError(null);
    try {
      const [collections, folderMedia] = await Promise.all([
        OrganizationService.getUserCollections(),
        OrganizationService.getCollectionMedia(collectionId),
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
      setScopeMediaIds(folderMedia.map((item) => item.media_item_id));
    } catch (err) {
      setError(
        getFriendlyErrorMessage(err, {
          fallback: t("collection.loadFailed"),
        }),
      );
    }
  }, [isAuthenticated, collectionId]);

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

  const handleMediaDeleted = useCallback((mediaItemId: string) => {
    setMedia((current) =>
      current.filter((item) => item.media_item_id !== mediaItemId),
    );
  }, []);

  // Patched in place rather than refetched: the rename already returned the
  // stored title, and the row has to carry it before the user leaves the screen.
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

  // The long-press menu of a source row. A move out of this collection needs no
  // handling here: the focus refetch above runs when the picker is popped, and
  // the row is gone because the collection no longer holds that media.
  const mediaActions = useMediaActions({
    onDeleted: handleMediaDeleted,
    onRenamed: handleMediaRenamed,
  });

  // The copy of the pressed row the menu lifts above its blur: the same row,
  // with the list margins dropped so it lands exactly on its measured rect.
  const renderSourcePreview = useCallback(
    (item: MediaListItem) => (
      <SourceRow
        media={item}
        onPress={noopOpenMedia}
        style={styles.sourceRowPreview}
      />
    ),
    [],
  );

  const rows = useMemo<Row[]>(() => {
    return [
      ...childFolders.map((node): Row => ({ kind: "folder", node })),
      ...media.map((m): Row => ({ kind: "media", media: m })),
    ];
  }, [childFolders, media]);

  return (
    <SafeAreaView style={styles.container} edges={["top", "bottom"]}>
      <ScreenHeader
        title={title}
        leading={
          <HeaderIconButton
            icon="arrow-back"
            onPress={handleBack}
            accessibilityLabel={t("common.goBack")}
          />
        }
      />

      <View style={styles.tabsContainer}>
        <ScreenTabs
          tabs={COLLECTION_TABS}
          activeKey={activeTab}
          onChange={setActiveTab}
          accessibilityLabel={t("collection.sectionsA11y")}
        />
      </View>

      {isLoading ? (
        <View style={styles.centered}>
          <ActivityIndicator size="large" color={Colors.primary} />
          <Text style={styles.centeredText}>{t("common.loading")}</Text>
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
            accessibilityLabel={t("collection.retryA11y")}
            accessibilityRole="button"
          >
            <Ionicons name="refresh" size={18} color={Colors.onPrimary} />
            <Text style={styles.retryButtonText}>{t("common.retry")}</Text>
          </Pressable>
        </View>
      ) : activeTab === "sources" ? (
        <FlatList
          data={rows}
          keyExtractor={(row) =>
            row.kind === "folder" ? `folder:${row.node.id}` : `media:${row.media.media_item_id}`
          }
          renderItem={({ item }) =>
            item.kind === "folder" ? (
              <FolderRow node={item.node} onPress={handleOpenFolder} />
            ) : (
              <SourceRow
                media={item.media}
                onPress={handleOpenMedia}
                onLongPress={mediaActions.open}
              />
            )
          }
          ListHeaderComponent={
            rows.length > 0 ? (
              <Text style={styles.sectionTitle}>
                {t("collection.tab.sources")}
              </Text>
            ) : null
          }
          contentContainerStyle={styles.listContent}
          showsVerticalScrollIndicator={false}
          ListEmptyComponent={<EmptyState />}
          testID="collection-sources-list"
        />
      ) : (
        <AiTab collectionId={collectionId} scopeMediaIds={scopeMediaIds} />
      )}

      {/* Screen level, outside the list: the menu belongs to the screen's
          state, and mounting it inside a row would tie a modal to a cell the
          virtualizer is free to recycle. */}
      <AnchoredContextMenu
        {...mediaActions.menuProps}
        renderPreview={renderSourcePreview}
      />
      <RenameDialog {...mediaActions.renameProps} />
    </SafeAreaView>
  );
}

// --- AI tab ---

interface AiTabProps {
  collectionId: string;
  /** Every media the generation would read, descendants included. */
  scopeMediaIds: readonly string[];
}

/**
 * The collection's half of the AI tab: the data only. Everything visible is
 * `ArtifactsPanel`, shared verbatim with the AI tab of a media item so the two
 * cannot drift apart again.
 *
 * One request per scope serves both the tiles and the history:
 * `GET /api/artifacts?scope=folder` returns the history *and* the entries still
 * queued or generating, so the poll is a single call whatever the number of
 * artifact types in flight.
 *
 * That listing carries no `sources`, though — the index it reads does not project
 * them — so the snapshot each tile is compared against is fetched once per entry
 * from the detail route and kept: an entry is immutable, so one read per artifact
 * is all this ever costs.
 */
function AiTab({ collectionId, scopeMediaIds }: AiTabProps) {
  const router = useRouter();
  const { isAuthenticated } = useAuth();

  const [history, setHistory] = useState<ArtifactSummary[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [listError, setListError] = useState<string | null>(null);
  const [refusal, setRefusal] = useState<string | null>(null);
  // The types whose POST is in flight. The history cannot know about them yet —
  // the entry only exists once the request answers, and over a collection that
  // request reads every descendant source's transcript from S3 first. Without
  // this, the tap stays visually unanswered for the whole round-trip.
  const [requestsInFlight, setRequestsInFlight] = useState<readonly ArtifactType[]>(
    [],
  );
  // The sources an entry was generated over, by `artifact_id`. `null` records a
  // read that failed: it is not retried, and an unknown snapshot leaves the
  // generation offered — the backend is the authority and answers the stored
  // artifact anyway, so the worst case is a request that changes nothing.
  const [sourceSnapshots, setSourceSnapshots] = useState<
    Record<string, readonly string[] | null>
  >({});
  const mountedRef = useRef(true);
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);
  // Snapshot reads already in flight, so the poll cannot fire a second read of
  // the same entry while the first is still travelling.
  const snapshotsInFlightRef = useRef<Set<string>>(new Set());

  useEffect(() => {
    mountedRef.current = true;
    return () => {
      mountedRef.current = false;
      if (pollRef.current) clearInterval(pollRef.current);
    };
  }, []);

  const fetchHistory = useCallback(async (): Promise<ArtifactSummary[]> => {
    if (!isAuthenticated) return [];
    const response = await ArtifactService.listArtifacts("folder", collectionId);
    return response.artifacts;
  }, [isAuthenticated, collectionId]);

  const refresh = useCallback(async () => {
    try {
      const artifacts = await fetchHistory();
      if (!mountedRef.current) return;
      setHistory(artifacts);
      setListError(null);
    } catch (err) {
      if (!mountedRef.current) return;
      setListError(
        getFriendlyErrorMessage(err, {
          fallback: t("collection.artifactsLoadFailed"),
        }),
      );
    }
  }, [fetchHistory]);

  // `isLoading` starts true and is only ever cleared, from inside the async
  // body: the spinner belongs to the first fetch of a given scope, and `refresh`
  // is stable for as long as the scope is.
  useEffect(() => {
    let cancelled = false;
    void (async () => {
      await refresh();
      if (!cancelled) setIsLoading(false);
    })();
    return () => {
      cancelled = true;
    };
  }, [refresh]);

  // The list itself says whether anything is in flight, so the poll starts and
  // stops from its own content instead of from a separate flag.
  const hasInFlight = useMemo(
    () =>
      history.some(
        (artifact) =>
          artifact.status === "queued" || artifact.status === "generating",
      ),
    [history],
  );

  useEffect(() => {
    if (!hasInFlight) {
      if (pollRef.current) {
        clearInterval(pollRef.current);
        pollRef.current = null;
      }
      return;
    }
    if (pollRef.current) return;
    pollRef.current = setInterval(() => {
      void refresh();
    }, ARTIFACT_POLL_INTERVAL_MS);
  }, [hasInFlight, refresh]);

  // The newest entry per type. The list comes back newest-first, so the first
  // entry seen for a type wins.
  const newestByType = useMemo(() => {
    const newest = new Map<ArtifactType, ArtifactSummary>();
    for (const artifact of history) {
      if (!newest.has(artifact.artifact_type)) {
        newest.set(artifact.artifact_type, artifact);
      }
    }
    return newest;
  }, [history]);

  // One detail read per entry the tiles depend on, and only for entries whose
  // snapshot is still unknown: an artifact is immutable, so a snapshot read once
  // stays valid for as long as the screen lives.
  useEffect(() => {
    const missing = [...newestByType.values()].filter(
      (artifact) =>
        !(artifact.artifact_id in sourceSnapshots) &&
        !snapshotsInFlightRef.current.has(artifact.artifact_id),
    );
    if (missing.length === 0) return;
    for (const artifact of missing) {
      snapshotsInFlightRef.current.add(artifact.artifact_id);
    }
    void (async () => {
      const read = await Promise.all(
        missing.map(async (artifact) => {
          try {
            const detail = await ArtifactService.getArtifact(
              artifact.artifact_id,
            );
            return [
              artifact.artifact_id,
              detail.sources.map((source) => source.media_item_id),
            ] as const;
          } catch {
            // Recorded as unknown rather than retried: the tile then keeps
            // offering the generation, which is the harmless direction.
            return [artifact.artifact_id, null] as const;
          }
        }),
      );
      for (const [artifactId] of read) {
        snapshotsInFlightRef.current.delete(artifactId);
      }
      if (!mountedRef.current) return;
      setSourceSnapshots((current) => {
        const next = { ...current };
        for (const [artifactId, sources] of read) next[artifactId] = sources;
        return next;
      });
    })();
  }, [newestByType, sourceSnapshots]);

  // The tiles show the newest entry per type, and whether generating that type
  // again would produce anything.
  const tileStates = useMemo(() => {
    const states = buildInitialArtifactStates();
    for (const [type, artifact] of newestByType) {
      if (!(type in states)) continue;
      const snapshot = sourceSnapshots[artifact.artifact_id];
      states[type] = {
        status: artifact.status,
        error: artifact.error_code ?? undefined,
        // The collection can legitimately be generated again, but only over a
        // different set of sources (task-322): the same set answers this very
        // entry. A failed entry is generated again as-is, and a snapshot not
        // read yet counts as different — the button then does no harm, whereas
        // hiding it on a failed read would lock a real regeneration out.
        generationAvailable:
          artifact.status === "failed" ||
          snapshot === undefined ||
          snapshot === null ||
          !sameSourceSet(snapshot, scopeMediaIds),
      };
    }
    // A request still in flight wins over whatever the history says about that
    // type — a previous `ready` or `failed` entry included, since the button
    // that was just tapped belongs to the newest attempt. `queued` is the state
    // the entry itself comes back with, so the tile shows the spinner from the
    // tap frame and nothing changes visually when the POST answers. It also
    // takes the button out of the tile, which is what stops a second tap from
    // firing a second POST.
    for (const type of requestsInFlight) {
      states[type] = { status: "queued", generationAvailable: false };
    }
    return states;
  }, [newestByType, sourceSnapshots, scopeMediaIds, requestsInFlight]);

  const handleGenerate = useCallback(
    async (artifactType: ArtifactType) => {
      if (!isAuthenticated) return;
      setRefusal(null);
      // Before the POST, with nothing awaited in between: this is the update
      // that flips the tile, and it must land on the frame the finger lifts.
      setRequestsInFlight((current) =>
        current.includes(artifactType) ? current : [...current, artifactType],
      );

      try {
        const created = await ArtifactService.generateArtifact(
          "folder",
          collectionId,
          artifactType,
        );
        if (!mountedRef.current) return;
        // The POST answers the entry itself, so it goes straight into the
        // history: no list call, hence no eventually-consistent GSI read that
        // could come back without it and hide a running generation. It also
        // arms the poll immediately, from the returned status.
        setHistory((current) => mergeArtifactIntoHistory(current, created));
        // The answer carries its own source snapshot, so the tile settles
        // without a detail read — the reuse path included, where the entry
        // handed back is precisely the one covering these sources.
        setSourceSnapshots((current) => ({
          ...current,
          [created.artifact_id]: created.sources.map(
            (source) => source.media_item_id,
          ),
        }));
      } catch (err) {
        if (!mountedRef.current) return;
        setRefusal(describeArtifactRefusal(err, { scope: "folder" }));
      } finally {
        // Both paths: the merged entry carries a real status from here, and a
        // refusal has to give the button back — keeping the type in the set
        // would lock the tile on a spinner nothing will ever clear.
        if (mountedRef.current) {
          setRequestsInFlight((current) =>
            current.filter((type) => type !== artifactType),
          );
        }
      }
    },
    [isAuthenticated, collectionId],
  );

  const handleOpenArtifact = useCallback(
    (artifact: ArtifactSummary) => {
      router.push(`/artifacts/${artifact.artifact_id}`);
    },
    [router],
  );

  return (
    <ScrollView showsVerticalScrollIndicator={false} testID="collection-ai-tab">
      {/* Every source of the collection is already processed, so generation is
          always offered here — unlike a media item still being transcribed. */}
      <ArtifactsPanel
        tileStates={tileStates}
        sourceReady
        onGenerate={(artifactType) => void handleGenerate(artifactType)}
        refusal={refusal}
        refusalTestID="collection-ai-refusal"
        history={history}
        historyLoading={isLoading}
        historyError={listError}
        onRetryHistory={() => void refresh()}
        historyEmptyTestID="collection-ai-history-empty"
        onOpenArtifact={handleOpenArtifact}
        showSourceCount
      />
    </ScrollView>
  );
}

// --- Sub-components ---

interface FolderRowProps {
  node: CollectionNode;
  onPress: (node: CollectionNode) => void;
}

function FolderRow({ node, onPress }: FolderRowProps) {
  return (
    <Pressable
      style={({ pressed }) => [styles.sourceRow, pressed && styles.sourceRowPressed]}
      onPress={() => onPress(node)}
      testID={`collection-source-folder-${node.id}`}
      accessibilityLabel={`Open collection ${node.name}`}
      accessibilityRole="button"
    >
      <View style={styles.sourceIconContainer}>
        <Ionicons name="folder" size={20} color={Colors.primary} />
      </View>
      <Text style={styles.sourceTitle} numberOfLines={1}>
        {node.name}
      </Text>
      <Ionicons name="chevron-forward" size={18} color={Colors.textMuted} />
    </Pressable>
  );
}

interface SourceRowProps {
  media: MediaListItem;
  onPress: (mediaItemId: string) => void;
  /**
   * Opens the row's actions menu — move, rename or delete the source — with the
   * row's own window rect, which is what the menu anchors itself to. Omitted for
   * the inert copy the menu lifts above its blur.
   */
  onLongPress?: (media: MediaListItem, anchor: AnchorRect) => void;
  /**
   * Overrides the row's outer box, so the lifted copy can drop the list margins
   * the measured rect already excludes.
   */
  style?: StyleProp<ViewStyle>;
}

function SourceRow({ media, onPress, onLongPress, style }: SourceRowProps) {
  const mediaType = (media.media_type ?? "unknown") as MediaType;
  const rowRef = useRef<View>(null);

  // Measured on the gesture rather than on layout: a `FlatList` cell moves with
  // every scroll, so the only rect the menu can trust is the one taken when the
  // press was recognised.
  const handleLongPress = () => {
    if (!onLongPress) return;
    rowRef.current?.measureInWindow((x, y, width, height) => {
      onLongPress(media, { x, y, width, height });
    });
  };

  return (
    <Pressable
      ref={rowRef}
      style={({ pressed }) => [
        styles.sourceRow,
        pressed && styles.sourceRowPressed,
        style,
      ]}
      onPress={() => onPress(media.media_item_id)}
      onLongPress={onLongPress ? handleLongPress : undefined}
      testID={`collection-source-media-${media.media_item_id}`}
      accessibilityLabel={`Open ${media.title ?? "source"}`}
      // The gesture is invisible, so a screen reader is told about it — and only
      // where it exists. `Pressable` keeps the tap and the long press exclusive,
      // so opening the menu never also opens the media.
      accessibilityHint={
        onLongPress ? t("mediaCard.longPressHint") : undefined
      }
      accessibilityRole="button"
    >
      <View style={styles.sourceIconContainer}>
        <Ionicons
          name={getMediaTypeIcon(mediaType)}
          size={20}
          color={Colors.primary}
        />
      </View>
      <Text style={styles.sourceTitle} numberOfLines={1}>
        {media.title ?? media.source_url ?? "Source"}
      </Text>
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
      <Text style={styles.emptyTitle}>{t("collection.empty")}</Text>
      <Text style={styles.emptyHint}>{t("collection.emptyHint")}</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: Colors.background,
  },
  // One page gutter for the whole screen, `Spacing.lg`, the same the header
  // already used and the same `ArtifactsPanel` brings to the AI tab: the tab bar
  // and the source rows line up with the tiles under them.
  tabsContainer: {
    paddingHorizontal: Spacing.lg,
    paddingBottom: Spacing.md,
  },
  listContent: {
    paddingTop: Spacing.sm,
    paddingBottom: Spacing.xxl,
  },
  // The Sources list header. The uppercase muted caption stays confined to it —
  // the AI tab's headings are section openers and use `Typography.headline`.
  sectionTitle: {
    fontSize: Typography.label.fontSize,
    fontWeight: "700",
    color: Colors.textMuted,
    textTransform: "uppercase",
    letterSpacing: 0.5,
    marginHorizontal: Spacing.lg,
    marginBottom: Spacing.sm,
  },

  // Source row: one icon, one truncated title, nothing else.
  sourceRow: {
    flexDirection: "row",
    alignItems: "center",
    gap: Spacing.md,
    backgroundColor: Colors.surface,
    borderRadius: BorderRadius.xl,
    paddingHorizontal: Spacing.md,
    paddingVertical: Spacing.sm,
    marginHorizontal: Spacing.lg,
    marginBottom: Spacing.sm,
    minHeight: TouchTarget.comfortable,
    ...Shadows.soft,
  },
  sourceRowPressed: {
    transform: [{ scale: 0.98 }],
    opacity: 0.9,
  },
  // The row as the context menu redraws it: the list margins are what the
  // measured rect already excludes, so keeping them would shift the copy.
  sourceRowPreview: {
    marginHorizontal: 0,
    marginBottom: 0,
  },
  sourceIconContainer: {
    width: 36,
    height: 36,
    borderRadius: BorderRadius.md,
    backgroundColor: Colors.surfaceContainerLow,
    alignItems: "center",
    justifyContent: "center",
  },
  sourceTitle: {
    flex: 1,
    fontSize: Typography.body.fontSize,
    fontWeight: "600",
    color: Colors.textMain,
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
