---
id: task-242
title: >-
  Restore processing_jobs hygiene: real archiver, re-enabled TTL and
  silent-failure alarm
status: To Do
assignee: []
created_date: '2026-08-11 16:12'
labels:
  - infra
  - terraform
  - cleanup
dependencies:
  - task-220
priority: medium
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Phase 4 of the task-218 benchmark (§5.5). Découpage de task-219.

Rétablit l'hygiène opérationnelle de `processing_jobs` **une fois que plus rien de visible par l'utilisateur ne lit cette table**. C'est ce qui satisfait le critère de fond : le nettoyage des jobs est préservé, mais la rétention des jobs ne gouverne plus la rétention de la bibliothèque.

**Contrainte d'ordonnancement du benchmark** : cette phase ne doit pas être appliquée avant que la porte de sortie de la Phase 3 (task-220) soit franchie. C'est pour ça qu'elle dépend de task-220.

Lire `docs/research/task-218-durable-media-library-persistence/README.md` **§5.5**.

Portée :

1. Réactiver le TTL sur `processing_jobs` avec une fenêtre choisie par l'owner (30-90 jours ; demander si non tranché).
2. Remplacer `infrastructure/terraform/job_archiver.zip` par un **vrai build** de `media_summarizer/workers/cleanup/job_archiver.py`. Le zip déployé aujourd'hui est un placeholder no-op de 462 octets qui a été invoqué 144 fois sans jamais écrire un seul objet (§1.5).
3. Alarmer sur « REMOVE events > 0 alors que objets archivés == 0 », pour que l'échec silencieux de §1.5 ne puisse pas se reproduire.
4. Purger les 6 stubs `pending` obsolètes de juin.

Vérifier que l'archiver fonctionne réellement **avant** de réactiver le TTL : après réactivation, les lignes supprimées ne sont archivées que si l'archiver a été validé.

Les agents ont tous les droits pour exécuter `terraform apply` et les commandes AWS CLI sur dev.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 Le job_archiver déployé est un vrai build de media_summarizer/workers/cleanup/job_archiver.py et non le placeholder de 462 octets
- [ ] #2 Il est prouvé en AWS dev que l'archiver écrit effectivement des objets dans le bucket d'archives sur un événement REMOVE
- [ ] #3 Le TTL de processing_jobs est réactivé avec la fenêtre choisie par l'owner, après validation de l'archiver
- [ ] #4 Une alarme déclenche quand des REMOVE events surviennent alors qu'aucun objet n'est archivé
- [ ] #5 Les 6 stubs pending obsolètes de juin sont purgés
- [ ] #6 La porte de sortie de task-220 est vérifiée franchie avant toute réactivation du TTL
<!-- AC:END -->
