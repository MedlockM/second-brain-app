/**
 * Digest — the media of a period, one full media page per swipe.
 *
 * Daily or Weekly, oldest first, and each page is `CompletedDetailView` with its
 * chrome off: the same component the `/media/[id]` route renders, so the Digest
 * shows the real thing — Reader tab, AI tab, everything — instead of a summary of
 * a summary. Nothing is redrawn here and there is no digest variant of the media
 * page; when that page changes, this screen follows without being touched.
 *
 * No action on the media either. Unlike the unsorted review, whose pager shape
 * this one borrows, the Digest presents and does not triage: no Discard, no
 * Deepen, no Save.
 *
 * ## The gestures
 *
 * A page scrolls vertically and carries its own tabs, inside a pager that scrolls
 * horizontally. Four things keep the two apart, and all four are load-bearing:
 *
 * 1. **The pager is the only horizontal scrollable in the tree.** Nothing in the
 *    media page subtree scrolls sideways, so no descendant ever competes for a
 *    horizontal pan. (`HomeTile`'s row is the Home screen's, not this one's.)
 * 2. **`directionalLockEnabled` on both scroll views.** A drag commits to one
 *    axis. Without it a diagonal drag scrolls the page *and* drags the pager, and
 *    a page ends up parked between two.
 * 3. **Every page is exactly `SCREEN_WIDTH` wide, mounted or not.** The content
 *    width of the pager is therefore `ids.length * SCREEN_WIDTH` at all times and
 *    the page boundaries never move — which is what makes lazy mounting safe. A
 *    placeholder that measured 0 would shift every boundary past it under the
 *    finger, the same failure `unsorted-review.tsx :: removeAt` has to undo by
 *    hand after a removal.
 * 4. **The intra-page tabs are `Pressable`s, not a swipe.** A tab change is a tap
 *    — it cannot consume a pan — and it repaints inside one page, leaving the
 *    pager's content width untouched.
 *
 * One accepted consequence on iOS: a touch that lands while a page is still
 * gliding is claimed by that page's scroll view to stop it, so the swipe in that
 * same touch does not turn the page. The next swipe does. Fighting it would mean
 * taking the arbitration away from UIKit for one screen.
 *
 * ## What gets mounted
 *
 * Only the current page and its two neighbours. Three pages, so three sets of the
 * artifact/translation/preview polls `CompletedDetailView` runs — the reason the
 * window is closed behind the user rather than left to grow: a period can hold
 * dozens of media, and thirty live pages means thirty poll timers and thirty
 * `MediaStatusResponse` in memory. The price is that a page left three or more
 * behind refetches when it comes back, which no single swipe can cause.
 */

import React, { useCallback, useMemo, useRef, useState } from "react";
import {
  ActivityIndicator,
  Dimensions,
  NativeScrollEvent,
  NativeSyntheticEvent,
  Platform,
  Pressable,
  RefreshControl,
  ScrollView,
  StyleSheet,
  Text,
  View,
} from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";
import { useFocusEffect } from "expo-router";
import { Ionicons } from "@expo/vector-icons";
import { useAuth } from "../../src/contexts/AuthContext";
import { DigestService } from "../../src/services/digestService";
import { CompletedDetailView } from "../../src/components/CompletedDetailView";
import { PaginationDots } from "../../src/components/PaginationDots";
import { useMediaDetailPolling } from "../../src/hooks/useMediaDetailPolling";
import { getFriendlyErrorMessage } from "../../src/lib/getFriendlyErrorMessage";
import {
  BorderRadius,
  Colors,
  Spacing,
  TouchTarget,
  Typography,
} from "../../src/constants/theme";
import { t, useTranslation } from "../../src/i18n";
import type { Digest } from "../../src/types/digest";

const { width: SCREEN_WIDTH } = Dimensions.get("window");

/**
 * The band at the bottom of the screen the tab bar owns, kept clear of the pager.
 * Same value and same reason as `app/(tabs)/inbox.tsx`: on iOS the bar is a
 * floating glass capsule the content passes under, on Android an opaque bar
 * `NativeTabs` already insets for.
 *
 * Taken off the pager's height rather than added to the page's scroll content:
 * the page is a shared component that owns its own padding, and the sticky tab
 * bar inside it has to stay visible, which a taller page under the capsule would
 * not guarantee.
 */
const TAB_BAR_CLEARANCE =
  Platform.OS === "ios" ? TouchTarget.large + Spacing.lg : Spacing.lg;

/** How many pages either side of the current one stay mounted. */
const MOUNT_RADIUS = 1;

type DigestTab = "daily" | "weekly";

