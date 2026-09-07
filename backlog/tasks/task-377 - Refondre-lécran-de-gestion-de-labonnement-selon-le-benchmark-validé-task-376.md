---
id: task-377
title: >-
  Refondre l'écran de gestion de l'abonnement selon le benchmark validé
  (task-376)
status: To Do
assignee: []
created_date: '2026-09-07 13:52'
labels:
  - mobile
  - ui
dependencies:
  - task-376
  - task-372
  - task-373
priority: high
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Réécrire la présentation de l'écran de gestion de l'abonnement conformément à la décision de l'owner sur le benchmark **task-376**.

## Avant de commencer

Lire `docs/research/task-376-*/README.md`, et en particulier le champ `Decision` sous **Owner Validation** : c'est lui qui fait foi, pas la recommandation initiale du benchmark, et il peut renvoyer à un fichier de complément qu'il faut alors lire aussi. Suivre le parti pris retenu, le lexique retenu et la liste de plateformes validée.

## Portée

- `mobile/app/paywall.tsx` — la présentation elle-même : hiérarchie, densité, dépliants, mise en avant des plateformes.
- `mobile/src/lib/planCopy.ts` — les constructeurs de textes (`buildPlanHighlights`, `buildPlanIncludes`, `buildMinutesLegend`, `minutesRule`) et, s'il y a lieu, la source unique dont la liste des plateformes est dérivée.
- Les onze catalogues de `mobile/src/i18n/` — le lexique retenu. `catalogs.ts` et `pseudo.ts` sont générés ou dérivés : vérifier comment avant de toucher l'un ou l'autre.
- `mobile/src/components/SubscriptionStatusCard.tsx` et l'entrée « Gérer l'abonnement » de `mobile/app/(tabs)/account.tsx`, si la décision tranche pour deux écrans plutôt qu'un.
- `docs/store-listing/app-store-connect.md` et `docs/store-listing/google-play-store.md` — mis à jour pour rester comparables à ce que l'app dit désormais, comme task-337 l'a fait dans l'autre sens.

## Ce qui ne bouge pas

Les règles d'en-tête de `paywall.tsx` et de `planCopy.ts` tiennent après la refonte : aucune figure ni aucun prix écrit côté mobile (tout arrive de `GET /api/pricing` et du package store), aucun bouton « Restaurer les achats » (task-336), aucun claim non vérifiable, les conditions de renouvellement et les deux liens légaux restent sur l'écran d'achat, et les trois états de chargement restent distincts (pricing absent, prix store absents, tout chargé). Une règle affichée ici ne peut pas contredire l'onglet Compte, qui lit le même module.

## Vocabulaire

Les dépendances task-372 (suppression des tags) et task-373 (« Collection » → « Dossier ») changent le vocabulaire que cet écran affiche : `plan.highlight.organise` et `plan.includes.organise.file` parlent aujourd'hui de « collections et de tags ». Elles passent avant pour que cette refonte n'écrive pas des textes à refaire.

## Cadrage projet

`AGENTS.md`, « Nothing is deployed yet » : rien n'est vendu, aucun abonnement n'est actif. L'ancienne présentation est remplacée, pas conservée en repli — les clés de traduction devenues inutiles partent dans la même passe, dans les onze catalogues.

## Notes pour l'owner (pas des ACs)

- Le rendu ne se juge que sur un appareil ou un simulateur : les notes d'implémentation diront quelle locale est la plus serrée et quoi regarder sur le prochain build.
- Si la décision change le mot « transcription », les descriptions d'abonnement et les noms d'affichage des produits doivent être mis à jour **par vous** dans App Store Connect et dans la Play Console ; les chemins de menus exacts sont dans le README de task-376.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 L'écran suit le parti pris de présentation décrit dans le champ Decision du README de task-376, compléments cités inclus ; les notes d'implémentation nomment chaque écart et sa raison
- [ ] #2 Le lexique retenu est appliqué aux onze catalogues de mobile/src/i18n/, sans qu'aucune clé existe dans un fichier et manque dans un autre, vérifiable en comparant les jeux de clés ; les clés rendues inutiles sont supprimées partout
- [ ] #3 Si la décision retire « transcription », aucun texte de l'écran d'abonnement ne l'emploie plus, dans aucune des onze locales
- [ ] #4 Toutes les plateformes et sources de la liste validée par task-376 sont présentes à l'écran, WhatsApp comprise et chaque plateforme de podcast nommée, sans en ajouter aucune qu'aucun worker ne traite
- [ ] #5 Aucune figure, aucun prix, aucune conversion d'unité n'est écrit dans mobile/ : les valeurs arrivent de GET /api/pricing et du package store par les emplacements d'interpolation existants
- [ ] #6 Les éléments exigés restent en place : conditions de renouvellement dès que l'achat est possible, liens CGU et confidentialité, aucun bouton « Restaurer les achats », et les trois états de chargement restent distincts à la lecture du code
- [ ] #7 Plus aucune mention de tags dans les textes de l'écran, et le mot employé pour un dossier est celui retenu par task-373
- [ ] #8 docs/store-listing/app-store-connect.md et docs/store-listing/google-play-store.md décrivent ce que l'app dit après cette refonte, sans paragraphe laissé en état « à aligner »
- [ ] #9 npm run typecheck et npm run lint sont propres dans mobile/
<!-- AC:END -->
