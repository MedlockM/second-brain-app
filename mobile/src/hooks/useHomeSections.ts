import { useCallback, useEffect, useRef, useState } from "react";
import { useAuth } from "../contexts/AuthContext";
import { EngagementService } from "../services/engagementService";
import { OrganizationService } from "../services/organizationService";
import { DigestService } from "../services/digestService";
import type { RecentEngagement } from "../types/engagements";
import type { Collection } from "../types/organization";

/**
 * The two data sources the Home screen owns beyond its media list, plus the
 * Daily Digest count (task-307).
 *
 * The point of the hook is *independence*. Three screens' worth of content now
 * share one scroll view, and a collections endpoint that 500s must not take the
 * engagement row down with it, nor blank the media list that `useMediaPolling`
 * fetches separately. So each source keeps its own state and its own failure,
 * and a failure resolves to "this section has nothing", never to an exception
 * crossing into another one.
 *
 * None of them exposes a loading flag on purpose: no section here may render a
 * spinner. A row with nothing to show is simply absent, which is the same thing
 * the screen does for an empty row and therefore needs no extra state.
 */
export interface UseHomeSectionsResult {
  /** "Continue learning", in the order the server returned. Empty hides it. */
  continueLearning: RecentEngagement[];
  /** The user's collections, feeding the "Recently added" merge. */
  collections: Collection[];
  /** Count on the Daily Digest card, or null when it is unavailable. */
  digestCount: number | null;
  /** Refetch all three. Never rejects. */
  refresh: () => Promise<void>;
}

/** Server-side cap of the engagement row; asking for more would be ignored. */
const CONTINUE_LEARNING_LIMIT = 12;

export function useHomeSections(): UseHomeSectionsResult {
  const { isAuthenticated } = useAuth();

  const [continueLearning, setContinueLearning] = useState<RecentEngagement[]>(
    [],
  );
  const [collections, setCollections] = useState<Collection[]>([]);
  const [digestCount, setDigestCount] = useState<number | null>(null);

  const isMountedRef = useRef(true);

  const refresh = useCallback(async () => {
    if (!isAuthenticated) return;

    // `allSettled`, not `all`: one rejection must leave the other two results
    // usable. The three calls are independent and issued together so the screen
    // costs one round trip, not three sequential ones.
    const [recent, folders, digest] = await Promise.allSettled([
      EngagementService.listRecent(CONTINUE_LEARNING_LIMIT),
      OrganizationService.getUserCollections(),
      DigestService.getDailyDigest(),
    ]);

    if (!isMountedRef.current) return;

    // A rejection keeps the previous value rather than clearing it: a refresh
    // that fails should leave the screen as the user last saw it, not empty it.
    if (recent.status === "fulfilled") {
      setContinueLearning(recent.value);
    }
    if (folders.status === "fulfilled") {
      setCollections(folders.value);
    }
    if (digest.status === "fulfilled") {
      const count = digest.value?.stats?.media_count;
      setDigestCount(typeof count === "number" ? count : null);
    }
  }, [isAuthenticated]);

  useEffect(() => {
    isMountedRef.current = true;

    // Deferred by a tick rather than called in the effect body, the same shape
    // `useMediaPolling` uses: a `setState` reached synchronously from an effect
    // cascades a render, and the lint rule that says so is on.
    let initialFetchTimer: ReturnType<typeof setTimeout> | null = null;
    if (isAuthenticated) {
      initialFetchTimer = setTimeout(() => {
        void refresh();
      }, 0);
    }

    return () => {
      if (initialFetchTimer) clearTimeout(initialFetchTimer);
      isMountedRef.current = false;
    };
  }, [isAuthenticated, refresh]);

  return { continueLearning, collections, digestCount, refresh };
}
