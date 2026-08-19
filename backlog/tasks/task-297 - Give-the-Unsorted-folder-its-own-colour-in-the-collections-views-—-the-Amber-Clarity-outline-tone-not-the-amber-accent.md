---
id: task-297
title: >-
  Give the Unsorted folder its own colour in the collections views — the Amber
  Clarity outline tone, not the amber accent
status: To Do
assignee: []
created_date: '2026-08-19 19:14'
labels:
  - mobile
  - ui
dependencies: []
priority: low
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
## Problème

Le dossier par défaut, affiché sous le label `Unsorted` (`mobile/src/lib/collectionTree.ts:7`), est rendu exactement comme les collections créées par l'utilisateur : même icône `folder`, même ambre `Colors.primary`. Rien ne signale visuellement qu'il s'agit d'un conteneur système regroupant les médias sans collection, et non d'une collection au même titre que les autres.

C'est aussi une entorse à la DA : `mobile-design-mockups/my_design_system/DESIGN.md` réserve l'ambre aux « high-value interactions (CTAs, active states) and meaningful accents ». Un bac par défaut n'en est pas un.

## Couleur retenue

**`Colors.outline` = `#78776f`** — déjà présent dans `mobile/src/constants/theme.ts:18`. C'est le « olive-grey secondary tone that grounds the interface » décrit par le DESIGN.md, et il sert déjà à teinter une icône dans `mobile/app/media/tags.tsx:315` : aucune couleur nouvelle n'entre dans la palette.

Pourquoi pas `Colors.textMuted` (`#8d99ae`), le candidat a priori plus naturel : son contraste tombe sous le seuil de 3:1 exigé par WCAG 1.4.11 pour un composant graphique non-textuel sur toutes les surfaces du système (2,9:1 sur `surface`, 2,6:1 sur `surfaceContainerLow`). `Colors.outline` passe partout : 4,5:1 sur `surface`, 4,1:1 sur `surfaceContainerLow`, 3,7:1 sur `surfaceContainerHigh`.

## Périmètre

Trois surfaces affichent le dossier par défaut et doivent toutes basculer :

1. `mobile/app/(tabs)/search.tsx:496` — `CollectionTile`, la grille 3 colonnes de l'onglet Search.
2. `mobile/app/media/collections/index.tsx:205` — `FolderRow`, l'explorateur en liste. Le conteneur d'icône passe en plus de `Colors.surfaceContainerLow` à `Colors.surfaceContainerHigh` pour renforcer la distinction par bloc de couleur — jamais par une bordure 1px, la « No-Line Rule » du DESIGN.md l'interdit.
3. `mobile/app/media/collection.tsx:425` — l'option « Non trié » du sélecteur de collection, qui utilise déjà une icône distincte (`file-tray-outline`) mais toujours l'ambre.

Le nœud à cibler est celui dont `is_default === true`. Dans `search.tsx` et `collections/index.tsx` le nœud est épinglé en tête via un spread qui remplace `name` : `is_default` survit, mais préférer un flag explicite passé au composant plutôt qu'une comparaison sur le label affiché.

Une seule source de vérité pour la couleur : soit un token sémantique dans `theme.ts`, soit une constante exportée à côté de `DEFAULT_COLLECTION_LABEL` dans `collectionTree.ts`. Pas de `#78776f` littéral, ni de `Colors.outline` recopié dans chacun des trois écrans.

Aucun changement de label, d'ordre de tri, d'épinglage en tête de liste, ni de navigation : la tâche est purement chromatique.

## Notes à l'owner

Vérification visuelle après merge (ne peut pas être un AC) : ouvrir l'onglet Search, l'explorateur `/media/collections` et le sélecteur de collection, et confirmer que le dossier Unsorted se distingue au premier regard sans paraître désactivé.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 La couleur du dossier par défaut est définie une seule fois (token sémantique dans theme.ts ou constante exportée près de DEFAULT_COLLECTION_LABEL) et vaut Colors.outline / #78776f
- [ ] #2 Le littéral #78776f n'apparaît dans aucun écran, et les trois surfaces lisent la même constante partagée
- [ ] #3 Dans la grille de l'onglet Search (search.tsx, CollectionTile), l'icône du dossier par défaut utilise cette couleur alors que les autres collections restent en Colors.primary
- [ ] #4 Dans l'explorateur en liste (collections/index.tsx, FolderRow), l'icône du dossier par défaut utilise cette couleur et son conteneur d'icône passe à Colors.surfaceContainerHigh, les autres lignes restant inchangées
- [ ] #5 Dans le sélecteur de collection (collection.tsx), l'icône de l'option Non trié utilise cette couleur
- [ ] #6 Le ciblage repose sur is_default (ou un flag explicite dérivé de is_default) et non sur une comparaison du nom affiché avec DEFAULT_COLLECTION_LABEL
- [ ] #7 Aucune bordure ni trait 1px n'est ajouté pour distinguer le dossier, conformément à la No-Line Rule du DESIGN.md
- [ ] #8 Le label, l'ordre de tri, l'épinglage en tête de liste et la navigation du dossier par défaut sont inchangés dans les trois écrans
- [ ] #9 npx tsc --noEmit et npm run lint sont clean dans mobile/
<!-- AC:END -->
