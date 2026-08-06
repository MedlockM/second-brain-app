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

## Contexte budget CI iOS

L'owner n'a pas de Mac local (cf. task-171) : toute exécution Maestro iOS passe obligatoirement par un runner macOS GitHub Actions. Ces runners comptent x10 sur les minutes Actions et l'owner reste sur le **plan gratuit (2000 min/mois → ~200 min réelles de macOS/mois avant facturation)**. La stratégie CI doit donc traiter iOS comme une ressource rationnée, pas comme un check systématique :

- **Android** : runner `ubuntu-latest`, gratuit/quasi-illimité → check obligatoire sur **chaque PR** touchant `mobile/**`.
- **iOS** : runner macOS, quota gratuit limité → **jamais en required check sur PR**. Déclenchement en `workflow_dispatch` (manuel, pour les itérations task-171) et/ou en **scheduled nightly** (cadence à choisir pour rester sous ~200 min/mois — ex. 1 run/nuit plutôt que par commit). Android couvre déjà 95% des régressions logiques ; iOS sert de filet de sécurité périodique, pas de gate par PR.

## Scope

1. **Vérifier le workflow actuel** : `.github/workflows/mobile-e2e-maestro.yml` doit déclencher sur `pull_request` paths `mobile/**`. Si pas le cas, ajouter le trigger.
2. **Vérifier la matrix** : Android par défaut sur `pull_request` (runner `ubuntu-latest`) ; iOS **uniquement** sur `workflow_dispatch` et un `schedule` nightly — jamais sur `pull_request`, pour ne pas cramer le quota gratuit à chaque push.
3. **Documenter dans `docs/V1_LAUNCH_PLAN.md` Phase 7** (CI/CD) que la suite Maestro Android est dans les required checks, et que l'iOS tourne en nightly/manuel avec le budget macOS gratuit (200 min/mois) comme contrainte explicite.
4. **Ajouter un README dans `mobile/.maestro/`** (s'il n'existe pas déjà) qui explique :
   - Comment lancer la suite Android en local (`maestro test mobile/.maestro/`)
   - Comment déclencher un run iOS via `workflow_dispatch` (pas d'exécution locale possible, pas de Mac)
   - Quels flows existent et ce qu'ils couvrent
   - Comment ajouter un nouveau flow (template)
   - Le budget macOS gratuit (200 min/mois) et comment surveiller la consommation (onglet Settings → Billing → Actions du repo GitHub)

5. **Ne PAS modifier la branch protection rules** depuis cette tâche — c'est une action sur `github.com/MedlockM/second-brain-app/settings/branches` qui requiert l'owner. Documente-la dans le ticket comme **action manuelle owner finale** :
   - Add `Mobile E2E Tests (Maestro) / android` to Required status checks on `main`
   - Ne PAS ajouter le job iOS aux required checks (cohérent avec la contrainte budget ci-dessus)

## Convention

- Ne touche pas aux workflows backend (`pr.yml`, `main.yml`, `deploy-lambda.yml`) — juste `mobile-e2e-maestro.yml`.
- Le runner macOS iOS ne doit jamais être déclenché automatiquement sur chaque PR — uniquement nightly (cadence à définir sous le budget de 200 min/mois) ou manuel via `workflow_dispatch`.

## References

- `.github/workflows/mobile-e2e-maestro.yml`
- `docs/V1_LAUNCH_PLAN.md` Phase 7 (CI/CD)
- task-113 (CI workflows backend + mobile, déjà Done)
- task-171 (suite Maestro verte localement)
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 mobile-e2e-maestro.yml déclenche bien sur pull_request paths mobile/**
- [ ] #2 Android est lancé par défaut sur PR ; iOS n'est JAMAIS déclenché sur pull_request, uniquement workflow_dispatch et/ou schedule nightly
- [ ] #3 README mobile/.maestro/ documente lancement local Android + déclenchement CI iOS (pas d'exécution locale possible) + liste des flows + template d'ajout + suivi du budget macOS gratuit
- [ ] #4 docs/V1_LAUNCH_PLAN.md Phase 7 mentionne Maestro Android comme required check et le régime nightly/manuel d'iOS sous contrainte budget (200 min/mois)
- [ ] #5 Action manuelle owner (branch protection) documentée en checklist du ticket, incluant la note de ne PAS rendre le job iOS obligatoire
<!-- AC:END -->
