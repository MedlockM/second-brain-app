import React, { useMemo, useRef, useState } from "react";
import {
  View,
  Text,
  StyleSheet,
  Pressable,
  type StyleProp,
  type ViewStyle,
} from "react-native";
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
import type { MediaType } from "../types/media";
import type { AnchorRect } from "./AnchoredContextMenu";
import { getMediaTypeIcon } from "../lib/mediaTypeDisplay";
import {
  MediaFailureBadge,
  describeWithFailure,
  isFailedLibraryStatus,
} from "./MediaFailureBadge";
import { t } from "../i18n";
import { getRelativeTime } from "../lib/relativeTime";
import {
  focusHighlightSegments,
  parseHighlightSnippet,
} from "../lib/highlightSnippet";

/**
 * Uniform media row for a vertical library list: the cover, the media type and
 * the age, the title, then the creator. Tapping it opens the media detail.
 *
 * The one media vignette of the Library tab, and deliberately the only one: the
 * list of everything saved and the list of search hits show the same items, and
 * two components drawing them were two apps (task-375). A search hit passes one
 * extra prop — the transcript excerpt that matched — and is otherwise this row.
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
 *
 * The only processing state the row shows is the terminal one: a failed import
 * gets a marker beside its type badge (task-381). The stages on the way in are
 * deliberately absent — they resolve on their own within a minute or two, where a
 * failure is final and is the one thing worth knowing without opening the item.
 */

/**
 * 112 x 63 is exactly 16:9, wide enough to read a thumbnail on a phone.
 *
 * Exported because the unsorted review draws the same cover on a card of its
 * own: sharing the numbers is what stops the two surfaces drifting into two
 * slightly different thumbnails for the same picture.
 */
export const COVER_WIDTH = 112;
export const COVER_HEIGHT = 63;

/**
 * How many lines of transcript excerpt a search hit gets.
 *
 * Three, which is what the search results have always shown. At 13px on an 18px
 * line that is 54px of text under a 63px cover head, so a hit stays about one
 * and a half library rows tall and six or seven still fit on a phone screen —
 * search is a scanning surface, and the number of results in view is what makes
 * it one. Two lines cut most sentences in half; four make every hit nearly two
 * rows and halve what can be scanned.
 */
const EXCERPT_LINES = 3;

/**
 * The character budgets `focusHighlightSegments` cuts the excerpt to.
 *
 * `45` is a little under one line of this box — roughly 50 characters at 13px
 * across a card interior of ~334px on a 390pt phone, and ~40 on the narrowest
 * one still supported. So the match always begins on the first or second of the
 * three lines, whatever the device, while keeping most of a line of context in
 * front of it.
 *
 * `220` sits comfortably past what three lines can hold (~150-170 characters),
 * so the ellipsis the reader sees at the end is normally the native
 * `numberOfLines` one; the cap exists for the case where the backend hands over
 * a whole highlighted transcript chunk instead of a snippet.
 */
const EXCERPT_LEAD_CHARS = 45;
const EXCERPT_MAX_CHARS = 220;

/**
 * Everything this card draws, and nothing else.
 *
 * Narrower than `MediaListItem` on purpose. The search results render this same
 * card from a `SearchHit`, and a hit is not a library list row: it carries no
 * triage blurb and no processing status, and inventing values for fields it does
 * not have would be the first step back towards two vignettes. Both shapes
 * satisfy this, which is the whole point — the one field only a library row has
 * (`status`) is optional here, so a hit simply omits it and gets no marker.
 */
export interface MediaCardItem {
  media_item_id: string;
  title?: string | null;
  /** The subtitle. Falls back to the domain of `source_url` when absent. */
  creator_name?: string | null;
  media_type?: MediaType | string | null;
  source_url?: string | null;
  media_image?: string | null;
  /** ISO 8601. Drawn as a relative age next to the type badge. */
  created_at: string;
  /** ISO 8601. Part of the cover's cache key, so a replaced cover reloads. */
  updated_at: string;
  /**
   * Lifecycle of the *library entry* (`pending | processing | ready | failed`),
   * of which this row reads one value: `failed` earns a marker next to the type
   * badge (task-381). The three others draw the row they always drew — an item on
   * its way in is not news, and one that arrived is the norm.
   *
   * Optional because a search hit has no status by contract: `hitToRow` does not
   * set the field, so a hit never carries a marker. A library row always does,
   * since `MediaListItem.status` is required there.
   */
  status?: string | null;
}

