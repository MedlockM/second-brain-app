import { useEffect, useState, useCallback, useMemo, useRef } from "react";
import {
  View,
  Text,
  StyleSheet,
  ScrollView,
  Pressable,
  ActivityIndicator,
  Animated,
} from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";
import { useLocalSearchParams, useRouter, useFocusEffect } from "expo-router";
import { Ionicons } from "@expo/vector-icons";
import * as Linking from "expo-linking";
import { useAuth } from "../../src/contexts/AuthContext";
import { MediaService } from "../../src/services/mediaService";
import { ArtifactService } from "../../src/services/artifactService";
import { OrganizationService } from "../../src/services/organizationService";
import { getFriendlyErrorMessage } from "../../src/lib/getFriendlyErrorMessage";
import { formatDuration } from "../../src/lib/formatDuration";
import { useMediaDetailPolling } from "../../src/hooks/useMediaDetailPolling";
import {
  ARTIFACT_TILES,
  ArtifactTile,
  type ArtifactTileState,
} from "../../src/components/ArtifactTile";
import { ScreenTabs, type ScreenTab } from "../../src/components/ScreenTabs";
import {
  TranscriptReader,
  type TranscriptContentState,
} from "../../src/components/TranscriptReader";
import {
  Colors,
  Typography,
  Spacing,
  BorderRadius,
  TouchTarget,
} from "../../src/constants/theme";
import type {
  MediaStatusResponse,
  ArtifactType,
} from "../../src/types/media";

/**
 * The two intra-screen tabs of a media item: what it says, and what the models
 * can make of it. Reader is the default — the content comes first, generating
 * something out of it is a deliberate second step.
 */
type MediaDetailTabKey = "reader" | "ai";

