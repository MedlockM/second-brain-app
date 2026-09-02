---
id: task-163
title: >-
  Provision the Android Google OAuth Client ID from the EAS keystore SHA-1, then
  run the single Android development build
status: Done
assignee: []
created_date: '2026-06-10 05:38'
updated_date: '2026-09-02 09:42'
labels:
  - phase-5
  - mobile
  - release
  - android
  - auth
dependencies:
  - task-162
  - task-325
priority: high
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

> ⚠️ **Chemin de console mis à jour le 2026-08-13 d'après la doc en ligne.** Google a réorganisé cette zone : « APIs & Services → Credentials » est remplacé par **Google Auth Platform → Clients**, à l'URL directe https://console.cloud.google.com/auth/clients. C'est ce chemin que la doc Google utilise désormais partout (`developers.google.com/identity/protocols/oauth2/native-app`, article support `15544987`). L'ancien chemin peut encore rediriger, mais ne pas s'y fier.

1. Va sur https://console.cloud.google.com/auth/clients → sélectionne le projet `media-summarizer`
2. **Create client** (l'écran Google Auth Platform → Clients)
3. Application type : **Android**
4. Renseigne :
   - **Name** : `Second Brain Android (EAS development)`
   - **Package name** : `com.secondbrainlabs.core`
   - **SHA-1 certificate fingerprint** : `38:D5:13:F4:2F:A9:DA:74:2F:A1:39:E3:17:9A:22:A8:59:58:DD:FD`
     (relevé par task-162 le 2026-08-13 ; à recopier tel quel, deux-points inclus)
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

9. **Déclarer la variable pour le build.** Commande exacte, vérifiée contre `eas-cli/20.1.0` (`eas secret:create` est déprécié, il redirige vers `env`) :
   ```
   cd mobile && npx eas env:create development \
     --name EXPO_PUBLIC_GOOGLE_CLIENT_ID_ANDROID \
     --value <le Client ID> \
     --type string --visibility plaintext --scope project --non-interactive
   ```
   L'environnement `development` est le bon : les cinq autres variables `EXPO_PUBLIC_*` y sont déjà (constaté le 2026-08-13). `plaintext` est cohérent avec elles — un Client ID Android n'est pas un secret d'authentification, il est extractible de tout APK et le préfixe `EXPO_PUBLIC_` le destine au client. L'ajouter au bloc `env` de `eas.json` marcherait aussi, mais mieux vaut rester là où vivent déjà ses cinq sœurs.
10. Vérifier que la variable est bien vue par EAS : `cd mobile && npx eas env:list --environment development` — la ligne `EXPO_PUBLIC_GOOGLE_CLIENT_ID_ANDROID=...` doit apparaître, non vide.
11. **Lancer le build unique** : `cd mobile && npx eas build --platform android --profile development`. Attendre ~10-20 min, puis récupérer l'URL de l'APK et le Build ID sur le dashboard EAS, et installer sur un device physique (`adb install <chemin>.apk` ou QR code). Noter Build ID, URL dashboard et erreurs/warnings éventuels dans ce ticket.

Le keystore existant depuis task-162, EAS ne posera plus de question de signature : le build doit partir sans prompt.

### Vérification à faire au tout début de l'étape 11 — ne pas la sauter

Le profil `development` de `mobile/eas.json` **ne déclare pas de champ `environment`**, et la doc Expo ne spécifie ni la valeur par défaut de ce champ, ni la précédence entre le bloc `env` inline et les variables côté serveur (vérifié le 2026-08-13 sur `/eas/json/`, `/eas/environment-variables/` et sa FAQ — l'ambiguïté est dans la doc, pas dans notre lecture). La FAQ Expo recommande d'ailleurs de **fixer `environment` explicitement** plutôt que de dépendre d'un défaut implicite.

Conséquence concrète : si le build ne se rattache pas à l'environnement `development`, il ne verra **aucune** des six variables serveur — Client ID Android compris — et l'APK repartirait avec `""`. Ce serait le double build qu'on cherche justement à éviter.

Donc, dès les premières lignes de log du build, contrôler qu'EAS annonce bien l'environnement `development` et le chargement des variables. S'il ne l'annonce pas, **interrompre immédiatement** (`Ctrl-C`), ajouter `"environment": "development"` au profil `development` de `mobile/eas.json`, puis relancer. Un build interrompu dans ses premières secondes ne consomme pas de créneau.

### Point annexe constaté, à ne pas traiter ici

`EXPO_PUBLIC_REVENUCAT_GOOGLE_KEY` valait le placeholder `your_revenucat_google_api_key_here` dans les trois environnements EAS, et `mobile/app.config.ts:117` la cuit dans `extra` exactement comme le Client ID. Cette valeur étant *truthy*, elle franchissait le garde `if (!apiKey)` de `mobile/src/services/purchaseService.ts:33` et atteignait `Purchases.configure()` avec une clé invalide. **Réglé en local le 2026-08-20** : `mobile/.env` porte la vraie clé publique `goog_`, l'app Play Store ayant été créée dans le projet RevenueCat. La propagation aux environnements EAS reste à faire (`task-238`, AC#5), et `mobile/eas.json` ne déclare toujours aucune clé RevenueCat.

Ce n'est **pas** bloquant pour ce build : `mobile/src/contexts/PurchasesContext.tsx:75-77` catche l'erreur et la logge. L'app démarre, seul le paywall est inopérant — ce qui est précisément le périmètre de `task-238`. Le build de dev garde donc toute sa valeur pour ce qu'on lui demande : Google Sign-In et le share intent. À savoir simplement pour ne pas s'alarmer du `[PurchasesContext] Failed to initialize RevenueCat` dans les logs.

## Important

- Quand on passera en **Phase 10** (publication Play Store), Google Play générera un **upload key + app signing key** distincts. Il faudra alors créer un **2ᵉ OAuth Client ID Android** avec le SHA-1 du nouveau keystore Play Console. Ce ticket gère uniquement le SHA-1 EAS (dev/preview build). Note cette suite dans le ticket Phase 10 quand on y arrivera. Règle Google : **un client Android par couple (package name, SHA-1)**.
  - **Où lire ce SHA-1, chemin vérifié le 2026-09-01** : Play Console → **Protégé avec Play** → **Distribution Play Store** → **Accéder à la signature d'application Play** → section **Clé de signature de l'application**. L'ancien chemin par *Tester et publier* → *Intégrité des applis* est mort : cette page n'affiche plus qu'un renvoi « Les paramètres d'intégrité de l'appli ont été déplacés ». Si la page liste plusieurs clés (signature hybride post-quantique), chaque empreinte demande son propre client Android.
  - **Ce n'est pas un prérequis documenté de Credential Manager**, contrairement à l'ancien SDK Google Sign-In. Les quatre pages Android (`credential-manager/prerequisites`, `sign-in/credential-manager-siwg`, son guide d'implémentation, son guide de dépannage) ne mentionnent ni client Android ni SHA-1 : elles ne demandent que le **Web** client ID passé à `setServerClientId`, ce que fait déjà `modules/google-credential-manager/.../GoogleCredentialManagerModule.kt:86`. Ce qui est documenté, c'est que Google re-signe l'AAB avec sa propre clé et qu'« il faut enregistrer l'empreinte de la clé de signature détenue par Google auprès de ses fournisseurs d'API, pas seulement la clé d'upload » (OAuth cité explicitement). Donc : builder d'abord, tester le bouton sur le téléphone, et n'ajouter le client Android que si le flow échoue.
- **Le Client ID Android ne sert pas d'`audience`.** Sur Android, le jeton renvoyé par Google porte comme `aud` le **Web** client ID, pas l'Android. C'est cohérent avec notre code : `mobile/src/components/SocialAuthButtons.tsx:47-51` passe les trois (`iosClientId`, `androidClientId`, `webClientId`) à `Google.useAuthRequest`, et le backend vérifie l'`aud` contre `GOOGLE_CLIENT_ID` (le Web). Le client Android existe pour que Google puisse vérifier la signature de l'APK — d'où le SHA-1. Conséquence pratique : ne pas remplacer le Web client ID par l'Android côté backend.
- **`androidClientId` n'est honoré que dans un build natif**, pas dans Expo Go — la doc `expo-auth-session` le qualifie de « for use in production builds and existing React Native projects ». Notre build `development` (`developmentClient: true`, `distribution: internal`) est un build natif : c'est bien le bon véhicule pour tester ce flow.
- La doc `expo-auth-session` marque la config Google **deprecated** et pousse vers `@react-native-google-signin/google-signin` (et Google pousse Credential Manager côté Android, l'ancien SDK Sign-In étant déprécié). Ça ne bloque rien pour V1 — notre implémentation actuelle fonctionne — mais c'est une dette à ouvrir en tâche séparée après le lancement, pas ici.
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
- [x] #1 OAuth Client ID Android créé dans Google Cloud Console avec package com.secondbrainlabs.core et SHA-1 EAS
- [x] #2 EXPO_PUBLIC_GOOGLE_CLIENT_ID_ANDROID rempli dans mobile/.env (dev local)
- [x] #3 docs/V1_LAUNCH_PLAN.md section 5 et Phase 2/5 mis à jour
- [x] #4 bash scripts/mobile_release_check.sh passe sans warning sur EXPO_PUBLIC_GOOGLE_CLIENT_ID_ANDROID
- [x] #5 EXPO_PUBLIC_GOOGLE_CLIENT_ID_ANDROID est déclarée côté EAS (secret projet ou bloc env du profil development de mobile/eas.json) AVANT tout build, et eas env:list / eas secret:list la montre
- [x] #6 Un seul build Android est lancé, après l'étape 5, via eas build --platform android --profile development, et il termine avec succès
- [x] #7 Build ID et URL du build EAS notés dans ce ticket ; l'APK est installé sur un device Android physique et l'app démarre
- [ ] #8 Le bouton Continue with Google est vérifié à la main sur ce build : il ouvre le consentement Google et ne renvoie pas DEVELOPER_ERROR
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
### AC#6 et AC#7 validées le 2026-09-01, avec deux écarts assumés par l'owner

Le build Android existe et l'app tourne sur le téléphone owner. Deux différences avec la lettre des ACs, actées plutôt que corrigées :

- **Deux builds, profil `internal` et non `development`.** L'AC#6 disait « un seul build » pour ménager le quota du free tier EAS ; le budget a été dépensé autrement. Le `versionCode` 4 a dû être jeté parce que les trois environnements EAS portaient encore le placeholder `your_revenucat_google_api_key_here` sur `EXPO_PUBLIC_REVENUCAT_GOOGLE_KEY` et qu'une variable `EXPO_PUBLIC_*` est inlinée à la compilation — le binaire était donc muet côté facturation (voir `task-238`). Le `versionCode` 5 est celui qui compte : build `56771adb-6213-407b-8cd7-ca1b07acf889`, `https://expo.dev/accounts/second-brain-labs/projects/media-summarizer/builds/56771adb-6213-407b-8cd7-ca1b07acf889`.
- **Un AAB installé depuis la piste de test interne Play, pas un APK sideloadé.** Résultat équivalent pour ce que l'AC cherchait à établir — l'app démarre sur un device physique — et supérieur en couverture, puisque le binaire testé est celui que Play resigne et distribue. Il a servi à valider l'AC#6 **et** l'AC#7 de `task-238` le même jour, cycle d'abonnement complet compris.

Il a fallu au passage corriger un défaut qui rendait *tout* build Release Android impossible : `mobile/locales/*.json` étaient plats, Expo recopiait les trois clés iOS dans les ressources Android, et `lintVitalRelease` échouait sur 33 erreurs `ExtraTranslation`.

### AC#8 échoue, et la « dette à ouvrir après le lancement » était en réalité un blocage dur

La section *Important* ci-dessus notait que `expo-auth-session` marque la config Google deprecated, en concluant « ça ne bloque rien pour V1 — notre implémentation actuelle fonctionne ». C'est faux sur Android, et ça n'a jamais fonctionné : le premier essai réel, le 2026-09-01, donne `Error 400: invalid_request` avec la raison `Custom URI scheme is not enabled for your Android client.` Google a retiré le redirect par custom scheme sur Android (« Custom URI schemes are no longer supported on Android and Chrome apps »), or c'est exactement ce que `expo-auth-session` construit. Ce n'est ni un `DEVELOPER_ERROR` ni un problème de SHA-1 : dans un flux navigateur, Google ne vérifie aucune signature d'app.

AC#8 reste donc décochée et cette tâche est bloquée par **`task-325`**, qui remplace ce flux par un module Expo local sur Credential Manager. Rien d'autre ne l'attendait : l'écran de connexion porte un formulaire email/mot de passe, et c'est par là que tout le reste de la validation Android est passé.

### Clôturée le 2026-09-02 avec l'AC#8 non satisfaite, sur décision de l'owner

L'AC#8 (« le bouton Continue with Google est vérifié à la main sur ce build ») est **abandonnée, pas reportée**. Elle demandait de valider, sur le binaire `versionCode` 5, un flux que `task-325` a supprimé le jour même : la vérifier reviendrait à re-constater le `invalid_request` documenté ci-dessus. Le binaire capable de passer ce test n'existe pas encore — il faut un `eas build` postérieur au module Kotlin. Et ce test ne valide plus rien de ce que cette tâche a livré : il valide Credential Manager. Il vit donc dans `task-165` (validation device Android), avec les conditions réelles : second client OAuth Android sur le SHA-1 **Play App Signing**, et échec runtime muet si l'empreinte n'est pas déclarée.

### Trois ACs cochées ici ont été défaites par `task-325` — ne pas s'y fier

`EXPO_PUBLIC_GOOGLE_CLIENT_ID_ANDROID` **n'existe plus dans le dépôt** (vérifié le 2026-09-02 : aucune occurrence dans `mobile/` ni `scripts/`). Credential Manager ne lit aucun Client ID Android côté app — il passe le client **Web** en `serverClientId`. Conséquences sur les ACs ci-dessus :

- **AC#2** — la variable a été retirée de `mobile/.env.example` et n'a plus d'objet en local.
- **AC#4** — la check correspondante de `scripts/mobile_release_check.sh` a disparu avec la machinerie `OPTIONAL_KEYS`, devenue vide.
- **AC#5** — la variable a été retirée des quatre profils de `mobile/eas.json`, ainsi que `extra.googleClientIdAndroid` dans `app.config.ts` et `Config.GOOGLE_CLIENT_ID_ANDROID`.

**AC#1 reste vraie mais insuffisante** : le client OAuth Android créé le 2026-08-13 existe toujours dans Google Cloud, sur le SHA-1 du keystore EAS. Or Credential Manager fait vérifier par Play services le couple *package name + empreinte du binaire installé*, et ce binaire est resigné par Play App Signing. Cette empreinte-là n'est pas déclarée. Un second client Android est nécessaire ; c'est du travail owner, consigné dans les Owner notes de `task-325`.

Ce qui reste durablement acquis de cette tâche, ce sont **l'AC#6 et l'AC#7** : le build Android existe, l'app tourne sur un device physique, et c'est ce binaire qui a permis le cycle d'abonnement Play complet de `task-238` le 2026-09-01.
<!-- SECTION:NOTES:END -->
