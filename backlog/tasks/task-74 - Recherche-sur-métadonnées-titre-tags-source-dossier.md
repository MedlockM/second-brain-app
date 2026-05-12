---
id: task-74
title: 'Recherche sur métadonnées (titre, tags, source, dossier)'
status: Done
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

Les utilisateurs doivent pouvoir rechercher dans leur bibliothèque de médias. **Cette task couvre uniquement le volet metadata** (titre, tags, source/plateforme, dossier, type). Le volet full-text sur transcripts est traité par **task-53.1** (Typesense Cloud, validée 2026-04-28) — les deux recherches coexistent en V1 et sont complémentaires.

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

### Pas dans cette task (scope task-74)
- Full-text search sur le contenu des transcripts/résumés → **traité par task-53.1 (Typesense Cloud)**, qui est aussi en V1

### Pas en V1 (du tout)
- Recherche sémantique / vectorielle
- Suggestions / autocomplétion

## Aspects techniques
- Endpoint API : GET /api/media?q=...&tags=...&folder_id=...&source=...&type=...
- Implémentation via DynamoDB queries + filtres (ou GSI adaptés)
- Dépend de l'implémentation des dossiers et tags

## Note
task-53.1 (full-text lexical search via Typesense Cloud) est **également en V1** et couvre le volet complémentaire. Cette task-74 se concentre spécifiquement sur le volet metadata (DynamoDB queries/GSI). Les deux endpoints peuvent être unifiés côté API ou rester séparés selon l'UX finale.
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
