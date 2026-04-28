---
id: task-66
title: Dossiers hiérarchiques (organisation des médias)
status: Done
assignee: []
created_date: '2026-03-29 21:00'
updated_date: '2026-04-21 21:52'
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

Les utilisateurs doivent pouvoir organiser leurs médias dans des dossiers imbriqués (hiérarchiques, comme Raindrop.io).

## Spécification V1

- **Dossiers imbriqués** : profondeur illimitée (ou raisonnable, ex: 5 niveaux)
- **Un média = un seul dossier** (pas de multi-assignation)
- **Dossier par défaut** : "Non classé" — tout média sauvegardé sans dossier explicite va dans "Non classé"
- **Privé par utilisateur** : aucun partage de dossiers entre utilisateurs
- **Assignation au share** : l'écran de share mobile permet de choisir un dossier existant ou d'en créer un nouveau

## Modèle de données

- Table DynamoDB `user_folders` : PK=user_id, SK=folder_id
- Champs : folder_id, name, parent_folder_id (null pour racine), created_at, updated_at
- Le dossier "Non classé" est créé automatiquement à la création de l'utilisateur
- Référence folder_id dans le modèle média (processing_job ou media_item)

## Endpoints API

- POST /api/folders — créer un dossier (name, parent_folder_id optionnel)
- GET /api/folders — lister les dossiers de l'utilisateur (arbre complet)
- PUT /api/folders/{folder_id} — renommer, déplacer (changer parent)
- DELETE /api/folders/{folder_id} — supprimer (médias déplacés vers "Non classé")
- PATCH /api/media/{media_id} — assigner/changer le dossier d'un média

## Contraintes
- La suppression d'un dossier parent déplace les sous-dossiers et médias vers "Non classé"
- Pas de dossiers partagés entre utilisateurs
- Frontend construit séparément dans Stitch
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 Dossiers imbriqués créables avec profondeur raisonnable
- [ ] #2 Un média n'appartient qu'à un seul dossier
- [ ] #3 Dossier 'Non classé' créé automatiquement par utilisateur
- [ ] #4 CRUD complet sur les dossiers (créer, lister arbre, renommer, déplacer, supprimer)
- [ ] #5 Suppression d'un dossier déplace son contenu vers 'Non classé'
- [ ] #6 Assignation de dossier possible au moment de l'ingestion (paramètre folder_id dans ingest-url)
- [ ] #7 Modèle DynamoDB user_folders implémenté
<!-- AC:END -->