export default function DigestScreen(): React.JSX.Element {
  // Resolved-on-render copy: the screen has to redraw with the language.
  useTranslation();
  const { isAuthenticated } = useAuth();

  const [activeTab, setActiveTab] = useState<DigestTab>("daily");
  const [daily, setDaily] = useState<Digest | null>(null);
  const [weekly, setWeekly] = useState<Digest | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [activeIndex, setActiveIndex] = useState(0);

  const pagerRef = useRef<ScrollView>(null);

  const fetchDigest = useCallback(
    async (tab: DigestTab) => {
      if (!isAuthenticated) return;

      try {
        if (tab === "daily") {
          setDaily(await DigestService.getDailyDigest());
        } else {
          setWeekly(await DigestService.getWeeklyDigest());
        }
        setError(null);
      } catch (err: unknown) {
        setError(
          getFriendlyErrorMessage(err, { fallback: t("digest.loadFailed") }),
        );
      } finally {
        setIsLoading(false);
        setIsRefreshing(false);
      }
    },
    [isAuthenticated],
  );

  // Fetched on focus, not on mount: `NativeTabs` has no lazy loading, so every
  // tab screen mounts on the first render of the bar (task-350). From a plain
  // `useEffect` this screen asked the backend for a digest on every cold start,
  // including the ones where the tab is never opened.
  //
  // The dependency on `activeTab` is what still refetches when the segmented
  // control moves: a new callback identity re-runs the effect, and the screen is
  // focused when the user is tapping it.
  useFocusEffect(
    useCallback(() => {
      const timer = setTimeout(() => void fetchDigest(activeTab), 0);
      return () => clearTimeout(timer);
    }, [activeTab, fetchDigest]),
  );

  const handleRetry = useCallback(() => {
    setIsRefreshing(true);
    setError(null);
    void fetchDigest(activeTab);
  }, [activeTab, fetchDigest]);

  const handleTabChange = useCallback(
    (tab: DigestTab) => {
      if (tab === activeTab) return;
      setActiveTab(tab);
      setIsLoading(true);
      setError(null);
      setActiveIndex(0);
      pagerRef.current?.scrollTo({ x: 0, animated: false });
    },
    [activeTab],
  );

  const digest = activeTab === "daily" ? daily : weekly;
  const ids = digest?.media_item_ids ?? [];

  const handleScroll = useCallback(
    (event: NativeSyntheticEvent<NativeScrollEvent>) => {
      const index = Math.round(event.nativeEvent.contentOffset.x / SCREEN_WIDTH);
      // Clamped: a bounce past the last page must not point outside the period.
      setActiveIndex(Math.max(0, Math.min(index, ids.length - 1)));
    },
    [ids.length],
  );

  const positionLabel = useMemo(
    () =>
      t("digest.position", {
        current: ids.length === 0 ? 0 : activeIndex + 1,
        total: ids.length,
      }),
    [activeIndex, ids.length],
  );

  const positionA11yLabel = useMemo(
    () =>
      t("digest.positionA11y", {
        current: ids.length === 0 ? 0 : activeIndex + 1,
        total: ids.length,
      }),
    [activeIndex, ids.length],
  );

  return (
    <SafeAreaView style={styles.container} edges={["top"]}>
      <View style={styles.segmentedControlContainer}>
        <View style={styles.segmentedControl}>
          <SegmentButton
            label={t("digest.daily")}
            isActive={activeTab === "daily"}
            onPress={() => handleTabChange("daily")}
          />
          <SegmentButton
            label={t("digest.weekly")}
            isActive={activeTab === "weekly"}
            onPress={() => handleTabChange("weekly")}
          />
        </View>
      </View>

      {/* The one header of the screen: the pages below carry none of their own. */}
      <View style={styles.header}>
        <Text style={styles.headerTitle}>
          {activeTab === "daily"
            ? t("digest.dailyTitle")
            : t("digest.weeklyTitle")}
        </Text>
        {/* The dots cap at seven and cannot state where in the period the user
            is. This is where that information lives, for the eye and for a
            screen reader alike. */}
        {ids.length > 0 ? (
          <Text
            style={styles.headerPosition}
            accessibilityLabel={positionA11yLabel}
            numberOfLines={1}
          >
            {positionLabel}
          </Text>
        ) : null}
      </View>

      {isLoading ? (
        <View style={styles.centered}>
          <ActivityIndicator size="large" color={Colors.primary} />
        </View>
      ) : error ? (
        /* `contentInsetAdjustmentBehavior` is set by hand, not left to
           `NativeTabs`. The bar insets the tab's scroll view itself, but only
           the one it can find: react-native-screens walks the first-subview
           chain down from the screen
           (`RNSScrollViewFinder.findScrollViewInFirstDescendantChainFrom`) and
           flips the first `UIScrollView` it meets from `never` to `automatic`
           (`RNSScrollViewHelper`). On this screen the segmented control and the
           header come first, so that walk dead-ends before any scrollable and
           the inset would never be applied. `automatic` here is the very value
           the native helper would have set. */
        <ScrollView
          contentInsetAdjustmentBehavior="automatic"
          contentContainerStyle={styles.centered}
          refreshControl={
            <RefreshControl
              refreshing={isRefreshing}
              onRefresh={handleRetry}
              tintColor={Colors.primary}
            />
          }
        >
          <Ionicons
            name="cloud-offline-outline"
            size={48}
            color={Colors.textMuted}
          />
          <Text style={styles.errorText}>{error}</Text>
          <Pressable
            style={({ pressed }) => [
              styles.retryButton,
              pressed && styles.retryButtonPressed,
            ]}
            onPress={handleRetry}
            accessibilityLabel={t("digest.tryAgain")}
            accessibilityRole="button"
          >
            <Text style={styles.retryButtonText}>{t("digest.tryAgain")}</Text>
          </Pressable>
        </ScrollView>
      ) : ids.length === 0 ? (
        /* Nothing was saved in the period, so the backend wrote no digest for it
           and there is nothing to page through. Sober, and deliberately without
           a way out: no fallback to an older, fuller period and no switch to the
           weekly tab — an empty day is a true answer, and answering with another
           day's media would be a lie about which one the notification named.
           Same hand-set inset as the error state above. */
        <ScrollView
          contentInsetAdjustmentBehavior="automatic"
          contentContainerStyle={styles.centered}
          refreshControl={
            <RefreshControl
              refreshing={isRefreshing}
              onRefresh={handleRetry}
              tintColor={Colors.primary}
            />
          }
        >
          <Text style={styles.emptyTitle}>
            {activeTab === "daily"
              ? t("digest.emptyDaily")
              : t("digest.emptyWeekly")}
          </Text>
          <Text style={styles.emptyHint}>
            {activeTab === "daily"
              ? t("digest.emptyDailyHint")
              : t("digest.emptyWeeklyHint")}
          </Text>
        </ScrollView>
      ) : (
        /* No automatic inset on the pager: it is the one scrollable here that
           scrolls horizontally, and an automatic adjustment would inset the
           paging axis. `collapsable={false}` keeps the wrapper a real view so
           the pager below it stays where the layout puts it.

           No `RefreshControl` either. It only works on a vertical scroll view,
           and there would be nothing for it to fetch: the list of a period is
           frozen at capture and cannot change until the next send. */
        <View style={styles.pagerContainer} collapsable={false}>
          <PaginationDots
            count={ids.length}
            activeIndex={activeIndex}
            testID="digest-dots"
          />

          <ScrollView
            ref={pagerRef}
            style={styles.pager}
            horizontal
            pagingEnabled
            directionalLockEnabled
            showsHorizontalScrollIndicator={false}
            onScroll={handleScroll}
            scrollEventThrottle={16}
            decelerationRate="fast"
            testID="digest-pager"
          >
            {ids.map((id, index) =>
              Math.abs(index - activeIndex) <= MOUNT_RADIUS ? (
                <DigestPage key={id} mediaItemId={id} />
              ) : (
                <View key={id} style={styles.page} />
              ),
            )}
          </ScrollView>
        </View>
      )}
    </SafeAreaView>
  );
}

