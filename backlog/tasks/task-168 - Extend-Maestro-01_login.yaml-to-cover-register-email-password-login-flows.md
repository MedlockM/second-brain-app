---
id: task-168
title: Extend Maestro 01_login.yaml to cover register + email/password login flows
status: In Progress
assignee:
  - Codex
created_date: '2026-06-10 05:58'
updated_date: '2026-08-09 20:13'
labels:
  - phase-5
  - mobile
  - release
  - tooling
  - e2e
dependencies:
  - task-161
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
- [x] #1 mobile/.maestro/01_login.yaml couvre l'inscription d'un nouvel utilisateur avec un email unique par run
- [x] #2 Le flow couvre ensuite la connexion email/password d'un utilisateur existant et vérifie l'arrivée sur Inbox
- [ ] #3 Le flow est validé sur le simulateur iOS CI et l'émulateur Android CI, sans appareil Android physique requis
- [x] #4 Aucun email ni mot de passe sensible n'est hardcodé : les valeurs viennent des variables Maestro/CI
- [x] #5 Les flows Apple et Google restent hors scope
<!-- AC:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
1. Aligner le parcours d'inscription mobile sur le contrat backend actuel sans modifier les endpoints /api/v1. 2. Étendre 01_login.yaml avec inscription unique, logout, puis login email/password existant. 3. Injecter les variables de run depuis la CI. 4. Valider statiquement puis via les jobs iOS/Android CI.
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Implémenté dans mobile/.maestro/01_login.yaml : inscription avec email unique basé sur MAESTRO_RUN_ID, logout, puis login explicite via le compte E2E. Les champs/boutons utilisent des testID stables. AuthService.register consomme la réponse user-only de register puis ouvre la session via login, sans modifier le backend.

2026-08-09 — Validation statique OK : TypeScript, ESLint (0 erreur), parsing YAML. Les secrets E2E et un compte AWS dev indexé sont configurés. L'AC #3 reste ouverte jusqu'aux runs iOS/Android de la version commitée.
<!-- SECTION:NOTES:END -->
