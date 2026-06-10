---
id: task-164
title: >-
  Validate iOS dev build — non-Maestrable flows only (Apple Sign-in, Google
  sheet, Safari share)
status: To Do
assignee: []
created_date: '2026-06-10 05:39'
updated_date: '2026-06-10 05:57'
labels:
  - phase-5
  - mobile
  - release
  - ios
  - validation
dependencies:
  - task-161
priority: high
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
> ⚠️ **MANUAL — OWNER ONLY. NEVER DISPATCH TO A SUBAGENT.**
> Cette tâche doit être exécutée à la main par l'owner sur device physique iOS. Même si à un moment elle est marquée `dispatchable: true` par erreur, **aucun agent ne doit la prendre**. Raison : la validation requiert d'utiliser un device iOS physique avec compte Apple ID + compte Google personnel, de tapoter dans des modaux natifs hors-process (Apple Sign-in, ASWebAuthenticationSession), et de partager depuis Safari via la UI iOS standard. Aucune de ces interactions n'est scriptable — c'est précisément la raison pour laquelle elles ne sont pas dans la suite Maestro.

## Context

Phase 5 du V1_LAUNCH_PLAN. La majorité des flows V1 sont validés automatiquement par la suite Maestro (cf. task-167 → task-170, mobile/.maestro/). Cette tâche couvre **uniquement les flows que Maestro ne peut pas tester** sur iOS, parce qu'ils impliquent des UI hors du process app :

1. **Sign in with Apple** — modal natif iOS hors process
2. **Continue with Google** — `ASWebAuthenticationSession` (sheet système)
3. **Share intent depuis Safari** — Maestro contrôle l'app, pas Safari ; la share extension iOS ne peut être déclenchée qu'à la main

**Tâche manuelle** — `dispatchable: false`. Doit rester courte (~10 min) une fois le dev build sur device.

## Prérequis

- task-161 ✅ (dev build iOS installé sur device physique)
- Compte Apple ID (peut être un sandbox tester)
- Compte Google personnel ajouté comme utilisateur test dans Google Cloud Console (mode Test)
- task-170 ✅ recommandé (suite Maestro verte AVANT cette tâche, pour ne pas mélanger les root causes)

## Scope — 3 flows seulement

Coche chaque case. Pour chaque KO, ouvre un sous-ticket bug avec format `task-XXX [ios] <description>` et label `bug, mobile, ios`.

- [ ] **Sign in with Apple** : tap "Continue with Apple" sur l'écran auth → modal natif Apple (Touch ID / Face ID) → user créé/lié côté backend → atterrit sur l'inbox.
- [ ] **Continue with Google** : tap "Continue with Google" → `ASWebAuthenticationSession` s'ouvre → choisis le compte test → user créé/lié → inbox.
- [ ] **Share intent depuis Safari** : ouvre un article Wikipedia dans Safari → bouton Share → sélectionne "Second Brain" → l'écran share-confirm s'affiche avec l'URL → submit → toast de confirmation. Vérifie ensuite dans l'inbox que la vignette est apparue.

## Tout le reste

Tout le reste (auth email/password, optimistic insert inbox, polling detail screen, search lexical, paywall display) est testé automatiquement par la suite Maestro. **N'inclus pas ces flows ici** sauf si Maestro est down et qu'on a besoin d'un fallback temporaire.

## References

- `docs/V1_LAUNCH_PLAN.md` Phase 5 §5
- `mobile/app/(auth)/login.tsx` (Apple/Google buttons)
- `mobile/app/share-confirm.tsx`
- task-170 (suite Maestro full coverage)
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 Sign in with Apple crée/lie un user iOS et atterrit sur l'inbox
- [ ] #2 Continue with Google (ASWebAuthenticationSession) crée/lie un user iOS et atterrit sur l'inbox
- [ ] #3 Share intent depuis Safari atteint share-confirm, soumet sans erreur, et la vignette apparaît dans l'inbox
- [ ] #4 Tous les bugs P0/P1 détectés ont un sous-ticket et sont résolus avant clôture
<!-- AC:END -->
