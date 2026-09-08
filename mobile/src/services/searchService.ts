import { apiRequest } from "./apiClient";
import type { MediaType } from "../types/media";

/**
 * Highlight snippet from a search hit (mirrors backend SearchHitHighlight).
 */
export interface SearchHitHighlight {
  field: string;
  snippet: string;
}

/**
 * A single search result from the Algolia transcript search endpoint.
 *
 * Everything but the highlights is read server-side from the durable library
 * row, not from the index (task-375): a hit and a library list row describe the
 * same media, so they answer with the same cover, the same subtitle and the same
 * date by construction. The index only says which items match and where.
 */
export interface SearchHit {
  media_item_id: string;
  title: string | null;
  /** Publisher of the media (channel, show, site), or null. */
  creator_name: string | null;
  source_platform: string | null;
  /** Media kind, drawn as a glyph when the hit has no cover. */
  media_type: MediaType | null;
  /**
   * Fetchable cover URL, already signed by the backend for a re-hosted cover.
   * Null when the item has none — and also for anything indexed before covers
   * were, which the vignette handles the same way: it falls back to the
   * media-type glyph rather than leaving a hole.
   */
  media_image: string | null;
  /** Where the media came from. The subtitle shows its domain absent a creator. */
  source_url: string | null;
  /** Folder the media is filed in; null is Unsorted, which "Move" preselects. */
  folder_id: string | null;
  /** ISO 8601, the library row's own save date — the age the vignette prints. */
  created_at: string;
  /** ISO 8601, last write on the row. Part of the cover's cache key. */
  updated_at: string;
  /**
   * The media still has a library row.
   *
   * `false` on a hit the index kept after a deletion — deleting a media does not
   * unindex its transcript — and the one case where the vignette offers no long
   * press: there is nothing left to rename, move or delete.
   */
  in_library: boolean;
  text_match_score: number;
  highlights: SearchHitHighlight[];
}

/**
 * Response from GET /api/search/transcripts.
 */
export interface SearchTranscriptsResponse {
  query: string;
  found: number;
  page: number;
  per_page: number;
  hits: SearchHit[];
}

/**
 * Search service for full-text transcript search via Algolia.
 *
 * Search is backend-proxied: the app calls GET /api/search/transcripts and the
 * backend queries Algolia, filtering results to the authenticated user.
 */
export class SearchService {
  /**
   * Full-text transcript search across all source platforms.
   * GET /api/search/transcripts?q=...&page=...&per_page=...
   *
   * Requires a non-empty query string (min 1 char).
   */
  static async searchTranscripts(
    query: string,
    options?: {
      page?: number;
      perPage?: number;
    },
  ): Promise<SearchTranscriptsResponse> {
    const params = new URLSearchParams();
    params.set("q", query.trim());

    if (options?.page && options.page > 1) {
      params.set("page", String(options.page));
    }

    if (options?.perPage) {
      params.set("per_page", String(options.perPage));
    }

    const path = `/api/search/transcripts?${params.toString()}`;

    return apiRequest<SearchTranscriptsResponse>(path, { method: "GET" });
  }
}
