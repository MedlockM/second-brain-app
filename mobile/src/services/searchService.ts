import { apiRequest } from "./apiClient";
import type { MediaItemContract, MediaType, SourcePlatform } from "../types/media";

/**
 * Search filters that can be combined with full-text query.
 */
export interface SearchFilters {
  type?: MediaType;
  source?: SourcePlatform;
  tags?: string[];
  folder?: string;
}

/**
 * Response from the search endpoint.
 */
export interface SearchResponse {
  items: MediaItemContract[];
  total: number;
}

/**
 * Search service for the media library.
 * Uses canonical GET /api/media/search endpoint (Algolia full-text).
 */
export class SearchService {
  /**
   * Full-text search with optional metadata filters.
   * GET /api/media/search?q=...&type=...&source=...&tags=...&folder=...
   */
  static async searchMedia(
    token: string,
    query: string,
    filters?: SearchFilters,
  ): Promise<SearchResponse> {
    const params = new URLSearchParams();

    if (query.trim()) {
      params.set("q", query.trim());
    }

    if (filters?.type) {
      params.set("type", filters.type);
    }

    if (filters?.source) {
      params.set("source", filters.source);
    }

    if (filters?.tags && filters.tags.length > 0) {
      params.set("tags", filters.tags.join(","));
    }

    if (filters?.folder) {
      params.set("folder", filters.folder);
    }

    const queryString = params.toString();
    const path = `/api/media/search${queryString ? `?${queryString}` : ""}`;

    return apiRequest<SearchResponse>(path, {
      method: "GET",
      token,
    });
  }
}
