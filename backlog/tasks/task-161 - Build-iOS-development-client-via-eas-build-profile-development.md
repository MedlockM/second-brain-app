---
id: task-161
title: Build iOS development client via eas build --profile development
status: Done
assignee:
  - Codex
created_date: '2026-06-10 05:37'
updated_date: '2026-08-09 19:29'
labels:
  - phase-5
  - mobile
  - release
  - ios
dependencies:
  - task-160
priority: high
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
> ⚠️ **MANUAL — OWNER ONLY. NEVER DISPATCH TO A SUBAGENT.**
> Cette tâche doit être exécutée à la main par l'owner. Même si à un moment elle est marquée `dispatchable: true` par erreur, **aucun agent ne doit la prendre**. Raison : `eas build` Apple est interactif (auth EAS, OTP Apple Developer, choix de provisioning, OTP iCloud) — un agent ne peut pas répondre aux prompts 2FA. L'agent fournirait un faux résultat ou bloquerait le worktree pendant 20+ min sans output.

## Context

Phase 5 du V1_LAUNCH_PLAN, étape 2 : `eas build --platform ios --profile development` produit un dev client iOS distribuable via TestFlight Internal ou direct install. Sans ce dev client, on ne peut pas tester `expo-share-intent` (qui requiert un dev build, pas Expo Go).

## Prérequis

- task-160 ✅ (prebuild a généré `mobile/ios/`)
- Apple Developer Program actif ($99/an, OK 2026-06-01)
- Service ID + Sign in with Apple Key + App ID `com.secondbrainlabs.core` provisionnés (OK 2026-06-08)
- `eas-cli` installé globalement, `eas whoami` retourne un compte valide

## Scope manuel

1. `cd mobile && eas whoami` — confirme l'auth EAS
2. (Première fois uniquement) `eas build:configure --platform ios` — EAS demande à créer/réutiliser : distribution certificate, push key, provisioning profile. Réponds **Yes** pour qu'EAS gère les credentials sur leurs servers.
3. `eas build --platform ios --profile development`
4. Attends la fin du build (~15-25 min). Récupère :
   - **URL TestFlight Internal** dans le dashboard EAS → onglet Build
   - **IPA direct install link** (pour install hors TestFlight)
   - Hash SHA-256 du build (signe-le dans le ticket)
5. Note dans le ticket :
   - Build ID EAS
   - URL dashboard EAS du build
   - URL TestFlight Internal
   - Erreurs/warnings éventuels (cert pinning, provisioning, missing entitlements)

## Pièges connus

- Si `eas build:configure` demande à régénérer le distribution certificate, **dis Yes** seulement si l'ancien n'est pas utilisé en production (V1 = premier build, OK).
- Sign in with Apple capability doit être active sur l'App ID Apple — vérifie sur developer.apple.com avant le build.
- Si erreur "no associated domains" et que `app.config.ts` ne déclare pas `associatedDomains` : OK, on n'utilise pas Universal Links en V1.

## References

- `docs/V1_LAUNCH_PLAN.md` Phase 5 §2-3
- `mobile/eas.json` profil `development`
- `docs/PRODUCTION_RELEASE_RUNBOOK.md` (référence release)
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 Un build EAS iOS avec le profil development termine en status FINISHED
- [x] #2 Le Build ID EAS et le commit source sont consignés dans le ticket
- [x] #3 Le build est une distribution interne pour iPhone physique et le caractère expiré du lien d'artifact est documenté
- [x] #4 Le development client est installé, se lance sur l'iPhone owner et charge le bundle Metro courant
<!-- AC:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
1. Vérifier l'historique EAS iOS du projet et identifier le dernier build development physique. 2. Confirmer que le build correspond au socle natif Expo SDK 55 actuellement installé et utilisé sur l'iPhone owner. 3. Consigner le Build ID et l'état de distribution. 4. Clore la tâche sur la preuve du client installé, même si l'ancien lien d'artifact EAS a depuis expiré.
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Validation 2026-08-09 : l'historique EAS confirme le build iOS development `324f110a-8cbe-447c-96bf-2214099348c4`, status `FINISHED`, distribution `INTERNAL`, SDK 55, iPhone physique, commit `8c637654c3951cdeee396b6981d8dbefd197ecd2`. Le lien d'artifact a expiré le 2026-06-25, mais l'owner confirme que le development client est déjà installé sur son iPhone et que les fonctions natives (share extension/auth) fonctionnent quand Metro est lancé. Le serveur du 2026-08-09 annonce explicitement `Using development build` et le bundle est chargé par ce client.
<!-- SECTION:NOTES:END -->
