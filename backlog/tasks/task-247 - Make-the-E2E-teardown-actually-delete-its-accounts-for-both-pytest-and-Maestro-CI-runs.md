---
id: task-247
title: >-
  Make the E2E teardown actually delete its accounts, for both pytest and
  Maestro CI runs
status: To Do
assignee: []
created_date: '2026-08-12 16:39'
labels:
  - e2e
  - tooling
  - infra
dependencies:
  - task-246
priority: medium
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
## Contexte

task-246 purge l'accumulé. Cette tâche ferme le robinet : sans elle, les comptes orphelins reviennent au run suivant.

**Deux canaux fuient, indépendamment l'un de l'autre.**

### 1. Le teardown pytest est silencieusement sauté

`tests/e2e/conftest.py:173-177` avale l'échec d'import de `database_async` et sort par `return` :

```python
try:
    from media_summarizer.utils import database_async
except Exception as exc:
    print(f"[e2e] teardown: cannot import database_async ({exc!r}); skipping")
    return
```

Ce garde est ancien et n'est pas une régression, mais **son effet a changé** : depuis task-237, `database_async.py:44-49` appelle `required_env("USERS_TABLE")` au chargement du module, et `required_env` lève délibérément un `RuntimeError` sans fallback (`media_summarizer/utils/env.py:27-45`). En local, sans les variables `*_TABLE` exportées, l'import échoue donc **toujours** — le teardown est systématiquement sauté et ne signale rien de plus qu'une ligne dans la sortie pytest. Résultat mesuré : 7 comptes `e2e-test-*` orphelins dans `users-dev`, 3 dans `users`.

Le nettoyage lui-même (`_teardown_user_inner`) est correct et complet ; il n'est simplement jamais atteint.

### 2. Les runs Maestro CI ne nettoient rien du tout

`mobile/.maestro/01_login.yaml:31` enregistre `e2e-register-${MAESTRO_RUN_ID}@test.local` à chaque exécution, et `.github/workflows/mobile-e2e-maestro.yml` n'a **aucune** étape de suppression. C'est le canal majoritaire : 23 des 31 comptes orphelins de `users-dev`. Un teardown côté pytest ne le couvrira jamais — il faut une étape distincte dans le workflow.

## Scope

1. **Rendre l'échec du teardown pytest visible et non silencieux.** L'import doit réussir en local, ou l'échec doit être bruyant. Deux options à arbitrer par l'implémenteur : exporter les noms de tables nécessaires depuis `conftest.py` avant l'import (l'environnement de test est connu et déjà forcé pour `AWS_REGION`, cf. `conftest.py:25-26`), ou faire échouer la session pytest si le teardown ne peut pas s'exécuter. Ce qui n'est pas acceptable, c'est le `return` muet actuel.
2. **Ajouter une étape de nettoyage au workflow Maestro**, qui supprime le compte `e2e-register-<run_id>-<attempt>-<platform>` créé par le run. Elle doit tourner en `if: always()` — un run rouge laisse un compte tout autant qu'un run vert — et ne jamais faire échouer le job si la suppression échoue.
3. **Supprimer les données associées, pas seulement la ligne `users`.** `database_async.delete_user()` ne supprime que celle-là (`database_async.py:239-248`), ce qui laisse tokens, jobs et compteurs d'usage derrière. Réutiliser le balayage de `scripts/purge_e2e_accounts.py` livré par task-246 au lieu d'en écrire un second.
4. **Couvrir la table historique non suffixée.** Tant que task-237 n'a pas retiré les tables sans suffixe, un compte créé via l'API dev apparaît dans `users-dev` **et** dans `users` — les deux doivent être nettoyées.

## Hors scope

- La purge de l'existant (task-246).
- La suppression des tables non suffixées (task-237).

## Références

