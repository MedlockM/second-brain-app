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
import { useMediaDetailPolling } from "../../src/hooks/useMediaDetailPolling";
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

/**
 * Tiles surfaced in the "AI Artifacts" dropdown. Each row maps to a single
 * backend artifact type produced by a dedicated worker.
 */
const ARTIFACT_TYPES: {
  type: ArtifactType;
  label: string;
  icon: React.ComponentProps<typeof Ionicons>["name"];
}[] = [
  {
    type: "summary_short",
    label: "Summary",
    icon: "document-text-outline",
  },
  {
    type: "summary_detailed",
    label: "Detailed summary",
    icon: "reader-outline",
  },
  { type: "notes", label: "Learning notes", icon: "book-outline" },
  { type: "flashcards", label: "Flashcards", icon: "card-outline" },
  { type: "quiz", label: "Quiz", icon: "help-circle-outline" },
];

/**
 * Some legacy items still carry the unscoped "summary" type from before the
 * short/detailed split. Surface them under the "Summary" tile instead of
 * dropping them on the floor.
 */
function bucketArtifactType(raw: ArtifactType): ArtifactType {
  if (raw === "summary") return "summary_short";
  return raw;
}

function buildInitialArtifactStates(): Record<ArtifactType, ArtifactLocalState> {
  return {
    summary: { status: "idle" },
    summary_short: { status: "idle" },
    summary_detailed: { status: "idle" },
    notes: { status: "idle" },
    flashcards: { status: "idle" },
    quiz: { status: "idle" },
  };
}

const ARTIFACT_POLL_INTERVAL_MS = 3000;

type ArtifactLocalState = {
  status: ArtifactStatus | "idle";
  artifactId?: string;
  error?: string;
};

type RawContentState =
  | { status: "idle" }
  | { status: "loading" }
  | { status: "ready"; content: string }
  | { status: "translation_pending"; content: string }
  | { status: "not_available" }
  | { status: "error"; message: string };

/** Delay between polls when translation is pending (ms). */
const TRANSLATION_POLL_DELAY_MS = 3000;
/** Maximum number of translation polls before giving up. */
const TRANSLATION_POLL_MAX_ATTEMPTS = 20;

/**
 * Media Detail Screen.
 *
 * Lifecycle:
 * 1. On mount, uses `useMediaDetailPolling` hook to fetch media status.
 * 2. If the processing job is non-terminal, shows a "Generating text..." placeholder
 *    with a spinner. Polls every 3s until status becomes terminal.
 * 3. On "completed": transitions to the full detail view with artifacts.
 * 4. On "failed": shows a failure banner with the error message.
 * 5. On 5-minute timeout: stops polling and shows a "taking longer" message.
 *
 * Features:
 * - Contextual processing message based on source_platform
 * - Artifacts section with generation actions
 * - Retry/refresh for failed states
 * - All interactive elements meet 48px minimum touch target
 */
