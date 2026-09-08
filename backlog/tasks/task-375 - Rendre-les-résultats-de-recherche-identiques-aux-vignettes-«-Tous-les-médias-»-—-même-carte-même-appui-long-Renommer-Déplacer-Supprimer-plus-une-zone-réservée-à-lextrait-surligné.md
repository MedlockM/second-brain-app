---
id: task-375
title: >-
  Rendre les résultats de recherche identiques aux vignettes « Tous les médias »
  — même carte, même appui long (Renommer/Déplacer/Supprimer), plus une zone
  réservée à l'extrait surligné
status: Done
assignee: []
created_date: '2026-09-07 13:48'
updated_date: '2026-09-08 08:54'
labels:
  - mobile
  - ui
  - search
  - backend
dependencies:
  - task-373
priority: medium
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
## Le constat

L'onglet Recherche affiche la même notion — un média sauvegardé — sous **deux vignettes différentes**, selon qu'une requête est tapée ou non :

- **sans requête**, la section « Tous les médias » rend `MediaListCard` (`mobile/src/components/MediaListCard.tsx`) : cover 16:9 (112×63) avec repli sur l'icône de type, badge de type coloré + temps relatif (`getRelativeTime`), titre sur 2 lignes, sous-titre `creator_name` avec repli sur le domaine de la source, retour de pression (`cardPressed`, scale 0.98), et **appui long** ouvrant l'`AnchoredContextMenu` avec Renommer / Déplacer / Supprimer (`useMediaActions`) ;
- **avec une requête**, chaque hit est rendu par `ResultCard`, un composant local de `mobile/app/(tabs)/search.tsx` (~ligne 1176) : il n'emprunte à `MediaListCard` que les constantes `COVER_WIDTH` / `COVER_HEIGHT`. Tout le reste diverge — carte bordée (`borderWidth` hairline + `outlineVariant`) au lieu d'une carte pleine, padding différent, aucun retour de pression, ligne meta faite d'une icône de plateforme et d'un libellé en majuscules au lieu du badge de type, date calculée par un `formatTimestamp` local au lieu de `getRelativeTime`, sous-titre sans repli sur le domaine, et **aucun appui long** : un résultat de recherche ne peut être ni renommé, ni déplacé, ni supprimé.

Cet écart est un choix explicite de deux tâches précédentes, que **cette tâche renverse** :

- task-317 (Done) a décidé de ne *pas* étendre `MediaListCard` et de partager seulement ses deux constantes de cover ;
- task-319 (Done), AC #4, a décidé que les vignettes de résultats de recherche n'ouvriraient *pas* le menu d'actions, au motif qu'un média y est « un match qu'on lit, pas un objet qu'on range ».

La décision de l'owner est l'inverse : une vignette de résultat doit ressembler et se comporter **comme** une vignette de « Tous les médias ».

## Ce qu'on veut

Une seule vignette média dans l'onglet Recherche. Le rendu et le comportement d'un résultat sont ceux de « Tous les médias » — mêmes éléments, même style, même appui long ouvrant Renommer / Déplacer / Supprimer — **plus** une zone réservée à l'extrait de transcript surligné, qui est la seule chose qu'un résultat a de plus et la raison d'être de la recherche.

L'extrait doit rester *lisible et utile* : le fragment qui correspond à la requête doit être visible dans les lignes affichées, avec du texte autour de lui. Un extrait tronqué avant le surlignage ne dit rien à l'utilisateur.

## Ce qui manque côté API pour y arriver

`SearchHit` (`media_summarizer/api/endpoints/search.py`, et son miroir TS `mobile/src/services/searchService.ts`) ne porte pas tout ce qu'une vignette de bibliothèque affiche ni tout ce que le menu d'actions consomme :

- **le dossier du média** : sans lui, « Déplacer » préselectionnerait « Non trié » pour un média déjà rangé ;
- **l'URL de la source** : c'est le repli du sous-titre quand il n'y a pas de créateur ;
- **les dates de la ligne de bibliothèque** : le hit ne porte qu'un `created_at` unix issu de l'index, là où « Tous les médias » lit la date de la ligne. Deux dates différentes pour le même média sur deux surfaces de la même page, c'est précisément l'incohérence que la tâche corrige.

La lecture est **gratuite** : `load_display_details` (`media_summarizer/core/services/media_search_service.py:254`) charge déjà l'enregistrement `user_media` complet de chaque hit et n'en retient que quatre champs. Il suffit d'en retenir plus. C'est le principe posé par task-317 — la ligne de bibliothèque est la source de vérité de ce à quoi un média ressemble, l'index répond seulement « lesquels correspondent et où ».

## Le cas du hit orphelin

