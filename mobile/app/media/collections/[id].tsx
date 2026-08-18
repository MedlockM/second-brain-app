import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  View,
  Text,
  StyleSheet,
  FlatList,
  ScrollView,
  ActivityIndicator,
  Pressable,
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
import { ScreenTabs, type ScreenTab } from "../../../src/components/ScreenTabs";
import { describeArtifactRefusal } from "../../../src/lib/artifactRefusal";
import { mergeArtifactIntoHistory } from "../../../src/lib/artifactHistory";
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
 * several entries of the same type coexist, each keeping the source count it was
 * generated over even after the collection has changed. Nothing here expires,
 * and nothing is regenerated automatically.
 */

const ARTIFACT_POLL_INTERVAL_MS = 3000;

type CollectionTabKey = "sources" | "ai";

const COLLECTION_TABS: readonly ScreenTab<CollectionTabKey>[] = [
  { key: "sources", label: "Sources", icon: "documents-outline" },
  { key: "ai", label: "AI", icon: "sparkles-outline" },
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
      acc[tile.type] = { status: "idle" };
      return acc;
    },
    {} as Record<ArtifactType, ArtifactTileState>,
  );
}

export default function CollectionDetailScreen() {
  const router = useRouter();
  const { token } = useAuth();
  const params = useLocalSearchParams<{ id: string; name?: string }>();
  const collectionId = params.id;

  const [activeTab, setActiveTab] = useState<CollectionTabKey>("sources");
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

      <View style={styles.tabsContainer}>
        <ScreenTabs
          tabs={COLLECTION_TABS}
          activeKey={activeTab}
          onChange={setActiveTab}
          accessibilityLabel="Collection sections"
        />
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
              <SourceRow media={item.media} onPress={handleOpenMedia} />
            )
          }
          ListHeaderComponent={
            rows.length > 0 ? <Text style={styles.sectionTitle}>Sources</Text> : null
          }
          contentContainerStyle={styles.listContent}
          showsVerticalScrollIndicator={false}
          ListEmptyComponent={<EmptyState />}
          testID="collection-sources-list"
        />
      ) : (
        <AiTab collectionId={collectionId} />
      )}
    </SafeAreaView>
  );
}

// --- AI tab ---

interface AiTabProps {
  collectionId: string;
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
 */
function AiTab({ collectionId }: AiTabProps) {
  const router = useRouter();
  const { token } = useAuth();

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
  const mountedRef = useRef(true);
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  useEffect(() => {
    mountedRef.current = true;
    return () => {
      mountedRef.current = false;
      if (pollRef.current) clearInterval(pollRef.current);
    };
  }, []);

  const fetchHistory = useCallback(async (): Promise<ArtifactSummary[]> => {
    if (!token) return [];
    const response = await ArtifactService.listArtifacts(
      token,
      "folder",
      collectionId,
    );
    return response.artifacts;
  }, [token, collectionId]);

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
          fallback: "Unable to load generated content. Please try again.",
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

  // The tiles show the newest entry per type. The list comes back newest-first,
  // so the first entry seen for a type wins.
  const tileStates = useMemo(() => {
    const states = buildInitialArtifactStates();
    const seen = new Set<ArtifactType>();
    for (const artifact of history) {
      const type = artifact.artifact_type;
      if (seen.has(type) || !(type in states)) continue;
      seen.add(type);
      states[type] = {
        status: artifact.status,
        error: artifact.error_code ?? undefined,
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
      states[type] = { status: "queued" };
    }
    return states;
  }, [history, requestsInFlight]);

  const handleGenerate = useCallback(
    async (artifactType: ArtifactType) => {
      if (!token) return;
      setRefusal(null);
      // Before the POST, with nothing awaited in between: this is the update
      // that flips the tile, and it must land on the frame the finger lifts.
      setRequestsInFlight((current) =>
        current.includes(artifactType) ? current : [...current, artifactType],
      );

      try {
        const created = await ArtifactService.generateArtifact(
          token,
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
    [token, collectionId],
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
}

function SourceRow({ media, onPress }: SourceRowProps) {
  const mediaType = (media.media_type ?? "unknown") as MediaType;
  return (
    <Pressable
      style={({ pressed }) => [styles.sourceRow, pressed && styles.sourceRowPressed]}
      onPress={() => onPress(media.media_item_id)}
      testID={`collection-source-media-${media.media_item_id}`}
      accessibilityLabel={`Open ${media.title ?? "source"}`}
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
