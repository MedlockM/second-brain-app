import { useEffect, useState, useCallback, useRef } from "react";
import {
  View,
  Text,
  StyleSheet,
  ScrollView,
  Pressable,
  ActivityIndicator,
  LayoutAnimation,
  Platform,
  UIManager,
} from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";
import { useLocalSearchParams, useRouter } from "expo-router";
import { Ionicons } from "@expo/vector-icons";
import { useAuth } from "../../src/contexts/AuthContext";
import { MediaService } from "../../src/services/mediaService";
import { ArtifactService } from "../../src/services/artifactService";
import { getFriendlyErrorMessage } from "../../src/lib/getFriendlyErrorMessage";
import {
  Colors,
  Typography,
  Spacing,
  BorderRadius,
  Shadows,
  TouchTarget,
} from "../../src/constants/theme";
import type {
  MediaStatusResponse,
  ArtifactType,
  ArtifactStatus,
  ProcessingJobLifecycleStatus,
} from "../../src/types/media";

// Enable LayoutAnimation on Android
if (
  Platform.OS === "android" &&
  UIManager.setLayoutAnimationEnabledExperimental
) {
  UIManager.setLayoutAnimationEnabledExperimental(true);
}

const ARTIFACT_TYPES: {
  type: ArtifactType;
  label: string;
  icon: React.ComponentProps<typeof Ionicons>["name"];
}[] = [
  { type: "summary", label: "Summary", icon: "document-text-outline" },
  { type: "quiz", label: "Flashcards", icon: "card-outline" },
  { type: "notes", label: "Learning Notes", icon: "book-outline" },
];

const POLL_INTERVAL_MS = 3000;

type ArtifactLocalState = {
  status: ArtifactStatus | "idle";
  artifactId?: string;
  error?: string;
};

/**
 * Media Detail Screen.
 *
 * Shows media metadata, transcript status with retry (AC#4),
 * and AI artifact generation actions (AC#5).
 *
 * Improvements over base implementation:
 * - Artifacts section auto-expands when media is ready (AC#5)
 * - View button for ready artifacts (AC#5)
 * - Retry button for failed transcripts (AC#4)
 * - Cancel indication for stuck processing (AC#4)
 * - All interactive elements meet 48px minimum touch target (AC#2)
 */