const MEDIA_DETAIL_TABS: readonly ScreenTab<MediaDetailTabKey>[] = [
  { key: "reader", label: "Reader", icon: "book-outline" },
  { key: "ai", label: "AI", icon: "sparkles-outline" },
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

function buildInitialArtifactStates(): Record<ArtifactType, ArtifactTileState> {
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
const ARTIFACT_TRANSLATION_RETRY_MAX_ATTEMPTS = 100;

/** Delay between polls when translation is pending (ms). */
const TRANSLATION_POLL_DELAY_MS = 3000;
/** Maximum number of translation polls before giving up. */
const TRANSLATION_POLL_MAX_ATTEMPTS = 20;

/** An `original_url` that is actually a destination the OS can open. */
type SourceLink = {
  /** The http(s) URL handed to `Linking.openURL`, verbatim. */
  url: string;
  /** Host without the `www.` prefix, used to name the destination out loud. */
  host: string;
};

/**
 * Decides whether the stored source URL is something we can offer to reopen.
 *
 * Only http(s) qualifies, and that is deliberate: on iOS and Android an
 * `instagram.com` / `youtube.com` https URL is claimed by the installed app and
 * opens it natively, so a universal link needs no per-source custom scheme (and
 * no `LSApplicationQueriesSchemes` entry per platform).
 *
 * Everything else stored in `source_url` is not a destination. Checked against
 * `user_media-dev` on 2026-08-17: uploads carry no `source_url` attribute at all
 * (the API defaults it to `""`), and WhatsApp-shared audio and text carry a
 * synthetic `share://whatsapp/...` marker. Both return `null` here, which is what
 * keeps the chip inert rather than offering a tap that goes nowhere.
 */
function resolveSourceLink(rawUrl: string): SourceLink | null {
  const trimmed = rawUrl.trim();
  if (!trimmed) return null;

  try {
    const parsed = new URL(trimmed);
    if (parsed.protocol !== "https:" && parsed.protocol !== "http:") {
      return null;
    }
    const host = parsed.hostname.replace(/^www\./, "");
    if (!host) return null;
    return { url: trimmed, host };
  } catch {
    return null;
  }
}

/**
 * Media Detail Screen.
 *
 * Lifecycle:
 * 1. On mount, uses `useMediaDetailPolling` hook to fetch media status.
 * 2. If the processing job is non-terminal, shows a "Generating text..." placeholder
 *    with a spinner. Polls every 3s until status becomes terminal.
 * 3. On "completed": transitions to the full detail view, split into a "Reader"
 *    tab (the transcript) and an "AI" tab (artifact generation).
 * 4. On "failed": shows a failure banner with the error message.
 * 5. On 5-minute timeout: stops polling and shows a "taking longer" message.
 *
 * Features:
 * - Contextual processing message based on source_platform
 * - Intra-screen Reader / AI tabs, Reader selected by default
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

  // --- Collection state ---
  const [currentFolderId, setCurrentFolderId] = useState<string | null>(
    media_item.folder_id ?? null,
  );
  const previousFolderIdRef = useRef<string | null>(currentFolderId);

  // Toast feedback state. The tone only swaps the glyph and its colour: one
  // surface carries both the collection confirmations and a failed source open,
  // instead of a second banner for errors.
  const [toast, setToast] = useState<{
    message: string;
    tone: "success" | "error";
  } | null>(null);
  const toastOpacity = useRef(new Animated.Value(0)).current;
  const toastTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const showToast = useCallback(
    (message: string, tone: "success" | "error" = "success") => {
      setToast({ message, tone });
      Animated.timing(toastOpacity, {
        toValue: 1,
        duration: 200,
        useNativeDriver: true,
      }).start();
      if (toastTimeoutRef.current) clearTimeout(toastTimeoutRef.current);
      toastTimeoutRef.current = setTimeout(() => {
        Animated.timing(toastOpacity, {
          toValue: 0,
          duration: 300,
          useNativeDriver: true,
        }).start(() => setToast(null));
      }, 2500);
    },
    [toastOpacity],
  );

  // Refresh collection state when returning from the collection picker
  useFocusEffect(
    useCallback(() => {
      if (!token) return;

      const refreshCollection = async () => {
        try {
          const response = await MediaService.getMediaStatus(
            token,
            media_item.media_item_id,
          );
          const newFolderId = response.media_item.folder_id ?? null;
          setCurrentFolderId(newFolderId);

          // Show toast if collection changed
          if (newFolderId !== previousFolderIdRef.current) {
            if (newFolderId) {
              // Fetch collection name for the toast
              try {
                const collections =
                  await OrganizationService.getUserCollections(token);
                const found = collections.find((c) => c.id === newFolderId);
                showToast(
                  found
                    ? `Moved to "${found.name}"`
                    : "Moved to collection",
                );
              } catch {
                showToast("Moved to collection");
              }
            } else {
              showToast("Removed from collection");
            }
            previousFolderIdRef.current = newFolderId;
          }
        } catch {
          // Silent fail: the main view already has data
        }
      };

      void refreshCollection();
    }, [token, media_item.media_item_id, showToast]),
  );

  // Cleanup toast timeout on unmount
  useEffect(() => {
    return () => {
      if (toastTimeoutRef.current) clearTimeout(toastTimeoutRef.current);
    };
  }, []);

  const handleCollectionPress = useCallback(() => {
    const params = new URLSearchParams();
    params.set("mode", "move");
    params.set("mediaItemId", media_item.media_item_id);
    if (currentFolderId) {
      params.set("currentCollectionId", currentFolderId);
    }
    router.push(`/media/collection?${params.toString()}`);
  }, [router, media_item.media_item_id, currentFolderId]);

  const [activeTab, setActiveTab] = useState<MediaDetailTabKey>("reader");
  // Artifacts are a per-scope history now, so the media detail response carries
  // no artifact projection: this screen reads the history and keeps the newest
  // entry per type for its tiles. Rendering the history itself is task-273.
  const [artifactStates, setArtifactStates] = useState<
    Record<ArtifactType, ArtifactTileState>
  >(buildInitialArtifactStates);

  const mountedRef = useRef(true);
  const artifactPollRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const artifactRetryTimeoutsRef = useRef<
    Partial<Record<ArtifactType, ReturnType<typeof setTimeout>>>
  >({});
  const artifactRetryAttemptsRef = useRef<
    Partial<Record<ArtifactType, number>>
  >({});
  const handleGenerateRef = useRef<
    (artifactType: ArtifactType) => Promise<void>
  >(async () => undefined);
  const [rawContent, setRawContent] = useState<TranscriptContentState>({
    status: "idle",
  });

  useEffect(() => {
    const artifactRetryTimeouts = artifactRetryTimeoutsRef.current;
    return () => {
      mountedRef.current = false;
      if (artifactPollRef.current) {
        clearInterval(artifactPollRef.current);
      }
      for (const timeout of Object.values(artifactRetryTimeouts)) {
        if (timeout) clearTimeout(timeout);
      }
    };
  }, []);

  // One request per scope serves both the history and the in-flight progress, so
  // there is never a request per artifact type. The list comes back newest-first,
  // hence the first entry seen for a type is the one the tile shows.
  const refreshArtifactStates = useCallback(async (): Promise<
    Record<ArtifactType, ArtifactTileState>
  > => {
    const next = buildInitialArtifactStates();
    if (!token) return next;

    const response = await ArtifactService.listArtifacts(
      token,
      "media",
      media_item.media_item_id,
    );
    const seen = new Set<ArtifactType>();
    for (const artifact of response.artifacts) {
      const bucket = bucketArtifactType(artifact.artifact_type);
      if (seen.has(bucket)) continue;
      seen.add(bucket);
      next[bucket] = {
        status: artifact.status,
        artifactId: artifact.artifact_id,
      };
    }
    return next;
  }, [token, media_item.media_item_id]);

  useEffect(() => {
    let cancelled = false;
    void (async () => {
      try {
        const states = await refreshArtifactStates();
        if (!cancelled && mountedRef.current) setArtifactStates(states);
      } catch {
        // Non-fatal: the tiles stay in their idle state and a generation still works.
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [refreshArtifactStates]);

  const startArtifactPolling = useCallback(() => {
    if (artifactPollRef.current) return;

    artifactPollRef.current = setInterval(async () => {
      if (!token || !mountedRef.current) return;

      try {
        const newStates = await refreshArtifactStates();
        if (!mountedRef.current) return;
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
  }, [token, refreshArtifactStates]);

  const handleGenerate = useCallback(
    async (artifactType: ArtifactType) => {
      if (!token || !mountedRef.current) return;

      const pendingRetry = artifactRetryTimeoutsRef.current[artifactType];
      if (pendingRetry) {
        clearTimeout(pendingRetry);
        delete artifactRetryTimeoutsRef.current[artifactType];
      }

      setArtifactStates((prev) => ({
        ...prev,
        [artifactType]: { status: "queued" },
      }));

      try {
        const result = await ArtifactService.generateArtifact(
          token,
          "media",
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
        delete artifactRetryAttemptsRef.current[artifactType];

        startArtifactPolling();
      } catch (err) {
        if (!mountedRef.current) return;

        // Handle 409 CONFLICT: translation is in-flight. No artifact record
        // exists yet, so retry the POST at the normal polling cadence. Once
        // accepted, regular artifact-status polling takes over.
        const httpStatus = (err as { status?: number } | undefined)?.status;
        if (httpStatus === 409) {
          const attempt =
            (artifactRetryAttemptsRef.current[artifactType] ?? 0) + 1;
          artifactRetryAttemptsRef.current[artifactType] = attempt;
          if (attempt >= ARTIFACT_TRANSLATION_RETRY_MAX_ATTEMPTS) {
            delete artifactRetryAttemptsRef.current[artifactType];
            setArtifactStates((prev) => ({
              ...prev,
              [artifactType]: {
                status: "failed",
                error: "Translation is taking longer than expected. Please try again.",
              },
            }));
            return;
          }

          setArtifactStates((prev) => ({
            ...prev,
            [artifactType]: { status: "queued" },
          }));
          if (!artifactRetryTimeoutsRef.current[artifactType]) {
            artifactRetryTimeoutsRef.current[artifactType] = setTimeout(() => {
              delete artifactRetryTimeoutsRef.current[artifactType];
              if (mountedRef.current) {
                void handleGenerateRef.current(artifactType);
              }
            }, ARTIFACT_POLL_INTERVAL_MS);
          }
          return;
        }

        delete artifactRetryAttemptsRef.current[artifactType];
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
  handleGenerateRef.current = handleGenerate;

  // The title is whatever the library row holds, exactly like the inbox
  // vignette -- and nothing more: since task-266 the backend always stores a
  // readable, non-empty title, so the URL-then-"Untitled" chain that used to be
  // here is gone from every screen.
  const displayTitle = media_item.title;

  const displayDomain = (() => {
    try {
      return new URL(media_item.original_url).hostname.replace(/^www\./, "");
    } catch {
      return media_item.source_platform;
    }
  })();

  // The way back to the thing itself. `null` for anything we cannot open, in
  // which case the chip below renders with no press behaviour and no glyph.
  const sourceLink = useMemo(
    () => resolveSourceLink(media_item.original_url),
    [media_item.original_url],
  );

  const handleOpenSource = useCallback(async () => {
    if (!sourceLink) return;
    try {
      await Linking.openURL(sourceLink.url);
    } catch {
      // No handler, or the OS refused: say so instead of letting the rejection
      // bubble out of the press handler.
      showToast(`Couldn't open ${sourceLink.host}`, "error");
    }
  }, [sourceLink, showToast]);

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
      const translationStatus = response.translation?.translation_status;

      if (!trimmed) {
        setRawContent({ status: "not_available" });
        return;
      }

      // If translation failed terminally, stop polling and show failure badge
      if (translationStatus === "failed") {
        setRawContent({ status: "translation_failed", content: trimmed });
        return;
      }

      if (isPending && translationPollCountRef.current < TRANSLATION_POLL_MAX_ATTEMPTS) {
        // Translation still in progress (queued/in_progress), show content and keep polling
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

      const translationStatus = response.translation?.translation_status;

      // If translation failed terminally, show content with failure badge (no polling)
      if (translationStatus === "failed") {
        setRawContent({ status: "translation_failed", content: trimmed });
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
      <Header
        onBack={onBack}
        collectionId={currentFolderId}
        onCollectionPress={handleCollectionPress}
      />

      {/* Toast feedback */}
      {toast && (
        <Animated.View style={[styles.toast, { opacity: toastOpacity }]}>
          <Ionicons
            name={toast.tone === "error" ? "alert-circle" : "checkmark-circle"}
            size={16}
            color={toast.tone === "error" ? Colors.error : Colors.primary}
          />
          <Text style={styles.toastText}>{toast.message}</Text>
        </Animated.View>
      )}

      <ScrollView
        style={styles.scrollView}
        contentContainerStyle={styles.scrollContent}
        showsVerticalScrollIndicator={false}
        // The tab bar is child index 1: it stays pinned while a long transcript
        // scrolls under it, so switching to AI never requires scrolling back up.
        stickyHeaderIndices={[1]}
      >
        {/* Hero Title & Metadata */}
        <View style={styles.heroSection}>
          <Text style={styles.heroTitle}>{displayTitle}</Text>
          <View style={styles.metaRow}>
            <SourceChip
              icon={getMediaTypeIcon(media_item.media_type)}
              label={displayDomain.toUpperCase()}
              link={sourceLink}
              onPress={handleOpenSource}
            />
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

        {/* Intra-screen tabs. Pinned by `stickyHeaderIndices` above, hence the
            opaque background: the content scrolls underneath it. */}
        <View style={styles.tabsBar}>
          <ScreenTabs
            tabs={MEDIA_DETAIL_TABS}
            activeKey={activeTab}
            onChange={setActiveTab}
            accessibilityLabel="Media sections"
          />
        </View>

        {/* Tab content. Artifact polling and the transcript fetch both live in
            this component, so neither stops when its tab is hidden. */}
        <View style={styles.tabContent}>
          {activeTab === "reader" ? (
            <TranscriptReader
              transcript={media_item.transcript}
              processingStatus={processing_job.status}
              content={rawContent}
              onRetry={fetchRawContent}
            />
          ) : (
            <View>
              <Text style={styles.sectionTitle}>Generate</Text>
              <View style={styles.artifactsList}>
                {ARTIFACT_TILES.map((artifact) => (
                  <ArtifactTile
                    key={artifact.type}
                    label={artifact.label}
                    icon={artifact.icon}
                    state={artifactStates[artifact.type]}
                    onGenerate={() => handleGenerate(artifact.type)}
                    onView={(artifactId) =>
                      router.push(`/artifacts/${artifactId}`)
                    }
                    sourceReady={mediaReady}
                  />
                ))}
              </View>
            </View>
          )}
        </View>
      </ScrollView>
    </SafeAreaView>
  );
}

