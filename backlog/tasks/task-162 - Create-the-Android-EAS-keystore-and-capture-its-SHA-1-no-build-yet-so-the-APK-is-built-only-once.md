---
id: task-162
title: >-
  Create the Android EAS keystore and capture its SHA-1 (no build yet, so the
  APK is built only once)
status: Done
assignee: []
created_date: '2026-06-10 05:38'
updated_date: '2026-08-13 18:33'
labels:
  - phase-5
  - mobile
  - release
  - android
dependencies:
  - task-160
priority: high
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
> ⚠️ **MANUAL — OWNER ONLY. NEVER DISPATCH TO A SUBAGENT.**
> Cette tâche doit être exécutée à la main par l'owner. Même si à un moment elle est marquée `dispatchable: true` par erreur, **aucun agent ne doit la prendre**. Raison : `eas credentials` est un menu interactif qui exige une session EAS authentifiée sur le compte de l'owner. Le résultat à reporter (SHA-1 du keystore) est un input critique pour task-163 — un SHA-1 mal relevé produit un OAuth Client ID invalide, et l'erreur Android côté login Google est laconique (`DEVELOPER_ERROR`), donc pénible à diagnostiquer.

## Context

Phase 5 du V1_LAUNCH_PLAN, étape 4. Cette tâche ne fait **plus** de build : elle se limite à **créer le keystore Android EAS et à en relever le SHA-1**. Le build de l'APK a été déplacé en fin de chaîne, dans task-163, pour n'avoir à le lancer qu'une seule fois.

### Pourquoi ce découpage (décision owner du 2026-08-13)

Le SHA-1 du keystore est requis par Google pour délivrer l'OAuth Client ID Android (task-163). Or `mobile/app.config.ts:114-115` cuit `EXPO_PUBLIC_GOOGLE_CLIENT_ID_ANDROID` dans `extra` **au moment du build** : un binaire construit avant que le Client ID existe embarque `""`, et le bouton « Continue with Google » y est mort quoi qu'on fasse ensuite. L'ancien découpage imposait donc deux builds Android : un pour obtenir le keystore, un second après provisionnement de la variable.

`eas credentials` sait générer un keystore **sans lancer de build**. En le créant seul ici, on obtient le SHA-1 tout de suite, task-163 peut créer le Client ID et renseigner la variable, et le build unique intervient ensuite avec la bonne valeur déjà en place. Un seul build Android au total.

## Prérequis

- task-160 ✅ (prebuild a généré `mobile/android/`)
- `eas-cli` installé, `eas whoami` retourne un compte valide
- Le nom de package est déjà figé : `com.secondbrainlabs.core` (`mobile/app.config.ts:77`)

## Scope manuel

