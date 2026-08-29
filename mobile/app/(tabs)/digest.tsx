import React, { useState, useCallback, useEffect, useRef } from "react";
import {
  View,
  Text,
  StyleSheet,
  ScrollView,
  Pressable,
  RefreshControl,
  Dimensions,
  NativeSyntheticEvent,
  NativeScrollEvent,
  Image,
  ActivityIndicator,
} from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";
import { useRouter } from "expo-router";
import { useAuth } from "../../src/contexts/AuthContext";
import { DigestService } from "../../src/services/digestService";
import {
  Colors,
  Typography,
  Spacing,
  BorderRadius,
  Shadows,
  TouchTarget,
} from "../../src/constants/theme";
import { t, tCount, useTranslation } from "../../src/i18n";
import type {
  DailyDigest,
  WeeklyDigest,
  DigestMediaItem,
} from "../../src/types/digest";

const { width: SCREEN_WIDTH } = Dimensions.get("window");
const CARD_HORIZONTAL_MARGIN = Spacing.lg;
const CARD_WIDTH = SCREEN_WIDTH - CARD_HORIZONTAL_MARGIN * 2;

type DigestTab = "daily" | "weekly";

/**
 * Digest screen with daily/weekly toggle and insight card carousel.
 * Matches the "Your Day in Review" / "Your Week in Review" mockup designs.
 */
