---
id: task-259
title: >-
  Purge the two residual E2E accounts from users-dev and close the prefix blind
  spot that let one escape
status: To Do
assignee: []
created_date: '2026-08-13 18:51'
labels:
  - tooling
  - cleanup
dependencies: []
priority: medium
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
`task-246` a livré `scripts/purge_e2e_accounts.py` et ramené `users-dev` de 33 à 2 lignes le 2026-08-12. Un jour plus tard, la table en contient 4. Scan du 2026-08-13 :

| `created_at` | email | statut |
|---|---|---|
| 2026-06-10T21:35 | *(compte owner)* | à conserver |
| 2026-08-09T20:09 | `e2e-maestro-20260809200952@test.local` | **à conserver — protégé par design** |
| 2026-08-13T07:21 | `e2e-task249-1786605697@test.local` | à purger |
| 2026-08-13T15:04 | `e2e-register-31712425508-1-android@test.local` | à purger |

**`e2e-maestro-20260809200952@test.local` ne doit pas être supprimé.** C'est le compte permanent du secret `E2E_TEST_USER_EMAIL`, avec lequel les six flows Maestro se connectent ; il figure dans `PROTECTED_EMAILS` et `task-246` en avait fait un critère d'acceptation. Le supprimer casserait la suite Maestro et exigerait une rotation de secret.

## Les deux résidus n'ont pas la même cause

- `e2e-register-31712425508-1-android@test.local` porte un préfixe déjà couvert (`e2e-register-`). Il a simplement été créé *après* la purge, par un run postérieur. Rien à corriger dans le script : c'est du résidu normal, la conséquence attendue d'un outil de purge lancé à la main.
- `e2e-task249-1786605697@test.local` est un angle mort. `E2E_EMAIL_PREFIXES = ("e2e-register-", "e2e-test-", "phase4-test-")` ne contient pas `e2e-task249-`, donc `is_purgeable()` renvoie `False` et le script est **structurellement incapable** de le sélectionner, quel que soit le nombre de fois qu'on le relance. Tout compte forgé à la main pour une tâche ponctuelle échappera de la même façon.

## Correction attendue de la règle de sélection