// --- Sub-components ---

function SegmentButton({
  label,
  isActive,
  onPress,
}: {
  label: string;
  isActive: boolean;
  onPress: () => void;
}): React.JSX.Element {
  return (
    <Pressable
      style={[styles.segmentButton, isActive && styles.segmentButtonActive]}
      onPress={onPress}
      accessibilityLabel={label}
      accessibilityRole="button"
      accessibilityState={{ selected: isActive }}
    >
      <Text
        style={[
          styles.segmentButtonText,
          isActive && styles.segmentButtonTextActive,
        ]}
      >
        {label}
      </Text>
    </Pressable>
  );
}

/**
 * One page of the pager: a media, fetched by the page itself.
 *
 * The fetch is the route's hook, unchanged — a digest page goes through the same
 * states a media does when opened directly, including still being processed or
 * having failed, which an item saved minutes before the send can be. Mounting is
 * what starts it and unmounting is what stops it, so the mount window *is* the
 * loading policy: there is no second mechanism to keep in step with it.
 *
 * The page always occupies a full screen width, whichever state it is in. A
 * spinner in a narrower box would move every page boundary after it.
 */
function DigestPage({
  mediaItemId,
}: {
  mediaItemId: string;
}): React.JSX.Element {
  const { state, mediaData, fetchError, processingError, processingMessage } =
    useMediaDetailPolling(mediaItemId);

  if (state === "completed" && mediaData) {
    return (
      <View style={styles.page}>
        <CompletedDetailView
          mediaData={mediaData}
          // The header that owns the back arrow is not rendered here, and
          // neither is the `…` menu whose deletion would call this. Nothing in
          // a chrome-less page can reach it — and the Digest has nowhere to go
          // back to: it is a tab, not a pushed route.
          onBack={() => {}}
          showChrome={false}
        />
      </View>
    );
  }

  if (state === "loading") {
    return (
      <View style={[styles.page, styles.pageCentered]}>
        <ActivityIndicator size="large" color={Colors.primary} />
      </View>
    );
  }

  if (state === "processing") {
    return (
      <View style={[styles.page, styles.pageCentered]}>
        <ActivityIndicator size="large" color={Colors.primary} />
        <Text style={styles.pageStateTitle}>{processingMessage}</Text>
      </View>
    );
  }

  // Failed, timed out, or unreachable. One quiet page, no retry button: the swipe
  // out of it is the way on, and the item is still one tap away in the library.
  return (
    <View style={[styles.page, styles.pageCentered]}>
      <Ionicons
        name={state === "timeout" ? "time-outline" : "alert-circle-outline"}
        size={40}
        color={Colors.textMuted}
      />
      <Text style={styles.pageStateTitle}>
        {state === "timeout"
          ? t("media.timeoutTitle")
          : state === "failed"
            ? t("media.failedTitle")
            : t("media.loadFailed")}
      </Text>
      <Text style={styles.pageStateBody}>
        {state === "timeout"
          ? t("media.timeoutHint")
          : (processingError ?? fetchError ?? t("media.failedFallback"))}
      </Text>
    </View>
  );
}

