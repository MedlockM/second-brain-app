---
id: task-162
title: Build Android development client via eas build --profile development
status: To Do
assignee: []
created_date: '2026-06-10 05:38'
labels:
  - phase-5
  - mobile
  - release
  - android
dependencies:
  - task-160
priority: high
dispatchable: false
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
> ⚠️ **MANUAL — OWNER ONLY. NEVER DISPATCH TO A SUBAGENT.**
> Cette tâche doit être exécutée à la main par l'owner. Même si à un moment elle est marquée `dispatchable: true` par erreur, **aucun agent ne doit la prendre**. Raison : `eas build` Android est interactif à la première exécution (création du keystore EAS, prompt de confirmation), et la capture du SHA-1 nécessite des clics sur le dashboard EAS / une commande `eas credentials` qui mène à un menu interactif. Le résultat à reporter (SHA-1, URL APK) est un input critique pour task-163 qui suit — un agent qui rate la capture invalide toute la chaîne Android.

## Context

Phase 5 du V1_LAUNCH_PLAN, étape 4 : `eas build --platform android --profile development` produit un APK dev client Android sideloadable. Première exécution génère le **keystore EAS** dont le SHA-1 est requis pour provisionner le Google OAuth Android Client ID (task-163).

## Prérequis

- task-160 ✅ (prebuild a généré `mobile/android/`)
- `eas-cli` installé, `eas whoami` retourne un compte valide
- (Pour la suite) Google Play Console disponible — pas requis pour ce build dev (sideload), seulement pour Phase 6

## Scope manuel

1. `cd mobile && eas build --platform android --profile development`
2. Première exécution : EAS demande à créer un nouveau keystore Android. Réponds **Yes** (V1 = premier build).
3. Attends la fin du build (~10-20 min). Récupère :
   - **URL APK** dans le dashboard EAS
   - **Keystore SHA-1** : `cd mobile && eas credentials --platform android` → sélectionne le profile `development` → note la valeur "SHA-1 fingerprint" (format `AB:CD:EF:...`)
4. Sideload l'APK sur device Android : `adb install <path>.apk` ou via le QR code EAS.
5. Note dans le ticket :
   - Build ID EAS
   - URL dashboard EAS
   - **SHA-1 keystore EAS** (sera consommé par task-163)
   - SHA-256 keystore (au cas où Google le demande)
   - Erreurs/warnings éventuels

## Pièges connus

- À la **première run**, EAS génère le keystore et le stocke sur leurs servers. Si tu réponds **No** par erreur, le build échoue avec "no keystore configured" — relance simplement.
- Le SHA-1 du keystore EAS sera **différent** d'un futur upload key Google Play (Phase 10). Pour le dev/preview build, c'est le SHA-1 EAS qui compte.
- Si `eas credentials` ne montre pas le keystore après le build, attends 1-2 min (sync dashboard) puis retry.

## References

- `docs/V1_LAUNCH_PLAN.md` Phase 5 §4 + section 5 (Google Cloud Console Android OAuth Client ID à différer)
- `mobile/eas.json` profil `development`
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 eas build --platform android --profile development termine en status finished
- [ ] #2 APK installé et lancable sur device physique Android (sideload via adb ou QR code)
- [ ] #3 Keystore SHA-1 récupéré via eas credentials --platform android et noté dans le ticket
- [ ] #4 Build ID EAS et URL dashboard notés dans le ticket
<!-- AC:END -->
