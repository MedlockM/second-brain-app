---
id: task-171
title: >-
  Run full Maestro suite locally on iOS+Android dev builds, iterate red→green
  until all flows pass
status: To Do
assignee: []
created_date: '2026-06-10 05:59'
labels:
  - phase-5
  - mobile
  - release
  - e2e
  - validation
dependencies:
  - task-161
  - task-162
  - task-168
  - task-169
  - task-170
priority: high
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
## Context

Cœur de la **boucle TDD Phase 5**. Une fois la suite Maestro étendue (task-168 register/login, task-169 search, task-170 paywall) et les dev builds installés sur device(s) (task-161 iOS, task-162 Android), on lance toute la suite localement et on itère red→green sur chaque flow KO.

Cette tâche est **dispatchable** : l'agent `task-mobile` (mode UI/UX et/ou Release engineering) tourne la suite Maestro contre device(s) branché(s) USB ou émulateur, identifie chaque red, fixe le code/config app, retourne le test, jusqu'à ce que tous les flows soient verts.

Le hot reload Expo permet d'éditer le code et le voir actif sans rebuild — boucle ~30s par itération au lieu de plusieurs minutes.

## Prérequis

- task-161 ✅ + task-162 ✅ (dev builds installés)
- task-168 ✅ + task-169 ✅ + task-170 ✅ (suite Maestro complète)
- Un device iOS branché USB OU un simulateur iOS bootté + un device/émulateur Android
- `maestro` CLI installé localement (cf. `.github/workflows/mobile-e2e-maestro.yml` pour la version : 1.38.0)

## Scope

1. Lance `maestro test mobile/.maestro/` (ou par flow individuel) sur iOS et Android successivement.
2. Pour chaque flow KO :
   - Lis le rapport Maestro (screenshots + logs)
   - Identifie la root cause : selector cassé (ajuster le flow YAML) OU bug app (fixer dans `mobile/`) OU bug backend (créer un sous-ticket label `bug, backend` et le linker comme dépendance)
   - Pour les fixes mobile : édite le code, laisse le hot reload appliquer, relance le flow
   - Pour les fixes backend : créé un sous-ticket et **skip temporairement** le flow concerné (`maestro test --exclude-tags=...`) en notant la dette
3. Continue jusqu'à ce que `maestro test mobile/.maestro/` retourne 0 sur les 7 flows critiques sur **les deux plateformes**.
4. Commit et push tous les fixes (regroupés par catégorie : selectors, app bugs, backend bugs).
5. Note dans le ticket :
   - Liste des flows initialement KO et leur cause
   - Liste des sous-tickets bugs créés
   - Output final `maestro test` (timing, count)

## Boundaries

- **Pas de touche aux flows hors mobile/.maestro/** (par ex. ne modifie pas les workflows GitHub — ça c'est task-172).
- **Pas de touche au backend** sauf si un fix mineur évite de créer un sous-ticket (ex: typo dans une error message). Pour tout fix backend non-trivial : sous-ticket dédié.
- Fixes mobile autorisés sous le périmètre Mode UI/UX du `task-mobile.md` (theme, accessibilité, services existants).

## References

- `mobile/.maestro/` (suite cible)
- `.github/workflows/mobile-e2e-maestro.yml` (référence runner CI, version Maestro 1.38.0)
- task-168, task-169, task-170 (flows à intégrer)
- `docs/V1_LAUNCH_PLAN.md` Phase 5 (suivi du statut)
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 maestro test mobile/.maestro/ retourne exit 0 sur device iOS
- [ ] #2 maestro test mobile/.maestro/ retourne exit 0 sur device/émulateur Android
- [ ] #3 Tous les fixes mobile sont commités avec messages descriptifs
- [ ] #4 Tous les bugs backend découverts ont un sous-ticket labelé bug, backend et résolu OU documenté comme dette
- [ ] #5 Le ticket liste les flows initialement KO et leur cause
<!-- AC:END -->