1. `cd mobile && eas credentials --platform android`
2. Sélectionne le profil **`development`** (build profile), puis, dans le menu Android :
   - `Keystore: Manage everything needed to build your project` → `Set up a new keystore` (libellés susceptibles de varier selon la version d'`eas-cli` ; l'objectif est de faire générer un keystore par EAS, pas d'en téléverser un).
   - Laisse EAS générer le keystore (option recommandée), ne fournis pas de `.jks` existant.
3. Toujours dans `eas credentials`, affiche le keystore créé et relève :
   - **SHA-1 certificate fingerprint** (format `AB:CD:EF:…`) — c'est la valeur que consomme task-163
   - **SHA-256** (au cas où Google le demande)
4. Note dans ce ticket le SHA-1, le SHA-256, et l'URL de la page credentials du dashboard EAS.

**Ne lance pas `eas build` dans cette tâche.** Le build unique est l'étape finale de task-163, une fois la variable d'environnement en place.

## Pièges connus

- Le SHA-1 du keystore EAS sera **différent** d'un futur upload key Google Play (Phase 10), qui imposera de créer un 2ᵉ OAuth Client ID Android. Ici c'est bien le SHA-1 EAS qui compte.
- Si le keystore n'apparaît pas immédiatement après création, attends 1-2 min (sync dashboard) puis retry.
- Si `eas credentials` propose de créer le keystore au niveau du projet plutôt que du profil `development`, c'est acceptable : `development`, `preview` et `production` partageront alors la même clé, ce qui est le comportement EAS par défaut et n'invalide pas le SHA-1.

## References

- task-163 — consomme le SHA-1, crée le Client ID, renseigne la variable et lance le build unique
- `docs/V1_LAUNCH_PLAN.md` Phase 5 §4 + section 5
- `mobile/eas.json` profil `development`
- `mobile/app.config.ts:114-115` (la variable est cuite dans `extra` au build)
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 Un keystore Android est créé côté EAS via eas credentials --platform android, sans qu'aucun build n'ait été lancé
- [x] #2 Le SHA-1 du keystore est relevé et noté dans ce ticket au format AB:CD:EF:...
- [x] #3 Le SHA-256 du keystore et l'URL de la page credentials du dashboard EAS sont notés dans ce ticket
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Exécuté le 2026-08-13. Keystore généré par EAS, **aucun build lancé** — le compteur de builds Android reste à zéro, ce qui était l'objectif du découpage.

### Résultat

- **Configuration** : `Build Credentials aRG08ty5Ek` (Default), profil `development`
- **Projet** : `media-summarizer` — Application Identifier `com.secondbrainlabs.core`
- **Key Alias** : `3d6435c18da4d3d15721839b43347b78`
- **SHA-1** : `38:D5:13:F4:2F:A9:DA:74:2F:A1:39:E3:17:9A:22:A8:59:58:DD:FD` ← valeur à coller dans Google Cloud Console (task-163)
- **SHA-256** : `11:1D:A7:DC:72:7B:16:EA:57:BC:54:A0:A3:81:11:BE:13:8E:98:58:F7:E3:6D:87:BF:27:E4:CB:AC:F7:DD:9C`
- **MD5** : `EF:8E:50:0E:B7:44:D6:3D:5B:FF:D3:C3:9F:C2:24:81`
- **Dashboard** : https://expo.dev/accounts/second-brain-labs/projects/media-summarizer/credentials

Ces empreintes sont des données publiques du certificat (elles sont extractibles de tout APK signé et destinées à être déclarées chez Google) — les noter ici ne contrevient pas à la règle « pas de secret dans un fichier suivi ». La clé privée, elle, reste côté EAS et n'a pas été téléchargée.

### Comment ça a été fait

`eas credentials` n'expose aucun mode non interactif : pas de flag `--non-interactive`, pas de sous-commande de lecture, et `CI=""` fait échouer le CLI (`GetEnv.NoBoolean`). Le menu a donc été piloté par un pty (script jetable dans `/tmp`, non versionné), avec une première passe en lecture seule pour confirmer l'état avant toute mutation.

L'état de départ était `No credentials set up yet!` : la création était donc purement additive, sans risque d'écraser une clé existante. Séquence retenue dans le menu : profil `development` → `Keystore: Manage everything needed to build your project` → `Set up a new keystore` → nom par défaut → `Generate a new Android Keystore? yes`. Sortie : `✔ Created keystore` / `✔ Created Android build credentials`.

EAS a rattaché le keystore au profil `development`. `preview` et `production` hériteront de la même clé par défaut, ce qui est le comportement EAS attendu et n'invalide pas le SHA-1 (cf. Pièges connus).

2026-08-13 — statut passé à `Done`. Les 3 critères étaient cochés et le travail consigné (keystore créé via `eas credentials` sans build, SHA-1 et SHA-256 relevés, page credentials EAS notée) depuis le 2026-08-13 ; seul le statut était resté `To Do`. Correction faite lors de la réconciliation de `docs/V1_LAUNCH_PLAN.md`, qui référençait cette tâche comme un reste-à-faire de Phase 5 alors qu'elle n'en était plus un.
<!-- SECTION:NOTES:END -->
