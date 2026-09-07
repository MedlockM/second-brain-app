/**
 * Types for tags and folders (media organization).
 */

export interface Tag {
  id: string;
  name: string;
  count: number;
  color?: string | null;
  created_at?: string;
  updated_at?: string;
}

/**
 * A folder, exactly as `GET /api/folders` returns it — the field names are the
 * API's own, so nothing between the wire and the screen renames anything.
 */
export interface Folder {
  id: string;
  name: string;
  /**
   * Items stored *directly* in this folder, counted server-side from the durable
   * `user_media` library (task-220) — so an item whose processing job has
   * expired still counts.
   */
  media_count: number;
  parent_folder_id?: string | null;
  is_default: boolean;
  created_at: string;
  updated_at: string;
}
