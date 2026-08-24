---
id: task-317
title: >-
  Aligner les vignettes de résultats de recherche sur le style des vignettes
  Home/Library (image, titre, auteur)
status: Done
assignee: []
created_date: '2026-08-23 00:52'
updated_date: '2026-08-23 20:15'
labels:
  - mobile
  - ui
  - search
dependencies: []
priority: medium
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
## Contexte

L'écran concerné est `mobile/app/(tabs)/search.tsx`, composant `ResultCard` (autour de la ligne 936). Aujourd'hui, une fois qu'une requête est tapée, chaque résultat Algolia est rendu comme une carte purement textuelle : icône de source + libellé + date en header, titre, puis un extrait du transcript avec les mots-clés surlignés (`cardSnippet` / `cardSnippetMatch`). Il n'y a **aucune image**.

À côté, deux autres écrans affichent déjà des vignettes de média avec image :
- `mobile/src/components/MediaListCard.tsx` — utilisé par la section "All media" de l'onglet Search (état idle, sans requête) et par le Home/Inbox. Cover 16:9 (112×63) via `expo-image`, avec repli sur l'icône de type de média (`getMediaTypeIcon`) quand `media_image` est vide ou en échec de chargement (jamais de rectangle gris vide). Deuxième ligne : `creator_name`, ou à défaut le domaine de la source.
- `mobile/src/components/HomeTile.tsx` / `mobile/src/components/ArtifactTile.tsx` pour la home.

Résultat : l'utilisateur voit une UI visuellement différente selon qu'il regarde sa librairie (vignettes avec image) ou qu'il tape une recherche (cartes texte seul), ce qui casse la cohérence visuelle de l'app.

## Objectif

Redessiner `ResultCard` pour qu'il se rapproche du langage visuel de `MediaListCard` (cover 16:9, silhouette de carte, typographie, rayons, ombre — les tokens `theme.ts` existants), **sans** perdre ce que `ResultCard` a de spécifique et qu'aucune autre vignette n'a : l'extrait de transcript avec le ou les mots-clés recherchés surlignés (`snippetSegments` / `cardSnippetMatch`). C'est cet extrait qui justifie que la carte soit plus grande/plus riche en texte qu'une simple ligne de librairie — il doit rester lisible et ne pas être sacrifié pour faire de la place à l'image.

Le champ `media_image` est déjà exposé par le hit Algolia côté indexation (voir `task-304`/`task-302`) — vérifier sa présence sur `SearchHit` (`mobile/src/services/searchService.ts` ou équivalent) avant de commencer ; si le champ n'est pas indexé/retourné aujourd'hui, l'ajouter côté client de lecture uniquement (pas de nouveau endpoint attendu, l'indexation Algolia existe déjà pour d'autres champs de cover).