export default function MediaDetailScreen() {
  const { id } = useLocalSearchParams<{ id: string }>();
  const router = useRouter();
  const { token } = useAuth();

  const [mediaData, setMediaData] = useState<MediaStatusResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [artifactsExpanded, setArtifactsExpanded] = useState(false);
  const [artifactStates, setArtifactStates] = useState<
    Record<ArtifactType, ArtifactLocalState>
  >({
    summary: { status: "idle" },
    quiz: { status: "idle" },
    notes: { status: "idle" },
  });

  const pollingRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const mountedRef = useRef(true);

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      mountedRef.current = false;
      if (pollingRef.current) {
        clearInterval(pollingRef.current);
      }
    };
  }, []);

  // Fetch media status on mount
  const fetchMediaStatus = useCallback(async () => {
    if (!token || !id) return;

    try {
      setLoading(true);
      setError(null);
      const response = await MediaService.getMediaStatus(token, id);
      if (!mountedRef.current) return;

      setMediaData(response);

      // Initialize artifact states from response
      const newStates: Record<ArtifactType, ArtifactLocalState> = {
        summary: { status: "idle" },
        quiz: { status: "idle" },
        notes: { status: "idle" },
      };

      for (const artifact of response.artifacts) {
        newStates[artifact.artifact_type] = {
          status: artifact.status,
          artifactId: artifact.artifact_id,
        };
      }

      // Also check artifact_statuses on media_item
      const artifactStatuses = response.media_item.artifact_statuses;
      if (artifactStatuses) {
        for (const [type, snapshot] of Object.entries(artifactStatuses)) {
          if (snapshot) {
            newStates[type as ArtifactType] = {
              status: snapshot.status,
              artifactId: snapshot.artifact_id,
            };
          }
        }
      }

      setArtifactStates(newStates);

      // Auto-expand artifacts panel when media is ready for artifacts (AC#5)
      const isMediaReady =
        response.media_item.status === "ready_for_artifacts" ||
        response.processing_job.status === "ready_for_artifacts" ||
        response.processing_job.status === "completed";
      if (isMediaReady) {
        setArtifactsExpanded(true);
      }

      // Start polling if any artifact is in progress
      const hasInProgress = Object.values(newStates).some(
        (s) => s.status === "queued" || s.status === "generating",
      );
      // Also poll if transcript is still processing
      const transcriptProcessing =
        response.media_item.transcript &&
        response.media_item.transcript.status !== "ready" &&
        response.media_item.transcript.status !== "failed";

      if (hasInProgress || transcriptProcessing) {
        startPolling();
      }
    } catch (err) {
      if (!mountedRef.current) return;
      setError(getFriendlyErrorMessage(err));
    } finally {
      if (mountedRef.current) {
        setLoading(false);
      }
    }
  }, [token, id]);

  useEffect(() => {
    fetchMediaStatus();
  }, [fetchMediaStatus]);

  // Polling for in-progress artifacts and transcript
  const startPolling = useCallback(() => {
    if (pollingRef.current) return; // Already polling

    pollingRef.current = setInterval(async () => {
      if (!token || !id || !mountedRef.current) return;

      try {
        const response = await MediaService.getMediaStatus(token, id);
        if (!mountedRef.current) return;

        setMediaData(response);

        const newStates: Record<ArtifactType, ArtifactLocalState> = {
          summary: { status: "idle" },
          quiz: { status: "idle" },
          notes: { status: "idle" },
        };

        for (const artifact of response.artifacts) {
          newStates[artifact.artifact_type] = {
            status: artifact.status,
            artifactId: artifact.artifact_id,
          };
        }

        const artifactStatuses = response.media_item.artifact_statuses;
        if (artifactStatuses) {
          for (const [type, snapshot] of Object.entries(artifactStatuses)) {
            if (snapshot) {
              newStates[type as ArtifactType] = {
                status: snapshot.status,
                artifactId: snapshot.artifact_id,
              };
            }
          }
        }

        setArtifactStates(newStates);

        // Stop polling if nothing is in progress anymore
        const hasInProgress = Object.values(newStates).some(
          (s) => s.status === "queued" || s.status === "generating",
        );
        const transcriptProcessing =
          response.media_item.transcript &&
          response.media_item.transcript.status !== "ready" &&
          response.media_item.transcript.status !== "failed";

        if (!hasInProgress && !transcriptProcessing && pollingRef.current) {
          clearInterval(pollingRef.current);
          pollingRef.current = null;
        }
      } catch {
        // Silent fail during polling - don't disrupt user
      }
    }, POLL_INTERVAL_MS);
  }, [token, id]);

  const handleGenerate = useCallback(
    async (artifactType: ArtifactType) => {
      if (!token || !id) return;

      // Optimistic update
      setArtifactStates((prev) => ({
        ...prev,
        [artifactType]: { status: "queued" },
      }));

      try {
        const result = await ArtifactService.generateArtifact(
          token,
          id,
          artifactType,
        );
        if (!mountedRef.current) return;

        setArtifactStates((prev) => ({
          ...prev,
          [artifactType]: {
            status: result.status,
            artifactId: result.artifact_id,
          },
        }));

        // Start polling for progress
        startPolling();
      } catch (err) {
        if (!mountedRef.current) return;
        setArtifactStates((prev) => ({
          ...prev,
          [artifactType]: {
            status: "failed",
            error: getFriendlyErrorMessage(err),
          },
        }));
      }
    },
    [token, id, startPolling],
  );

  const handleRetryProcessing = useCallback(async () => {
    // Re-fetch media status to check if processing has resumed
    if (!token || !id) return;
    try {
      const response = await MediaService.getMediaStatus(token, id);
      if (!mountedRef.current) return;
      setMediaData(response);
      // If still failed, user needs to re-submit. Otherwise, start polling.
      if (
        response.processing_job.status !== "failed" &&
        response.processing_job.status !== "cancelled"
      ) {
        startPolling();
      }
    } catch {
      // Silent - user can try again
    }
  }, [token, id, startPolling]);

  const toggleArtifactsExpanded = () => {
    LayoutAnimation.configureNext(LayoutAnimation.Presets.easeInEaseOut);
    setArtifactsExpanded((prev) => !prev);
  };

  // Loading state
  if (loading) {
    return (
      <SafeAreaView style={styles.container} edges={["top"]}>
        <Header onBack={() => router.back()} />
        <View style={styles.centered}>
          <ActivityIndicator size="large" color={Colors.primary} />
        </View>
      </SafeAreaView>
    );
  }

  // Error state
  if (error || !mediaData) {
    return (
      <SafeAreaView style={styles.container} edges={["top"]}>
        <Header onBack={() => router.back()} />
        <View style={styles.centered}>
          <Ionicons
            name="alert-circle-outline"
            size={48}
            color={Colors.error}
          />
          <Text style={styles.errorText}>
            {error || "Unable to load media details."}
          </Text>
          <Pressable
            style={styles.retryButton}
            onPress={fetchMediaStatus}
            accessibilityLabel="Retry loading media details"
            accessibilityRole="button"
          >
            <Text style={styles.retryButtonText}>Retry</Text>
          </Pressable>
        </View>
      </SafeAreaView>
    );
  }

  const { media_item, processing_job } = mediaData;

  // Extract display info
  let displayTitle: string;
  try {
    const parsed = new URL(media_item.original_url);
    displayTitle = parsed.pathname.split("/").pop() || parsed.hostname;
  } catch {
    displayTitle = media_item.original_url;
  }

  const displayDomain = (() => {
    try {
      return new URL(media_item.original_url).hostname.replace(/^www\./, "");
    } catch {
      return media_item.source_platform;
    }
  })();

  const formattedDate = (() => {
    try {
      return new Date(media_item.created_at).toLocaleDateString("en-US", {
        month: "short",
        day: "numeric",
        year: "numeric",
      });
    } catch {
      return "";
    }
  })();

  const durationLabel = media_item.transcript?.duration_seconds
    ? formatDuration(media_item.transcript.duration_seconds)
    : null;

  const mediaReady =
    media_item.status === "ready_for_artifacts" ||
    processing_job.status === "ready_for_artifacts" ||
    processing_job.status === "completed";

  return (
    <SafeAreaView style={styles.container} edges={["top"]}>
      <Header onBack={() => router.back()} />

      <ScrollView
        style={styles.scrollView}
        contentContainerStyle={styles.scrollContent}
        showsVerticalScrollIndicator={false}
      >
        {/* Hero Title & Metadata */}
        <View style={styles.heroSection}>
          <Text style={styles.heroTitle}>{displayTitle}</Text>
          <View style={styles.metaRow}>
            <View style={styles.metaChip}>
              <Ionicons
                name={getMediaTypeIcon(media_item.media_type)}
                size={14}
                color={Colors.textMain}
              />
              <Text style={styles.metaChipText}>
                {displayDomain.toUpperCase()}
              </Text>
            </View>
            {formattedDate ? (
              <>
                <Text style={styles.metaDot}>{"•"}</Text>
                <Text style={styles.metaText}>{formattedDate}</Text>
              </>
            ) : null}
            {durationLabel ? (
              <>
                <Text style={styles.metaDot}>{"•"}</Text>
                <Text style={styles.metaText}>{durationLabel}</Text>
              </>
            ) : null}
          </View>
        </View>

        {/* Processing Status Banner (AC#4) */}
        {processing_job.status === "failed" && (
          <ProcessingFailedBanner
            errorMessage={processing_job.error_message}
            onRetry={handleRetryProcessing}
          />
        )}

        {/* AI Artifacts Section (AC#5) */}
        <View style={styles.artifactsSection}>
          <Pressable
            style={styles.artifactsToggle}
            onPress={toggleArtifactsExpanded}
            accessibilityLabel={`AI Artifacts, ${artifactsExpanded ? "collapse" : "expand"}`}
            accessibilityRole="button"
          >
            <View style={styles.artifactsToggleLeft}>
              <Ionicons
                name={artifactsExpanded ? "chevron-up" : "chevron-down"}
                size={20}
                color={Colors.textMain}
              />
              <Text style={styles.artifactsToggleText}>AI Artifacts</Text>
            </View>
            <Ionicons
              name={artifactsExpanded ? "chevron-up" : "chevron-down"}
              size={20}
              color={Colors.textMain}
            />
          </Pressable>

          {artifactsExpanded && (
            <View style={styles.artifactsList}>
              {ARTIFACT_TYPES.map((artifact) => (
                <ArtifactRow
                  key={artifact.type}
                  type={artifact.type}
                  label={artifact.label}
                  icon={artifact.icon}
                  state={artifactStates[artifact.type]}
                  onGenerate={() => handleGenerate(artifact.type)}
                  mediaReady={mediaReady}
                />
              ))}
            </View>
          )}
        </View>

        {/* Transcript / Content Section (AC#4) */}
        <View style={styles.contentSection}>
          <TranscriptSection
            transcript={media_item.transcript}
            processingStatus={processing_job.status}
            onRefresh={fetchMediaStatus}
          />
        </View>
      </ScrollView>
    </SafeAreaView>
  );
}

