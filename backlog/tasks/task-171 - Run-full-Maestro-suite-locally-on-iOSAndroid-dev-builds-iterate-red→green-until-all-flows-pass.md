---
id: task-171
title: >-
  Run full Maestro suite (Android locally, iOS via CI macOS runner) on dev
  builds, iterate red→green until all flows pass
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

Cœur de la **boucle TDD Phase 5**. Une fois la suite Maestro étendue (task-168 register/login, task-169 search, task-170 paywall) et les dev builds installés sur device(s) (task-161 iOS, task-162 Android), on lance toute la suite et on itère red→green sur chaque flow KO.

**Contrainte owner : pas de Mac disponible.** Le CLI `maestro` a besoin d'un host macOS pour driver un device/simulateur iOS (dépendance Xcode/XCTest), même en ciblant un device physique branché en USB. La boucle d'itération est donc **asymétrique entre plateformes** :

- **Android** : itération 100% locale, sur la machine de l'owner (Linux) — `maestro` CLI + `adb` + device/émulateur Android ne nécessitent pas macOS. Boucle rapide (~30s/itération avec hot reload Expo), identique à ce qui était prévu initialement.
- **iOS** : pas d'exécution locale possible. L'itération passe par le workflow GitHub Actions `.github/workflows/mobile-e2e-maestro.yml` déclenché manuellement (`workflow_dispatch`) sur un runner macOS hébergé. Ce runner est payant au-delà du **quota gratuit de 200 min/mois** (macOS compte x10 sur les minutes Actions) — donc itérer flow-par-flow comme en local n'est pas viable : il faut **grouper les fixes par lot** (batch plusieurs hypothèses de correction avant de relancer un run complet) pour économiser le quota, et consulter les screenshots/logs du run comme artifacts CI plutôt qu'en direct sur device.

Cette tâche est **dispatchable** : l'agent `task-mobile` (mode UI/UX et/ou Release engineering) tourne la suite Android localement, identifie chaque red, fixe le code/config app, jusqu'à ce que tous les flows Android soient verts. Pour iOS, l'agent prépare les fixes candidats puis délègue le déclenchement du run CI à l'owner (accès GitHub Actions requis) — cf. Boundaries.

## Prérequis

- task-161 ✅ + task-162 ✅ (dev builds installés)
- task-168 ✅ + task-169 ✅ + task-170 ✅ (suite Maestro complète)
- Android : `maestro` CLI installé localement + `adb` + device/émulateur Android
- iOS : accès au repo GitHub (pour déclencher `workflow_dispatch` sur `mobile-e2e-maestro.yml`) — pas de device/simulateur local requis
- (cf. `.github/workflows/mobile-e2e-maestro.yml` pour la version Maestro utilisée en CI : 1.38.0, à aligner avec la version locale Android)

## Scope

1. **Android (local)** : lance `maestro test mobile/.maestro/` (ou par flow individuel) sur device/émulateur Android.
2. Pour chaque flow KO (Android local ou iOS via run CI) :
   - Lis le rapport Maestro (screenshots + logs, en local ou en artifact CI pour iOS)
   - Identifie la root cause : selector cassé (ajuster le flow YAML) OU bug app (fixer dans `mobile/`) OU bug backend (créer un sous-ticket label `bug, backend` et le linker comme dépendance)
   - Pour les fixes Android : édite le code, laisse le hot reload appliquer, relance le flow localement
   - Pour les fixes iOS : regroupe plusieurs corrections candidates avant de redéclencher un run CI complet (économie du quota macOS gratuit)
   - Pour les fixes backend : créé un sous-ticket et **skip temporairement** le flow concerné (`maestro test --exclude-tags=...`) en notant la dette
3. Continue jusqu'à ce que `maestro test mobile/.maestro/` retourne 0 sur les 7 flows critiques sur **les deux plateformes** (Android en local, iOS via le dernier run CI vert).
4. Commit et push tous les fixes (regroupés par catégorie : selectors, app bugs, backend bugs).
5. Note dans le ticket :
   - Liste des flows initialement KO et leur cause (par plateforme)
   - Liste des sous-tickets bugs créés
   - Output final `maestro test` Android (timing, count) + lien vers le run CI iOS final vert
   - Minutes macOS consommées sur le quota gratuit mensuel (pour suivi budget, cf. task-172)

## Boundaries

- **Pas de touche aux flows hors mobile/.maestro/** (par ex. ne modifie pas les workflows GitHub — ça c'est task-172).
- **Pas de touche au backend** sauf si un fix mineur évite de créer un sous-ticket (ex: typo dans une error message). Pour tout fix backend non-trivial : sous-ticket dédié.
- Fixes mobile autorisés sous le périmètre Mode UI/UX du `task-mobile.md` (theme, accessibilité, services existants).
- **Déclenchement des runs CI iOS (`workflow_dispatch`) réservé à l'owner** : un agent dispatché ne doit pas déclencher de run macOS de façon répétée/non supervisée (risque de consommer le quota gratuit mensuel sans contrôle). L'agent prépare et commit les fixes candidats ; l'owner déclenche le run et rapporte le résultat dans le ticket.

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
