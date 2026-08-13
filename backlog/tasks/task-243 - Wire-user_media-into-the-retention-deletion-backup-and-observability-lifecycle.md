---
id: task-243
title: >-
  Wire user_media into the retention, deletion, backup and observability
  lifecycle
status: Done
assignee: []
created_date: '2026-08-11 16:12'
updated_date: '2026-08-13 08:40'
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
- [x] #1 La rétention de la bibliothèque utilisateur est définie et explicitement séparée de la rétention des processing jobs
- [x] #2 La suppression initiée par l'utilisateur est le seul chemin qui écrit purge_at, et elle est vérifiée en dev
- [x] #3 user_media est inclus dans le périmètre de purge de la suppression de compte, en coordination avec task-224 sans duplication
- [x] #4 L'archivage et la sauvegarde de user_media sont en place avec une fenêtre de restauration explicite
- [x] #5 Des métriques et alarmes couvrent les écritures durables et leurs échecs, conformément à §6.5
- [x] #6 Une vérification en AWS dev démontre qu'un enregistrement supprimé par l'utilisateur suit bien le cycle purge_at attendu
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
## 2026-08-13 — implémentation

### Les deux horloges (AC#1)

`docs/DATA_RETENTION.md` est le document de référence : **la bibliothèque d'un
utilisateur n'a pas d'horloge de rétention**, seul l'utilisateur peut y mettre
fin. La séparation avec `processing_jobs.expire_at` est structurelle et pas
conventionnelle : `purge_at` / `deleted_at` ne sont écrits que par
`utils/user_media.mark_deleted`, `update_attributes` les rejette
(`_FORBIDDEN_UPDATE_ATTRS`), et `scripts/check_purge_at_writers.py` (branché dans
`.github/workflows/pr.yml`) fait échouer la CI si un second écrivain apparaît.

### Suppression utilisateur (AC#2)

`DELETE /api/media/{media_item_id}` → `core/services/media_deletion_service.py` :
soft delete (`deleted_at`, `purge_at = now + 30 j`), invisible immédiatement
(filtre de lecture DynamoDB + suppression Algolia synchrone), idempotent (une
seconde suppression renvoie 200 avec le `purge_at` d'origine, elle ne repousse pas
la purge). Documenté dans `docs/CANONICAL_MEDIA_API_CONTRACT.md` §6) et dans
l'OpenAPI. Le passage job-id → id durable dans `_resolve_row` est marqué
`TASK-220` : à supprimer dès que l'API ne distribue plus que des ids durables.

Trou fermé au passage : sauver de nouveau une URL supprimée mais pas encore purgée
**réveille** la ligne (`create_if_absent` efface les deux attributs), sinon le
nouveau save atterrissait sur une ligne invisible détruite 30 jours plus tard.

### Purge après TTL (AC#2, AC#3)

`workers/cleanup/media_lifecycle.py`, une Lambda deux déclencheurs (stream
`REMOVE` filtré + schedule quotidien). Classification volontaire des REMOVE :
sweep TTL avec `deleted_at` → cascade ; sweep TTL **sans** `deleted_at` → alarme
`unexplained_purge` et **pas** de cascade (le contenu reste récupérable le temps
de corriger l'écrivain illégal) ; suppression par un appelant → pas de cascade
(la suppression de compte cascade en ligne, sur tout le compte).

Coordination task-224 sans duplication : la cascade par média a été **extraite**
de `account_deletion_service` vers `core/services/media_purge_service.py`, appelée
par les deux chemins. `user_media` reste dans le périmètre de la purge de compte
(étape 6, `delete_all_for_user`), et comme l'inventaire passe par
`list_all_for_user` — qui inclut délibérément les lignes soft-deleted — les
artifacts d'un média supprimé mais pas encore purgé partent aussi.

### Backup (AC#4)

`infrastructure/terraform/modules/platform/backup_library.tf` : trois étages,
trois fenêtres explicites — PITR 35 j (déjà en place), snapshots AWS Backup
hebdo 90 j (vault `media-summarizer-library-<env>`, sans `force_destroy`), exports
S3 DYNAMODB_JSON mensuels 365 j (règle de cycle de vie du bucket archives) sur
`user_media`, `user_folders`, `user_tags`, `media_artifacts`. Un export réel a été
déclenché en dev via une schedule `at(...)` temporaire utilisant le même rôle et
le même input : `COMPLETED`, 20 items, manifeste sous
`dynamodb-exports/user_media-dev/`. **Un restore n'est jamais transparent** :
DynamoDB restaure dans une *nouvelle* table sans la config TTL — réactiver le TTL
`purge_at` est une étape obligatoire, et l'alarme `purge-overdue` est ce qui
rattrape l'oubli. Procédure dans le runbook.

### Observabilité (AC#5)

`durable_media_alerts.tf` : 13 metric filters (dont les gauges numériques de la
réconciliation) et 7 alarmes, toutes des métriques d'**outcome** — suppression en
échec, purge inexpliquée, cascade en échec, sweeps TTL sans cascade (math
CloudWatch contre `TimeToLiveDeletedItemCount`), purges en retard, orphelins
récents (fenêtre 48 h, parce que le backfill task-241 crée une dérive permanente),
réconciliation arrêtée (`treat_missing_data = breaching`). L'ancienne alarme
« les suppressions TTL doivent rester à zéro » est supprimée : elle devenait fausse
le jour où la suppression utilisateur existe.

Non fait volontairement : le balayage hebdomadaire des orphelins Algolia de §6.5
(pas d'helper de browse ; la suppression synchrone + la cascade font qu'un orphelin
demande une double panne, elle-même alarmée). Les alarmes archiver de §6.5
appartiennent à task-242.

### Vérification dev (AC#6)

Script one-off (non versionné) exécuté contre les vraies ressources dev, 20 checks
verts (dont le réveil sur re-save) : `purge_at = now + 30 j`, ligne invisible en lecture normale mais lisible
avec `include_deleted`, seconde suppression idempotente, OldImage réelle lue sur la
table → cascade complète (ligne artifact, objet S3 d'artifact, objet transcript),
sweep TTL sans `deleted_at` → `unexplained_purge` sans cascade, REMOVE par un
appelant → pas de cascade, `update_attributes` refuse les deux attributs, sortie de
`run_reconciliation()`. Aucune donnée synthétique laissée en dev.

Conflit à trancher par l'owner : `docs/compliance/privacy-policy.md` §7 annonce des
sauvegardes qui expirent « sous 35 jours », alors que les étages mandatés par §6.4
vont à 90 j (snapshots) et 365 j (exports). Détaillé dans `docs/DATA_RETENTION.md`
§6.
<!-- SECTION:NOTES:END -->
