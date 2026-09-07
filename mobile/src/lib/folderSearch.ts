import { DEFAULT_FOLDER_LABEL, type FolderNode } from "./folderTree";

/**
 * Fold a name down to what a search should compare: no case, no diacritics.
 *
 * NFD splits an accented letter into its base plus a combining mark, and the
 * mark is then dropped, so "Recettes vegan" is reachable by typing "vegan" as
 * much as by "végan". Hermes ships `String.prototype.normalize`, and the
 * combining range is spelled out rather than through a `\p{Diacritic}` escape,
 * which the engine does not support.
 */
export function normalizeForSearch(value: string): string {
  return value
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .toLowerCase();
}

/**
 * The folders whose name matches every token of the query.
 *
 * The query is split on whitespace and each token has to be a substring of the
 * name, so "recipes vegan" finds `Vegan recipes` whatever the word order, and a
 * prefix as short as "veg" is enough. Names only -- descriptions and the media
 * a folder holds are out of scope.
 *
 * Callers pass the flat `nodeById` values of `buildFolderTree`, so a nested
 * folder surfaces exactly like a root one. The default folder is matched on
 * the label the user has actually seen ("Unsorted"), never on its stored
 * `Uncategorized` name, and is returned carrying that label.
 */
export function filterFoldersByName(
  folders: Iterable<FolderNode>,
  query: string,
): FolderNode[] {
  const tokens = query
    .split(/\s+/)
    .map(normalizeForSearch)
    .filter((token) => token.length > 0);

  if (tokens.length === 0) return [];

  const matches: FolderNode[] = [];

  for (const folder of folders) {
    const displayName = folder.is_default
      ? DEFAULT_FOLDER_LABEL
      : folder.name;
    const haystack = normalizeForSearch(displayName);

    if (tokens.every((token) => haystack.includes(token))) {
      matches.push(
        folder.is_default
          ? { ...folder, name: displayName }
          : folder,
      );
    }
  }

  matches.sort((a, b) => a.name.localeCompare(b.name));
  return matches;
}
