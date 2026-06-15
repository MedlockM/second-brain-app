import { apiRequest } from "./apiClient";
import type {
  IngestUrlRequest,
  IngestUrlResponse,
  MediaListItem,
  MediaStatusResponse,
} from "../types/media";

/**
 * Response shape for GET /api/media (list endpoint).
 * Matches `MediaSearchResponse` on the backend.
 */
export interface ListMediaResponse {
  status: string;
  items: MediaListItem[];
  total: number;
  next_cursor?: string | null;
  has_more: boolean;
}

/**
 * Translation metadata from the backend (task-192 / task-200).
 */
export interface TranslationMetadata {
  is_translated: boolean;
  translated_from?: string | null;
  target_language?: string | null;
  detected_language?: string | null;
  detection_method?: string | null;
  /** When true, translation is being produced asynchronously. Poll again. */
  translation_pending?: boolean;
}

/**
 * Response shape for GET /api/media/:id/raw-content.
 * Matches `RawContentResponse` on the backend.
 */
export interface RawContentResponse {
  status: string;
  media_item_id: string;
  content: string;
  content_type: string;
  media_type?: string | null;
  source_format?: string | null;
  translation?: TranslationMetadata | null;
}

/**
 * Media ingestion service for mobile.
 * Uses the canonical /api/media/* endpoints.
 * Shared by both Android share intent and iOS share extension flows.
 */
export class MediaService {
  /**
   * Fetch the list of all media items for the current user.
   * GET /api/media
   */
  static async listMedia(token: string): Promise<ListMediaResponse> {
    return apiRequest<ListMediaResponse>("/api/media", {
      method: "GET",
      token,
    });
  }

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

  /**
   * Fetch the raw textual content of a media item (formatted transcript,
   * extracted article body, OCR result, …). Available once processing has
   * progressed enough to produce content; returns 404 otherwise.
   * GET /api/media/:mediaItemId/raw-content
   */
  static async getRawContent(
    token: string,
    mediaItemId: string,
  ): Promise<RawContentResponse> {
    return apiRequest<RawContentResponse>(
      `/api/media/${encodeURIComponent(mediaItemId)}/raw-content`,
      {
        method: "GET",
        token,
      },
    );
  }
}
