---
id: task-67
title: Tags utilisateur (métadonnées médias)
status: Done
assignee: []
created_date: '2026-03-29 21:01'
updated_date: '2026-04-28 12:00'
labels:
  - feature
  - organization
  - v1
dependencies:
  - task-10
priority: high
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
## Contexte

Les utilisateurs doivent pouvoir associer des tags à leurs médias pour les filtrer et les retrouver facilement.

## Spécification V1

- **Tags créés manuellement** par l'utilisateur (pas d'auto-génération IA)
- **Privés par utilisateur** : aucun partage entre utilisateurs
- **Multi-tags par média** : un média peut avoir 0 à N tags
- **Assignation au share** : l'écran de share mobile permet d'associer des tags existants ou d'en créer de nouveaux

## Modèle de données

- Table DynamoDB `user_tags` : PK=user_id, SK=tag_id
- Champs : tag_id, name, color (optionnel), created_at
- Table de jointure ou attribut list dans le modèle média : tags = [tag_id, ...]
- GSI pour la recherche par tag : PK=user_id#tag_id → liste des media_keys

## Endpoints API

- POST /api/tags — créer un tag (name, color optionnel)
- GET /api/tags — lister les tags de l'utilisateur
- PUT /api/tags/{tag_id} — renommer un tag
- DELETE /api/tags/{tag_id} — supprimer un tag (dissociation des médias)
- PATCH /api/media/{media_id}/tags — associer/dissocier des tags à un média

## Contraintes
- Pas de tags auto-générés par l'IA en V1
- Frontend construit séparément dans Stitch
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 Tags créables manuellement par l'utilisateur
- [ ] #2 Association multi-tags possible par média
- [ ] #3 CRUD complet sur les tags (créer, lister, renommer, supprimer)
- [ ] #4 Association/dissociation de tags sur un média
- [ ] #5 Tags associables au moment de l'ingestion (paramètre tag_ids dans ingest-url)
- [ ] #6 Modèle DynamoDB user_tags implémenté
- [ ] #7 Suppression d'un tag le dissocie de tous les médias
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Dispatch 2026-04-28: Implémentation complétée par agent-task-67. Créé core/models/tag.py (Tag domain model), core/services/tag_service.py (CRUD business logic), api/endpoints/tags.py (POST/GET/PUT/DELETE /api/tags). Modifié api/endpoints/media.py (PATCH /{media_id}/tags + tag_ids sur ingest-url), processing_job.py (ajout tag_ids), database_async.py (tag CRUD DynamoDB). DynamoDB table user_tags avec GSI user-index. Terraform localstack + core tables. Merged dans second-brain-project (conflit résolu dans main.py, __init__.py, localstack/main.tf).
<!-- SECTION:NOTES:END -->
