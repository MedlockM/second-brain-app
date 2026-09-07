---
id: task-375
title: >-
  Rendre les résultats de recherche identiques aux vignettes « Tous les médias »
  — même carte, même appui long (Renommer/Déplacer/Supprimer), plus une zone
  réservée à l'extrait surligné
status: To Do
assignee: []
created_date: '2026-09-07 13:48'
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
- [ ] #1 Le composant local ResultCard n'existe plus dans mobile/app/(tabs)/search.tsx : les résultats de recherche sont rendus par MediaListCard, et il ne reste aucune seconde implémentation de vignette média dans cet écran
- [ ] #2 Une vignette de résultat affiche les mêmes éléments qu'une vignette de « Tous les médias » : cover 16:9 avec repli sur l'icône de type de média, badge de type coloré, temps relatif, titre sur 2 lignes, sous-titre creator_name avec repli sur le domaine de la source — le libellé de plateforme en majuscules et le formatTimestamp local de l'écran de recherche ont disparu
- [ ] #3 Une vignette de résultat a la même surface, le même rayon, la même ombre, les mêmes marges et le même retour de pression (cardPressed) qu'une vignette de « Tous les médias » : aucun style propre aux résultats ne subsiste en dehors de la zone d'extrait
- [ ] #4 La date affichée sur une vignette de résultat est produite par le même helper que « Tous les médias » (getRelativeTime) à partir de la date portée par la ligne de bibliothèque, de sorte qu'un même média affiche la même date sur les deux listes
- [ ] #5 Un appui long sur une vignette de résultat ouvre le même AnchoredContextMenu que dans « Tous les médias », avec Renommer, Déplacer et Supprimer, servi par useMediaActions et non par une seconde implémentation des actions
- [ ] #6 La copie soulevée par le menu (renderPreview) redessine la vignette pressée à l'identique, extrait compris, sur le rect mesuré
- [ ] #7 « Déplacer » ouvre le sélecteur /media/collection avec le dossier courant du média préselectionné, lu sur la ligne de bibliothèque via la réponse de recherche et non remplacé par un défaut « Non trié »
- [ ] #8 « Renommer » met à jour le titre du résultat dans la liste sans rechargement, et « Supprimer » ne retire le résultat de la liste qu'après confirmation du backend
- [ ] #9 Un renommage ou une suppression déclenché depuis un résultat met aussi à jour la liste « Tous les médias » tenue par l'écran : effacer la requête ne remontre pas l'ancien titre ni le média supprimé
- [ ] #10 Un échec réseau sur Renommer, Déplacer ou Supprimer affiche un message et laisse le média en place dans la liste des résultats
- [ ] #11 Un hit dont la ligne de bibliothèque est absente (média supprimé, toujours présent dans l'index) n'offre pas l'appui long : aucune action n'est proposée sur un média qui n'existe plus
- [ ] #12 L'extrait de transcript surligné reste affiché dans une zone dédiée sous la tête de la vignette, sur toute la largeur, bornée à un nombre fixe de lignes ; le choix de ce nombre est documenté dans les Implementation Notes
- [ ] #13 Le segment surligné du premier extrait est toujours visible dans les lignes affichées, avec du texte de contexte de part et d'autre quand il en existe ; la mécanique retenue pour y parvenir est documentée dans les Implementation Notes
- [ ] #14 La zone d'extrait est une prop optionnelle de MediaListCard : les surfaces qui n'en passent pas (Inbox, « Tous les médias », intérieur d'une collection) rendent une vignette inchangée
- [ ] #15 GET /api/search/transcripts renvoie, lus sur la ligne de bibliothèque par load_display_details, le dossier du média, l'URL de sa source et ses dates ; le modèle Pydantic SearchHit et le type TS SearchHit les déclarent tous les deux
- [ ] #16 L'indexation Algolia est inchangée : aucun champ ajouté aux documents, aucune réindexation nécessaire (git diff vide sur search_indexing.py et sur les workers d'indexation)
- [ ] #17 Le surlignage passe toujours par parseHighlightSnippet et les tokens Colors.highlight / Colors.onHighlight ; aucune couleur ni recette d'ombre littérale n'est introduite, seuls les tokens de mobile/src/constants/theme.ts sont utilisés
- [ ] #18 Toute nouvelle chaîne passe par t() et est présente dans les 11 catalogues de mobile/src/i18n/
- [ ] #19 cd mobile && npm run lint && npm run typecheck sont clean, et make lint (ruff + mypy) est clean
<!-- AC:END -->
