/**
 * One AI artifact type, as a full-width tile carrying its own state.
 *
 * Shared because the same five tiles are offered from two places: the "AI" tab
 * of a media item (`app/media/[id].tsx`) and the AI tab of a collection. The
 * component is deliberately free of any media/collection notion — it takes a
 * label, a glyph, the state of that artifact and one callback.
 *
 * The label sits in its own column so a secondary metadata line (generation
 * date, number of sources) can be added later without reshaping the tile.
 *
 * Generating is always offered when the source is ready, whatever already
 * exists: artifacts are an append-only history, so a second tap adds an entry
 * rather than a request the API would refuse. The button therefore keeps saying
 * "Generate" once something exists, instead of switching to a second wording,
 * and the tile carries no "View" action either: opening a generated artifact is
 * the job of the history list below it, which routes to `/artifacts/<id>`.
 * Keeping the action column to a single button is what lets the label breathe;
 * two buttons side by side squeezed long labels like "Detailed summary" into a
 * mid-word wrap.
 */

import React from "react";
import { ActivityIndicator, Pressable, StyleSheet, Text, View } from "react-native";
import { Ionicons } from "@expo/vector-icons";
import {
  BorderRadius,
  Colors,
  Spacing,
  TouchTarget,
  Typography,
} from "../constants/theme";
import { t, type TranslationKey } from "../i18n";
import type { ArtifactStatus, ArtifactType } from "../types/media";

/**
 * What the screen knows about one artifact type: the backend status, or `idle`
 * when nothing has been generated yet.
 *
 * The status is not necessarily read off a fetched entry: a host reports a
 * generation request whose POST is still in flight as `queued` here, so the
 * spinner appears on the tap frame instead of after the round-trip. The tile
 * does not need to tell the two apart — both mean the same thing to the user,
 * and both must take the button away so a second tap cannot fire a second POST.
 */
export type ArtifactTileState = {
  status: ArtifactStatus | "idle";
  error?: string;
};

/**
 * The five artifact types offered to the user, each backed by a dedicated
 * backend worker. Order is the order they are displayed in.
 */
export const ARTIFACT_TILES: readonly {
  type: ArtifactType;
  /**
   * The catalogue key of the label, not the label: this array is built once at
   * import time, so a resolved string would freeze the language the app was
   * launched in and survive a change in the settings.
   */
  labelKey: TranslationKey;
  icon: keyof typeof Ionicons.glyphMap;
}[] = [
  {
    type: "summary_short",
    labelKey: "artifacts.type.summaryShort",
    icon: "document-text-outline",
  },
  {
    type: "summary_detailed",
    labelKey: "artifacts.type.summaryDetailed",
    icon: "reader-outline",
  },
  { type: "notes", labelKey: "artifacts.type.notes", icon: "book-outline" },
  {
    type: "flashcards",
    labelKey: "artifacts.type.flashcards",
    icon: "card-outline",
  },
  { type: "quiz", labelKey: "artifacts.type.quiz", icon: "help-circle-outline" },
];

interface ArtifactTileProps {
  /** Identifies the tile in `testID`s, which must not move with the language. */
  type: ArtifactType;
  label: string;
  icon: keyof typeof Ionicons.glyphMap;
  state: ArtifactTileState;
  /**
   * Whether the underlying source is far enough along to generate from. False
   * keeps the tile inert with a "Processing..." note instead of offering a
   * button that the API would refuse.
   */
  sourceReady: boolean;
  onGenerate: () => void;
}

