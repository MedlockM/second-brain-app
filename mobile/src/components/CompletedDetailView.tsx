/**
 * A media item that has finished processing, as a page.
 *
 * The hero title and its metadata, then two intra-screen tabs: the transcript
 * ("Reader") and artifact generation ("AI"). Everything it shows comes from the
 * `mediaData` prop — it reads no route parameter and holds no polling of its
 * own, so the same component renders the `/media/[id]` route and a card of the
 * Digest pager. That is the point of it living here rather than in the route:
 * a change to the media page lands in both by construction.
 *
 * The route keeps what belongs to a route: the fetch, and the loading,
 * processing, timeout and failure states of the item on its way here.
 *
 * `useRouter()` stays — the folder picker and an artifact are pushed the
 * same way from a route as from a pager. What does not stay is any read of the
 * URL segment.
 */

import React, {
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";
import {
  Animated,
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  View,
} from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";
import { useFocusEffect, useRouter } from "expo-router";
import { Ionicons } from "@expo/vector-icons";
import * as Linking from "expo-linking";
import { useAuth } from "../contexts/AuthContext";
import { MediaService } from "../services/mediaService";
import { ArtifactService } from "../services/artifactService";
import type { ArtifactSummary } from "../types/artifacts";
import { OrganizationService } from "../services/organizationService";
import { getFriendlyErrorMessage } from "../lib/getFriendlyErrorMessage";
import { formatDuration } from "../lib/formatDuration";
import type { ArtifactTileState } from "./ArtifactTile";
import { ArtifactsPanel } from "./ArtifactsPanel";
import { ScreenTabs, type ScreenTab } from "./ScreenTabs";
import { HeaderMenuGlyph } from "./ScreenHeader";
import { AnchoredContextMenu } from "./AnchoredContextMenu";
import { MediaDetailHeader } from "./MediaDetailHeader";
import { RenameDialog } from "./RenameDialog";
import { useMediaActions } from "../hooks/useMediaActions";
import {
  TranscriptReader,
  type TranscriptContentState,
} from "./TranscriptReader";
import {
  SourcePreview,
  resolveSourcePreviewState,
  type SourcePreviewState,
} from "./SourcePreview";
import {
  Colors,
  Typography,
  Spacing,
  BorderRadius,
} from "../constants/theme";
import { formatDate, t } from "../i18n";
import type {
  MediaStatusResponse,
  MediaItemContract,
  ArtifactType,
} from "../types/media";
import { getMediaTypeIcon } from "../lib/mediaTypeDisplay";
import { describeArtifactRefusal } from "../lib/artifactRefusal";
import { mergeArtifactIntoHistory } from "../lib/artifactHistory";

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
    summary: { status: "idle", generationAvailable: true },
    summary_short: { status: "idle", generationAvailable: true },
    summary_detailed: { status: "idle", generationAvailable: true },
    notes: { status: "idle", generationAvailable: true },
    flashcards: { status: "idle", generationAvailable: true },
    quiz: { status: "idle", generationAvailable: true },
  };
}

const ARTIFACT_POLL_INTERVAL_MS = 3000;

/** Delay between polls when translation is pending (ms). */
const TRANSLATION_POLL_DELAY_MS = 3000;
/** Maximum number of translation polls before giving up. */
const TRANSLATION_POLL_MAX_ATTEMPTS = 20;

/** Delay between polls while the source preview is still being generated (ms). */
const PREVIEW_POLL_DELAY_MS = 3000;
/**
 * Maximum number of preview polls, i.e. one minute of waiting.
 *
 * The generation runs off the completion event and takes seconds, so a preview
 * that has not landed by then is not going to land while the screen is open. The
 * section then stays on its waiting line: the next visit re-reads the item, and
 * a generation that was lost outright comes back as `failed` from the API rather
 * than being guessed at here.
 */
const PREVIEW_POLL_MAX_ATTEMPTS = 20;

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

export interface CompletedDetailViewProps {
  mediaData: MediaStatusResponse;
  /**
   * Leave the item. The header's back arrow, and where a deletion goes once
   * there is nothing left to show.
   */
  onBack: () => void;
  /**
   * Whether the page carries its own top chrome — the safe area and the title
   * bar. On by default, which is the route: it mounts this straight under the
   * status bar. A pager turns it off, since it owns the top inset and shows one
   * header above every card rather than one per card.
   */
  showChrome?: boolean;
}

