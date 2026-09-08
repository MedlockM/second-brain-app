---
id: task-377
title: >-
  Refondre l'écran de gestion de l'abonnement selon le benchmark validé
  (task-376)
status: Done
assignee: []
created_date: '2026-09-07 13:52'
updated_date: '2026-09-08 08:54'
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
- [x] #1 L'écran suit le parti pris de présentation décrit dans le champ Decision du README de task-376, compléments cités inclus ; les notes d'implémentation nomment chaque écart et sa raison
- [x] #2 Le lexique retenu est appliqué aux onze catalogues de mobile/src/i18n/, sans qu'aucune clé existe dans un fichier et manque dans un autre, vérifiable en comparant les jeux de clés ; les clés rendues inutiles sont supprimées partout
- [x] #3 Si la décision retire « transcription », aucun texte de l'écran d'abonnement ne l'emploie plus, dans aucune des onze locales
- [x] #4 Toutes les plateformes et sources de la liste validée par task-376 sont présentes à l'écran, WhatsApp comprise et chaque plateforme de podcast nommée, sans en ajouter aucune qu'aucun worker ne traite
- [x] #5 Aucune figure, aucun prix, aucune conversion d'unité n'est écrit dans mobile/ : les valeurs arrivent de GET /api/pricing et du package store par les emplacements d'interpolation existants
- [x] #6 Les éléments exigés restent en place : conditions de renouvellement dès que l'achat est possible, liens CGU et confidentialité, aucun bouton « Restaurer les achats », et les trois états de chargement restent distincts à la lecture du code
- [x] #7 Plus aucune mention de tags dans les textes de l'écran, et le mot employé pour un dossier est celui retenu par task-373
- [x] #8 docs/store-listing/app-store-connect.md et docs/store-listing/google-play-store.md décrivent ce que l'app dit après cette refonte, sans paragraphe laissé en état « à aligner »
- [x] #9 npm run typecheck et npm run lint sont propres dans mobile/
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Parti pris A appliqué : le dépliant `paywall-includes-toggle` est supprimé (pas
raccourci), avec `isDetailOpen`, `buildPlanIncludes`, `buildMinutesLegend`,
`buildPlanHighlights`, `listArtifactLabels` et les 28 clés devenues inutiles dans les
onze catalogues. À la place, deux blocs plats : une vitrine de noms propres
(`paywall-sources`, une puce par plateforme et par famille de fichiers, aucune phrase,
aucun logo tiers) et un tableau de coûts (`paywall-cost-table`).

**Ce qui n'est pas dans mobile/ et qui est nouveau côté backend.** La vitrine devait
être dérivée du backend sans second appel réseau : `GET /api/pricing` porte désormais
un champ `sources`, alimenté par `media_summarizer/core/media_ingestion/adapters/
share_targets.py` (nouveau). Ce module ne contient que des noms propres et des
identifiants — le client garde la formulation, le backend garde la liste. Un
`_assert_exhaustive()` au chargement du module lève une `RuntimeError` si un
`SourcePlatform` apparaît sans être ni décrit ni explicitement retenu, si un hôte
reconnu par `classifiers.py` n'a pas de puce, ou si un format déclaré n'est plus
accepté : la vitrine ne peut pas mentir par omission après l'ajout d'un worker.
`classifiers.py` expose pour cela `RECOGNISED_HOSTS` et `AUDIO_URL_EXTENSIONS`.

**Écarts avec la lettre du README, et leur raison.**

1. *Six lignes de coût, là où la prose dit « quatre » et où le maquettage du §3.1 en
   dessine cinq.* Le §3.1 omet `folder_sources_per_minute`, qui est un débit réel
   (`quota_enforcer` le facture) : ne pas l'afficher rendait le tableau faux dès qu'on
   génère sur un dossier. La sixième ligne est le podcast qui publie son texte, à zéro
   minute — c'est un avantage tarifaire invisible autrement, et il coûte une ligne.
2. *`paywall.subtitle` est conservé (reformulé) au lieu d'être fondu dans la phrase de
   promesse.* C'est la seule ligne qui dit que les trois formules ont les mêmes
   capacités. `DEFAULT_PRICING_CONFIG` le confirme : elles ne diffèrent que par
   `minutes_per_month` (60/300/720) et `max_minutes_per_item` (60/180/240). La
   supprimer laissait croire que la formule basse retient une fonctionnalité, ce qui
   est exactement la sous-description que vise l'App Review 3.1.2(c). Formulée « ils
   diffèrent seulement par combien vous envoyez », elle couvre les deux axes ; « par
   combien de minutes » n'aurait nommé que le premier et laissé le plafond par import
   non annoncé.
