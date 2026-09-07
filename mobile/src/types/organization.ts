/**
 * Types for collections (media organization).
 */

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
