---
id: task-166
title: Mark Phase 5 as DONE in V1_LAUNCH_PLAN.md and finalize Phase 5 status section
status: To Do
assignee: []
created_date: '2026-06-10 05:40'
updated_date: '2026-06-10 06:00'
labels:
  - phase-5
  - mobile
  - release
  - docs
dependencies:
  - task-164
  - task-165
  - task-171
  - task-172
priority: high
dispatchable: false
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
## Context

Une fois task-164 et task-165 closes (validation device des 3 flows non-Maestrables), task-171 close (suite Maestro verte localement) et task-172 close (Maestro Android dans les required PR checks), Phase 5 du V1_LAUNCH_PLAN est terminée. Il faut acter ça dans la doc, comme ça a été fait pour Phase 3 (`PARTIELLEMENT DONE 2026-06-08`) et Phase 4 (`PARTIELLEMENT DONE 2026-06-09`), pour garder la traçabilité release.

Tâche **dispatchable** (Mode Release engineering de `task-mobile`) : édition de doc + petit cleanup checklist.

## Scope

1. Édite `docs/V1_LAUNCH_PLAN.md` :
   - **Phase 5 header** : ajoute `**DONE YYYY-MM-DD**` (ou `PARTIELLEMENT DONE` si certains bugs P2 encore ouverts) — même format que Phase 3 et Phase 4.
   - **Sous-section "Bugs détectés et fixés en route"** : liste les sous-tickets bugs créés par task-164/165/171 et qui ont été fixés (par task ID + 1 ligne de description), même format que Phase 4.
   - **Section "Outputs Phase 5"** (à créer si absente) : note URL TestFlight Internal, lien APK Android, SHA-1 keystore EAS (peut être tronqué pour la doc, valeur complète reste dans les tickets task-161/162).
   - **Sous-section "TDD coverage"** : note que la suite Maestro (7 flows) est en place et bloque les PR sur `mobile/**` (référence task-172).

2. Mets à jour la **section 5 "Ce qui reste bloqué sur des credentials externes"** :
   - `[x]` Google Cloud Console Android OAuth Client ID provisionné (renvoie à task-163)
   - Aucune autre case à cocher en Phase 5 (Phase 6 ouvrira IAP sandbox + RevenueCat webhook)

3. Met à jour le header du fichier (ligne 4) : `Dernière mise à jour : YYYY-MM-DD (Phase 5 dev build iOS+Android validés sur device + suite Maestro 7 flows verte, prêt pour Phase 6 IAP sandbox)`.

4. Aucune autre Phase à toucher dans ce ticket. **Pas de commit Phase 6** (IAP) dans le même PR — séparation propre.

## References

- `docs/V1_LAUNCH_PLAN.md` (cible unique)
- task-164, task-165, task-171, task-172 (sources des outputs et bugs trackés)
- Pattern existant : Phase 3 et Phase 4
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 docs/V1_LAUNCH_PLAN.md Phase 5 marquée DONE avec date, même format que Phase 3 et Phase 4
- [ ] #2 Sous-section Bugs détectés et fixés en route complétée avec les sous-tickets task-164/165/171
- [ ] #3 Sous-section TDD coverage mentionne la suite Maestro 7 flows + référence task-172
- [ ] #4 Section 5 (credentials) : ligne Google Cloud Console Android OAuth Client ID en [x]
- [ ] #5 Header du fichier (Dernière mise à jour) actualisé

- [ ] #6 Aucun changement hors-scope (Phase 6+ non touchées)
<!-- AC:END -->
