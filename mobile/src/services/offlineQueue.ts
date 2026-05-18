import AsyncStorage from "@react-native-async-storage/async-storage";

const QUEUE_STORAGE_KEY = "@media_summarizer/offline_share_queue";

/**
 * An item queued for submission when the device goes back online.
 */
export interface OfflineQueueItem {
  /** Unique ID for this queued item */
  id: string;
  /** The URL to ingest */
  url: string;
  /** Source app identifier */
  sourceApp: string;
  /** Timestamp when the item was queued */
  queuedAt: string;
  /** Number of times this item has been retried */
  retryCount: number;
}

/**
 * OfflineQueue manages a persistent queue of URLs that were shared while
 * the device was offline. Items are stored in AsyncStorage and processed
 * when connectivity is restored.
 *
 * This implements AC#6: Offline/poor network behavior for shared-link queue and sync.
 */
export class OfflineQueue {
  /**
   * Add a URL to the offline queue for later submission.
   */
  static async enqueue(url: string, sourceApp: string): Promise<OfflineQueueItem> {
    const item: OfflineQueueItem = {
      id: `offline-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
      url,
      sourceApp,
      queuedAt: new Date().toISOString(),
      retryCount: 0,
    };

    const queue = await this.getAll();
    queue.push(item);
    await this.persist(queue);

    return item;
  }

  /**
   * Get all items currently in the offline queue.
   */
  static async getAll(): Promise<OfflineQueueItem[]> {
    try {
      const raw = await AsyncStorage.getItem(QUEUE_STORAGE_KEY);
      if (!raw) return [];
      return JSON.parse(raw) as OfflineQueueItem[];
    } catch {
      return [];
    }
  }

  /**
   * Remove a specific item from the queue (after successful submission).
   */
  static async dequeue(id: string): Promise<void> {
    const queue = await this.getAll();
    const filtered = queue.filter((item) => item.id !== id);
    await this.persist(filtered);
  }

  /**
   * Mark an item as having been retried (increment retry count).
   */
  static async markRetried(id: string): Promise<void> {
    const queue = await this.getAll();
    const updated = queue.map((item) =>
      item.id === id ? { ...item, retryCount: item.retryCount + 1 } : item,
    );
    await this.persist(updated);
  }

  /**
   * Remove items that have exceeded the max retry count.
   */
  static async pruneExhausted(maxRetries: number = 5): Promise<OfflineQueueItem[]> {
    const queue = await this.getAll();
    const exhausted = queue.filter((item) => item.retryCount >= maxRetries);
    const remaining = queue.filter((item) => item.retryCount < maxRetries);
    await this.persist(remaining);
    return exhausted;
  }

  /**
   * Get the count of items in the queue.
   */
  static async count(): Promise<number> {
    const queue = await this.getAll();
    return queue.length;
  }

  /**
   * Clear the entire queue.
   */
  static async clear(): Promise<void> {
    await AsyncStorage.removeItem(QUEUE_STORAGE_KEY);
  }

  /**
   * Persist the queue to AsyncStorage.
   */
  private static async persist(queue: OfflineQueueItem[]): Promise<void> {
    await AsyncStorage.setItem(QUEUE_STORAGE_KEY, JSON.stringify(queue));
  }
}