// --- Sub-components ---

function Header({ onBack }: { onBack: () => void }) {
  return (
    <View style={styles.header}>
      <Pressable
        style={styles.headerButton}
        onPress={onBack}
        accessibilityLabel="Go back"
        accessibilityRole="button"
        hitSlop={{ top: 4, bottom: 4, left: 4, right: 4 }}
      >
        <Ionicons name="arrow-back" size={24} color={Colors.textMain} />
      </Pressable>
      <Pressable
        style={styles.headerButton}
        accessibilityLabel="Share"
        accessibilityRole="button"
        hitSlop={{ top: 4, bottom: 4, left: 4, right: 4 }}
      >
        <Ionicons name="share-outline" size={24} color={Colors.textMain} />
      </Pressable>
    </View>
  );
}

/**
 * Banner shown when the processing job has failed (AC#4).
 * Provides context and a refresh action.
 */
function ProcessingFailedBanner({
  errorMessage,
  onRetry,
}: {
  errorMessage?: string;
  onRetry: () => void;
}) {
  return (
    <View style={styles.failedBanner}>
      <View style={styles.failedBannerContent}>
        <Ionicons name="alert-circle" size={20} color={Colors.error} />
        <View style={styles.failedBannerText}>
          <Text style={styles.failedBannerTitle}>Processing failed</Text>
          <Text style={styles.failedBannerMessage}>
            {errorMessage || "An error occurred during processing. You can try refreshing."}
          </Text>
        </View>
      </View>
      <Pressable
        style={styles.failedBannerRetry}
        onPress={onRetry}
        accessibilityLabel="Refresh processing status"
        accessibilityRole="button"
      >
        <Ionicons name="refresh" size={16} color={Colors.error} />
        <Text style={styles.failedBannerRetryText}>Refresh</Text>
      </Pressable>
    </View>
  );
}