export default function DigestScreen() {
  // Resolved-on-render copy: the screen has to redraw with the language.
  useTranslation();
  const { isAuthenticated } = useAuth();
  const router = useRouter();

  const [activeTab, setActiveTab] = useState<DigestTab>("daily");
  const [dailyDigest, setDailyDigest] = useState<DailyDigest | null>(null);
  const [weeklyDigest, setWeeklyDigest] = useState<WeeklyDigest | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [activeCardIndex, setActiveCardIndex] = useState(0);

  const scrollViewRef = useRef<ScrollView>(null);

  const fetchDigest = useCallback(
    async (tab: DigestTab) => {
      if (!isAuthenticated) return;

      try {
        if (tab === "daily") {
          const data = await DigestService.getDailyDigest();
          setDailyDigest(data);
        } else {
          const data = await DigestService.getWeeklyDigest();
          setWeeklyDigest(data);
        }
      } catch (err: unknown) {
        const message =
          err instanceof Error ? err.message : t("digest.loadFailed");
        setError(message);
      } finally {
        setIsLoading(false);
        setIsRefreshing(false);
      }
    },
    [isAuthenticated],
  );

  useEffect(() => {
    const timer = setTimeout(() => void fetchDigest(activeTab), 0);
    return () => clearTimeout(timer);
  }, [activeTab, fetchDigest]);

  const handleRefresh = useCallback(() => {
    setIsRefreshing(true);
    setError(null);
    void fetchDigest(activeTab);
  }, [activeTab, fetchDigest]);

  const handleTabChange = useCallback((tab: DigestTab) => {
    if (tab === activeTab) return;
    setActiveTab(tab);
    setIsLoading(true);
    setError(null);
    setActiveCardIndex(0);
    scrollViewRef.current?.scrollTo({ x: 0, animated: false });
  }, [activeTab]);

  const handleScroll = useCallback(
    (event: NativeSyntheticEvent<NativeScrollEvent>) => {
      const offsetX = event.nativeEvent.contentOffset.x;
      const index = Math.round(offsetX / SCREEN_WIDTH);
      setActiveCardIndex(index);
    },
    [],
  );

  const handleMediaPress = useCallback(
    (mediaItemId: string) => {
      router.push(`/media/${mediaItemId}` as never);
    },
    [router],
  );

  // Derive display data from the active tab
  const items: DigestMediaItem[] =
    activeTab === "daily"
      ? dailyDigest?.media_items ?? []
      : weeklyDigest?.top_items ?? [];

  const headerTitle =
    activeTab === "daily" ? t("digest.dailyTitle") : t("digest.weeklyTitle");

  const headerSubtitle =
    activeTab === "daily"
      ? tCount("digest.dailySubtitle", items.length)
      : tCount("digest.weeklySubtitle", items.length);

  return (
    <SafeAreaView style={styles.container} edges={["top"]}>
      {/* Segmented Control */}
      <View style={styles.segmentedControlContainer}>
        <View style={styles.segmentedControl}>
          <Pressable
            style={[
              styles.segmentButton,
              activeTab === "daily" && styles.segmentButtonActive,
            ]}
            onPress={() => handleTabChange("daily")}
          >
            <Text
              style={[
                styles.segmentButtonText,
                activeTab === "daily" && styles.segmentButtonTextActive,
              ]}
            >
              {t("digest.daily")}
            </Text>
          </Pressable>
          <Pressable
            style={[
              styles.segmentButton,
              activeTab === "weekly" && styles.segmentButtonActive,
            ]}
            onPress={() => handleTabChange("weekly")}
          >
            <Text
              style={[
                styles.segmentButtonText,
                activeTab === "weekly" && styles.segmentButtonTextActive,
              ]}
            >
              {t("digest.weekly")}
            </Text>
          </Pressable>
        </View>
      </View>

      {/* Header */}
      <View style={styles.header}>
        <Text style={styles.headerTitle}>{headerTitle}</Text>
        <Text style={styles.headerSubtitle}>{headerSubtitle}</Text>
      </View>

      {/* Content */}
      {isLoading ? (
        <View style={styles.centeredContent}>
          <ActivityIndicator size="large" color={Colors.primary} />
        </View>
      ) : error ? (
        <ScrollView
          contentContainerStyle={styles.centeredContent}
          refreshControl={
            <RefreshControl
              refreshing={isRefreshing}
              onRefresh={handleRefresh}
              tintColor={Colors.primary}
            />
          }
        >
          <Text style={styles.errorText}>{error}</Text>
          <Pressable style={styles.retryButton} onPress={handleRefresh}>
            <Text style={styles.retryButtonText}>{t("digest.tryAgain")}</Text>
          </Pressable>
        </ScrollView>
      ) : items.length === 0 ? (
        <ScrollView
          contentContainerStyle={styles.centeredContent}
          refreshControl={
            <RefreshControl
              refreshing={isRefreshing}
              onRefresh={handleRefresh}
              tintColor={Colors.primary}
            />
          }
        >
          <EmptyState tab={activeTab} />
        </ScrollView>
      ) : (
        <View style={styles.carouselContainer}>
          {/* Pagination Dots */}
          <View style={styles.paginationDots}>
            {items.map((_, index) => (
              <View
                key={index}
                style={[
                  styles.dot,
                  index === activeCardIndex
                    ? styles.dotActive
                    : styles.dotInactive,
                ]}
              />
            ))}
          </View>

          {/* Carousel */}
          <ScrollView
            ref={scrollViewRef}
            horizontal
            pagingEnabled
            showsHorizontalScrollIndicator={false}
            onScroll={handleScroll}
            scrollEventThrottle={16}
            decelerationRate="fast"
            contentContainerStyle={styles.carouselContent}
            refreshControl={
              <RefreshControl
                refreshing={isRefreshing}
                onRefresh={handleRefresh}
                tintColor={Colors.primary}
              />
            }
          >
            {items.map((item) => (
              <InsightCard
                key={item.media_item_id}
                item={item}
                onPress={() => handleMediaPress(item.media_item_id)}
              />
            ))}
          </ScrollView>
        </View>
      )}
    </SafeAreaView>
  );
}

// --- Sub-components ---

function EmptyState({ tab }: { tab: DigestTab }) {
  return (
    <View style={styles.emptyState}>
      <Text style={styles.emptyStateTitle}>
        {tab === "daily" ? t("digest.emptyDaily") : t("digest.emptyWeekly")}
      </Text>
      <Text style={styles.emptyStateHint}>
        {tab === "daily"
          ? t("digest.emptyDailyHint")
          : t("digest.emptyWeeklyHint")}
      </Text>
    </View>
  );
}

