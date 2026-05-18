import { apiRequest } from "./apiClient";
import type {
  IngestUrlRequest,
  IngestUrlResponse,
  MediaStatusResponse,
} from "../types/media";

/**
 * Media ingestion service for mobile.
 * Uses the canonical /api/media/* endpoints.
 * Shared by both Android share intent and iOS share extension flows.
 */
export class MediaService {
  /**
   * Submit a URL for ingestion via the canonical endpoint.
   * POST /api/media/ingest-url
   */
  static async ingestUrl(
    token: string,
    payload: IngestUrlRequest,
  ): Promise<IngestUrlResponse> {
    return apiRequest<IngestUrlResponse>("/api/media/ingest-url", {
      method: "POST",
      body: payload,
      token,
    });
  }

  /**
   * Get the current status of a media item and its processing job.
   * GET /api/media/:mediaItemId
   */
  static async getMediaStatus(
    token: string,
    mediaItemId: string,
  ): Promise<MediaStatusResponse> {
    return apiRequest<MediaStatusResponse>(
      `/api/media/${encodeURIComponent(mediaItemId)}`,
      {
        method: "GET",
        token,
      },
    );
  }
}
