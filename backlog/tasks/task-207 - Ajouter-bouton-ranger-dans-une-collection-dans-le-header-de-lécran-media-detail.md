---
id: task-207
title: >-
  Ajouter bouton "ranger dans une collection" dans le header de l'écran media
  detail
status: To Do
assignee: []
created_date: '2026-06-15 15:33'
labels:
  - mobile
  - feature
  - ux
dependencies: []
priority: medium
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
## Contexte

Sur l'écran de détail d'un média (`mobile/app/media/[id].tsx`), l'utilisateur peut actuellement uniquement revenir en arrière et partager le média via l'icône share-outline en haut à droite (cf. `Header` autour de la ligne 699). Il n'y a pas de moyen, depuis cet écran, de ranger ou déplacer le média vers une collection sans repasser par le flow de partage.

Pourtant, le modal de confirmation de partage (`mobile/app/share-confirmation.tsx`) propose déjà un sélecteur de collection (`folder-open-outline` + libellé "Non trié" / chemin de la collection) qui ouvre l'écran `/media/collection?mode=share`. On veut offrir la même action depuis le media detail.

## Objectif

Ajouter, dans le header de l'écran media detail, un nouveau bouton à gauche de l'icône share-outline représentant un dossier (icône type `folder-outline` / `folder-open-outline`). Au tap, l'utilisateur est dirigé vers le sélecteur de collection (réutiliser `app/media/collection.tsx`) afin de ranger ou déplacer le média en cours dans une collection. La sélection doit ensuite être persistée côté API pour que le média apparaisse dans la collection choisie (cohérent avec ce qui se fait dans le flow share-confirmation).

## Scope

- UI : ajouter un bouton dossier dans le composant `Header` de `mobile/app/media/[id].tsx`, placé immédiatement à gauche du bouton share existant, avec mêmes hitSlop / styles que les autres `headerButton`.
- Navigation : au press, ouvrir l'écran de sélection de collection (réutiliser le composant existant). Adapter `app/media/collection.tsx` si besoin pour gérer un mode "déplacer un média existant" (par opposition au mode `share` actuel) — par exemple via un nouveau paramètre `mode=move` + `mediaItemId`.
- Persistance : appeler l'endpoint d'assignation collection ↔ media existant (vérifier l'API media côté backend ; sinon créer une issue de suivi). Afficher la collection actuelle du média à l'ouverture du sélecteur.
- Feedback : à la confirmation, revenir au media detail et afficher une indication (toast / banner discret) "Rangé dans <collection>" ou similaire. Si une collection est déjà associée, le bouton doit refléter cet état (par ex. `folder` rempli au lieu de `folder-outline`).
- Cohérence : réutiliser autant que possible la logique du flow share-confirmation pour éviter la divergence visuelle/comportementale (cf. également task-206 qui vise à unifier ces écrans).

## Hors scope

- Création / renommage / suppression de collections (déjà couverts ailleurs).
- Évolution UX du sélecteur de collection lui-même.
- Refonte du header media detail au-delà de l'ajout du bouton.

## Acceptance Criteria
<!-- AC:BEGIN -->
- Un bouton dossier est visible dans le header du media detail, immédiatement à gauche de l'icône share, avec accessibilityLabel approprié (par ex. "Move to collection").
- Le tap ouvre le sélecteur de collection (même UI que celui ouvert depuis share-confirmation).
- Sélectionner une collection puis valider met à jour l'appartenance du média : à la sortie, l'écran media detail reflète la nouvelle collection (état du bouton mis à jour) et le média apparaît dans cette collection dans l'app.
- Annuler la sélection revient au media detail sans modification.
- Pas de régression visuelle ni comportementale sur le bouton share existant.
<!-- SECTION:DESCRIPTION:END -->

- [ ] #1 Un bouton dossier (folder-outline) est ajouté dans le Header de mobile/app/media/[id].tsx, à gauche du bouton share-outline existant, avec accessibilityLabel 'Move to collection' et mêmes styles/hitSlop que les autres headerButton
- [ ] #2 Le tap sur ce bouton ouvre le sélecteur de collection (réutilise app/media/collection.tsx) avec un mode adapté pour ranger un média existant (ex. mode=move + mediaItemId)
- [ ] #3 Confirmer une collection met à jour l'appartenance du média côté API et l'écran media detail reflète la nouvelle collection (le bouton dossier indique l'état rangé/non rangé)
- [ ] #4 Le média sélectionné apparaît dans la collection choisie dans l'app (vérifier via l'explorateur de collections)
- [ ] #5 Annuler la sélection revient au media detail sans modification, et aucune régression n'est introduite sur le bouton share existant
<!-- AC:END -->
