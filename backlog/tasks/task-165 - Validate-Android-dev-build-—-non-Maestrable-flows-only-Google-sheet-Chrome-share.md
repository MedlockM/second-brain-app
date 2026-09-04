---
id: task-165
title: >-
  Validate Android dev build — non-Maestrable flows only (Google sheet, Chrome
  share)
status: To Do
assignee: []
created_date: '2026-06-10 05:39'
updated_date: '2026-09-04 10:45'
labels:
  - phase-5
  - mobile
  - release
  - android
  - validation
dependencies:
  - task-162
  - task-163
  - task-338
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

- task-162 ✅ (keystore EAS créé, SHA-1 relevé)
- task-163 ✅ (Google OAuth Client ID Android provisionné, variable déclarée côté EAS, build unique lancé et APK installé sur device)
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
- [x] #1 Continue with Google crée/lie un user Android et atterrit sur l'inbox (sans DEVELOPER_ERROR)
- [x] #2 Bouton Sign in with Apple soit absent soit no-op clean sur Android
- [x] #3 Share intent depuis Chrome (URL) atteint share-confirm, soumet, et la vignette apparaît dans l'inbox
- [x] #4 Share intent texte ou audio depuis app native fonctionne
- [ ] #5 Tous les bugs P0/P1 détectés ont un sous-ticket et sont résolus avant clôture
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
### AC#1 et AC#2 validées le 2026-09-02 (owner), sur le `versionCode` 6

**AC#1 — Continue with Google fonctionne sur Android.** Le libellé de la vérif 1 ci-dessus était périmé : il parlait de `DEVELOPER_ERROR` et du SHA-1 du keystore EAS, or le flux a changé le 2026-09-01 (`task-325`) — Android passe désormais par **Credential Manager** via le module Expo local `mobile/modules/google-credential-manager`, avec le client **Web** en `serverClientId`. Le binaire qui valide cette AC est donc le `versionCode` 6, pas celui de `task-163` :

- build EAS `a04c9c46-4b28-4a56-9a1a-c99213fee1b0`, profil `internal`, commit `ca9cadb` — le commit immédiatement postérieur au merge de `task-325` (`16c6cd9`), donc le module Kotlin est bien dans l'AAB ;
- installé depuis la piste de test interne Play ;
- preuve côté backend : `POST /api/auth/google/native 200` dans `/aws/lambda/media-summarizer-api-dev` à `2026-09-01T20:58:17Z`, pour l'utilisateur `039ea8cf`. C'est une **connexion** à un compte `google` préexistant (créé le 2026-08-19), pas une inscription : aucune ligne nouvelle dans `users-dev`, ce qui est le comportement attendu.

Première exécution réussie de Credential Manager, et première connexion Google réussie sur Android tout court.

**AC#2 — pas de bouton Apple sur Android.** Vrai par construction, lisible dans le code sans device : `mobile/src/components/SocialAuthButtons.tsx:156` conditionne le rendu à `Platform.OS === "ios"`.

### AC#3 et AC#4 validées le 2026-09-02 (owner), sur le même `versionCode` 6

Aucun nouveau build n'a été nécessaire : les deux filtres utiles étaient déjà dans le binaire installé. Testé à la main sur device physique Android :

- **AC#3** — article ouvert dans Chrome → ⋮ → Partager → Second Brain → share-confirm → submit : fonctionne.
- **AC#4** — fichier MP3 partagé depuis une app native vers Second Brain : fonctionne.

Ce sont les deux seuls types que le manifest expose. `mobile/app.config.ts:188-199` déclare `text/plain` (ce que Chrome envoie pour une URL) et `audio/*`.

### Écart relevé le 2026-09-02, hors périmètre de cette tâche : le partage entrant n'accepte ni document ni image

Constaté par l'owner en tentant de partager un PDF : **Second Brain n'apparaît pas dans la feuille de partage Android.** Deux causes indépendantes, les deux à corriger, dans cet ordre.

**1. Le manifest ne déclare aucun `mimeType` document ni image.** Le manifest final porte trois filtres `SEND`, pas deux — parce que le plugin en ajoute un que le dépôt ne configure pas :

| Origine | Filtre `SEND` |
| --- | --- |
| `android.intentFilters` (`app.config.ts:188-199`) | `text/plain` |
| `android.intentFilters` | `audio/*` |
| plugin `expo-share-intent`, **valeur par défaut** | `text/*` |

