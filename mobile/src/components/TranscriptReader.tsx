/**
 * The readable body of a media item: the "Reader" tab of `app/media/[id].tsx`.
 *
 * Rendering only — fetching, translation polling and retrying live in the screen
 * that owns the state, and are handed over through `content`. That split is what
 * lets the screen keep loading (and keep a translation poll alive) while the
 * user is looking at another tab.
 */

import React, { useMemo } from "react";
import { ActivityIndicator, Pressable, StyleSheet, Text, View } from "react-native";
import { Ionicons } from "@expo/vector-icons";
import {
  BorderRadius,
  Colors,
  Spacing,
  TouchTarget,
  Typography,
} from "../constants/theme";
import { formatDuration } from "../lib/formatDuration";
import type {
  MediaStatusResponse,
  ProcessingJobLifecycleStatus,
} from "../types/media";

/** Lifecycle of the transcript body, as fetched by the owning screen. */
export type TranscriptContentState =
  | { status: "idle" }
  | { status: "loading" }
  | { status: "ready"; content: string }
  | { status: "translation_pending"; content: string }
  | { status: "translation_failed"; content: string }
  | { status: "not_available" }
  | { status: "error"; message: string };

/** Blank-line separator between transcript paragraphs, tolerating trailing spaces. */
const PARAGRAPH_SEPARATOR = /\n[ \t]*\n+/;
/** Optional in-band speaker label emitted when Deepgram diarization is enabled. */
const SPEAKER_PREFIX = /^(Speaker\s+\d+)\s*:\s*/i;

type TranscriptParagraph = {
  /** Speaker label without its trailing colon, when the paragraph carries one. */
  speaker: string | null;
  text: string;
};

/**
 * Splits the API's plain-text transcript into renderable paragraphs.
 *
 * The backend guarantees paragraphs are separated by a blank line and that no
 * paragraph exceeds ~900 characters (task-232, benchmark task-231 option B), so
 * there is deliberately no re-chunking heuristic on the client: legacy
 * single-block transcripts are already re-structured server-side at read time.
 */
function splitTranscriptParagraphs(content: string): TranscriptParagraph[] {
  return content
    .split(PARAGRAPH_SEPARATOR)
    .map((block) => block.trim())
    .filter((block) => block.length > 0)
    .map((block) => {
      const match = block.match(SPEAKER_PREFIX);
      if (!match) {
        return { speaker: null, text: block };
      }
      return {
        speaker: match[1],
        text: block.slice(match[0].length),
      };
    });
}

interface TranscriptReaderProps {
  transcript: MediaStatusResponse["media_item"]["transcript"];
  processingStatus: ProcessingJobLifecycleStatus;
  content: TranscriptContentState;
  onRetry: () => void;
}

