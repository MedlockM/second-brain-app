---
id: task-74
title: 'Recherche sur métadonnées (titre, tags, source, dossier)'
status: To Do
assignee: []
created_date: '2026-03-29 21:02'
updated_date: '2026-03-29 21:18'
labels:
  - feature
  - search
  - v1
dependencies:
  - task-53
  - task-66
  - task-67
priority: high
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
## Contexte

Les utilisateurs doivent pouvoir rechercher dans leur bibliothèque de médias. La recherche V1 porte **uniquement sur les métadonnées** (pas de full-text sur le contenu des transcripts).

## Spécification V1

### Champs recherchables
- **Titre** du média
- **Tags** associés (filtre exact ou partiel)
- **Source/plateforme** (Spotify, YouTube, article, etc.)
- **Dossier** (filtre par dossier, incluant sous-dossiers)
- **Type de média** (podcast, article, vidéo, etc.)

### Fonctionnalités
- Recherche textuelle simple sur le titre (case-insensitive, substring match)
- Filtrage combiné : tags + dossier + source + type
- Tri par date d'ajout (récent d'abord par défaut)
- Pagination

### Pas en V1
- Full-text search sur le contenu des transcripts/résumés
- Recherche sémantique / vectorielle
- Suggestions / autocomplétion

## Aspects techniques
- Endpoint API : GET /api/media?q=...&tags=...&folder_id=...&source=...&type=...
- Implémentation via DynamoDB queries + filtres (ou GSI adaptés)
- Dépend de l'implémentation des dossiers et tags

## Note
task-53 et task-53.1 existants couvrent un scoping plus large. Cette tâche se concentre sur l'implémentation V1 minimaliste basée sur les décisions produit validées.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 Recherche textuelle sur le titre des médias (case-insensitive)
- [ ] #2 Filtrage par tags (un ou plusieurs)
- [ ] #3 Filtrage par dossier (incluant sous-dossiers)
- [ ] #4 Filtrage par source/plateforme
- [ ] #5 Filtrage par type de média
- [ ] #6 Filtres combinables
- [ ] #7 Pagination
- [ ] #8 Endpoint API GET /api/media avec paramètres de recherche
<!-- AC:END -->
