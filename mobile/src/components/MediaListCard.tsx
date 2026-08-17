import React from "react";
import { View, Text, StyleSheet, Pressable } from "react-native";
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

/**
 * Uniform media row used to list `MediaListItem` results outside the inbox
 * (e.g. inside the collections explorer). Tapping it opens the media detail,
 * matching the inbox/search behaviour.
 */
interface MediaListCardProps {
  item: MediaListItem;
  onPress: (mediaItemId: string) => void;
}

export function MediaListCard({ item, onPress }: MediaListCardProps): React.JSX.Element {
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

  return (
    <Pressable
      style={({ pressed }) => [styles.card, pressed && styles.cardPressed]}
      onPress={() => onPress(item.media_item_id)}
      accessibilityLabel={`${mediaTypeLabel} from ${displayDomain}`}
      accessibilityRole="button"
    >
      <View style={styles.cardContent}>
        <View style={styles.thumbnailContainer}>
          <Ionicons name={icon} size={28} color={Colors.textMuted} />
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

          {displayDomain ? (
            <Text style={styles.cardDomain} numberOfLines={1}>
              {displayDomain}
            </Text>
          ) : null}
        </View>
      </View>
    </Pressable>
  );
}

// --- Helpers (kept in sync with the inbox vignette presentation) ---

function getRelativeTime(isoDate: string): string {
  const now = Date.now();
  const date = new Date(isoDate).getTime();
  const diffMs = now - date;
  const diffMins = Math.floor(diffMs / 60000);
  const diffHours = Math.floor(diffMs / 3600000);
  const diffDays = Math.floor(diffMs / 86400000);

  if (diffMins < 1) return "Just now";
  if (diffMins < 60) return `${diffMins}m ago`;
  if (diffHours < 24) return `${diffHours}h ago`;
  if (diffDays === 1) return "Yesterday";
  if (diffDays < 7) return `${diffDays}d ago`;
  return new Date(isoDate).toLocaleDateString(undefined, {
    month: "short",
    day: "numeric",
  });
}

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

function getMediaTypeIcon(
  type: MediaType,
): React.ComponentProps<typeof Ionicons>["name"] {
  switch (type) {
    case "podcast_episode":
      return "headset-outline";
    case "article":
      return "document-text-outline";
    case "youtube_video":
    case "short_video":
      return "play-circle-outline";
    case "audio_file":
    case "audio":
      return "musical-notes-outline";
    case "shared_text":
      return "text-outline";
    case "document":
      return "document-attach-outline";
    default:
      return "link-outline";
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
  thumbnailContainer: {
    width: 72,
    height: 72,
    borderRadius: BorderRadius.lg,
    backgroundColor: Colors.surfaceContainerLow,
    alignItems: "center",
    justifyContent: "center",
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
    fontSize: 11,
    fontWeight: "700",
    color: Colors.textMain,
    letterSpacing: 0.5,
  },
  timeText: {
    fontSize: 11,
    color: Colors.textMuted,
  },
  cardTitle: {
    fontSize: Typography.body.fontSize,
    fontWeight: "700",
    color: Colors.textMain,
    lineHeight: 22,
  },
  cardDomain: {
    fontSize: Typography.small.fontSize,
    color: Colors.textMuted,
  },
});
