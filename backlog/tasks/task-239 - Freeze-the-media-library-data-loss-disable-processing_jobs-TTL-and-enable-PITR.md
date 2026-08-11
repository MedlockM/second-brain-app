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
- [x] #1 Le TTL de la table processing_jobs est désactivé en dev et un apply le confirme
- [x] #2 Le PITR est activé sur processing_jobs, user_folders, user_tags, media_artifacts et user_media_submissions
- [x] #3 Un backup on-demand et un export Scan vers S3 de l'état courant existent avant toute écriture de migration
- [x] #4 La désactivation du TTL est vérifiée côté AWS (describe-time-to-live) et non seulement dans le code Terraform
- [x] #5 Le nombre de lignes processing_jobs survivantes est relevé et consigné avant/après, pour mesurer ce que le gel a permis de récupérer
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Executed 2026-08-11 against AWS dev account `125313707865` in `eu-west-3`.

### Order of operations

The TTL was killed first via the AWS CLI (`update-time-to-live`) rather than waiting for a
Terraform round-trip, because every minute of delay is a potentially unrecoverable row. The
Terraform config was updated immediately afterwards so nothing can re-enable it; the
subsequent `plan` therefore reported no TTL drift (AWS and code already agreed) and the final
`plan -detailed-exitcode` returned **"No changes. Your infrastructure matches the
configuration."**

Terraform was applied with `-target` on the five tables only, to keep this change surgical and
avoid touching unrelated resources ahead of the task-237 restructuring: `Apply complete!
Resources: 0 added, 5 changed, 0 destroyed.`

### AC #4 — AWS-side verification, not just Terraform code

`aws dynamodb describe-time-to-live --table-name processing_jobs`:

| When | `TimeToLiveStatus` | `AttributeName` |
|---|---|---|
| Before (2026-08-11 ~18:23 CEST) | `ENABLED` | `expire_at` |
| After the freeze | `DISABLED` | — (attribute no longer reported) |

`aws dynamodb describe-continuous-backups` on all five tables returns
`PointInTimeRecoveryStatus: ENABLED`, `RecoveryPeriodInDays: 35`,
`EarliestRestorableDateTime: 2026-08-11T18:24:18+02:00` — the restore window starts here.
Before this task, PITR was `DISABLED` on all of them (§1.5 of the benchmark).

### AC #5 — surviving processing_jobs rows, before/after

| Reading | Rows |
|---|---|
| Table-wide before the freeze (`scan --select COUNT`) | **22** |
| Table-wide after the freeze | **22** — zero rows lost during the operation |
| Benchmark baseline, 2026-08-05 (§1.4) | 7 |

Breakdown of the 22 rows at freeze time:

| Cohort | Count |
|---|---|
| Carrying `expire_at` (i.e. scheduled for deletion) | **16** — all `completed` except one `failed` |
| Without any `expire_at` (stale June `pending` stubs) | 6 |
| Belonging to the owner `4cd1abcb-…` (`marc.medlock@live.fr`) | 14 |
| Distinct users represented | 8 |
| Rows already expired but not yet swept (recoverable by the freeze) | **0** |

Earliest `expire_at` was `1788301872` = **2026-09-01T22:31:12Z**, latest `1788994876` =
2026-09-09T23:01:16Z (current epoch at freeze time: `1786465582`).

**What the freeze bought:** nothing was recovered retroactively — no row was in the
expired-but-not-yet-swept state, so the "TTL off can resurrect recent rows" effect did not
apply here. What it did do is take **16 rows off death row**, the first of which would have
started disappearing on **2026-09-01**, i.e. 21 days out. The whole `completed` cohort — the
only rows that carry any real library content — was scheduled for deletion; consistent with
§1.4's finding that the TTL selects *against* successfully processed media.

Context for the follow-up migration tasks: `media_artifacts` now holds **166 rows** spanning
**27 distinct `media_item_id`s**, versus 22 jobs, and **91 of 166 rows still carry no
`media_item_id` attribute at all** (benchmark §1.4 saw 150 / 20 / 83).

### AC #3 — pre-migration snapshot

On-demand backups, all `AVAILABLE`:

| Table | Backup name | Size (bytes) |
|---|---|---|
| processing_jobs | `task239-freeze-20260811-processing-jobs` | 29014 |
| user_folders | `task239-freeze-20260811-user-folders` | 2692 |
| user_tags | `task239-freeze-20260811-user-tags` | 190 |
| media_artifacts | `task239-freeze-20260811-media-artifacts` | 97260 |
| user_media_submissions | `task239-freeze-20260811-user-media-submissions` | 6281 |

`Scan` exports (full, no `LastEvaluatedKey` on any table, so no truncation) uploaded to
`s3://media-summarizer-archives-125313707865-dev/snapshots/task-239-freeze/2026-08-11/`:
`processing_jobs.json` (22 items), `user_folders.json` (14), `user_tags.json` (1),
`media_artifacts.json` (166), `user_media_submissions.json` (27), plus
`media_idempotence.json` (27) which is not in scope but is a §5.3 backfill source and was free
to capture. Note the archives bucket lifecycle transitions objects to `GLACIER_IR` at day 0
(instant retrieval, no restore step) and expires them at 365 days.

### Reversibility and the trap to avoid

Re-applying the previous Terraform would re-enable the TTL and resume the deletions — do not
roll this back. The `ttl` block is kept in the config with `enabled = false` and a comment
naming Phase 4 as the only moment it may return, once nothing user-facing reads
`processing_jobs`.

No automated tests were added, per the project agent instructions.
<!-- SECTION:NOTES:END -->
