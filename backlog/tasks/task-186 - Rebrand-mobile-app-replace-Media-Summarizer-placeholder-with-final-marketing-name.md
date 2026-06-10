---
id: task-186
title: >-
  Rebrand mobile app: replace "Media Summarizer" placeholder with final
  marketing name
status: To Do
assignee: []
created_date: '2026-06-10 18:51'
labels:
  - mobile
  - release
  - branding
  - phase-10
dependencies: []
priority: high
dispatchable: false
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
## Description

L'app utilise actuellement le nom legacy **« Media Summarizer »** comme placeholder partout (display name, slug Expo, scheme deep link, share extension). Le nom marketing définitif n'est pas encore décidé. Quand il le sera, appliquer le rename **avant la première soumission App Store / Play Store** (Phase 10 du V1_LAUNCH_PLAN) — coût ~30 min en pré-distribution, beaucoup plus élevé après.

## Contexte

- L'entité légale est `Second Brain Labs`. Le bundle id `com.secondbrainlabs.core` est figé et **ne change pas** lors du rebrand.
- Un premier benchmark (task-115) avait recommandé "Percole", rejeté par l'owner. La task est completed et toutes ses traces ont été purgées (commit `9db3a21`).
- Le nom marketing définitif doit être trouvé séparément — quand l'owner aura statué, lancer cette tâche.

## Pré-requis

- Nom marketing définitif décidé par l'owner (pas de benchmark à relancer ici — la décision est un input).
- Aucun build distribué publiquement (App Store / Play Store) pour le moment ; sinon le scope grandit (gérer l'ancien scheme en plus pendant 1-2 versions).

## Scope manuel

Remplacer **8 endroits** dans le repo + 1 endroit côté Expo dashboard :

1. `mobile/app.config.ts:5` — `name: "Media Summarizer"` → `name: "<NomDef>"` (display name iOS/Android sous l'icône)
2. `mobile/app.config.ts:6` — `slug: "media-summarizer"` → `slug: "<nom-def>"` (URL Expo dashboard, kebab-case)
3. `mobile/app.config.ts:11` — `scheme: "media-summarizer"` → `scheme: "<nom-def>"` (deep link URL scheme)
4. `mobile/plugins/withShareExtension.js:28,33` — la string `"media-summarizer"` aux deux occurrences (CFBundleURLSchemes du Info.plist iOS + check d'idempotence)
5. `mobile/ios-share-extension/Info.plist:8` — `<string>Share to Media Summarizer</string>` → `Share to <NomDef>` (label dans le iOS Share Sheet)
6. `mobile/src/contexts/ShareIntentContext.tsx:265,302` — handlers `media-summarizer://` aux deux occurrences (URL handling JS)
7. `mobile/src/hooks/useShareIntent.ts:112-113` — `media-summarizer://` (parsing input + check préfixe)
8. `mobile/package.json:2` — `"name": "media-summarizer-mobile"` → `"<nom-def>-mobile"` (purement interne npm, optionnel mais propre)
9. **Côté Expo dashboard** : Settings du projet → renommer le slug pour qu'il matche `app.config.ts:6`. L'`expo.projectId` (UUID) reste le même — c'est le contrat de fait, le slug est un alias lisible.

## Vérifications après rebrand

- `cd mobile && npm run typecheck` doit passer.
- `cd mobile && npx expo prebuild --clean` doit régénérer le natif sans erreur.
- `bash scripts/mobile_release_check.sh` doit passer (pas de régression sur le bundle id check).
- `grep -rn "media-summarizer\|Media Summarizer" mobile/ --include="*.ts" --include="*.tsx" --include="*.json" --include="*.js" --include="*.plist" | grep -v node_modules | grep -v "/ios/" | grep -v "/android/" | grep -v "package-lock"` doit retourner 0 résultat hors auto-générés.

## Ce qui ne change PAS lors du rebrand

- `bundleIdentifier` iOS / `package` Android (`com.secondbrainlabs.core`) — figé. Donc Apple Developer / Google Cloud Console / RevenueCat / OAuth client IDs / share extension App Group ne sont pas impactés.
- `expo.projectId` UUID — reste identique, c'est l'identifiant stable côté EAS.
- Backend API (FastAPI, AWS) — aucune référence au nom marketing, rien à toucher.

## References

- `docs/V1_LAUNCH_PLAN.md` Phase 10 (à exécuter **avant** la sous-étape 1 « Apple App Store Connect → App Information »)
- `mobile/app.config.ts` (source de vérité name + slug + scheme)
- `mobile/plugins/withShareExtension.js` (plugin custom App Groups + URL scheme)

## Pourquoi MANUAL OWNER ONLY

Cette tâche dépend d'une décision business (le nom marketing définitif) qui n'est pas dans le repo. Un agent ne peut pas inventer ou choisir le nom — c'est l'owner qui statue. Une fois le nom décidé, l'application des 8-9 changements peut être assistée par un agent, mais le déclenchement et la validation finale restent owner-only.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 Le nom marketing définitif est noté dans cette tache (champ Decision) avant tout rename
- [ ] #2 mobile/app.config.ts (name, slug, scheme) alignés sur le nouveau nom
- [ ] #3 mobile/plugins/withShareExtension.js et mobile/ios-share-extension/Info.plist cohérents
- [ ] #4 mobile/src/contexts/ShareIntentContext.tsx et mobile/src/hooks/useShareIntent.ts utilisent le nouveau scheme
- [ ] #5 mobile/package.json name est aligné (optionnel mais propre)
- [ ] #6 npm run typecheck et expo prebuild --clean passent
- [ ] #7 Slug renommé côté Expo dashboard (project ID UUID inchangé)
- [ ] #8 Aucune occurrence résiduelle de 'Media Summarizer' ou 'media-summarizer' hors fichiers auto-générés (ios/, android/, package-lock)
<!-- AC:END -->
