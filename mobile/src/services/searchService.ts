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
 * Secured Algolia credentials for direct client-side search.
 * Returned by GET /api/search/credentials.
 */
export interface SearchCredentials {
  app_id: string;
  secured_key: string;
  index_name: string;
  valid_until: number; // Unix timestamp
}

/**
 * Search service for full-text transcript search via Algolia.
 *
 * Two modes are available:
 * 1. Backend-proxied: GET /api/search/transcripts (current default)
 * 2. Direct Algolia: fetch secured key from GET /api/search/credentials,
 *    then query Algolia directly using the secured key (future optimization)
 */
export class SearchService {
  /**
   * Fetch secured Algolia credentials for direct client-side search.
   * The returned secured key embeds a tamper-proof user_id filter and has
   * a short TTL (~1h). Refresh before validUntil or on 403 from Algolia.
   *
   * GET /api/search/credentials
   */
  static async getSearchCredentials(
    token: string,
  ): Promise<SearchCredentials> {
    return apiRequest<SearchCredentials>("/api/search/credentials", {
      method: "GET",
      token,
    });
  }

  /**
   * Full-text transcript search across all source platforms.
   * GET /api/search/transcripts?q=...&page=...&per_page=...
   *
   * Requires a non-empty query string (min 1 char).
   */
  static async searchTranscripts(
    token: string,
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

    return apiRequest<SearchTranscriptsResponse>(path, {
      method: "GET",
      token,
    });
  }
}
