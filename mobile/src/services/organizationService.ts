import { apiRequest } from "./apiClient";
import type { Tag, Folder } from "../types/organization";
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

interface FolderListResponse {
  folders: Folder[];
}

/**
 * What deleting a folder actually did, straight off `DELETE /api/folders/:id`.
 */
export interface FolderDeletion {
  /** The folder itself plus every subfolder under it. */
  deleted_folders: number;
  /** Items reassigned to the default folder. None were deleted. */
  moved_media_count: number;
  default_folder_id: string;
}

function toTag(tag: TagListResponse["tags"][number]): Tag {
  return {
    id: tag.id,
    name: tag.name,
    color: tag.color ?? null,
    created_at: tag.created_at,
    updated_at: tag.updated_at,
    // Genuinely zero: `GET /api/tags` exposes no per-tag count, unlike
    // `/api/folders`, which counts server-side. Do not "fix" this one by
    // symmetry without adding the count server-side first.
    count: 0,
  };
}

/**
 * Service for tags and folders management.
 *
 * Folders cross the wire under their API field names and are handed to the
 * screens as they came: there is no vocabulary to translate any more, so there
 * is no mapper here either.
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
   * Fetch all folders for the authenticated user.
   * GET /api/folders
   */
  static async getUserFolders(): Promise<Folder[]> {
    const response = await apiRequest<FolderListResponse>("/api/folders", {
      method: "GET",
    });
    return response.folders;
  }

  /**
   * Fetch the media items stored inside a folder.
   *
   * The backend `folder_id` filter is inclusive of sub-folders, so callers that
   * want only the media stored *directly* in a folder (the file-explorer
   * behaviour, where subfolders are surfaced as folders) should keep the
   * rows whose `folder_id` equals the requested folder id.
   *
   * `sort` is the chronological direction of the page (task-323). It defaults to
   * the server's own default — newest first — and `"asc"` is what a triage pass
   * through the unsorted backlog asks for: reversing a page client-side would
   * only reverse *that page*, leaving the oldest item on the last one.
   *
   * GET /api/media?folder_id=:folderId&limit=:limit&sort=:sort
   */
  static async getFolderMedia(
    folderId: string,
    options: { limit?: number; sort?: MediaSortDirection } = {},
  ): Promise<MediaListItem[]> {
    const params = new URLSearchParams();
    params.set("folder_id", folderId);
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
   * Set the folder for a specific media item.
   * PATCH /api/media/:id
   */
  static async setMediaFolder(
    mediaItemId: string,
    folderId: string | null,
  ): Promise<void> {
    return apiRequest<void>(
      `/api/media/${encodeURIComponent(mediaItemId)}`,
      {
        method: "PATCH",
        body: { folder_id: folderId },
      },
    );
  }

  /**
   * Create a new folder.
   * POST /api/folders
   */
  static async createFolder(
    name: string,
    parentId?: string | null,
  ): Promise<Folder> {
    return apiRequest<Folder>("/api/folders", {
      method: "POST",
      body: { name, parent_folder_id: parentId ?? null },
    });
  }

  /**
   * Rename a folder, and only rename it.
   *
   * The body carries `name` alone on purpose: `PUT /api/folders/:id` decides
   * whether to reparent by looking at whether `parent_folder_id` is *present* in
   * the JSON (`payload.model_fields_set`), so sending it as `null` would move the
   * folder to the root as a side effect of a rename.
   *
   * PUT /api/folders/:id
   */
  static async renameFolder(folderId: string, name: string): Promise<Folder> {
    return apiRequest<Folder>(
      `/api/folders/${encodeURIComponent(folderId)}`,
      {
        method: "PUT",
        body: { name },
      },
    );
  }

  /**
   * Delete a folder and its subfolders.
   *
   * No media is destroyed: the backend reassigns every item of the deleted
   * subtree to the default folder first, and answers with how many folders
   * went and how many items moved.
   *
   * DELETE /api/folders/:id
   */
  static async deleteFolder(folderId: string): Promise<FolderDeletion> {
    return apiRequest<FolderDeletion>(
      `/api/folders/${encodeURIComponent(folderId)}`,
      { method: "DELETE" },
    );
  }
}
