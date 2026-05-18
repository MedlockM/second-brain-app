import { useState, useEffect, useRef, useCallback } from "react";
import { AppState, AppStateStatus } from "react-native";
import { useAuth } from "../contexts/AuthContext";
import { useInbox, InboxItem } from "../contexts/InboxContext";
import { MediaService } from "../services/mediaService";
import { getFriendlyErrorMessage } from "../lib/getFriendlyErrorMessage";
import type {
  MediaStatusResponse,
  ProcessingJobLifecycleStatus,
} from "../types/media";

const POLL_INTERVAL_MS = 5000;

const TERMINAL_STATUSES: ProcessingJobLifecycleStatus[] = [
  "completed",
  "failed",
  "cancelled",
];

function isTerminalStatus(status: ProcessingJobLifecycleStatus): boolean {
  return TERMINAL_STATUSES.includes(status);
}

export interface UseMediaPollingResult {
  /** Merged list of media items (backend + optimistic local) */
  items: MediaStatusResponse[];
  /** Optimistic local items not yet confirmed by backend */
  pendingLocalItems: InboxItem[];
  /** Whether the initial fetch is in progress */
  isLoading: boolean;
  /** Whether a refresh (pull-to-refresh) is in progress */
  isRefreshing: boolean;
  /** User-friendly error message, or null */
  error: string | null;
  /** Trigger a manual refresh */
  refresh: () => Promise<void>;
  /** Retry after an error */
  retry: () => void;
  /** Whether polling is currently active */
  isPolling: boolean;
}

/**
 * Custom hook that manages media list fetching and polling.
 *
 * - Fetches media list from GET /api/media on mount
 * - Polls every 5s while any item is in a non-terminal state
 * - Stops polling when all visible items are terminal (completed/failed/cancelled)
 * - Resumes when new non-terminal items appear (e.g., from share intent)
 * - Pauses polling when app goes to background
 * - Merges with InboxContext for optimistic UI from share intent
 */
export function useMediaPolling(): UseMediaPollingResult {
  const { token } = useAuth();
  const { items: localInboxItems } = useInbox();

  const [backendItems, setBackendItems] = useState<MediaStatusResponse[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const pollTimerRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const isMountedRef = useRef(true);
  const appStateRef = useRef<AppStateStatus>(AppState.currentState);

  /**
   * Fetch media list from the backend.
   */
  const fetchMedia = useCallback(
    async (options?: { silent?: boolean }) => {
      if (!token) return;

      if (!options?.silent) {
        setError(null);
      }

      try {
        const response = await MediaService.listMedia(token);
        if (isMountedRef.current) {
          setBackendItems(response.items);
          setError(null);
        }
      } catch (err) {
        if (isMountedRef.current && !options?.silent) {
          const message = getFriendlyErrorMessage(err, {
            fallback: "Unable to load your inbox. Please try again.",
          });
          setError(message);
        }
      }
    },
    [token],
  );

  /**
   * Determine whether polling should be active.
   * Polling is needed when any item has a non-terminal processing status.
   */
  const shouldPoll = useCallback((): boolean => {
    // Check backend items
    const hasActiveBackendItems = backendItems.some(
      (item) => !isTerminalStatus(item.processing_job.status),
    );
    if (hasActiveBackendItems) return true;

    // Check local inbox items that are still submitting or pending
    const hasActiveLocalItems = localInboxItems.some(
      (item) =>
        item.state === "submitting" ||
        item.state === "pending" ||
        (item.processingStatus && !isTerminalStatus(item.processingStatus)),
    );
    return hasActiveLocalItems;
  }, [backendItems, localInboxItems]);

  /**
   * Start polling interval.
   */
  const startPolling = useCallback(() => {
    if (pollTimerRef.current) return; // Already polling

    pollTimerRef.current = setInterval(() => {
      fetchMedia({ silent: true });
    }, POLL_INTERVAL_MS);
  }, [fetchMedia]);

  /**
   * Stop polling interval.
   */
  const stopPolling = useCallback(() => {
    if (pollTimerRef.current) {
      clearInterval(pollTimerRef.current);
      pollTimerRef.current = null;
    }
  }, []);

  /**
   * Public refresh function (pull-to-refresh).
   */
  const refresh = useCallback(async () => {
    setIsRefreshing(true);
    await fetchMedia();
    if (isMountedRef.current) {
      setIsRefreshing(false);
    }
  }, [fetchMedia]);

  /**
   * Retry after an error.
   */
  const retry = useCallback(() => {
    setIsLoading(true);
    setError(null);
    fetchMedia().finally(() => {
      if (isMountedRef.current) {
        setIsLoading(false);
      }
    });
  }, [fetchMedia]);

  // Initial fetch on mount
  useEffect(() => {
    isMountedRef.current = true;

    if (token) {
      setIsLoading(true);
      fetchMedia().finally(() => {
        if (isMountedRef.current) {
          setIsLoading(false);
        }
      });
    } else {
      setIsLoading(false);
    }

    return () => {
      isMountedRef.current = false;
      stopPolling();
    };
  }, [token, fetchMedia, stopPolling]);

  // Manage polling based on item states
  useEffect(() => {
    if (appStateRef.current !== "active") return;

    if (shouldPoll()) {
      startPolling();
    } else {
      stopPolling();
    }
  }, [shouldPoll, startPolling, stopPolling]);

  // Pause/resume polling on app state changes
  useEffect(() => {
    const subscription = AppState.addEventListener(
      "change",
      (nextState: AppStateStatus) => {
        const wasBackground = appStateRef.current !== "active";
        appStateRef.current = nextState;

        if (nextState === "active" && wasBackground) {
          // App came to foreground - refresh and restart polling if needed
          fetchMedia({ silent: true });
          if (shouldPoll()) {
            startPolling();
          }
        } else if (nextState !== "active") {
          // App went to background - stop polling
          stopPolling();
        }
      },
    );

    return () => {
      subscription.remove();
    };
  }, [fetchMedia, shouldPoll, startPolling, stopPolling]);

  // Re-fetch when local inbox items change (new item shared)
  useEffect(() => {
    if (localInboxItems.length > 0 && token && !isLoading) {
      // Slight delay to let the backend process the new item
      const timer = setTimeout(() => {
        fetchMedia({ silent: true });
      }, 1500);
      return () => clearTimeout(timer);
    }
  }, [localInboxItems.length, token, isLoading, fetchMedia]);

  /**
   * Compute pending local items that are not yet in the backend response.
   * These are items the user just shared but the backend hasn't returned them yet.
   */
  const pendingLocalItems = localInboxItems.filter((localItem) => {
    if (!localItem.mediaItemId) return true; // Not yet submitted
    return !backendItems.some(
      (bi) => bi.media_item.media_item_id === localItem.mediaItemId,
    );
  });

  return {
    items: backendItems,
    pendingLocalItems,
    isLoading,
    isRefreshing,
    error,
    refresh,
    retry,
    isPolling: pollTimerRef.current !== null,
  };
}
