---
id: task-362
title: >-
  Implémenter l'encart « Revue des non classés » de l'accueil selon la maquette
  retenue (task-361)
status: Done
assignee: []
created_date: '2026-09-06 13:41'
updated_date: '2026-09-07 00:00'
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
- [x] #1 `UnsortedReviewButton` de `mobile/app/(tabs)/inbox.tsx` rend la variante désignée par l'owner dans `mobile-design-mockups/home_unsorted_review_card/README.md`, et les notes d'implémentation citent la variante retenue telle qu'elle y est nommée
- [x] #2 L'icône `file-tray-outline` et les styles hérités de la carte Daily Digest ne subsistent plus dans l'encart : le bloc `reviewButton*` est redessiné ou remplacé, sans style mort conservé
- [x] #3 Aucune valeur littérale de couleur, d'espacement ou de rayon n'est introduite : tout vient de `mobile/src/constants/theme.ts`, et la pastille d'icône n'utilise plus de `rgba(...)` écrit en dur
- [x] #4 Le français dit « Revue des non classés » sur `home.unsortedReview` et `unsortedReview.title`, et les chaînes FR voisines parlant de « tri » (`home.unsortedReviewA11y`, `unsortedReview.closeA11y`) sont réalignées sur ce vocabulaire
- [x] #5 Les dix autres catalogues de `mobile/src/i18n/` sont inchangés sur ces clés, et aucune clé n'est ajoutée sans être présente dans les onze
- [x] #6 Le comportement de l'encart est préservé : absent quand le compte vaut 0, `testID` `home-unsorted-review-button` conservé, cible tactile au moins égale à `TouchTarget.comfortable`, `accessibilityLabel` portant toujours le compte
- [x] #7 Le rythme vertical de l'accueil est inchangé : ni `HOME_BLOCK_GAP` ni les marges de section ne sont modifiés, conformément au no-go owner du 2026-09-04 (`docs/testflight-feedback-log.md`, `AE3J09ClZ0T9VY8Jc5SnCRc`)
- [x] #8 `npx tsc --noEmit` et ESLint passent sur les fichiers mobile modifiés
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
## La variante retenue

**F · Layering Principle — « Deck tactile »**, telle qu'elle est nommée dans
`mobile-design-mockups/home_unsorted_review_card/README.md`, section « Choix de
l'owner » (2026-09-07, « Écarts demandés par rapport à la variante : aucun »).
Elle vit dans `code2.html`, le second tour ; A, B et C de `code.html` sont
abandonnées et n'ont pas été consultées pour le rendu.

## Ce que rend l'encart

Trois surfaces décalées, du fond vers l'avant : `surfaceContainerHigh`,
`surfaceContainer`, puis la carte en `surface`. Les deux plaques arrière sont
`position: "absolute"` contre le `Pressable`, et c'est la carte de devant qui
cède la marge par laquelle elles dépassent (`marginEnd: Spacing.xs`,
`marginBottom: Spacing.sm`) — donc aucune plaque ne sort du `Pressable`, rien à
rogner sur Android, et `start`/`end` retournent toute la pile en RTL sans code
supplémentaire. L'ordre de déclaration fait l'ordre de peinture : React Native
peint les frères dans l'ordre de l'arbre, pas par `zIndex`.

Le contenu : `albums-outline` 22 en `textMain` sur une pastille de 48
(`TouchTarget.minimum`) au rayon `BorderRadius.lg` et au fond `Colors.primaryTint`
(les 5 % que prescrit « Signature Textures ») ; le compteur en sticker ambre
accroché au coin bas-fin de cette pastille ; le libellé 16 / 600 sur deux lignes
au plus ; et `chevron-forward` 20 sur un disque `textMain` — les deux corrections
que le second tour de la maquette visait (le compteur redevient le geste au lieu
d'un badge, le chevron quitte l'ambre pâle).