Supprimer un média ne le retire pas de l'index Algolia (constat de task-317, toujours vrai). Un tel hit revient sans ligne de bibliothèque : `load_display_details` ne lui associe rien et il retombe sur ce que l'index sait. Il n'y a alors **rien à renommer, déplacer ni supprimer** — l'appui long ne doit pas être offert sur ces vignettes. `onLongPress` est déjà une prop optionnelle de `MediaListCard`, exactement pour ce genre de cas.

## Périmètre

- `mobile/app/(tabs)/search.tsx` : `ResultCard` disparaît au profit de `MediaListCard`, et `SearchResultsState` câble l'appui long sur le `useMediaActions` que l'écran tient déjà pour « Tous les médias ».
- `mobile/src/components/MediaListCard.tsx` : une prop optionnelle porte la zone d'extrait. Aucune surface qui n'en passe pas ne doit changer d'aspect.
- La copie soulevée par le menu (`renderPreview`) est redessinée sur le rect mesuré : elle doit inclure l'extrait, sinon la copie est plus courte que la vignette pressée et le décalage se voit.
- Les deux listes que l'écran tient en mémoire — `results` et `media` — sont patchées ensemble sur un renommage et sur une suppression : elles montrent les mêmes médias, et effacer la requête ne doit pas remontrer l'état d'avant.
- Le `contentContainerStyle` de la liste de résultats (`resultsList`) porte aujourd'hui `paddingHorizontal` + `gap` là où la liste de bibliothèque laisse les marges à la carte — à réconcilier, sinon la gouttière est doublée.
- Backend : `load_display_details` et le modèle `SearchHit` sont élargis. Pas de nouvel endpoint, pas de champ ajouté à l'index Algolia, aucune réindexation.

## Hors périmètre

- Le `SourceRow` de `mobile/app/media/collections/[id].tsx`, volontairement plus compact, et les tuiles de Home.
- La désindexation d'un média supprimé (voir notes à l'owner).
- La pagination des résultats, les filtres, le total `found`.
- La sélection multiple.

## Contraintes

- Seulement des tokens existants de `mobile/src/constants/theme.ts`. Le surlignage garde `Colors.highlight` / `Colors.onHighlight` et passe toujours par `parseHighlightSnippet`.
- Toute nouvelle chaîne passe par `t()` et existe dans les **11** catalogues de `mobile/src/i18n/` (le typecheck échoue sur une clé manquante).
- Un échec réseau ne fait jamais disparaître un média qui existe encore.
- `cd mobile && npm run lint && npm run typecheck` clean ; `make lint` (ruff + mypy) clean.
- Pas de tests automatisés (règle projet).

## Notes à l'owner

