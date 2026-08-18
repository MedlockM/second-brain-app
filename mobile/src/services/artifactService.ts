import { apiRequest } from "./apiClient";
import type { ArtifactType } from "../types/media";
import type {
  ArtifactContentResponse,
  ArtifactDetail,
  ArtifactListResponse,
  ArtifactScope,
  GenerateArtifactRequest,
} from "../types/artifacts";

export type {
  ArtifactContentResponse,
  ArtifactDetail,
  ArtifactListResponse,
  ArtifactScope,
  ArtifactSource,
  ArtifactSummary,
  GenerateArtifactRequest,
} from "../types/artifacts";

/**
 * Artifact service for the mobile app.
 *
 * One scope-addressed API serves both a single media and a collection: the
 * per-media routes are gone. Artifacts are an append-only history, so a scope
 * can hold several entries of the same type and `listArtifacts` is the single
 * source for both the history and the in-flight progress — one request per
 * scope, never one per artifact type.
 */
export class ArtifactService {
  /**
   * Request a generation over a scope.
   * POST /api/artifacts
   */
  static async generateArtifact(
    token: string,
    scope: ArtifactScope,
    scopeId: string,
    artifactType: ArtifactType,
  ): Promise<ArtifactDetail> {
    return apiRequest<ArtifactDetail>(`/api/artifacts`, {
      method: "POST",
      body: {
        scope,
        scope_id: scopeId,
        artifact_type: artifactType,
      } satisfies GenerateArtifactRequest,
      token,
    });
  }

  /**
   * A scope's artifact history, newest first, every type mixed.
   * GET /api/artifacts?scope=...&scope_id=...
   */
  static async listArtifacts(
    token: string,
    scope: ArtifactScope,
    scopeId: string,
    options?: { limit?: number; cursor?: string },
  ): Promise<ArtifactListResponse> {
    const params = new URLSearchParams({ scope, scope_id: scopeId });
    if (options?.limit) params.set("limit", String(options.limit));
    if (options?.cursor) params.set("cursor", options.cursor);
    return apiRequest<ArtifactListResponse>(
      `/api/artifacts?${params.toString()}`,
      {
        method: "GET",
        token,
      },
    );
  }

  /**
   * One entry with its full source snapshot.
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
