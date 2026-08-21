import React, { useState } from "react";
import { View, Text, StyleSheet, Pressable } from "react-native";
import { Image } from "expo-image";
import { Ionicons } from "@expo/vector-icons";
import {
  Colors,
  Typography,
  Spacing,
  BorderRadius,
  TouchTarget,
} from "../constants/theme";
import type { MediaType, SourcePlatform } from "../types/media";
import { getMediaTypeIcon } from "../lib/mediaTypeDisplay";

/**
 * The tile of the Home screen's two horizontal rows (task-307).
 *
 * One component for "Continue learning" and "Recently added" alike: a large
 * cover, the title on up to three lines, the creator on one muted line. There is
 * no type badge and no timestamp — the rows are short and ordered, so neither
 * earns its space, and dropping them is what lets the title breathe.
 *
 * The cover is 16:9 and cropped with `contentFit="cover"`, the ratio validated
 * by the task-302 benchmark (§6.4): it matches the two highest-volume sources
 * (YouTube, `og:image`) and keeps every tile the same height. It is rendered
 * with `expo-image` for the three props §6.1-6.2 selected it for — a `cacheKey`
 * that survives the rotating signature of a re-hosted cover, a `recyclingKey` so
 * a recycled cell never shows the previous tile's picture, and an explicit
 * `memory-disk` policy.
 *
 * With no cover — or when loading one fails — the media-type glyph is drawn on
 * `surfaceContainerLow`. There is no third state: the empty grey rectangle at
 * `digest.tsx` is the anti-pattern the benchmark names by name (§6.3).
 */

/**
 * Layout of the row, in one place because these three numbers are what decides
 * whether the next tile peeks at the right edge — which is the only thing
 * telling the user the row scrolls at all.
 *
 * 200 wide with a 16 px gutter puts the second tile's left edge at x=232. On the
 * narrowest phone this app targets (375 pt) that leaves ~143 pt of it visible,
 * and ~158 pt on a 390 pt screen: cut in both cases, never flush.
 */
export const TILE_WIDTH = 200;
/** 200 x 113 is 16:9 to within half a point. */
export const TILE_COVER_HEIGHT = 113;
export const TILE_GAP = Spacing.md;

/** Up to four member covers, per the collection tile's mosaic. */
const MAX_MOSAIC_IMAGES = 4;

/**
 * What a tile can hold. Three shapes rather than one loose bag of optional
 * fields: a collection has no creator and a pending share has no cover, and
 * making that explicit is what keeps the rendering branches honest.
 */
export type HomeTileItem =
  | {
      kind: "media";
      id: string;
      title: string | null;
      creator: string | null;
      /** Already a fetchable URL: the API signs re-hosted covers on read. */
      imageUrl: string | null;
      /**
       * Stable identity of the picture, independent from the signature in the
       * URL. Callers holding an `updated_at` should fold it in so a replaced
       * cover invalidates; callers that do not (the engagement row) pass the id
       * alone rather than something that churns on every engagement.
       */
      cacheKey: string;
      mediaType: MediaType;
    }
  | {
      kind: "collection";
      id: string;
      name: string;
      itemCount: number;
      /** Up to four covers of its newest items. Possibly empty. */
      previewImages: string[];
    }
  | {
      kind: "pending";
      id: string;
      /** The shared URL, shown as-is while the backend catches up. */
      url: string;
      sourcePlatform?: SourcePlatform;
      failed: boolean;
    };

interface HomeTileProps {
  item: HomeTileItem;
  onPress: (item: HomeTileItem) => void;
}

export function HomeTile({ item, onPress }: HomeTileProps): React.JSX.Element {
  return (
    <Pressable
      style={({ pressed }) => [styles.tile, pressed && styles.tilePressed]}
      onPress={() => onPress(item)}
      // A pending share is not navigable yet, but it stays focusable so the row
      // does not develop a hole for screen readers between two real tiles.
      disabled={item.kind === "pending"}
      accessibilityLabel={describeTile(item)}
      accessibilityRole="button"
    >
      <TileCover item={item} />
      <Text style={styles.title} numberOfLines={3}>
        {tileTitle(item)}
      </Text>
      {tileSubtitle(item) ? (
        <Text style={styles.subtitle} numberOfLines={1}>
          {tileSubtitle(item)}
        </Text>
      ) : null}
    </Pressable>
  );
}