// --- Sub-components ---

function Header({
  onBack,
  collectionId,
  onCollectionPress,
}: {
  onBack: () => void;
  collectionId?: string | null;
  onCollectionPress?: () => void;
}) {
  const hasCollection = !!collectionId;

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
      <View style={styles.headerRightGroup}>
        {onCollectionPress && (
          <Pressable
            style={styles.headerButton}
            onPress={onCollectionPress}
            accessibilityLabel="Move to collection"
            accessibilityRole="button"
            hitSlop={{ top: 4, bottom: 4, left: 4, right: 4 }}
          >
            <Ionicons
              name={hasCollection ? "folder" : "folder-outline"}
              size={24}
              color={hasCollection ? Colors.primary : Colors.textMain}
            />
          </Pressable>
        )}
        <Pressable
          style={styles.headerButton}
          accessibilityLabel="Share"
          accessibilityRole="button"
          hitSlop={{ top: 4, bottom: 4, left: 4, right: 4 }}
        >
          <Ionicons name="share-outline" size={24} color={Colors.textMain} />
        </Pressable>
      </View>
    </View>
  );
}

/**
 * The domain chip under the hero title, and the way back to the original source.
 *
 * When the item has an openable https URL the chip *is* the tap target: it
 * already names the platform and sits under the title, so it only needs the
 * external-link glyph to read as openable — cheaper than a second control
 * competing with the artifacts card. When there is nothing to open it stays a
 * plain label: no glyph, no press, no disabled state.
 */
