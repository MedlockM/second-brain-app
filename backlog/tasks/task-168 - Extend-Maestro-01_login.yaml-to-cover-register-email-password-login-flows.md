---
id: task-168
title: Extend Maestro 01_login.yaml to cover register + email/password login flows
status: To Do
assignee: []
created_date: '2026-06-10 05:58'
labels:
  - phase-5
  - mobile
  - release
  - tooling
  - e2e
dependencies:
  - task-161
  - task-162
priority: high
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
## Context

Phase 5 = boucle TDD (cf. réorganisation task-167 → task-171). Le flow Maestro actuel `mobile/.maestro/01_login.yaml` ne couvre que login d'un user existant (`TEST_USER_EMAIL` / `TEST_USER_PASSWORD` from `config.yaml`). Il manque :

1. Le **register** d'un user neuf (création de compte côté backend)
2. Le **login email/password** explicite avec assertion sur l'arrivée sur l'inbox

Sans ces deux assertions, on ne peut pas régresser sur la chaîne `register → verification → login → inbox` qui est le path le plus utilisé en prod.

## Scope

Édite `mobile/.maestro/01_login.yaml` (et au besoin ajoute des fichiers utilitaires dans `mobile/.maestro/utils/`) pour ajouter :

1. **Sous-flow register** : tap "Sign up" → renseigne un email frais (template `e2e-register-${MAESTRO_RUN_ID}@test.local` avec timestamp pour idempotence) → password fort → submit → assertion sur écran de verification ou bypass dev → atterrit sur l'inbox.
2. **Sous-flow login email** : tap "Sign in with email" → renseigne `TEST_USER_EMAIL` / `TEST_USER_PASSWORD` from env → assertion `text: "Inbox"` (ou équivalent du tab Inbox visible).
3. Garde le flow Apple/Google login **hors scope** (Maestro ne peut pas tester les modaux natifs hors process — c'est ce que validera task-164/165 manuellement).

## Convention

- Réutilise les patterns Maestro déjà en place dans les autres flows (`extendedWaitUntil`, `tapOn`, `inputText`).
- `appId: com.secondbrainlabs.core` et tags `critical, auth` (déjà en place).
- Pas de hardcoding d'email/password : utilise `${TEST_USER_EMAIL}` / `${TEST_USER_PASSWORD}` from `config.yaml`.
- L'email register doit être unique par run (use `${MAESTRO_RUN_ID}` ou `${TIMESTAMP}` injecté par le runner CI).

## References

- `mobile/.maestro/01_login.yaml` (à éditer)
- `mobile/.maestro/config.yaml` (env vars existantes)
- `mobile/.maestro/utils/` (helpers existants)
- `.github/workflows/mobile-e2e-maestro.yml` (runner CI)
- `mobile/app/(auth)/login.tsx` et `mobile/app/(auth)/register.tsx`
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 mobile/.maestro/01_login.yaml couvre register d'un user neuf avec email unique par run
- [ ] #2 Couvre login email/password d'un user existant avec assertion sur l'inbox
- [ ] #3 Le flow passe en local sur device iOS branché USB ET sur device/émulateur Android
- [ ] #4 Pas de hardcoding email/password (utilise les env vars du config.yaml)
- [ ] #5 Aucun test des flows Apple/Google (restés hors-scope)
<!-- AC:END -->
