---
id: task-223
title: >-
  Make Main Branch Checks green: add missing ESLint config and resolve the
  backend Ruff and Mypy gates
status: Done
assignee: []
created_date: '2026-08-05 17:54'
updated_date: '2026-08-05 18:40'
labels:
  - tooling
  - ci
  - release
dependencies: []
priority: high
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
## Contexte

Le workflow `Main Branch Checks` échoue sur chaque push `main`. Dernier run rouge le 2026-08-02 (run `30769601208`). État vérifié au 2026-08-05 :

**Backend — `ruff check .` → 757 erreurs**

| Règle | Nombre | Nature |
|---|---|---|
| `E501` line-too-long | 571 | Cosmétique — `line-length = 88` dans `pyproject.toml` |
| `I001` unsorted-imports | 83 | Auto-fixable |
| `F401` unused-import | 75 | Auto-fixable |
| `F841` unused-variable | 13 | **Potentiellement révélateur de bugs** |
| `E402` module-import-not-at-top | 8 | À examiner cas par cas |
| `F541` f-string sans placeholder | 4 | Auto-fixable |
| `E741` ambiguous-variable-name | 3 | Renommage |

162 sont auto-fixables. Les **571 `E501` dominent le bruit** : `line-length = 88` est le défaut Black hérité, jamais appliqué au code existant. Décider de la valeur cible (relever à 100/120, ou formater réellement) avant de traiter le reste — c'est le choix qui détermine l'ampleur du chantier.

Les 13 `F841` doivent être examinées individuellement : une variable assignée jamais lue signale parfois un résultat d'appel ignoré par erreur.

`pyproject.toml` utilise aussi la section dépréciée `[tool.ruff] select` au lieu de `[tool.ruff.lint] select`, ce qui produit un warning à chaque invocation.

**Mobile — `npm run lint` échoue : aucune config ESLint n'existe**

`mobile/package.json` déclare `"lint": "eslint . --ext .ts,.tsx"` et les dépendances `eslint@^8`, `@typescript-eslint/{parser,eslint-plugin}@^7`, mais **aucun fichier de configuration** (`.eslintrc*` ni `eslint.config.js`) n'est présent. La commande échoue donc systématiquement, sans jamais avoir analysé une ligne.

Le projet est sur **Expo SDK 55** : vérifier si `eslint-config-expo` est le point de départ approprié plutôt qu'une config manuelle, et si la migration vers le flat config ESLint 9 est préférable à une config legacy pour ESLint 8.

`npm run typecheck` passe déjà.

**Mypy** — n'a pas pu être revalidé localement (interpréteur du venv cassé au 2026-07-31). Doit être rejoué et rendu vert après réparation du gate Ruff.

## Objectif

Obtenir un `Main Branch Checks` réellement vert sur le SHA destiné au déploiement, sans neutraliser les gates. Ne pas atteindre le vert par exclusions massives ou `|| true` : si une règle est écartée, la décision doit être explicite et justifiée dans la configuration.

Périmètre limité au workflow `Main Branch Checks` (backend ruff/mypy + mobile typecheck/lint). Les workflows `Mobile Build & Distribute` et `Mobile E2E Tests (Maestro)` sont également rouges mais traités par leurs tâches dédiées.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 An ESLint configuration exists in mobile/ and npm run lint actually analyses the codebase instead of failing on a missing config
- [ ] #2 The chosen ESLint base config and the ESLint 8 versus 9 flat-config decision are justified in the task notes against the project's Expo SDK 55 setup
- [ ] #3 ruff check . exits clean, and any rule or path exclusion introduced to get there is explicitly justified in pyproject.toml rather than applied silently
- [ ] #4 The deprecated [tool.ruff] select section is migrated to [tool.ruff.lint] so no deprecation warning is emitted
- [ ] #5 Each of the 13 F841 unused-variable findings is reviewed individually and any that reveals a discarded call result is fixed as a real defect, not merely silenced
- [ ] #6 mypy media_summarizer runs and its gate is green in CI after the local venv interpreter is repaired
- [ ] #7 Main Branch Checks passes on a pushed commit, evidenced by the GitHub run id, with no || true or continue-on-error added to reach that state
- [ ] #8 Auto-fix passes are committed separately from behavioural fixes so the diff remains reviewable
<!-- AC:END -->