interface MediaListCardProps<T extends MediaCardItem> {
  item: T;
  onPress: (mediaItemId: string) => void;
  /**
   * Long press on the row, when there is something to offer for it. It receives
   * the row whole — so the caller can redraw exactly what was pressed — and the
   * row's own window rect, measured as the press is recognised: the context menu
   * is anchored to it and redraws the row there.
   *
   * Optional, and deliberately not wired inside the component. Both lists of the
   * Library tab pass a handler; the one row that gets none is a search hit whose
   * library row is gone — the index keeps a deleted media findable, and there is
   * nothing left on it to rename, move or delete. A row without a handler keeps
   * a bare tap and says nothing about a gesture it does not answer.
   */
  onLongPress?: (item: T, anchor: AnchorRect) => void;
  /**
   * The transcript excerpt that matched a search, exactly as the API sends it:
   * Algolia's `<mark>`-tagged, HTML-escaped snippet. Drawn full width under the
   * head of the card, bounded to `EXCERPT_LINES`.
   *
   * The one thing a search hit has that a library row does not, and the reason
   * this prop is optional: every other surface passes nothing and gets the row
   * it has always had, to the pixel.
   */
  excerpt?: string | null;
  /**
   * Overrides the card's outer box. Used by the context menu to redraw this row
   * as a lifted copy on the measured rect, where the list margins would offset
   * it — nothing else has a reason to touch it.
   */
  style?: StyleProp<ViewStyle>;
  /** Set by the list rendering the row so a flow can address it. */
  testID?: string;
}

export function MediaListCard<T extends MediaCardItem>({
  item,
  onPress,
  onLongPress,
  excerpt,
  style,
  testID,
}: MediaListCardProps<T>): React.JSX.Element {
  const rowRef = useRef<View>(null);
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

  // The import failed — not to be confused with `failedCoverId` right above,
  // which is one picture that would not load on an otherwise healthy item.
  const importFailed = isFailedLibraryStatus(item.status);

  // Windowed, not merely truncated: `numberOfLines` cuts at the *end* of the
  // box, so a match further in than the lead budget would be off screen and the
  // excerpt would say nothing about why this media is in the results.
  const excerptSegments = useMemo(
    () =>
      excerpt
        ? focusHighlightSegments(parseHighlightSnippet(excerpt), {
            leadChars: EXCERPT_LEAD_CHARS,
            maxChars: EXCERPT_MAX_CHARS,
          })
        : [],
    [excerpt],
  );

  // Measured on the gesture rather than on layout: a `FlatList` cell moves with
  // every scroll, so the only rect the menu can trust is the one taken when the
  // press was recognised.
  const handleLongPress = () => {
    if (!onLongPress) return;
    rowRef.current?.measureInWindow((x, y, width, height) => {
      onLongPress(item, { x, y, width, height });
    });
  };

  return (
    <Pressable
      ref={rowRef}
      testID={testID}
      style={({ pressed }) => [
        styles.card,
        pressed && styles.cardPressed,
        style,
      ]}
      onPress={() => onPress(item.media_item_id)}
      onLongPress={onLongPress ? handleLongPress : undefined}
      // The gesture is invisible, so a screen reader is told about it — and only
      // where it exists. `Pressable` keeps the tap and the long press exclusive,
      // so opening the menu never also opens the media.
      accessibilityHint={onLongPress ? t("mediaCard.longPressHint") : undefined}
      accessibilityLabel={describeWithFailure(
        creator
          ? t("mediaCard.a11yByCreator", {
              title: displayTitle ?? "",
              creator,
              type: mediaTypeLabel,
            })
          : t("mediaCard.a11yFromDomain", {
              title: displayTitle ?? "",
              type: mediaTypeLabel,
              domain: displayDomain,
            }),
        importFailed,
      )}
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
            {importFailed ? <MediaFailureBadge /> : null}
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

      {/* The matched transcript, full width under the head rather than beside
          the cover: it is prose, and the ~334px the card leaves next to a 112px
          thumbnail would break three lines into six. */}
      {excerptSegments.length > 0 ? (
        <Text style={styles.excerpt} numberOfLines={EXCERPT_LINES}>
          {excerptSegments.map((segment, index) => (
            <Text
              key={index}
              style={segment.highlighted ? styles.excerptMatch : undefined}
            >
              {segment.text}
            </Text>
          ))}
        </Text>
      ) : null}
    </Pressable>
  );
}

// --- Helpers (kept in sync with the inbox vignette presentation) ---


function getMediaTypeLabel(type: MediaType): string {
  switch (type) {
    case "podcast_episode":
      return t("mediaType.podcast");
    case "article":
      return t("mediaType.article");
    case "youtube_video":
      return t("mediaType.video");
    case "short_video":
      return t("mediaType.short");
    case "audio_file":
    case "audio":
      return t("mediaType.audio");
    case "shared_text":
      return t("mediaType.text");
    case "document":
      return t("mediaType.document");
    default:
      return t("mediaType.link");
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
  // `textSubtle`, not `textMuted`: this is the one thing on the card the reader
  // has to actually *read* rather than glance at, and the token's own note is
  // that `textMuted` fails AA below 18.66px.
  excerpt: {
    fontSize: Typography.small.fontSize,
    color: Colors.textSubtle,
    lineHeight: 18,
    marginTop: Spacing.sm,
  },
  excerptMatch: {
    backgroundColor: Colors.highlight,
    color: Colors.onHighlight,
    fontWeight: "600",
  },
});
