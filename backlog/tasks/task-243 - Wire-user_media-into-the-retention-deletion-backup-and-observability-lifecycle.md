---
id: task-243
title: >-
  Wire user_media into the retention, deletion, backup and observability
  lifecycle
status: To Do
assignee: []
created_date: '2026-08-11 16:12'
labels:
  - backend
  - infra
  - compliance
dependencies:
  - task-241
priority: medium
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Phase 5 (§6) of the task-218 benchmark. Découpage de task-219 — reprend l'ancien critère #9 de task-219, qui n'était couvert par aucune autre phase.

Une fois `user_media` en place et alimenté, il doit participer au cycle de vie complet des données plutôt que d'être une table orpheline.

Lire `docs/research/task-218-durable-media-library-persistence/README.md` **§6** — sous-sections §6.1 (rétention), §6.2 (suppression initiée par l'utilisateur), §6.3 (suppression de compte, aujourd'hui manquante — voir §1.6.5), §6.4 (archivage et sauvegarde), §6.5 (observabilité).

Portée : politique de rétention de la bibliothèque explicitement séparée de celle des jobs ; chemin de suppression utilisateur qui est le seul à écrire `purge_at` ; participation de `user_media` à la suppression de compte ; archivage/sauvegarde et fenêtre de restauration ; métriques et alarmes d'observabilité sur les écritures durables.

Lien avec task-224 (suppression de compte in-app avec purge complète des données) : cette tâche fournit la brique `user_media` du périmètre de purge. Coordonner plutôt que dupliquer — si task-224 est déjà partie, se limiter à garantir que `user_media` est bien inclus dans sa purge.

Les agents ont tous les droits pour exécuter `terraform apply` et les commandes AWS CLI sur dev.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 La rétention de la bibliothèque utilisateur est définie et explicitement séparée de la rétention des processing jobs
- [ ] #2 La suppression initiée par l'utilisateur est le seul chemin qui écrit purge_at, et elle est vérifiée en dev
- [ ] #3 user_media est inclus dans le périmètre de purge de la suppression de compte, en coordination avec task-224 sans duplication
- [ ] #4 L'archivage et la sauvegarde de user_media sont en place avec une fenêtre de restauration explicite
- [ ] #5 Des métriques et alarmes couvrent les écritures durables et leurs échecs, conformément à §6.5
- [ ] #6 Une vérification en AWS dev démontre qu'un enregistrement supprimé par l'utilisateur suit bien le cycle purge_at attendu
<!-- AC:END -->
