import React, { useCallback, useMemo, useState } from "react";
import {
  View,
  Text,
  StyleSheet,
  FlatList,
  ScrollView,
  ActivityIndicator,
  Alert,
  Pressable,
  Platform,
  RefreshControl,
} from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";
import { Ionicons } from "@expo/vector-icons";
import { useRouter } from "expo-router";
import { useFocusEffect } from "expo-router";
import { useShareIntake } from "../../src/contexts/ShareIntentContext";
import { usePurchases } from "../../src/contexts/PurchasesContext";
import { useMediaPolling } from "../../src/hooks/useMediaPolling";
import type { InboxItem } from "../../src/contexts/InboxContext";
import { useHomeSections } from "../../src/hooks/useHomeSections";
import { t, tCount, useTranslation } from "../../src/i18n";
import { AddSourceSheet } from "../../src/components/AddSourceSheet";
import { MinutesWarningBanner } from "../../src/components/MinutesWarningBanner";
import { FreeTrialNotice } from "../../src/components/FreeTrialNotice";
import {
  HomeTile,
  TILE_GAP,
  type HomeTileItem,
} from "../../src/components/HomeTile";
import { buildCollectionTree } from "../../src/lib/collectionTree";
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
import { HOME_BLOCK_GAP } from "../../src/constants/homeRhythm";
import type { MediaListItem, MediaType } from "../../src/types/media";
import type { RecentEngagement } from "../../src/types/engagements";

/**
 * Home screen — the unsorted review entry point and two horizontal
 * rows of tiles: "Recently added" and "Continue learning" (task-307).
 *
 * The vertical list of every media item that used to live here is gone: task-306
 * moved the full library to the Search tab, which is where a list of everything
 * belongs. What is left is a landing screen — what just arrived, and what you
 * were in the middle of — and it is deliberately short.
 *
 * The Daily Digest card that used to sit at the top is gone too (task-324): it
 * pushed the Digest tab, which is one tap away in the tab bar. Its place is now
 * held by the entry into the triage of the default collection, which is the one
 * thing on this screen with a backlog behind it.
 *
 * Two sources feed it and each fails alone: "Recently added" comes from the
 * media list `useMediaPolling` holds, while `useHomeSections` brings the
 * engagement row and the collections behind the unsorted count. Only the very
 * first media fetch may show a full-screen spinner; no row ever shows one,
 * because a row with nothing to say is simply absent.
 *
 * Also hosts the ingestion gestures (task-264): a camera button that shoots
 * straight away, and an "add" button opening the choice between a file and a
 * gallery photo. All three hand the result to the share confirmation screen,
 * where the collection and tags are picked before sending.
 */

/**
 * How many tiles "Recently added" holds. The row is a landing strip, not a
 * library: past a dozen the user is better served by the Search tab, and every
 * extra tile is a cover to fetch on a screen that already has two rows.
 */
const RECENTLY_ADDED_LIMIT = 12;

/**
 * The band at the bottom of the screen the tab bar owns, and the one figure both
 * floating things on this screen measure themselves from.
 *
 * It is written down rather than measured: `NativeTabs` exposes no tab bar
 * height, because the bar is a `UITabBar` / Material `BottomNavigationView` the
 * system lays out itself (task-350).
 *
 * On iOS 26 the bar is a capsule detached from the screen edges with the content
 * passing under it, and this screen's `SafeAreaView` takes `edges={["top"]}`, so
 * the safe area runs all the way to the screen bottom — the 24 pt the buttons
 * used to sit at now lands *inside* the glass. `TouchTarget.large` is the strip
 * the capsule itself needs, and it is the same 64 the deleted Android branch of
 * `tabBarStyle` gave a bottom bar; `Spacing.lg` is the gap the capsule floats
 * above the screen bottom plus the room that keeps the buttons visibly off it
 * rather than tangent to it.
 *
 * On Android the native bottom navigation is opaque and `NativeTabs` already
 * wraps the screen in a `SafeAreaView` with the bottom inset applied, so there is
 * no glass to clear and the old 24 dp margin is still the whole of it.
 */