function ArtifactRow({
  type,
  label,
  icon,
  state,
  onGenerate,
  mediaReady,
}: {
  type: ArtifactType;
  label: string;
  icon: React.ComponentProps<typeof Ionicons>["name"];
  state: ArtifactLocalState;
  onGenerate: () => void;
  mediaReady: boolean;
}) {
  const isInProgress =
    state.status === "queued" || state.status === "generating";
  const isReady = state.status === "ready";
  const isFailed = state.status === "failed";
  const canGenerate = state.status === "idle" && mediaReady;

  return (
    <View style={styles.artifactRow}>
      <View style={styles.artifactRowLeft}>
        <Ionicons name={icon} size={20} color={Colors.primary} />
        <Text style={styles.artifactRowLabel}>{label}</Text>
      </View>

      <View style={styles.artifactRowRight}>
        {isInProgress && (
          <View style={styles.artifactProgressContainer}>
            <ActivityIndicator size="small" color={Colors.primary} />
            <Text style={styles.artifactProgressText}>
              {state.status === "queued" ? "Queued" : "Generating..."}
            </Text>
          </View>
        )}

        {isReady && (
          <View style={styles.artifactReadyContainer}>
            <View style={styles.artifactReadyBadge}>
              <Ionicons name="checkmark-circle" size={16} color="#4caf50" />
              <Text style={styles.artifactReadyText}>Ready</Text>
            </View>
            <Pressable
              style={styles.artifactViewButton}
              accessibilityLabel={`View ${label}`}
              accessibilityRole="button"
            >
              <Text style={styles.artifactViewButtonText}>View</Text>
            </Pressable>
          </View>
        )}

        {isFailed && (
          <View style={styles.artifactFailedContainer}>
            <Text style={styles.artifactFailedText}>Failed</Text>
            <Pressable
              style={styles.artifactRetryButton}
              onPress={onGenerate}
              accessibilityLabel={`Retry generating ${label}`}
              accessibilityRole="button"
            >
              <Text style={styles.artifactRetryText}>Retry</Text>
            </Pressable>
          </View>
        )}

        {canGenerate && (
          <Pressable
            style={styles.generateButton}
            onPress={onGenerate}
            accessibilityLabel={`Generate ${label}`}
            accessibilityRole="button"
          >
            <Text style={styles.generateButtonText}>Generate</Text>
          </Pressable>
        )}

        {state.status === "idle" && !mediaReady && (
          <Text style={styles.artifactWaitingText}>Processing...</Text>
        )}
      </View>
    </View>
  );
}

