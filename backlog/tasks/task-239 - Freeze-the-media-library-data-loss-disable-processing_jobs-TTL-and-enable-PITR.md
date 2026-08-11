---
id: task-239
title: >-
  Freeze the media-library data loss: disable processing_jobs TTL and enable
  PITR
status: To Do
assignee: []
created_date: '2026-08-11 16:10'
labels:
  - infra
  - terraform
  - data-safety
  - urgent
dependencies: []
priority: high
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Phase 0 of the task-218 benchmark (§5.1). Découpage de task-219.

**Urgent et autonome.** La bibliothèque média perd des données en ce moment : d'après §1.4 du benchmark, le compte de l'owner a 5 dossiers et 6 enregistrements de submission mais **un seul** processing job survivant. Le TTL de `processing_jobs` supprime des lignes dont dépendent tous les chemins de lecture de la bibliothèque.

Cette tâche est un gel, pas la correction de fond : c'est l'Option C utilisée **uniquement comme freeze**, jamais comme état final. Elle ne dépend d'aucune autre tâche et doit partir en premier.

Portée (voir §5.1 pour les détails) :

1. Désactiver le `ttl` sur la table `processing_jobs` (`infrastructure/terraform/dynamodb_core_tables.tf:62-66`) et appliquer. DynamoDB arrête immédiatement de supprimer, quelles que soient les valeurs `expire_at` déjà présentes. Les lignes expirées mais pas encore balayées redeviennent lisibles — appliquer ceci **avant tout le reste** peut donc récupérer des données des derniers jours.
2. Activer le PITR sur `processing_jobs`, `user_folders`, `user_tags`, `media_artifacts`, `user_media_submissions` → fenêtre de restauration de 35 jours.
3. Prendre un snapshot de l'état courant (backup on-demand + export `Scan` vers S3) avant toute écriture de migration ultérieure.

Changement d'infra d'une ligne côté TTL, aucun code, aucune migration. Réversible en réappliquant le Terraform précédent.

Note factuelle importante (§1.5) : il n'existe aujourd'hui aucun filet de récupération — le PITR est désactivé et la Lambda `job-archiver` déployée est un placeholder no-op de 462 octets (144 invocations, 0 objet écrit). Le point 2 est ce qui crée ce filet pour toutes les tâches suivantes.

Les agents ont tous les droits pour exécuter `terraform apply` et les commandes AWS CLI sur dev.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 Le TTL de la table processing_jobs est désactivé en dev et un apply le confirme
- [ ] #2 Le PITR est activé sur processing_jobs, user_folders, user_tags, media_artifacts et user_media_submissions
- [ ] #3 Un backup on-demand et un export Scan vers S3 de l'état courant existent avant toute écriture de migration
- [ ] #4 La désactivation du TTL est vérifiée côté AWS (describe-time-to-live) et non seulement dans le code Terraform
- [ ] #5 Le nombre de lignes processing_jobs survivantes est relevé et consigné avant/après, pour mesurer ce que le gel a permis de récupérer
<!-- AC:END -->
