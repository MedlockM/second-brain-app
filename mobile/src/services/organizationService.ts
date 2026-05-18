import { apiRequest } from "./apiClient";
import type { Tag, Collection } from "../types/organization";

/**
 * Service for tags and collections management.
 * Uses canonical /api/tags and /api/collections endpoints.
 */
export class OrganizationService {
  /**
   * Fetch all tags for the authenticated user.
   * GET /api/tags
   */
  static async getUserTags(token: string): Promise<Tag[]> {
    return apiRequest<Tag[]>("/api/tags", { method: "GET", token });
  }

  /**
   * Update the tags on a specific media item.
   * PUT /api/media/:id/tags
   */
  static async updateMediaTags(
    token: string,
    mediaItemId: string,
    tags: string[],
  ): Promise<void> {
    return apiRequest<void>(
      `/api/media/${encodeURIComponent(mediaItemId)}/tags`,
      {
        method: "PUT",
        body: { tags },
        token,
      },
    );
  }

  /**
   * Fetch all collections for the authenticated user.
   * GET /api/collections
   */
  static async getUserCollections(token: string): Promise<Collection[]> {
    return apiRequest<Collection[]>("/api/collections", {
      method: "GET",
      token,
    });
  }

  /**
   * Set the collection for a specific media item.
   * PUT /api/media/:id/collection
   */
  static async setMediaCollection(
    token: string,
    mediaItemId: string,
    collectionId: string | null,
  ): Promise<void> {
    return apiRequest<void>(
      `/api/media/${encodeURIComponent(mediaItemId)}/collection`,
      {
        method: "PUT",
        body: { collection_id: collectionId },
        token,
      },
    );
  }

  /**
   * Create a new collection.
   * POST /api/collections
   */
  static async createCollection(
    token: string,
    name: string,
    parentId?: string | null,
  ): Promise<Collection> {
    return apiRequest<Collection>("/api/collections", {
      method: "POST",
      body: { name, parent_id: parentId ?? null },
      token,
    });
  }
}
