---
id: task-246
title: Purge the orphaned E2E accounts and their rows from dev DynamoDB
status: To Do
assignee: []
created_date: '2026-08-12 16:39'
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
- [ ] #1 scripts/purge_e2e_accounts.py exists, defaults to a dry run, and requires an explicit flag to delete
- [ ] #2 The script sweeps both users-dev and the unsuffixed users table, and for each selected account deletes its rows in auth_tokens, processing_jobs, media_artifacts, user_tags, user_folders, user_media_submissions and user_usage_monthly before the users row
- [ ] #3 e2e-maestro-20260809200952@test.local is protected by an explicit exclusion list and survives the purge
- [ ] #4 No account whose email matches none of the known E2E prefixes is deleted, verified by comparing the account count before and after against the expected delta
- [ ] #5 After the purge, users-dev and users contain only the permanent E2E account plus genuine accounts, and no auth_tokens row references a deleted user_id
- [ ] #6 A full E2E run (01_login, 06_search, 07_paywall) passes on both platforms after the purge
- [ ] #7 The script is idempotent: a second run reports nothing left to delete
<!-- AC:END -->
