import { apiRequest } from "./apiClient";
import type { ArtifactType, ArtifactStatus } from "../types/media";

export interface GenerateArtifactRequest {
  artifact_type: ArtifactType;
  parameters?: Record<string, unknown>;
}

export interface GenerateArtifactResponse {
  artifact_id: string;
  media_item_id: string;
  artifact_type: ArtifactType;
  status: ArtifactStatus;
  s3_key?: string | null;
}

export interface ArtifactDetail {
  artifact_id: string;
  media_item_id: string;
  artifact_type: ArtifactType;
  status: ArtifactStatus;
  s3_key?: string | null;
}

export interface ArtifactContentResponse {
  artifact_id: string;
  artifact_type: ArtifactType;
  media_item_id: string;
  status: ArtifactStatus;
  /** Parsed JSON payload (shape depends on artifact_type). */
  content: Record<string, unknown>;
}

/**
 * Artifact service for the mobile app.
 * Uses the canonical /api/media/:id/artifacts endpoint per the OpenAPI contract.
 */
export class ArtifactService {
  /**
   * Trigger artifact generation for a media item.
   * POST /api/media/:mediaItemId/artifacts
   */
  static async generateArtifact(
    token: string,
    mediaItemId: string,
    artifactType: ArtifactType,
  ): Promise<GenerateArtifactResponse> {
    return apiRequest<GenerateArtifactResponse>(
      `/api/media/${encodeURIComponent(mediaItemId)}/artifacts`,
      {
        method: "POST",
        body: { artifact_type: artifactType } satisfies GenerateArtifactRequest,
        token,
      },
    );
  }

  /**
   * Get a specific artifact's details.
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

  /**
   * Fetch the rendered JSON payload for a ready artifact.
   * GET /api/artifacts/:artifactId/content
   */
  static async getArtifactContent(
    token: string,
    artifactId: string,
  ): Promise<ArtifactContentResponse> {
    return apiRequest<ArtifactContentResponse>(
      `/api/artifacts/${encodeURIComponent(artifactId)}/content`,
      {
        method: "GET",
        token,
      },
    );
  }
}
