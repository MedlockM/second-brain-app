---
id: task-241
title: >-
  Backfill user_media from all surviving sources and reconstruct the lost
  library
status: To Do
assignee: []
created_date: '2026-08-11 16:11'
labels:
  - backend
  - migration
  - data-safety
dependencies:
  - task-240
priority: high
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Phase 2 of the task-218 benchmark (§5.3). Découpage de task-219.

Reconstruit la bibliothèque à partir de toutes les sources survivantes. Script de backfill **idempotent, réexécutable, `--dry-run` d'abord**, émettant un rapport ligne par ligne.

Lire `docs/research/task-218-durable-media-library-persistence/README.md` **§5.3** — il donne le tableau des 5 sources par richesse décroissante et les volumes réels constatés en dev. Règle générale : une source plus tardive n'écrase jamais un champ déjà renseigné par une source plus riche.

Sources, dans l'ordre : (1) `processing_jobs` survivants, (2) `user_media_submissions` (prouve la propriété même quand le job a disparu), (3) `media_artifacts` + GSI `media-item-index`, (4) index Algolia (souvent la seule copie survivante du titre), (5) préfixes de clés S3 en dernier recours.

Règles impératives du benchmark :

- **Les ids légataires sont préservés.** Une ligne migrée garde `media_item_id = <l'id déjà utilisé par les artefacts et Algolia>`, pour que `media_artifacts.media_item_id`, les `objectID` Algolia (`{media_item_id}_chunk_{i}`), les caches mobiles et les deep links restent valides. **Aucune réécriture des artefacts ou des enregistrements Algolia n'est nécessaire.** Seules les *nouvelles* sauvegardes utilisent l'id déterministe ; le mélange de formats est sûr car l'id est opaque.
- **Les références pendantes de `user_media_submissions` ne sont pas réparées, elles sont supplantées.** Chaque ligne devient une ligne `user_media` clé par l'id dérivé des artefacts s'il existe, sinon par l'id déterministe calculé depuis `(user_id, media_key)` ; `last_job_id` reste null.
- **Les lignes non résolubles sont mises en quarantaine, jamais devinées.** Les **83 lignes sur 150** de `media_artifacts` sans attribut `media_item_id`, et tout groupe d'artefacts dont le `user_id` ne peut être établi via les sources 2-4, partent dans un rapport pour revue manuelle de l'owner. La propriété n'est jamais inférée du fait que dev est mono-utilisateur.
- **`media_idempotence` est réparé** : les lignes bloquées à `reserved` dont le job n'existe plus passent à `processed` quand un jeu d'artefacts complet existe, sinon sont remises à zéro pour que le média puisse être légitimement réingéré.
- Le backfill ne supprime ni ne mute jamais `processing_jobs`, `media_artifacts` ou S3.

Cas de régression nommé par le benchmark : après cette tâche, les 5 dossiers du compte `marc.medlock@live.fr` doivent à nouveau contenir les médias récupérés.

Rollback : supprimer les lignes backfillées, identifiables par `schema_version` + un attribut `backfilled_from`.

Les agents ont tous les droits pour exécuter les commandes AWS CLI sur dev.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 Le script de backfill est idempotent et réexécutable: le relancer converge et ne crée pas de doublon
- [ ] #2 Un mode --dry-run existe et est exécuté avant toute écriture réelle, avec un rapport par ligne
- [ ] #3 Les 5 sources de §5.3 sont exploitées dans l'ordre de richesse décroissante et une source tardive n'écrase jamais un champ déjà renseigné
- [ ] #4 Les media_item_id légataires sont préservés: aucun artefact ni enregistrement Algolia n'est réécrit, les deep links restent valides
- [ ] #5 Les lignes user_media_submissions à job_id pendant deviennent des lignes user_media avec last_job_id null
- [ ] #6 Les lignes non résolubles (dont les 83 media_artifacts sans media_item_id) sont mises en quarantaine dans un rapport de revue owner, sans inférence de propriétaire
- [ ] #7 media_idempotence est réparé: les lignes reserved orphelines sont avancées à processed si un jeu d'artefacts complet existe, sinon remises à zéro
- [ ] #8 Le backfill ne supprime ni ne mute processing_jobs, media_artifacts ou S3
- [ ] #9 Les lignes backfillées portent schema_version et backfilled_from pour permettre le rollback
- [ ] #10 Vérification en AWS dev: après backfill, les 5 dossiers du compte marc.medlock@live.fr contiennent à nouveau les médias récupérés
- [ ] #11 Le rapport final énonce explicitement le nombre de médias récupérés, quarantainés et définitivement perdus
<!-- AC:END -->
