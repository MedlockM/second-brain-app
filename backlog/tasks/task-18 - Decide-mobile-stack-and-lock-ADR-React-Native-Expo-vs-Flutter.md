---
id: task-18
title: Decide mobile stack and lock ADR (React Native Expo vs Flutter)
status: Done
assignee:
  - codex
created_date: '2026-02-24 11:02'
updated_date: '2026-02-24 20:29'
labels: []
dependencies: []
priority: high
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Decide the mobile implementation stack for the share-first app and lock the architecture decision record so all downstream mobile work targets one runtime and toolchain.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 A decision between React Native Expo and Flutter is formally recorded in an ADR.
- [x] #2 The ADR documents rationale, key tradeoffs, and constraints for share intent/extension support.
- [x] #3 The ADR lists required CI/CD, signing, and developer setup implications.
- [x] #4 All Phase 4/5 tasks can reference this ADR as the single source of truth.
<!-- AC:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
1) Formaliser un ADR de décision de stack mobile (React Native + Expo retenu) avec statut, contexte, alternatives évaluées et décision.
2) Documenter explicitement les contraintes share entrant iOS/Android, les limites Expo out-of-the-box et la stratégie de mitigation (validation précoce sur devices réels, possibilité de basculer vers RN bare si blocage).
3) Documenter les implications pratiques pour un profil novice mobile: setup développeur, CI/CD, signature, distribution interne.
4) Mettre à jour le plan phasé pour référencer cet ADR comme source de vérité pour les phases mobile/release.
5) Mettre à jour task-18 (notes + cases d'acceptance remplies) une fois les documents modifiés.
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
ADR créé: docs/ADR/mobile-stack-share-first.md (décision retenue: React Native + Expo development builds + EAS).

L'ADR documente les alternatives (RN Expo, RN bare, Flutter), les compromis, les contraintes share entrant iOS/Android, et la stratégie de mitigation/fallback.

Implications setup dev, CI/CD, signing et critères de passage vers publication documentés.

Plan phasé mis à jour pour référencer explicitement l'ADR comme source de vérité mobile (Directives + Phase 0).
<!-- SECTION:NOTES:END -->
