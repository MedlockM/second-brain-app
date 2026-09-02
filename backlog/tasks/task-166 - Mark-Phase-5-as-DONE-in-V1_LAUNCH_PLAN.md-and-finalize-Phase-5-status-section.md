---
id: task-166
title: Mark Phase 5 as DONE in V1_LAUNCH_PLAN.md and finalize Phase 5 status section
status: To Do
assignee: []
created_date: '2026-06-10 05:40'
updated_date: '2026-09-02 18:45'
labels:
  - phase-5
  - mobile
  - release
  - docs
dependencies:
  - task-164
  - task-165
  - task-171
priority: high
dispatchable: false
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
## Context

Une fois task-164 et task-165 closes (validation device des flows non-Maestrables), Phase 5 du V1_LAUNCH_PLAN est terminée. Il faut acter ça dans la doc, comme ça a été fait pour Phase 3 (`PARTIELLEMENT DONE 2026-06-08`) et Phase 4 (`PARTIELLEMENT DONE 2026-06-09`), pour garder la traçabilité release.

Tâche **dispatchable** (Mode Release engineering de `task-mobile`) : édition de doc + petit cleanup checklist.

### Dépendances corrigées le 2026-09-02 — `task-172` retirée

`task-172` (Maestro Android dans les required PR checks) était listée en dépendance et est verrouillée `dispatchable: false` jusqu'à ce que l'UI soit figée, avec la CI Maestro en sommeil depuis le 2026-08-13 (`task-254`). Cette tâche ne pouvait donc **jamais** se débloquer. Maestro n'est plus un bloquant release : Phase 5 se clôt sur les validations device, pas sur la CI E2E.

Corollaire : **ne pas écrire dans le plan que la suite Maestro est verte ni qu'elle bloque les PR** — 3 flows sur 7 seulement sont verts, la CI est en sommeil, et `task-172` est ouverte. AC#3 a été réécrite en conséquence.

## Scope

1. Édite `docs/V1_LAUNCH_PLAN.md` :
   - **Phase 5 header** : ajoute `**DONE YYYY-MM-DD**` (ou `PARTIELLEMENT DONE` si certains bugs P2 encore ouverts) — même format que Phase 3 et Phase 4.
   - **Sous-section "Bugs détectés et fixés en route"** : liste les sous-tickets bugs créés par task-164/165/171 et qui ont été fixés (par task ID + 1 ligne de description), même format que Phase 4.
   - **Section "Outputs Phase 5"** (à créer si absente) : note URL TestFlight Internal, lien APK Android, SHA-1 keystore EAS (peut être tronqué pour la doc, valeur complète reste dans les tickets task-161/162).
   - **Sous-section "TDD coverage"** : consigner l'état réel de Maestro, pas un état souhaité — flows écrits, lesquels sont verts, CI en sommeil depuis le 2026-08-13 (`task-254`), `task-172` ouverte et verrouillée. Ne pas écrire que la suite est verte ni qu'elle bloque les PR.

2. Mets à jour la **section 5 "Ce qui reste bloqué sur des credentials externes"** :
   - `[x]` Google Cloud Console Android OAuth Client IDs provisionnés — il y en a **deux** (SHA-1 keystore EAS et SHA-1 Play App Signing), déjà consignés au 2026-09-02 ; vérifier que la ligne dit bien les deux (renvoie à task-163 et task-325)
   - Aucune autre case à cocher en Phase 5 (Phase 6 ouvrira IAP sandbox + RevenueCat webhook)

3. Met à jour le header du fichier (ligne 4) : `Dernière mise à jour : YYYY-MM-DD (Phase 5 close — builds iOS et Android validés sur device)`. Ne pas y accrocher de claim Maestro.

4. Aucune autre Phase à toucher dans ce ticket. **Pas de commit Phase 6** (IAP) dans le même PR — séparation propre.

## References

- `docs/V1_LAUNCH_PLAN.md` (cible unique)
- task-164, task-165, task-171 (sources des outputs et bugs trackés)
- task-172 : **non bloquante**, seulement à citer comme ouverte dans la sous-section TDD coverage
- Pattern existant : Phase 3 et Phase 4
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 docs/V1_LAUNCH_PLAN.md Phase 5 marquée DONE avec date, même format que Phase 3 et Phase 4
- [ ] #2 Sous-section Bugs détectés et fixés en route complétée avec les sous-tickets task-164/165/171
- [ ] #3 Sous-section TDD coverage décrit l'état réel de Maestro (flows écrits, lesquels sont verts, CI en sommeil depuis le 2026-08-13, task-172 ouverte) sans affirmer que la suite est verte ni qu'elle bloque les PR
- [ ] #4 Section 5 (credentials) : ligne Google Cloud Console Android OAuth en [x] et mentionnant les deux clients (SHA-1 keystore EAS + SHA-1 Play App Signing)
- [ ] #5 Header du fichier (Dernière mise à jour) actualisé

- [ ] #6 Aucun changement hors-scope (Phase 6+ non touchées)
<!-- AC:END -->
