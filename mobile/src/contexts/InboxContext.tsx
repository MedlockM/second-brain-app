import React, {
  createContext,
  useContext,
  useState,
  useCallback,
} from "react";
import { IngestUrlResponse, ProcessingJobLifecycleStatus, SourcePlatform } from "../types/media";

/**
 * Represents a single inbox item - a shared URL that has been submitted or is pending.
 */
export interface InboxItem {
  /** Unique local ID for optimistic UI */
  localId: string;
  /** The shared URL */
  url: string;
  /** Optional note added by the user */
  note?: string;
  /** Source app identifier */
  sourceApp?: string;
  /** Detected source platform for placeholder icon */
  sourcePlatform?: SourcePlatform;
  /** Local state of the item */
  state: "pending" | "submitting" | "submitted" | "failed";
  /** Processing status from the backend (after submission) */
  processingStatus?: ProcessingJobLifecycleStatus;
  /** Media item ID from the backend (after successful submission) */
  mediaItemId?: string;
  /** Job ID from the backend */
  jobId?: string;
  /** Whether this was a duplicate */
  deduplicated?: boolean;
  /** Error message if submission failed */
  errorMessage?: string;
  /** Timestamp of when the item was added */
  createdAt: string;
}

interface InboxContextValue {
  items: InboxItem[];
  addItem: (url: string, sourceApp?: string, sourcePlatform?: SourcePlatform) => string;
  updateItem: (localId: string, updates: Partial<InboxItem>) => void;
  removeItem: (localId: string) => void;
  markSubmitted: (localId: string, response: IngestUrlResponse) => void;
  markFailed: (localId: string, errorMessage: string) => void;
  clearCompleted: () => void;
}

const InboxContext = createContext<InboxContextValue | null>(null);

let localIdCounter = 0;

function generateLocalId(): string {
  localIdCounter += 1;
  return `share-${Date.now()}-${localIdCounter}`;
}

export function InboxProvider({ children }: { children: React.ReactNode }) {
  const [items, setItems] = useState<InboxItem[]>([]);

  const addItem = useCallback((url: string, sourceApp?: string, sourcePlatform?: SourcePlatform): string => {
    const localId = generateLocalId();
    const item: InboxItem = {
      localId,
      url,
      sourceApp,
      sourcePlatform,
      state: "pending",
      createdAt: new Date().toISOString(),
    };
    setItems((prev) => [item, ...prev]);
    return localId;
  }, []);

  const updateItem = useCallback(
    (localId: string, updates: Partial<InboxItem>) => {
      setItems((prev) =>
        prev.map((item) =>
          item.localId === localId ? { ...item, ...updates } : item,
        ),
      );
    },
    [],
  );

  const removeItem = useCallback((localId: string) => {
    setItems((prev) => prev.filter((item) => item.localId !== localId));
  }, []);

  const markSubmitted = useCallback(
    (localId: string, response: IngestUrlResponse) => {
      setItems((prev) =>
        prev.map((item) =>
          item.localId === localId
            ? {
                ...item,
                state: "submitted" as const,
                mediaItemId: response.media_item.media_item_id,
                jobId: response.processing_job.job_id,
                processingStatus: response.processing_job.status,
                deduplicated: response.deduplicated,
              }
            : item,
        ),
      );
    },
    [],
  );

  const markFailed = useCallback((localId: string, errorMessage: string) => {
    setItems((prev) =>
      prev.map((item) =>
        item.localId === localId
          ? { ...item, state: "failed" as const, errorMessage }
          : item,
      ),
    );
  }, []);

  const clearCompleted = useCallback(() => {
    setItems((prev) =>
      prev.filter(
        (item) =>
          item.state !== "submitted" ||
          (item.processingStatus !== "completed" &&
            item.processingStatus !== "failed"),
      ),
    );
  }, []);

  const value: InboxContextValue = {
    items,
    addItem,
    updateItem,
    removeItem,
    markSubmitted,
    markFailed,
    clearCompleted,
  };

  return (
    <InboxContext.Provider value={value}>{children}</InboxContext.Provider>
  );
}

/**
 * Hook to access inbox context. Must be used within InboxProvider.
 */
export function useInbox(): InboxContextValue {
  const context = useContext(InboxContext);
  if (!context) {
    throw new Error("useInbox must be used within an InboxProvider");
  }
  return context;
}
