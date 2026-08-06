---
id: task-227
title: >-
  Fix the 20 react-hooks violations in the mobile app and restore the rules to
  error
status: Done
assignee:
  - Codex
created_date: '2026-08-05 18:17'
updated_date: '2026-08-06 01:02'
labels:
  - bug
  - mobile
  - tech-debt
dependencies: []
priority: medium
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
## Contexte

Découvert pendant task-223. Pour rendre `npm run lint` vert, la config ESLint ajoutée (`mobile/.eslintrc.js`) a rétrogradé cinq règles react-hooks de `error` à `warn` :

```js
'react-hooks/exhaustive-deps': 'warn',
'react-hooks/set-state-in-effect': 'warn',
'react-hooks/refs': 'warn',
'react-hooks/purity': 'warn',
'react-hooks/immutability': 'warn',
```

L'agent task-223 a lui-même qualifié ces 20 violations de "real bugs" (commit `5bc3cad`). Ce sont des défauts React authentiques : `set-state-in-effect` provoque des re-renders en cascade, `exhaustive-deps` cause des closures obsolètes et des données périmées à l'écran, `refs` et `immutability` signalent des accès non sûrs.

En l'état, le gate CI ne les voit plus : ils passent en warnings et n'échouent plus le build. Le périmètre de task-223 était le tooling CI, pas le debug applicatif React, d'où cette tâche dédiée.

## Objectif

Corriger les 20 violations puis remettre les règles react-hooks à `error` dans `mobile/.eslintrc.js`, afin que le gate protège à nouveau contre les régressions.

Lancer `cd mobile && npx eslint . --ext .ts,.tsx` pour l'inventaire exact. Attention : `exhaustive-deps` ne se corrige pas en ajoutant aveuglément les dépendances manquantes — chaque cas demande de comprendre l'intention (mémoïser la dépendance, déplacer la logique, ou utiliser une ref) sous peine d'introduire des boucles de rendu.

Contrainte design system : cette tâche touche `mobile/`, donc respecter les conventions "Amber Clarity" et ne modifier aucun rendu visuel — refactor de comportement uniquement, sans changement d'UI.

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 #1 #1 Les 20 violations react-hooks sont corrigées, chacune avec la compréhension de l'intention et non un ajout mécanique de dépendances
- [x] #2 #2 #2 Les cinq règles react-hooks sont remises à error dans mobile/.eslintrc.js
- [x] #3 #3 #3 npm run lint exite 0 avec les règles à error
- [x] #4 #4 #4 npm run typecheck exite toujours 0
- [x] #5 #5 #5 Aucun changement visuel de l'UI : le refactor est purement comportemental
- [x] #6 #6 #6 Vérification manuelle qu'aucune boucle de re-render n'a été introduite sur les écrans touchés
<!-- SECTION:DESCRIPTION:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
1. Remplacer les états initialisables/derivables (langue onboarding, tags, collections, index digest, recherche vide) par des initializers ou des handlers, afin de supprimer les setState synchrones dans les effets.
2. Garder les chargements asynchrones dans les effets mais déplacer leurs mutations d’état après une frontière asynchrone explicite et conserver les gardes d’unmount ; stabiliser les callbacks récursifs d’authentification et de fermeture.
3. Corriger les usages de refs/pureté sans changer le rendu : Animated.Value via initialisation lazy stable, synchronisation pathname dans un effet, horodatage de polling initialisé au démarrage effectif.
4. Remettre les cinq règles react-hooks à error, exécuter lint et typecheck, puis relire chaque effet touché pour vérifier dépendances, cleanup et absence de boucle de rendu.
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Implémentation terminée :
- Correction des violations set-state-in-effect en séparant les déclencheurs événementiels, les initialisations lazy et les callbacks asynchrones planifiés avec cleanup.
- Correction des violations refs/purity : Animated.Value est initialisé de façon stable, pathnameRef est synchronisé dans un effet, Date.now() n’est plus exécuté pendant le rendu.
- Les callbacks récursifs/anté-déclarés d’auth et de share confirmation sont stabilisés ; les suppressions exhaustive-deps ont été retirées du polling.
- Les cinq règles react-hooks sont revenues à error.
- Aucun style, libellé ou structure visuelle n’a été modifié.

Validation :
- npm run lint : exit 0, aucune violation react-hooks (10 warnings TypeScript préexistants restent non bloquants).
- npm run typecheck : exit 0.
- git diff --check : exit 0.
- Relecture manuelle des dépendances/cleanup des effets touchés : aucune dépendance modifiée par l’effet lui-même, timers annulés au cleanup, donc aucune boucle de re-render introduite.
<!-- SECTION:NOTES:END -->

<!-- AC:END -->

<!-- AC:END -->
