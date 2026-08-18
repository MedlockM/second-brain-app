/**
 * The complete "AI" tab of a scope: the five generation tiles on top, the
 * append-only history underneath.
 *
 * Rendered by both `app/media/[id].tsx` (a single media item) and
 * `app/media/collections/[id].tsx` (a whole collection). The tab used to be
 * declared twice, and the two copies drifted until the same headings rendered as
 * a large dark title on one screen and a small muted uppercase caption on the
 * other. So this component owns *all* of the layout and every presentational
 * state, and there is deliberately **no prop per visual difference** — a knob
 * would just let the two callers drift again inside here.
 *
 * The screens keep owning their data: fetching, polling, the tile states, the
 * generation handler and the refusal message are all passed in. `sourceReady` is
 * part of that data, not a style knob: a media item still being transcribed
 * cannot be generated from yet, whereas a collection's sources always can.
 *
 * The single scope-dependent piece of rendering is `showSourceCount`: an
 * artifact generated over one media item has no source count worth saying.
 */

import React from "react";
import {
  ActivityIndicator,
  Pressable,
  StyleSheet,
  Text,
  View,
} from "react-native";
import { Ionicons } from "@expo/vector-icons";
import {
  BorderRadius,
  Colors,
  Spacing,
  TouchTarget,
  Typography,
} from "../constants/theme";
import type { ArtifactSummary } from "../types/artifacts";
import type { ArtifactType } from "../types/media";
import {
  ARTIFACT_TILES,
  ArtifactTile,
  type ArtifactTileState,
} from "./ArtifactTile";
import { ArtifactHistoryRow } from "./ArtifactHistoryRow";

/**
 * The empty history, worded once for every scope. It says what to do next and
 * stays silent about what is being generated over, which is the only part that
 * differed between a media item and a collection.
 */
const EMPTY_HISTORY_COPY =
  "Nothing generated yet. Pick a format above to create one.";

export interface ArtifactsPanelProps {
  /** The newest state per artifact type, driving the five tiles. */
  tileStates: Record<ArtifactType, ArtifactTileState>;
  /** Whether the underlying source is far enough along to generate from. */
  sourceReady: boolean;
  onGenerate: (artifactType: ArtifactType) => void;
  /** Why the last generation attempt was refused, or `null`. */
  refusal: string | null;
  /** `testID` of the refusal banner — scope-specific, the Maestro flows use it. */
  refusalTestID: string;
  /** The scope's artifacts, newest first. */
  history: ArtifactSummary[];
  /** True while the first fetch of this scope's history is in flight. */
  historyLoading: boolean;
  /** Why the history could not be loaded, or `null`. */
  historyError: string | null;
  onRetryHistory: () => void;
  /** `testID` of the empty history — scope-specific, the Maestro flows use it. */
  historyEmptyTestID: string;
  onOpenArtifact: (artifact: ArtifactSummary) => void;
  /**
   * Whether a history line names the number of sources it was generated over:
   * `true` for a collection, `false` for a single media item.
   */
  showSourceCount: boolean;
}

export function ArtifactsPanel({
  tileStates,
  sourceReady,
  onGenerate,
  refusal,
  refusalTestID,
  history,
  historyLoading,
  historyError,
  onRetryHistory,
  historyEmptyTestID,
  onOpenArtifact,
  showSourceCount,
}: ArtifactsPanelProps): React.JSX.Element {
  return (
    <View style={styles.panel}>
      <Text style={styles.heading}>Generate</Text>
      <View style={styles.tileStack}>
        {ARTIFACT_TILES.map((tile) => (
          <ArtifactTile
            key={tile.type}
            label={tile.label}
            icon={tile.icon}
            state={tileStates[tile.type]}
            sourceReady={sourceReady}
            onGenerate={() => onGenerate(tile.type)}
          />
        ))}
      </View>

      {refusal ? (
        <View style={styles.refusalBanner} testID={refusalTestID}>
          <Ionicons
            name="information-circle-outline"
            size={18}
            color={Colors.error}
          />
          <Text style={styles.refusalText}>{refusal}</Text>
        </View>
      ) : null}

      {/* The history is append-only: several entries of the same type coexist,
          a regeneration adds one instead of replacing the previous, and nothing
          here is deduplicated or marked stale. */}
      <Text style={[styles.heading, styles.historyHeading]}>Generated</Text>
      {historyLoading ? (
        <View style={styles.inlineState}>
          <ActivityIndicator size="small" color={Colors.primary} />
          <Text style={styles.inlineStateText}>Loading...</Text>
        </View>
      ) : historyError ? (
        <View style={styles.inlineState}>
          <Text style={styles.inlineStateText}>{historyError}</Text>
          <Pressable
            style={styles.retryButton}
            onPress={onRetryHistory}
            accessibilityLabel="Retry loading generated content"
            accessibilityRole="button"
          >
            <Text style={styles.retryButtonText}>Retry</Text>
          </Pressable>
        </View>
      ) : history.length === 0 ? (
        <View style={styles.inlineState} testID={historyEmptyTestID}>
          <Text style={styles.inlineStateText}>{EMPTY_HISTORY_COPY}</Text>
        </View>
      ) : (
        <View style={styles.historyList}>
          {history.map((artifact) => (
            <ArtifactHistoryRow
              key={artifact.artifact_id}
              artifact={artifact}
              showSourceCount={showSourceCount}
              onPress={onOpenArtifact}
            />
          ))}
        </View>
      )}
    </View>
  );
}

const styles = StyleSheet.create({
  // The panel carries its own gutter — the same `Spacing.lg` the rest of both
  // screens sits on — so neither caller re-applies one and neither can shift it.
  panel: {
    paddingHorizontal: Spacing.lg,
    paddingTop: Spacing.sm,
    paddingBottom: Spacing.xxl,
  },
  heading: {
    fontSize: Typography.headline.fontSize,
    fontWeight: Typography.headline.fontWeight,
    color: Colors.textMain,
    marginBottom: Spacing.md,
  },
  // Air above the second heading only: the first one opens the tab and needs
  // none, hence a separate style rather than a change to the shared one.
  historyHeading: {
    marginTop: Spacing.lg,
  },
  // Stacks of self-contained cards: the gap does the sectioning, so there is no
  // rule and no container frame ("No-Line rule").
  tileStack: {
    gap: Spacing.sm,
  },
  historyList: {
    gap: Spacing.sm,
  },
  inlineState: {
    alignItems: "center",
    gap: Spacing.sm,
    paddingVertical: Spacing.lg,
  },
  inlineStateText: {
    fontSize: Typography.body.fontSize,
    color: Colors.textMuted,
    textAlign: "center",
    lineHeight: Typography.body.lineHeight,
  },
  retryButton: {
    justifyContent: "center",
    alignItems: "center",
    backgroundColor: Colors.primary,
    paddingHorizontal: Spacing.lg,
    paddingVertical: Spacing.sm + 4,
    borderRadius: BorderRadius.lg,
    minHeight: TouchTarget.minimum,
  },
  retryButtonText: {
    fontSize: Typography.label.fontSize,
    fontWeight: Typography.label.fontWeight,
    color: Colors.onPrimary,
  },
  refusalBanner: {
    flexDirection: "row",
    alignItems: "flex-start",
    gap: Spacing.sm,
    backgroundColor: Colors.errorContainer,
    borderRadius: BorderRadius.lg,
    padding: Spacing.md,
    marginTop: Spacing.md,
  },
  refusalText: {
    flex: 1,
    fontSize: Typography.small.fontSize,
    color: Colors.error,
    lineHeight: Typography.body.lineHeight,
  },
});
