---
id: task-354
title: >-
  Corriger la garde OTA qui échoue sur toute mise à jour valide, et supprimer
  l'URL d'API en dur vers un domaine tiers
status: Done
assignee: []
created_date: '2026-09-04 13:56'
updated_date: '2026-09-04 14:40'
labels:
  - mobile
  - ci
  - bug
dependencies: []
priority: high
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
## Le fait

L'étape `Verify the published bundle inlined the API base URL` de `.github/workflows/mobile-ota-or-build.yml` fait échouer le workflow sur **toute** OTA, y compris une OTA parfaitement valide. Constaté le 2026-09-04 : première OTA réellement publiée par ce workflow, échec sur iOS et Android, deux fois de suite, alors que les manifestes servis aux appareils étaient corrects.

La garde `grep -raqF "${EXPO_PUBLIC_API_BASE_URL}" dist/` repose sur une prémisse fausse pour ce projet : elle suppose que la valeur est inlinée dans le bundle JS. Or aucun fichier applicatif ne déréférence `process.env.EXPO_PUBLIC_API_BASE_URL` — le seul lecteur est `app.config.ts:312`, au moment de la config, qui dépose la valeur dans `extra.apiBaseUrl` ; l'app lit `extra.apiBaseUrl` (`src/constants/config.ts:10`). La valeur voyage donc dans le **manifeste**, jamais dans `mobile/dist/`. Le bundler n'a aucune raison de l'inliner, et ne le fait pas.

Vérification faite contre les serveurs (détail et tableau dans `mobile/MOBILE_CI_CD.md`, section « The guard reads the served manifest, not `mobile/dist/` ») : le manifeste servi sur le canal `internal` porte la bonne URL sur les deux plateformes, zéro occurrence du domaine de repli.

Conséquence : chaque push JS-only rend le workflow rouge **après** avoir publié une mise à jour saine. Une alarme qui se déclenche toujours est une alarme qu'on cesse de lire — et c'est le seul signal censé dire « arrête tout » sur le chemin d'expédition.

## Le second défaut, dans le même périmètre

L'URL de repli est **`https://api.mediasummarizer.com`**, en dur à deux endroits : `mobile/app.config.ts:313` et `mobile/src/constants/config.ts:10`. Ce domaine n'appartient pas au projet (cf. `AGENTS.md` / la note « aucun domaine n'est possédé »). Un repli silencieux vers un domaine tiers n'est pas une valeur par défaut inoffensive : si la variable venait à manquer, l'app enverrait ses requêtes authentifiées — jetons compris — vers un hôte contrôlé par quelqu'un d'autre. Une absence de configuration doit être bruyante, pas discrète.

## Ce qui est attendu

Deux choses, dans le même run :

1. La garde vérifie la valeur **là où elle vit réellement** — le manifeste de l'update, ou l'`extra` résolu de la config exportée — et non le contenu de `dist/`. Elle doit être capable d'échouer : une valeur absente ou différente de celle du profil `internal` fait toujours échouer le run.
2. Les deux replis en dur vers le domaine tiers disparaissent. Une configuration manquante doit échouer visiblement plutôt que pointer ailleurs.

Rappel de cadrage (`AGENTS.md`, « Nothing is deployed yet ») : rien n'est en production, aucun contrat à préserver. Pas de repli de compatibilité conservé « au cas où ».

## Notes pour l'owner (pas des ACs)

- L'environnement EAS `production` définit désormais `EXPO_PUBLIC_API_BASE_URL` (ajouté le 2026-09-04 pour chasser ce faux positif ; il ne corrigeait rien). Il rompt l'invariant « aucune clé des deux côtés » documenté dans `MOBILE_CI_CD.md` et fait diverger build et update sur le canal `production`. Sans effet aujourd'hui, ce canal ne servant personne. La suppression et son chemin exact sont dans `MOBILE_CI_CD.md`.
- La validation finale du correctif de garde est un push réel sur `main` : le workflow doit être vert sur une OTA saine. Cela vous revient, après merge.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 L'étape de vérification du workflow lit la valeur dans le manifeste de l'update publiée (ou dans l'`extra` résolu de la config exportée), et non par un grep du contenu de `mobile/dist/`
- [x] #2 La garde reste capable d'échouer : sur une valeur absente ou différente de celle déclarée par le profil `internal` dans `eas.json`, l'étape sort non-zéro — démontré par un essai local du script de l'étape sur une entrée fabriquée
- [x] #3 `grep -rn 'api.mediasummarizer.com' mobile/ --include=*.ts --include=*.tsx` ne renvoie plus aucun repli en dur dans le code applicatif ni dans `app.config.ts`
- [x] #4 Une configuration manquante échoue de façon visible au lieu de retomber silencieusement sur un hôte tiers ; le chemin de code correspondant existe et est câblé
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
### Où vit réellement la valeur (AC #1)

`Constants.expoConfig` **est** `manifest.extra.expoClient` (`node_modules/expo-constants/build/Constants.js`). Le chemin exact que l'app lit est donc `manifest.extra.expoClient.extra.apiBaseUrl` — et c'est celui que la garde interroge.

Nouveau script `scripts/mobile_ota_manifest_check.sh`, appelé par l'étape `Verify the served manifest carries the internal API base URL` de `.github/workflows/mobile-ota-or-build.yml` (l'ancien `grep -raqF … dist/` est supprimé, pas conservé) :

```
--profile <name> --platform <ios|android> --runtime-version <hash>
   [--project-id <uuid>] [--attempts <n>]     # interroge u.expo.dev
--profile <name> --platform <ios|android> --manifest-file <path>   # hors-ligne
```

Il lit `build.<profile>.env.EXPO_PUBLIC_API_BASE_URL` et `build.<profile>.channel` dans `eas.json` (en suivant `extends`), résout le project id depuis la config exportée (`npx expo config --type public --json`, jamais un UUID recopié), puis `GET https://u.expo.dev/<projectId>` avec les en-têtes `expo-platform` / `expo-channel-name` / `expo-runtime-version`.

Deux faits mesurés le 2026-09-04, tous deux dans l'en-tête du script :

- la réponse est `multipart/mixed` **même sans en-tête de version de protocole** : parties `manifest` et `extensions` délimitées par CRLF, chacune une ligne de JSON compact. L'extracteur accepte aussi un corps JSON nu, ce qui rend `--manifest-file` utilisable sur une capture ou une entrée fabriquée ;
- la version de runtime à demander est le **hash d'empreinte native** déjà calculé par le workflow : `runtimeVersion: { policy: "fingerprint" }` fait des deux la même chaîne. Vérifié contre les manifestes servis pour les deux empreintes du run `33879183625`.

Cette égalité est aussi ce qui fait que la garde attrape le piège de précédence documenté dans `MOBILE_CI_CD.md` : `extra` participe à l'empreinte (`@expo/fingerprint` ne l'écarte que sous `SourceSkips.ExpoConfigExtraSection`, que rien ne pose ici), donc un `eas update` qui résoudrait une autre URL publie sous une **autre** version de runtime — et demander l'empreinte du profil revient alors en 404, ce que le script traite comme un échec en nommant l'override d'environnement EAS comme cause probable.

