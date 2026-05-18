import { apiRequest } from "./apiClient";
import type {
  IngestUrlRequest,
  IngestUrlResponse,
  MediaStatusResponse,
} from "../types/media";

/**
 * Media ingestion service for mobile.
 * Uses the canonical /api/media/* endpoints.
 * Pattern adapted from front/src/services/mediaService.ts.
 */
export class MediaService {
  /**
   * Submit a URL for ingestion via the canonical endpoint.
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