export function TranscriptReader({
  transcript,
  processingStatus,
  content,
  onRetry,
}: TranscriptReaderProps): React.JSX.Element {
  if (!transcript) {
    return (
      <View style={styles.empty}>
        <Ionicons
          name="document-text-outline"
          size={32}
          color={Colors.textMuted}
        />
        <Text style={styles.emptyText}>No transcript available yet.</Text>
        {processingStatus !== "completed" &&
          processingStatus !== "failed" &&
          processingStatus !== "cancelled" && (
            <Text style={styles.emptyHint}>
              Transcript will appear once processing completes.
            </Text>
          )}
      </View>
    );
  }

  const statusMessages: Record<string, string> = {
    pending: "Transcript processing will start soon.",
    extracting: "Extracting audio content...",
    transcribing: "Transcribing audio to text...",
    ready: "Transcript is ready.",
    failed: "Transcript processing failed.",
  };

  const isReady = transcript.status === "ready";
  const isFailed = transcript.status === "failed";
  const isProcessing = !isReady && !isFailed;

  return (
    <View style={styles.container}>
      <Text style={styles.sectionTitle}>Transcript</Text>

      {/* Transcript metadata */}
      <View style={styles.meta}>
        {transcript.language && (
          <View style={styles.metaItem}>
            <Ionicons
              name="language-outline"
              size={14}
              color={Colors.textMuted}
            />
            <Text style={styles.metaText}>
              {transcript.language.toUpperCase()}
            </Text>
          </View>
        )}
        {transcript.duration_seconds && (
          <View style={styles.metaItem}>
            <Ionicons name="time-outline" size={14} color={Colors.textMuted} />
            <Text style={styles.metaText}>
              {formatDuration(transcript.duration_seconds)}
            </Text>
          </View>
        )}
        {transcript.segments_count && (
          <View style={styles.metaItem}>
            <Ionicons name="list-outline" size={14} color={Colors.textMuted} />
            <Text style={styles.metaText}>
              {transcript.segments_count === 1
                ? "1 paragraph"
                : `${transcript.segments_count} paragraphs`}
            </Text>
          </View>
        )}
      </View>

      {/* When the transcript is ready, surface the actual content inline.
          Until it's ready (or if fetching the body fails), keep the status row
          so the user knows where things stand. */}
      {isReady ? (
        <TranscriptContent state={content} onRetry={onRetry} />
      ) : (
        <View style={styles.statusRow}>
          {isProcessing && (
            <ActivityIndicator
              size="small"
              color={Colors.primary}
              style={styles.statusGlyph}
            />
          )}
          {isFailed && (
            <Ionicons
              name="close-circle"
              size={16}
              color={Colors.error}
              style={styles.statusGlyph}
            />
          )}
          <Text
            style={[styles.statusText, isFailed && styles.statusTextFailed]}
          >
            {statusMessages[transcript.status] || "Processing..."}
          </Text>
        </View>
      )}
    </View>
  );
}

/**
 * Renders the transcript body as discrete paragraphs.
 *
 * The backend stores and serves transcripts as plain text whose paragraphs are
 * separated by a blank line (task-232, benchmark task-231 option B), so the
 * client only has to split on blank lines — no heuristic here.
 *
 * A leading "Speaker N:" prefix is optional per paragraph (it only appears when
 * Deepgram diarization is enabled) and is rendered as a nested Text so the label
 * reflows with the body copy instead of becoming its own block.
 */
function TranscriptBody({ content }: { content: string }) {
  const paragraphs = useMemo(() => splitTranscriptParagraphs(content), [content]);

  if (paragraphs.length === 0) {
    return null;
  }

  return (
    <View style={styles.body}>
      {paragraphs.map((paragraph, index) => (
        <Text
          key={index}
          selectable
          style={[
            styles.paragraph,
            index === paragraphs.length - 1 && styles.paragraphLast,
          ]}
        >
          {paragraph.speaker ? (
            <Text style={styles.speaker}>{paragraph.speaker}: </Text>
          ) : null}
          {paragraph.text}
        </Text>
      ))}
    </View>
  );
}

