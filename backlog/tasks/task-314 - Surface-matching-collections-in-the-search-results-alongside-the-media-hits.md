---
id: task-314
title: 'Surface matching collections in the search results, alongside the media hits'
status: Done
assignee: []
created_date: '2026-08-21 03:58'
updated_date: '2026-08-21 12:00'
labels:
  - mobile
  - search
  - feature
dependencies: []
priority: medium
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
## Context

Measured on `main` at `65d578e` on 2026-08-21, in `mobile/app/(tabs)/search.tsx` (1076 lines).

The Library tab has **two mutually exclusive bodies**, switched on whether a query is typed
(`search.tsx:334-370`):

- **Empty query** → `LibraryState`: a `Collections` grid of tiles in the list header
  (`LibraryHeader`, `search.tsx:572-628`) followed by an `All media` section listing every
  saved item.
- **Non-empty query** → the Algolia body: a flat `FlatList` of `ResultCard` hits from
  `GET /api/search/transcripts`, with no `Collections` section at all.

So a user who types the name of one of their own collections gets, at best, the media that
happen to mention that word in their transcript — and never the collection itself. Collections
become unreachable by name the moment the search bar is used, even though the full folder list
is already in memory: `loadCollections()` (`search.tsx:208-227`) runs on every focus,
regardless of the query.

## Scope

Keep **both** sections on screen while a query is typed. Same two headings as the library body,
same tiles, same rows:

- **`Collections`** — the collections whose name matches the query, filtered **client-side** from
  the already-loaded folder list. No new endpoint, no Algolia call for collections.
- **`All media`** — the Algolia hits, exactly as today. The lexical search behaviour, the ranking,
  the highlight snippets and the `ResultCard` layout are **not** touched.

### Matching rule

The query is split on whitespace, and a collection matches when **every** token is a substring of
its name. Comparison is case- and accent-insensitive (lowercase + NFD diacritic strip; Hermes
supports both, `Intl` is already used in `mobile/src/lib/planCopy.ts`). "recipes vegan" therefore
matches `Vegan recipes`, and so does "veg". The helper belongs next to the tree code
(`mobile/src/lib/collectionTree.ts` or a sibling module in `mobile/src/lib/`), not inlined in the
screen.

The filter runs over the **whole tree**, not only the roots: `buildCollectionTree` returns
`nodeById`, and a nested collection whose name matches must surface just like a root one. The
default folder is included too, matched on its **display** label `Unsorted`
(`DEFAULT_COLLECTION_LABEL`) rather than on its stored `Uncategorized` name — that is the only
name the user has ever seen. Matches are sorted by name, `localeCompare`, as the library grid is.

Tapping a tile opens `/media/collections/[id]` through the existing `handleOpenCollection`.

### The collections half must not wait on Algolia

Filtering is local and instant; the hits are a debounced network round-trip. Today a single
full-screen `LoadingState` (`search.tsx:335`) blanks everything while the request is in flight,
and a single full-screen `ErrorState` replaces everything when it fails. Neither may hide the
collections any more:

- **While the search request is in flight**, the matching collections are already on screen; only
  the `All media` slot carries the spinner.
- **When the search request fails**, the collections stay, and the error is stated in the
  `All media` slot (the `InlineErrorCard` pattern the library body already uses for a half that
  failed).
- The `Collections` section keeps its own existing loading / error / retry handling
  (`collectionsLoading`, `collectionsError`, `handleRetryCollections`) — a folder list that has
  not arrived yet is not an empty result.

### Empty states

- Collections match, no media hit → the `Collections` section renders, and the "no matches for X"
  message sits in the `All media` slot instead of taking the whole screen.
- Nothing matches on either side → the full-screen `NoResultsState` as today.
- No collection matches but media hits exist → the `Collections` section is **not** rendered at
  all (no empty heading, no "no collection matches" line); the media rows keep the screen.

## Not in scope

- The Algolia query, its ranking, or any backend change. This is a mobile-only task.
- Searching collections by their **description** or by the media they contain — names only.
- Showing the parent path or a media count on a matching tile.

## Owner notes (not acceptance criteria)

**Visual check on device**: with a query typed, confirm the collections grid and the hits share
one vertical scroll under the floating search pill, and that the grid does not push the hits
off-screen when many collections match (the cap is `MAX_FOLDERS_PER_USER = 50`).
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 Typing a query in mobile/app/(tabs)/search.tsx renders a Collections section above the All media section: both headings are present in the search body, not only in the empty-query library body
- [x] #2 A collection is listed when every whitespace-separated token of the query is a substring of its name, compared case- and accent-insensitively; the matcher is a named exported helper under mobile/src/lib/ and is not inlined in the screen component
- [x] #3 The filter runs over the full collection tree from buildCollectionTree's nodeById, so a nested collection matches like a root one, and the default folder is matched on its DEFAULT_COLLECTION_LABEL display name rather than its stored Uncategorized name; matches are sorted by name with localeCompare
- [x] #4 Matching collections are filtered from the already-loaded folder list with no new network request: grep over the diff shows no new endpoint call and mobile/src/services/searchService.ts is unchanged
- [x] #5 Tapping a matching collection tile navigates to /media/collections/[id] through the same handler the library grid uses
- [x] #6 While the Algolia request is in flight, the matching collections stay rendered and the spinner is confined to the All media slot: the full-screen LoadingState no longer covers the whole search body
- [x] #7 When the Algolia request fails, the matching collections stay rendered and the failure is stated inside the All media slot via the existing InlineErrorCard pattern, with the full-screen ErrorState reserved for nothing else on screen
- [x] #8 With collection matches but zero media hits, the no-matches message occupies the All media slot only; with zero matches on both sides, the full-screen NoResultsState renders as before
- [x] #9 With zero collection matches and at least one media hit, no Collections heading and no placeholder text are rendered
- [x] #10 The Collections section keeps its own collectionsLoading / collectionsError / retry handling while a query is typed, so a folder list that failed to load shows its retry card instead of reading as zero matches
- [x] #11 The Algolia call, the ResultCard layout and the highlight rendering are unchanged: mobile/src/services/searchService.ts and the ResultCard component are untouched by the diff
- [x] #12 npm run typecheck and npm run lint are clean in mobile/
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
## Le helper

