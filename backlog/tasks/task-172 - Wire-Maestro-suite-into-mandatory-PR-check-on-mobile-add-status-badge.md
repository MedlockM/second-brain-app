---
id: task-172
title: Wire Maestro suite into mandatory PR check on mobile/** + add status badge
status: To Do
assignee: []
created_date: '2026-06-10 06:00'
labels:
  - phase-5
  - mobile
  - release
  - tooling
  - ci
dependencies:
  - task-171
priority: high
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
## Context

Une fois la suite Maestro complète et verte localement (task-171), il faut la **rendre bloquante** sur toute PR qui touche `mobile/`. Aujourd'hui le workflow `.github/workflows/mobile-e2e-maestro.yml` existe mais n'est pas dans la liste des "required status checks" de la branche protection.

Sans cette dernière étape, un PR peut merger malgré une régression Maestro — la TDD perd son intérêt.

## Scope

1. **Vérifier le workflow actuel** : `.github/workflows/mobile-e2e-maestro.yml` doit déclencher sur `pull_request` paths `mobile/**`. Si pas le cas, ajouter le trigger.
2. **Vérifier la matrix** : actuellement Android par défaut + iOS optionnel via `workflow_dispatch`. Pour le PR check, lancer **Android par défaut** (runner ubuntu-latest, plus rapide) ; iOS reste manuel/scheduled (runner macOS = $).
3. **Documenter dans `docs/V1_LAUNCH_PLAN.md` Phase 7** (CI/CD) que la suite Maestro Android est dans les required checks.
4. **Ajouter un README dans `mobile/.maestro/`** (s'il n'existe pas déjà) qui explique :
   - Comment lancer la suite localement (`maestro test mobile/.maestro/`)
   - Quels flows existent et ce qu'ils couvrent
   - Comment ajouter un nouveau flow (template)

5. **Ne PAS modifier la branch protection rules** depuis cette tâche — c'est une action sur `github.com/MedlockM/second-brain-app/settings/branches` qui requiert l'owner. Documente-la dans le ticket comme **action manuelle owner finale** :
   - Add `Mobile E2E Tests (Maestro) / android` to Required status checks on `main`

## Convention

- Ne touche pas aux workflows backend (`pr.yml`, `main.yml`, `deploy-lambda.yml`) — juste `mobile-e2e-maestro.yml`.
- Si l'iOS runner est trop coûteux pour chaque PR, scheduled nightly ou on-demand reste OK pour V1 — Android couvre 95% des régressions logiques.

## References

- `.github/workflows/mobile-e2e-maestro.yml`
- `docs/V1_LAUNCH_PLAN.md` Phase 7 (CI/CD)
- task-113 (CI workflows backend + mobile, déjà Done)
- task-171 (suite Maestro verte localement)
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 mobile-e2e-maestro.yml déclenche bien sur pull_request paths mobile/**
- [ ] #2 Android est lancé par défaut sur PR ; iOS resté sur workflow_dispatch ou nightly
- [ ] #3 README mobile/.maestro/ documente lancement local + liste des flows + template d'ajout
- [ ] #4 docs/V1_LAUNCH_PLAN.md Phase 7 mentionne Maestro Android comme required check
- [ ] #5 Action manuelle owner (branch protection) documentée en checklist du ticket
<!-- AC:END -->
