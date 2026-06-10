---
id: task-165
title: >-
  Validate Android dev build — non-Maestrable flows only (Google sheet, Chrome
  share)
status: To Do
assignee: []
created_date: '2026-06-10 05:39'
updated_date: '2026-06-10 05:57'
labels:
  - phase-5
  - mobile
  - release
  - android
  - validation
dependencies:
  - task-162
  - task-163
priority: high
dispatchable: false
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
> ⚠️ **MANUAL — OWNER ONLY. NEVER DISPATCH TO A SUBAGENT.**
> Cette tâche doit être exécutée à la main par l'owner sur device physique Android. Même si à un moment elle est marquée `dispatchable: true` par erreur, **aucun agent ne doit la prendre**. Raison : la validation requiert un device Android physique avec compte Google de test, l'utilisation du sheet Google Sign-In natif (hors process app), et le partage depuis Chrome via la UI Android. Aucune de ces interactions n'est scriptable — c'est précisément la raison pour laquelle elles ne sont pas dans la suite Maestro.

## Context

Phase 5 du V1_LAUNCH_PLAN. La majorité des flows V1 sont validés automatiquement par la suite Maestro (cf. task-167 → task-170, mobile/.maestro/). Cette tâche couvre **uniquement les flows que Maestro ne peut pas tester** sur Android, parce qu'ils impliquent des UI hors du process app :

1. **Continue with Google** — sheet Google Sign-In natif hors process app
2. **Share intent depuis Chrome / app native** — Maestro contrôle l'app, pas Chrome ; il peut faire un deep link mais pas valider l'intégration share intent réelle

Sign in with Apple n'est **pas applicable sur Android** — vérifie juste que le bouton soit absent ou no-op clean.

**Tâche manuelle** — `dispatchable: false`. Doit rester courte (~10 min) une fois l'APK sur device.

## Prérequis

- task-162 ✅ (APK installé sur device Android)
- task-163 ✅ (Google OAuth Client ID Android provisionné)
- Compte Google ajouté comme utilisateur test dans Google Cloud Console
- task-170 ✅ recommandé (suite Maestro verte AVANT cette tâche)

## Scope — 3 vérifs

- [ ] **Continue with Google** : tap "Continue with Google" → sheet Google natif → choisis le compte test → user créé/lié → inbox. Si **DEVELOPER_ERROR** apparaît : SHA-1 du keystore EAS ne matche pas celui déclaré dans Google Cloud Console (re-vérifier task-163).
- [ ] **Sign in with Apple sur Android** : vérifie que le bouton "Continue with Apple" est soit absent, soit explicitement disabled, soit no-op clean (pas de crash). Pas de flow à exécuter, juste un check d'état UI.
- [ ] **Share intent depuis Chrome** : ouvre un article dans Chrome → menu ⋮ → Partager → sélectionne "Second Brain" → écran share-confirm → submit. Vérifie ensuite dans l'inbox que la vignette est apparue.
- [ ] **Share intent texte/audio depuis app native** : depuis Google Keep ou un fichier audio, partage vers Second Brain → écran share-confirm reconnait le type → submit.

## Pièges connus

- Si le share intent ne propose pas "Second Brain" : vérifie `mobile/app.config.ts` → `android.intentFilters`.
- Sur certains OEM (Xiaomi, Oppo), les permissions notifications/background exigent une activation manuelle. Note dans le ticket si rencontré.

## References

- `docs/V1_LAUNCH_PLAN.md` Phase 5 §5
- `mobile/app.config.ts` section `android.intentFilters`
- task-163 (OAuth Client ID Android)
- task-170 (suite Maestro full coverage)
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 Continue with Google crée/lie un user Android et atterrit sur l'inbox (sans DEVELOPER_ERROR)
- [ ] #2 Bouton Sign in with Apple soit absent soit no-op clean sur Android
- [ ] #3 Share intent depuis Chrome (URL) atteint share-confirm, soumet, et la vignette apparaît dans l'inbox
- [ ] #4 Share intent texte ou audio depuis app native fonctionne
- [ ] #5 Tous les bugs P0/P1 détectés ont un sous-ticket et sont résolus avant clôture
<!-- AC:END -->