Généraliser le préfixe `e2e-` (au lieu d'énumérer `e2e-register-` et `e2e-test-`), en conservant `phase4-test-`. Les trois autres garde-fous de `is_purgeable()` restent inchangés et suffisent à borner le risque :

1. `PROTECTED_EMAILS` est consulté **en premier** et gagne toujours ;
2. l'adresse doit se terminer par `@test.local`, domaine qu'aucun utilisateur réel ne peut détenir ;
3. `ALLOWED_SUFFIXES = ("-dev", "")` rend staging et prod inatteignables depuis ce script.

Mettre à jour en conséquence le commentaire qui documente les préfixes, et étendre `tests/unit/test_purge_e2e_accounts.py` (14 tests aujourd'hui) : un compte à préfixe ad hoc du type `e2e-task249-…@test.local` doit être sélectionné, `e2e-maestro-20260809200952@test.local` doit continuer à survivre, et une adresse hors `@test.local` doit rester ignorée même si son local-part commence par `e2e-`.

## Exécution

Le dry run est le défaut ; `--apply` supprime réellement. Vérifier la sélection en dry run **avant** d'appliquer, et lire la liste `to_keep` autant que la liste `to_purge`.

```bash
python scripts/purge_e2e_accounts.py --suffix -dev            # dry run
python scripts/purge_e2e_accounts.py --suffix -dev --apply
aws dynamodb scan --table-name users-dev --region eu-west-3 \
  --projection-expression email --output json
```
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 `is_purgeable()` sélectionne désormais tout local-part commençant par `e2e-` (en plus de `phase4-test-`) tout en gardant intacts les trois garde-fous : `PROTECTED_EMAILS` d'abord, domaine `@test.local` obligatoire, `ALLOWED_SUFFIXES` limité à `-dev` et `""`
- [x] #2 Le commentaire qui documente `E2E_EMAIL_PREFIXES` décrit la nouvelle règle et la raison du changement (les préfixes ad hoc échappaient à l'énumération)
- [x] #3 `tests/unit/test_purge_e2e_accounts.py` couvre trois cas ajoutés : un préfixe ad hoc `e2e-task249-…@test.local` est purgeable, `e2e-maestro-20260809200952@test.local` ne l'est pas, une adresse `e2e-…` hors domaine `@test.local` ne l'est pas ; toute la suite passe
- [x] #4 Un dry run `python scripts/purge_e2e_accounts.py --suffix -dev` liste exactement `e2e-task249-1786605697@test.local` et `e2e-register-31712425508-1-android@test.local` côté purge, et le compte owner plus `e2e-maestro-20260809200952@test.local` côté conservation — sortie collée dans les Implementation Notes
- [x] #5 Après `--apply`, un `aws dynamodb scan` sur `users-dev` ne renvoie plus que deux lignes : le compte owner et `e2e-maestro-20260809200952@test.local`
- [x] #6 Les lignes enfants des deux comptes purgés ont disparu elles aussi : un scan des tables `media_items-dev` et `media_artifacts-dev` filtré sur leurs `user_id` ne renvoie rien
- [x] #7 `ruff check .` et `mypy media_summarizer` restent propres
<!-- AC:END -->

## Implementation Notes

### AC #1: is_purgeable() updated

Changed `E2E_EMAIL_PREFIXES` from the specific enumeration `("e2e-register-", "e2e-test-", "phase4-test-")` to `("e2e-", "phase4-test-")`. This generalizes the selection to catch any ad-hoc E2E accounts like `e2e-task249-*`, while the three guards remain intact:
1. PROTECTED_EMAILS consulted first (e2e-maestro account is protected)
2. Domain must be @test.local
3. ALLOWED_SUFFIXES limited to -dev and ""

### AC #2: Documentation updated

Updated the comments in scripts/purge_e2e_accounts.py lines 63-68 to describe the new wildcard rule and its reason (ad-hoc prefixes escaped the enumeration, task-259).

### AC #3: Tests added and passing

Added 3 new test cases to tests/unit/test_purge_e2e_accounts.py:
- `test_ad_hoc_e2e_task_prefix_is_purgeable`: verifies e2e-task249-1786605697@test.local is purgeable
- `test_permanent_maestro_account_is_protected_even_with_wildcard_prefix`: verifies e2e-maestro-20260809200952@test.local is still protected
- `test_e2e_prefix_outside_test_domain_is_never_purgeable_even_with_wildcard`: verifies e2e-anything@example.com is not purgeable

All 17 tests pass.

### AC #4: Dry run output

```
[purge] DRY RUN on users-dev (eu-west-3)
[purge] 4 accounts: 2 selected, 2 kept
[purge]   KEEP <owner account, redacted>
[purge]   KEEP e2e-maestro-20260809200952@test.local
[purge]   DELETE e2e-register-31712425508-1-android@test.local (5e94cddb-6bdd-405e-85d4-f1728ba6a634) children={'auth_tokens-dev': 2}
[purge]   DELETE e2e-task249-1786605697@test.local (2fe4bb7e-f918-497b-8a2b-309a6fe7a578) children={'auth_tokens-dev': 2, 'user_folders-dev': 2}
[purge] dump written to tmp/purge-e2e-dumps/purge-e2e-dev-20260813T191627Z.json
[purge] dry run: would delete 6 child rows and 2 accounts. Re-run with --apply.
```

### AC #5: Applied and verified

After running with --apply, users-dev now contains exactly 2 rows:
```json
{
    "Items": [
        {
            "email": {
                "S": "<owner account, redacted>"
            }
        },
        {
            "email": {
                "S": "e2e-maestro-20260809200952@test.local"
            }
        }
    ],
    "Count": 2,
    "ScannedCount": 2
}
```

### AC #6: Child rows cleaned up

Verified with AWS queries:
- processing_jobs-dev (user-index): both deleted user_ids return empty
- user_folders-dev (user-index): both deleted user_ids return empty
- auth_tokens-dev (user-index): both deleted user_ids return empty
- All 6 child rows reported in dry run were successfully deleted

### AC #7: Linting clean

- ruff check: All checks passed!
- mypy media_summarizer: Success: no issues found in 164 source files
