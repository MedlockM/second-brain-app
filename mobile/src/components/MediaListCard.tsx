import React, { useState } from "react";
import { View, Text, StyleSheet, Pressable } from "react-native";
import { Image } from "expo-image";
import { Ionicons } from "@expo/vector-icons";
import {
  Colors,
  Typography,
  Spacing,
  BorderRadius,
  Shadows,
  TouchTarget,
} from "../constants/theme";
import type { MediaListItem, MediaType } from "../types/media";
import { getMediaTypeIcon } from "../lib/mediaTypeDisplay";
import { getRelativeTime } from "../lib/relativeTime";

/**
 * Uniform media row for a vertical library list: the cover, the media type and
 * the age, the title, then the creator. Tapping it opens the media detail.
 *
 * The second line holds `creator_name` and falls back to the source domain: five
 * sources can never have a creator (shared text, documents, audio files), and a
 * domain is the only other thing that says where the media comes from. The two
 * are never stacked — the row keeps a fixed height whatever the source.
 *
 * The cover is 16:9 and cropped with `contentFit="cover"`, the ratio validated
 * on the task-302 benchmark (§6.4): it matches the two highest-volume sources
 * (YouTube, `og:image`) and keeps every row the same height. It is rendered with
 * `expo-image` rather than React Native's `Image` for the three props that
 * benchmark selected it for (§6.1-6.2): a `cacheKey` that survives the rotating
 * signature of a re-hosted cover, a `recyclingKey` so a recycled row never shows
 * the previous item's picture, and an explicit `memory-disk` policy.
 *
 * With no cover — or when loading one fails — the media-type glyph is drawn on
 * `surfaceContainerLow`. There is no third state: an empty grey rectangle is the
 * anti-pattern the benchmark names (§6.3).
 */

/** 112 x 63 is exactly 16:9, wide enough to read a thumbnail on a phone. */
const COVER_WIDTH = 112;
const COVER_HEIGHT = 63;

interface MediaListCardProps {
  item: MediaListItem;
  onPress: (mediaItemId: string) => void;
  /** Set by the list rendering the row so a flow can address it. */
  testID?: string;
}

export function MediaListCard({
  item,
  onPress,
  testID,
}: MediaListCardProps): React.JSX.Element {
  // Keyed by media id rather than a bare boolean: a `FlatList` cell can be
  // handed a different item, and a failure recorded for the previous one must
  // not hide the new one's cover.
  const [failedCoverId, setFailedCoverId] = useState<string | null>(null);

  const sourceUrl = item.source_url ?? "";

  let displayDomain: string;
  try {
    displayDomain = new URL(sourceUrl).hostname.replace(/^www\./, "");
  } catch {
    displayDomain = sourceUrl;
  }

  const mediaType = (item.media_type ?? "unknown") as MediaType;
  const mediaTypeLabel = getMediaTypeLabel(mediaType);
  const mediaTypeBgColor = getMediaTypeBgColor(mediaType);
  const timeAgo = getRelativeTime(item.created_at);
  const icon = getMediaTypeIcon(mediaType);

  // The backend always stores a non-empty, human-readable title (task-266), so
  // there is nothing left to invent here. The previous fallback rendered the
  // raw source URL, which duplicated the domain line right below it.
  const displayTitle = item.title;

  const creator = item.creator_name?.trim() ?? "";
  const subtitle = creator || displayDomain;

  const coverUrl = item.media_image?.trim() ?? "";
  const showCover = coverUrl.length > 0 && failedCoverId !== item.media_item_id;

  return (
    <Pressable
      testID={testID}
      style={({ pressed }) => [styles.card, pressed && styles.cardPressed]}
      onPress={() => onPress(item.media_item_id)}
      accessibilityLabel={
        creator
          ? `${displayTitle} by ${creator}, ${mediaTypeLabel}`
          : `${displayTitle}, ${mediaTypeLabel} from ${displayDomain}`
      }
      accessibilityRole="button"
    >
      <View style={styles.cardContent}>
        <View style={styles.coverContainer}>
          {showCover ? (
            <Image
              source={{
                uri: coverUrl,
                cacheKey: `${item.media_item_id}:${item.updated_at}`,
              }}
              recyclingKey={item.media_item_id}
              cachePolicy="memory-disk"
              contentFit="cover"
              transition={150}
              priority="low"
              style={styles.cover}
              onError={() => setFailedCoverId(item.media_item_id)}
              accessible={false}
            />
          ) : (
            <Ionicons name={icon} size={28} color={Colors.textMuted} />
          )}
        </View>

        <View style={styles.cardTextSection}>
          <View style={styles.cardMeta}>
            <View
              style={[styles.typeBadge, { backgroundColor: mediaTypeBgColor }]}
            >
              <Text style={styles.typeBadgeText}>{mediaTypeLabel}</Text>
            </View>
            <Text style={styles.timeText}>{timeAgo}</Text>
          </View>

          <Text style={styles.cardTitle} numberOfLines={2}>
            {displayTitle}
          </Text>

          {subtitle ? (
            <Text style={styles.cardSubtitle} numberOfLines={1}>
              {subtitle}
            </Text>
          ) : null}
        </View>
      </View>
    </Pressable>
  );
}

