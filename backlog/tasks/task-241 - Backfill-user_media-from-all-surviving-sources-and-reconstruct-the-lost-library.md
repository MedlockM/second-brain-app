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
- [x] #1 Le script de backfill est idempotent et réexécutable: le relancer converge et ne crée pas de doublon
- [x] #2 Un mode --dry-run existe et est exécuté avant toute écriture réelle, avec un rapport par ligne
- [x] #3 Les 5 sources de §5.3 sont exploitées dans l'ordre de richesse décroissante et une source tardive n'écrase jamais un champ déjà renseigné
- [x] #4 Les media_item_id légataires sont préservés: aucun artefact ni enregistrement Algolia n'est réécrit, les deep links restent valides
- [x] #5 Les lignes user_media_submissions à job_id pendant deviennent des lignes user_media avec last_job_id null
- [x] #6 Les lignes non résolubles (dont les 83 media_artifacts sans media_item_id) sont mises en quarantaine dans un rapport de revue owner, sans inférence de propriétaire
- [x] #7 media_idempotence est réparé: les lignes reserved orphelines sont avancées à processed si un jeu d'artefacts complet existe, sinon remises à zéro
- [x] #8 Le backfill ne supprime ni ne mute processing_jobs, media_artifacts ou S3
- [x] #9 Les lignes backfillées portent schema_version et backfilled_from pour permettre le rollback
- [x] #10 Vérification en AWS dev: après backfill, les 5 dossiers du compte marc.medlock@live.fr contiennent à nouveau les médias récupérés
- [x] #11 Le rapport final énonce explicitement le nombre de médias récupérés, quarantainés et définitivement perdus
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
`scripts/backfill_user_media.py` + a Phase 2 section in
`infrastructure/observability/runbooks/durable-media.md`. Sync boto3, reuses the
canonical `UserMediaRecord` so the item shape cannot drift from the live save path.
Dry run by default, `--apply` to write, `--suffix` allow-list limited to `-dev` and
`-staging` (prod unreachable), plus `--user-id`, `--no-algolia`, `--no-s3`,
`--rollback`.

**Run on AWS dev (eu-west-3):** dry run, then `--apply`, then re-run → `created=0
enriched=0 unchanged=20`, every row resolved through `id_origin=existing_row`, which
proves convergence (AC#1). Final counts: **20 media recovered, 139 quarantined, 4
definitively lost**, plus 91 non-media index rows reported (AC#11).

- 19 of the 20 rows belong to `marc.medlock@live.fr`, spread over 9 of its 13 folders
  (`11 septembre`, `Arabesque`, `Bibou`, `Conversation Papa`, `Les piqûres de Tess` ×3,
  `Surf` ×2, `Test collection` ×2, `Tout pour la lumière`, `Uncategorized` ×7),
  verified through the `folder-index` and `saved-at-index` LSIs (AC#10). The
  description says "the 5 folders"; the account actually has 13, 9 of which now
  contain media. The 4 empty ones never had any surviving trace.
- All 20 rows keep a **legacy uuid** `media_item_id`, 0 deterministic `mi_` ids, and
  `media_artifacts-dev` (166), Algolia `media_items_dev` (35 records),
  `processing_jobs-dev` (22), `user_media_submissions-dev` (26) and the transcripts
  bucket (185 objects) are byte-for-byte unchanged (AC#4, AC#8). The script has no
  write call against any of them.
- The 5 submissions with a dangling `job_id` (`29edcb43`, `3bd9fdf4`, `357d1728`,
  `1d7534d5`, `daaf4187`) became rows keyed by the artifact-derived legacy id with
  **no `last_job_id`** (AC#5). Their titles could not be recovered from any source
  (absent from Algolia, no title in `media_artifacts`) so `title` is null rather than
  invented — the owner can rename them in-app; transcripts and artifacts are intact.
- Ledger repair (AC#7): 15 kept (job alive), 5 advanced to `processed` + `repaired_by`,
  7 reservations released. All 27 rows were stuck at `reserved` — see the findings
  below.

**Two deliberate deviations, both stricter than the letter of the description:**

1. The "**83 of 150** `media_artifacts` rows without `media_item_id`" are now **91 of
   166**, and they are not lost media: every one is an `item_type: request_pointer`
   idempotence index row (`artifact_id = request#<fingerprint>` +
   `active_artifact_id`). They are reported as non-media index rows instead of being
   counted as recoverable media (AC#6).
2. A `reserved` row whose job is gone is advanced to `processed` only when the content
   survives **and** a library row now carries that id; otherwise the reservation is
   released. `_build_duplicate_outcome` returns the ledger's `job_id` as the
   `media_item_id`, so sealing a row as `processed` while no library row carries that
   id would hand the user a media that 404s — the §1.6.1 failure this epic exists to
   fix. 7 rows fell in that case (owner unresolvable → quarantined, so no row).

**Rollback (AC#9):** every created row carries `schema_version: 1` +
`backfilled_from: "<comma-separated sources>"`. `--rollback` deletes exactly those,
under `ConditionExpression="attribute_exists(backfilled_from)"`. Rows that already
existed and were only enriched get `backfill_enriched_from` instead, a deliberately
different attribute so the rollback cannot delete a row a real user save created; it
lists them and refuses. Exercised for real on dev: rolled back the 20 rows, fixed a
bug, re-applied. `--apply` also dumps the pre-image of `media_idempotence` and
`user_media` to the report dir before the only destructive operation.

**Findings for the owner, out of scope here:**

- `media_idempotence.mark_processed` looks **never to be called** in the live
  pipeline: all 27 dev rows sat at `reserved`, including rows whose job completed
  successfully and whose `created_at == updated_at`. Deduplication still works
  (`already_processed` returns any row) but the ledger's status is meaningless, and
  `_status_from_idempotence` therefore reports a completed media as `PENDING`.
- `submit()` calls `try_save_media_for_user` **before** the duplicate short-circuit,
  always deriving the deterministic `mi_` id. Re-saving a recovered media (which keeps
  its legacy uuid) will therefore create a **second** library row for the same
  `media_key`. The backfill handles the converse direction (it reuses an existing row
  found by `media_key` instead of creating a legacy twin), but the save path cannot
  see rows under another id. Deserves a follow-up task.
- The `-dev` tables are the live ones; the unsuffixed copies were left strictly alone
  (task-249).

No automated tests were added, per the repository instruction that forbids them.
Validation was: `ruff`, `py_compile`, the dry run, the apply, the convergence re-run,
the rollback dry run and a read-only AWS verification of both LSIs and of the
unchanged source stores.
<!-- SECTION:NOTES:END -->
