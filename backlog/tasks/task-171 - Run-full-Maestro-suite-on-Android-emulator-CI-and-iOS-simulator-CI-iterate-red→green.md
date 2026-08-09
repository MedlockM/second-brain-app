---
id: task-171
title: >-
  Run full Maestro suite on Android emulator CI and iOS simulator CI, iterate
  red→green
status: To Do
assignee: []
created_date: '2026-06-10 05:59'
updated_date: '2026-08-09 20:13'
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
<!-- SECTION:NOTES:END -->