// --- Cover ---

function TileCover({ item }: { item: HomeTileItem }): React.JSX.Element {
  // Keyed by tile id rather than a bare boolean: a horizontal `FlatList` cell is
  // recycled, and a failure recorded for the previous tile must not hide the
  // next one's cover.
  const [failedId, setFailedId] = useState<string | null>(null);

  if (item.kind === "collection") {
    return <CollectionMosaic item={item} />;
  }

  if (item.kind === "pending") {
    return (
      <View style={styles.cover}>
        <Ionicons
          name={
            item.failed ? "alert-circle" : getSourcePlatformIcon(item.sourcePlatform)
          }
          size={32}
          color={item.failed ? Colors.error : Colors.textMuted}
        />
      </View>
    );
  }

  const uri = item.imageUrl?.trim() ?? "";
  const showCover = uri.length > 0 && failedId !== item.id;

  return (
    <View style={styles.cover}>
      {showCover ? (
        <Image
          source={{ uri, cacheKey: item.cacheKey }}
          recyclingKey={item.id}
          cachePolicy="memory-disk"
          contentFit="cover"
          transition={150}
          priority="low"
          style={styles.coverImage}
          onError={() => setFailedId(item.id)}
          accessible={false}
        />
      ) : (
        <Ionicons
          name={getMediaTypeIcon(item.mediaType)}
          size={32}
          color={Colors.textMuted}
        />
      )}
    </View>
  );
}

/**
 * A collection has no cover of its own, so it borrows its members'.
 *
 * The layout is chosen by how many there are rather than by dropping them into a
 * fixed 2x2 grid: a grid with two pictures and two holes reintroduces the empty
 * rectangle §6.3 forbids. With none at all the tile falls back to the folder
 * glyph alone.
 */
function CollectionMosaic({
  item,
}: {
  item: Extract<HomeTileItem, { kind: "collection" }>;
}): React.JSX.Element {
  const images = item.previewImages.filter(Boolean).slice(0, MAX_MOSAIC_IMAGES);

  if (images.length === 0) {
    // Just the folder. The name and the count are already the tile's two text
    // lines directly below, so putting them here too printed each of them twice
    // (owner call, 2026-08-21). Same silhouette as a media tile with no cover:
    // a tonal surface carrying a single glyph, never an empty grey rectangle.
    return (
      <View style={styles.cover}>
        <Ionicons name="folder" size={44} color={Colors.primary} />
      </View>
    );
  }

  const cell = (uri: string, index: number, style: object) => (
    <Image
      key={`${item.id}:${index}`}
      // A member cover is signed and its signature rotates, so the query string
      // is stripped: what identifies the picture is the object it points at. A
      // per-slot key would go stale the moment the collection's newest items
      // change, which is exactly when the mosaic must redraw.
      source={{ uri, cacheKey: stableImageIdentity(uri) }}
      recyclingKey={`${item.id}:${index}`}
      cachePolicy="memory-disk"
      contentFit="cover"
      transition={150}
      priority="low"
      style={style}
      accessible={false}
    />
  );

  if (images.length === 1) {
    return <View style={styles.cover}>{cell(images[0], 0, styles.coverImage)}</View>;
  }

  if (images.length === 2) {
    return (
      <View style={[styles.cover, styles.mosaicRow]}>
        {cell(images[0], 0, styles.mosaicHalf)}
        {cell(images[1], 1, styles.mosaicHalf)}
      </View>
    );
  }

  if (images.length === 3) {
    return (
      <View style={[styles.cover, styles.mosaicRow]}>
        {cell(images[0], 0, styles.mosaicHalf)}
        <View style={styles.mosaicColumn}>
          {cell(images[1], 1, styles.mosaicQuarter)}
          {cell(images[2], 2, styles.mosaicQuarter)}
        </View>
      </View>
    );
  }

  return (
    <View style={[styles.cover, styles.mosaicRow]}>
      <View style={styles.mosaicColumn}>
        {cell(images[0], 0, styles.mosaicQuarter)}
        {cell(images[1], 1, styles.mosaicQuarter)}
      </View>
      <View style={styles.mosaicColumn}>
        {cell(images[2], 2, styles.mosaicQuarter)}
        {cell(images[3], 3, styles.mosaicQuarter)}
      </View>
    </View>
  );
}

