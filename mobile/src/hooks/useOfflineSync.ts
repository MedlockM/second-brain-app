import { useEffect, useRef, useState, useCallback } from "react";
import { useNetworkStatus } from "./useNetworkStatus";
import { useAuth } from "../contexts/AuthContext";
import { useInbox } from "../contexts/InboxContext";
import { OfflineQueue, OfflineQueueItem } from "../services/offlineQueue";
import { MediaService } from "../services/mediaService";
import { getFriendlyErrorMessage } from "../lib/getFriendlyErrorMessage";

/**
 * Hook that processes the offline share queue when connectivity is restored.
 *
 * Behavior:
 * - On app start, checks if there are queued items
 * - When the device transitions from offline to online, processes the queue
 * - Items are submitted one by one with brief delays to avoid flooding
 * - Failed items are retried (up to 5 times) or pruned
 * - Integrates with InboxContext for optimistic UI updates
 */
export function useOfflineSync(): {
  queuedCount: number;
  isSyncing: boolean;
  triggerSync: () => void;
} {
  const { isConnected, isReady } = useNetworkStatus();
  const { token } = useAuth();
  const { addItem, markSubmitted, markFailed } = useInbox();

  const [queuedCount, setQueuedCount] = useState(0);
  const [isSyncing, setIsSyncing] = useState(false);
  const wasOfflineRef = useRef(false);
  const isSyncingRef = useRef(false);

  // Load initial queue count
  useEffect(() => {
    OfflineQueue.count().then(setQueuedCount);
  }, []);

  // Track offline/online transitions
  useEffect(() => {
    if (!isReady) return;

    if (!isConnected) {
      wasOfflineRef.current = true;
    } else if (wasOfflineRef.current && token) {
      // Just came back online
      wasOfflineRef.current = false;
      processQueue();
    }
  }, [isConnected, isReady, token]);

  const processQueue = useCallback(async () => {
    if (isSyncingRef.current || !token) return;

    isSyncingRef.current = true;
    setIsSyncing(true);

    try {
      // Prune items that have been retried too many times
      await OfflineQueue.pruneExhausted(5);

      const items = await OfflineQueue.getAll();
      if (items.length === 0) {
        setQueuedCount(0);
        return;
      }

      for (const item of items) {
        try {
          const localId = addItem(item.url, item.sourceApp);

          const response = await MediaService.ingestUrl(token, {
            url: item.url,
            source_app: item.sourceApp,
            idempotency_key: item.id,
          });

          markSubmitted(localId, response);
          await OfflineQueue.dequeue(item.id);
        } catch (err) {
          const friendlyMessage = getFriendlyErrorMessage(err, {
            fallback: "Failed to submit queued link.",
          });

          // If it's a client error (4xx), don't retry - remove from queue
          const status = (err as { status?: number }).status;
          if (status && status >= 400 && status < 500) {
            await OfflineQueue.dequeue(item.id);
          } else {
            await OfflineQueue.markRetried(item.id);
          }
        }

        // Brief delay between submissions
        await new Promise((resolve) => setTimeout(resolve, 500));
      }
    } finally {
      isSyncingRef.current = false;
      setIsSyncing(false);
      const remaining = await OfflineQueue.count();
      setQueuedCount(remaining);
    }
  }, [token, addItem, markSubmitted, markFailed]);

  const triggerSync = useCallback(() => {
    if (isConnected && token) {
      processQueue();
    }
  }, [isConnected, token, processQueue]);

  return { queuedCount, isSyncing, triggerSync };
}
