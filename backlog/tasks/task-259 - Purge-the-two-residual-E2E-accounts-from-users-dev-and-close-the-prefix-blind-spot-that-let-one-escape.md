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
- [ ] #1 `is_purgeable()` sélectionne désormais tout local-part commençant par `e2e-` (en plus de `phase4-test-`) tout en gardant intacts les trois garde-fous : `PROTECTED_EMAILS` d'abord, domaine `@test.local` obligatoire, `ALLOWED_SUFFIXES` limité à `-dev` et `""`
- [ ] #2 Le commentaire qui documente `E2E_EMAIL_PREFIXES` décrit la nouvelle règle et la raison du changement (les préfixes ad hoc échappaient à l'énumération)
- [ ] #3 `tests/unit/test_purge_e2e_accounts.py` couvre trois cas ajoutés : un préfixe ad hoc `e2e-task249-…@test.local` est purgeable, `e2e-maestro-20260809200952@test.local` ne l'est pas, une adresse `e2e-…` hors domaine `@test.local` ne l'est pas ; toute la suite passe
- [ ] #4 Un dry run `python scripts/purge_e2e_accounts.py --suffix -dev` liste exactement `e2e-task249-1786605697@test.local` et `e2e-register-31712425508-1-android@test.local` côté purge, et le compte owner plus `e2e-maestro-20260809200952@test.local` côté conservation — sortie collée dans les Implementation Notes
- [ ] #5 Après `--apply`, un `aws dynamodb scan` sur `users-dev` ne renvoie plus que deux lignes : le compte owner et `e2e-maestro-20260809200952@test.local`
- [ ] #6 Les lignes enfants des deux comptes purgés ont disparu elles aussi : un scan des tables `media_items-dev` et `media_artifacts-dev` filtré sur leurs `user_id` ne renvoie rien
- [ ] #7 `ruff check .` et `mypy media_summarizer` restent propres
<!-- AC:END -->