// --- Text ---

function tileTitle(item: HomeTileItem): string {
  if (item.kind === "collection") return item.name;
  if (item.kind === "pending") return item.url;
  // The backend stores a non-empty, human-readable title (task-266); the guard
  // covers the window before an item's metadata has resolved.
  return item.title?.trim() || "Untitled";
}

function tileSubtitle(item: HomeTileItem): string {
  if (item.kind === "collection") return formatItemCount(item.itemCount);
  if (item.kind === "pending") {
    return item.failed ? "Could not be saved" : "Saving…";
  }
  return item.creator?.trim() ?? "";
}

function formatItemCount(count: number): string {
  return `${count} ${count === 1 ? "item" : "items"}`;
}

/**
 * A presigned cover carries its signature in the query string, so the full URL
 * changes on every read while the picture does not. The path is what identifies
 * the object; a third-party URL with no query is unaffected.
 */
function stableImageIdentity(uri: string): string {
  return uri.split("?")[0];
}

function describeTile(item: HomeTileItem): string {
  if (item.kind === "collection") {
    return `Collection ${item.name}, ${formatItemCount(item.itemCount)}`;
  }
  if (item.kind === "pending") {
    return item.failed
      ? `${item.url} could not be saved`
      : `${item.url}, being saved`;
  }
  const creator = item.creator?.trim();
  const title = item.title?.trim() || "Untitled";
  return creator ? `${title} by ${creator}` : title;
}

function getSourcePlatformIcon(
  platform?: SourcePlatform,
): keyof typeof Ionicons.glyphMap {
  switch (platform) {
    case "spotify":
    case "apple_podcasts":
    case "deezer":
    case "rss":
    case "podcast_index":
      return "headset-outline";
    case "youtube":
      return "play-circle-outline";
    case "instagram":
    case "tiktok":
      return "videocam-outline";
    case "x":
      return "chatbubble-outline";
    default:
      return "link-outline";
  }
}

// --- Styles ---

const styles = StyleSheet.create({
  tile: {
    width: TILE_WIDTH,
    // Well past the 48 px floor on its own; stated so a future tightening of the
    // tile cannot silently take it under.
    minHeight: TouchTarget.minimum,
  },
  tilePressed: {
    opacity: 0.7,
  },
  cover: {
    width: TILE_WIDTH,
    height: TILE_COVER_HEIGHT,
    borderRadius: BorderRadius.lg,
    backgroundColor: Colors.surfaceContainerLow,
    overflow: "hidden",
    alignItems: "center",
    justifyContent: "center",
  },
  coverImage: {
    width: "100%",
    height: "100%",
  },
  mosaicRow: {
    flexDirection: "row",
    gap: 2,
  },
  mosaicColumn: {
    flex: 1,
    gap: 2,
  },
  mosaicHalf: {
    flex: 1,
    height: "100%",
  },
  mosaicQuarter: {
    flex: 1,
    width: "100%",
  },
  title: {
    ...Typography.label,
    fontSize: 15,
    lineHeight: 20,
    color: Colors.textMain,
    marginTop: Spacing.sm,
  },
  subtitle: {
    ...Typography.small,
    color: Colors.textSubtle,
    marginTop: Spacing.xs,
  },
});
