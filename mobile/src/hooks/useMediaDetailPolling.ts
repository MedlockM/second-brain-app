import { useState, useEffect, useRef, useCallback } from "react";
import { useAuth } from "../contexts/AuthContext";
import { MediaService } from "../services/mediaService";
import { getFriendlyErrorMessage } from "../lib/getFriendlyErrorMessage";
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
      return "Transcribing audio...";
    case "youtube":
      return "Transcribing video...";
    case "instagram":
    case "tiktok":
    case "x":
      return "Extracting content...";
    default:
      return "Generating text...";
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
  const { token } = useAuth();

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
  const startTimeRef = useRef<number>(Date.now());

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
            "Processing failed. Please try again later.",
        );
        stopPolling();
      } else {
        setState("processing");
      }
    },
    [stopPolling],
  );

  const fetchMediaStatus = useCallback(async () => {
    if (!token || !mediaId) return;

    try {
      const response = await MediaService.getMediaStatus(token, mediaId);
      if (!mountedRef.current) return;
      setFetchError(null);
      handleResponse(response);
    } catch (err) {
      if (!mountedRef.current) return;
      setFetchError(getFriendlyErrorMessage(err));
      setState("error");
      stopPolling();
    }
  }, [token, mediaId, handleResponse, stopPolling]);

  const startPolling = useCallback(() => {
    if (pollTimerRef.current) return; // Already polling

    pollTimerRef.current = setInterval(async () => {
      if (!token || !mediaId || !mountedRef.current) return;

      // Check timeout before making the request
      const elapsed = Date.now() - startTimeRef.current;
      if (elapsed >= TIMEOUT_MS) {
        setTimedOut(true);
        setState("timeout");
        stopPolling();
        return;
      }

      try {
        const response = await MediaService.getMediaStatus(token, mediaId);
        if (!mountedRef.current) return;
        handleResponse(response);
      } catch {
        // Silent fail during polling - don't disrupt the user
      }
    }, POLL_INTERVAL_MS);

    // Set a hard timeout to stop polling after 5 minutes
    if (!timeoutTimerRef.current) {
      const remainingMs = TIMEOUT_MS - (Date.now() - startTimeRef.current);
      timeoutTimerRef.current = setTimeout(() => {
        if (!mountedRef.current) return;
        setTimedOut(true);
        setState("timeout");
        stopPolling();
      }, Math.max(0, remainingMs));
    }
  }, [token, mediaId, handleResponse, stopPolling]);

  // Initial fetch and polling setup
  useEffect(() => {
    mountedRef.current = true;
    startTimeRef.current = Date.now();

    if (token && mediaId) {
      setState("loading");
      fetchMediaStatus().then(() => {
        // After initial fetch, start polling if still in processing state
        if (mountedRef.current) {
          // We read the latest state via a micro-delay to let setState flush
          // Instead, check state directly from the response in handleResponse
        }
      });
    }

    return () => {
      mountedRef.current = false;
      stopPolling();
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token, mediaId]);

  // Start or stop polling when state changes
  useEffect(() => {
    if (state === "processing") {
      startPolling();
    } else {
      stopPolling();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [state]);

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
