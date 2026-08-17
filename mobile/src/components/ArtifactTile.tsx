/**
 * One AI artifact type, as a full-width tile carrying its own state.
 *
 * Shared because the same five tiles are offered from two places: the "AI" tab
 * of a media item (`app/media/[id].tsx`) and the AI tab of a collection. The
 * component is deliberately free of any media/collection notion — it takes a
 * label, a glyph, the state of that artifact and two callbacks.
 *
 * The label sits in its own column so a secondary metadata line (generation
 * date, number of sources) can be added later without reshaping the tile.
 *
 * Generating is always offered when the source is ready, whatever already
 * exists: artifacts are an append-only history, so a second tap is a legitimate
 * regeneration that adds an entry rather than a request the API would refuse.
 * The tile shows the state of the newest entry of its type; the full history
 * lives in the list below it.
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
import type { ArtifactStatus, ArtifactType } from "../types/media";

/**
 * What the screen knows about one artifact type: the backend status, or `idle`
 * when nothing has been generated yet.
 */
export type ArtifactTileState = {
  status: ArtifactStatus | "idle";
  artifactId?: string;
  error?: string;
};

/**
 * The five artifact types offered to the user, each backed by a dedicated
 * backend worker. Order is the order they are displayed in.
 */
export const ARTIFACT_TILES: readonly {
  type: ArtifactType;
  label: string;
  icon: keyof typeof Ionicons.glyphMap;
}[] = [
  { type: "summary_short", label: "Summary", icon: "document-text-outline" },
  { type: "summary_detailed", label: "Detailed summary", icon: "reader-outline" },
  { type: "notes", label: "Learning notes", icon: "book-outline" },
  { type: "flashcards", label: "Flashcards", icon: "card-outline" },
  { type: "quiz", label: "Quiz", icon: "help-circle-outline" },
];

interface ArtifactTileProps {
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
  onView: (artifactId: string) => void;
}

export function ArtifactTile({
  label,
  icon,
  state,
  sourceReady,
  onGenerate,
  onView,
}: ArtifactTileProps): React.JSX.Element {
  const isInProgress =
    state.status === "queued" || state.status === "generating";
  const isReady = state.status === "ready";
  const isFailed = state.status === "failed";
  const canGenerate = !isInProgress && sourceReady;
  const generateLabel = state.status === "idle" ? "Generate" : "Regenerate";

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
              {state.status === "queued" ? "Queued" : "Generating..."}
            </Text>
          </View>
        )}

        {isReady && state.artifactId && (
          <Pressable
            style={styles.viewButton}
            onPress={() => state.artifactId && onView(state.artifactId)}
            testID={`artifact-tile-view-${label}`}
            accessibilityLabel={`View ${label}`}
            accessibilityRole="button"
          >
            <Text style={styles.viewButtonText}>View</Text>
          </Pressable>
        )}

        {isFailed && <Text style={styles.failedText}>Failed</Text>}

        {canGenerate && (
          <Pressable
            style={[styles.generateButton, isFailed && styles.retryButton]}
            onPress={onGenerate}
            testID={`artifact-tile-generate-${label}`}
            accessibilityLabel={`${generateLabel} ${label}`}
            accessibilityHint={state.error}
            accessibilityRole="button"
          >
            <Text
              style={[
                styles.generateButtonText,
                isFailed && styles.retryText,
              ]}
            >
              {isFailed ? "Retry" : generateLabel}
            </Text>
          </Pressable>
        )}

        {!sourceReady && !isInProgress && (
          <Text style={styles.waitingText}>Processing...</Text>
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
  viewButton: {
    paddingHorizontal: Spacing.md,
    paddingVertical: Spacing.sm,
    borderRadius: BorderRadius.md,
    backgroundColor: Colors.surfaceContainerHigh,
    minHeight: TouchTarget.minimum,
    justifyContent: "center",
  },
  viewButtonText: {
    fontSize: Typography.label.fontSize,
    fontWeight: "600",
    color: Colors.textMain,
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
  generateButtonText: {
    fontSize: Typography.label.fontSize,
    fontWeight: "600",
    color: Colors.textMain,
  },
});