function InsightCard({
  item,
  onPress,
}: {
  item: DigestMediaItem;
  onPress: () => void;
}) {
  const readTime = item.read_time_minutes
    ? tCount("digest.readTime", item.read_time_minutes)
    : "";

  // Extract a "key quote" from the summary_excerpt (first sentence as emphasis)
  const excerptParts = item.summary_excerpt.split(". ");
  const keyQuote = excerptParts[0] + (excerptParts.length > 1 ? "." : "");
  const remainingExcerpt =
    excerptParts.length > 1 ? excerptParts.slice(1).join(". ") : "";

  return (
    <Pressable style={styles.cardWrapper} onPress={onPress}>
      <View style={styles.card}>
        {/* Thumbnail area */}
        <View style={styles.cardThumbnail}>
          {item.thumbnail_url ? (
            <Image
              source={{ uri: item.thumbnail_url }}
              style={styles.cardThumbnailImage}
              resizeMode="cover"
            />
          ) : (
            <View style={styles.cardThumbnailPlaceholder} />
          )}
          {/* Gradient overlay */}
          <View style={styles.cardThumbnailOverlay} />
          {/* Badges */}
          <View style={styles.cardBadgeRow}>
            <View style={styles.mediaTypeBadge}>
              <Text style={styles.mediaTypeBadgeText} numberOfLines={1}>
                {formatMediaType(item.media_type)}
              </Text>
            </View>
            {readTime ? (
              <Text style={styles.readTimeBadge} numberOfLines={1}>
                {readTime}
              </Text>
            ) : null}
          </View>
        </View>

        {/* Content area */}
        <View style={styles.cardContent}>
          <Text style={styles.cardSource}>
            {item.title}
          </Text>
          <View style={styles.quoteContainer}>
            <Text style={styles.quoteDecoration}>{"“"}</Text>
            <Text style={styles.cardQuote}>{keyQuote}</Text>
          </View>
          {remainingExcerpt ? (
            <Text style={styles.cardExcerpt}>{remainingExcerpt}</Text>
          ) : null}
        </View>
      </View>
    </Pressable>
  );
}

// --- Helpers ---

function formatMediaType(type: string): string {
  const map: Record<string, string> = {
    podcast_episode: t("digest.type.podcast"),
    article: t("digest.type.article"),
    // YouTube is a brand, so it is the same word in every catalogue — it still
    // goes through one so the map has a single shape.
    youtube_video: t("digest.type.youtube"),
    short_video: t("digest.type.video"),
    audio_file: t("digest.type.audio"),
    shared_text: t("digest.type.text"),
  };
  return map[type] || type.charAt(0).toUpperCase() + type.slice(1);
}

