/**
 * Unsorted review — the triage pass over the default collection.
 *
 * One media per page, oldest first, with three ways out: throw it away, open it
 * to have a proper look, or file it. Swipe left and right to move through the
 * queue the way an image carousel works. What this screen is fighting is the
 * default folder filling up at every ingestion with nothing ever pushing the
 * user to empty it.
 *
 * The pager is a `ScrollView horizontal pagingEnabled` from the core, one page per
 * screen width, active index derived from the scroll offset — the shape
 * `app/(tabs)/digest.tsx` already uses. No gesture or animation library is
 * involved, and none is wanted: paging is a native behaviour of the scroll view.
 *
 * Two things about this screen are unusual enough to be spelled out where they
 * happen: the queue is frozen at mount (see `load`), and every mutation of it
 * re-anchors the pager by hand (see `removeAt`).
 */

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  ActivityIndicator,
  Alert,
  Dimensions,
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  View,
  type NativeScrollEvent,
  type NativeSyntheticEvent,
} from "react-native";
import { Image } from "expo-image";
import { SafeAreaView } from "react-native-safe-area-context";
import { Ionicons } from "@expo/vector-icons";
import { useRouter } from "expo-router";
import {
  BorderRadius,
  Colors,
  Shadows,
  Spacing,
  TouchTarget,
  Typography,
} from "../../src/constants/theme";
import { t, useTranslation } from "../../src/i18n";
import {
  COVER_HEIGHT,
  COVER_WIDTH,
} from "../../src/components/MediaListCard";
import { PaginationDots } from "../../src/components/PaginationDots";
import { CollectionSaveSheet } from "../../src/components/CollectionSaveSheet";
import { buildCollectionTree } from "../../src/lib/collectionTree";
import { getFriendlyErrorMessage } from "../../src/lib/getFriendlyErrorMessage";
import { getMediaTypeIcon } from "../../src/lib/mediaTypeDisplay";
import { MediaService } from "../../src/services/mediaService";
import { OrganizationService } from "../../src/services/organizationService";
import type { MediaListItem, MediaType } from "../../src/types/media";
import type { Collection } from "../../src/types/organization";

const { width: SCREEN_WIDTH } = Dimensions.get("window");

/**
 * How deep a single triage pass goes. The list endpoint caps a page at 100 and
 * the queue is one request by design — a hundred decisions is already more than
 * anyone makes in a sitting, and the next pass picks up where this one stopped.
 */
const QUEUE_LIMIT = 100;

