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
import type { ArtifactSummary } from "../../src/types/artifacts";
import { OrganizationService } from "../../src/services/organizationService";
import { getFriendlyErrorMessage } from "../../src/lib/getFriendlyErrorMessage";
import { formatDuration } from "../../src/lib/formatDuration";
import { useMediaDetailPolling } from "../../src/hooks/useMediaDetailPolling";
import type { ArtifactTileState } from "../../src/components/ArtifactTile";
import { ArtifactsPanel } from "../../src/components/ArtifactsPanel";
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
import { formatDate, t, useTranslation } from "../../src/i18n";
import type {
  MediaStatusResponse,
  ArtifactType,
} from "../../src/types/media";
import { getMediaTypeIcon } from "../../src/lib/mediaTypeDisplay";
import { describeArtifactRefusal } from "../../src/lib/artifactRefusal";
import { mergeArtifactIntoHistory } from "../../src/lib/artifactHistory";

/**
 * The two intra-screen tabs of a media item: what it says, and what the models
 * can make of it. Reader is the default — the content comes first, generating
 * something out of it is a deliberate second step.
 */
type MediaDetailTabKey = "reader" | "ai";

const MEDIA_DETAIL_TABS: readonly ScreenTab<MediaDetailTabKey>[] = [
  { key: "reader", labelKey: "media.tab.reader", icon: "book-outline" },
  { key: "ai", labelKey: "media.tab.ai", icon: "sparkles-outline" },
];

