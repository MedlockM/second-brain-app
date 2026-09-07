---
id: task-362
title: >-
  Implémenter l'encart « Revue des non classés » de l'accueil selon la maquette
  retenue (task-361)
status: To Do
assignee: []
created_date: '2026-09-06 13:41'
labels:
  - mobile
  - ui
dependencies:
  - task-361
priority: medium
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
## Ce qu'il faut lire d'abord

`mobile-design-mockups/home_unsorted_review_card/README.md` : **la variante retenue par l'owner y est notée, et c'est elle qui fait foi**. La maquette montre le rendu, le README dit pourquoi — et **le README désigne lui-même le fichier à ouvrir** : l'owner a retenu une variante du second tour, qui est dans `code2.html` et non dans `code.html`. `code.html` porte le premier tour (A, B, C), abandonné ; ne pas s'y référer. Ne rien redessiner ici et ne pas préférer une autre variante à celle qui est cochée — si le README ne désigne aucune variante, la tâche s'arrête et le dit, elle ne tranche pas à la place de l'owner.

## Ce que la tâche remplace

`UnsortedReviewButton` dans `mobile/app/(tabs)/inbox.tsx` (composant vers la ligne 371, styles `reviewButton*` vers la ligne 589) est le bouton Daily Digest recyclé — son propre commentaire le dit : « *the style block was renamed, not redrawn* ». Ce bloc de styles hérité et l'icône `file-tray-outline` disparaissent, ils ne sont pas ajustés.

## Le libellé français

Décision owner du 2026-09-06 : **« Revue des non classés »**, sur `home.unsortedReview` et sur `unsortedReview.title` (le titre de l'écran de tri, `mobile/app/media/unsorted-review.tsx`, doit dire la même chose que la porte d'entrée). Le vocabulaire FR voisin suit : `home.unsortedReviewA11y` (« Trier vos médias non classés ») et `unsortedReview.closeA11y` (« Fermer le tri des non classés ») parlent encore de tri.

Les dix autres catalogues ne bougent pas : ils disent déjà « revue » sous une forme ou une autre (EN « Unsorted review », DE « Unsortiertes durchgehen », NL « Ongesorteerd nalopen », IT « Revisione dei non ordinati », PT « Revisão dos não organizados »). Le français était le seul à diverger.

## Cadrage AGENTS.md, « Nothing is deployed yet »

Aucun repli sur l'ancien encart, aucun style conservé « au cas où » : le composant est remplacé, les styles morts supprimés. Rien n'est en circulation qu'on ne puisse réémettre.

## Garde-fou

Le rythme vertical de l'accueil reste tel quel. Le feedback `AE3J09ClZ0T9VY8Jc5SnCRc` est classé `declined` le 2026-09-04 dans `docs/testflight-feedback-log.md` : l'owner a tranché qu'on ne touche pas aux écarts entre sections. `HOME_BLOCK_GAP` et les marges de section ne bougent pas, même si le nouvel encart change de hauteur.

## Notes pour l'owner (pas des ACs)

- La vérification visuelle t'appartient : elle demande un build, que l'agent ne peut pas produire depuis son worktree.
- L'encart reste invisible tant qu'aucun média n'est non classé ; pour le voir, il faut au moins une source sans collection.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 `UnsortedReviewButton` de `mobile/app/(tabs)/inbox.tsx` rend la variante désignée par l'owner dans `mobile-design-mockups/home_unsorted_review_card/README.md`, et les notes d'implémentation citent la variante retenue telle qu'elle y est nommée
- [ ] #2 L'icône `file-tray-outline` et les styles hérités de la carte Daily Digest ne subsistent plus dans l'encart : le bloc `reviewButton*` est redessiné ou remplacé, sans style mort conservé
- [ ] #3 Aucune valeur littérale de couleur, d'espacement ou de rayon n'est introduite : tout vient de `mobile/src/constants/theme.ts`, et la pastille d'icône n'utilise plus de `rgba(...)` écrit en dur
- [ ] #4 Le français dit « Revue des non classés » sur `home.unsortedReview` et `unsortedReview.title`, et les chaînes FR voisines parlant de « tri » (`home.unsortedReviewA11y`, `unsortedReview.closeA11y`) sont réalignées sur ce vocabulaire
- [ ] #5 Les dix autres catalogues de `mobile/src/i18n/` sont inchangés sur ces clés, et aucune clé n'est ajoutée sans être présente dans les onze
- [ ] #6 Le comportement de l'encart est préservé : absent quand le compte vaut 0, `testID` `home-unsorted-review-button` conservé, cible tactile au moins égale à `TouchTarget.comfortable`, `accessibilityLabel` portant toujours le compte
- [ ] #7 Le rythme vertical de l'accueil est inchangé : ni `HOME_BLOCK_GAP` ni les marges de section ne sont modifiés, conformément au no-go owner du 2026-09-04 (`docs/testflight-feedback-log.md`, `AE3J09ClZ0T9VY8Jc5SnCRc`)
- [ ] #8 `npx tsc --noEmit` et ESLint passent sur les fichiers mobile modifiés
<!-- AC:END -->