const TAB_BAR_CLEARANCE =
  Platform.OS === "ios" ? TouchTarget.large + Spacing.lg : Spacing.lg;

export default function InboxScreen() {
  // The screen's copy is resolved on render, so it redraws with the language.
  useTranslation();
  const router = useRouter();
  const { startLocalUpload } = useShareIntake();
  const { refreshEntitlements } = usePurchases();
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
  const { continueLearning, collections, refresh: refreshSections } =
    useHomeSections();

  // Silent refetch when the screen gains focus (multi-device sync). Uses the
  // non-spinner variant so we don't show the pull-to-refresh indicator just
  // because the user navigated back to this tab.
  // Entitlements come along for the ride: the minutes warning lives in this
  // header, and minutes are spent by imports made from this very screen, so
  // reading the figure fetched at sign-in would keep the banner a period behind.
  useFocusEffect(
    useCallback(() => {
      refetch();
      void refreshSections();
      void refreshEntitlements();
    }, [refetch, refreshSections, refreshEntitlements]),
  );

  const handleRefresh = useCallback(async () => {
    // Both, together: the spinner belongs to the gesture, not to one endpoint,
    // and `refreshSections` never rejects.
    await Promise.all([refresh(), refreshSections()]);
  }, [refresh, refreshSections]);

  const handleUnsortedReviewPress = useCallback(() => {
    router.push("/media/unsorted-review");
  }, [router]);

  const handleTilePress = useCallback(
    (item: HomeTileItem) => {
      if (item.kind === "media") {
        router.push(`/media/${item.id}`);
      } else if (item.kind === "collection") {
        router.push(`/media/collections/${item.id}`);
      }
      // A pending share has no id to open yet; its tile is disabled.
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

  const continueTiles = useMemo(
    () => continueLearning.map(toEngagementTile),
    [continueLearning],
  );

  const recentTiles = useMemo(
    () => buildRecentlyAdded(items, pendingLocalItems),
    [items, pendingLocalItems],
  );

  /**
   * How many media are waiting in the default collection.
   *
   * Read off the collections `useHomeSections` already fetched, so the figure
   * costs no request of its own. `buildCollectionTree` is what identifies the
   * folder — by its `is_default` flag, never by its label: the stored name is
   * `Uncategorized`, the UI says "Unsorted", and matching on either is what
   * task-297 ruled out.
   */
  const unsortedCount = useMemo(
    () => buildCollectionTree(collections).defaultCollection?.media_count ?? 0,
    [collections],
  );

  // Loading state — the only spinner on this screen, and only on the very first
  // media fetch. Every later refresh happens under the existing content.
  if (isLoading) {
    return (
      <SafeAreaView testID="inbox-screen" style={styles.container} edges={["top"]}>
        <View style={styles.centeredContainer}>
          <ActivityIndicator size="large" color={Colors.primary} />
          <Text style={styles.loadingText}>{t("home.loading")}</Text>
        </View>
      </SafeAreaView>
    );
  }

  // Error state — only when the media list failed *and* has nothing cached. The
  // other two sections are decorations on a screen that cannot show its content.
  if (error && items.length === 0 && pendingLocalItems.length === 0) {
    return (
      <SafeAreaView testID="inbox-screen" style={styles.container} edges={["top"]}>
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
            accessibilityLabel={t("home.retryA11y")}
            accessibilityRole="button"
          >
            <Ionicons name="refresh" size={18} color={Colors.onPrimary} />
            <Text style={styles.retryButtonText}>{t("common.retry")}</Text>
          </Pressable>
        </View>
      </SafeAreaView>
    );
  }

  const hasAnything = continueTiles.length > 0 || recentTiles.length > 0;

  return (
    <SafeAreaView testID="inbox-screen" style={styles.container} edges={["top"]}>
      {/* First child of the screen root, and it has to stay there: under
          `NativeTabs` the scrollable UIKit insets and hangs the scroll-edge
          effect on is found by walking the first-subview chain down from the
          screen (`RNSScrollViewFinder.findScrollViewInFirstDescendantChainFrom`
          in react-native-screens), so anything inserted above this loses both.
          The floating buttons below are fine: they come after it. */}
      <ScrollView
        contentContainerStyle={styles.scrollContent}
        showsVerticalScrollIndicator={false}
        refreshControl={
          <RefreshControl
            refreshing={isRefreshing}
            onRefresh={handleRefresh}
            tintColor={Colors.primary}
            colors={[Colors.primary]}
          />
        }
      >
        {/* Both read the entitlement state themselves and render nothing until
            they have something true to say — the trial notice while a trial is
            running, the minutes warning once the allowance is nearly spent. They
            stack in that order and, like every block below them, each carries the
            screen's one inter-block gap above itself and nothing below, so a
            trial user who is also low on minutes sees both, neither displacing
            the other, and an absent one costs the column nothing. */}
        <FreeTrialNotice />
        <MinutesWarningBanner />

        <UnsortedReviewButton
          count={unsortedCount}
          onPress={handleUnsortedReviewPress}
        />

        {recentTiles.length > 0 && (
          <TileRow
            testID="home-recently-added-row"
            icon="sparkles"
            title={t("home.recentlyAdded")}
            tiles={recentTiles}
            onTilePress={handleTilePress}
          />
        )}

        {/* Absent entirely when there is nothing to continue: no heading, no
            empty box, no placeholder tiles. A brand-new account has engaged with
            nothing, and entries age out of the server's window on their own. */}
        {continueTiles.length > 0 && (
          <TileRow
            testID="home-continue-learning-row"
            icon="play-circle"
            title={t("home.continueLearning")}
            tiles={continueTiles}
            onTilePress={handleTilePress}
          />
        )}

        {!hasAnything && <EmptyState />}
      </ScrollView>

      {/* box-none: the row now spans the full width, so without this it would
          swallow taps on the content sitting behind it. */}
      <View style={styles.fabStack} pointerEvents="box-none">
        <Pressable
          testID="inbox-camera-button"
          style={({ pressed }) => [
            styles.cameraButton,
            pressed && styles.addButtonPressed,
          ]}
          onPress={handleTakePhoto}
          accessibilityLabel={t("home.takePhotoA11y")}
          accessibilityRole="button"
        >
          <Ionicons name="camera" size={24} color={Colors.surface} />
        </Pressable>

        <Pressable
          testID="inbox-add-button"
          style={({ pressed }) => [styles.addButton, pressed && styles.addButtonPressed]}
          onPress={() => setSourceSheetVisible(true)}
          accessibilityLabel={t("addSource.title")}
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

// --- Sub-components ---

interface UnsortedReviewButtonProps {
  count: number;
  onPress: () => void;
}

/**
 * The entry into the triage of the default collection, with the size of the
 * backlog on its right.
 *
 * Nothing waiting, nothing to show: at zero the button is absent from the screen
 * altogether rather than sitting there inert with a `0` on it. A card offering
 * to sort an empty queue is one more thing to read on a landing screen that is
 * deliberately short.
 *
 * Same silhouette, card, badge and chevron as the Daily Digest card it replaces —
 * the style block was renamed, not redrawn, so the top of the Home did not move.
 */
function UnsortedReviewButton({ count, onPress }: UnsortedReviewButtonProps) {
  if (count <= 0) return null;

  return (
    <Pressable
      testID="home-unsorted-review-button"
      style={({ pressed }) => [
        styles.reviewButton,
        pressed && styles.reviewButtonPressed,
      ]}
      onPress={onPress}
      accessibilityLabel={t("home.unsortedReviewA11y", {
        count: tCount("common.itemCount", count),
      })}
      accessibilityRole="button"
    >
      <View style={styles.reviewIconContainer}>
        <Ionicons name="file-tray-outline" size={22} color={Colors.primary} />
      </View>
      <Text style={styles.reviewButtonLabel} numberOfLines={2}>
        {t("home.unsortedReview")}
      </Text>
      <View style={styles.reviewButtonRight}>
        <View style={styles.reviewCountBadge}>
          <Text style={styles.reviewCountText}>{count}</Text>
        </View>
        <Ionicons name="chevron-forward" size={20} color={Colors.primary} />
      </View>
    </Pressable>
  );
}

interface TileRowProps {
  testID: string;
  icon: keyof typeof Ionicons.glyphMap;
  title: string;
  tiles: HomeTileItem[];
  onTilePress: (item: HomeTileItem) => void;
}

/**
 * A heading and one horizontally scrollable row of tiles.
 *
 * The heading is Title Case with an icon in the primary tint, replacing the
 * uppercase muted `YOUR MEDIA` label the vertical list used. The icon is an
 * Ionicon rather than an emoji: Ionicons is the app's icon language everywhere
 * else, and an emoji renders differently on each platform.
 */
function TileRow({ testID, icon, title, tiles, onTilePress }: TileRowProps) {
  return (
    <View style={styles.section}>
      <View style={styles.sectionHeaderRow}>
        <Ionicons name={icon} size={18} color={Colors.primary} />
        <Text style={styles.sectionTitle} numberOfLines={1}>
          {title}
        </Text>
      </View>
      <FlatList
        testID={testID}
        data={tiles}
        keyExtractor={(tile) => `${tile.kind}:${tile.id}`}
        renderItem={({ item }) => <HomeTile item={item} onPress={onTilePress} />}
        horizontal
        showsHorizontalScrollIndicator={false}
        contentContainerStyle={styles.rowContent}
      />
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
      <Text style={styles.emptyTitle}>{t("home.empty")}</Text>
      <Text style={styles.emptyHint}>{t("home.emptyHint")}</Text>
    </View>
  );
}

// --- Tile assembly ---

/**
 * The engagement row is already merged, ordered and signed server-side, so this
 * only maps the wire shape onto the tile shape — and keeps the order it came in.
 */
function toEngagementTile(entry: RecentEngagement): HomeTileItem {
  if (entry.kind === "collection") {
    return {
      kind: "collection",
      id: entry.id,
      name: entry.title?.trim() || t("home.untitledCollection"),
      itemCount: entry.item_count ?? 0,
      previewImages: entry.preview_images ?? [],
    };
  }
  return {
    kind: "media",
    id: entry.id,
    title: entry.title ?? null,
    creator: entry.creator_name ?? null,
    imageUrl: entry.image_url ?? null,
    // No `updated_at` on this payload, and `engaged_at` would churn the cache on
    // every engagement — the id alone is the stable identity here.
    cacheKey: entry.id,
    mediaType: (entry.media_type ?? "unknown") as MediaType,
  };
}

/**
 * "Recently added": what just arrived to read, and nothing else.
 *
 * Pending shares come first whatever their age — they are what the user just
 * did, and keeping them at the head is what makes a share visible on return from
 * the confirmation screen while the backend catches up.
 *
 * The media follow, newest-first on `created_at`, and the whole row is capped.
 * Collections do not appear here (task-348): a folder is not something that just
 * arrived to read, and one created from the confirmation screen used to double
 * every filed save into two tiles. They keep their place in "Continue learning",
 * where picking a reading back up is the point.
 */
function buildRecentlyAdded(
  media: MediaListItem[],
  pending: InboxItem[],
): HomeTileItem[] {
  const pendingTiles: HomeTileItem[] = pending.map((local) => ({
    kind: "pending",
    id: local.localId,
    url: local.url,
    sourcePlatform: local.sourcePlatform,
    failed: local.state === "failed",
  }));

  const mediaTiles = media
    .map((item) => ({
      at: toTimestamp(item.created_at),
      tile: {
        kind: "media" as const,
        id: item.media_item_id,
        title: item.title ?? null,
        creator: item.creator_name ?? null,
        imageUrl: item.media_image ?? null,
        cacheKey: `${item.media_item_id}:${item.updated_at}`,
        mediaType: (item.media_type ?? "unknown") as MediaType,
      },
    }))
    .sort((a, b) => b.at - a.at)
    .map((entry) => entry.tile);

  return [...pendingTiles, ...mediaTiles].slice(0, RECENTLY_ADDED_LIMIT);
}

function toTimestamp(value?: string | null): number {
  const parsed = Date.parse(value ?? "");
  return Number.isNaN(parsed) ? 0 : parsed;
}


// --- Styles ---

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: Colors.background,
  },
  scrollContent: {
    // No top padding on purpose: whichever block comes first carries the gap
    // under the safe area itself, through the same `HOME_BLOCK_GAP` as every
    // other. Padding here would stack on top of it and make the head of the
    // screen the one place with a different rhythm — which is what it was, at 32
    // above the trial pill against 16 below it.
    // Room for the floating buttons so they never cover the last row, on top of
    // the band the tab bar owns. Derived from the same `TAB_BAR_CLEARANCE` the
    // buttons are pinned at rather than restated as a second figure: the row is
    // `TouchTarget.large` tall and sits that far above the screen bottom, and
    // `Spacing.sm` is the gap left between the last tile and it — the same 8 the
    // previous pair of values produced (64 + 32 against a 24 pt offset).
    paddingBottom: TAB_BAR_CLEARANCE + TouchTarget.large + Spacing.sm,
  },

  // Loading state
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

  // Unsorted review button (the Daily Digest card's block, renamed)
  reviewButton: {
    flexDirection: "row",
    alignItems: "center",
    backgroundColor: Colors.surface,
    marginHorizontal: Spacing.md,
    // Its share of the column's rhythm, above only — see `HOME_BLOCK_GAP`.
    marginTop: HOME_BLOCK_GAP,
    padding: Spacing.md + 4,
    borderRadius: BorderRadius.xl,
    borderWidth: StyleSheet.hairlineWidth,
    borderColor: Colors.outlineVariant,
    minHeight: TouchTarget.comfortable,
    ...Shadows.soft,
  },
  reviewButtonPressed: {
    transform: [{ scale: 0.98 }],
    opacity: 0.9,
  },
  reviewIconContainer: {
    width: 40,
    height: 40,
    borderRadius: BorderRadius.lg,
    backgroundColor: "rgba(255, 203, 5, 0.1)",
    alignItems: "center",
    justifyContent: "center",
  },
  reviewButtonLabel: {
    flex: 1,
    fontSize: Typography.body.fontSize,
    fontWeight: "700",
    color: Colors.textMain,
    marginStart: Spacing.md,
  },
  reviewButtonRight: {
    flexDirection: "row",
    alignItems: "center",
    gap: Spacing.sm,
  },
  reviewCountBadge: {
    minWidth: 24,
    paddingHorizontal: Spacing.xs + 2,
    paddingVertical: 2,
    borderRadius: BorderRadius.full,
    backgroundColor: Colors.surfaceContainerHigh,
    alignItems: "center",
    justifyContent: "center",
  },
  reviewCountText: {
    fontSize: Typography.small.fontSize,
    fontWeight: "700",
    color: Colors.textMain,
  },

  // Rows
  section: {
    // Same gap as every other block, and on the same side of it, so the space
    // between the review card and the first heading and the space between the
    // first row and the second heading are one value. The row's own height no
    // longer varies with the kinds of tile it holds (`TILE_HEIGHT`), so this is
    // now the whole of what separates two rows.
    marginTop: HOME_BLOCK_GAP,
  },
  sectionHeaderRow: {
    flexDirection: "row",
    alignItems: "center",
    gap: Spacing.sm,
    paddingHorizontal: Spacing.lg,
    paddingBottom: Spacing.md,
  },
  sectionTitle: {
    // Claims the room left by the icon rather than wrapping under it.
    flex: 1,
    fontSize: Typography.headline.fontSize,
    fontWeight: Typography.headline.fontWeight,
    color: Colors.textMain,
  },
  rowContent: {
    paddingHorizontal: Spacing.md,
    gap: TILE_GAP,
  },

  // Floating ingestion controls (task-264)
  fabStack: {
    position: "absolute",
    left: 0,
    right: 0,
    // Absolutely positioned, so nothing insets it for the bar: this row is the
    // reason `TAB_BAR_CLEARANCE` exists.
    bottom: TAB_BAR_CLEARANCE,
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
