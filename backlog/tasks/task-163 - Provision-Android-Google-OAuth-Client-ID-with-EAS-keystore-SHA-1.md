---
id: task-163
title: Provision Android Google OAuth Client ID with EAS keystore SHA-1
status: To Do
assignee: []
created_date: '2026-06-10 05:38'
labels:
  - phase-5
  - mobile
  - release
  - android
  - auth
dependencies:
  - task-162
priority: high
dispatchable: false
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
> ⚠️ **MANUAL — OWNER ONLY. NEVER DISPATCH TO A SUBAGENT.**
> Cette tâche doit être exécutée à la main par l'owner. Même si à un moment elle est marquée `dispatchable: true` par erreur, **aucun agent ne doit la prendre**. Raison : la création du Client ID OAuth Android se fait exclusivement via l'UI web de Google Cloud Console — `gcloud` CLI n'expose pas la création d'OAuth Client ID type Android. Aucun agent ne peut cliquer dans la Cloud Console à la place de l'owner.

## Context

Différé de Phase 2 vers Phase 5 dans V1_LAUNCH_PLAN (cf. ligne 217, ligne 394). Le Google OAuth Client ID Android requiert le **SHA-1 du keystore qui signera l'APK** — ce keystore n'existe qu'après le premier `eas build` Android (task-162).

Sans ce Client ID, le bouton "Continue with Google" ne fonctionnera pas sur Android (erreur DEVELOPER_ERROR ou similaire au tap).

## Prérequis

- task-162 ✅ (keystore EAS créé, SHA-1 noté)
- Compte Google Cloud Console actif, projet `Second Brain` (ou nom équivalent) déjà créé
- Accès owner au projet GCP

## Scope manuel

1. Va sur https://console.cloud.google.com → sélectionne le projet GCP
2. **APIs & Services → Credentials → CREATE CREDENTIALS → OAuth client ID**
3. Application type : **Android**
4. Renseigne :
   - **Name** : `Second Brain Android (EAS development)`
   - **Package name** : `com.secondbrainlabs.core`
   - **SHA-1 certificate fingerprint** : la valeur récupérée dans task-162 (format `AB:CD:EF:...`)
5. Save → copie l'**OAuth Client ID** généré
6. Dans `mobile/.env` (local, gitignored), renseigne :
   ```
   EXPO_PUBLIC_GOOGLE_CLIENT_ID_ANDROID=<la valeur>
   ```
7. Édite `docs/V1_LAUNCH_PLAN.md` :
   - Section 5 : passe la ligne `[ ] Google Cloud Console Android OAuth Client ID à créer` en `[x]` avec la date du jour
   - Phase 2 §6/§7 : note que le 3ᵉ Client ID Google est désormais provisionné
8. Lance `bash scripts/mobile_release_check.sh` pour confirmer que la check `EXPO_PUBLIC_GOOGLE_CLIENT_ID_ANDROID` n'est plus skipped et passe.

## Important

- Quand on passera en **Phase 10** (publication Play Store), Google Play générera un **upload key + app signing key** distincts. Il faudra alors créer un **2ᵉ OAuth Client ID Android** avec le SHA-1 du nouveau keystore Play Console. Ce ticket gère uniquement le SHA-1 EAS (dev/preview build). Note cette suite dans le ticket Phase 10 quand on y arrivera.
- Le rebuild Android n'est PAS strictement nécessaire après ajout de la var dans `.env` — `expo-auth-session` la lit au runtime via `process.env.EXPO_PUBLIC_GOOGLE_CLIENT_ID_ANDROID`. Mais pour qu'elle soit injectée dans le binaire EAS, il faut la déclarer dans **EAS Secrets** (`eas secret:create`) ou dans le profil `development` de `eas.json` puis **rebuild** (relancer task-162).

## References

- `docs/V1_LAUNCH_PLAN.md` Phase 2 §7, Phase 5 §5, section 5
- `mobile/.env.example` ligne `EXPO_PUBLIC_GOOGLE_CLIENT_ID_ANDROID`
- `mobile/app.config.ts` (lit la var via `process.env`)
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 OAuth Client ID Android créé dans Google Cloud Console avec package com.secondbrainlabs.core et SHA-1 EAS
- [ ] #2 EXPO_PUBLIC_GOOGLE_CLIENT_ID_ANDROID rempli dans mobile/.env (et EAS Secrets si rebuild prévu)
- [ ] #3 docs/V1_LAUNCH_PLAN.md section 5 et Phase 2/5 mis à jour
- [ ] #4 bash scripts/mobile_release_check.sh passe sans warning sur EXPO_PUBLIC_GOOGLE_CLIENT_ID_ANDROID
<!-- AC:END -->
