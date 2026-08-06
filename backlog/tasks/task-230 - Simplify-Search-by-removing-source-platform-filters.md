---
id: task-230
title: Simplify Search by removing source-platform filters
status: Done
assignee:
  - Codex
created_date: '2026-08-05 23:17'
updated_date: '2026-08-06 01:05'
labels:
  - mobile
  - ux
dependencies: []
priority: medium
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Remove the source-platform filtering feature from the mobile Search experience so the initial collections view and global search flow remain visually coherent. Search should continue to query the full user library across all supported sources, while source information remains visible on individual results. No filtering controls should be added to collection screens in this scope.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 The Search landing state displays the search field and collections without the All, YouTube, Spotify, Web, Instagram, or TikTok filter controls
- [x] #2 Submitting or typing a search query searches across all supported source platforms without applying a source-platform constraint
- [x] #3 Search results continue to display each media item's source label and icon
- [x] #4 Clearing a query returns to the collections state without retaining any hidden source-filter state
- [x] #5 Collection screens do not introduce source-platform or other filtering controls as part of this change
- [x] #6 Loading, error, no-result, and populated-result states remain usable after the filter feature is removed
- [x] #7 Manual verification covers the initial collections state, active search, no-results state, populated results, and clearing the query
<!-- AC:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
1. Supprimer de l’écran Search la configuration des chips, l’état activeSourceFilter, les handlers, le bloc visuel et les styles associés.
2. Simplifier SearchService.searchTranscripts et son appel pour ne plus accepter ni sérialiser source_platform côté mobile ; la requête texte couvre ainsi toute la bibliothèque.
3. Conserver sans modification le rendu des cartes de résultat (icône et label source) et les écrans de collections ; ajuster seulement le message no-results qui mentionnait les filtres.
4. Valider lint/typecheck puis relire statiquement les cinq états demandés (collections, chargement, erreur, aucun résultat, résultats) et le retour aux collections lors du clear.
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Implémentation terminée :
- Suppression complète des chips All/YouTube/Spotify/Web/Instagram/TikTok, de leur état, handlers et styles sur l’écran Search.
- SearchService.searchTranscripts n’accepte plus de filtre source_platform et ne peut plus ajouter ce paramètre à la requête mobile ; la recherche texte couvre toute la bibliothèque.
- Les cartes conservent source_platform pour afficher getSourceLabel/getSourceIcon.
- Le clear remet query, results, totalResults, hasSearched et error à leur état collections ; aucun état de filtre caché ne subsiste.
- Aucun contrôle n’a été ajouté aux écrans de collections.
- Relecture manuelle des branches de rendu : loading, error, collections initiales, no-results, résultats peuplés et retour après clear restent présentes.

Validation :
- npx eslint app/(tabs)/search.tsx src/services/searchService.ts : succès.
- npm run typecheck : succès.
- rg confirme que source_platform ne subsiste que comme métadonnée de résultat pour le label et l’icône.
- Le lint global avait passé à la clôture de task-227 ; une modification concurrente hors périmètre dans mobile/app/media/[id].tsx a ensuite introduit un nouvel écart exhaustive-deps. Elle n’a pas été modifiée ici.
<!-- SECTION:NOTES:END -->