- **PRÉREQUIS DE DÉPLOIEMENT** — les nouveaux champs de `GET /api/search/transcripts` n'arrivent qu'une fois `main` poussé et l'image Lambda redéployée. Avant ça, l'app tourne sur l'ancienne réponse : « Déplacer » préselectionne « Non trié » et le sous-titre n'a pas de repli sur le domaine.
- **VÉRIF VISUELLE** — sur simulateur iOS et émulateur Android : basculer entre la liste sans requête et la liste avec requête, et vérifier que la vignette est la même ; appui long sur un résultat (menu ancré, copie soulevée alignée sur la vignette) ; cycle complet Renommer / Déplacer / Supprimer depuis un résultat ; un résultat dont l'extrait est long, et un dont le match tombe en fin d'extrait.
- **SUPPRESSION** — irréversible passé la fenêtre de grâce (`docs/DATA_RETENTION.md`). Tester sur `-dev` avec un média jetable, jamais sur l'article persistant « Commonplace book ».
- **À DÉCIDER** — supprimer un média ne le désindexe pas : retaper la même requête après une suppression le ramène, sans cover et sans actions. Cette tâche rend le défaut visible puisqu'elle met la suppression à portée de la recherche. La désindexation reste à ouvrir en tâche séparée si vous la voulez.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 Le composant local ResultCard n'existe plus dans mobile/app/(tabs)/search.tsx : les résultats de recherche sont rendus par MediaListCard, et il ne reste aucune seconde implémentation de vignette média dans cet écran
- [x] #2 Une vignette de résultat affiche les mêmes éléments qu'une vignette de « Tous les médias » : cover 16:9 avec repli sur l'icône de type de média, badge de type coloré, temps relatif, titre sur 2 lignes, sous-titre creator_name avec repli sur le domaine de la source — le libellé de plateforme en majuscules et le formatTimestamp local de l'écran de recherche ont disparu
- [x] #3 Une vignette de résultat a la même surface, le même rayon, la même ombre, les mêmes marges et le même retour de pression (cardPressed) qu'une vignette de « Tous les médias » : aucun style propre aux résultats ne subsiste en dehors de la zone d'extrait
- [x] #4 La date affichée sur une vignette de résultat est produite par le même helper que « Tous les médias » (getRelativeTime) à partir de la date portée par la ligne de bibliothèque, de sorte qu'un même média affiche la même date sur les deux listes
- [x] #5 Un appui long sur une vignette de résultat ouvre le même AnchoredContextMenu que dans « Tous les médias », avec Renommer, Déplacer et Supprimer, servi par useMediaActions et non par une seconde implémentation des actions
- [x] #6 La copie soulevée par le menu (renderPreview) redessine la vignette pressée à l'identique, extrait compris, sur le rect mesuré
- [x] #7 « Déplacer » ouvre le sélecteur /media/collection avec le dossier courant du média préselectionné, lu sur la ligne de bibliothèque via la réponse de recherche et non remplacé par un défaut « Non trié »
- [x] #8 « Renommer » met à jour le titre du résultat dans la liste sans rechargement, et « Supprimer » ne retire le résultat de la liste qu'après confirmation du backend
- [x] #9 Un renommage ou une suppression déclenché depuis un résultat met aussi à jour la liste « Tous les médias » tenue par l'écran : effacer la requête ne remontre pas l'ancien titre ni le média supprimé
- [x] #10 Un échec réseau sur Renommer, Déplacer ou Supprimer affiche un message et laisse le média en place dans la liste des résultats
- [x] #11 Un hit dont la ligne de bibliothèque est absente (média supprimé, toujours présent dans l'index) n'offre pas l'appui long : aucune action n'est proposée sur un média qui n'existe plus
- [x] #12 L'extrait de transcript surligné reste affiché dans une zone dédiée sous la tête de la vignette, sur toute la largeur, bornée à un nombre fixe de lignes ; le choix de ce nombre est documenté dans les Implementation Notes
- [x] #13 Le segment surligné du premier extrait est toujours visible dans les lignes affichées, avec du texte de contexte de part et d'autre quand il en existe ; la mécanique retenue pour y parvenir est documentée dans les Implementation Notes
- [x] #14 La zone d'extrait est une prop optionnelle de MediaListCard : les surfaces qui n'en passent pas (Inbox, « Tous les médias », intérieur d'une collection) rendent une vignette inchangée
- [x] #15 GET /api/search/transcripts renvoie, lus sur la ligne de bibliothèque par load_display_details, le dossier du média, l'URL de sa source et ses dates ; le modèle Pydantic SearchHit et le type TS SearchHit les déclarent tous les deux
- [x] #16 L'indexation Algolia est inchangée : aucun champ ajouté aux documents, aucune réindexation nécessaire (git diff vide sur search_indexing.py et sur les workers d'indexation)
- [x] #17 Le surlignage passe toujours par parseHighlightSnippet et les tokens Colors.highlight / Colors.onHighlight ; aucune couleur ni recette d'ombre littérale n'est introduite, seuls les tokens de mobile/src/constants/theme.ts sont utilisés
- [x] #18 Toute nouvelle chaîne passe par t() et est présente dans les 11 catalogues de mobile/src/i18n/
- [x] #19 cd mobile && npm run lint && npm run typecheck sont clean, et make lint (ruff + mypy) est clean
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
## Delivered

- `ResultCard` and its three private helpers (`getSourceIcon`, `getSourceLabel`, `formatTimestamp`) are gone from `mobile/app/(tabs)/search.tsx`. Both bodies of the screen — the query-less "All media" list and the results list — render `MediaListCard`, and both are served by the single `useMediaActions` the screen already held. `MediaListCard` is now the only media vignette in the tab, which reverses task-317 (do not extend it) and task-319 AC#4 (no actions menu on a hit).
- `MediaListCard` became generic over a new exported `MediaCardItem`, the eight fields the card actually reads. A `SearchHit` carries no processing status and no triage blurb, and inventing values for fields nothing in the card reads would have been the first step back to two vignettes. Both `MediaListItem` and the hit projection satisfy the narrower contract.
- The screen projects every hit into one `MediaRow` (`hitToRow`) carrying `folder_id` for "Move", the excerpt, and an `isOrphan` flag. `onLongPress` is `undefined` when `isOrphan`, so a hit whose library row is gone keeps a bare tap.
- `handleMediaDeleted` and `handleMediaRenamed` patch `results` and `media` in the same callback. Both come from `useMediaActions`, which only fires them once the backend has answered — a failed rename or delete surfaces its error and leaves the row in both lists, so no extra code was needed for the network-failure criterion.
- Backend: `load_display_details` keeps four more fields off the `user_media` record it already loads whole (`source_url`, `folder_id`, `saved_at`, `updated_at`). `SearchHit` gained `source_url`, `folder_id`, `updated_at` and `in_library`, and `created_at` changed from the index's Unix int to the row's ISO string so a media prints the same age on both lists. `_iso_from_index_timestamp` renders the index timestamp as UTC ISO for an orphan hit, which keeps the field one type for the client. `search_indexing.py` and the indexing workers are untouched: no field added to a document, no reindex.

