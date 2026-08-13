---
id: task-171
title: >-
  Run full Maestro suite on Android emulator CI and iOS simulator CI, iterate
  red→green
status: Done
assignee: []
created_date: '2026-06-10 05:59'
updated_date: '2026-08-13 14:19'
labels:
  - phase-5
  - mobile
  - release
  - e2e
  - validation
dependencies:
  - task-161
  - task-168
  - task-169
  - task-170
priority: high
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
## Contexte

Cette tâche exécute la suite Maestro complète après l'ajout des flows 168–170. Aucun appareil Android physique n'est disponible : Android est donc validé sur l'émulateur GitHub Actions `ubuntu-latest`, tandis qu'iOS est validé sur simulateur via le job macOS déclenché manuellement. Les validations natives réelles (OAuth Google Android et share intents depuis Chrome/apps) restent dans task-162/task-163/task-165 et ne sont pas couvertes ici.

## Scope

1. Produire dans chaque job CI un build de test autonome qui embarque le bundle JavaScript et les variables publiques de l'environnement dev.
2. Lancer les sept flows critiques sur l'émulateur Android CI et sur le simulateur iOS CI.
3. Ne jamais masquer le code de sortie Maestro ; un flow rouge doit rendre le job rouge.
4. Collecter rapport JUnit, logs, captures et vidéos comme artifacts.
5. Itérer sur les selectors ou bugs applicatifs jusqu'à obtenir les deux plateformes vertes.
6. Consigner les flows initialement rouges, leur cause et les liens des runs finaux.

## Limites

- Cette tâche ne valide pas les UI natives hors-process : Apple/Google OAuth et véritables share sheets restent manuels.
- Elle ne clôt pas task-162, task-163 ou task-165.
- Les runs macOS restent manuels pour maîtriser le budget GitHub Actions.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 Le job iOS CI exécute toute la suite Maestro et retourne exit 0
- [ ] #2 Le job Android CI exécute toute la suite Maestro sur émulateur et retourne exit 0
- [x] #3 Les jobs ne contiennent aucun mécanisme masquant un échec Maestro et publient rapports et artifacts
- [ ] #4 Tous les correctifs applicatifs ou selectors nécessaires sont consignés
- [ ] #5 Le ticket liste les flows initialement en échec, leur cause et les liens vers les runs finaux verts
<!-- AC:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
1. S'appuyer sur les builds Release de test autonomes produits par le workflow. 2. Exécuter Android sur émulateur CI sans appareil physique. 3. Exécuter iOS uniquement via workflow_dispatch macOS. 4. Triage par artifacts, correction par lots, puis relance jusqu'au vert. 5. Conserver les validations natives réelles dans 162/163/165.
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Workflow refondu pour Maestro 2.8.0, builds Release autonomes, Android x86_64 sur émulateur, iOS Simulator manuel, vrais codes de sortie, JUnit et artifacts. Correctif reproductible patch-package ajouté pour Foojay 0.5/Gradle 9 (React Native 0.83), avec Foojay 1.0.

2026-08-09 — Ancienne CI diagnostiquée : install Maestro 1.38.0 en 404 puis commande absente, et publication JUnit en 403. Source corrigée (Maestro 2.8, permissions checks:write). Le build Gradle local dépasse désormais IBM_SEMERU et atteint la configuration app ; il s'arrête seulement faute de SDK Android local. Tous les secrets E2E requis sont configurés. Les runs finaux attendent le commit/push de ces changements.

2026-08-13 — Clôturée sur décision de l'owner, avec la couverture réelle consignée ici plutôt que par des AC cochés à tort. Les AC #1, #2, #4 et #5 restent non cochés : ils demandaient un run de la suite complète à exit 0 sur les deux plateformes, ce qui n'a pas eu lieu.

Ce qui est acquis : le run 31612429695 (workflow_dispatch sur 1d337e4, 2026-08-12) est vert sur les deux plateformes, mais avec `flow_filter: suites/tasks_168_170` — donc 3 flows sur 7. `01_login`, `06_search` et `07_paywall` sont passés sur émulateur Android API 33 et simulateur iPhone 16 / iOS 18.5, avec des durées réelles et `status="SUCCESS"` dans les rapports JUnit. L'AC #3 (aucun mécanisme masquant un échec, rapports et artifacts publiés) était déjà coché et le reste : le workflow propage les vrais codes de sortie.

Ce qui ne l'est pas : les 4 autres flows n'ont jamais tourné en CI. `02_share_intake` est volontairement neutralisé (tag `skipped`, réduit à un smoke test auth) car le share natif n'est pas pilotable par Maestro. `03_inbox_visibility`, `04_media_detail_progression` et `05_artifact_trigger_action` sont cassés : ils amorcent tous par `openLink: "media-summarizer://share?url=…"` puis attendent `assertVisible: "Save Link"`, or `redirectSystemPath` dans `mobile/app/+native-intent.tsx` redirige ce pattern vers `/(tabs)/inbox` depuis le 2026-06-11. Le flow 05 porte en outre quatre défauts de selector et de timeout indépendants de l'UI.

Pourquoi on clôt quand même : l'UI va être refondue, donc réparer et faire passer la suite maintenant serait à refaire. La CI Maestro passe en sommeil via task-254, qui consigne l'état des 7 flows et le plan de réactivation dans `docs/V1_LAUNCH_PLAN.md`. La couverture complète des 7 flows sera reprise à ce moment-là.
<!-- SECTION:NOTES:END -->
