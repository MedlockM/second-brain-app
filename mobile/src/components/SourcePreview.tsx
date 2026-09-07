/**
 * "Aperçu": what a source is about, above its full text on the Reader tab.
 *
 * The content is the triage card of the internal `review_blurb` artifact
 * (task-323), mirrored on the library row and served by
 * `GET /api/media/{id}`. Until task-363 the only surface that read it was the
 * unsorted-review screen, so the answer to "what is in here again?" disappeared
 * the moment an item was sorted — which is precisely when it is asked.
 *
 * Rendering only: the owning screen holds the state and the bounded poll that
 * resolves the waiting state, the same split `TranscriptReader` already uses.
 *
 * The section is always present, in all three states. A preview being generated
 * and a preview that will never exist look identical from the content alone
 * (both are a null blurb), so the status travels with it and the two get
 * different, honest lines instead of a section that silently vanishes.
 */

import React from "react";
import { ActivityIndicator, StyleSheet, Text, View } from "react-native";
import { Ionicons } from "@expo/vector-icons";

import { Bullets } from "./Bullets";
import { BorderRadius, Colors, Spacing, Typography } from "../constants/theme";
import { t } from "../i18n";
import type { MediaItemContract } from "../types/media";

/** What the section renders, once content and status have been reconciled. */
export type SourcePreviewState =
  | { status: "ready"; hook: string; points: string[] }
  | { status: "pending" }
  | { status: "failed" };

/**
 * Reconciles the two contract fields into the one thing the section draws.
 *
 * Content wins: a blurb with a hook is a preview, whatever the artifact entry
 * says about itself. Only its absence is read from the status, and only an
 * outright `failed` closes the question — every other value means "still
 * coming", which is what the screen's poll then resolves.
 */
export function resolveSourcePreviewState(
  item: Pick<MediaItemContract, "review_blurb" | "review_blurb_status">,
): SourcePreviewState {
  const hook = item.review_blurb?.hook?.trim() ?? "";
  const points = (item.review_blurb?.points ?? [])
    .map((point) => point.trim())
    .filter(Boolean);

  if (hook) {
    return { status: "ready", hook, points };
  }
  return item.review_blurb_status === "failed"
    ? { status: "failed" }
    : { status: "pending" };
}

export function SourcePreview({
  state,
}: {
  state: SourcePreviewState;
}): React.JSX.Element {
  return (
    <View style={styles.container}>
      <Text style={styles.sectionTitle}>{t("preview.heading")}</Text>
      <View style={styles.card}>
        {state.status === "ready" ? (
          <>
            <Text style={styles.hook}>{state.hook}</Text>
            {/* The same bullets the triage card draws. One bullet style in the
                app, and it lives in `Bullets`. */}
            {state.points.length > 0 ? <Bullets items={state.points} /> : null}
          </>
        ) : state.status === "pending" ? (
          <View style={styles.statusRow}>
            <ActivityIndicator
              size="small"
              color={Colors.primary}
              style={styles.statusGlyph}
            />
            <Text style={styles.statusText}>{t("preview.pending")}</Text>
          </View>
        ) : (
          /* No retry: the generation is internal and `POST /api/artifacts`
             refuses this type outright. A calm line, and the full text below is
             untouched — the preview was never what the reader came for. */
          <View style={styles.statusRow}>
            <Ionicons
              name="information-circle-outline"
              size={16}
              color={Colors.textMuted}
              style={styles.statusGlyph}
            />
            <Text style={styles.statusText}>{t("preview.failed")}</Text>
          </View>
        )}
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  /**
   * The gap to the full text is the section's own: the Reader tab stacks the two
   * blocks directly, and only this one knows how much air it needs under itself.
   */
  container: {
    marginBottom: Spacing.xl,
  },
  // Same heading treatment as the full-text section below, so the two read as
  // two sections of one page rather than a card bolted on top.
  sectionTitle: {
    fontSize: Typography.headline.fontSize,
    fontWeight: Typography.headline.fontWeight,
    color: Colors.textMain,
    marginBottom: Spacing.md,
  },
  // A tonal shift, no border: the block separates itself from the reading canvas
  // the way the triage card does ("No-Line" rule).
  card: {
    backgroundColor: Colors.surfaceContainerLow,
    borderRadius: BorderRadius.lg,
    padding: Spacing.md,
    gap: Spacing.sm,
  },
  // Body size, headline weight: the hook is a sentence to read, not a title, but
  // it has to lead the bullets under it. Both values are tokens.
  hook: {
    fontSize: Typography.body.fontSize,
    fontWeight: Typography.headline.fontWeight,
    color: Colors.textMain,
    lineHeight: Typography.body.lineHeight,
  },
  statusRow: {
    flexDirection: "row",
    alignItems: "center",
  },
  statusGlyph: {
    marginEnd: Spacing.sm,
  },
  statusText: {
    flex: 1,
    fontSize: Typography.body.fontSize,
    color: Colors.textSubtle,
    lineHeight: Typography.body.lineHeight,
  },
});