Le plugin est instancié sans `androidIntentFilters` (`app.config.ts:212-222`), donc `withAndroidIntentFilters.js:51` retombe sur son défaut `["text/*"]`. Rien ne matche `application/pdf`, ni les MIME Office, ni `image/*` — alors que `task-264` a fait de la capture caméra un point d'entrée d'ingestion. Le fix propre passe par l'option `androidIntentFilters` du plugin plutôt que par `android.intentFilters`, ce qui supprime au passage le doublon `text/*` / `text/plain`.

**2. Même avec le filtre, le handler rejetterait le fichier.** `mobile/src/contexts/ShareIntentContext.tsx:316-345` ne route que `mimeType?.startsWith("audio/")` ; tout autre fichier tombe dans la branche `share.unsupportedFile` (« This file type is not supported yet. »). Lisible sur iOS sans device Android : `NSExtensionActivationSupportsFileWithMaxCount: 1` y fait bien apparaître l'app pour un PDF, et le partage échoue ensuite sur ce message.

Le PDF est pourtant une cible d'ingestion supportée (`mobile/src/types/upload.ts:57`, `mobile/src/services/uploadService.ts:54`) — mais uniquement par le picker interne (Add source → Import file), jamais par le partage entrant.

**Enjeu commercial** : le copy vendu au paywall promet le contraire. `mobile/src/i18n/en.ts:271` — « Save from any app: YouTube, podcasts, TikTok, Instagram, X, articles, PDFs, documents, photos and audio files », décliné dans les 10 locales. Sur Android l'app n'apparaît même pas ; sur iOS elle apparaît et refuse.

**Tranché par l'owner le 2026-09-02 : P1 bloquant.** Sous-ticket `task-338`, ajouté aux dépendances de cette tâche. AC#5 ne peut donc pas être cochée avant que `task-338` soit résolue *et* vérifiée sur device — ce qui exige un nouveau build EAS, contrairement à AC#3 et AC#4 : un changement d'intent filter vit dans le manifest.

### Session de test du 2026-09-04 : AC#5 reste ouverte, le partage de fichier échoue encore

L'owner a rejoué le check device de `task-338` sur le binaire installé, le `versionCode` **8** (commit `50ad6f5`). Deux symptômes, une cause dominante, plus un vrai bug backend révélé au passage.

**Ce que les logs prouvent.** `/aws/lambda/media-summarizer-api-dev` porte exactement trois `POST /api/media/upload` entre 08:18 et 08:21 UTC, tous trois en **500**, chacun précédé d'un `api.validation_error` (`validation_error_count: 1`) puis d'une `Unhandled exception` de type **`UnicodeDecodeError`**. Aucun `POST /api/media/upload-url` sur la journée.

**1. Le binaire est plus vieux que le contrat d'API — cause suffisante des deux symptômes.** `task-345` (merge `57b3c9e`, 2026-09-03) a sorti les octets de l'API : le client demande une URL presignée à `POST /api/media/upload-url`, PUT sur S3, puis poste du JSON `{upload_key, folder_id, tag_ids}`. Le `versionCode` 8 est antérieur (`git merge-base --is-ancestor 57b3c9e 50ad6f5` → faux) : il poste encore du multipart, que l'endpoint refuse. D'où l'absence totale d'appel à `upload-url` dans les logs. **Tout partage de document ou d'image depuis ce binaire échoue, quelle que soit l'app source.**

Le `versionCode` **9** (commit `519d8ba`) porte `task-345` et a bien terminé sur EAS le 2026-09-03T12:07:31Z — mais il n'est jamais arrivé sur la piste interne : sa soumission Play a échoué (relevé le 2026-09-04, `SUBMISSION_SERVICE_ANDROID_UNKNOWN_ERROR`, « Fastlane supply failed »). Le device est donc resté sur 8. C'est ce qui explique l'asymétrie avec iOS, dont le build `1.0.0 (4)` — même commit — a été livré : `task-164` est passée.

**2. Le cas Drive a en plus un problème de nom de fichier, corrigé par `task-347` et présent dans aucun build.** Drive partage un `content://` dont le `DISPLAY_NAME` ne porte pas toujours d'extension exploitable. `classifyUploadFile` n'a que l'extension comme discriminant, donc l'intake tombe en `status: "invalid"` **pendant la validation**, avant tout appui sur Enregistrer — ce qui correspond au « l'erreur apparaît dès que le modal s'ouvre ». `resolveUploadFileName` (`mobile/src/types/upload.ts:221`, `task-347`, commit `da55059`) récupère l'extension depuis le `path` puis depuis le `mimeType` ; il n'est **ni dans le 8 ni dans le 9** (`git merge-base --is-ancestor da55059 519d8ba` → faux).

