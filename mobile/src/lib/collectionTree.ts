import type { Collection } from "../types/organization";

/**
 * Label shown for the backend default folder, whose stored name is
 * `Uncategorized`. Only the display differs; the backend name is untouched.
 */
export const DEFAULT_COLLECTION_LABEL = "Unsorted";

export interface CollectionNode extends Collection {
  children: CollectionNode[];
  /** Number of media stored directly in this collection. */
  directMediaCount: number;
}

/**
 * Build a navigable tree of user collections from the flat folder list returned
 * by the backend.
 *
 * - The default folder (stored as `Uncategorized`, shown as "Unsorted") is kept
 *   so unsorted media stay reachable; callers decide how to surface it.
 * - `directCountById` lets the caller seed the per-collection media counts that
 *   were computed client-side (the folder list endpoint does not return them).
 */
export function buildCollectionTree(
  collections: Collection[],
  directCountById?: Map<string, number>,
): {
  roots: CollectionNode[];
  defaultCollection: CollectionNode | null;
  nodeById: Map<string, CollectionNode>;
} {
  const nodeById = new Map<string, CollectionNode>();

  for (const collection of collections) {
    nodeById.set(collection.id, {
      ...collection,
      children: [],
      directMediaCount: directCountById?.get(collection.id) ?? 0,
    });
  }

  const roots: CollectionNode[] = [];
  let defaultCollection: CollectionNode | null = null;

  for (const node of nodeById.values()) {
    if (node.is_default) {
      defaultCollection = node;
    }
    const parentId = node.parent_id ?? node.parent_folder_id ?? null;
    const parent = parentId ? nodeById.get(parentId) : null;
    if (parent && parent.id !== node.id) {
      parent.children.push(node);
    } else if (!node.is_default) {
      roots.push(node);
    }
  }

  const sortByName = (items: CollectionNode[]) => {
    items.sort((a, b) => a.name.localeCompare(b.name));
    for (const item of items) {
      if (item.children.length) sortByName(item.children);
    }
  };
  sortByName(roots);

  return { roots, defaultCollection, nodeById };
}
