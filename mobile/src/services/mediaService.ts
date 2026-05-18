import { apiRequest } from "./apiClient";
import {
  IngestUrlRequest,
  IngestUrlResponse,
  MediaStatusResponse,
} from "../types/media";

/**
 * Media ingestion service for the mobile app.
 * Handles URL submission to the canonical /api/media/* endpoints.
 * Pattern ported from front/src/services/podcastService.ts (HTTP client pattern only).
 */
export class MediaService {
  /**
   * Submit a URL for ingestion.
   * POST /api/media/ingest-url
   */
  static async ingestUrl(
    request: IngestUrlRequest,
    token: string,
  ): Promise<IngestUrlResponse> {
    return apiRequest<IngestUrlResponse>("/api/media/ingest-url", {
      method: "POST",
      body: request,
      token,
    });
  }

  /**
   * Get the status of a media item (includes processing job and artifacts).
   * GET /api/media/:mediaItemId/status
   */
  static async getMediaStatus(
    mediaItemId: string,
    token: string,
  ): Promise<MediaStatusResponse> {
    return apiRequest<MediaStatusResponse>(`/api/media/${mediaItemId}/status`, {
      method: "GET",
      token,
    });
  }
}
