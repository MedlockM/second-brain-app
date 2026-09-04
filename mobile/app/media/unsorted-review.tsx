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
  type LayoutChangeEvent,
  type NativeScrollEvent,
  type NativeSyntheticEvent,
} from "react-native";
import { Image } from "expo-image";
import {
  initialWindowMetrics,
  useSafeAreaInsets,
} from "react-native-safe-area-context";
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
import { Bullets } from "../../src/components/Bullets";
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

/**
 * The most lines the triage card ever gives one bullet, and the value it starts
 * from before measuring. Past three a bullet stops being glanceable, and three is
 * what the blurb prompt's lengths need on a 390 pt-wide screen.
 */
const MAX_BULLET_LINES = 3;

export default function UnsortedReviewScreen(): React.JSX.Element {
  // Copy resolved on render: the screen redraws with the interface language.
  useTranslation();
  const router = useRouter();

  /**
   * Safe area applied by hand, with the launch metrics as a floor.
   *
   * This screen is a `fullScreenModal`: it covers the status bar and the home
   * indicator, so it owns its insets — but it reads them from the provider that
   * measures the view it was presented *over*, and iOS zeroes that view's
   * `safeAreaInsets` while a full-screen modal is up. A plain `SafeAreaView`
   * therefore lays the header out at y = 0, under the clock. `initialWindowMetrics`
   * is captured natively at launch and never collapses, so it is the floor here
   * rather than the value.
   */
  const insets = useSafeAreaInsets();
  const topInset = Math.max(insets.top, initialWindowMetrics?.insets.top ?? 0);
  const bottomInset = Math.max(
    insets.bottom,
    initialWindowMetrics?.insets.bottom ?? 0,
  );

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
    <View
      testID="unsorted-review-screen"
      style={[
        styles.container,
        { paddingTop: topInset, paddingBottom: bottomInset },
      ]}
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
          <Text style={styles.headerTitle} numberOfLines={1}>
            {t("unsortedReview.title")}
          </Text>
          {/* The dots cap at seven and therefore cannot state where in the queue
              the user is. This is where that information lives, for the eye and
              for a screen reader alike. */}
          {items.length > 0 ? (
            <Text
              style={styles.headerPosition}
              accessibilityLabel={positionA11yLabel}
              numberOfLines={1}
            >
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
                      leaves on this tap with no dialog behind it. */}
                  <Ionicons name="close" size={26} color={Colors.error} />
                  <Text
                    style={[styles.plainActionLabel, styles.discardLabel]}
                    numberOfLines={1}
                  >
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
                <Text style={styles.plainActionLabel} numberOfLines={1}>
                  {t("unsortedReview.deepen")}
                </Text>
              </Pressable>

              <View style={styles.gutterEnd}>
                <Pressable
                  style={({ pressed }) => [
                    styles.plainAction,
                    pressed && styles.plainActionPressed,
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
                  {/* The brand amber, carried by the glyph alone: the three
                      actions share one shape, and this is the one the screen
                      exists for. The label stays `textMain` — amber on the
                      background is nowhere near readable at 13px. */}
                  <Ionicons
                    name="folder-open"
                    size={26}
                    color={Colors.primary}
                  />
                  <Text style={styles.plainActionLabel} numberOfLines={1}>
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
    </View>
  );
}

// --- Sub-components ---

/**
 * One page of the pager: the cover small and top-left, the title beside it, the
 * creator under the title, then the triage card below the whole block.
 *
 * The card never scrolls. Its first shape wrapped a prose paragraph in a nested
 * vertical `ScrollView`, which failed at the one job of this screen: a summary you
 * have to scroll is not a summary you can decide on, and the nested scroller stole
 * swipes meant for the pager. The blurb is now a hook and a few bullets, and the
 * card gives each bullet as many lines as it can actually spare, so it fits
 * whatever the model wrote and the action bar stays put.
 *
 * That last part is measured, not assumed, and it took a TestFlight report to get
 * there. A fixed `numberOfLines={3}` is not a fit: three lines a bullet is what the
 * prompt's lengths need on a 390 pt-wide screen, where the blurb box has room for
 * about twelve. Narrow the screen — an iPhone 13 in Display Zoom is 320 pt — and
 * the same 65-character bullet wraps onto three lines while the box loses height,
 * so a three-line hook and four bullets want ~327 pt of a 295 pt box. Nothing
 * clamped them: the box is `flex: 1` inside a card whose height the pager fixes,
 * and `flexShrink` is 0 by default in React Native, so the list ran past the
 * padding and the last line came to rest on the frame with its descenders outside
 * it — "collé à l'encadrement sans espacement", in the tester's words.
 *
 * So `fitBullets` lowers the per-bullet cap by one and lets the layout re-measure,
 * until the list fits the room the box has left with its bottom padding intact.
 * The text that no longer fits is paid for with an ellipsis, spread evenly over the
 * bullets rather than taken out of any one of them. Two alternatives are worse for
 * a triage pass: dropping the bullets that do not fit loses whole topics where
 * clipping only loses the tail of a fragment whose head still names one
 * ("Limites : …"), and tightening the type or the line height would write a
 * per-screen exception into a design system that fixes body text at 16/1.6. A
 * second scroll axis inside the pager is not on the table at all — see above.
 *
 * The caps stay a backstop and not a layout mechanism: the prompt asks for lengths
 * the card can render, so an ellipsis on a roomy screen still means the model
 * overran. Raising `MAX_BULLET_LINES` instead of shortening the text is the wrong
 * fix — a clipped bullet carries less than a shorter one.
 */
function ReviewCard({ item }: { item: MediaListItem }): React.JSX.Element {
  // Kept per card rather than per screen: a cover that failed on one media says
  // nothing about the next one's.
  const [coverFailed, setCoverFailed] = useState(false);

  const [bulletLines, setBulletLines] = useState(MAX_BULLET_LINES);

  /**
   * The measurements `fitBullets` works from, in refs and not in state.
   *
   * Refs because they are inputs to a decision, not things to render: holding them
   * in state would redraw the card once per measurement for nothing. And the
   * decision runs from the layout handlers rather than from an effect watching
   * them — `react-hooks/set-state-in-effect` is an error in this project, and a
   * layout event is exactly where a layout-driven `setState` belongs.
   */
  const boxHeight = useRef<number | null>(null);
  const hookHeight = useRef<number | null>(null);
  const listHeight = useRef<number | null>(null);
  /** The room the cap currently in force was fitted against. */
  const fittedRoom = useRef<number | null>(null);

  /**
   * Shrink the bullets by one line if they overrun the box, one measurement at a
   * time.
   *
   * Called from all three layout handlers, so whichever of them fires last in a
   * layout pass is the one that has the full picture — the order they arrive in is
   * not guaranteed and does not matter. Each shrink re-lays out the list, which
   * fires its handler again, which is how this converges: three passes at worst,
   * and at one line a bullet `Math.max` returns the value already held and React
   * stops re-rendering.
   *
   * Deliberately monotonic. It only ever shrinks within a given box, so the sole
   * way back up is a box that actually grew — a live text-size change, say — which
   * resets the cap rather than leaving the list stuck at what an earlier, smaller
   * box could take.
   */
  const fitBullets = useCallback(() => {
    const box = boxHeight.current;
    const hook = hookHeight.current;
    const list = listHeight.current;
    if (box === null || hook === null || list === null) return;

    // The box reports its own height, padding included, and what separates the
    // hook from the list is the box's own `gap`.
    const room = box - 2 * Spacing.md - hook - Spacing.sm;

    if (fittedRoom.current !== null && room > fittedRoom.current + 1) {
      fittedRoom.current = room;
      setBulletLines(MAX_BULLET_LINES);
      return;
    }
    fittedRoom.current = room;

    if (list > room) setBulletLines((prev) => Math.max(1, prev - 1));
  }, []);

  const handleBlurbLayout = useCallback(
    (event: LayoutChangeEvent) => {
      boxHeight.current = event.nativeEvent.layout.height;
      fitBullets();
    },
    [fitBullets],
  );

  const handleHookLayout = useCallback(
    (event: LayoutChangeEvent) => {
      hookHeight.current = event.nativeEvent.layout.height;
      fitBullets();
    },
    [fitBullets],
  );

  const handleBulletsLayout = useCallback(
    (event: LayoutChangeEvent) => {
      listHeight.current = event.nativeEvent.layout.height;
      fitBullets();
    },
    [fitBullets],
  );

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

  const blurb = item.review_blurb ?? null;
  const hook = blurb?.hook?.trim() ?? "";
  const points = (blurb?.points ?? []).map((p) => p.trim()).filter(Boolean);

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

        <View style={styles.blurbCard} onLayout={handleBlurbLayout}>
          {hook ? (
            <>
              <Text
                style={styles.blurbHook}
                numberOfLines={3}
                onLayout={handleHookLayout}
              >
                {hook}
              </Text>
              {/* The wrapper is there to be measured. `Bullets` is shared with the
                  artifact screen, which has no use for a layout callback, so the
                  one screen that needs the height reads it from a view of its own
                  rather than putting an `onLayout` prop on the component. */}
              {points.length > 0 ? (
                <View onLayout={handleBulletsLayout}>
                  <Bullets items={points} numberOfLines={bulletLines} />
                </View>
              ) : null}
            </>
          ) : (
            /* No blurb yet — generation in flight, failed, or an item ingested
               before the artifact existed. A quiet line, and the three actions
               stay live: a decision does not need the summary. No spinner and no
               polling either; the blurb is not what the user is waiting for. */
            <Text style={styles.blurbMissing}>{t("unsortedReview.noBlurb")}</Text>
          )}
        </View>
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
    // Below the status bar, not against it: the safe area inset stops the
    // content overlapping the clock, it does not give the header any air.
    paddingTop: Spacing.sm,
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
  blurbCard: {
    flex: 1,
    backgroundColor: Colors.surfaceContainerLow,
    borderRadius: BorderRadius.lg,
    padding: Spacing.md,
    gap: Spacing.sm,
    // The floor under `fitBullets`: at one line a bullet it stops shrinking, and on
    // a box too small even for that the spill is cut by the frame instead of being
    // drawn over the white card behind it.
    overflow: "hidden",
  },
  blurbHook: {
    fontSize: Typography.body.fontSize,
    fontWeight: "600",
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
    // Three labels share one row: each one has to give ground rather than wrap
    // and drag the whole bar out of alignment.
    flexShrink: 1,
    fontSize: Typography.small.fontSize,
    fontWeight: "600",
    color: Colors.textMain,
  },
  discardLabel: {
    color: Colors.error,
  },
});
