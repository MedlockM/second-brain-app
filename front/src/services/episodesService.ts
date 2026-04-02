import { createHttpError, parseErrorResponse } from "../lib/httpError";

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || "http://localhost:8000";

export interface Summary {
  main_topics: string[];
  key_points: string[];
  notable_quotes: string[];
  conclusion: string | string[];
}

export interface QuizChoice {
  id: string;
  text: string;
  correct: boolean;
}

export interface QuizQuestion {
  id: string;
  prompt: string;
  multiple: boolean;
  choices: QuizChoice[];
  explanation?: string;
}

export interface Quiz {
  id: string;
  language: string;
  questions: QuizQuestion[];
}

export interface Episode {
  job_id: string;
  podcast_title: string;
  podcast_id: string;
  episode_title: string;
  episode_image: string;
  episode_date_published: number; // Unix timestamp - episode publication date (for display)
  created_at: number; // Unix timestamp - job submission date (for sorting)
  completed_at?: number; // Unix timestamp
  summary: Summary;
  quiz: Quiz;
}

export interface MyEpisodesResponse {
  status: string;
  episodes: Episode[];
  count: number;
}

export const EpisodesService = {
  async getMyEpisodes(token: string): Promise<MyEpisodesResponse> {
    const response = await fetch(`${API_BASE_URL}/api/v1/episodes/my-episodes`, {
      method: "GET",
      headers: {
        Authorization: `Bearer ${token}`,
        "Content-Type": "application/json",
      },
    });

    if (!response.ok) {
      const { message, code } = await parseErrorResponse(
        response,
        `Failed to fetch episodes: ${response.statusText}`,
      );
      throw createHttpError(message, response.status, code);
    }

    return response.json();
  },
};