/**
 * Some legacy items still carry the unscoped "summary" type from before the
 * short/detailed split. Surface them under the "Summary" tile instead of
 * dropping them on the floor.
 */
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
  // Copy resolved on render: redraw when the interface language changes.
  useTranslation();
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
            {fetchError || t("media.loadFailed")}
          </Text>
          <Pressable
            style={styles.retryButton}
            onPress={refresh}
            accessibilityLabel={t("media.retryA11y")}
            accessibilityRole="button"
          >
            <Text style={styles.retryButtonText}>{t("common.retry")}</Text>
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
            {t("media.processingHint")}
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
          <Text style={styles.timeoutTitle}>{t("media.timeoutTitle")}</Text>
          <Text style={styles.timeoutSubtitle}>{t("media.timeoutHint")}</Text>
          <Pressable
            style={styles.refreshButton}
            onPress={refresh}
            accessibilityLabel={t("media.refreshA11y")}
            accessibilityRole="button"
          >
            <Ionicons name="refresh" size={18} color={Colors.onPrimary} />
            <Text style={styles.refreshButtonText}>{t("media.refresh")}</Text>
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
          <Text style={styles.failedTitle}>{t("media.failedTitle")}</Text>
          <Text style={styles.failedMessage}>
            {processingError || t("media.failedFallback")}
          </Text>
          <Pressable
            style={styles.refreshButton}
            onPress={refresh}
            accessibilityLabel={t("media.refreshA11y")}
            accessibilityRole="button"
          >
            <Ionicons name="refresh" size={18} color={Colors.onPrimary} />
            <Text style={styles.refreshButtonText}>{t("media.refresh")}</Text>
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
          <Text style={styles.errorText}>{t("media.loadFailed")}</Text>
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
  const { isAuthenticated } = useAuth();
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
  // Not a ref: an Animated.Value is created once and read during render, which
  // is exactly `useMemo` and not `useRef().current`.
  const toastOpacity = useMemo(() => new Animated.Value(0), []);
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
      if (!isAuthenticated) return;

      const refreshCollection = async () => {
        try {
          const response = await MediaService.getMediaStatus(
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
                  await OrganizationService.getUserCollections();
                const found = collections.find((c) => c.id === newFolderId);
                showToast(
                  found
                    ? t("media.movedToNamed", { name: found.name })
                    : t("media.movedToCollection"),
                );
              } catch {
                showToast(t("media.movedToCollection"));
              }
            } else {
              showToast(t("media.removedFromCollection"));
            }
            previousFolderIdRef.current = newFolderId;
          }
        } catch {
          // Silent fail: the main view already has data
        }
      };

      void refreshCollection();
    }, [isAuthenticated, media_item.media_item_id, showToast]),
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
  // Artifacts are a per-scope append-only history: the media detail response
  // carries no artifact projection any more. This screen holds the history and
  // derives its tiles from it — the newest entry per type — so there is one
  // source of truth behind both the tiles and the list under them.
  const [artifactHistory, setArtifactHistory] = useState<ArtifactSummary[]>([]);
  const [historyLoading, setHistoryLoading] = useState(true);
  const [historyError, setHistoryError] = useState<string | null>(null);
  const [generationRefusal, setGenerationRefusal] = useState<string | null>(null);
  // The types whose POST is in flight. The history cannot know about them yet —
  // the entry only exists once the request answers, and that request reads every
  // source's transcript from S3 before it does. Without this, the tap stays
  // visually unanswered for the whole round-trip and reads as ignored.
  const [requestsInFlight, setRequestsInFlight] = useState<readonly ArtifactType[]>(
    [],
  );

  const mountedRef = useRef(true);
  const artifactPollRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const [rawContent, setRawContent] = useState<TranscriptContentState>({
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

  // One request per scope serves both the history and the in-flight progress, so
  // there is never a request per artifact type. A failure is surfaced rather
  // than swallowed: the panel then offers a Retry instead of claiming the scope
  // has nothing generated.
  const refreshArtifacts = useCallback(async () => {
    if (!isAuthenticated) return;
    try {
      const response = await ArtifactService.listArtifacts(
        "media",
        media_item.media_item_id,
      );
      if (!mountedRef.current) return;
      setArtifactHistory(response.artifacts);
      setHistoryError(null);
    } catch (err) {
      if (!mountedRef.current) return;
      setHistoryError(
        getFriendlyErrorMessage(err, {
          fallback: t("collection.artifactsLoadFailed"),
        }),
      );
    }
  }, [isAuthenticated, media_item.media_item_id]);

  // `historyLoading` starts true and is only ever cleared: the spinner belongs
  // to the first fetch of a given scope, and `refreshArtifacts` is stable for as
  // long as the scope is.
  useEffect(() => {
    let cancelled = false;
    void (async () => {
      await refreshArtifacts();
      if (!cancelled) setHistoryLoading(false);
    })();
    return () => {
      cancelled = true;
    };
  }, [refreshArtifacts]);

  // The list itself says whether anything is in flight, so the poll starts and
  // stops from its own content rather than from a separate flag.
  const hasArtifactInFlight = useMemo(
    () =>
      artifactHistory.some(
        (artifact) =>
          artifact.status === "queued" || artifact.status === "generating",
      ),
    [artifactHistory],
  );

  // The newest entry per type, for the tiles. The list comes back newest-first,
  // so the first entry seen for a type wins.
  const artifactStates = useMemo(() => {
    const states = buildInitialArtifactStates();
    const seen = new Set<ArtifactType>();
    for (const artifact of artifactHistory) {
      const type = artifact.artifact_type;
      if (seen.has(type) || !(type in states)) continue;
      seen.add(type);
      states[type] = {
        status: artifact.status,
        error: artifact.error_code ?? undefined,
      };
    }
    // A request still in flight wins over whatever the history says about that
    // type — a previous `ready` or `failed` entry included, since the button
    // that was just tapped belongs to the newest attempt. `queued` is the state
    // the entry itself comes back with, so the tile shows the spinner from the
    // tap frame and nothing changes visually when the POST answers. It also
    // takes the button out of the tile, which is what stops a second tap from
    // firing a second POST.
    for (const type of requestsInFlight) {
      states[type] = { status: "queued" };
    }
    return states;
  }, [artifactHistory, requestsInFlight]);

  const startArtifactPolling = useCallback(() => {
    if (artifactPollRef.current) return;

    artifactPollRef.current = setInterval(() => {
      void refreshArtifacts();
    }, ARTIFACT_POLL_INTERVAL_MS);
  }, [refreshArtifacts]);

  useEffect(() => {
    if (hasArtifactInFlight) {
      startArtifactPolling();
      return;
    }
    if (artifactPollRef.current) {
      clearInterval(artifactPollRef.current);
      artifactPollRef.current = null;
    }
  }, [hasArtifactInFlight, startArtifactPolling]);

  const handleGenerate = useCallback(
    async (artifactType: ArtifactType) => {
      if (!isAuthenticated || !mountedRef.current) return;
      setGenerationRefusal(null);
      // Before the POST, with nothing awaited in between: this is the update
      // that flips the tile, and it must land on the frame the finger lifts.
      setRequestsInFlight((current) =>
        current.includes(artifactType) ? current : [...current, artifactType],
      );

      try {
        const created = await ArtifactService.generateArtifact(
          "media",
          media_item.media_item_id,
          artifactType,
        );
        if (!mountedRef.current) return;
        // The POST answers the entry itself, so it goes straight into the
        // history: no list call, hence no eventually-consistent GSI read that
        // could come back without it and hide a running generation. It also
        // arms the poll immediately, from the returned status.
        setArtifactHistory((current) =>
          mergeArtifactIntoHistory(current, created),
        );
      } catch (err) {
        if (!mountedRef.current) return;
        // A refusal is typed and carries its reason (a transcript still being
        // prepared, a quota reached). Showing it beats the silent retry loop
        // that used to hide it behind a spinner.
        setGenerationRefusal(describeArtifactRefusal(err, { scope: "media" }));
      } finally {
        // Both paths: the merged entry carries a real status from here, and a
        // refusal has to give the button back — keeping the type in the set
        // would lock the tile on a spinner nothing will ever clear.
        if (mountedRef.current) {
          setRequestsInFlight((current) =>
            current.filter((type) => type !== artifactType),
          );
        }
      }
    },
    [isAuthenticated, media_item.media_item_id],
  );
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
      showToast(t("media.openFailed", { host: sourceLink.host }), "error");
    }
  }, [sourceLink, showToast]);

  const formattedDate = (() => {
    try {
      // The active UI locale, never a hardcoded language tag.
      return formatDate(new Date(media_item.created_at), {
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

  // The poll reschedules itself; going through a ref keeps the callback from
  // referencing its own binding before it is declared.
  const pollForTranslationRef = useRef<() => Promise<void>>(async () => undefined);

  const pollForTranslation = useCallback(async () => {
    if (!isAuthenticated || !mountedRef.current) return;
    translationPollCountRef.current += 1;

    try {
      const response = await MediaService.getRawContent(
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
          void pollForTranslationRef.current();
        }, TRANSLATION_POLL_DELAY_MS);
      } else {
        // Translation ready (or max polls reached -- show whatever we have)
        setRawContent({ status: "ready", content: trimmed });
      }
    } catch {
      // Silent fail during translation polling -- keep current state
      if (translationPollCountRef.current < TRANSLATION_POLL_MAX_ATTEMPTS) {
        translationPollRef.current = setTimeout(() => {
          void pollForTranslationRef.current();
        }, TRANSLATION_POLL_DELAY_MS);
      }
    }
  }, [isAuthenticated, media_item.media_item_id]);

  useEffect(() => {
    pollForTranslationRef.current = pollForTranslation;
  }, [pollForTranslation]);

  const fetchRawContent = useCallback(async () => {
    if (!isAuthenticated) return;
    setRawContent({ status: "loading" });
    translationPollCountRef.current = 0;

    try {
      const response = await MediaService.getRawContent(
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
          void pollForTranslationRef.current();
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
          fallback: t("media.transcriptLoadFailed"),
        }),
      });
    }
  }, [isAuthenticated, media_item.media_item_id]);

  // Whether the transcript fetch has already been kicked off for the media as it
  // currently stands. A flag rather than a read of `rawContent`: deciding from
  // the state would put the state in the dependencies and re-run the effect on
  // every transition it causes.
  const rawFetchStartedRef = useRef(false);

  useEffect(() => {
    let cancelled = false;
    void (async () => {
      if (!mediaReady) {
        // Reset whenever processing rewinds (e.g. user retries an item).
        rawFetchStartedRef.current = false;
        if (!cancelled) setRawContent({ status: "idle" });
        return;
      }
      if (transcriptStatus === "failed") {
        if (!cancelled) setRawContent({ status: "not_available" });
        return;
      }
      if (rawFetchStartedRef.current) return;
      rawFetchStartedRef.current = true;
      if (!cancelled) setRawContent({ status: "loading" });
      await fetchRawContent();
    })();
    return () => {
      cancelled = true;
    };
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
            accessibilityLabel={t("media.sectionsA11y")}
          />
        </View>

        {/* Tab content. Artifact polling and the transcript fetch both live in
            this component, so neither stops when its tab is hidden. Each branch
            carries the page gutter itself — `ArtifactsPanel` owns the one it
            shares with the collection screen. */}
        {activeTab === "reader" ? (
          <View style={styles.readerContent}>
            <TranscriptReader
              transcript={media_item.transcript}
              processingStatus={processing_job.status}
              content={rawContent}
              onRetry={fetchRawContent}
            />
          </View>
        ) : (
          // No "N sources" line: a media item is a single source.
          <ArtifactsPanel
            tileStates={artifactStates}
            sourceReady={mediaReady}
            onGenerate={(artifactType) => void handleGenerate(artifactType)}
            refusal={generationRefusal}
            refusalTestID="media-ai-refusal"
            history={artifactHistory}
            historyLoading={historyLoading}
            historyError={historyError}
            onRetryHistory={() => void refreshArtifacts()}
            historyEmptyTestID="media-ai-history-empty"
            onOpenArtifact={(artifact) =>
              router.push(`/artifacts/${artifact.artifact_id}`)
            }
            showSourceCount={false}
          />
        )}
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
        accessibilityLabel={t("common.goBack")}
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
            accessibilityLabel={t("media.moveToCollectionA11y")}
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
          accessibilityLabel={t("media.shareA11y")}
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
  // No gutter and no bottom inset here: each block below owns the page gutter,
  // because the AI tab is a shared component that carries its own.
  scrollContent: {
    paddingTop: Spacing.md,
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
    paddingHorizontal: Spacing.lg,
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
    paddingHorizontal: Spacing.lg,
    paddingBottom: Spacing.md,
  },
  // The Reader tab only. The AI tab is `ArtifactsPanel`, which brings the same
  // gutter and the same bottom inset with it.
  readerContent: {
    paddingHorizontal: Spacing.lg,
    paddingTop: Spacing.sm,
    paddingBottom: Spacing.xxl,
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