export default function UnsortedReviewScreen(): React.JSX.Element {
  // Copy resolved on render: the screen redraws with the interface language.
  useTranslation();
  const router = useRouter();

  const [items, setItems] = useState<MediaListItem[]>([]);
  const [collections, setCollections] = useState<Collection[]>([]);
  const [activeIndex, setActiveIndex] = useState(0);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [isMutating, setIsMutating] = useState(false);
  const [saveTargetId, setSaveTargetId] = useState<string | null>(null);

  const pagerRef = useRef<ScrollView>(null);
  const isMountedRef = useRef(true);

  const load = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    try {
      // The folder list is what gives the default collection's id, and the save
      // sheet needs the same list to offer destinations — one read serves both.
      const folders = await OrganizationService.getUserCollections();
      // `is_default`, never the label: the stored name is `Uncategorized`, the UI
      // says "Unsorted", and matching on either is what task-297 forbade.
      const { defaultCollection } = buildCollectionTree(folders);

      let queue: MediaListItem[] = [];
      if (defaultCollection) {
        const page = await OrganizationService.getCollectionMedia(
          defaultCollection.id,
          { limit: QUEUE_LIMIT, sort: "asc" },
        );
        // The backend `folder_id` filter is inclusive of sub-folders, so the
        // exact id is re-checked here: a triage of "unsorted" must not hand out
        // media the user has already filed somewhere below it.
        queue = page.filter((item) => item.folder_id === defaultCollection.id);
      }

      if (!isMountedRef.current) return;
      setCollections(folders);
      setItems(queue);
      setActiveIndex(0);
    } catch (err) {
      if (!isMountedRef.current) return;
      setError(
        getFriendlyErrorMessage(err, {
          fallback: t("unsortedReview.loadFailed"),
        }),
      );
    } finally {
      if (isMountedRef.current) setIsLoading(false);
    }
  }, []);

  /**
   * Loaded once, at mount, and never on focus.
   *
   * Deliberately against the convention of the rest of the app, where a screen
   * refetches in a `useFocusEffect` so several devices stay in step. Here the
   * user comes back from Deepen with a finger already on the card: a refetch
   * would reshuffle the queue and renumber every index under it, and the next
   * swipe would land somewhere else. The queue this screen shows is the queue it
   * opened with; what the server has meanwhile is next pass's business.
   *
   * Deferred by a tick — a `setState` reached synchronously from an effect
   * cascades a render, and the lint rule that says so is on.
   */
  useEffect(() => {
    isMountedRef.current = true;
    const timer = setTimeout(() => void load(), 0);
    return () => {
      clearTimeout(timer);
      isMountedRef.current = false;
    };
  }, [load]);

  const handleClose = useCallback(() => {
    if (router.canGoBack()) {
      router.back();
      return;
    }
    router.replace("/(tabs)/inbox");
  }, [router]);

  const handleScroll = useCallback(
    (event: NativeSyntheticEvent<NativeScrollEvent>) => {
      const offsetX = event.nativeEvent.contentOffset.x;
      const index = Math.round(offsetX / SCREEN_WIDTH);
      // Clamped: a bounce past the last page, or a scroll event arriving in the
      // same frame as a removal, must not point past the queue.
      setActiveIndex(Math.max(0, Math.min(index, items.length - 1)));
    },
    [items.length],
  );

  /**
   * Drop one page from the queue and put the pager back on a page boundary.
   *
   * This second half is not optional. The content width of a paging `ScrollView`
   * is the number of pages times the screen width; removing one shrinks it while
   * React Native keeps the `contentOffset` it had, which leaves the pager parked
   * between two pages with a slice of each visible. So every mutation ends with
   * an explicit, *non-animated* `scrollTo` on the index that is now current —
   * non-animated because the following card slid into the vacated slot on its
   * own, and animating a jump the layout already made would be a second motion
   * for one event. `requestAnimationFrame` puts it after the frame the new list
   * is laid out in; called straight after `setItems` it would still be measuring
   * the old content.
   */
  const removeAt = useCallback(
    (index: number) => {
      const remaining = items.filter((_, i) => i !== index);
      const nextIndex = Math.min(index, Math.max(0, remaining.length - 1));
      setItems(remaining);
      setActiveIndex(nextIndex);
      requestAnimationFrame(() => {
        pagerRef.current?.scrollTo({
          x: nextIndex * SCREEN_WIDTH,
          animated: false,
        });
      });
    },
    [items],
  );

  const removeById = useCallback(
    (mediaItemId: string) => {
      const index = items.findIndex(
        (item) => item.media_item_id === mediaItemId,
      );
      if (index === -1) return;
      removeAt(index);
    },
    [items, removeAt],
  );

  const current = items[activeIndex];

  /**
   * Discard: the deletion goes out on the first tap, with no confirmation.
   *
   * An owner decision, and a deliberate divergence from the long-press menu in
   * Library (task-319), which does ask. Two contexts: there, one media is singled
   * out among the ones being kept; here the user is going through a backlog at
   * the rhythm of a tap, and a dialog per item turns a triage into a chore. Not
   * to be "harmonised" in either direction.
   */
  const handleDiscard = useCallback(() => {
    if (!current || isMutating) return;
    const target = current;
    const index = activeIndex;
    setIsMutating(true);
    void (async () => {
      try {
        await MediaService.deleteMedia(target.media_item_id);
        if (!isMountedRef.current) return;
        removeAt(index);
      } catch (err) {
        // The card stays: the media is still in the library, and a queue that
        // hid it would be lying about what the server holds.
        Alert.alert(
          t("common.error"),
          getFriendlyErrorMessage(err, {
            fallback: t("unsortedReview.discardFailed"),
          }),
        );
      } finally {
        if (isMountedRef.current) setIsMutating(false);
      }
    })();
  }, [current, isMutating, activeIndex, removeAt]);

  /**
   * Deepen: open the media and come back. Not a decision — the item stays in the
   * queue, and since nothing reloads on focus the same card is under the finger
   * on return, at the same index.
   */
  const handleDeepen = useCallback(() => {
    if (!current) return;
    router.push(`/media/${current.media_item_id}`);
  }, [current, router]);

  const handleSavePress = useCallback(() => {
    if (!current || isMutating) return;
    setSaveTargetId(current.media_item_id);
  }, [current, isMutating]);

  const handleCollectionCreated = useCallback((collection: Collection) => {
    setCollections((prev) => [...prev, collection]);
  }, []);

  const handleSaved = useCallback(
    (mediaItemId: string) => {
      setSaveTargetId(null);
      removeById(mediaItemId);
    },
    [removeById],
  );

  const positionLabel = useMemo(
    () =>
      t("unsortedReview.position", {
        current: items.length === 0 ? 0 : activeIndex + 1,
        total: items.length,
      }),
    [activeIndex, items.length],
  );

  const positionA11yLabel = useMemo(
    () =>
      t("unsortedReview.positionA11y", {
        current: items.length === 0 ? 0 : activeIndex + 1,
        total: items.length,
      }),
    [activeIndex, items.length],
  );

  return (
    <SafeAreaView
      testID="unsorted-review-screen"
      style={styles.container}
      edges={["top", "bottom"]}
    >
      <View style={styles.header}>
        <Pressable
          style={({ pressed }) => [
            styles.closeButton,
            pressed && styles.closeButtonPressed,
          ]}
          onPress={handleClose}
          testID="unsorted-review-close"
          accessibilityLabel={t("unsortedReview.closeA11y")}
          accessibilityRole="button"
        >
          <Ionicons name="close" size={22} color={Colors.textMain} />
        </Pressable>

        <View style={styles.headerTextSection}>
          <Text style={styles.headerTitle}>{t("unsortedReview.title")}</Text>
          {/* The dots cap at seven and therefore cannot state where in the queue
              the user is. This is where that information lives, for the eye and
              for a screen reader alike. */}
          {items.length > 0 ? (
            <Text style={styles.headerPosition} accessibilityLabel={positionA11yLabel}>
              {positionLabel}
            </Text>
          ) : null}
        </View>

        {/* Balances the close button so the title block stays where it is. */}
        <View style={styles.headerSpacer} />
      </View>

      {isLoading ? (
        <View style={styles.centered}>
          <ActivityIndicator size="large" color={Colors.primary} />
        </View>
      ) : error ? (
        <View style={styles.centered}>
          <Ionicons
            name="cloud-offline-outline"
            size={48}
            color={Colors.textMuted}
          />
          <Text style={styles.centeredTitle}>{error}</Text>
          <Pressable
            style={({ pressed }) => [
              styles.primaryButton,
              pressed && styles.primaryButtonPressed,
            ]}
            onPress={() => void load()}
            accessibilityLabel={t("common.retry")}
            accessibilityRole="button"
          >
            <Text style={styles.primaryButtonLabel}>{t("common.retry")}</Text>
          </Pressable>
        </View>
      ) : items.length === 0 ? (
        // Completion, and no auto-dismiss: pulling the screen away at the moment
        // the last card is dealt with steals the confirmation of having finished.
        <View style={styles.centered} testID="unsorted-review-done">
          <Ionicons
            name="checkmark-circle-outline"
            size={56}
            color={Colors.primary}
          />
          <Text style={styles.centeredTitle}>
            {t("unsortedReview.doneTitle")}
          </Text>
          <Text style={styles.centeredBody}>
            {t("unsortedReview.doneBody")}
          </Text>
          <Pressable
            style={({ pressed }) => [
              styles.primaryButton,
              pressed && styles.primaryButtonPressed,
            ]}
            onPress={handleClose}
            testID="unsorted-review-done-close"
            accessibilityLabel={t("common.done")}
            accessibilityRole="button"
          >
            <Text style={styles.primaryButtonLabel}>{t("common.done")}</Text>
          </Pressable>
        </View>
      ) : (
        <>
          <ScrollView
            ref={pagerRef}
            style={styles.pager}
            horizontal
            pagingEnabled
            showsHorizontalScrollIndicator={false}
            onScroll={handleScroll}
            scrollEventThrottle={16}
            decelerationRate="fast"
          >
            {items.map((item) => (
              <ReviewCard key={item.media_item_id} item={item} />
            ))}
          </ScrollView>

          <View style={styles.footer}>
            <PaginationDots
              count={items.length}
              activeIndex={activeIndex}
              testID="unsorted-review-dots"
            />

            {/* Deepen is centred on the *screen*, whatever the widths of the two
                controls beside it, which is why it sits between two `flex: 1`
                gutters instead of in a `space-between` row — that would only
                spread the three, putting Deepen off centre as soon as Discard
                and Save differ in width. */}
            <View style={styles.actionBar}>
              <View style={styles.gutterStart}>
                <Pressable
                  style={({ pressed }) => [
                    styles.plainAction,
                    pressed && styles.plainActionPressed,
                  ]}
                  onPress={handleDiscard}
                  disabled={isMutating}
                  testID="unsorted-review-discard"
                  accessibilityLabel={t("unsortedReview.discardA11y", {
                    title: current?.title ?? "",
                  })}
                  accessibilityRole="button"
                  accessibilityState={{ disabled: isMutating }}
                >
                  {/* The error tint is the only warning there is: the deletion
                      leaves on this tap with no dialog behind it. Save keeps the
                      hierarchy anyway — it is the one filled control. */}
                  <Ionicons name="close" size={26} color={Colors.error} />
                  <Text style={[styles.plainActionLabel, styles.discardLabel]}>
                    {t("unsortedReview.discard")}
                  </Text>
                </Pressable>
              </View>

              <Pressable
                style={({ pressed }) => [
                  styles.plainAction,
                  pressed && styles.plainActionPressed,
                ]}
                onPress={handleDeepen}
                testID="unsorted-review-deepen"
                accessibilityLabel={t("unsortedReview.deepenA11y", {
                  title: current?.title ?? "",
                })}
                accessibilityRole="button"
              >
                <Ionicons
                  name="book-outline"
                  size={26}
                  color={Colors.textMain}
                />
                <Text style={styles.plainActionLabel}>
                  {t("unsortedReview.deepen")}
                </Text>
              </Pressable>

              <View style={styles.gutterEnd}>
                <Pressable
                  style={({ pressed }) => [
                    styles.saveAction,
                    pressed && styles.saveActionPressed,
                  ]}
                  onPress={handleSavePress}
                  disabled={isMutating}
                  testID="unsorted-review-save"
                  accessibilityLabel={t("unsortedReview.saveA11y", {
                    title: current?.title ?? "",
                  })}
                  accessibilityRole="button"
                  accessibilityState={{ disabled: isMutating }}
                >
                  <Ionicons
                    name="folder-open"
                    size={30}
                    color={Colors.onPrimary}
                  />
                  <Text style={styles.saveActionLabel}>
                    {t("unsortedReview.save")}
                  </Text>
                </Pressable>
              </View>
            </View>
          </View>
        </>
      )}

      <CollectionSaveSheet
        visible={saveTargetId !== null}
        mediaItemId={saveTargetId}
        collections={collections}
        onClose={() => setSaveTargetId(null)}
        onCollectionCreated={handleCollectionCreated}
        onSaved={handleSaved}
      />
    </SafeAreaView>
  );
}