export default function MediaDetailScreen() {
  const { id } = useLocalSearchParams<{ id: string }>();
  const router = useRouter();

  const {
    state: pollingState,
    mediaData,
    fetchError,
    processingError,
    processingMessage,
    refresh,
  } = useMediaDetailPolling(id);

  // --- Loading state (initial fetch) ---
  if (pollingState === "loading") {
    return (
      <SafeAreaView style={styles.container} edges={["top"]}>
        <Header onBack={() => router.back()} />
        <View style={styles.centered}>
          <ActivityIndicator size="large" color={Colors.primary} />
        </View>
      </SafeAreaView>
    );
  }

  // --- Fetch error state (network/auth error) ---
  if (pollingState === "error") {
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
            {fetchError || "Unable to load media details."}
          </Text>
          <Pressable
            style={styles.retryButton}
            onPress={refresh}
            accessibilityLabel="Retry loading media details"
            accessibilityRole="button"
          >
            <Text style={styles.retryButtonText}>Retry</Text>
          </Pressable>
        </View>
      </SafeAreaView>
    );
  }

  // --- Processing state (non-terminal, showing placeholder) ---
  if (pollingState === "processing") {
    return (
      <SafeAreaView style={styles.container} edges={["top"]}>
        <Header onBack={() => router.back()} />
        <View style={styles.centered}>
          <View style={styles.processingIconContainer}>
            <ActivityIndicator size="large" color={Colors.primary} />
          </View>
          <Text style={styles.processingTitle}>{processingMessage}</Text>
          <Text style={styles.processingSubtitle}>
            This usually takes less than a minute.
          </Text>
        </View>
      </SafeAreaView>
    );
  }

  // --- Timeout state (5 minutes elapsed without completion) ---
  if (pollingState === "timeout") {
    return (
      <SafeAreaView style={styles.container} edges={["top"]}>
        <Header onBack={() => router.back()} />
        <View style={styles.centered}>
          <Ionicons
            name="time-outline"
            size={48}
            color={Colors.textMuted}
          />
          <Text style={styles.timeoutTitle}>
            This is taking longer than usual.
          </Text>
          <Text style={styles.timeoutSubtitle}>
            Pull down to refresh or come back later.
          </Text>
          <Pressable
            style={styles.refreshButton}
            onPress={refresh}
            accessibilityLabel="Refresh media status"
            accessibilityRole="button"
          >
            <Ionicons name="refresh" size={18} color={Colors.onPrimary} />
            <Text style={styles.refreshButtonText}>Refresh</Text>
          </Pressable>
        </View>
      </SafeAreaView>
    );
  }

  // --- Failed state (processing failed) ---
  if (pollingState === "failed") {
    return (
      <SafeAreaView style={styles.container} edges={["top"]}>
        <Header onBack={() => router.back()} />
        <View style={styles.centered}>
          <Ionicons
            name="alert-circle"
            size={48}
            color={Colors.error}
          />
          <Text style={styles.failedTitle}>Processing failed</Text>
          <Text style={styles.failedMessage}>
            {processingError || "An unexpected error occurred."}
          </Text>
          <Pressable
            style={styles.refreshButton}
            onPress={refresh}
            accessibilityLabel="Refresh media status"
            accessibilityRole="button"
          >
            <Ionicons name="refresh" size={18} color={Colors.onPrimary} />
            <Text style={styles.refreshButtonText}>Refresh</Text>
          </Pressable>
        </View>
      </SafeAreaView>
    );
  }

  // --- Completed state (full detail view) ---
  if (!mediaData) {
    // Safety check: should not happen after the hook resolves
    return (
      <SafeAreaView style={styles.container} edges={["top"]}>
        <Header onBack={() => router.back()} />
        <View style={styles.centered}>
          <Text style={styles.errorText}>Unable to load media details.</Text>
        </View>
      </SafeAreaView>
    );
  }

  return (
    <CompletedDetailView
      mediaData={mediaData}
      onBack={() => router.back()}
    />
  );
}

// --- Completed Detail View (extracted for clarity) ---

interface CompletedDetailViewProps {
  mediaData: MediaStatusResponse;
  onBack: () => void;
}