// --- Styles ---

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: Colors.background,
  },

  // Segmented Control
  segmentedControlContainer: {
    paddingHorizontal: Spacing.lg,
    paddingTop: Spacing.md,
    paddingBottom: Spacing.sm,
  },
  segmentedControl: {
    flexDirection: "row",
    backgroundColor: Colors.surfaceContainerLow,
    borderRadius: BorderRadius.full,
    padding: 3,
  },
  segmentButton: {
    flex: 1,
    paddingVertical: Spacing.sm + 2,
    alignItems: "center",
    borderRadius: BorderRadius.full,
    minHeight: 40,
    justifyContent: "center",
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
    paddingTop: Spacing.md,
    paddingBottom: Spacing.sm,
  },
  headerTitle: {
    fontSize: 28,
    fontWeight: "700",
    color: Colors.textMain,
    letterSpacing: -0.5,
  },
  headerSubtitle: {
    fontSize: Typography.small.fontSize,
    color: Colors.textMuted,
    marginTop: Spacing.xs,
  },

  // Loading / Error / Empty
  centeredContent: {
    flex: 1,
    justifyContent: "center",
    alignItems: "center",
    paddingHorizontal: Spacing.xl,
  },
  errorText: {
    fontSize: Typography.body.fontSize,
    color: Colors.error,
    textAlign: "center",
    marginBottom: Spacing.md,
  },
  retryButton: {
    backgroundColor: Colors.primary,
    paddingHorizontal: Spacing.lg,
    paddingVertical: Spacing.sm + 2,
    borderRadius: BorderRadius.full,
    minHeight: TouchTarget.minimum,
    justifyContent: "center",
    alignItems: "center",
  },
  retryButtonText: {
    fontSize: Typography.label.fontSize,
    fontWeight: "600",
    color: Colors.onPrimary,
  },

  // Empty state
  emptyState: {
    alignItems: "center",
    paddingHorizontal: Spacing.xl,
  },
  emptyStateTitle: {
    fontSize: Typography.headline.fontSize,
    fontWeight: Typography.headline.fontWeight,
    color: Colors.textMain,
    textAlign: "center",
    marginBottom: Spacing.sm,
  },
  emptyStateHint: {
    fontSize: Typography.body.fontSize,
    color: Colors.textMuted,
    textAlign: "center",
    lineHeight: Typography.body.lineHeight,
  },

  // Carousel
  carouselContainer: {
    flex: 1,
  },
  carouselContent: {
    paddingHorizontal: 0,
  },
  paginationDots: {
    flexDirection: "row",
    justifyContent: "center",
    alignItems: "center",
    paddingVertical: Spacing.md,
    gap: Spacing.sm,
  },
  dot: {
    width: 8,
    height: 8,
    borderRadius: 4,
  },
  dotActive: {
    backgroundColor: Colors.textMain,
  },
  dotInactive: {
    backgroundColor: Colors.outlineVariant,
  },

  // Card
  cardWrapper: {
    width: SCREEN_WIDTH,
    paddingHorizontal: CARD_HORIZONTAL_MARGIN,
    flex: 1,
  },
  card: {
    flex: 1,
    backgroundColor: Colors.surface,
    borderRadius: BorderRadius.xl,
    overflow: "hidden",
    borderWidth: StyleSheet.hairlineWidth,
    borderColor: "rgba(0,0,0,0.05)",
    ...Shadows.soft,
  },

  // Card thumbnail
  cardThumbnail: {
    height: 192,
    width: "100%",
    position: "relative",
    backgroundColor: Colors.surfaceContainerHigh,
  },
  cardThumbnailImage: {
    ...StyleSheet.absoluteFillObject,
  },
  cardThumbnailPlaceholder: {
    ...StyleSheet.absoluteFillObject,
    backgroundColor: Colors.surfaceContainerHigh,
  },
  cardThumbnailOverlay: {
    ...StyleSheet.absoluteFillObject,
    // Gradient approximation: darker at bottom
    backgroundColor: "rgba(0,0,0,0.3)",
  },
  cardBadgeRow: {
    position: "absolute",
    bottom: Spacing.md,
    left: Spacing.md,
    right: Spacing.md,
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "flex-end",
  },
  mediaTypeBadge: {
    // Both badges sit on the thumbnail with nothing between them: without a
    // shrink they meet in the middle and overlap in the longer languages.
    flexShrink: 1,
    paddingHorizontal: 12,
    paddingVertical: 4,
    backgroundColor: "rgba(255,255,255,0.2)",
    borderRadius: BorderRadius.full,
    borderWidth: 1,
    borderColor: "rgba(255,255,255,0.3)",
  },
  mediaTypeBadgeText: {
    color: "#ffffff",
    fontSize: 11,
    fontWeight: "600",
    textTransform: "uppercase",
    letterSpacing: 0.5,
  },
  readTimeBadge: {
    flexShrink: 0,
    marginStart: Spacing.sm,
    color: "rgba(255,255,255,0.9)",
    fontSize: Typography.small.fontSize,
    fontWeight: "500",
  },

  // Card content
  cardContent: {
    flex: 1,
    padding: Spacing.lg,
    justifyContent: "center",
  },
  cardSource: {
    fontSize: Typography.small.fontSize,
    fontWeight: "600",
    color: Colors.textMuted,
    textTransform: "uppercase",
    letterSpacing: 0.8,
    marginBottom: Spacing.sm + 4,
  },
  quoteContainer: {
    position: "relative",
    marginBottom: Spacing.lg,
  },
  quoteDecoration: {
    position: "absolute",
    top: -16,
    left: -8,
    fontSize: 56,
    color: "rgba(255,203,5,0.2)",
    fontFamily: "serif",
    lineHeight: 56,
  },
  cardQuote: {
    fontSize: 22,
    fontWeight: "700",
    color: Colors.textMain,
    lineHeight: 30,
  },
  cardExcerpt: {
    fontSize: Typography.body.fontSize,
    fontWeight: Typography.body.fontWeight,
    color: Colors.textMuted,
    lineHeight: Typography.body.lineHeight,
  },
});
