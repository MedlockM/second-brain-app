---
id: task-361
title: Maquetter le nouvel encart « Revue des non classés » de l'accueil
status: To Do
assignee: []
created_date: '2026-09-06 13:40'
labels:
  - mobile
  - ui
  - design
dependencies: []
priority: medium
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
## Ce que l'owner reproche à l'encart actuel (2026-09-06)

L'encart d'entrée dans le tri des médias non classés, en haut de l'accueil, ne tient pas le standing du reste de l'app : **l'icône fait vieillotte et enfantine**, **la formulation « Tri des non classés » manque d'allure**, et **l'ensemble de l'encart est à revoir**, pas seulement retouché.

## État actuel, mesuré

`UnsortedReviewButton`, `mobile/app/(tabs)/inbox.tsx` (composant vers la ligne 371, styles `reviewButton*` vers la ligne 589) :

- icône Ionicons **`file-tray-outline`** en 22px, dans une pastille 40×40 remplie de `rgba(255, 203, 5, 0.1)` — une valeur littérale, pas un token ;
- libellé 16px/700 sur deux lignes maximum, puis un badge de compte sur `surfaceContainerHigh` et un chevron ;
- carte `Colors.surface`, `BorderRadius.xl`, bordure `StyleSheet.hairlineWidth` en `outlineVariant`, `Shadows.soft` ;
- l'encart disparaît entièrement quand le compte vaut 0.

Le commentaire du composant dit l'origine du problème : « *Same silhouette, card, badge and chevron as the Daily Digest card it replaces — the style block was renamed, not redrawn* ». L'encart est le bouton Daily Digest recyclé (sa maquette d'origine est `mobile-design-mockups/inbox_daily_digest_button_ux/`), ce qui explique qu'il ne ressemble à rien d'autre dans l'app actuelle.

## Écarts vérifiables au design system

`mobile-design-mockups/my_design_system/DESIGN.md` (« Amber Clarity ») :

- **« The No-Line Rule »** — « *Avoid 1px solid borders for broad layout divisions* » : la carte porte une bordure hairline pleine.
- **« Signature Textures »** — « *Use a 5% opacity tint of the Primary color* » : la pastille d'icône est à 10 %.
- **« Don't over-apply shadows. Only the top bar and primary interactive containers should utilize the soft shadow »** : à arbitrer, l'encart n'est pas le conteneur principal de l'écran.

Ces trois points sont des faits opposables, pas des goûts. Ce sont eux qui doivent porter les variantes, avec les références demandées plus bas.

## Le libellé est tranché

**« Revue des non classés »** (décision owner, 2026-09-06). Ce n'est pas une préférence : le français est le **seul catalogue sur onze** à parler de « tri » — EN « Unsorted review », DE « Unsortiertes durchgehen », NL « Ongesorteerd nalopen », IT « Revisione dei non ordinati », PT « Revisão dos não organizados ». Le FR revient dans le rang. La maquette affiche ce libellé ; son portage dans les catalogues appartient à la tâche d'implémentation.

## Contraintes de la maquette

- Valeurs prises dans `mobile/src/constants/theme.ts` uniquement — couleurs, rayons, ombres, échelle typographique, `TouchTarget`.
- Le compteur reste lisible d'un coup d'œil : c'est la seule information chiffrée de l'encart, et l'encart s'efface à 0.
- Ionicons est la langue d'icônes de l'app partout ailleurs ; une variante qui en sort doit dire pourquoi.
- **Le rythme vertical de l'accueil n'est pas rouvert.** Le feedback `AE3J09ClZ0T9VY8Jc5SnCRc` est classé `declined` le 2026-09-04 dans `docs/testflight-feedback-log.md` : l'owner a tranché qu'on ne touche pas aux écarts entre sections. Aucune variante ne doit proposer de changer `HOME_BLOCK_GAP` ni les marges de section.

## Justifier par des références, pas par une intuition

Une variante n'est recevable que si elle s'appuie sur une règle citée du design system **et** sur au moins une implémentation de référence nommée : les files « à traiter » des apps de lecture différée (Readwise Reader, Matter, Raindrop, Pocket), les patterns documentés de Material 3 (card, list item, banner), ou les captures déjà déposées dans `mobile-design-mockups/notebooklm-reference/`. C'est la même exigence que task-263 posait : un agent ne devine pas une cible visuelle.

## Périmètre

Le livrable est la maquette, pas le code de l'app. Aucun fichier de `mobile/app/` ni de `mobile/src/` n'est modifié ici — l'implémentation suit dans la tâche qui dépend de celle-ci.

## Notes pour l'owner (pas des ACs)

- Tu ouvres `code.html` dans un navigateur, tu choisis une variante (ou tu demandes un tour de plus), et tu notes ton choix dans le README du dossier : c'est ce que la tâche d'implémentation lira.
- Aucune capture d'écran n'est demandée à l'agent : il n'a pas de navigateur pour la produire. Le HTML autonome tient ce rôle.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 `mobile-design-mockups/home_unsorted_review_card/code.html` existe et s'ouvre seul dans un navigateur, sans ressource distante nécessaire à la fidélité du rendu (repli de police système déclaré), présentant au moins trois variantes de l'encart côte à côte
- [ ] #2 Chaque variante est rendue avec les valeurs réelles de `mobile/src/constants/theme.ts` (couleurs, rayons, ombres, échelle typographique) et porte le libellé « Revue des non classés », son icône, son compteur et son affordance d'entrée
- [ ] #3 Chaque variante est montrée dans les cas limites que l'app produit : compteur à un chiffre et à trois chiffres, et libellé long des catalogues existants (DE « Unsortiertes durchgehen », PT « Revisão dos não organizados »)
- [ ] #4 `mobile-design-mockups/home_unsorted_review_card/README.md` justifie chaque variante par une règle citée de `my_design_system/DESIGN.md` et par au moins une implémentation de référence nommée, dit ce que chaque variante abandonne, et ne s'appuie à aucun endroit sur une préférence personnelle
- [ ] #5 Le README nomme l'icône proposée par variante avec son identifiant exact dans la bibliothèque utilisée par l'app, et dit ce qui la rend préférable à `file-tray-outline`
- [ ] #6 Le README traite explicitement les trois écarts relevés au design system — bordure hairline contre la « No-Line Rule », teinte d'icône à 10 % contre les 5 % de la règle, usage de `Shadows.soft` — en disant pour chacun ce que la variante retient et pourquoi
- [ ] #7 Aucune variante ne propose de modifier le rythme vertical de l'accueil (`HOME_BLOCK_GAP`, marges de section), conformément au no-go owner du 2026-09-04 consigné dans `docs/testflight-feedback-log.md` (`AE3J09ClZ0T9VY8Jc5SnCRc`)
- [ ] #8 Le diff de la tâche se limite à `mobile-design-mockups/` et au backlog : aucun fichier de `mobile/app/` ou `mobile/src/` n'est modifié
<!-- AC:END -->