Écart assumé de 8 px avec la maquette : le sticker déborde la pastille de 48 au
lieu d'élargir la colonne de tête à 56. Le débordement reste dans les 16 px de
padding de la carte, il ne touche jamais le bord, et la colonne de tête garde la
largeur que la maquette lui donne — ce qui laisse 8 px de plus au libellé, ce qui
compte à 320 pt pour « Revisão dos não organizados ».

La maquette signale que F est la plus décorative de son tour et que sa pile peut
concurrencer les vraies cartes de média juste dessous. La réponse est dans les
plaques elles-mêmes : ni ombre ni ambre, seulement des paliers tonals du fond, de
sorte que l'encart se lit comme une annonce au-dessus de la liste et non comme une
quatrième tuile dedans.

## Ce qui a disparu

Le bloc `reviewButton*` entier, avec ses trois écarts au design system : le filet
`hairlineWidth` en `outlineVariant` (No-Line Rule), `Shadows.soft` (il était sur
trois des quatre surfaces interactives de l'écran, donc il ne distinguait plus
rien), et `backgroundColor: "rgba(255, 203, 5, 0.1)"` écrit en dur et au double de
l'opacité prescrite. `file-tray-outline` part aussi : c'est le glyphe de l'onglet
même où l'encart se trouve. Ses trois autres sites d'appel (onglet Accueil, état
vide de collection, ligne « Non classés » du sélecteur) sont hors périmètre et
intacts. Aucun style mort n'a été conservé, aucun repli sur l'ancien encart.

## Le token de couleur

`Colors.primaryTint` (`rgba(255, 203, 5, 0.05)`) est ajouté à
`mobile/src/constants/theme.ts`, à côté du `primary` dont il dérive. C'était la
note d'implémentation n° 1 de la maquette : quelle que soit la variante, la valeur
devait devenir un token nommé. Le `40 × 40` magique de l'ancienne pastille devient
`TouchTarget.minimum`, la note n° 2.

## Le français

Quatre chaînes dans `mobile/src/i18n/fr.ts`, aucune clé ajoutée ni supprimée, et
les dix autres catalogues sont intacts (`git diff -- mobile/src/i18n/` ne montre
que `fr.ts`) :

| Clé | Avant | Après |
|---|---|---|
| `home.unsortedReview` | Tri des non classés | **Revue des non classés** |
| `unsortedReview.title` | Tri des non classés | **Revue des non classés** |
| `home.unsortedReviewA11y` | Trier vos médias non classés, {count} | Passer en revue vos médias non classés, {count} |
| `unsortedReview.closeA11y` | Fermer le tri des non classés | Fermer la revue des non classés |

`unsortedReview.doneTitle` (« Plus rien à trier ») est laissé tel quel
volontairement : l'anglais y dit lui-même « Nothing left to sort », donc le
français n'y divergeait pas — il n'y avait rien à réaligner.

## Rythme vertical

Non touché, comme le no-go owner l'exige. `marginHorizontal: Spacing.md` et
`marginTop: HOME_BLOCK_GAP` apparaissent en lignes de contexte inchangées dans le
diff du bloc de styles, `mobile/src/constants/homeRhythm.ts` n'est pas modifié, et
`styles.section` non plus. Seule la hauteur propre de l'encart change (88 pour la
carte + 8 pour la plaque du fond, contre ~80 avant), ce que la maquette classe
explicitement hors « écart entre sections ».

## Vérifications

- `./node_modules/.bin/tsc --noEmit` depuis `mobile/` : aucune sortie.
- ESLint sur `app/(tabs)/inbox.tsx`, `src/constants/theme.ts`, `src/i18n/fr.ts` :
  aucun diagnostic. Le run complet ne laisse que les deux avertissements
  préexistants de `digest.tsx` et `purchaseService.ts`, hors périmètre.
- Aucun test automatisé écrit, conformément à `AGENTS.md`.

## Reste à l'owner

Le rendu visuel de la pile — décalages, contraste des trois paliers, sticker à
quatre chiffres, DE et PT à 320 pt — demande un build sur device, hors de portée
d'un worktree. L'encart n'apparaît qu'avec au moins une source sans collection.
<!-- SECTION:NOTES:END -->
