/**
 * Types for tags and collections (media organization).
 */

export interface Tag {
  id: string;
  name: string;
  count: number;
}

export interface Collection {
  id: string;
  name: string;
  media_count: number;
  created_at: string;
  parent_id?: string | null;
  children?: Collection[];
}
