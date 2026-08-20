---
id: task-311
title: Purge last_engaged_at beyond the 90-day window so nothing is stored past it
status: Done
assignee: []
created_date: '2026-08-20 21:04'
updated_date: '2026-08-21 00:20'
labels:
  - backend
  - phase-6
dependencies:
  - task-305
priority: medium
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
The engagement signal behind the Inbox "Continue learning" row (task-305, Option A of `docs/research/task-303-engagement-recency-model/README.md`) is one attribute, `last_engaged_at`, on `user_media_v1` and `user_folders_v1` rows. The 90-day freshness window is enforced **only at read time** — `engagement_service.list_recent` queries the sparse `engaged-index` with a sort-key range condition — so a stamp written 6 months ago is still stored, and still occupies an entry in the GSI, forever.

The owner has decided there is no reason to keep it: past 90 days the value must be **removed from the row**, not merely hidden. Removing the attribute also removes the row from the sparse GSI, which is the point — the index should hold engaged items, not the whole history of them.

## Why not a TTL

DynamoDB allows one TTL attribute per table, `user_media_v1` already uses it for `purge_at` (user-initiated deletion, invariant I2), and `dynamodb_user_media.tf:126-134` forbids adding a second one. A TTL would also destroy the whole library row, not one attribute — the wrong granularity entirely. The purge is therefore an explicit write.

## Where it goes

The daily reconciliation of the `media_lifecycle` worker (`media_summarizer/workers/cleanup/media_lifecycle.py:343`, `run_reconciliation`, EventBridge `cron(30 3 * * ? *)`) **already scans `user_media` end to end** with a `ProjectionExpression` (`:349-352`). Adding `last_engaged_at` to that projection and issuing the removals from the same pass costs one extra attribute per scanned row and no new schedule, no new Lambda, no new IAM. `user_folders_v1` is **not** scanned today and needs its own pass — that table carries the attribute with no index of its own, by design.

## Scope

- Extend the daily reconciliation to remove every `last_engaged_at` older than the window, on both `user_media_v1` and `user_folders_v1`.
- The window comes from `engagement_service.RECENT_WINDOW_DAYS` — one source of truth, not a second constant that can drift from the read path.
- Report the count in the existing `EVENT_RECONCILED` structured log alongside the other gauges, so a systematic failure is visible in CloudWatch.

## Constraints

- **Conditional write.** The removal must carry a condition on `last_engaged_at` still being older than the cutoff, so an engagement stamped between the scan and the write is never erased.
- **Never through `user_media.update_attributes`.** That helper always appends `updated_at`, and `updated_at` is the cache key of the `expo-image` covers — purging through it would invalidate every cover in the app. Use a targeted `UpdateItem` with `REMOVE`, the way `stamp_engagement` does its `SET`.
- **Do not touch `purge_at`, `deleted_at`, or any other attribute.** `scripts/check_purge_at_writers.py` must stay green (invariant I2).
- Soft-deleted rows (`deleted_at` present) are already excluded from the row at read time; purging their stale stamp too is fine, but must not resurrect or modify anything else about them.
- A failed purge must not fail the reconciliation as a whole — it logs and the run continues, like the other reconciliation gauges.
- No automated tests unless the owner asks. `ruff` and `mypy` clean.
- Nothing is deployed (`AGENTS.md`): no compatibility path, no flag to keep the old behaviour.

## Owner notes (not acceptance criteria)

- Applied on the next deploy of the worker image; the purge then runs at the next 03:30 UTC schedule. Nothing to `terraform apply` is expected — verify with `terraform plan` that this is indeed the case.
- Owner-side check after deploy: invoke the Lambda manually (or wait for the schedule), then confirm with the AWS CLI that no `user_media-dev` or `user_folders-dev` row carries a `last_engaged_at` older than 90 days, and that the `user_media.reconciled` log event reports the count of removals.
- The visible behaviour of "Continue learning" does not change at all — the read path already ignored these values. This task is about what is stored, not what is shown.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 The daily reconciliation removes last_engaged_at from every user_media_v1 row whose value is older than the window, and from every user_folders_v1 row likewise, in the same scheduled run
- [x] #2 The cutoff is derived from engagement_service.RECENT_WINDOW_DAYS with no second window constant introduced anywhere
- [x] #3 Each removal is a targeted UpdateItem with a REMOVE expression guarded by a condition on last_engaged_at still being older than the cutoff, and no code path routes it through user_media.update_attributes
- [x] #4 No attribute other than last_engaged_at is written or removed by the new code, and python scripts/check_purge_at_writers.py exits 0
- [x] #5 The count of removed stamps is reported in the reconciliation's existing structured log event alongside the other gauges
- [x] #6 A failure on one removal is logged and does not abort the reconciliation run or raise out of it
- [x] #7 ruff check . and mypy media_summarizer/ are clean, and terraform validate plus terraform plan exit 0 for the -dev environment with no infrastructure change required by this task
- [x] #8 A comment at the purge site records why this is an explicit write and not a TTL (one TTL per table, purge_at owns it, wrong granularity), so the next reader does not re-litigate it
<!-- AC:END -->


## Implementation Notes
<!-- SECTION:NOTES:BEGIN -->
La purge vit dans la réconciliation quotidienne du worker `media_lifecycle` (`run_reconciliation`, EventBridge `cron(30 3 * * ? *)`), comme prévu par la description : pas de nouveau schedule, pas de nouveau Lambda, pas de nouvel IAM.