### La garde échoue toujours (AC #2)

Toutes ces exécutions sont locales, sur le vrai serveur d'update ou sur des entrées fabriquées à partir de la capture réelle du canal `internal` (update `01a06cb1-0b08-73f5-850d-b3a8aa77be06`, runtime `c1dcf637…6982252`) :

| Entrée | Résultat |
|---|---|
| Manifeste réellement servi (ios, runtime `c1dcf637…`) — celui que l'ancien grep faisait échouer | **exit 0** |
| Idem android (`24f20990…907b859`) | **exit 0** |
| Corps multipart fabriqué, URL remplacée par `https://api.mediasummarizer.com` | **exit 1**, « points the app at another host than profile 'internal' declares » + les deux commandes de rollback |
| JSON nu fabriqué, `extra.expoClient.extra.apiBaseUrl` **supprimée** | **exit 1**, « carries no extra.expoClient.extra.apiBaseUrl » |
| JSON nu fabriqué, valeur correcte (contrôle) | **exit 0** |
| Runtime `deadbeef…` (divergence d'empreinte simulée), `--attempts 1` | **exit 1** sur HTTP 404, avec l'explication de divergence |
| Profil inconnu / `development` et `development-simulator` (aucun canal) | **exit 1** — prouve aussi que `extends` est suivi |

### Plus aucun repli vers un domaine tiers (AC #3, #4)

`grep -rn 'api.mediasummarizer.com' mobile/ --include=*.ts --include=*.tsx` → **exit 1, aucune correspondance**.

Deux couches bruyantes remplacent les deux replis :

- `mobile/app.config.ts` lève si `EXPO_PUBLIC_API_BASE_URL` est vide, donc la **résolution de config** échoue : aucun bundle, aucun build, aucune update ne peut être produit sans la variable. Vérifié : `npx expo config --type public` sans la variable sort en 1, stdout vide, message explicite sur stderr. Avec la variable, `extra.apiBaseUrl`, le project id et `updates.url` sortent normalement ;
- `mobile/src/constants/config.ts` lève au démarrage si un manifeste arrivait malgré tout sans `extra.apiBaseUrl`, au lieu de pointer ailleurs.

`https://api.mediasummarizer.com` **reste** la valeur déclarée du profil `production` dans `eas.json`, volontairement : c'est une cible déclarée et bloquée par le contrôle DNS de `scripts/mobile_release_check.sh`, pas un repli silencieux. `mobile/src/constants/legal.ts` garde ses URLs CGU/confidentialité sur ce domaine — hors périmètre de cette tâche.

### Vérifications

`npm run typecheck` exit 0. `npm run lint` : 0 erreur, 2 avertissements pré-existants sur des fichiers non touchés (`app/(tabs)/digest.tsx`, `src/services/purchaseService.ts`). `bash -n` propre sur les deux scripts. `bash scripts/mobile_release_check.sh internal` → tous les contrôles passent, bundle ID `com.secondbrainlabs.core` intact. Le workflow parse en YAML.

### Ce qui reste à l'owner

Non couvert par un AC, par construction : la validation finale est un push réel sur `main` (le workflow doit être vert sur une OTA saine) — le déploiement se déclenche après la sortie de l'implémenteur. Et la suppression de `EXPO_PUBLIC_API_BASE_URL` de l'environnement EAS `production`, dont le chemin exact est dans `MOBILE_CI_CD.md`.
<!-- SECTION:NOTES:END -->
