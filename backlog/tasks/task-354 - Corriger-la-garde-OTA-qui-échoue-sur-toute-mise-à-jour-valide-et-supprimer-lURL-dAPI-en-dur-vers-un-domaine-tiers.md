---
id: task-354
title: >-
  Corriger la garde OTA qui échoue sur toute mise à jour valide, et supprimer
  l'URL d'API en dur vers un domaine tiers
status: To Do
assignee: []
created_date: '2026-09-04 13:56'
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

Vérification faite contre les serveurs (détail et tableau dans `mobile/MOBILE_CI_CD.md`, section « that grep is a false positive here ») : le manifeste servi sur le canal `internal` porte la bonne URL sur les deux plateformes, zéro occurrence du domaine de repli.

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
- [ ] #1 L'étape de vérification du workflow lit la valeur dans le manifeste de l'update publiée (ou dans l'`extra` résolu de la config exportée), et non par un grep du contenu de `mobile/dist/`
- [ ] #2 La garde reste capable d'échouer : sur une valeur absente ou différente de celle déclarée par le profil `internal` dans `eas.json`, l'étape sort non-zéro — démontré par un essai local du script de l'étape sur une entrée fabriquée
- [ ] #3 `grep -rn 'api.mediasummarizer.com' mobile/ --include=*.ts --include=*.tsx` ne renvoie plus aucun repli en dur dans le code applicatif ni dans `app.config.ts`
- [ ] #4 Une configuration manquante échoue de façon visible au lieu de retomber silencieusement sur un hôte tiers ; le chemin de code correspondant existe et est câblé
<!-- AC:END -->
