---
id: task-163
title: >-
  Provision the Android Google OAuth Client ID from the EAS keystore SHA-1, then
  run the single Android development build
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
> Cette tâche doit être exécutée à la main par l'owner. Même si à un moment elle est marquée `dispatchable: true` par erreur, **aucun agent ne doit la prendre**. Raison : la création du Client ID OAuth Android se fait exclusivement via l'UI web de Google Cloud Console — `gcloud` CLI n'expose pas la création d'OAuth Client ID type Android. Aucun agent ne peut cliquer dans la Cloud Console à la place de l'owner. Le build EAS et l'installation sur device physique sont eux aussi hors de portée d'un agent.

## Context

Différé de Phase 2 vers Phase 5 dans V1_LAUNCH_PLAN (cf. ligne 217, ligne 394). Le Google OAuth Client ID Android requiert le **SHA-1 du keystore qui signera l'APK** — ce keystore est créé par task-162 via `eas credentials`, sans build.

Sans ce Client ID, le bouton "Continue with Google" ne fonctionnera pas sur Android (erreur DEVELOPER_ERROR ou similaire au tap).

Cette tâche porte désormais **aussi le build Android de développement**, déplacé depuis task-162 pour n'en faire qu'un seul (voir la section « Étapes 9 à 11 » plus bas). Séquence complète : keystore (task-162) → Client ID → variable déclarée côté EAS → build unique.

## Prérequis

- task-162 ✅ (keystore EAS créé, SHA-1 noté)
- Compte Google Cloud Console actif, projet `Second Brain` (ou nom équivalent) déjà créé
- Accès owner au projet GCP
- `eas-cli` installé, `eas whoami` retourne un compte valide (pour les étapes 9 à 11)
- Un device Android physique avec débogage USB actif, ou `adb` opérationnel

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

## Étapes 9 à 11 — déclarer la variable, PUIS lancer le build unique

Ajouté le 2026-08-13 sur décision de l'owner : le build Android a été retiré de task-162 et déplacé ici, pour n'être lancé qu'une seule fois, une fois le Client ID connu.

**Pourquoi cet ordre est obligatoire.** `mobile/app.config.ts:114-115` écrit `process.env.EXPO_PUBLIC_GOOGLE_CLIENT_ID_ANDROID || ""` dans `extra.googleClientIdAndroid`, et `extra` est figé **au moment du build**. Côté app, `mobile/src/constants/config.ts:13` lit cette valeur cuite, puis `mobile/src/components/SocialAuthButtons.tsx:49` la passe en `androidClientId`. Un APK construit avant que la variable existe embarque donc `""` de façon définitive : le bouton « Continue with Google » y est mort, et aucune édition de `mobile/.env` après coup ne le réparera. D'où : variable d'abord, build ensuite.

9. **Déclarer la variable pour le build.** Le profil `development` de `mobile/eas.json` ne contient aujourd'hui que `EXPO_PUBLIC_API_BASE_URL` — la variable Android n'y est pas. Deux options, au choix :
   - `cd mobile && eas secret:create --scope project --name EXPO_PUBLIC_GOOGLE_CLIENT_ID_ANDROID --value <le Client ID>` (recommandé : la valeur n'entre pas dans le dépôt) ;
   - ou l'ajouter au bloc `env` du profil `development` de `mobile/eas.json`. Un OAuth Client ID Android n'est pas un secret d'authentification — il est de toute façon extractible du binaire, et le préfixe `EXPO_PUBLIC_` le destine au client — donc le versionner est acceptable. Rester cohérent avec `EXPO_PUBLIC_API_BASE_URL`, déjà en clair dans ce fichier.
10. Vérifier que la variable est bien vue par EAS : `cd mobile && eas env:list` (ou `eas secret:list` selon la version d'`eas-cli`).
11. **Lancer le build unique** : `cd mobile && eas build --platform android --profile development`. Attendre ~10-20 min, puis récupérer l'URL de l'APK et le Build ID sur le dashboard EAS, et installer sur un device physique (`adb install <chemin>.apk` ou QR code). Noter Build ID, URL dashboard et erreurs/warnings éventuels dans ce ticket.

Le keystore existant depuis task-162, EAS ne posera plus de question de signature : le build doit partir sans prompt.

## Important

- Quand on passera en **Phase 10** (publication Play Store), Google Play générera un **upload key + app signing key** distincts. Il faudra alors créer un **2ᵉ OAuth Client ID Android** avec le SHA-1 du nouveau keystore Play Console. Ce ticket gère uniquement le SHA-1 EAS (dev/preview build). Note cette suite dans le ticket Phase 10 quand on y arrivera.
- Renseigner `mobile/.env` (étape 6) sert au dev local ; c'est l'étape 9 qui fait entrer la valeur dans le binaire EAS. Les deux sont utiles et ne se remplacent pas.

## Pièges connus (étapes 9 à 11)

- Un APK construit sans la variable embarque `""` définitivement. Si le build part avant l'étape 9, il faut le refaire — c'est précisément ce que ce découpage évite.
- Le SHA-1 du keystore EAS diffère de celui du futur upload key Google Play (Phase 10) : ne pas confondre.
- Si le build échoue sur une question de credentials, c'est que task-162 n'a pas abouti — ne pas laisser EAS générer un keystore ici, sinon le SHA-1 déclaré dans le Client ID ne correspondra plus.

## References

- task-162 — crée le keystore et fournit le SHA-1 consommé à l'étape 4
- `docs/V1_LAUNCH_PLAN.md` Phase 2 §7, Phase 5 §4 et §5, section 5
- `mobile/.env.example` ligne `EXPO_PUBLIC_GOOGLE_CLIENT_ID_ANDROID`
- `mobile/app.config.ts:114-115` (cuit la var dans `extra` au moment du build)
- `mobile/src/constants/config.ts:13` puis `mobile/src/components/SocialAuthButtons.tsx:49` (chaîne de lecture côté app)
- `mobile/eas.json` profil `development` (ne contient aujourd'hui que `EXPO_PUBLIC_API_BASE_URL`)
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 OAuth Client ID Android créé dans Google Cloud Console avec package com.secondbrainlabs.core et SHA-1 EAS
- [ ] #2 EXPO_PUBLIC_GOOGLE_CLIENT_ID_ANDROID rempli dans mobile/.env (dev local)
- [ ] #3 docs/V1_LAUNCH_PLAN.md section 5 et Phase 2/5 mis à jour
- [ ] #4 bash scripts/mobile_release_check.sh passe sans warning sur EXPO_PUBLIC_GOOGLE_CLIENT_ID_ANDROID
- [ ] #5 EXPO_PUBLIC_GOOGLE_CLIENT_ID_ANDROID est déclarée côté EAS (secret projet ou bloc env du profil development de mobile/eas.json) AVANT tout build, et eas env:list / eas secret:list la montre
- [ ] #6 Un seul build Android est lancé, après l'étape 5, via eas build --platform android --profile development, et il termine avec succès
- [ ] #7 Build ID et URL du build EAS notés dans ce ticket ; l'APK est installé sur un device Android physique et l'app démarre
- [ ] #8 Le bouton Continue with Google est vérifié à la main sur ce build : il ouvre le consentement Google et ne renvoie pas DEVELOPER_ERROR
<!-- AC:END -->
