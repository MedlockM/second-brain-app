import { useState, useEffect, useRef, useCallback } from "react";
import { useAuth } from "../contexts/AuthContext";
import { useInbox, InboxItem } from "../contexts/InboxContext";
import { MediaService } from "../services/mediaService";
import { getFriendlyErrorMessage } from "../lib/getFriendlyErrorMessage";
import type { MediaStatusResponse } from "../types/media";

export interface UseMediaPollingResult {
  /** Backend media items */
  items: MediaStatusResponse[];
  /** Optimistic local items not yet confirmed by backend */
  pendingLocalItems: InboxItem[];
  /** Whether the initial fetch is in progress */
  isLoading: boolean;
  /** Whether a refresh (pull-to-refresh) is in progress */
  isRefreshing: boolean;
  /** User-friendly error message, or null */
  error: string | null;
  /** Trigger a manual refresh (pull-to-refresh or focus refetch) */
  refresh: () => Promise<void>;
  /** Retry after an error */
  retry: () => void;
}

/**
 * Custom hook that manages media list fetching without polling.
 *
 * V1 design: no recurring network requests while the inbox is open.
 * - Fetches once on mount
 * - Exposes refresh() for pull-to-refresh and focus-based refetch
 * - Merges with InboxContext for optimistic UI from share intent
 */
export function useMediaPolling(): UseMediaPollingResult {
  const { token } = useAuth();
  const { items: localInboxItems } = useInbox();

  const [backendItems, setBackendItems] = useState<MediaStatusResponse[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const isMountedRef = useRef(true);

  /**
   * Fetch media list from the backend (one-shot).
   */
  const fetchMedia = useCallback(async () => {
    if (!token) return;

    setError(null);

    try {
      const response = await MediaService.listMedia(token);
      if (isMountedRef.current) {
        setBackendItems(response.items);
        setError(null);
      }
    } catch (err) {
      if (isMountedRef.current) {
        const message = getFriendlyErrorMessage(err, {
          fallback: "Unable to load your inbox. Please try again.",
        });
        setError(message);
      }
    }
  }, [token]);

  /**
   * Public refresh function (pull-to-refresh / focus refetch).
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
    };
  }, [token, fetchMedia]);

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
  };
}
