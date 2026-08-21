import { DEFAULT_COLLECTION_LABEL, type CollectionNode } from "./collectionTree";

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
 * The collections whose name matches every token of the query.
 *
 * The query is split on whitespace and each token has to be a substring of the
 * name, so "recipes vegan" finds `Vegan recipes` whatever the word order, and a
 * prefix as short as "veg" is enough. Names only -- descriptions and the media
 * a collection holds are out of scope.
 *
 * Callers pass the flat `nodeById` values of `buildCollectionTree`, so a nested
 * collection surfaces exactly like a root one. The default folder is matched on
 * the label the user has actually seen ("Unsorted"), never on its stored
 * `Uncategorized` name, and is returned carrying that label.
 */
export function filterCollectionsByName(
  collections: Iterable<CollectionNode>,
  query: string,
): CollectionNode[] {
  const tokens = query
    .split(/\s+/)
    .map(normalizeForSearch)
    .filter((token) => token.length > 0);

  if (tokens.length === 0) return [];

  const matches: CollectionNode[] = [];

  for (const collection of collections) {
    const displayName = collection.is_default
      ? DEFAULT_COLLECTION_LABEL
      : collection.name;
    const haystack = normalizeForSearch(displayName);

    if (tokens.every((token) => haystack.includes(token))) {
      matches.push(
        collection.is_default
          ? { ...collection, name: displayName }
          : collection,
      );
    }
  }

  matches.sort((a, b) => a.name.localeCompare(b.name));
  return matches;
}