function SourceChip({
  icon,
  label,
  link,
  onPress,
}: {
  icon: React.ComponentProps<typeof Ionicons>["name"];
  label: string;
  link: SourceLink | null;
  onPress: () => void;
}) {
  const body = (
    <>
      <Ionicons name={icon} size={14} color={Colors.textMain} />
      <Text style={styles.metaChipText}>{label}</Text>
      {link ? (
        <Ionicons name="open-outline" size={14} color={Colors.textMain} />
      ) : null}
    </>
  );

  if (!link) {
    return <View style={styles.metaChip}>{body}</View>;
  }

  return (
    <Pressable
      style={({ pressed }) => [
        styles.metaChip,
        pressed && styles.metaChipPressed,
      ]}
      onPress={onPress}
      accessibilityRole="link"
      accessibilityLabel={`Open on ${link.host}`}
      // The chip is ~25px tall by design; the slop takes the actual touch area
      // past the 48px floor without inflating the pill, same trick as the
      // header buttons.
      hitSlop={{ top: 14, bottom: 14, left: 8, right: 8 }}
    >
      {body}
    </Pressable>
  );
}

// --- Helpers ---

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
  headerRightGroup: {
    flexDirection: "row",
    alignItems: "center",
    gap: Spacing.xs,
  },

  // Toast feedback
  toast: {
    flexDirection: "row",
    alignItems: "center",
    gap: Spacing.sm,
    alignSelf: "center",
    backgroundColor: Colors.surfaceContainer,
    paddingHorizontal: Spacing.md,
    paddingVertical: Spacing.sm,
    borderRadius: BorderRadius.full,
    marginBottom: Spacing.sm,
  },
  toastText: {
    fontSize: Typography.small.fontSize,
    fontWeight: Typography.label.fontWeight,
    color: Colors.textMain,
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
  metaChipPressed: {
    backgroundColor: Colors.surfaceContainerHigh,
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

  // Intra-screen tabs. The bar carries the page background because it is a
  // sticky header: content scrolls underneath it.
  tabsBar: {
    backgroundColor: Colors.background,
    paddingBottom: Spacing.md,
  },
  tabContent: {
    marginTop: Spacing.sm,
  },
  sectionTitle: {
    fontSize: Typography.headline.fontSize,
    fontWeight: Typography.headline.fontWeight,
    color: Colors.textMain,
    marginBottom: Spacing.md,
  },
  // A stack of self-contained tiles: the gap between them does the sectioning,
  // so there is no rule and no container frame ("No-Line rule").
  artifactsList: {
    gap: Spacing.sm,
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
