---
id: task-258
title: >-
  Stop mobile-build-distribute.yml from firing production builds on every push
  to main
status: To Do
assignee: []
created_date: '2026-08-13 18:51'
labels:
  - ci
  - mobile
  - bug
dependencies: []
priority: high
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
`.github/workflows/mobile-build-distribute.yml` est aujourd'hui un workflow qui ne peut que rater, et qui raterait *bruyamment* le jour où il cesserait de rater. Trois défauts cumulés, tous vérifiés le 2026-08-13.

## 1. Tout push sur `main` touchant `mobile/**` déclenche un build ET une soumission store

Le déclencheur mélange branches et tags dans un même bloc `push` :

```yaml
on:
  push:
    branches: [main]
    paths: ["mobile/**", ".github/workflows/mobile-build-distribute.yml"]
    tags: ["mobile-v*"]
```

GitHub applique `branches` aux pushes de branche et `tags` aux pushes de tag : le tag n'est donc pas une condition supplémentaire, c'est un déclencheur **de plus**. Résultat : n'importe quel commit sur `main` qui touche un fichier de `mobile/` lance un build EAS `production` sur les deux plateformes, puis `eas submit` vers TestFlight et Google Play Internal Testing. C'est du quota EAS brûlé et une soumission store involontaire à chaque commit mobile.

L'étape « Determine build profile » aggrave le tableau : ses trois branches `if` / `elif tag` / `else` retournent toutes `production`. Le calcul est mort, il n'y a aucun moyen d'obtenir un build `preview` autrement que par `workflow_dispatch`.

Attendu : un build production/submit ne part **que** sur tag `mobile-v*` ou `workflow_dispatch` explicite. Un push sur `main` ne doit rien construire, ou au plus un build `preview` sans `eas submit` — au choix de l'implémenteur, du moment que le chemin « push sur main → soumission store » disparaît.

## 2. Le job de notification d'échec échoue lui aussi

L'étape « Create GitHub Issue for persistent failures » fait `gh issue create --label "bug,ci/cd"`. Le label `ci/cd` **n'existe pas** dans le dépôt (`gh label list` ne renvoie que les 9 labels GitHub par défaut : `bug`, `documentation`, `duplicate`, `enhancement`, `good first issue`, `help wanted`, `invalid`, `question`, `wontfix`). `gh issue create` échoue sur un label inconnu : le job censé signaler la panne tombe en panne à son tour, et l'échec réel n'est jamais remonté. Le workflow n'a par ailleurs aucun bloc `permissions:`, alors que créer une issue exige `issues: write` sur le `GITHUB_TOKEN`.

## 3. `EXPO_TOKEN` n'est pas provisionné

`gh secret list` renvoie 6 secrets et aucun n'est lié à Expo. Sans `EXPO_TOKEN`, tous les `eas build --non-interactive` du workflow échouent à l'authentification — c'est la cause du `Mobile Build & Distribute | push | failure` du dernier push. Le workflow doit échouer **tôt et lisiblement** dans ce cas au lieu de partir installer Node, `npm ci` et l'EAS CLI pour mourir sur un `eas build` à la douzième étape.

> **Note à l'owner (hors AC, aucun agent ne peut le faire) :** créer le token sur https://expo.dev/settings/access-tokens puis `gh secret set EXPO_TOKEN`. Sans ce secret, le workflow reste non fonctionnel même après cette tâche — celle-ci le rend seulement inoffensif et diagnosticable.

## Défaut adjacent à corriger au passage

`cache-dependency-path: mobile/package.json` dans les deux jobs : `npm ci` lit `mobile/package-lock.json` (présent dans le dépôt). La clé de cache doit pointer sur le lockfile, sinon le cache ne s'invalide pas quand les dépendances résolues changent.

## Vérification

Pas de moyen de déclencher un vrai build depuis un worktree isolé (et il ne faut surtout pas en déclencher un : quota EAS). La vérification passe par la lecture du YAML, `gh label list`, et `actionlint` s'il est disponible.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 Un push sur `main` touchant `mobile/**` ne peut plus déclencher d'`eas submit` : le déclencheur et/ou les conditions de job réservent le couple build production + submit aux tags `mobile-v*` et à `workflow_dispatch`, et le YAML modifié est commenté pour expliciter cette règle
- [ ] #2 L'étape « Determine build profile » ne contient plus de branche morte : soit elle produit réellement des profils différents selon l'événement, soit elle est supprimée au profit d'une valeur unique explicite
- [ ] #3 L'étape « Create GitHub Issue for persistent failures » ne référence plus aucun label absent du dépôt — vérifiable en croisant les labels cités dans le YAML avec la sortie de `gh label list`
- [ ] #4 Le workflow déclare un bloc `permissions:` explicite couvrant au minimum `issues: write` pour le job `notify-failure` (et un `contents: read` par défaut ailleurs)
- [ ] #5 Une garde en tête des jobs de build échoue immédiatement avec un message nommant `EXPO_TOKEN` quand le secret est vide, avant toute installation de Node ou de l'EAS CLI
- [ ] #6 `cache-dependency-path` pointe sur `mobile/package-lock.json` dans les deux jobs de build
- [ ] #7 `actionlint .github/workflows/mobile-build-distribute.yml` passe sans erreur — ou, si `actionlint` n'est pas installable dans le worktree, le fait est noté dans les Implementation Notes et le YAML est validé par `python -c "import yaml,sys; yaml.safe_load(open(...))"`
- [ ] #8 `mobile/MOBILE_CI_CD.md` décrit le nouveau contrat de déclenchement (ce qui part sur tag, ce qui part sur dispatch, ce qui ne part plus sur push) et mentionne `EXPO_TOKEN` comme prérequis owner
<!-- AC:END -->
