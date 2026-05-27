import { createHttpError, parseErrorResponse } from "../lib/httpError";

// When VITE_API_URL is empty, use relative URLs (for Vite proxy)
// Otherwise use the full URL (for production)
const API_BASE_URL = import.meta.env.VITE_API_URL || "";

export interface SummaryContent {
  main_topics: string[];
  key_points: string[];
  notable_quotes: string[];
  conclusion: string | string[];
}

export interface SummaryItem {
  job_id: string;
  user_id: string;
  episode_guid: string;
  feed_id: number;
  episode_title: string;
  podcast_title: string;
  episode_image?: string;
  summary: SummaryContent;
  status: string;
  created_at: string;
  completed_at?: string;
  minutes_charged?: number;
}

export interface MySummariesResponse {
  summaries: SummaryItem[];
  count: number;
  page: number;
  page_size: number;
  total_pages: number;
}

export class SummariesService {
  static async getMySummaries(
    token: string,
    page: number = 1,
    pageSize: number = 20
  ): Promise<MySummariesResponse> {
    const params = new URLSearchParams({
      page: page.toString(),
      page_size: pageSize.toString(),
    });

    const response = await fetch(
      `${API_BASE_URL}/api/v1/summaries/me?${params}`,
      {
        method: "GET",
        headers: {
          Authorization: `Bearer ${token}`,
          "Content-Type": "application/json",
        },
      }
    );

    if (!response.ok) {
      const { message, code } = await parseErrorResponse(
        response,
        "Failed to fetch summaries",
      );
      throw createHttpError(message, response.status, code);
    }

    return response.json();
  }

  static async getSummary(jobId: string, token: string): Promise<SummaryItem> {
    const response = await fetch(`${API_BASE_URL}/api/v1/summaries/${jobId}`, {
      method: "GET",
      headers: {
        Authorization: `Bearer ${token}`,
        "Content-Type": "application/json",
      },
    });

    if (!response.ok) {
      const { message, code } = await parseErrorResponse(
        response,
        "Failed to fetch summary",
      );
      throw createHttpError(message, response.status, code);
    }

    return response.json();
  }
}
