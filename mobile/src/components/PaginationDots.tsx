/**
 * The row of dots under a paged carousel: one dot per page, the current one
 * tinted, at most seven on screen at a time with the outer ones shrinking.
 *
 * Core React Native only — two `View`s and a `StyleSheet`. A dots row is a few
 * rectangles whose sizes are recomputed on a page change; there is nothing here
 * an animation library or a pager component would do better.
 *
 * Colours are the ones `app/(tabs)/digest.tsx` already uses for its own dots, so
 * the two carousels of the app read as the same control.
 */

import { StyleSheet, View } from "react-native";
import { BorderRadius, Colors, Spacing } from "../constants/theme";

/**
 * Seven is the Instagram cap and the reason this component exists: past it the
 * row stops being glanceable and starts being a ruler.
 */
const MAX_VISIBLE = 7;

/**
 * Half of `MAX_VISIBLE - 1`: the offset that puts the active dot in the middle
 * of the window whenever the window is free to move.
 */
const CENTER_OFFSET = 3;

/** Base diameter, matching the digest carousel's dots. */
const DOT_SIZE = 8;

/**
 * The two steps of the decrescendo, applied to the dot on a truncated edge and
 * to its neighbour. Ratios rather than sizes so the base can change in one place.
 */
const EDGE_SCALE = 0.5;
const NEAR_EDGE_SCALE = 0.75;

interface PaginationDotsProps {
  /** Number of pages. Zero renders nothing at all. */
  count: number;
  /** Index of the page currently on screen. */
  activeIndex: number;
  testID?: string;
}

export function PaginationDots({
  count,
  activeIndex,
  testID,
}: PaginationDotsProps): React.JSX.Element | null {
  // Nothing to page through: no row, not an empty one. A container reserving
  // height for zero dots would leave a gap above the action bar.
  if (count <= 0) return null;

  const windowSize = Math.min(count, MAX_VISIBLE);

  /**
   * `activeIndex - CENTER_OFFSET` clamped between 0 and `count - MAX_VISIBLE`.
   *
   * That clamp *is* the behaviour being copied: the active dot sits in the middle
   * while it can, and the window pins itself to either end rather than sliding
   * past it. When `count <= MAX_VISIBLE` the upper bound is zero or negative, so
   * the `Math.max` collapses it to 0 and every dot is shown.
   */
  const start = Math.max(
    0,
    Math.min(activeIndex - CENTER_OFFSET, count - MAX_VISIBLE),
  );
  const end = start + windowSize;

  // Which sides are truncated. This — not the position inside the window — is
  // what the decrescendo is indexed on, so a shrunk dot means exactly "there are
  // more items this way" and a full-size edge dot means "this is the end".
  const hasBefore = start > 0;
  const hasAfter = end < count;

  const dots = [];
  for (let index = start; index < end; index += 1) {
    const position = index - start;
    let scale = 1;

    if (hasBefore) {
      if (position === 0) scale = Math.min(scale, EDGE_SCALE);
      else if (position === 1) scale = Math.min(scale, NEAR_EDGE_SCALE);
    }
    if (hasAfter) {
      if (position === windowSize - 1) scale = Math.min(scale, EDGE_SCALE);
      else if (position === windowSize - 2) {
        scale = Math.min(scale, NEAR_EDGE_SCALE);
      }
    }

    // The active dot always keeps the base size. With the clamp above it can
    // never land on a truncated edge, so this is an invariant rather than a
    // branch that fires — and it is stated because a later change to the window
    // maths must not be allowed to silently shrink the one dot being pointed at.
    if (index === activeIndex) scale = 1;

    const size = DOT_SIZE * scale;
    dots.push(
      <View
        key={index}
        style={[
          styles.dot,
          { width: size, height: size },
          index === activeIndex ? styles.dotActive : styles.dotInactive,
        ]}
      />,
    );
  }

  return (
    <View
      testID={testID}
      style={styles.row}
      // Decoration: the position it encodes is spelled out in the header of the
      // screen that hosts it, which is also the only place that can state it
      // exactly — the row itself caps at seven.
      accessible={false}
      accessibilityElementsHidden
      importantForAccessibility="no-hide-descendants"
      pointerEvents="none"
    >
      {dots}
    </View>
  );
}

const styles = StyleSheet.create({
  // Fixed height, so the row does not jump as the dots resize under it.
  row: {
    height: Spacing.md,
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "center",
    gap: Spacing.sm,
  },
  dot: {
    borderRadius: BorderRadius.full,
  },
  dotActive: {
    backgroundColor: Colors.textMain,
  },
  dotInactive: {
    backgroundColor: Colors.outlineVariant,
  },
});
