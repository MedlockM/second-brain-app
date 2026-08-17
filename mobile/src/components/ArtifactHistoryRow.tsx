/**
 * One line of a scope's AI artifact history.
 *
 * The history is append-only: several entries of the same type coexist, and an
 * entry keeps describing the sources it was generated over even after the
 * collection has changed. That is exactly what "N sources" says — it is the
 * entry's own snapshot, never a count of the collection as it stands now, so
 * nothing here dedupes, hides or marks an entry as stale.
 *
 * Shared between the AI tab of a collection and the AI tab of a media item: the
 * two histories are the same object rendered the same way.
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
import { getRelativeTime } from "../lib/relativeTime";
import type { ArtifactSummary } from "../services/artifactService";
import { ARTIFACT_TILES } from "./ArtifactTile";

interface ArtifactHistoryRowProps {
  artifact: ArtifactSummary;
  /** Whether to show the source count — a single-media scope has nothing to say. */
  showSourceCount?: boolean;
  onPress: (artifact: ArtifactSummary) => void;
}

export function ArtifactHistoryRow({
  artifact,
  showSourceCount = true,
  onPress,
}: ArtifactHistoryRowProps): React.JSX.Element {
  const tile = ARTIFACT_TILES.find((entry) => entry.type === artifact.artifact_type);
  const inFlight =
    artifact.status === "queued" || artifact.status === "generating";
  const failed = artifact.status === "failed";
  // A title only exists once the model has produced one, so an in-flight or
  // failed entry falls back to its type label rather than rendering blank.
  const title = artifact.title?.trim() || tile?.label || artifact.artifact_type;

  const metaParts: string[] = [];
  if (showSourceCount) {
    metaParts.push(
      `${artifact.source_count} ${artifact.source_count === 1 ? "source" : "sources"}`,
    );
  }
  if (inFlight) {
    metaParts.push(artifact.status === "queued" ? "Queued" : "Generating...");
  } else if (failed) {
    metaParts.push("Failed");
  } else {
    metaParts.push(getRelativeTime(artifact.created_at));
  }

  return (
    <Pressable
      style={({ pressed }) => [styles.row, pressed && styles.rowPressed]}
      onPress={() => onPress(artifact)}
      disabled={inFlight}
      testID={`artifact-history-row-${artifact.artifact_id}`}
      accessibilityLabel={`${tile?.label ?? artifact.artifact_type}: ${title}`}
      accessibilityRole="button"
      accessibilityState={{ disabled: inFlight }}
    >
      <View style={styles.iconContainer}>
        <Ionicons
          name={tile?.icon ?? "sparkles-outline"}
          size={20}
          color={failed ? Colors.error : Colors.primary}
        />
      </View>
      <View style={styles.textColumn}>
        <Text style={styles.title} numberOfLines={1}>
          {title}
        </Text>
        <Text style={styles.meta} numberOfLines={1}>
          {metaParts.join(" • ")}
        </Text>
      </View>
      {inFlight ? (
        <ActivityIndicator size="small" color={Colors.primary} />
      ) : (
        <Ionicons name="chevron-forward" size={18} color={Colors.textMuted} />
      )}
    </Pressable>
  );
}

const styles = StyleSheet.create({
  row: {
    flexDirection: "row",
    alignItems: "center",
    gap: Spacing.md,
    paddingHorizontal: Spacing.md,
    paddingVertical: Spacing.sm,
    minHeight: TouchTarget.comfortable,
    backgroundColor: Colors.surface,
    borderRadius: BorderRadius.xl,
  },
  rowPressed: {
    transform: [{ scale: 0.98 }],
    opacity: 0.9,
  },
  iconContainer: {
    width: 36,
    height: 36,
    borderRadius: BorderRadius.md,
    backgroundColor: Colors.surfaceContainerLow,
    alignItems: "center",
    justifyContent: "center",
  },
  textColumn: {
    flex: 1,
    gap: 2,
  },
  title: {
    fontSize: Typography.body.fontSize,
    fontWeight: "600",
    color: Colors.textMain,
  },
  meta: {
    fontSize: Typography.small.fontSize,
    color: Colors.textMuted,
  },
});
