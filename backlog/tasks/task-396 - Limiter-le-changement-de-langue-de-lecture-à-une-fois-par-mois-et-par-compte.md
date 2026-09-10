---
id: task-396
title: Limiter le changement de langue de lecture à une fois par mois et par compte
status: To Do
assignee: []
created_date: '2026-09-10 12:37'
labels:
  - backend
  - mobile
  - cost
dependencies: []
priority: medium
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
## Contexte

Changer de langue de lecture engage un coût fournisseur réel : traduction du texte complet de chaque média ouvert, puis traduction de ses artefacts. Ce coût est maîtrisé par média (la traduction est persistée et ne se relance pas), mais rien ne limite la **fréquence** à laquelle un compte peut changer de langue, et chaque changement rouvre la porte à une nouvelle vague de traductions sur toute la bibliothèque au fil des ouvertures.

## Décision du propriétaire

**Un changement de langue de lecture par mois et par compte.** Garde-fou de coût, pas une fonctionnalité produit.

## Périmètre

Le refus doit être lisible côté application : l'utilisateur comprend qu'il a déjà changé de langue récemment et à partir de quand il pourra le refaire. Le message passe par les 11 catalogues i18n existants, comme toute autre chaîne de l'application.

À la charge de l'implémenteur de vérifier si la langue de lecture est modifiable ailleurs que sur l'écran de réglages (par exemple à l'inscription ou lors d'un choix initial) et de ne pas appliquer la limite là où elle empêcherait un premier réglage.

## Notes au propriétaire (hors critères d'acceptation)

Vérification manuelle après déploiement : changer de langue, puis tenter un second changement immédiatement et lire le refus dans l'application.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 Un second changement de langue de lecture dans le mois qui suit le précédent est refusé côté backend, indépendamment du client qui le demande.
- [ ] #2 Le refus est présenté dans l'application avec la date à partir de laquelle un nouveau changement est possible, via les 11 catalogues i18n existants.
- [ ] #3 Le premier réglage de la langue de lecture d'un compte n'est pas soumis à la limite.
- [ ] #4 ruff et mypy passent sans erreur sur les modules touchés.
<!-- AC:END -->
