import { apiRequest } from "./apiClient";
import type { SourcePlatform } from "../types/media";

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
 * Search filters supported by the Algolia transcript search endpoint.
 * Only `source_platform` is supported for now.
 */
export interface SearchFilters {
  source_platform?: SourcePlatform;
}

/**
 * Search service for full-text transcript search via Algolia.
 * Uses GET /api/search/transcripts endpoint.
 */
export class SearchService {
  /**
   * Full-text transcript search with optional source_platform filter.
   * GET /api/search/transcripts?q=...&page=...&per_page=...&source_platform=...
   *
   * Requires a non-empty query string (min 1 char).
   */
  static async searchTranscripts(
    token: string,
    query: string,
    options?: {
      filters?: SearchFilters;
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

    if (options?.filters?.source_platform) {
      params.set("source_platform", options.filters.source_platform);
    }

    const path = `/api/search/transcripts?${params.toString()}`;

    return apiRequest<SearchTranscriptsResponse>(path, {
      method: "GET",
      token,
    });
  }
}