export function CompletedDetailView({
  mediaData,
  onBack,
  showChrome = true,
}: CompletedDetailViewProps): React.JSX.Element {
  const { isAuthenticated } = useAuth();
  const router = useRouter();
  const { media_item, processing_job } = mediaData;

  // --- Folder state ---
  const [currentFolderId, setCurrentFolderId] = useState<string | null>(
    media_item.folder_id ?? null,
  );
  const previousFolderIdRef = useRef<string | null>(currentFolderId);

  // Toast feedback state. The tone only swaps the glyph and its colour: one
  // surface carries both the folder confirmations and a failed source open,
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

  // Refresh folder state when returning from the folder picker
  useFocusEffect(
    useCallback(() => {
      if (!isAuthenticated) return;

      const refreshFolder = async () => {
        try {
          const response = await MediaService.getMediaStatus(
            media_item.media_item_id,
          );
          const newFolderId = response.media_item.folder_id ?? null;
          setCurrentFolderId(newFolderId);

          // Show toast if folder changed
          if (newFolderId !== previousFolderIdRef.current) {
            if (newFolderId) {
              // Fetch folder name for the toast
              try {
                const folders =
                  await OrganizationService.getUserFolders();
                const found = folders.find((c) => c.id === newFolderId);
                showToast(
                  found
                    ? t("media.movedToNamed", { name: found.name })
                    : t("media.movedToFolder"),
                );
              } catch {
                showToast(t("media.movedToFolder"));
              }
            } else {
              showToast(t("media.removedFromFolder"));
            }
            previousFolderIdRef.current = newFolderId;
          }
        } catch {
          // Silent fail: the main view already has data
        }
      };

      void refreshFolder();
    }, [isAuthenticated, media_item.media_item_id, showToast]),
  );

  // Cleanup toast timeout on unmount
  useEffect(() => {
    return () => {
      if (toastTimeoutRef.current) clearTimeout(toastTimeoutRef.current);
    };
  }, []);

  const handleFolderPress = useCallback(() => {
    const params = new URLSearchParams();
    params.set("mode", "move");
    params.set("mediaItemId", media_item.media_item_id);
    if (currentFolderId) {
      params.set("currentFolderId", currentFolderId);
    }
    router.push(`/media/folder?${params.toString()}`);
  }, [router, media_item.media_item_id, currentFolderId]);

  // The title as this screen shows it: whatever the library row holds, and
  // nothing more — since task-266 the backend always stores a readable, non-empty
  // title, so the URL-then-"Untitled" chain that used to be here is gone from
  // every screen. A rename patches it in place: this screen holds no list to
  // reload, so the new name has to land on the hero directly.
  const [renamedTitle, setRenamedTitle] = useState<string | null>(null);
  const displayTitle = renamedTitle ?? media_item.title;

  // The header `…`, and what it offers: the rename and the delete a long press
  // already offers in Library, reachable from the item itself. No "Move" row —
  // the folder button one slot to its left opens that very picker.
  const mediaActions = useMediaActions<MediaItemContract>({
    canMove: false,
    // Nothing left to show once the deletion is confirmed, so the screen leaves.
    // The list it was opened from refetches on focus and comes back without it.
    onDeleted: onBack,
    onRenamed: (_mediaItemId, title) => setRenamedTitle(title),
  });

  // What the menu acts on, carrying the title currently on screen: a second
  // rename has to start from the name the first one stored.
  const menuTarget = useMemo<MediaItemContract>(
    () => ({ ...media_item, title: displayTitle }),
    [media_item, displayTitle],
  );

  // The copy of the pressed control the menu lifts above its blur. A header
  // button has no row to redraw, so it redraws itself: the `…` stays sharp and
  // the card visibly hangs from it.
  const renderActionsPreview = useCallback(() => <HeaderMenuGlyph />, []);

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
          fallback: t("folder.artifactsLoadFailed"),
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
        // A media item's sources never change, so one entry closes the type for
        // good (task-322): asking again would answer this very artifact. Only a
        // failure leaves the door open — it holds nothing to read, and the
        // backend reruns it under the same id.
        generationAvailable: artifact.status === "failed",
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
      states[type] = { status: "queued", generationAvailable: false };
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
        // A refusal is typed and carries its reason (a quota reached, a
        // translation the provider refused for good). Showing it beats the
        // silent retry loop that used to hide it behind a spinner. An unfinished
        // preparation is not among them any more: the backend accepts the
        // request and holds the entry until the text lands (task-360).
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

  // --- Source preview ("Aperçu"), above the full text ---

  // Seeded from the item this screen was opened with, then owned here: the
  // detail poll stops the moment processing completes, and the preview is
  // generated *after* that — so nothing else would ever bring it in.
  const [preview, setPreview] = useState<SourcePreviewState>(() =>
    resolveSourcePreviewState(media_item),
  );

  const previewPollRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const previewPollCountRef = useRef(0);
  // Same indirection as the translation poll: the callback reschedules itself,
  // and a ref keeps it from referencing its own binding before it exists.
  const pollForPreviewRef = useRef<() => Promise<void>>(async () => undefined);

  const pollForPreview = useCallback(async () => {
    if (!isAuthenticated || !mountedRef.current) return;
    previewPollCountRef.current += 1;

    try {
      const response = await MediaService.getMediaStatus(
        media_item.media_item_id,
      );
      if (!mountedRef.current) return;
      const next = resolveSourcePreviewState(response.media_item);
      setPreview(next);
      // Resolved, either way: nothing left to wait for.
      if (next.status !== "pending") return;
    } catch {
      // Silent: a failed read is not news the reader needs, and the attempt
      // still counts against the ceiling so a broken network cannot loop.
      if (!mountedRef.current) return;
    }

    if (previewPollCountRef.current < PREVIEW_POLL_MAX_ATTEMPTS) {
      previewPollRef.current = setTimeout(() => {
        void pollForPreviewRef.current();
      }, PREVIEW_POLL_DELAY_MS);
    }
  }, [isAuthenticated, media_item.media_item_id]);

  useEffect(() => {
    pollForPreviewRef.current = pollForPreview;
  }, [pollForPreview]);

  // Armed once, from the waiting state itself, and stopped by the cleanup —
  // whether the preview resolved or the screen went away. No interval: the chain
  // is a bounded series of timeouts that ends on its own.
  useEffect(() => {
    if (preview.status !== "pending") return undefined;
    previewPollRef.current = setTimeout(() => {
      void pollForPreviewRef.current();
    }, PREVIEW_POLL_DELAY_MS);
    return () => {
      if (previewPollRef.current) {
        clearTimeout(previewPollRef.current);
        previewPollRef.current = null;
      }
    };
  }, [preview.status]);

  return (
    <DetailContainer showChrome={showChrome}>
      {showChrome ? (
        <MediaDetailHeader
          onBack={onBack}
          folderId={currentFolderId}
          onFolderPress={handleFolderPress}
          onActionsPress={(anchor) => mediaActions.open(menuTarget, anchor)}
        />
      ) : null}

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
        // One axis per drag, which is what makes this page swipeable when the
        // Digest nests it in a horizontal pager: a drag that starts sideways is
        // not half-absorbed here as a diagonal scroll before the pager takes it.
        // Never a constraint on the route, where this is the only scrollable and
        // there is nothing horizontal to lock out.
        directionalLockEnabled
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
            shares with the folder screen. */}
        {activeTab === "reader" ? (
          <View style={styles.readerContent}>
            {/* What this source is about, before the source itself. */}
            <SourcePreview state={preview} />
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

      {/* Screen level, outside the scroll view: both are modals belonging to the
          screen's state, and the menu's backdrop covers the whole page. */}
      <AnchoredContextMenu
        {...mediaActions.menuProps}
        renderPreview={renderActionsPreview}
      />
      <RenameDialog {...mediaActions.renameProps} />
    </DetailContainer>
  );
}

// --- Sub-components ---

/**
 * The page's outer box.
 *
 * With the chrome on it is a `SafeAreaView` claiming the top inset, which is
 * what the route needs: nothing sits between the status bar and this page.
 * Without it the host already owns that inset, so the box is a plain `View` — a
 * second safe area nested inside one would push the content down twice.
 */
function DetailContainer({
  showChrome,
  children,
}: {
  showChrome: boolean;
  children: React.ReactNode;
}): React.JSX.Element {
  if (!showChrome) {
    return <View style={styles.container}>{children}</View>;
  }
  return (
    <SafeAreaView style={styles.container} edges={["top"]}>
      {children}
    </SafeAreaView>
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

// --- Styles ---

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: Colors.background,
  },
  scrollView: {
    flex: 1,
  },
  // No gutter and no bottom inset here: each block below owns the page gutter,
  // because the AI tab is a shared component that carries its own.
  scrollContent: {
    paddingTop: Spacing.md,
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
});