function TranscriptContent({
  state,
  onRetry,
}: {
  state: TranscriptContentState;
  onRetry: () => void;
}) {
  if (state.status === "ready") {
    return (
      <View>
        <TranscriptBody content={state.content} />
      </View>
    );
  }

  if (state.status === "translation_pending") {
    return (
      <View>
        <View style={styles.translationPendingBanner}>
          <ActivityIndicator
            size="small"
            color={Colors.primary}
            style={styles.statusGlyph}
          />
          <Text style={styles.translationPendingText}>
            Translating transcript...
          </Text>
        </View>
        <TranscriptBody content={state.content} />
      </View>
    );
  }

  if (state.status === "translation_failed") {
    return (
      <View>
        <View style={styles.translationFailedBanner}>
          <Ionicons
            name="alert-circle"
            size={16}
            color={Colors.error}
            style={styles.statusGlyph}
          />
          <Text style={styles.translationFailedText}>
            Translation failed. Showing original transcript.
          </Text>
        </View>
        <TranscriptBody content={state.content} />
      </View>
    );
  }

  if (state.status === "loading" || state.status === "idle") {
    return (
      <View style={styles.statusRow}>
        <ActivityIndicator
          size="small"
          color={Colors.primary}
          style={styles.statusGlyph}
        />
        <Text style={styles.statusText}>Loading transcript…</Text>
      </View>
    );
  }

  if (state.status === "not_available") {
    return (
      <View style={styles.statusRow}>
        <Ionicons
          name="information-circle-outline"
          size={16}
          color={Colors.textMuted}
          style={styles.statusGlyph}
        />
        <Text style={styles.statusText}>
          Transcript content is not available for this item.
        </Text>
      </View>
    );
  }

  return (
    <View>
      <View style={styles.statusRow}>
        <Ionicons
          name="alert-circle"
          size={16}
          color={Colors.error}
          style={styles.statusGlyph}
        />
        <Text style={[styles.statusText, styles.statusTextFailed]}>
          {state.message}
        </Text>
      </View>
      <Pressable
        style={styles.retryButton}
        onPress={onRetry}
        accessibilityLabel="Retry loading transcript"
        accessibilityRole="button"
      >
        <Ionicons name="refresh" size={18} color={Colors.onPrimary} />
        <Text style={styles.retryButtonText}>Retry</Text>
      </Pressable>
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    gap: Spacing.sm,
  },
  sectionTitle: {
    fontSize: Typography.headline.fontSize,
    fontWeight: Typography.headline.fontWeight,
    color: Colors.textMain,
    marginBottom: Spacing.md,
  },
  meta: {
    flexDirection: "row",
    flexWrap: "wrap",
    gap: Spacing.md,
    marginBottom: Spacing.sm,
  },
  metaItem: {
    flexDirection: "row",
    alignItems: "center",
    gap: Spacing.xs,
  },
  metaText: {
    fontSize: Typography.small.fontSize,
    color: Colors.textMuted,
  },
  statusRow: {
    flexDirection: "row",
    alignItems: "center",
    paddingVertical: Spacing.sm,
  },
  statusGlyph: {
    marginRight: Spacing.sm,
  },
  statusText: {
    fontSize: Typography.body.fontSize,
    color: Colors.textMain,
    lineHeight: Typography.body.lineHeight,
  },
  statusTextFailed: {
    color: Colors.error,
  },
  translationPendingBanner: {
    flexDirection: "row",
    alignItems: "center",
    paddingVertical: Spacing.sm,
    paddingHorizontal: Spacing.md,
    backgroundColor: Colors.surfaceContainerLow,
    borderRadius: BorderRadius.md,
    marginBottom: Spacing.sm,
  },
  translationPendingText: {
    fontSize: Typography.small.fontSize,
    color: Colors.textMuted,
    fontStyle: "italic",
  },
  translationFailedBanner: {
    flexDirection: "row",
    alignItems: "center",
    paddingVertical: Spacing.sm,
    paddingHorizontal: Spacing.md,
    backgroundColor: Colors.errorContainer,
    borderRadius: BorderRadius.md,
    marginBottom: Spacing.sm,
  },
  translationFailedText: {
    fontSize: Typography.small.fontSize,
    color: Colors.error,
    flex: 1,
  },
  body: {
    paddingVertical: Spacing.sm,
  },
  paragraph: {
    fontSize: Typography.body.fontSize,
    lineHeight: Typography.body.lineHeight,
    color: Colors.textMain,
    marginBottom: Spacing.md,
  },
  paragraphLast: {
    marginBottom: 0,
  },
  speaker: {
    color: Colors.textMuted,
    fontWeight: "600",
  },
  empty: {
    alignItems: "center",
    gap: Spacing.sm,
    paddingVertical: Spacing.xl,
  },
  emptyText: {
    fontSize: Typography.body.fontSize,
    color: Colors.textMuted,
  },
  emptyHint: {
    fontSize: Typography.small.fontSize,
    color: Colors.textMuted,
    fontStyle: "italic",
    textAlign: "center",
  },
  retryButton: {
    flexDirection: "row",
    alignItems: "center",
    gap: Spacing.sm,
    backgroundColor: Colors.primary,
    paddingHorizontal: Spacing.lg,
    paddingVertical: Spacing.sm,
    borderRadius: BorderRadius.lg,
    minHeight: TouchTarget.minimum,
    marginTop: Spacing.md,
    alignSelf: "flex-start",
  },
  retryButtonText: {
    fontSize: Typography.label.fontSize,
    fontWeight: Typography.label.fontWeight,
    color: Colors.onPrimary,
  },
});
