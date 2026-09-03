/**
 * Types for tags and collections (media organization).
 */

export interface Tag {
  id: string;
  name: string;
  count: number;
  color?: string | null;
  created_at?: string;
  updated_at?: string;
}

export interface Collection {
  id: string;
  name: string;
  media_count: number;
  updated_at?: string;
  parent_id?: string | null;
  parent_folder_id?: string | null;
  is_default?: boolean;
  path?: string;
  children?: Collection[];
}
