import { apiRequest } from "./apiClient";
import type { Tag, Collection } from "../types/organization";
import type { MediaListItem } from "../types/media";

interface MediaListResponse {
  status: string;
  items: MediaListItem[];
  total: number;
  next_cursor?: string | null;
  has_more: boolean;
}

interface TagListResponse {
  tags: Array<{
    id: string;
    name: string;
    color?: string | null;
    created_at: string;
    updated_at: string;
  }>;
}

interface FolderResponse {
  id: string;
  name: string;
  parent_folder_id?: string | null;
  is_default: boolean;
  created_at: string;
  updated_at: string;
}

interface FolderListResponse {
  folders: FolderResponse[];
}

function toTag(tag: TagListResponse["tags"][number]): Tag {
  return {
    id: tag.id,
    name: tag.name,
    color: tag.color ?? null,
    created_at: tag.created_at,
    updated_at: tag.updated_at,
    count: 0,
  };
}

function toCollection(folder: FolderResponse): Collection {
  return {
    id: folder.id,
    name: folder.name,
    parent_id: folder.parent_folder_id ?? null,
    parent_folder_id: folder.parent_folder_id ?? null,
    is_default: folder.is_default,
    created_at: folder.created_at,
    updated_at: folder.updated_at,
    media_count: 0,
  };
}

/**
 * Service for tags and collections management.
 * Collections in the UI map to backend folders.
 */
export class OrganizationService {
  /**
   * Fetch all tags for the authenticated user.
   * GET /api/tags
   */
  static async getUserTags(token: string): Promise<Tag[]> {
    const response = await apiRequest<TagListResponse>("/api/tags", {
      method: "GET",
      token,
    });
    return response.tags.map(toTag);
  }

  /**
   * Create a user tag.
   * POST /api/tags
   */
  static async createTag(token: string, name: string): Promise<Tag> {
    const response = await apiRequest<TagListResponse["tags"][number]>(
      "/api/tags",
      {
        method: "POST",
        body: { name },
        token,
      },
    );
    return toTag(response);
  }

  /**
   * Update the tags on a specific media item.
   * PATCH /api/media/:id/tags
   */
  static async updateMediaTags(
    token: string,
    mediaItemId: string,
    tagIds: string[],
  ): Promise<void> {
    return apiRequest<void>(
      `/api/media/${encodeURIComponent(mediaItemId)}/tags`,
      {
        method: "PATCH",
        body: { tag_ids: tagIds },
        token,
      },
    );
  }

  /**
   * Fetch all collections for the authenticated user.
   * GET /api/folders
   */
  static async getUserCollections(token: string): Promise<Collection[]> {
    const response = await apiRequest<FolderListResponse>("/api/folders", {
      method: "GET",
      token,
    });
    return response.folders.map(toCollection);
  }

  /**
   * Fetch the media items stored inside a collection.
   *
   * The backend `folder_id` filter is inclusive of sub-folders, so callers that
   * want only the media stored *directly* in a collection (the file-explorer
   * behaviour, where sub-collections are surfaced as folders) should keep the
   * rows whose `folder_id` equals the requested collection id.
   *
   * GET /api/media?folder_id=:collectionId&limit=:limit
   */
  static async getCollectionMedia(
    token: string,
    collectionId: string,
    limit = 100,
  ): Promise<MediaListItem[]> {
    const params = new URLSearchParams();
    params.set("folder_id", collectionId);
    params.set("limit", String(limit));
    const response = await apiRequest<MediaListResponse>(
      `/api/media?${params.toString()}`,
      { method: "GET", token },
    );
    return response.items;
  }

  /**
   * Set the collection for a specific media item.
   * PATCH /api/media/:id
   */
  static async setMediaCollection(
    token: string,
    mediaItemId: string,
    collectionId: string | null,
  ): Promise<void> {
    return apiRequest<void>(
      `/api/media/${encodeURIComponent(mediaItemId)}`,
      {
        method: "PATCH",
        body: { folder_id: collectionId },
        token,
      },
    );
  }

  /**
   * Create a new collection.
   * POST /api/folders
   */
  static async createCollection(
    token: string,
    name: string,
    parentId?: string | null,
  ): Promise<Collection> {
    const response = await apiRequest<FolderResponse>("/api/folders", {
      method: "POST",
      body: { name, parent_folder_id: parentId ?? null },
      token,
    });
    return toCollection(response);
  }
}
