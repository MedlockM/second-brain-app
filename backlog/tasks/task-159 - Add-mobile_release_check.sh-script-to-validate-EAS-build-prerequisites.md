---
id: task-159
title: Add mobile_release_check.sh script to validate EAS build prerequisites
status: Done
assignee: []
created_date: '2026-06-10 05:36'
labels:
  - phase-5
  - mobile
  - release
  - tooling
dependencies: []
priority: high
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
## Context

Phase 5 du V1_LAUNCH_PLAN va lancer `eas build --profile development` pour iOS et Android. Avant chaque build, il faut s'assurer que la config locale est saine : `eas.json` parse, `.env` rempli, bundle ID `com.secondbrainlabs.core` intact, version Expo SDK alignée. Aujourd'hui ces vérifications sont manuelles et faciles à oublier (cf. task-119/120/131/132 — bugs config attrapés tard pendant Phase 4).

Ce script préventif les centralise pour qu'on lance `bash scripts/mobile_release_check.sh` avant chaque build et qu'on coupe court à 100% des erreurs config.

## Scope

Crée `scripts/mobile_release_check.sh` qui exécute en séquence :

1. **eas.json valide** : `jq . mobile/eas.json > /dev/null` doit passer
2. **app.config.ts présent** : `test -f mobile/app.config.ts`
3. **.env rempli** : pour chaque clé `EXPO_PUBLIC_*` listée dans `mobile/.env.example`, vérifie qu'elle existe dans `mobile/.env` et n'est pas vide. **Exception** : `EXPO_PUBLIC_GOOGLE_CLIENT_ID_ANDROID` peut rester vide (différé jusqu'à task-163).
4. **Bundle ID intact** : grep `com.secondbrainlabs.core` doit matcher dans `mobile/app.config.ts`, `mobile/eas.json`, `mobile/plugins/withShareExtension.js`, `mobile/ios-share-extension/Info.plist`
5. **Expo SDK version** : lit `mobile/package.json`, affiche la version du package `expo`, warn (sans fail) si != `~52.x`

Code retour 0 si tous les checks passent, 1 sinon. Output coloré (vert / rouge / jaune) pour lecture rapide.

## Hors scope

- Pas de validation runtime (lancer expo / eas) — purement lecture fichiers locaux
- Pas de check des credentials EAS distants (auth, certs) — manuel par l'owner
- Pas de tests automatisés (script bash standalone)

## References

- `docs/V1_LAUNCH_PLAN.md` Phase 5
- `mobile/.env.example` — source de vérité des `EXPO_PUBLIC_*` attendues
- `scripts/dispatch_backlog.sh` — exemple de pattern bash dans le repo (set -euo pipefail, parse args, etc.)
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 bash scripts/mobile_release_check.sh retourne 0 sur HEAD propre
- [ ] #2 Le script échoue avec code 1 si on vide une EXPO_PUBLIC_* requise dans mobile/.env
- [ ] #3 Le script échoue avec code 1 si on altère le bundle ID dans mobile/app.config.ts
- [ ] #4 Le script affiche la version Expo SDK détectée dans mobile/package.json
- [ ] #5 Le script ne crashe pas si EXPO_PUBLIC_GOOGLE_CLIENT_ID_ANDROID est vide (différé Phase 5)
<!-- AC:END -->