- `tests/e2e/conftest.py:52-72` (création), `:163-279` (teardown)
- `media_summarizer/utils/env.py:27-45`, `media_summarizer/utils/database_async.py:44-49`
- `mobile/.maestro/01_login.yaml:31`, `.github/workflows/mobile-e2e-maestro.yml`
- task-237 (Implementation Notes, « Deux défauts constatés, hors périmètre du merge », point 1)
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 A local pytest E2E run deletes its e2e-test-* account: the account count in users-dev is unchanged before and after the run
- [x] #2 The teardown no longer returns silently when database_async cannot be imported — either the import succeeds, or the failure is loud enough to be noticed in the run output
- [x] #3 The Maestro workflow deletes the e2e-register-* account it created, in a step that runs on red runs too and never fails the job
- [x] #4 Both teardowns remove the account's rows in the linked tables (auth_tokens, processing_jobs, user_usage_monthly, ...), not just the users row
- [x] #5 Both teardowns cover the unsuffixed users table as well as users-dev, for as long as the historical tables coexist
- [ ] #6 Two consecutive full CI runs leave the account count in users-dev and users unchanged
- [x] #7 The permanent E2E account designated by E2E_TEST_USER_EMAIL is never deleted by either teardown
<!-- AC:END -->

## Implementation Notes

**Delivered:**

1. **Created `scripts/delete_e2e_account.py`** — a reusable per-account deletion script that:
   - Takes an email as argument and deletes the account + all child rows from both `-dev` and unsuffixed tables
   - **Imports** shared selection rules and table topology from `purge_e2e_accounts.py` to avoid drift (scope item 3: "réutiliser le balayage au lieu d'en écrire un second")
   - When a child table is added to the purge script, this script automatically picks it up
   - Never fails: exits 0 even if the account doesn't exist or is protected
   - Designed to be called from both test teardowns and CI cleanup steps

2. **Fixed pytest teardown** (`tests/e2e/conftest.py`):
   - Exported required table env vars (`USERS_TABLE`, `PROCESSING_JOBS_TABLE`, etc.) at module load (before any `media_summarizer` import) to prevent the `required_env()` RuntimeError that was silently skipping the teardown
   - Replaced the old manual teardown logic with a call to `delete_e2e_account.py`
   - The new teardown is comprehensive, consistent with the purge script, and covers both table suffixes

3. **Added Maestro CI cleanup steps** (`.github/workflows/mobile-e2e-maestro.yml`):
   - Added "Delete E2E test account" step to both `android-e2e` and `ios-e2e` jobs
   - Steps run with `if: always()` so they execute even on red runs
   - Steps use `continue-on-error: true` so they never fail the job
   - Each step installs `boto3`, constructs the email from `MAESTRO_RUN_ID`, and calls the deletion script
   - Android deletes `e2e-register-<run_id>-<attempt>-android@test.local`
   - iOS deletes `e2e-register-<run_id>-<attempt>-ios@test.local`

**What was verified:**

- AC #2: conftest.py now exports `*_TABLE` env vars at module load, so `database_async` import succeeds
- AC #3: workflow steps have `if: always()` and `continue-on-error: true`, verified by inspection
- AC #4: `delete_e2e_account.py` calls `collect_children()` from `purge_e2e_accounts.py`, which sweeps all child tables including `user_media_submissions` and `user_usage_monthly`
- AC #5: `ALLOWED_SUFFIXES = ("-dev", "")` imported from purge script; both suffixes are swept
- AC #7: `PROTECTED_EMAILS` imported from purge script includes `e2e-maestro-20260809200952@test.local`; verified the script rejects it

**What needs owner verification:**

- AC #1: Run a local pytest E2E session (`pytest tests/e2e/`) and confirm the throwaway account is deleted. Before/after DynamoDB scan counts should match.
- AC #6: Trigger two consecutive Maestro CI runs (workflow_dispatch) and confirm both cleanup steps execute and the final account count in `users-dev` and `users` is unchanged from baseline.

**Notes:**

- The deletion script is idempotent: calling it multiple times on the same email is safe
- No duplication: shared logic lives in one place (`purge_e2e_accounts.py`), imported by the per-account script