`mobile/src/lib/collectionSearch.ts`, deux fonctions exportées :

- `normalizeForSearch(value)` — NFD puis suppression de la plage combinante `\u0300-\u036f` puis minuscules. La plage est écrite en clair plutôt qu'avec `\p{Diacritic}`, que Hermes ne reconnaît pas.
- `filterCollectionsByName(collections, query)` — la requête est découpée sur les blancs, chaque token doit être une sous-chaîne du nom normalisé. Le dossier par défaut est comparé sur `DEFAULT_COLLECTION_LABEL` (« Unsorted ») et ressort en portant ce label, jamais son `Uncategorized` stocké. Tri final `localeCompare`.

Les tokens vides sont écartés **après** normalisation : sans ça une requête réduite à un signe diacritique (`"´"`) devenait un token vide, et `includes("")` fait matcher toutes les collections.

## L'écran

`allCollections` est un nouvel état alimenté par `Array.from(tree.nodeById.values())` dans `loadCollections`. La liste `roots` déjà présente ne convenait pas : une collection imbriquée n'y figure pas, et l'AC #3 demande qu'elle remonte comme une racine. Le filtre tourne sur `query`, pas sur `debouncedQuery` — c'est une passe sur une liste en mémoire, elle n'a aucune raison d'attendre le round-trip réseau.

Le corps de l'écran bascule désormais sur `query.trim()` et non plus sur `hasSearched`.

**`hasSearched` est remplacé par `settledQuery: string | null`**, la requête à laquelle les hits affichés répondent. C'est ce qui rend `isPending = isLoading || settledQuery !== query.trim()` juste pendant la fenêtre de debounce, là où `isLoading` est encore `false` alors que les hits à l'écran sont périmés. Sans ça le slot `All media` affichait « No matches » pendant les 300 ms de debounce, à chaque frappe.

`LoadingState` (plein écran, « Searching… ») est **supprimé** : il n'a plus d'appelant, le spinner vivant dans le slot. `ErrorState` et `NoResultsState` sont conservés pour le seul cas où la section Collections n'est pas rendue du tout — sinon ils masqueraient les collections trouvées.

`showCollections = collectionsLoading || collectionsError !== null || collections.length > 0` porte l'AC #10 : une liste de dossiers en cours de chargement ou en échec garde son titre et sa carte de retry, elle ne se lit pas comme « zéro correspondance ».

## Le retry de la recherche

L'AC #7 demande une `InlineErrorCard`, qui exige un `onRetry`. La recherche était déclenchée par un `useEffect` sans point d'entrée rejouable. Premier essai : extraire `performSearch` en `useCallback` appelé depuis l'effet — refusé par `react-hooks/set-state-in-effect` (« Calling setState synchronously within an effect can trigger cascading renders »), le lint suivant l'appel jusqu'au `setIsLoading(true)` une fois la fonction nommée hors de l'effet. Retenu à la place : un compteur `searchAttempt` dans les dépendances de l'effet, que `handleRetrySearch` incrémente. La fonction reste locale à l'effet, comme avant.

## Espacement

Le conteneur de la liste de recherche (`resultsList`) porte déjà `paddingHorizontal` et `gap`, contrairement à celui de la bibliothèque. D'où deux ajouts : `inlineErrorCardFlush` (annule le `marginHorizontal` de la carte, qui doublait la gouttière) et `searchSectionHeading` (annule le `marginBottom` du titre « All media », que le `gap` du conteneur fournit déjà). Le style `resultsCount` disparaît avec le compteur autonome : le nombre de résultats passe à droite du titre « All media », dans le `mediaSectionCount` que la bibliothèque utilise pour son propre compte.

## Vérifications

- `npm run typecheck` clean ; `npm run lint` 0 erreur, 2 warnings préexistants sans rapport (`digest.tsx` `CARD_WIDTH` inutilisé, `purchaseService.ts` `any`).
- `git status` sur `mobile/src/services/` et `mobile/src/components/` : vide — `searchService.ts` et les composants partagés ne sont pas touchés (AC #4, #11). Le composant `ResultCard`, local au fichier, n'est modifié que par son appelant (`onOpenMedia` au lieu d'un `router.push` inline).
- Le diff n'introduit aucun appel réseau : la seule ligne `Service.` ajoutée est le `SearchService.searchTranscripts` déplacé.

## Non vérifiable depuis le worktree

Le rendu visuel — grille et hits dans un même scroll sous la pilule flottante, et la hauteur que prend la grille quand beaucoup de collections matchent (plafond `MAX_FOLDERS_PER_USER = 50`). C'est la note owner de la description.
<!-- SECTION:NOTES:END -->
