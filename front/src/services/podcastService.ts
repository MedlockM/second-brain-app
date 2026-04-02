import {
  PodcastSearchResponse,
  PodcastEpisodesResponse,
} from "../types/podcast";
import { parseErrorResponse } from "../lib/httpError";

// When VITE_API_URL is empty, use relative URLs (for Vite proxy)
// Otherwise use the full URL (for production)
const API_BASE_URL = import.meta.env.VITE_API_URL || "";

export class ServiceError extends Error {
  status?: number;
  code?: string;
  constructor(message: string, status?: number, code?: string) {
    super(message);
    this.status = status;
    this.code = code;
    this.name = "ServiceError";
  }
}

export interface SubmitEpisodeRequest {
  feed_id: number;
  episode_guid: string;
}

export interface SubmitEpisodeResponse {
  job_id: string;
  status: string;
  message: string;
  estimated_minutes: number;
}

export interface Job {
  job_id: string;
  user_id: string;
  episode_guid: string;
  feed_id: number;
  status:
    | "pending"
    | "rss_resolving"
    | "downloading"
    | "transcribing"
    | "summarizing"
    | "notifying"
    | "completed"
    | "failed"
    | "cancelled";
  progress?: number;
  error_message?: string;
  created_at: string;
  updated_at: string;
  episode_title?: string;
  podcast_title?: string;
  episode_image?: string;
  duration_seconds?: number;
  episode_date_published?: number;
}

export interface JobsResponse {
  jobs: Job[];
  total: number;
}

export class PodcastService {
  static async searchPodcasts(
    query: string,
    token: string,
    page: number = 1,
    pageSize: number = 20,
    similar: boolean = true,
  ): Promise<PodcastSearchResponse> {
    const params = new URLSearchParams({
      query,
      page: page.toString(),
      page_size: pageSize.toString(),
      clean: "true",
      similar: similar ? "true" : "false",
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
      const { message, code } = await parseErrorResponse(
        response,
        "Search failed",
      );
      throw new ServiceError(
        message || "Failed to search podcasts",
        response.status,
        code,
      );
    }

    return response.json();
  }

  static async getPodcastEpisodes(
    feedId: number,
    token: string,
    maxResults: number = 50,
  ): Promise<PodcastEpisodesResponse> {
    const response = await fetch(
      `${API_BASE_URL}/api/v1/podcast-search/episodes`,
      {
        method: "POST",
        headers: {
          Authorization: `Bearer ${token}`,
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          feed_id: feedId,
          max_results: maxResults,
        }),
      },
    );

    if (!response.ok) {
      const { message, code } = await parseErrorResponse(
        response,
        "Failed to fetch episodes",
      );
      throw new ServiceError(
        message || "Failed to fetch episodes",
        response.status,
        code,
      );
    }

    return response.json();
  }

  static async submitEpisode(
    feedId: number,
    episodeGuid: string,
    token: string,
  ): Promise<SubmitEpisodeResponse> {
    const response = await fetch(
      `${API_BASE_URL}/api/v1/podcast-search/submit-episode`,
      {
        method: "POST",
        headers: {
          Authorization: `Bearer ${token}`,
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          feed_id: feedId,
          episode_guid: episodeGuid,
        }),
      },
    );

    if (!response.ok) {
      const { message, code } = await parseErrorResponse(
        response,
        "Failed to submit episode",
      );
      throw new ServiceError(
        message || "Failed to submit episode for processing",
        response.status,
        code,
      );
    }

    return response.json();
  }

  static async getUserJobs(
    token: string,
    status?: string,
  ): Promise<JobsResponse> {
    const params = new URLSearchParams();
    if (status) {
      params.append("status", status);
    }

    const url = `${API_BASE_URL}/api/v1/jobs/me${params.toString() ? `?${params}` : ""}`;

    const response = await fetch(url, {
      method: "GET",
      headers: {
        Authorization: `Bearer ${token}`,
        "Content-Type": "application/json",
      },
    });

    if (!response.ok) {
      const { message, code } = await parseErrorResponse(
        response,
        "Failed to fetch jobs",
      );
      throw new ServiceError(
        message || "Failed to fetch jobs",
        response.status,
        code,
      );
    }

    // The API returns a list directly, normalize to JobsResponse format
    const data = await response.json();
    if (Array.isArray(data)) {
      return { jobs: data, total: data.length };
    }
    // Already in expected format
    return data;
  }

  static async getJob(jobId: string, token: string): Promise<Job> {
    const response = await fetch(`${API_BASE_URL}/api/v1/jobs/${jobId}`, {
      method: "GET",
      headers: {
        Authorization: `Bearer ${token}`,
        "Content-Type": "application/json",
      },
    });

    if (!response.ok) {
      const { message, code } = await parseErrorResponse(
        response,
        "Failed to fetch job",
      );
      throw new ServiceError(
        message || "Failed to fetch job",
        response.status,
        code,
      );
    }

    return response.json();
  }
}
