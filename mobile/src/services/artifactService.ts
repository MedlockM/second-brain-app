import { apiRequest } from "./apiClient";
import type { ArtifactType } from "../types/media";

export interface GenerateArtifactRequest {
  media_item_id: string;
  artifact_type: ArtifactType;
}

export interface GenerateArtifactResponse {
  artifact_id: string;
  media_item_id: string;
  artifact_type: ArtifactType;
  status: "queued" | "generating";
  created_at: string;
}

export interface ArtifactDetail {
  artifact_id: string;
  media_item_id: string;
  artifact_type: ArtifactType;
  status: "queued" | "generating" | "ready" | "failed";
  content?: string;
  created_at: string;
  updated_at: string;
  error_message?: string;
}

/**
 * Artifact service for the mobile app.
 * Uses the canonical /api/artifacts/* endpoints.
 */
export class ArtifactService {
  /**
   * Trigger artifact generation for a media item.
   * POST /api/artifacts/generate
   */
  static async generateArtifact(
    token: string,
    mediaItemId: string,
    artifactType: ArtifactType,
  ): Promise<GenerateArtifactResponse> {
    return apiRequest<GenerateArtifactResponse>("/api/artifacts/generate", {
      method: "POST",
      body: {
        media_item_id: mediaItemId,
        artifact_type: artifactType,
      } satisfies GenerateArtifactRequest,
      token,
    });
  }

  /**
   * Get a specific artifact's details and content.
   * GET /api/artifacts/:artifactId
   */
  static async getArtifact(
    token: string,
    artifactId: string,
  ): Promise<ArtifactDetail> {
    return apiRequest<ArtifactDetail>(
      `/api/artifacts/${encodeURIComponent(artifactId)}`,
      {
        method: "GET",
        token,
      },
    );
  }
}