function CompletedDetailView({ mediaData, onBack }: CompletedDetailViewProps) {
  const { token } = useAuth();
  const router = useRouter();
  const { media_item, processing_job } = mediaData;

  const [artifactsExpanded, setArtifactsExpanded] = useState(true);
  const [artifactStates, setArtifactStates] = useState<
    Record<ArtifactType, ArtifactLocalState>
  >(() => {
    const initial = buildInitialArtifactStates();

    for (const artifact of mediaData.artifacts) {
      const bucket = bucketArtifactType(artifact.artifact_type);
      initial[bucket] = {
        status: artifact.status,
        artifactId: artifact.artifact_id,
      };
    }

    const artifactStatuses = media_item.artifact_statuses;
    if (artifactStatuses) {
      for (const [type, snapshot] of Object.entries(artifactStatuses)) {
        if (snapshot) {
          const bucket = bucketArtifactType(type as ArtifactType);
          initial[bucket] = {
            status: snapshot.status,
            artifactId: snapshot.artifact_id,
          };
        }
      }
    }

    return initial;
  });

  const mountedRef = useRef(true);
  const artifactPollRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const [rawContent, setRawContent] = useState<RawContentState>({
    status: "idle",
  });

  useEffect(() => {
    return () => {
      mountedRef.current = false;
      if (artifactPollRef.current) {
        clearInterval(artifactPollRef.current);
      }
    };
  }, []);

  const startArtifactPolling = useCallback(() => {
    if (artifactPollRef.current) return;

    artifactPollRef.current = setInterval(async () => {
      if (!token || !mountedRef.current) return;

      try {
        const response = await MediaService.getMediaStatus(
          token,
          media_item.media_item_id,
        );
        if (!mountedRef.current) return;

        const newStates = buildInitialArtifactStates();

        for (const artifact of response.artifacts) {
          const bucket = bucketArtifactType(artifact.artifact_type);
          newStates[bucket] = {
            status: artifact.status,
            artifactId: artifact.artifact_id,
          };
        }

        const artifactStatuses = response.media_item.artifact_statuses;
        if (artifactStatuses) {
          for (const [type, snapshot] of Object.entries(artifactStatuses)) {
            if (snapshot) {
              const bucket = bucketArtifactType(type as ArtifactType);
              newStates[bucket] = {
                status: snapshot.status,
                artifactId: snapshot.artifact_id,
              };
            }
          }
        }

        setArtifactStates(newStates);

        // Stop if no artifacts are in progress
        const hasInProgress = Object.values(newStates).some(
          (s) => s.status === "queued" || s.status === "generating",
        );
        if (!hasInProgress && artifactPollRef.current) {
          clearInterval(artifactPollRef.current);
          artifactPollRef.current = null;
        }
      } catch {
        // Silent fail during polling
      }
    }, ARTIFACT_POLL_INTERVAL_MS);
  }, [token, media_item.media_item_id]);

  const handleGenerate = useCallback(
    async (artifactType: ArtifactType) => {
      if (!token) return;

      setArtifactStates((prev) => ({
        ...prev,
        [artifactType]: { status: "queued" },
      }));

      try {
        const result = await ArtifactService.generateArtifact(
          token,
          media_item.media_item_id,
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

        startArtifactPolling();
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
    [token, media_item.media_item_id, startArtifactPolling],
  );

  const toggleArtifactsExpanded = () => {
    LayoutAnimation.configureNext(LayoutAnimation.Presets.easeInEaseOut);
    setArtifactsExpanded((prev) => !prev);
  };

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

  const transcriptStatus = media_item.transcript?.status;

  const translationPollRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const translationPollCountRef = useRef(0);

  // Cleanup translation polling on unmount
  useEffect(() => {
    return () => {
      if (translationPollRef.current) {
        clearTimeout(translationPollRef.current);
        translationPollRef.current = null;
      }
    };
  }, []);

  const pollForTranslation = useCallback(async () => {
    if (!token || !mountedRef.current) return;
    translationPollCountRef.current += 1;

    try {
      const response = await MediaService.getRawContent(
        token,
        media_item.media_item_id,
      );
      if (!mountedRef.current) return;

      const trimmed = (response.content ?? "").trim();
      const isPending = response.translation?.translation_pending === true;

      if (!trimmed) {
        setRawContent({ status: "not_available" });
        return;
      }

      if (isPending && translationPollCountRef.current < TRANSLATION_POLL_MAX_ATTEMPTS) {
        // Translation still in progress, show content and keep polling
        setRawContent({ status: "translation_pending", content: trimmed });
        translationPollRef.current = setTimeout(() => {
          void pollForTranslation();
        }, TRANSLATION_POLL_DELAY_MS);
      } else {
        // Translation ready (or max polls reached -- show whatever we have)
        setRawContent({ status: "ready", content: trimmed });
      }
    } catch {
      // Silent fail during translation polling -- keep current state
      if (translationPollCountRef.current < TRANSLATION_POLL_MAX_ATTEMPTS) {
        translationPollRef.current = setTimeout(() => {
          void pollForTranslation();
        }, TRANSLATION_POLL_DELAY_MS);
      }
    }
  }, [token, media_item.media_item_id]);

  const fetchRawContent = useCallback(async () => {
    if (!token) return;
    setRawContent({ status: "loading" });
    translationPollCountRef.current = 0;

    try {
      const response = await MediaService.getRawContent(
        token,
        media_item.media_item_id,
      );
      if (!mountedRef.current) return;
      const trimmed = (response.content ?? "").trim();
      if (!trimmed) {
        setRawContent({ status: "not_available" });
        return;
      }

      const isPending = response.translation?.translation_pending === true;
      if (isPending) {
        // Show the original transcript immediately, start polling for translation
        setRawContent({ status: "translation_pending", content: trimmed });
        translationPollRef.current = setTimeout(() => {
          void pollForTranslation();
        }, TRANSLATION_POLL_DELAY_MS);
      } else {
        setRawContent({ status: "ready", content: trimmed });
      }
    } catch (err) {
      if (!mountedRef.current) return;
      const httpStatus = (err as { status?: number } | undefined)?.status;
      if (httpStatus === 404) {
        setRawContent({ status: "not_available" });
        return;
      }
      setRawContent({
        status: "error",
        message: getFriendlyErrorMessage(err, {
          fallback: "Unable to load the transcript right now.",
        }),
      });
    }
  }, [token, media_item.media_item_id, pollForTranslation]);

  useEffect(() => {
    if (!mediaReady) {
      // Reset whenever processing rewinds (e.g. user retries an item).
      setRawContent((prev) => (prev.status === "idle" ? prev : { status: "idle" }));
      return;
    }
    if (transcriptStatus === "failed") {
      setRawContent({ status: "not_available" });
      return;
    }
    setRawContent((prev) => {
      if (prev.status === "idle" || prev.status === "error") {
        void fetchRawContent();
        return { status: "loading" };
      }
      return prev;
    });
  }, [mediaReady, transcriptStatus, fetchRawContent]);

  return (
    <SafeAreaView style={styles.container} edges={["top"]}>
      <Header onBack={onBack} />

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

        {/* AI Artifacts Section */}
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
                  onView={(artifactId) =>
                    router.push(`/artifacts/${artifactId}`)
                  }
                  mediaReady={mediaReady}
                />
              ))}
            </View>
          )}
        </View>

        {/* Transcript / Content Section */}
        <View style={styles.contentSection}>
          <TranscriptSection
            transcript={media_item.transcript}
            processingStatus={processing_job.status}
            rawContent={rawContent}
            onRetryRawContent={fetchRawContent}
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

