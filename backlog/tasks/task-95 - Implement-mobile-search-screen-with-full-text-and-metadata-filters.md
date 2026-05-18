---
id: task-95
title: Implement mobile search screen with full-text and metadata filters
status: Done
assignee: []
created_date: '2026-05-18 20:27'
labels:
  - feature
  - mobile
dependencies:
  - task-37
  - task-38
priority: high
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Implement the search screen combining full-text search (via Algolia) and metadata filters (title, tags, source/platform, folder, type).

**Design reference:** `mobile-design-mockups/search_harmonized_v2/`
**Design system:** `mobile-design-mockups/my_design_system/DESIGN.md`

Réutilisation obligatoire:
- Endpoints canoniques: `GET /api/media/search` (full-text Algolia), `GET /api/media` avec query params (metadata filters)
- `front/src/types/media.ts`: types de résultats de recherche

Contraintes: implémenter nativement, recherche réactive (debounce), filtres combinables.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 Recherche full-text fonctionnelle avec résultats en temps réel (debounce)
- [ ] #2 Filtres métadonnées disponibles (type, source, tags, dossier)
- [ ] #3 Résultats affichés avec titre, source, date, statut
- [ ] #4 Layout conforme au mockup search_harmonized_v2
- [ ] #5 Fonctionne sur petits et grands viewports
<!-- AC:END -->
