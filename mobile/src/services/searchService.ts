import { apiRequest } from "./apiClient";

/**
 * Highlight snippet from a search hit (mirrors backend SearchHitHighlight).
 */
export interface SearchHitHighlight {
  field: string;
  snippet: string;
}

/**
 * A single search result from the Algolia transcript search endpoint.
 */
export interface SearchHit {
  media_item_id: string;
  title: string | null;
  source_platform: string | null;
  created_at: number; // Unix timestamp
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