// --- Styles ---

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: Colors.background,
  },

  // Segmented control
  segmentedControlContainer: {
    paddingHorizontal: Spacing.lg,
    paddingTop: Spacing.md,
    paddingBottom: Spacing.sm,
  },
  segmentedControl: {
    flexDirection: "row",
    backgroundColor: Colors.surfaceContainerLow,
    borderRadius: BorderRadius.full,
    padding: Spacing.xs,
  },
  segmentButton: {
    flex: 1,
    alignItems: "center",
    justifyContent: "center",
    borderRadius: BorderRadius.full,
    minHeight: TouchTarget.minimum,
  },
  segmentButtonActive: {
    backgroundColor: Colors.primary,
  },
  segmentButtonText: {
    fontSize: Typography.label.fontSize,
    fontWeight: Typography.label.fontWeight,
    color: Colors.textMuted,
  },
  segmentButtonTextActive: {
    color: Colors.onPrimary,
    fontWeight: "600",
  },

  // Header
  header: {
    paddingHorizontal: Spacing.lg,
    paddingTop: Spacing.sm,
    paddingBottom: Spacing.sm,
  },
  headerTitle: {
    ...Typography.display,
    color: Colors.textMain,
  },
  headerPosition: {
    fontSize: Typography.small.fontSize,
    color: Colors.textSubtle,
    marginTop: Spacing.xs,
  },

  // Loading / error / empty
  centered: {
    flex: 1,
    alignItems: "center",
    justifyContent: "center",
    paddingHorizontal: Spacing.xl,
    gap: Spacing.md,
  },
  errorText: {
    fontSize: Typography.body.fontSize,
    color: Colors.textMain,
    textAlign: "center",
  },
  retryButton: {
    minHeight: TouchTarget.minimum,
    justifyContent: "center",
    paddingHorizontal: Spacing.xl,
    borderRadius: BorderRadius.full,
    backgroundColor: Colors.primary,
  },
  retryButtonPressed: {
    opacity: 0.9,
  },
  retryButtonText: {
    fontSize: Typography.label.fontSize,
    fontWeight: "600",
    color: Colors.onPrimary,
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
    lineHeight: Typography.body.lineHeight,
  },

  // Pager
  pagerContainer: {
    flex: 1,
    // The band the tab bar owns. See TAB_BAR_CLEARANCE.
    paddingBottom: TAB_BAR_CLEARANCE,
  },
  pager: {
    flex: 1,
  },
  // Exactly one screen width, in every state of a page. See the gesture note at
  // the top of the file: the page boundaries are `index * SCREEN_WIDTH` and
  // nothing about mounting is allowed to move them.
  page: {
    width: SCREEN_WIDTH,
  },
  pageCentered: {
    alignItems: "center",
    justifyContent: "center",
    paddingHorizontal: Spacing.xl,
    gap: Spacing.md,
  },
  pageStateTitle: {
    fontSize: Typography.headline.fontSize,
    fontWeight: Typography.headline.fontWeight,
    color: Colors.textMain,
    textAlign: "center",
  },
  pageStateBody: {
    fontSize: Typography.body.fontSize,
    color: Colors.textMuted,
    textAlign: "center",
    lineHeight: Typography.body.lineHeight,
  },
});