// --- Helpers (kept in sync with the inbox vignette presentation) ---


function getMediaTypeLabel(type: MediaType): string {
  switch (type) {
    case "podcast_episode":
      return "PODCAST";
    case "article":
      return "ARTICLE";
    case "youtube_video":
      return "VIDEO";
    case "short_video":
      return "SHORT";
    case "audio_file":
    case "audio":
      return "AUDIO";
    case "shared_text":
      return "TEXT";
    case "document":
      return "DOC";
    default:
      return "LINK";
  }
}

function getMediaTypeBgColor(type: MediaType): string {
  switch (type) {
    case "podcast_episode":
      return Colors.primary;
    case "youtube_video":
    case "short_video":
      return Colors.errorContainer;
    case "article":
      return Colors.surfaceContainerHigh;
    default:
      return Colors.surfaceContainerHigh;
  }
}


const styles = StyleSheet.create({
  card: {
    backgroundColor: Colors.surface,
    borderRadius: BorderRadius.xl,
    padding: Spacing.sm + 4,
    marginHorizontal: Spacing.md,
    marginBottom: Spacing.md,
    minHeight: TouchTarget.comfortable,
    ...Shadows.soft,
  },
  cardPressed: {
    transform: [{ scale: 0.98 }],
    opacity: 0.9,
  },
  cardContent: {
    flexDirection: "row",
    alignItems: "center",
    gap: Spacing.md,
  },
  // The container is the fallback surface *and* the frame of the cover: one
  // tonal rectangle either way, so a row with a picture and a row without have
  // the same silhouette.
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
  cardTextSection: {
    flex: 1,
    paddingVertical: Spacing.xs,
    gap: 2,
  },
  cardMeta: {
    flexDirection: "row",
    alignItems: "center",
    gap: Spacing.sm,
    marginBottom: Spacing.xs,
  },
  typeBadge: {
    paddingHorizontal: Spacing.sm,
    paddingVertical: 2,
    borderRadius: BorderRadius.md,
  },
  typeBadgeText: {
    fontSize: Typography.small.fontSize,
    fontWeight: "700",
    color: Colors.textMain,
    letterSpacing: 0.5,
  },
  timeText: {
    fontSize: Typography.small.fontSize,
    color: Colors.textMuted,
  },
  cardTitle: {
    fontSize: Typography.body.fontSize,
    fontWeight: "700",
    color: Colors.textMain,
    lineHeight: 22,
  },
  cardSubtitle: {
    fontSize: Typography.small.fontSize,
    color: Colors.textSubtle,
  },
});
