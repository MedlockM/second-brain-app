import { apiRequest } from "./apiClient";
import type { Tag, Collection } from "../types/organization";
import type { MediaListItem, MediaSortDirection } from "../types/media";

interface MediaListResponse {
  status: string;
  items: MediaListItem[];
  total: number;
  next_cursor?: string | null;
  has_more: boolean;
}

interface TagListResponse {
  tags: {
    id: string;
    name: string;
    color?: string | null;
    created_at: string;
    updated_at: string;
  }[];
}

interface FolderResponse {
  id: string;
  name: string;
  parent_folder_id?: string | null;
  is_default: boolean;
  /**
   * Items stored *directly* in this folder, counted server-side from the durable
   * `user_media` library (task-220) — so an item whose processing job has
   * expired still counts. `GET /api/folders` has returned it all along; this
   * interface simply did not declare it, and `toCollection` overwrote it with a
   * zero, which is why every collection read `0 items` everywhere.
   */
  media_count?: number;
  created_at: string;
  updated_at: string;
}

interface FolderListResponse {
  folders: FolderResponse[];
}

interface FolderDeleteResponse {
  deleted_folders: number;
  moved_media_count: number;
  default_folder_id: string;
}

/** What deleting a collection actually did, in the vocabulary of the UI. */
export interface CollectionDeletion {
  /** The collection itself plus every sub-collection under it. */
  deleted_collections: number;
  /** Items reassigned to the default collection. None were deleted. */
  moved_media_count: number;
  default_collection_id: string;
}

function toTag(tag: TagListResponse["tags"][number]): Tag {
  return {
    id: tag.id,
    name: tag.name,
    color: tag.color ?? null,
    created_at: tag.created_at,
    updated_at: tag.updated_at,
    // Genuinely zero: `GET /api/tags` exposes no per-tag count, unlike
    // `/api/folders`. Not the same defect as the folder one fixed above — do not
    // "fix" this one by symmetry without adding the count server-side first.
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
    updated_at: folder.updated_at,
    media_count: folder.media_count ?? 0,
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
  static async getUserTags(): Promise<Tag[]> {
    const response = await apiRequest<TagListResponse>("/api/tags", {
      method: "GET",
    });
    return response.tags.map(toTag);
  }

  /**
   * Create a user tag.
   * POST /api/tags
   */
  static async createTag(name: string): Promise<Tag> {
    const response = await apiRequest<TagListResponse["tags"][number]>(
      "/api/tags",
      {
        method: "POST",
        body: { name },
      },
    );
    return toTag(response);
  }

  /**
   * Update the tags on a specific media item.
   * PATCH /api/media/:id/tags
   */
  static async updateMediaTags(
    mediaItemId: string,
    tagIds: string[],
  ): Promise<void> {
    return apiRequest<void>(
      `/api/media/${encodeURIComponent(mediaItemId)}/tags`,
      {
        method: "PATCH",
        body: { tag_ids: tagIds },
      },
    );
  }

  /**
   * Fetch all collections for the authenticated user.
   * GET /api/folders
   */
  static async getUserCollections(): Promise<Collection[]> {
    const response = await apiRequest<FolderListResponse>("/api/folders", {
      method: "GET",
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
   * `sort` is the chronological direction of the page (task-323). It defaults to
   * the server's own default — newest first — and `"asc"` is what a triage pass
   * through the unsorted backlog asks for: reversing a page client-side would
   * only reverse *that page*, leaving the oldest item on the last one.
   *
   * GET /api/media?folder_id=:collectionId&limit=:limit&sort=:sort
   */
  static async getCollectionMedia(
    collectionId: string,
    options: { limit?: number; sort?: MediaSortDirection } = {},
  ): Promise<MediaListItem[]> {
    const params = new URLSearchParams();
    params.set("folder_id", collectionId);
    params.set("limit", String(options.limit ?? 100));
    if (options.sort) {
      params.set("sort", options.sort);
    }
    const response = await apiRequest<MediaListResponse>(
      `/api/media?${params.toString()}`,
      { method: "GET" },
    );
    return response.items;
  }

  /**
   * Set the collection for a specific media item.
   * PATCH /api/media/:id
   */
  static async setMediaCollection(
    mediaItemId: string,
    collectionId: string | null,
  ): Promise<void> {
    return apiRequest<void>(
      `/api/media/${encodeURIComponent(mediaItemId)}`,
      {
        method: "PATCH",
        body: { folder_id: collectionId },
      },
    );
  }

  /**
   * Create a new collection.
   * POST /api/folders
   */
  static async createCollection(
    name: string,
    parentId?: string | null,
  ): Promise<Collection> {
    const response = await apiRequest<FolderResponse>("/api/folders", {
      method: "POST",
      body: { name, parent_folder_id: parentId ?? null },
    });
    return toCollection(response);
  }

  /**
   * Rename a collection, and only rename it.
   *
   * The body carries `name` alone on purpose: `PUT /api/folders/:id` decides
   * whether to reparent by looking at whether `parent_folder_id` is *present* in
   * the JSON (`payload.model_fields_set`), so sending it as `null` would move the
   * collection to the root as a side effect of a rename.
   *
   * PUT /api/folders/:id
   */
  static async renameCollection(
    collectionId: string,
    name: string,
  ): Promise<Collection> {
    const response = await apiRequest<FolderResponse>(
      `/api/folders/${encodeURIComponent(collectionId)}`,
      {
        method: "PUT",
        body: { name },
      },
    );
    return toCollection(response);
  }

  /**
   * Delete a collection and its sub-collections.
   *
   * No media is destroyed: the backend reassigns every item of the deleted
   * subtree to the default collection first, and answers with how many folders
   * went and how many items moved.
   *
   * DELETE /api/folders/:id
   */
  static async deleteCollection(
    collectionId: string,
  ): Promise<CollectionDeletion> {
    const response = await apiRequest<FolderDeleteResponse>(
      `/api/folders/${encodeURIComponent(collectionId)}`,
      { method: "DELETE" },
    );
    return {
      deleted_collections: response.deleted_folders,
      moved_media_count: response.moved_media_count,
      default_collection_id: response.default_folder_id,
    };
  }
}
