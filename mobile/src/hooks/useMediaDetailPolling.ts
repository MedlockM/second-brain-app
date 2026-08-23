import { useState, useEffect, useRef, useCallback } from "react";
import { useAuth } from "../contexts/AuthContext";
import { MediaService } from "../services/mediaService";
import { getFriendlyErrorMessage } from "../lib/getFriendlyErrorMessage";
import { t } from "../i18n";
import type {
  MediaStatusResponse,
  SourcePlatform,
} from "../types/media";

const POLL_INTERVAL_MS = 3000;
const TIMEOUT_MS = 5 * 60 * 1000; // 5 minutes

/**
 * Returns a contextual processing message based on the source platform.
 */
function getProcessingMessage(sourcePlatform?: SourcePlatform): string {
  switch (sourcePlatform) {
    case "spotify":
    case "apple_podcasts":
    case "deezer":
    case "rss":
    case "podcast_index":
      return t("media.processing.audio");
    case "youtube":
      return t("media.processing.video");
    case "instagram":
    case "tiktok":
    case "x":
      return t("media.processing.extracting");
    default:
      return t("media.processing.generating");
  }
}

export type MediaDetailPollingState =
  | "loading"
  | "processing"
  | "completed"
  | "failed"
  | "timeout"
  | "error";

export interface UseMediaDetailPollingResult {
  /** Current state of the polling lifecycle */
  state: MediaDetailPollingState;
  /** The media status response once available */
  mediaData: MediaStatusResponse | null;
  /** User-friendly error message for network/fetch failures */
  fetchError: string | null;
  /** Error message from the backend processing job (when state is 'failed') */
  processingError: string | null;
  /** Contextual processing message (varies by source platform) */
  processingMessage: string;
  /** Whether the 5-minute timeout has been reached */
  timedOut: boolean;
  /** Manual refresh function (e.g., for pull-to-refresh after timeout) */
  refresh: () => Promise<void>;
}

/**
 * Hook that manages polling for a single media item's detail screen.
 *
 * Behavior:
 * - On mount, fetches the media status via GET /api/media/:id
 * - If the processing job is in a non-terminal state, polls every 3s
 * - Stops polling when status becomes terminal (completed/failed/cancelled)
 * - Stops polling after 5 minutes and shows a timeout message
 * - Cleans up on unmount (no leaked intervals)
 */
export function useMediaDetailPolling(
  mediaId: string | undefined,
): UseMediaDetailPollingResult {
  const { isAuthenticated } = useAuth();

  const [mediaData, setMediaData] = useState<MediaStatusResponse | null>(null);
  const [state, setState] = useState<MediaDetailPollingState>("loading");
  const [fetchError, setFetchError] = useState<string | null>(null);
  const [processingError, setProcessingError] = useState<string | null>(null);
  const [processingMessage, setProcessingMessage] =
    useState<string>("Generating text...");
  const [timedOut, setTimedOut] = useState(false);

  const mountedRef = useRef(true);
  const pollTimerRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const timeoutTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const startTimeRef = useRef<number | null>(null);

  const stopPolling = useCallback(() => {
    if (pollTimerRef.current) {
      clearInterval(pollTimerRef.current);
      pollTimerRef.current = null;
    }
    if (timeoutTimerRef.current) {
      clearTimeout(timeoutTimerRef.current);
      timeoutTimerRef.current = null;
    }
  }, []);

  const handleResponse = useCallback(
    (response: MediaStatusResponse) => {
      if (!mountedRef.current) return;

      setMediaData(response);
      setProcessingMessage(
        getProcessingMessage(response.media_item.source_platform),
      );

      const jobStatus = response.processing_job.status;

      if (jobStatus === "completed") {
        setState("completed");
        stopPolling();
      } else if (jobStatus === "failed" || jobStatus === "cancelled") {
        setState("failed");
        setProcessingError(
          response.processing_job.error_message ||
            t("media.processingFailed"),
        );
        stopPolling();
      } else {
        setState("processing");
      }
    },
    [stopPolling],
  );

  const fetchMediaStatus = useCallback(async () => {
    if (!isAuthenticated || !mediaId) return;

    try {
      const response = await MediaService.getMediaStatus(mediaId);
      if (!mountedRef.current) return;
      setFetchError(null);
      handleResponse(response);
    } catch (err) {
      if (!mountedRef.current) return;
      setFetchError(getFriendlyErrorMessage(err));
      setState("error");
      stopPolling();
    }
  }, [isAuthenticated, mediaId, handleResponse, stopPolling]);

  const startPolling = useCallback(() => {
    if (pollTimerRef.current) return; // Already polling
    if (startTimeRef.current === null) {
      startTimeRef.current = Date.now();
    }

    pollTimerRef.current = setInterval(async () => {
      if (!isAuthenticated || !mediaId || !mountedRef.current) return;

      // Check timeout before making the request
      const startedAt = startTimeRef.current ?? Date.now();
      const elapsed = Date.now() - startedAt;
      if (elapsed >= TIMEOUT_MS) {
        setTimedOut(true);
        setState("timeout");
        stopPolling();
        return;
      }

      try {
        const response = await MediaService.getMediaStatus(mediaId);
        if (!mountedRef.current) return;
        handleResponse(response);
      } catch {
        // Silent fail during polling - don't disrupt the user
      }
    }, POLL_INTERVAL_MS);

    // Set a hard timeout to stop polling after 5 minutes
    if (!timeoutTimerRef.current) {
      const startedAt = startTimeRef.current ?? Date.now();
      const remainingMs = TIMEOUT_MS - (Date.now() - startedAt);
      timeoutTimerRef.current = setTimeout(() => {
        if (!mountedRef.current) return;
        setTimedOut(true);
        setState("timeout");
        stopPolling();
      }, Math.max(0, remainingMs));
    }
  }, [isAuthenticated, mediaId, handleResponse, stopPolling]);

  // Initial fetch and polling setup
  useEffect(() => {
    mountedRef.current = true;
    startTimeRef.current = Date.now();

    let initialFetchTimer: ReturnType<typeof setTimeout> | null = null;
    if (isAuthenticated && mediaId) {
      initialFetchTimer = setTimeout(() => void fetchMediaStatus(), 0);
    }

    return () => {
      if (initialFetchTimer) clearTimeout(initialFetchTimer);
      mountedRef.current = false;
      stopPolling();
    };
  }, [isAuthenticated, mediaId, fetchMediaStatus, stopPolling]);

  // Start or stop polling when state changes
  useEffect(() => {
    if (state === "processing") {
      startPolling();
    } else {
      stopPolling();
    }
  }, [state, startPolling, stopPolling]);

  // Manual refresh (e.g., after timeout or pull-to-refresh)
  const refresh = useCallback(async () => {
    setTimedOut(false);
    startTimeRef.current = Date.now(); // Reset timeout
    setState("loading");
    await fetchMediaStatus();
  }, [fetchMediaStatus]);

  return {
    state,
    mediaData,
    fetchError,
    processingError,
    processingMessage,
    timedOut,
    refresh,
  };
}