**`user_media_v1`** — `last_engaged_at` a été ajouté à la `ProjectionExpression` du scan qui parcourait déjà la table de bout en bout ; le coût est d'un attribut de plus par ligne scannée. Les lignes soft-deleted sont purgées aussi : leur stamp est déjà invisible du chemin de lecture, et le laisser les maintiendrait dans le GSI sparse jusqu'au balayage TTL 30 jours plus tard. Rien d'autre sur ces lignes n'est touché.

**`user_folders_v1`** — n'était pas scannée : elle a sa propre passe, projection `#fid, last_engaged_at` (le `id` passe par un placeholder de nom, même précaution que `scope` plus haut vis-à-vis de la liste des mots réservés DynamoDB).

**Fenêtre (AC #2)** — `engagement_cutoff = (now - timedelta(days=RECENT_WINDOW_DAYS)).isoformat()`, importé de `engagement_service`. Aucune seconde constante introduite ; `grep -rn "RECENT_WINDOW_DAYS"` ne renvoie que la définition et ses deux lecteurs (le chemin de lecture et celui-ci).

**Forme de l'écriture (AC #3)** — `UpdateItem` ciblé, `UpdateExpression="REMOVE last_engaged_at"`, `ConditionExpression="last_engaged_at < :cutoff"`. Jamais via `user_media.update_attributes`, qui appose systématiquement `updated_at` — la clé de cache des couvertures `expo-image`. Même forme que le `SET` de `stamp_engagement`. La comparaison est lexicographique sur la chaîne ISO-8601, exactement celle que font déjà `stamp_engagement` et la range condition de `engaged-index` : tous les stamps sont écrits en `isoformat()` UTC, les deux ordres coïncident. La sélection Python utilise la même comparaison que la condition DynamoDB, pour qu'elles ne puissent pas diverger.

**Robustesse (AC #6)** — trois niveaux : une `ConditionalCheckFailedException` par ligne est un `continue` silencieux (ré-engagement entre le scan et l'écriture, ou run concurrent — deux issues correctes) ; toute autre erreur par ligne est journalisée et la boucle continue ; et chacune des deux passes est enveloppée à son point d'appel, de sorte qu'un échec de scan ou de session ne coûte pas la publication des jauges de la réconciliation.

**Jauges (AC #5)** — `engagement_stamps_purged_media` et `engagement_stamps_purged_collections` sont ajoutées au `report`, donc au `user_media.reconciliation_completed` existant, aux côtés des autres.

**Vérifications**
- `ruff check .` et `mypy media_summarizer/` (173 fichiers) propres.
- `python scripts/check_purge_at_writers.py` → exit 0, invariant I2 intact (le `REMOVE` porte sur `last_engaged_at`, jamais sur `purge_at`/`deleted_at`).
- Contre le `-dev` réel : les deux `ProjectionExpression` du code s'exécutent telles quelles (`user_folders-dev` 19 lignes, `user_media-dev` 21). Le `UpdateItem` conditionnel a été soumis tel quel à `user_media-dev` avec un cutoff `1970-01-01` — réponse `ConditionalCheckFailedException`, donc l'expression est acceptée par DynamoDB et rien n'a été muté. Schéma de clé confirmé : `user_folders-dev` en HASH `id` seul, d'où `key_fields=("id",)`.
- Import du module vérifié : l'ajout de `engagement_service` n'introduit ni import circulaire ni nouvelle variable d'environnement (la chaîne d'import atteignait déjà `translation_idempotence` avant ce changement).
- `terraform validate` OK sur `envs/dev`, `terraform plan` exit 0.

**État réel de dev (utile à l'owner)** — aucune ligne de `user_media-dev` ni de `user_folders-dev` ne porte `last_engaged_at` aujourd'hui (`Count: 0` avec `attribute_exists(last_engaged_at)`), la purge ne trouvera donc rien au premier passage. Ce n'est pas un problème, mais cela veut dire que la vérification owner ci-dessous n'aura de contenu qu'après quelques engagements réels.

**Note sur `terraform plan` (AC #7)** — le plan n'est pas vide : il annonce `module.platform.aws_dynamodb_table.user_media_v1 will be updated in-place`, c'est-à-dire la **création du GSI `engaged-index`** — un reste de task-305 non encore appliqué sur dev, sans rapport avec cette tâche. Cette tâche ne modifie aucun fichier `.tf` (`git status --porcelain | grep '\.tf$'` est vide) : aucun changement d'infrastructure n'est requis par elle, et l'IAM couvre déjà `Scan`/`UpdateItem` sur toutes les tables `*-dev` via `local.table_arns`, tandis que `USER_FOLDERS_TABLE` est déjà dans `local.lambda_environment`.

**Notes owner (hors AC)**
- Appliqué au prochain déploiement de l'image worker ; la purge tourne ensuite au schedule de 03:30 UTC. Rien à `terraform apply` pour cette tâche — mais l'`engaged-index` de task-305 attend toujours son apply sur dev.
- Après déploiement : invoquer le Lambda manuellement (ou attendre le schedule), puis vérifier à l'AWS CLI qu'aucune ligne `user_media-dev` / `user_folders-dev` ne porte de `last_engaged_at` de plus de 90 jours, et que `user_media.reconciliation_completed` rapporte bien les deux compteurs.
- Le comportement visible de « Continue learning » ne change pas : le chemin de lecture ignorait déjà ces valeurs.
<!-- SECTION:NOTES:END -->
