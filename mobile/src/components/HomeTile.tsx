import React, { useState } from "react";
import { View, Text, StyleSheet, Pressable } from "react-native";
import { Image } from "expo-image";
import { Ionicons } from "@expo/vector-icons";
import { Colors, Typography, Spacing, BorderRadius } from "../constants/theme";
import type { MediaType } from "../types/media";
import { getMediaTypeIcon } from "../lib/mediaTypeDisplay";
import { t, tCount } from "../i18n";

/**
 * The tile of the Home screen's two horizontal rows (task-307).
 *
 * One component for "Continue learning" and "Recently added" alike: a large
 * cover, the title on up to three lines, the creator on one muted line. There is
 * no type badge and no timestamp — the rows are short and ordered, so neither
 * earns its space, and dropping them is what lets the title breathe.
 *
 * Its height is fixed (`TILE_HEIGHT`) rather than driven by its own text, so the
 * row it sits in is the same height whichever kinds of tile it holds — see the
 * constant's comment for what that was breaking on the Home screen.
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

/**
 * The text block under the cover is *reserved*, not measured — which is what
 * makes every tile the same height whatever it holds (task-332).
 *
 * A tile that sized itself to its content made the row size itself to whichever
 * tile happened to be tallest, and the gap the Home screen declares below a row
 * was then measured from that one tile. Two things make tiles disagree: a
 * collection tile always carries a subtitle (its item count) where a media tile
 * without a creator carries none, and a three-line title stands 40 dp taller than
 * a one-line one. So a row holding one media tile beside one collection tile left
 * a void under the media tile ~20 dp deeper than declared, and the next heading
 * read as pushed away. Reserving the worst case — three title lines plus one
 * subtitle line — makes the row's height independent of the kinds it holds, so
 * the gap between two Home blocks means what `inbox.tsx` says it means.
 *
 * Text stays top-aligned, so a short tile carries its slack at the bottom, where
 * it is the same on every tile of the row. The line heights are explicit for the
 * same reason the height is fixed: a height computed from tokens is only exact if
 * the text cannot pick its own leading. Android font padding may still spend a dp
 * or two past the box; nothing is clipped, and the tile's layout height is
 * constant either way, which is all the row's rhythm depends on.
 */
const TILE_TITLE_MAX_LINES = 3;
const TILE_TITLE_LINE_HEIGHT = 20;
const TILE_SUBTITLE_LINE_HEIGHT = 18;
export const TILE_HEIGHT =
  TILE_COVER_HEIGHT +
  Spacing.sm +
  TILE_TITLE_MAX_LINES * TILE_TITLE_LINE_HEIGHT +
  Spacing.xs +
  TILE_SUBTITLE_LINE_HEIGHT;

/** Up to four member covers, per the collection tile's mosaic. */
const MAX_MOSAIC_IMAGES = 4;

/**
 * What a tile can hold. Two shapes rather than one loose bag of optional fields:
 * a media item has a creator and one cover of its own where a collection has an
 * item count and borrows its members', and making that explicit is what keeps
 * the rendering branches honest.
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
      accessibilityLabel={describeTile(item)}
      accessibilityRole="button"
    >
      <TileCover item={item} />
      <Text style={styles.title} numberOfLines={TILE_TITLE_MAX_LINES}>
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
  // The backend stores a non-empty, human-readable title (task-266); the guard
  // covers the window before an item's metadata has resolved.
  return item.title?.trim() || t("common.untitled");
}

function tileSubtitle(item: HomeTileItem): string {
  if (item.kind === "collection") return formatItemCount(item.itemCount);
  return item.creator?.trim() ?? "";
}

function formatItemCount(count: number): string {
  return tCount("common.itemCount", count);
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
    return t("home.tile.a11yCollection", {
      name: item.name,
      count: formatItemCount(item.itemCount),
    });
  }
  const creator = item.creator?.trim();
  const title = item.title?.trim() || t("common.untitled");
  return creator ? t("home.tile.a11yByCreator", { title, creator }) : title;
}

// --- Styles ---

const styles = StyleSheet.create({
  tile: {
    width: TILE_WIDTH,
    // Fixed, not minimum: the row's height must not depend on which kinds of tile
    // it happens to hold. Well past the 48 px touch floor, which the tile would
    // clear on its cover alone.
    height: TILE_HEIGHT,
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
    lineHeight: TILE_TITLE_LINE_HEIGHT,
    color: Colors.textMain,
    marginTop: Spacing.sm,
  },
  subtitle: {
    ...Typography.small,
    lineHeight: TILE_SUBTITLE_LINE_HEIGHT,
    color: Colors.textSubtle,
    marginTop: Spacing.xs,
  },
});