## Excerpt zone

- **Three lines** (`EXCERPT_LINES` in `MediaListCard.tsx`), which is what search results already showed. At 13px on an 18px line that is 54px under a 63px cover head, so a hit stays about one and a half library rows tall and six or seven still fit on a phone screen. Search is a scanning surface and the number of results in view is what makes it one: two lines cut most sentences in half, four make every hit nearly two rows.
- **Making the match visible** (AC#13) is a windowing pass, `focusHighlightSegments` in `mobile/src/lib/highlightSnippet.ts`, applied to the already-parsed segments. `numberOfLines` truncates at the *end*, so a match sitting further into the snippet is simply not on screen. Two independent cuts:
  - the **lead-in** is trimmed to `EXCERPT_LEAD_CHARS = 45` — a little under one line of this box (~50 characters at 13px across a card interior of ~334px on a 390pt phone, ~40 on the narrowest supported width). The match therefore begins on the first or second of the three lines on any device, while keeping most of a line of context in front of it;
  - the **tail** is capped at `EXCERPT_MAX_CHARS = 220`, past what three lines hold (~150-170), so the trailing ellipsis the reader sees is normally the native `numberOfLines` one. The cap exists for the case the backend hands over a whole highlighted transcript chunk instead of a snippet, which it does whenever Algolia returns no snippet.
  - Both cuts land on a word boundary, and the `…` is pushed as its own non-highlighted segment so it is never drawn on the match's amber.
- Highlighting still goes through `parseHighlightSnippet` and only `Colors.highlight` / `Colors.onHighlight`. The two new styles (`excerpt`, `excerptMatch`) use existing tokens only.
- `excerpt` is optional and nothing else passes it: Inbox, "All media" and the inside of a collection render the row they had, and `renderMediaPreview` passes it so the lifted copy matches the pressed vignette.

## Layout reconciliation

`libraryListContent` and `resultsList` collapsed into one `listContent` with no horizontal padding and no `gap` — `MediaListCard` brings its own margins, and keeping the results gutter would have doubled it. `libraryHeader` became `listHeader` and is applied to both headers; `searchSectionHeading` was deleted so both "All media" headings share one spacing. The whole `ResultCard` style block was removed.

## i18n

No new string was needed, so no catalogue gained a key. `time.today` and `mediaType.unknownSource` had exactly one consumer each — the two deleted helpers — and were removed from all 11 catalogues. The `…` is a typographic mark, identical in every locale, and is documented as such in `highlightSnippet.ts` rather than translated.

## Verification

- `make lint`: `ruff check media_summarizer/` all checks passed; `mypy media_summarizer/` success, 180 source files.
- `cd mobile && npm run typecheck`: clean. `npm run lint`: 0 errors, 1 pre-existing warning in the untouched `mobile/src/services/purchaseService.ts:98`.
- `git status` confirms `media_summarizer/core/services/search_indexing.py` is unmodified (AC#16).
- No automated tests were added, per the project rule.

## Owner follow-up

- **DEPLOYMENT PREREQUISITE** — the new `GET /api/search/transcripts` fields only arrive once `main` is pushed and the Lambda image is redeployed. Until then the app runs on the old response: "Move" preselects Unsorted and the subtitle has no domain fallback. The app degrades rather than breaks (`folder_id`/`source_url` read as absent), but the visual check below is only meaningful after the deploy.
- **VISUAL CHECK** — on the iOS simulator and the Android emulator: switch between the query-less list and the results list and confirm the vignette is the same; long press a result (anchored menu, lifted copy aligned on the row); a full Rename / Move / Delete cycle from a result; one result with a long excerpt and one whose match falls late in the excerpt.
- **DELETION** — irreversible past the grace window (`docs/DATA_RETENTION.md`). Test on `-dev` with a disposable media, never on the persistent "Commonplace book" article.
- **STILL TO DECIDE** — deleting a media does not unindex it, so retyping the same query after a deletion brings it back with no cover and no actions. This task makes the flaw visible since it puts deletion within reach of search. Un-indexing remains to be opened as a separate task if wanted.
<!-- SECTION:NOTES:END -->