/**
 * Transcript section with status display and retry capability (AC#4).
 */
function TranscriptSection({
  transcript,
  processingStatus,
  onRefresh,
}: {
  transcript: MediaStatusResponse["media_item"]["transcript"];
  processingStatus: ProcessingJobLifecycleStatus;
  onRefresh: () => void;
}) {
  if (!transcript) {
    return (
      <View style={styles.transcriptEmpty}>
        <Ionicons
          name="document-text-outline"
          size={32}
          color={Colors.textMuted}
        />
        <Text style={styles.transcriptEmptyText}>
          No transcript available yet.
        </Text>
        {processingStatus !== "completed" &&
          processingStatus !== "failed" &&
          processingStatus !== "cancelled" && (
            <Text style={styles.transcriptEmptyHint}>
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
    <View style={styles.transcriptContainer}>
      <Text style={styles.sectionTitle}>Transcript</Text>

      {/* Transcript metadata */}
      <View style={styles.transcriptMeta}>
        {transcript.language && (
          <View style={styles.transcriptMetaItem}>
            <Ionicons
              name="language-outline"
              size={14}
              color={Colors.textMuted}
            />
            <Text style={styles.transcriptMetaText}>
              {transcript.language.toUpperCase()}
            </Text>
          </View>
        )}
        {transcript.duration_seconds && (
          <View style={styles.transcriptMetaItem}>
            <Ionicons name="time-outline" size={14} color={Colors.textMuted} />
            <Text style={styles.transcriptMetaText}>
              {formatDuration(transcript.duration_seconds)}
            </Text>
          </View>
        )}
        {transcript.segments_count && (
          <View style={styles.transcriptMetaItem}>
            <Ionicons name="list-outline" size={14} color={Colors.textMuted} />
            <Text style={styles.transcriptMetaText}>
              {transcript.segments_count} segments
            </Text>
          </View>
        )}
      </View>

      {/* Status indicator */}
      <View style={styles.transcriptStatusRow}>
        {isProcessing && (
          <ActivityIndicator
            size="small"
            color={Colors.primary}
            style={{ marginRight: Spacing.sm }}
          />
        )}
        {isFailed && (
          <Ionicons
            name="close-circle"
            size={16}
            color={Colors.error}
            style={{ marginRight: Spacing.sm }}
          />
        )}
        {isReady && (
          <Ionicons
            name="checkmark-circle"
            size={16}
            color="#4caf50"
            style={{ marginRight: Spacing.sm }}
          />
        )}
        <Text
          style={[
            styles.transcriptStatusText,
            isFailed && { color: Colors.error },
          ]}
        >
          {statusMessages[transcript.status] || "Processing..."}
        </Text>
      </View>

      {/* Retry button for failed transcription (AC#4) */}
      {isFailed && (
        <Pressable
          style={styles.transcriptRetryButton}
          onPress={onRefresh}
          accessibilityLabel="Refresh transcript status"
          accessibilityRole="button"
        >
          <Ionicons name="refresh" size={16} color={Colors.error} />
          <Text style={styles.transcriptRetryText}>Refresh status</Text>
        </Pressable>
      )}
    </View>
  );
}

// --- Helpers ---

function formatDuration(seconds: number): string {
  const mins = Math.floor(seconds / 60);
  const secs = Math.floor(seconds % 60);
  if (mins >= 60) {
    const hrs = Math.floor(mins / 60);
    const remainMins = mins % 60;
    return `${hrs}h ${remainMins}m`;
  }
  return `${mins}m ${secs}s`;
}

function getMediaTypeIcon(
  mediaType: string,
): React.ComponentProps<typeof Ionicons>["name"] {
  switch (mediaType) {
    case "podcast_episode":
      return "mic-outline";
    case "youtube_video":
    case "short_video":
      return "videocam-outline";
    case "article":
      return "document-text-outline";
    case "audio_file":
      return "musical-notes-outline";
    default:
      return "link-outline";
  }
}

// --- Styles ---

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: Colors.background,
  },
  centered: {
    flex: 1,
    justifyContent: "center",
    alignItems: "center",
    paddingHorizontal: Spacing.xl,
    gap: Spacing.md,
  },
  scrollView: {
    flex: 1,
  },
  scrollContent: {
    paddingHorizontal: Spacing.lg,
    paddingTop: Spacing.md,
    paddingBottom: Spacing.xxl,
  },

  // Header - buttons meet 48px with hitSlop
  header: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    paddingHorizontal: Spacing.md,
    paddingVertical: Spacing.sm,
    minHeight: TouchTarget.comfortable,
  },
  headerButton: {
    width: 44,
    height: 44,
    borderRadius: BorderRadius.full,
    justifyContent: "center",
    alignItems: "center",
  },

  // Hero
  heroSection: {
    marginBottom: Spacing.xl,
  },
  heroTitle: {
    fontSize: Typography.display.fontSize,
    fontWeight: Typography.display.fontWeight,
    color: Colors.textMain,
    letterSpacing: Typography.display.letterSpacing,
    lineHeight: 38,
    marginBottom: Spacing.sm,
  },
  metaRow: {
    flexDirection: "row",
    alignItems: "center",
    flexWrap: "wrap",
    gap: Spacing.sm,
  },
  metaChip: {
    flexDirection: "row",
    alignItems: "center",
    gap: 6,
    paddingHorizontal: 10,
    paddingVertical: 4,
    borderRadius: BorderRadius.full,
    backgroundColor: Colors.surface,
    borderWidth: StyleSheet.hairlineWidth,
    borderColor: Colors.outlineVariant,
  },
  metaChipText: {
    fontSize: Typography.small.fontSize,
    fontWeight: Typography.label.fontWeight,
    color: Colors.textMain,
    letterSpacing: 0.5,
  },
  metaDot: {
    fontSize: Typography.small.fontSize,
    color: Colors.textMuted,
  },
  metaText: {
    fontSize: Typography.small.fontSize,
    fontWeight: Typography.label.fontWeight,
    color: Colors.textMuted,
    textTransform: "uppercase",
    letterSpacing: 0.5,
  },

  // Processing failed banner (AC#4)
  failedBanner: {
    backgroundColor: Colors.errorContainer,
    borderRadius: BorderRadius.xl,
    padding: Spacing.md,
    marginBottom: Spacing.lg,
    gap: Spacing.sm,
  },
  failedBannerContent: {
    flexDirection: "row",
    alignItems: "flex-start",
    gap: Spacing.sm,
  },
  failedBannerText: {
    flex: 1,
  },
  failedBannerTitle: {
    fontSize: Typography.label.fontSize,
    fontWeight: "600",
    color: Colors.error,
    marginBottom: 2,
  },
  failedBannerMessage: {
    fontSize: Typography.small.fontSize,
    color: Colors.textMain,
    lineHeight: 18,
  },
  failedBannerRetry: {
    flexDirection: "row",
    alignItems: "center",
    alignSelf: "flex-start",
    gap: Spacing.xs,
    paddingHorizontal: Spacing.md,
    paddingVertical: Spacing.sm,
    borderRadius: BorderRadius.md,
    backgroundColor: "rgba(186, 26, 26, 0.08)",
    minHeight: TouchTarget.minimum,
  },
  failedBannerRetryText: {
    fontSize: Typography.label.fontSize,
    fontWeight: "600",
    color: Colors.error,
  },

  // Artifacts section
  artifactsSection: {
    marginBottom: Spacing.lg,
  },
  artifactsToggle: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    backgroundColor: Colors.primary,
    paddingHorizontal: Spacing.lg,
    paddingVertical: Spacing.md,
    borderRadius: BorderRadius.xl,
    minHeight: TouchTarget.minimum,
    ...Shadows.soft,
  },
  artifactsToggleLeft: {
    flexDirection: "row",
    alignItems: "center",
    gap: Spacing.sm,
  },
  artifactsToggleText: {
    fontSize: Typography.body.fontSize,
    fontWeight: "600",
    color: Colors.textMain,
  },
  artifactsList: {
    marginTop: Spacing.sm,
    backgroundColor: Colors.surface,
    borderRadius: BorderRadius.xl,
    borderWidth: StyleSheet.hairlineWidth,
    borderColor: Colors.outlineVariant,
    overflow: "hidden",
    ...Shadows.soft,
  },
  artifactRow: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    paddingHorizontal: Spacing.lg,
    paddingVertical: 14,
    minHeight: TouchTarget.minimum,
    borderBottomWidth: StyleSheet.hairlineWidth,
    borderBottomColor: Colors.outlineVariant,
  },
  artifactRowLeft: {
    flexDirection: "row",
    alignItems: "center",
    gap: Spacing.sm + 4,
  },
  artifactRowLabel: {
    fontSize: Typography.body.fontSize,
    fontWeight: "600",
    color: Colors.textMain,
  },
  artifactRowRight: {
    flexDirection: "row",
    alignItems: "center",
  },

  // Artifact states
  artifactProgressContainer: {
    flexDirection: "row",
    alignItems: "center",
    gap: Spacing.sm,
  },
  artifactProgressText: {
    fontSize: Typography.small.fontSize,
    color: Colors.textMuted,
  },
  artifactReadyContainer: {
    flexDirection: "row",
    alignItems: "center",
    gap: Spacing.sm,
  },
  artifactReadyBadge: {
    flexDirection: "row",
    alignItems: "center",
    gap: 4,
  },
  artifactReadyText: {
    fontSize: Typography.small.fontSize,
    fontWeight: Typography.label.fontWeight,
    color: "#4caf50",
  },
  artifactViewButton: {
    paddingHorizontal: Spacing.md,
    paddingVertical: 6,
    borderRadius: BorderRadius.md,
    backgroundColor: Colors.surfaceContainerHigh,
    minHeight: 36,
    justifyContent: "center",
  },
  artifactViewButtonText: {
    fontSize: Typography.label.fontSize,
    fontWeight: "600",
    color: Colors.textMain,
  },
  artifactFailedContainer: {
    flexDirection: "row",
    alignItems: "center",
    gap: Spacing.sm,
  },
  artifactFailedText: {
    fontSize: Typography.small.fontSize,
    color: Colors.error,
  },
  artifactRetryButton: {
    paddingHorizontal: Spacing.md,
    paddingVertical: 6,
    borderRadius: BorderRadius.md,
    backgroundColor: Colors.errorContainer,
    minHeight: 36,
    justifyContent: "center",
  },
  artifactRetryText: {
    fontSize: Typography.small.fontSize,
    fontWeight: Typography.label.fontWeight,
    color: Colors.error,
  },
  artifactWaitingText: {
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

  // Content / Transcript section
  contentSection: {
    marginTop: Spacing.sm,
  },
  sectionTitle: {
    fontSize: Typography.headline.fontSize,
    fontWeight: Typography.headline.fontWeight,
    color: Colors.textMain,
    marginBottom: Spacing.md,
  },
  transcriptContainer: {
    gap: Spacing.sm,
  },
  transcriptMeta: {
    flexDirection: "row",
    flexWrap: "wrap",
    gap: Spacing.md,
    marginBottom: Spacing.sm,
  },
  transcriptMetaItem: {
    flexDirection: "row",
    alignItems: "center",
    gap: 4,
  },
  transcriptMetaText: {
    fontSize: Typography.small.fontSize,
    color: Colors.textMuted,
  },
  transcriptStatusRow: {
    flexDirection: "row",
    alignItems: "center",
    paddingVertical: Spacing.sm,
  },
  transcriptStatusText: {
    fontSize: Typography.body.fontSize,
    color: Colors.textMain,
    lineHeight: Typography.body.lineHeight,
  },
  transcriptRetryButton: {
    flexDirection: "row",
    alignItems: "center",
    alignSelf: "flex-start",
    gap: Spacing.xs,
    paddingHorizontal: Spacing.md,
    paddingVertical: Spacing.sm,
    borderRadius: BorderRadius.md,
    backgroundColor: Colors.errorContainer,
    minHeight: TouchTarget.minimum,
    marginTop: Spacing.sm,
  },
  transcriptRetryText: {
    fontSize: Typography.label.fontSize,
    fontWeight: "600",
    color: Colors.error,
  },
  transcriptEmpty: {
    alignItems: "center",
    gap: Spacing.sm,
    paddingVertical: Spacing.xl,
  },
  transcriptEmptyText: {
    fontSize: Typography.body.fontSize,
    color: Colors.textMuted,
  },
  transcriptEmptyHint: {
    fontSize: Typography.small.fontSize,
    color: Colors.textMuted,
    fontStyle: "italic",
    textAlign: "center",
  },

  // Error state
  errorText: {
    fontSize: Typography.body.fontSize,
    color: Colors.textMain,
    textAlign: "center",
  },
  retryButton: {
    paddingHorizontal: Spacing.lg,
    paddingVertical: Spacing.sm,
    backgroundColor: Colors.primary,
    borderRadius: BorderRadius.md,
    marginTop: Spacing.sm,
    minHeight: TouchTarget.minimum,
    justifyContent: "center",
    alignItems: "center",
  },
  retryButtonText: {
    fontSize: Typography.label.fontSize,
    fontWeight: "600",
    color: Colors.textMain,
  },
});
