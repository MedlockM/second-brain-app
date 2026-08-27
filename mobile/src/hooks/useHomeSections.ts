import { useCallback, useEffect, useRef, useState } from "react";
import { useAuth } from "../contexts/AuthContext";
import { EngagementService } from "../services/engagementService";
import { OrganizationService } from "../services/organizationService";
import type { RecentEngagement } from "../types/engagements";
import type { Collection } from "../types/organization";

/**
 * The two data sources the Home screen owns beyond its media list.
 *
 * The point of the hook is *independence*. Several screens' worth of content
 * share one scroll view, and a collections endpoint that 500s must not take the
 * engagement row down with it, nor blank the media list that `useMediaPolling`
 * fetches separately. So each source keeps its own state and its own failure,
 * and a failure resolves to "this section has nothing", never to an exception
 * crossing into another one.
 *
 * Neither exposes a loading flag on purpose: no section here may render a
 * spinner. A row with nothing to show is simply absent, which is the same thing
 * the screen does for an empty row and therefore needs no extra state.
 *
 * The collections carry their own `media_count`, which is where the unsorted
 * review button's figure comes from (task-324) — the Home no longer calls the
 * digest endpoint just to put a number on a card.
 */
export interface UseHomeSectionsResult {
  /** "Continue learning", in the order the server returned. Empty hides it. */
  continueLearning: RecentEngagement[];
  /**
   * The user's collections, feeding the "Recently added" merge and the unsorted
   * count on the review button.
   */
  collections: Collection[];
  /** Refetch both. Never rejects. */
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

  const isMountedRef = useRef(true);

  const refresh = useCallback(async () => {
    if (!isAuthenticated) return;

    // `allSettled`, not `all`: one rejection must leave the other result usable.
    // The two calls are independent and issued together so the screen costs one
    // round trip, not two sequential ones.
    const [recent, folders] = await Promise.allSettled([
      EngagementService.listRecent(CONTINUE_LEARNING_LIMIT),
      OrganizationService.getUserCollections(),
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

  return { continueLearning, collections, refresh };
}
