---
id: task-113
title: Set up GitHub Actions CI workflows (lint + typecheck) for backend and mobile
status: Done
assignee: []
created_date: '2026-06-01 13:58'
labels:
  - tooling
  - ci
  - v1
dependencies: []
priority: high
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
## Contexte

Phase 1.3 du `docs/V1_LAUNCH_PLAN.md`. Le repo `MedlockM/second-brain-app` n'a pas encore de CI. Il faut un workflow GitHub Actions minimal qui passe sur **chaque PR** et **chaque push sur `main`**, pour empêcher les régressions de lint/typing avant que le code arrive en prod.

## Scope d'implémentation

1. **Workflow `pr.yml`** (`.github/workflows/pr.yml`) déclenché sur `pull_request` :
   - Job **backend** :
     - `setup-python@v5` avec Python 3.10 (cf. `pyproject.toml:requires-python = ">=3.10"`).
     - Cache `pip` keyed sur `pyproject.toml`.
     - Install : `pip install -e ".[dev]"`.
     - `ruff check .`
     - `mypy media_summarizer` (si `mypy.ini` ou `pyproject.toml` configure mypy ; sinon `--ignore-missing-imports` au minimum).
   - Job **mobile** :
     - `setup-node@v4` avec Node version pinnée (lire `mobile/package.json` engines ou `.nvmrc` si présent).
     - Cache `npm` keyed sur `mobile/package-lock.json`.
     - `cd mobile && npm ci`.
     - `npm run typecheck` (vérifier que le script existe dans `mobile/package.json` ; sinon utiliser `npx tsc --noEmit`).
     - `npm run lint` (idem fallback `npx eslint .`).
   - Les 2 jobs s'exécutent **en parallèle** (pas de `needs:`).
   - Concurrency group par PR pour annuler les runs précédents (`concurrency: { group: pr-${{ github.head_ref }}, cancel-in-progress: true }`).

2. **Workflow `main.yml`** (`.github/workflows/main.yml`) déclenché sur `push` vers `main` :
   - Mêmes jobs que `pr.yml` (lint + typecheck) pour vérifier qu'aucun merge ne casse main.
   - Pas encore de déploiement Lambda dans ce ticket (sera fait dans un ticket Phase 7 séparé `deploy-lambda.yml`).

3. **Branch protection rule** : à activer manuellement par l'owner sur `main` après que les workflows passent verts une première fois (require PR + require status checks `backend` + `mobile`). **Pas dans le scope du ticket** (action GitHub UI manuelle), juste le mentionner dans les Implementation Notes pour rappel.

## Découvertes attendues

L'agent doit auditer le repo avant d'écrire les workflows et adapter en conséquence :

- Vérifier la version Python utilisée localement (`.venv` indique 3.10).
- Vérifier la version Node mobile (lire `mobile/package.json` `engines.node` si défini, ou `.nvmrc`).
- Vérifier que les scripts `typecheck` et `lint` existent dans `mobile/package.json` ; sinon les ajouter avant le workflow.
- Vérifier que `pyproject.toml [tool.ruff]` est utilisable tel quel (présent au moins jusqu'à `select = ["E", "F", "I"]`).
- Vérifier si mypy est configuré dans le repo ; si non, ajouter une config minimale `[tool.mypy]` dans `pyproject.toml` qui ne casse pas le code existant (`ignore_missing_imports = true`, `check_untyped_defs = false`).

Si une étape révèle qu'un fix mineur est nécessaire (ex. ajouter `typecheck` dans `mobile/package.json`), l'inclure dans le PR sans ouvrir un ticket séparé.

## Hors-scope

- **Pas de tests unitaires** dans ce ticket. Une fois les tests retrouvent un état propre (cf. session 2026-05-31 où `pytest-asyncio` manquait — déjà ajouté à `pyproject.toml` dev deps), on pourra ajouter un job `pytest` dans un follow-up.
- **Pas de déploiement Lambda** (Phase 7).
- Pas d'intégration EAS Submit pour mobile builds (Phase 7).
- Pas de matrix multi-version Python/Node : Python 3.10 + Node version unique pinnée suffisent en V1.

## Vérification

- Ouvrir une PR triviale (ex. modif d'une ligne de doc) → workflow `pr.yml` se déclenche → les 2 jobs `backend` et `mobile` passent verts en < 5 min.
- Pousser un commit factice sur main (ou re-trigger le workflow main une fois mergé) → workflow `main.yml` passe vert.
- Tester un cas de rouge : créer une PR avec un import inutilisé ou un type error → le workflow rouge sur le job concerné.

## Contexte fichiers utiles

- `pyproject.toml` — section `[tool.ruff]` déjà configurée ; section `[project.optional-dependencies] dev` contient `ruff`, `mypy`, `pytest`.
- `mobile/package.json` — vérifier scripts `typecheck` et `lint`.
- `mobile/tsconfig.json` — config TypeScript.
- Pas de `.github/workflows/` existant à fusionner avec.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 Un workflow .github/workflows/pr.yml déclenché sur pull_request lance en parallèle les jobs backend (ruff + mypy) et mobile (typecheck + lint)
- [ ] #2 Un workflow .github/workflows/main.yml déclenché sur push main lance les mêmes jobs lint + typecheck
- [ ] #3 Le job backend utilise Python 3.10, cache pip keyé sur pyproject.toml, et installe les dev extras
- [ ] #4 Le job mobile utilise une version Node pinnée (lue de mobile/package.json engines ou .nvmrc), cache npm keyé sur mobile/package-lock.json, et fait npm ci
- [ ] #5 Les scripts mobile typecheck et lint existent dans mobile/package.json (ajoutés si manquants)
- [ ] #6 La config mypy est utilisable (mypy.ini, pyproject.toml [tool.mypy], ou flags ignore-missing-imports en CLI) sans casser le code existant
- [ ] #7 Concurrency group par PR (cancel-in-progress) pour ne pas accumuler les runs
- [ ] #8 Une PR triviale déclenche bien le workflow pr.yml et passe verte en moins de 5 min sur les 2 jobs
- [ ] #9 Une régression triviale (import inutilisé backend ou type error mobile) est bien détectée par le workflow
- [ ] #10 Implementation Notes documente l'action GitHub UI manuelle restante : activer branch protection sur main avec required checks backend + mobile — **couverte par `task-257` le 2026-08-13** : la branch protection est posée sur `main` (via `gh api`, pas l'UI). Régime volontairement plus léger que ce qu'annonçait cette case : force-push et suppression interdits, **aucun** required status check et **aucune** required review, parce que le flow réel est un merge local puis un push direct sur `main` (des required checks rejetteraient tout push direct, et `Main Branch Checks` ne tourne jamais sur une PR). Raisonnement complet et commande de rollback dans `task-257`
<!-- AC:END -->
