import { apiRequest } from "./apiClient";
import type {
  EngagementKind,
  RecentEngagement,
  RecentEngagementsResponse,
  RecordEngagementRequest,
} from "../types/engagements";

export type {
  EngagementKind,
  RecentEngagement,
  RecentEngagementsResponse,
} from "../types/engagements";

/**
 * Engagement service for the mobile app (task-303).
 *
 * The write side is a decoration on top of whatever the user was actually doing,
 * so `reportEngagement` is the one call in this codebase that resolves to nothing
 * and never rejects: a failed stamp costs one tile in one row, and must not
 * surface an alert, block a screen, or delay a render. It is deliberately not
 * retried either — the same signal is produced again the next time the user opens
 * something.
 *
 * The read side (`listRecent`) throws like every other service call, because the
 * caller has a section to hide.
 */
export class EngagementService {
  /**
   * Record that the user just opened and read something.
   * POST /api/engagements -> 204
   *
   * Fire-and-forget by contract: call it without awaiting, or await it knowing it
   * always resolves. The server rate-limits repeats itself, so a screen that
   * remounts does not need its own throttle beyond firing once per mount.
   */
  static async reportEngagement(
    kind: EngagementKind,
    id: string,
  ): Promise<void> {
    if (!id) {
      return;
    }
    try {
      await apiRequest<void>("/api/engagements", {
        method: "POST",
        body: { kind, id } satisfies RecordEngagementRequest,
      });
    } catch {
      // Swallowed on purpose. There is nothing the user could do about it and
      // nothing on screen depends on it.
    }
  }

  /**
   * The "Continue learning" row: media and collections merged, newest first,
   * already capped and with every cover signed.
   * GET /api/engagements/recent
   *
   * An empty array is a normal answer — a fresh account has engaged with nothing,
   * and entries age out of the server's freshness window on their own. The caller
   * hides the section rather than showing a placeholder.
   */
  static async listRecent(limit?: number): Promise<RecentEngagement[]> {
    const query = limit ? `?limit=${encodeURIComponent(String(limit))}` : "";
    const response = await apiRequest<RecentEngagementsResponse>(
      `/api/engagements/recent${query}`,
      { method: "GET" },
    );
    return response?.items ?? [];
  }
}
