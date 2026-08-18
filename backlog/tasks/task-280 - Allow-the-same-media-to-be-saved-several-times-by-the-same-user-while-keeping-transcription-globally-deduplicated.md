---
id: task-280
title: >-
  Allow the same media to be saved several times by the same user while keeping
  transcription globally deduplicated
status: Done
assignee:
  - '@Codex'
created_date: '2026-08-17 22:20'
updated_date: '2026-08-18 01:38'
labels:
  - ingestion
  - backend
dependencies:
  - task-279
priority: high
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
## Problem

A user cannot save the same media twice — for instance to file it in two different collections. The library row id is derived from the content and the user:

```
build_media_item_id(user_id, media_key) = "mi_" + sha256(f"{user_id}|{media_key}")[:32]
```

(`core/models/user_media.py:73`), and the row is written with `create_if_absent` (`durable_media_service.py:175`). A second save of the same URL therefore converges on the **same single row** — and because the write is conditional, the folder and tags requested on that second save are silently dropped. The user sees a save that reports success and changes nothing.

This is a deliberate property of the current model ("idempotent by construction... re-saving the same content converges on the same single row instead of creating a duplicate"), and it is the property that has to change.

## What must not change

Deduplication of the **pipeline** stays: the same media must never be transcribed, nor paid for, twice. Idempotence is global across users, keyed by `media_key`, and that stays as it is.

The rule is therefore a separation of two things the current model conflates: *what was processed* (one entity per `media_key`, global) and *what a user saved* (one row per save, with its own folder and tags).

## Scope

A save creates its own library row. `media_item_id` becomes the id of a save, not a function of `(user_id, media_key)`; several rows for one user may share a `media_key`. Folder and tags belong to the row, so two saves of the same URL land in two collections independently, and deleting one does not touch the other.

The reads must follow: a row addresses its content by `media_key` rather than through a job that only the first save owns. That is what makes the deduplicated save — including one deduplicated against **another user's** job — able to show its transcript, which task-279 explicitly left open.

Generated artifacts follow the content, not the row: a second save of an already-processed media must not regenerate or re-bill any artifact, and both rows must surface the same ones.

## Legacy to delete, not to support

Some rows predate the derived id: the task-241 backfill kept the legacy **job id** as `media_item_id`, which is why `resolve_job_for_record` carries a branch for ids that do not start with `mi_` (`durable_media_service.py:260`). On dev this produces exactly the confusing state observed on 2026-08-17 — two rows for the same `media_key`, one legacy and ready, one derived and empty.

Nothing is deployed and there is no installed base: these rows and that branch are deleted in this task, not migrated or supported alongside the new shape.

## Notes to the owner