// --- Sub-components ---

/**
 * One page of the pager: the cover small and top-left, the title beside it, the
 * creator under the title, then the blurb below the whole block.
 *
 * The blurb gets its own vertical `ScrollView` so that a long one scrolls inside
 * the card instead of growing it and pushing the action bar off the screen —
 * which would leave the user swiping with nothing to decide with.
 */
function ReviewCard({ item }: { item: MediaListItem }): React.JSX.Element {
  // Kept per card rather than per screen: a cover that failed on one media says
  // nothing about the next one's.
  const [coverFailed, setCoverFailed] = useState(false);

  const mediaType = (item.media_type ?? "unknown") as MediaType;
  const coverUrl = item.media_image?.trim() ?? "";
  const showCover = coverUrl.length > 0 && !coverFailed;

  const creator = item.creator_name?.trim() ?? "";
  // Same subtitle policy as `MediaListCard`: five sources can never have a
  // creator, and the domain is then the only thing that says where this came
  // from. The line is never doubled up.
  let subtitle = creator;
  if (!subtitle) {
    const sourceUrl = item.source_url ?? "";
    try {
      subtitle = new URL(sourceUrl).hostname.replace(/^www\./, "");
    } catch {
      subtitle = sourceUrl;
    }
  }

  const blurb = item.review_blurb?.trim() ?? "";

  return (
    <View style={styles.page}>
      <View style={styles.card}>
        <View style={styles.cardHeader}>
          <View style={styles.coverContainer}>
            {showCover ? (
              <Image
                source={{
                  uri: coverUrl,
                  // The signature of a re-hosted cover rotates; keying the cache
                  // on the item and its last change is what stops a re-download
                  // on every read (task-302 §6.2).
                  cacheKey: `${item.media_item_id}:${item.updated_at}`,
                }}
                recyclingKey={item.media_item_id}
                cachePolicy="memory-disk"
                contentFit="cover"
                transition={150}
                priority="low"
                style={styles.cover}
                onError={() => setCoverFailed(true)}
                accessible={false}
              />
            ) : (
              <Ionicons
                name={getMediaTypeIcon(mediaType)}
                size={28}
                color={Colors.textMuted}
              />
            )}
          </View>

          <View style={styles.cardHeading}>
            <Text style={styles.cardTitle} numberOfLines={3}>
              {item.title}
            </Text>
            {subtitle ? (
              <Text style={styles.cardCreator} numberOfLines={1}>
                {subtitle}
              </Text>
            ) : null}
          </View>
        </View>

        <ScrollView
          style={styles.blurbScroll}
          contentContainerStyle={styles.blurbContent}
          showsVerticalScrollIndicator={false}
          nestedScrollEnabled
        >
          {/* No blurb yet — generation in flight, failed, or an item ingested
              before the artifact existed. A quiet line, and the three actions
              stay live: a decision does not need the summary. No spinner and no
              polling either; the blurb is not what the user is waiting for. */}
          <Text style={blurb ? styles.blurb : styles.blurbMissing}>
            {blurb || t("unsortedReview.noBlurb")}
          </Text>
        </ScrollView>
      </View>
    </View>
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
    flexDirection: "row",
    alignItems: "center",
    paddingHorizontal: Spacing.md,
    paddingBottom: Spacing.sm,
    gap: Spacing.md,
  },
  closeButton: {
    width: TouchTarget.minimum,
    height: TouchTarget.minimum,
    borderRadius: BorderRadius.full,
    backgroundColor: Colors.surfaceContainerHigh,
    alignItems: "center",
    justifyContent: "center",
  },
  closeButtonPressed: {
    opacity: 0.7,
  },
  headerTextSection: {
    flex: 1,
    alignItems: "center",
  },
  headerTitle: {
    fontSize: Typography.headline.fontSize,
    fontWeight: Typography.headline.fontWeight,
    color: Colors.textMain,
  },
  headerPosition: {
    fontSize: Typography.small.fontSize,
    color: Colors.textSubtle,
    marginTop: 2,
  },
  headerSpacer: {
    width: TouchTarget.minimum,
    height: TouchTarget.minimum,
  },

  // Loading / error / completion
  centered: {
    flex: 1,
    alignItems: "center",
    justifyContent: "center",
    paddingHorizontal: Spacing.xl,
    gap: Spacing.md,
  },
  centeredTitle: {
    fontSize: Typography.headline.fontSize,
    fontWeight: Typography.headline.fontWeight,
    color: Colors.textMain,
    textAlign: "center",
  },
  centeredBody: {
    fontSize: Typography.body.fontSize,
    color: Colors.textSubtle,
    textAlign: "center",
    lineHeight: Typography.body.lineHeight,
  },
  primaryButton: {
    minHeight: TouchTarget.minimum,
    justifyContent: "center",
    paddingHorizontal: Spacing.xl,
    borderRadius: BorderRadius.full,
    backgroundColor: Colors.primary,
    marginTop: Spacing.sm,
    ...Shadows.soft,
  },
  primaryButtonPressed: {
    transform: [{ scale: 0.98 }],
    opacity: 0.9,
  },
  primaryButtonLabel: {
    fontSize: Typography.label.fontSize,
    fontWeight: "600",
    color: Colors.onPrimary,
  },

  // Pager
  pager: {
    flex: 1,
  },
  page: {
    width: SCREEN_WIDTH,
    paddingHorizontal: Spacing.md,
    paddingVertical: Spacing.sm,
  },
  card: {
    flex: 1,
    backgroundColor: Colors.surface,
    borderRadius: BorderRadius.xl,
    padding: Spacing.md,
    gap: Spacing.md,
    ...Shadows.soft,
  },
  cardHeader: {
    flexDirection: "row",
    alignItems: "flex-start",
    gap: Spacing.md,
  },
  // The container is both the frame of the cover and the fallback surface, so a
  // card with a picture and one without keep the same silhouette.
  coverContainer: {
    width: COVER_WIDTH,
    height: COVER_HEIGHT,
    borderRadius: BorderRadius.lg,
    backgroundColor: Colors.surfaceContainerLow,
    alignItems: "center",
    justifyContent: "center",
    overflow: "hidden",
  },
  cover: {
    width: "100%",
    height: "100%",
  },
  cardHeading: {
    flex: 1,
    gap: Spacing.xs,
  },
  cardTitle: {
    fontSize: Typography.headline.fontSize,
    fontWeight: "700",
    color: Colors.textMain,
  },
  cardCreator: {
    fontSize: Typography.small.fontSize,
    color: Colors.textSubtle,
  },
  blurbScroll: {
    flex: 1,
    backgroundColor: Colors.surfaceContainerLow,
    borderRadius: BorderRadius.lg,
  },
  blurbContent: {
    padding: Spacing.md,
  },
  blurb: {
    fontSize: Typography.body.fontSize,
    color: Colors.textMain,
    lineHeight: Typography.body.lineHeight,
  },
  blurbMissing: {
    fontSize: Typography.body.fontSize,
    color: Colors.textSubtle,
    lineHeight: Typography.body.lineHeight,
    fontStyle: "italic",
  },

  // Footer: dots, then the three actions
  footer: {
    paddingTop: Spacing.sm,
    paddingBottom: Spacing.sm,
    gap: Spacing.sm,
  },
  actionBar: {
    flexDirection: "row",
    alignItems: "center",
    paddingHorizontal: Spacing.md,
  },
  gutterStart: {
    flex: 1,
    alignItems: "flex-start",
  },
  gutterEnd: {
    flex: 1,
    alignItems: "flex-end",
  },
  plainAction: {
    minWidth: TouchTarget.minimum,
    minHeight: TouchTarget.minimum,
    paddingHorizontal: Spacing.sm,
    alignItems: "center",
    justifyContent: "center",
    gap: Spacing.xs,
  },
  plainActionPressed: {
    opacity: 0.6,
  },
  plainActionLabel: {
    fontSize: Typography.small.fontSize,
    fontWeight: "600",
    color: Colors.textMain,
  },
  discardLabel: {
    color: Colors.error,
  },
  // The one filled control on the screen and the largest target of the three:
  // the whole point of this queue is that a media not saved stays unsorted, so
  // the button that files it is the one that has to be seen first.
  saveAction: {
    minWidth: TouchTarget.large + Spacing.md,
    minHeight: TouchTarget.large,
    paddingHorizontal: Spacing.md,
    alignItems: "center",
    justifyContent: "center",
    gap: 2,
    borderRadius: BorderRadius.xl,
    backgroundColor: Colors.primary,
    ...Shadows.soft,
  },
  saveActionPressed: {
    transform: [{ scale: 0.97 }],
    opacity: 0.9,
  },
  saveActionLabel: {
    fontSize: Typography.small.fontSize,
    fontWeight: "700",
    color: Colors.onPrimary,
  },
});
