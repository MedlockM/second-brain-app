---
id: task-246
title: Purge the orphaned E2E accounts and their rows from dev DynamoDB
status: In Progress
assignee: []
created_date: '2026-08-12 16:39'
updated_date: '2026-08-12 17:05'
labels:
  - cleanup
  - infra
  - e2e
dependencies: []
priority: medium
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
## Contexte

Aucun nettoyage n'a jamais tourné : les comptes créés par les runs E2E s'accumulent depuis juin 2026. Mesuré le 2026-08-12 en région `eu-west-3` :

| Table | Comptes | Dont orphelins E2E |
|---|---|---|
| `users-dev` | 33 | **31** (23 `e2e-register-*`, 7 `e2e-test-*`, 1 `phase4-*`) |
| `users` | 25 | **22** |

Et ces comptes ne sont pas isolés — leurs lignes filles polluent les tables liées :

| Table | Lignes appartenant à un compte orphelin |
|---|---|
| `auth_tokens-dev` | 72 / 195 (37 %) |
| `auth_tokens` | 56 / 154 (36 %) |
| `processing_jobs-dev` | 6 / 28 (21 %) |
| `user_usage_monthly-dev` | 8 / 87 (9 %) |
| `user_media_submissions-dev` | 1 / 27 (4 %) |

Deux sources distinctes, à traiter toutes les deux :
- `e2e-register-<run_id>-<attempt>-<platform>@test.local` — créés par `mobile/.maestro/01_login.yaml:31` à **chaque run CI Maestro**, jamais supprimés (aucune étape de teardown dans `.github/workflows/mobile-e2e-maestro.yml`).
- `e2e-test-<timestamp>-<hex>@test.local` — créés par la fixture `test_user` de `tests/e2e/conftest.py:52`, dont le teardown est systématiquement sauté en local (voir la tâche de correction liée).

Enjeu de sécurité, pas seulement d'hygiène : tous ces comptes partagent le mot de passe issu de `E2E_TEST_USER_PASSWORD`. À la fuite du 2026-08-11 (artifact public du run 31514654593), **chacun** était donc compromis, pas seulement le compte principal. La rotation du 2026-08-12 n'a traité que `e2e-maestro-20260809200952@test.local`.

## Scope

1. Écrire `scripts/purge_e2e_accounts.py`, réutilisable et idempotent, qui balaie `users-dev` **et** `users` (les tables historiques non suffixées coexistent toujours, héritage de task-237), sélectionne les comptes E2E par préfixe d'email, et supprime pour chacun ses lignes dans les tables liées avant la ligne `users` elle-même.
2. Ne pas se contenter d'appeler `database_async.delete_user()` : il ne supprime **que** la ligne `users` (`media_summarizer/utils/database_async.py:239-248`), ce qui laisse précisément les 72 + 56 tokens et le reste orphelins. C'est la cause de l'état actuel.
3. Exécuter la purge sur dev et sur les tables non suffixées.

## Précautions

- **Ne jamais supprimer** `e2e-maestro-20260809200952@test.local` : c'est le compte permanent désigné par le secret `E2E_TEST_USER_EMAIL`, celui dont dépendent les six flows. Le protéger par une liste d'exclusion explicite, pas par un `if` sur un préfixe.
- **Ne jamais toucher** aux comptes ne matchant aucun préfixe E2E connu (il y a un compte réel dans chaque table). Un mode `--dry-run` par défaut, listant ce qui serait supprimé, est le minimum.
- Le PITR est ENABLED sur les cinq tables `-dev` mais **DISABLED** sur l'ancienne `users` — l'erreur y serait irréversible. Traiter `users-dev` d'abord et vérifier le résultat avant de passer à `users`.
- Faire tourner un run E2E vert après la purge : c'est la seule preuve que rien d'utilisé n'a été emporté.

## Références

- `tests/e2e/conftest.py:163-279` (la logique de teardown existante énumère déjà les tables à balayer — la reprendre plutôt que la réinventer)
- `mobile/.maestro/01_login.yaml:31`, `.github/workflows/mobile-e2e-maestro.yml`
- task-237 (Implementation Notes : « 7 utilisateurs `e2e-test-*` orphelins », constat initial ; tables en triplicate)
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 scripts/purge_e2e_accounts.py exists, defaults to a dry run, and requires an explicit flag to delete
- [x] #2 The script sweeps both users-dev and the unsuffixed users table, and for each selected account deletes its rows in auth_tokens, processing_jobs, media_artifacts, user_tags, user_folders, user_media_submissions and user_usage_monthly before the users row
- [x] #3 e2e-maestro-20260809200952@test.local is protected by an explicit exclusion list and survives the purge
- [x] #4 No account whose email matches none of the known E2E prefixes is deleted, verified by comparing the account count before and after against the expected delta
- [x] #5 After the purge, users-dev and users contain only the permanent E2E account plus genuine accounts, and no auth_tokens row references a deleted user_id
- [ ] #6 A full E2E run (01_login, 06_search, 07_paywall) passes on both platforms after the purge
- [x] #7 The script is idempotent: a second run reports nothing left to delete
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Added `scripts/purge_e2e_accounts.py` (low-level boto3 client, dry run by
default, `--apply` to delete) and `tests/unit/test_purge_e2e_accounts.py`
(14 tests on the selection/exclusion logic, no AWS call).