- DEPLOY CHECK — after merge, save the same YouTube video twice into two different collections and confirm two entries appear, each in its own collection, both showing the same transcript, and that only the first one triggered a provider run.
- Quota is deliberately out of scope here: not debiting a user twice for content they already hold is the follow-up task.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 A library row id is no longer a function of (user_id, media_key): two saves of the same URL by the same user produce two distinct rows
- [x] #2 build_media_item_id and the create_if_absent convergence behaviour are deleted rather than kept behind a flag or a fallback
- [x] #3 Folder and tags requested on a save are always applied to that save's own row, including when the same media is already in the user's library under another folder
- [x] #4 Deleting one of several rows sharing a media_key leaves the others readable and does not purge the shared content
- [x] #5 A row resolves its transcript through its media_key rather than through a job it does not own, so a save deduplicated against another user's job displays the same content
- [x] #6 A save deduplicated against existing content creates no new processing job and triggers no provider call
- [x] #7 Generated artifacts are resolved by content, so a second save of an already-processed media regenerates nothing and both rows surface the same artifacts
- [x] #8 The task-241 legacy rows whose media_item_id is not prefixed mi_ are deleted from user_media-dev, and the resolve_job_for_record branch that exists to support them is removed
- [x] #9 The two YouTube rows sharing media_key mkey_v1_9f75a099… in user_media-dev are reduced to a single coherent state, verified by querying the table with the AWS CLI
- [x] #10 ruff and mypy are clean, and terraform validate plus terraform plan exit 0 for the dev env if any infrastructure is touched
<!-- AC:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
1. Remplacer l'identité déterministe par un identifiant `mi_` aléatoire créé pour chaque sauvegarde et faire de l'écriture `user_media` une création stricte, sans réutilisation, fallback ni kill-switch ; conserver dossier et tags sur cette ligne indépendante.
2. Résoudre le contenu via `media_key` et le registre global d'idempotence, y compris lorsque le job canonique appartient à un autre utilisateur, tout en gardant le pointeur de job propriétaire pour les uploads directs hors registre.
3. Adresser, dédupliquer et lister les artefacts média par `(user_id, media_key)` en conservant `media_item_id` comme contrat public ; dédupliquer aussi les sources identiques d'une collection.
4. Ajouter l'index `media-key-index`, propager l'état du job à toutes les sauvegardes du contenu et protéger les cascades pour ne supprimer artefacts, objets et registre qu'après la disparition de la dernière ligne retenue.
5. Supprimer le backfill task-241 et ses branches legacy, puis effacer de `user_media-dev` les lignes non préfixées `mi_` et vérifier l'état YouTube ciblé par lectures AWS cohérentes.
6. Aligner le contrat canonique, la politique de rétention, le runbook et Terraform ; exécuter les contrôles statiques et Terraform, auditer les secrets, puis commiter uniquement le périmètre task-280 en préservant task-283.
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
## Résultat

- Chaque sauvegarde reçoit désormais un identifiant `mi_` UUID distinct et une nouvelle ligne conditionnelle ; le dossier et les tags ne peuvent plus être absorbés par une ligne antérieure. L'ancien générateur déterministe, `create_if_absent`, le kill-switch `DURABLE_MEDIA_ENABLED`, les champs/fallbacks de backfill et le script task-241 ont été supprimés.
- Les lectures de transcript partent du `media_key` vers le registre global et acceptent le job canonique quel que soit son propriétaire après validation de la ligne utilisateur. Une duplication déjà traitée ne persiste aucun nouveau job et n'appelle aucun fournisseur ; elle finalise seulement la nouvelle sauvegarde.
- `media-key-index` permet de propager état et métadonnées à toutes les sauvegardes. Les artefacts média utilisent `(user_id, media_key)` pour leur clé interne, leur déduplication et leur historique, tandis que l'API continue d'accepter l'identifiant de sauvegarde. Les doublons d'une collection ne comptent qu'une source de contenu.
- La purge compte toutes les lignes encore retenues, y compris celles en période de grâce : elle conserve les artefacts tant que le même utilisateur possède une autre référence et conserve les objets de traitement ainsi que le registre tant qu'une référence globale subsiste.

## Données dev

- Les 20 lignes legacy task-241 ont été supprimées de `user_media-dev`. Une lecture fortement cohérente confirme `legacy_count=0` sur 6 lignes.
- Le préfixe `mkey_v1_9f75a099…` ne retourne plus qu'une ligne `mi_`, au statut `ready`. Aucun identifiant d'utilisateur ni payload sensible n'est consigné ici.
- Ces suppressions restent récupérables via le PITR DynamoDB pendant la fenêtre de restauration de la table.

## Vérifications

- `ruff check media_summarizer` : OK.
- `mypy media_summarizer` : OK, 169 fichiers.
- Complétude `.env.example`, invariant des écrivains `purge_at`/`deleted_at` et `git diff --check` : OK.
- `terraform fmt -check` et `terraform validate` sur dev : OK.
- `terraform plan` sur dev : sortie 0, `1 to add, 19 to change, 0 to destroy` ; aucune destruction.
- Aucun test automatisé ajouté ou exécuté, conformément aux règles de livraison du dépôt.
<!-- SECTION:NOTES:END -->
