import { Colors } from "../constants/theme";
import type { Folder } from "../types/organization";

/**
 * Label shown for the backend default folder, whose stored name is
 * `Uncategorized`. Only the display differs; the backend name is untouched.
 */
export const DEFAULT_FOLDER_LABEL = "Unsorted";

/**
 * Tint of the default folder wherever it is listed, so it reads as a system
 * container and not as one more user folder.
 *
 * The olive-grey `outline` tone instead of the amber accent, which DESIGN.md
 * reserves for "high-value interactions (CTAs, active states) and meaningful
 * accents" -- a catch-all bin is none of those. `textMuted` was the other
 * candidate but falls under the 3:1 that WCAG 1.4.11 asks of a non-text
 * graphic (2.9:1 on `surface`); `outline` clears it on every system surface.
 *
 * Single source of truth: every screen showing the default folder reads this.
 */
export const DEFAULT_FOLDER_TINT = Colors.outline;

export interface FolderNode extends Folder {
  children: FolderNode[];
  /** Number of media stored directly in this folder. */
  directMediaCount: number;
}

/**
 * Build a navigable tree of user folders from the flat folder list returned
 * by the backend.
 *
 * - The default folder (stored as `Uncategorized`, shown as "Unsorted") is kept
 *   so unsorted media stay reachable; callers decide how to surface it.
 * - `directCountById` lets the caller seed the per-folder media counts that
 *   were computed client-side (the folder list endpoint does not return them).
 */
export function buildFolderTree(
  folders: Folder[],
  directCountById?: Map<string, number>,
): {
  roots: FolderNode[];
  defaultFolder: FolderNode | null;
  nodeById: Map<string, FolderNode>;
} {
  const nodeById = new Map<string, FolderNode>();

  for (const folder of folders) {
    nodeById.set(folder.id, {
      ...folder,
      children: [],
      directMediaCount: directCountById?.get(folder.id) ?? 0,
    });
  }

  const roots: FolderNode[] = [];
  let defaultFolder: FolderNode | null = null;

  for (const node of nodeById.values()) {
    if (node.is_default) {
      defaultFolder = node;
    }
    const parentId = node.parent_folder_id ?? null;
    const parent = parentId ? nodeById.get(parentId) : null;
    if (parent && parent.id !== node.id) {
      parent.children.push(node);
    } else if (!node.is_default) {
      roots.push(node);
    }
  }

  const sortByName = (items: FolderNode[]) => {
    items.sort((a, b) => a.name.localeCompare(b.name));
    for (const item of items) {
      if (item.children.length) sortByName(item.children);
    }
  };
  sortByName(roots);

  return { roots, defaultFolder, nodeById };
}

/** One user folder, named by the full trail down to it. */
export interface FolderPath {
  id: string;
  /** Leaf name, for a surface that only has room for one word. */
  name: string;
  /** `Parent / Child / Leaf`, the breadcrumb the folder picker shows. */
  path: string;
}

/** Separator of a folder breadcrumb, shared with the folder picker. */
const PATH_SEPARATOR = " / ";

/**
 * Every non-default folder as a flat, depth-first list of breadcrumbs.
 *
 * For the surfaces that ask "which folder?" and nothing else: a flat list is
 * answered in one glance where a tree has to be navigated, and the trail is what
 * separates two leaves that happen to share a name. Built on `buildFolderTree`
 * so the ordering (alphabetical, parents before their children) and the exclusion
 * of the default folder come from one place.
 */
export function flattenFolderPaths(
  folders: Folder[],
): FolderPath[] {
  const { roots } = buildFolderTree(folders);
  const flat: FolderPath[] = [];

  const walk = (nodes: FolderNode[], prefix: string) => {
    for (const node of nodes) {
      const path = prefix ? `${prefix}${PATH_SEPARATOR}${node.name}` : node.name;
      flat.push({ id: node.id, name: node.name, path });
      if (node.children.length) walk(node.children, path);
    }
  };
  walk(roots, "");

  return flat;
}