Laissée à l'appréciation de l'implémenteur (pas d'idée arrêtée côté owner) :
- Disposition exacte (cover à gauche façon `MediaListCard`, ou cover en bandeau au-dessus vu que la carte porte plus de texte qu'une ligne de liste) — trancher et documenter le choix et le pourquoi dans les Implementation Notes.
- Comment faire cohabiter source/date, titre, auteur (si la place le permet sans surcharger — l'auteur peut être omis si ça encombre) et l'extrait surligné sans que la carte devienne disproportionnée par rapport aux vignettes Home/Library.
- Réutiliser directement `MediaListCard` (en l'étendant pour accepter un extrait de recherche en enfant/slot) plutôt que dupliquer son style, si c'est raisonnable — sinon partager au moins les constantes de cover (dimensions 16:9, `BorderRadius`, comportement de repli) pour éviter une deuxième implémentation divergente du même composant.

## Contraintes

- Garder l'esprit visuel existant : mêmes tokens `theme.ts` (`Colors`, `Typography`, `Spacing`, `BorderRadius`, `Shadows`, `TouchTarget`), pas de nouvelle couleur ni de recette d'ombre inédite.
- Le repli sans image doit suivre le même principe que `MediaListCard` : icône de type de média sur `surfaceContainerLow`, jamais de zone grise vide.
- `expo-image` pour le rendu de la cover (déjà une dépendance du projet), avec `cacheKey`/`recyclingKey` cohérents avec ce que fait déjà `MediaListCard`.
- Le `testID="search-result-card"` est un ancrage Maestro (`mobile/.maestro/06_search.yaml`) : il doit rester présent sur l'élément pressable, quelle que soit la nouvelle structure interne.
- Le surlignage des mots-clés (`parseHighlightSnippet`, `cardSnippetMatch`) doit rester fonctionnel et visible.
- `cd mobile && npm run lint && npm run typecheck` doivent rester clean.

## Notes à l'owner

- VÉRIF VISUELLE — la cohérence entre les trois familles de vignettes (Home, Library/All media, résultats de recherche) ne se juge pas en lint/typecheck. À regarder sur simulateur, requête tapée avec et sans résultats ayant une image.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 Le composant ResultCard dans mobile/app/(tabs)/search.tsx affiche l'image du média (media_image) en reprenant le langage visuel de MediaListCard (dimensions/ratio de cover, BorderRadius, comportement d'expo-image)
- [x] #2 Quand media_image est absent ou échoue au chargement, la carte affiche l'icône de type de média sur surfaceContainerLow au lieu d'une image, jamais un espace vide ou un rectangle gris
- [x] #3 Le titre du résultat reste affiché, ainsi que l'extrait de transcript avec le(s) mot(s)-clé(s) recherché(s) toujours visuellement surligné(s) via cardSnippetMatch/parseHighlightSnippet
- [x] #4 L'auteur/creator_name (ou à défaut le domaine de la source, comme dans MediaListCard) est affiché sur la carte seulement s'il ne surcharge pas visuellement la carte ; le choix retenu et le pourquoi sont documentés dans les Implementation Notes
- [x] #5 Seuls des tokens existants de mobile/src/constants/theme.ts sont utilisés (Colors, Typography, Spacing, BorderRadius, Shadows, TouchTarget) : aucune couleur ni recette d'ombre nouvelle
- [x] #6 Le testID="search-result-card" reste présent sur l'élément pressable de la carte, préservant l'ancrage utilisé par mobile/.maestro/06_search.yaml
- [x] #7 Les Implementation Notes documentent la disposition retenue (position de la cover par rapport au texte) et pourquoi, ainsi que le degré de réutilisation avec MediaListCard (extension du composant existant vs constantes/styles partagés vs implémentation séparée documentée)
- [x] #8 cd mobile && npm run lint && npm run typecheck sont clean
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
## La prémisse de la description était fausse

> « Le champ `media_image` est déjà exposé par le hit Algolia côté indexation (voir task-304/task-302) »

Non. **Rien de tout cela n'était indexé.** `index_transcript` n'écrivait que `title`, `creator_name`, `source_platform`, `created_at`, `chunk_index`, `transcript` — et `creator_name`, bien qu'écrit, n'était ni dans `attributesToRetrieve`, ni dans le mapping du hit, ni sur le modèle `SearchHit` de l'API. Il n'y avait donc **ni cover, ni auteur, ni type de média** à afficher, quel que soit le travail fait côté app.

La description prévoyait le cas (« si le champ n'est pas indexé/retourné aujourd'hui, l'ajouter côté client de lecture uniquement, pas de nouveau endpoint attendu »). Aucun endpoint n'a été créé : `GET /api/search/transcripts` est étendu.

## D'où vient la cover : de la ligne de bibliothèque, pas de l'index

**Première approche, écartée** : dénormaliser `media_image` / `media_type` dans les documents Algolia. Elle a été implémentée puis retirée, parce qu'elle est fausse sur trois plans :

- **Elle ne marche pas sur l'existant.** Tout ce qui est déjà indexé a été écrit sans ces champs et resterait sans cover jusqu'à une réingestion — ce qui obligeait à demander à l'owner de re-sauvegarder des médias juste pour voir le résultat. C'est ce qui a mis la puce à l'oreille.
- **Elle périme.** Une cover ré-hébergée ou remplacée après l'indexation laisse l'index sur l'ancienne valeur, sans rien pour les réconcilier hors réindexation.
- **Elle crée une deuxième vérité.** La ligne `user_media` est déjà la source de la cover pour l'Inbox et pour « All media ». Une copie dans l'index est une seconde valeur qui peut en diverger.

**Approche retenue** : l'index reste un index de *recherche* — il répond quels items correspondent et où dans leur texte. Ce à quoi ces items *ressemblent* est lu sur la ligne de bibliothèque, au moment de la lecture, par `load_display_details(user_id, media_item_ids)` dans `media_search_service` : un `get_item` par hit, par clé primaire, borné par la pagination que l'endpoint applique déjà (au plus `per_page`, 10 par défaut — `search_transcripts` pagine avant de rendre ses hits).

Conséquence directe : **la recherche affiche exactement la même image que l'Inbox et que « All media », par construction, et sans rien réindexer.** Elle marche immédiatement sur les données existantes.

Les covers passent par `resolve_cover_urls`, le résolveur que la liste de bibliothèque utilise déjà, rendu public pour l'occasion — une seconde implémentation de la signature aurait été le moyen pour les deux surfaces de finir par ne pas s'accorder sur les covers qui chargent.

`title` reste indexé (il est recherché et surligné) mais l'affichage préfère la valeur de la ligne, avec l'index en repli.

## Un manque constaté au passage

**Supprimer un média ne le retire pas de l'index Algolia** : le seul `_delete_chunks_for_media` du code est celui qui précède une réindexation. Un média supprimé reste donc trouvable — c'était déjà vrai avant cette tâche, et ça le reste : ces hits ont désormais une ligne de bibliothèque absente et retombent sur ce que l'index sait. Les filtrer changerait le total `found` renvoyé et sort du périmètre ; c'est signalé ici comme une tâche à part.

## La disposition retenue (AC #7)

**Cover à gauche, comme `MediaListCard`, l'extrait en dessous sur toute la largeur.**

La tête de la carte — cover 112×63, ligne meta, titre, auteur — est *exactement* la silhouette d'une ligne de bibliothèque. L'extrait de transcript est la seule chose qui pend en dessous.

L'alternative (cover en bandeau au-dessus, que la description proposait au motif que la carte porte plus de texte) a été écartée : elle double la hauteur de chaque résultat et fait passer la liste de six ou sept résultats visibles à trois. **La recherche est une surface de balayage, et ce qu'on y balaye est l'extrait** — lui faire de la place vaut mieux qu'une plus grande image. La disposition retenue donne la parenté visuelle demandée sans rien coûter à la densité.

### Le degré de réutilisation

`MediaListCard` **n'est pas étendu**, et n'est pas dupliqué non plus : il **exporte ses constantes de cover** (`COVER_WIDTH`, `COVER_HEIGHT`), que `ResultCard` importe. Le raisonnement :

- L'étendre avec un slot `children` pour l'extrait aurait fait porter à un composant de *ligne de liste* la connaissance d'un cas de *résultat de recherche* — surlignage compris — alors que les deux ont des données d'entrée différentes (`MediaListItem` contre `SearchHit`, qui n'a ni `updated_at`, ni `source_url`, ni le même repli de sous-titre).
- Partager les deux nombres suffit à empêcher la divergence que l'AC vise : ce sont eux, et pas la structure JSX, qui décideraient de deux vignettes légèrement différentes pour la même image.

Le reste (rayon, surface tonale de repli, `contentFit`, `transition`, `priority`, politique de cache) suit les mêmes tokens et les mêmes props, ce que le commentaire du composant explicite.

### `cacheKey`

`MediaListCard` utilise `${media_item_id}:${updated_at}`. Le hit de recherche n'a pas d'`updated_at`, et son URL de cover est re-signée à chaque recherche : la clé est donc le chemin de l'URL, requête retirée (`coverUrl.split("?")[0]`), le même raisonnement que `stableImageIdentity` dans `HomeTile`. Ce qui identifie l'image est l'objet qu'elle désigne, pas la signature du moment.

## L'auteur (AC #4)

**Affiché**, sur une ligne, `numberOfLines={1}`, sous le titre — et seulement s'il existe.

Il ne surcharge pas : la ligne meta porte la plateforme et la date, le titre porte deux lignes au plus, l'auteur une, l'extrait trois. C'est un bloc de plus que `MediaListCard`, ce qui est précisément la différence assumée entre une ligne de bibliothèque et un résultat de recherche.

**Pas de repli sur le domaine**, contrairement à `MediaListCard` : le hit Algolia ne porte pas `source_url`, et l'indexer pour n'en extraire qu'un nom d'hôte aurait ajouté un champ à toute la chaîne pour une redondance — le libellé de plateforme est déjà sur la ligne meta juste au-dessus. Sans auteur, la ligne disparaît simplement.

## Rien à réindexer

Les covers étant lues sur la ligne de bibliothèque, tout média déjà indexé **et** toujours présent dans la bibliothèque affiche sa cover dès le déploiement. Aucune réingestion, aucune migration.

## Vérifications

- `npm run typecheck` clean ; `npm run lint` 0 erreur, 2 warnings préexistants sans rapport (AC #8).
- `make lint` : `ruff` clean, `mypy` — 173 fichiers, aucun problème.
- L'indexation Algolia est **inchangée** par rapport à avant cette tâche (`git diff` vide sur `search_indexing.py` et les deux workers) : seule la lecture est étendue.
- `testID="search-result-card"` toujours sur le `Pressable` racine, ancrage de `.maestro/06_search.yaml` (lignes 34 et 38) préservé (AC #6).
- Le diff de `search.tsx` n'introduit **aucune** couleur littérale, `rgba()`, `shadowColor`, `shadowOffset` ni `elevation` : uniquement des tokens de `theme.ts` (AC #5).
- `parseHighlightSnippet` et `cardSnippetMatch` sont inchangés et toujours rendus (AC #3).

## Non vérifiable depuis le worktree

La cohérence visuelle des trois familles de vignettes — c'est la note owner de la description, et elle demande un simulateur, une requête tapée, et des résultats avec et sans cover.
<!-- SECTION:NOTES:END -->
