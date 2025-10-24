import { PodcastSearchResponse } from "../types/podcast";

// When VITE_API_URL is empty, use relative URLs (for Vite proxy)
// Otherwise use the full URL (for production)
const API_BASE_URL = import.meta.env.VITE_API_URL || "";

export class PodcastService {
  static async searchPodcasts(
    query: string,
    token: string,
    page: number = 1,
    pageSize: number = 20,
  ): Promise<PodcastSearchResponse> {
    const params = new URLSearchParams({
      query,
      page: page.toString(),
      page_size: pageSize.toString(),
    });

    const response = await fetch(
      `${API_BASE_URL}/api/v1/podcasts/search?${params}`,
      {
        method: "GET",
        headers: {
          Authorization: `Bearer ${token}`,
          "Content-Type": "application/json",
        },
      },
    );

    if (!response.ok) {
      const error = await response
        .json()
        .catch(() => ({ message: "Search failed" }));
      throw new Error(
        error.message || error.detail || "Failed to search podcasts",
      );
    }

    return response.json();
  }
}