function ArtifactRow({
  type,
  label,
  icon,
  state,
  onGenerate,
  onView,
  mediaReady,
}: {
  type: ArtifactType;
  label: string;
  icon: React.ComponentProps<typeof Ionicons>["name"];
  state: ArtifactLocalState;
  onGenerate: () => void;
  onView: (artifactId: string) => void;
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
              <Ionicons name="checkmark-circle" size={16} color={Colors.primary} />
              <Text style={styles.artifactReadyText}>Ready</Text>
            </View>
            <Pressable
              style={styles.artifactViewButton}
              onPress={() =>
                state.artifactId && onView(state.artifactId)
              }
              disabled={!state.artifactId}
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
 * Transcript section with status display.
 */
function TranscriptSection({
  transcript,
  processingStatus,
  rawContent,
  onRetryRawContent,
}: {
  transcript: MediaStatusResponse["media_item"]["transcript"];
  processingStatus: ProcessingJobLifecycleStatus;
  rawContent: RawContentState;
  onRetryRawContent: () => void;
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

      {/* When the transcript is ready, surface the actual content inline.
          Until it's ready (or if fetching the body fails), keep the status row
          so the user knows where things stand. */}
      {isReady ? (
        <TranscriptContent state={rawContent} onRetry={onRetryRawContent} />
      ) : (
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
          <Text
            style={[
              styles.transcriptStatusText,
              isFailed && { color: Colors.error },
            ]}
          >
            {statusMessages[transcript.status] || "Processing..."}
          </Text>
        </View>
      )}
    </View>
  );
}

function TranscriptContent({
  state,
  onRetry,
}: {
  state: RawContentState;
  onRetry: () => void;
}) {
  if (state.status === "ready") {
    return (
      <View>
        <Text style={styles.transcriptBody}>{state.content}</Text>
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
            style={{ marginRight: Spacing.sm }}
          />
          <Text style={styles.translationPendingText}>
            Translating transcript...
          </Text>
        </View>
        <Text style={styles.transcriptBody}>{state.content}</Text>
      </View>
    );
  }

  if (state.status === "loading" || state.status === "idle") {
    return (
      <View style={styles.transcriptStatusRow}>
        <ActivityIndicator
          size="small"
          color={Colors.primary}
          style={{ marginRight: Spacing.sm }}
        />
        <Text style={styles.transcriptStatusText}>Loading transcript…</Text>
      </View>
    );
  }

  if (state.status === "not_available") {
    return (
      <View style={styles.transcriptStatusRow}>
        <Ionicons
          name="information-circle-outline"
          size={16}
          color={Colors.textMuted}
          style={{ marginRight: Spacing.sm }}
        />
        <Text style={styles.transcriptStatusText}>
          Transcript content is not available for this item.
        </Text>
      </View>
    );
  }

  return (
    <View>
      <View style={styles.transcriptStatusRow}>
        <Ionicons
          name="alert-circle"
          size={16}
          color={Colors.error}
          style={{ marginRight: Spacing.sm }}
        />
        <Text style={[styles.transcriptStatusText, { color: Colors.error }]}>
          {state.message}
        </Text>
      </View>
      <Pressable
        style={styles.refreshButton}
        onPress={onRetry}
        accessibilityLabel="Retry loading transcript"
        accessibilityRole="button"
      >
        <Ionicons name="refresh" size={18} color={Colors.onPrimary} />
        <Text style={styles.refreshButtonText}>Retry</Text>
      </Pressable>
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

  // Processing placeholder
  processingIconContainer: {
    marginBottom: Spacing.md,
  },
  processingTitle: {
    fontSize: Typography.headline.fontSize,
    fontWeight: Typography.headline.fontWeight,
    color: Colors.textMain,
    textAlign: "center",
  },
  processingSubtitle: {
    fontSize: Typography.body.fontSize,
    color: Colors.textMuted,
    textAlign: "center",
    marginTop: Spacing.xs,
  },

  // Timeout state
  timeoutTitle: {
    fontSize: Typography.headline.fontSize,
    fontWeight: Typography.headline.fontWeight,
    color: Colors.textMain,
    textAlign: "center",
  },
  timeoutSubtitle: {
    fontSize: Typography.body.fontSize,
    color: Colors.textMuted,
    textAlign: "center",
    marginTop: Spacing.xs,
  },

  // Failed state
  failedTitle: {
    fontSize: Typography.headline.fontSize,
    fontWeight: Typography.headline.fontWeight,
    color: Colors.error,
    textAlign: "center",
  },
  failedMessage: {
    fontSize: Typography.body.fontSize,
    color: Colors.textMain,
    textAlign: "center",
    lineHeight: Typography.body.lineHeight,
    marginTop: Spacing.xs,
  },

  // Refresh/Retry button
  refreshButton: {
    flexDirection: "row",
    alignItems: "center",
    gap: Spacing.sm,
    backgroundColor: Colors.primary,
    paddingHorizontal: Spacing.lg,
    paddingVertical: Spacing.sm + 4,
    borderRadius: BorderRadius.lg,
    minHeight: TouchTarget.minimum,
    marginTop: Spacing.md,
  },
  refreshButtonText: {
    fontSize: Typography.label.fontSize,
    fontWeight: Typography.label.fontWeight,
    color: Colors.onPrimary,
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
    color: Colors.primary,
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
  transcriptBody: {
    fontSize: Typography.body.fontSize,
    color: Colors.textMain,
    lineHeight: 24,
    paddingVertical: Spacing.sm,
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