Selection is layered so a single mistake cannot be enough: the email must end
with `@test.local`, its local part must start with `e2e-register-`,
`e2e-test-` or `phase4-test-`, and it must not be in `PROTECTED_EMAILS`
(checked first, holds `e2e-maestro-20260809200952@test.local`). `--suffix` is
restricted to `-dev` and `""` by `ALLOWED_SUFFIXES`: staging and prod are
unreachable from this script. Children are collected by `user_id` (GSI
`user-index` or partition key) and deleted BEFORE the `users` row;
`media_artifacts` has no `user_id`, so it is reached through the
`media-item-index` GSI from each processing job of the user, exactly as the
teardown of `tests/e2e/conftest.py` does.

Every run, dry or applied, dumps the full rows it selected in low-level
DynamoDB format before deleting anything, so `aws dynamodb put-item` can
restore them by hand. This is what replaces PITR on the unsuffixed `users`
table, which has none.

### Measured on 2026-08-12, region eu-west-3

`users-dev` (PITR enabled), purged first:

| Table | Before | Rows deleted | After |
|---|---|---|---|
| `users-dev` | 33 | 31 | 2 |
| `auth_tokens-dev` | 195 | 72 | 123 |
| `processing_jobs-dev` | 28 | 6 | 22 |
| `user_usage_monthly-dev` | 87 | 8 | 79 |
| `user_media_submissions-dev` | 27 | 1 | 26 |
| `media_artifacts-dev` | 166 | 0 | 166 |
| `user_tags-dev` | 1 | 0 | 1 |
| `user_folders-dev` | 14 | 0 | 14 |

31 accounts deleted = 23 `e2e-register-*` + 7 `e2e-test-*` + 1
`phase4-test-*`, i.e. exactly the delta announced in the description; 87 child
rows. The two survivors are `marc.medlock@live.fr` and
`e2e-maestro-20260809200952@test.local` (still present, 58 auth tokens intact).

Unsuffixed legacy tables (no PITR), purged after verifying dev:

| Table | Before | Rows deleted | After |
|---|---|---|---|
| `users` | 25 | 23 | 2 |
| `auth_tokens` | 154 | 56 | 98 |
| `processing_jobs` | 22 | 3 | 19 |
| `user_usage_monthly` | 80 | 4 | 76 |
| `user_media_submissions` | 27 | 1 | 26 |
| `media_artifacts` / `user_tags` / `user_folders` | 166 / 1 / 14 | 0 | unchanged |

23 accounts, not the 22 announced: the description's count omitted
`phase4-test-1780952477@test.local`. 64 child rows.

Dumps (gitignored, they contain password hashes and refresh tokens):
`tmp/purge-e2e-dumps/purge-e2e-dev-20260812T165934Z.json` and
`tmp/purge-e2e-dumps/purge-e2e-legacy-20260812T170146Z.json`.

Verified after each purge, by full scan (never `DescribeTable.ItemCount`):
zero row in the seven linked tables still references one of the purged
`user_id`s, and both `users` tables hold exactly the permanent E2E account
plus the real account. A second run on both suffixes reports
`0 selected, 2 kept` / `nothing to delete` (AC #7).

### Deliberately not deleted

Rows whose `user_id` matches no `users` row at all: 27 `auth_tokens-dev`,
7 `processing_jobs-dev`, 6 `user_media_submissions-dev`,
76 `user_usage_monthly-dev` (and 18 / 4 / 6 / 73 on the legacy side). These are
the residue of accounts deleted long ago through `delete_user()`, which only
removed the `users` row — the very bug this task documents. Their email is
gone, so no prefix rule can attribute them to E2E tooling and the purge's
safety model does not cover them. Removing them needs its own decision (an
explicit "delete rows referencing a non-existent user" sweep); it is not done
here.

Note for task-249: the 21 unsuffixed tables are frozen duplicates slated for
deletion. Purging them was therefore redundant with dropping them, but it was
in scope and it is done.

### Not validated

AC #6: no Maestro run was executed. It needs CI or local emulators, which this
worktree does not have. The three flows (01_login, 06_search, 07_paywall) on
iOS and Android remain to be run as the only real proof that nothing in use was
carried away.
<!-- SECTION:NOTES:END -->