export function ArtifactTile({
  type,
  label,
  icon,
  state,
  sourceReady,
  onGenerate,
}: ArtifactTileProps): React.JSX.Element {
  const isInProgress =
    state.status === "queued" || state.status === "generating";
  const isFailed = state.status === "failed";
  const canGenerate = !isInProgress && sourceReady;

  return (
    <View style={styles.tile}>
      <View style={styles.identity}>
        <Ionicons name={icon} size={20} color={Colors.primary} />
        <View style={styles.labelColumn}>
          <Text style={styles.label}>{label}</Text>
        </View>
      </View>

      <View style={styles.action}>
        {isInProgress && (
          <View style={styles.progressContainer}>
            <ActivityIndicator size="small" color={Colors.primary} />
            <Text style={styles.progressText}>
              {state.status === "queued"
                ? t("artifacts.status.queued")
                : t("artifacts.status.generating")}
            </Text>
          </View>
        )}

        {isFailed && (
          <Text style={styles.failedText}>{t("artifacts.status.failed")}</Text>
        )}

        {canGenerate && (
          <Pressable
            style={({ pressed }) => [
              styles.generateButton,
              isFailed && styles.retryButton,
              pressed && styles.generateButtonPressed,
            ]}
            onPress={onGenerate}
            testID={`artifact-tile-generate-${type}`}
            accessibilityLabel={t("artifacts.a11yGenerate", { label })}
            accessibilityHint={state.error}
            accessibilityRole="button"
          >
            <Text
              style={[
                styles.generateButtonText,
                isFailed && styles.retryText,
              ]}
            >
              {isFailed ? t("common.retry") : t("artifacts.generate")}
            </Text>
          </Pressable>
        )}

        {!sourceReady && !isInProgress && (
          <Text style={styles.waitingText}>{t("artifacts.processing")}</Text>
        )}
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  // A card on `surface` over the page background: the tiles are separated by a
  // tonal shift and a gap, never by a rule ("No-Line rule").
  tile: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    gap: Spacing.sm,
    paddingHorizontal: Spacing.md,
    paddingVertical: Spacing.md,
    minHeight: TouchTarget.comfortable,
    backgroundColor: Colors.surface,
    borderRadius: BorderRadius.xl,
  },
  identity: {
    flexDirection: "row",
    alignItems: "center",
    gap: Spacing.md,
    flexShrink: 1,
  },
  labelColumn: {
    flexShrink: 1,
    gap: Spacing.xs,
  },
  label: {
    fontSize: Typography.body.fontSize,
    fontWeight: "600",
    color: Colors.textMain,
  },
  action: {
    flexDirection: "row",
    alignItems: "center",
    gap: Spacing.sm,
  },

  // States
  progressContainer: {
    flexDirection: "row",
    alignItems: "center",
    gap: Spacing.sm,
  },
  progressText: {
    fontSize: Typography.small.fontSize,
    color: Colors.textMuted,
  },
  failedText: {
    fontSize: Typography.small.fontSize,
    color: Colors.error,
  },
  retryButton: {
    paddingHorizontal: Spacing.md,
    paddingVertical: Spacing.sm,
    borderRadius: BorderRadius.md,
    backgroundColor: Colors.errorContainer,
    minHeight: TouchTarget.minimum,
    justifyContent: "center",
  },
  retryText: {
    fontSize: Typography.small.fontSize,
    fontWeight: Typography.label.fontWeight,
    color: Colors.error,
  },
  waitingText: {
    fontSize: Typography.small.fontSize,
    color: Colors.textMuted,
    fontStyle: "italic",
  },
  generateButton: {
    paddingHorizontal: Spacing.md,
    paddingVertical: Spacing.sm,
    borderRadius: BorderRadius.md,
    backgroundColor: Colors.primary,
    minHeight: TouchTarget.minimum,
    justifyContent: "center",
    alignItems: "center",
  },
  // The same press feedback every other button in the app gives (inbox digest
  // card, artifact history row): the request behind this one can take seconds,
  // so the finger must get an answer on the frame it lands.
  generateButtonPressed: {
    transform: [{ scale: 0.98 }],
    opacity: 0.9,
  },
  generateButtonText: {
    fontSize: Typography.label.fontSize,
    fontWeight: "600",
    color: Colors.textMain,
  },
});