3. *La phrase de promesse ne nomme plus les cinq types de génération.* Une liste
   interpolée de cinq éléments fait environ quatre lignes en allemand dans l'en-tête et
   repousse le premier prix sous la ligne de flottaison — précisément la propriété pour
   laquelle le parti pris A existe. Conséquence assumée : `ARTIFACT_TILES` n'est plus
   annoncé sur le paywall (il l'est toujours sur la fiche store et à l'usage).
4. *`plan.legend.overLimit` disparaît de l'écran.* Le plafond par import reste écrit
   sur chaque carte (`plan.card.perImport`), donc l'information n'est pas perdue ; la
   version en légende la répétait une troisième fois.
5. *Le nombre de langues de lecture (`V1_READING_LANGUAGES`) n'est plus annoncé sur le
   paywall.* C'était une ligne de `buildPlanIncludes` ; aucun des trois blocs retenus
   n'en est le bon porteur.
6. *`account.subscription.manageHint` est réécrit, pas seulement le libellé du bouton.*
   Il disait « Changer de formule ou restaurer un achat » alors que task-336 a retiré
   le bouton de restauration : c'était une promesse fausse dans les onze locales.

**AC#5, deux cas à ne pas confondre avec une figure.** `paywall.renewalTerms` porte
« 24 heures » dans les onze locales : c'est le texte de renouvellement imposé par les
stores, pas une valeur de configuration, et il est antérieur à cette passe. En
japonais, `plan.card.perImport` s'écrit « 1 回あたり最大 {duration} » : le « 1 » est le
classificateur de « par import », comme dans le préexistant « 1 時間あたり »
(`plan.hourlyRate`). Aucune valeur de prix, de quota ni de conversion n'est écrite dans
`mobile/` : les six lignes du tableau interpolent `document_pages_per_minute` et
`folder_sources_per_minute`, et les deux conversions sont formulées en mots
(« une minute par {pages} pages ») pour ne pas avoir à écrire de chiffre.

**RTL et accessibilité.** Une puce = un `Text` = un seul run bidi, ce qui évite le
collage arabe du type `وSpotify` qu'aurait produit une chaîne concaténée ; le lien
entre le libellé et la valeur d'une ligne de coût est un `flex: 1` et non un `·`
inséré dans le texte ; `costValue` aligne avec `I18nManager.isRTL`. La vitrine est un
élément accessible par groupe, avec un libellé joint via `joinList()` (qui garde
vivantes `plan.list.separator` et `plan.list.lastConjunction`), et chaque ligne de coût
un élément accessible annonçant « libellé, valeur ».

**À regarder sur le prochain build (le rendu ne se juge pas depuis un worktree).**
Trois locales sont les plus serrées, pour trois raisons différentes : **pt** pour la
longueur de libellé (`plan.cost.captions.label` = « Um vídeo do YouTube, qualquer que
seja a duração », 48 caractères, le plus long des onze ; fr suit à 43), **de** pour la
largeur de mot (les intitulés de bloc sont en capitales avec `letterSpacing`, d'où
`Typography.small` à 13 pt et non `label` ; son plus long libellé est
`plan.cost.transcript.label` à 45), **hi** pour le nombre de mots dans la phrase de
promesse. Vérifier : que les
puces de la vitrine passent bien à la ligne sans être tronquées (aucun `numberOfLines`
posé, `flexWrap: "wrap"`), que la valeur d'une ligne de coût ne dépasse pas ses 45 %
de largeur au point de couper le libellé, et que le premier prix reste visible sans
défilement sur un écran de 375 pt de large.

**Suite manuelle, côté owner (hors périmètre d'un worktree).** Les 39 descriptions
d'abonnement (13 locales × 3 formules) sont écrites dans
`docs/store-listing/app-store-connect.md`, et la section abonnements de la Play Console
(Name + 4 Benefits par formule) est désormais créée dans
`docs/store-listing/google-play-store.md`. Les deux consoles restent à mettre à jour à
la main, chemins de menus dans le README de task-376 §4.4. Les chaînes marquées
« nouveau » au §4.2 du même README méritent une relecture par un locuteur natif ; les
traductions livrées ici ne le sont pas.

Aucun test automatisé n'a été ajouté (règle du projet).
<!-- SECTION:NOTES:END -->