À noter pour la lecture des symptômes : `status: "invalid"` affiche « Impossible d'enregistrer ce contenu » et `status: "error"` « Échec de l'enregistrement » (`mobile/app/share-confirmation.tsx:287` et `:449`). Les deux titres se ressemblent à l'usage, mais seul le second implique qu'une requête a été envoyée.

**3. Bug backend réel, corrigé dans la même session.** Le 500 n'était pas le refus de validation : c'était le handler censé répondre 422 qui mourait. `jsonable_encoder` encode les `bytes` avec un `o.decode()` nu (`fastapi/encoders.py:59`), or Pydantic met le corps multipart brut dans `input` — un PDF ou un JPEG lève `UnicodeDecodeError` **à l'intérieur** de `validation_exception_handler`. Conséquence : le client recevait un 500 opaque au lieu du seul message utile, que `upload_key` manquait. `_renderable_value` dans `media_summarizer/api/error_handling.py` neutralise désormais bytes, exceptions et chaînes trop longues, récursivement, avec un dernier recours qui conserve `loc`/`msg`/`type`. Même famille de bug que celui déjà rencontré sur `POST /api/artifacts` via `ctx["error"]`.

### Reste à faire pour clore cette tâche

AC#5 seule, et elle ne demande pas de rejouer AC#1 à AC#4. Il faut un binaire qui porte **à la fois** `task-345` et `task-347`, puis le check device des Owner notes de `task-338` : PDF depuis « Mes fichiers », photo et PDF depuis Drive, et un `.zip` pour vérifier que le refus reste propre.

**Un nouveau build native est obligatoire — l'OTA ne peut pas servir de raccourci**, bien que les deux correctifs client soient du JS pur. Mesuré le 2026-09-04 :

- le `versionCode` **8**, celui installé, n'a **ni `runtimeVersion` ni canal** côté EAS : il est antérieur à `task-340`, donc son binaire ne porte pas `updates.url` et ne demandera jamais de bundle à personne ;
- le `versionCode` **9** est bien à jour d'EAS Update (runtime `e53f6e78…`, canal `internal`), mais le fingerprint natif de `HEAD` vaut `e9ba0880…` en Android et `819da548…` en iOS, et **aucun** build `internal` terminé ne porte l'un ou l'autre (`eas build:list --fingerprint-hash` → 0 des deux côtés). `mobile/app.config.ts` et `mobile/package.json` ont bougé depuis `519d8ba` — revendication des images dans la feuille de partage iOS (`4d6951b`), suppression de l'extension de partage écrite à la main (`8450448`), et le matériau Liquid Glass (`task-350`, `task-351`). La politique `fingerprint` d'`app.config.ts:144` refuse par construction de servir ce bundle aux binaires existants.

**Le build et la soumission ne demandent aucune action manuelle** : `mobile-ota-or-build.yml` se déclenche au push sur `main` dès qu'un fichier `mobile/**` hors `.md` et hors `.maestro/` change, décide par plateforme, et sur route `build` lance `eas build --profile internal --auto-submit` — TestFlight et la piste `internal` de Play. Le seul angle mort est la **soumission** : `--no-wait` rend le run vert immédiatement, `mobile-build-watch.yml` ne surveille que `--status errored` des *builds*, donc un échec de soumission comme celui du `versionCode` 9 n'ouvre aucune issue et ne se voit qu'en consultant EAS.

### Question SHA-1 — tranchée (fait owner relevé le 2026-09-02)

La doc avait raison : Credential Manager fait vérifier par Play services le couple *package name + empreinte du binaire installé*, qui est celle de **Play App Signing** et non du keystore EAS. L'owner a déclaré un **second client OAuth Android** sur le SHA-1 de Play (même `package=com.secondbrainlabs.core`). Il était donc en place **au plus tard le 2026-09-01T20:58** — date du `POST /api/auth/google/native 200` qui valide AC#1 ci-dessus, obtenu depuis un binaire installé par Play, ce qui n'aurait pas pu aboutir sans lui.

Les deux clients coexistent et aucun n'est redondant : celui du keystore EAS (`task-163` AC#1) couvre les APK posés à la main, celui de Play couvre tout binaire servi par Play. Aucun des deux n'entre dans le bundle — `task-325` a supprimé `EXPO_PUBLIC_GOOGLE_CLIENT_ID_ANDROID`, l'app ne passe que le client **Web** en `serverClientId`. Rien à rejouer pour la production : le certificat Play App Signing est le même sur la piste interne, le closed testing et la production.

Il n'y a donc plus de réserve sur AC#1, et le « second client Android » qui figurait comme travail owner restant dans les Owner notes de `task-325` est clos.
<!-- SECTION:NOTES:END -->
