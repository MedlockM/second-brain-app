---
id: task-376
title: >-
  Benchmark d'une refonte disruptive de l'écran d'abonnement : hiérarchie de
  l'information, vocabulaire sans jargon, et vitrine exhaustive des plateformes
  prises en charge
status: To Do
assignee: []
created_date: '2026-09-07 13:51'
labels:
  - benchmark
  - mobile
  - ui
  - product
dependencies: []
priority: high
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Recherche d'un parti pris de présentation pour l'écran de gestion de l'abonnement — `mobile/app/paywall.tsx`, atteint depuis l'onglet Compte par la ligne « Gérer l'abonnement » (`mobile/app/(tabs)/account.tsx:200`) — que l'owner juge trop bavard, trop lent à lire, et dont les informations décisives sont enfouies.

## Le constat de l'owner, replacé dans le code

1. **Trop de texte.** Les clés `plan.*` et `paywall.*` de `mobile/src/i18n/fr.ts` totalisent ~870 mots, dont ~50 pour les quatre lignes de bénéfices (`buildPlanHighlights`), ~26 pour `plan.minutesRule` et ~355 pour le détail déplié (`plan.includes.*` + `plan.legend.*`). L'écran demande donc plusieurs minutes de lecture attentive avant qu'un nouveau venu sache ce qu'il achète.

2. **Les informations décisives sont derrière des dépliants imbriqués.** Le chemin est : onglet Compte → « Gérer l'abonnement » → paywall → « Voir les détails » (`paywall-includes-toggle`, `isDetailOpen`, `mobile/app/paywall.tsx:530`) → cinq sections de puces produites par `buildPlanIncludes` (`mobile/src/lib/planCopy.ts:517`). Ce qui vit là-dedans n'est pas du détail : la liste des sources acceptées, ce que les minutes comptent et ce qui est gratuit y sont enfermés. Le commentaire d'en-tête de `planCopy.ts` assume ce choix (« put on screen unprompted it is the wall of text every paywall study says nobody reads ») — c'est exactement l'arbitrage que ce benchmark doit rejuger, pas contourner.

3. **« Transcription » est un terme technique.** Il porte la ligne dominante des cartes (`plan.card.allowance` : « {duration} de transcription »), le libellé du sélecteur (`paywall.selectorLabel`), la règle des minutes (`plan.minutesRule`) et plusieurs items du détail — dans les onze catalogues. Un utilisateur non averti ne sait pas ce qu'il achète quand on lui vend « 5 h de transcription ».

4. **Les plateformes prises en charge sont sous-vendues et incomplètes.** `plan.highlight.capture` dit « podcasts » sans nommer une seule plateforme ; le détail (`plan.includes.capture.links`) nomme Apple Podcasts, Spotify, Deezer et RSS, mais **WhatsApp n'apparaît nulle part sur cet écran** alors que `SourcePlatform.WHATSAPP` existe côté backend et que le partage WhatsApp (message texte *et* note vocale Opus) est documenté et implémenté (`docs/whatsapp-share-payload-shapes.md`, `mobile/src/contexts/ShareIntentContext.tsx`, clé `share.whatsappText`). C'est la capacité la plus quotidienne du produit, invisible sur l'écran qui doit la vendre.

## Dimensions à couvrir

1. **État des lieux chiffré.** Mots à l'écran et nombre de gestes pour atteindre chaque information, en état replié et déplié, sur la locale la plus courte et la plus longue. C'est la ligne de base contre laquelle la proposition sera jugée.

2. **Hiérarchie de l'information.** Quelle information mérite le premier écran, laquelle peut attendre, et par quel moyen autre qu'un dépliant textuel (tableau comparatif, pictogrammes, chiffres, logos, groupement visuel). Chaque parti pris proposé doit être rattaché à une implémentation de référence nommée et consultable, pas à une intuition ; ce qui n'a pas pu être consulté depuis l'environnement doit être dit tel quel.

3. **Vocabulaire.** Un lexique de remplacement pour « transcription » et les termes voisins (« minutes », « formule », « essai », « import »), dans les onze locales. Contrainte à intégrer, pas à ignorer : les descriptions d'abonnement d'App Store Connect utilisent « transcription » dans les onze langues, choix de l'owner du 2026-09-02 (`docs/store-listing/app-store-connect.md`, § *Localizations*, et task-337). Changer le mot dans l'app désaligne l'app de la fiche store : chiffrer ce coût et donner les chemins de menus exacts, dans l'UI actuelle des deux consoles, pour mettre à jour les descriptions et les noms d'affichage des produits.

4. **Vitrine des plateformes, exhaustive et prouvée.** La liste doit être dressée depuis le code, pas de mémoire : `SourcePlatform` (`media_summarizer/core/media_ingestion/domain.py:31` et `api/models/media_contracts.py:37`), les hôtes du classifieur (`core/media_ingestion/adapters/classifiers.py`), `docs/INGESTION_WORKERS_PROVIDERS.md`, les formats de fichiers (`UPLOAD_PICKER_MIME_TYPES` côté mobile, `DocumentFormat.supported_extensions()` côté backend), et `docs/whatsapp-share-payload-shapes.md`. Les sous-cas comptent : les quatre chemins podcast (Apple Podcasts, Spotify, Deezer, flux RSS quelconque), YouTube y compris `music.youtube.com`, Instagram reel *contre* publication photo, X (dont `twitter.com`), TikTok, article et page web quelconque, URL audio directe, WhatsApp texte et note vocale. Traiter aussi : afficher des logos de marques tierces sur un écran d'achat est-il permis (guidelines de marque de chaque plateforme, règles des stores), ou faut-il s'en tenir aux noms.

5. **Non-régression de l'exactitude.** L'écran a déjà dérivé une fois (task-299) parce que les chiffres et les listes étaient retapés à plusieurs endroits. Proposer un mécanisme qui empêche la liste des plateformes de redevenir fausse — dérivation depuis une source unique plutôt que onze catalogues écrits à la main — compatible avec la règle d'en-tête de `planCopy.ts` : aucune figure, aucun prix n'est écrit côté mobile.

6. **Un écran ou deux.** Aujourd'hui « Gérer l'abonnement » ouvre le paywall, et l'état de l'abonnement vit ailleurs (`SubscriptionStatusCard`, onglet Compte). Trancher si consulter son abonnement et choisir/changer de formule doivent rester le même écran, et dire ce que ça change au chemin de navigation.

7. **Ce qui ne peut pas bouger.** La proposition doit rester compatible avec : prix issus uniquement du package store (jamais de la config), conditions de renouvellement affichées dès que l'achat est possible, liens CGU et confidentialité présents dans le binaire sur l'écran d'achat, aucun bouton « Restaurer les achats » (task-336 : le rajouter est une régression), aucun claim non vérifiable (pas de « le plus populaire »), et les trois états distincts du chargement (pricing absent, prix store absents, tout chargé).

8. **Tenue en langue et en accessibilité.** Arabe en RTL, allemand et néerlandais aux mots longs, écran de 375pt, Dynamic Type, et les labels VoiceOver que les cartes portent déjà. Une maquette qui ne survit pas à l'allemand ou à l'arabe est disqualifiée.

## Cadrage projet

`AGENTS.md`, « Nothing is deployed yet » : l'app n'a jamais été soumise à un store, aucune formule n'est vendue, aucun abonnement n'est actif. La refonte remplace l'écran actuel — ne pas proposer de variante A/B, de bascule progressive ni de conservation de l'ancienne présentation.

## Livrable

Un `docs/research/task-XXX-<description-courte>/README.md` avec le front-matter de décision (`owner_decision: pending`), les maquettes textuelles, les tableaux comparatifs et une recommandation argumentée. **Aucune implémentation** : ni écran, ni catalogue de traduction, ni modification de `mobile/` ou de `media_summarizer/`. La tâche d'implémentation liée s'en chargera après la décision de l'owner.

## Note pour l'owner (pas un AC)

Le rendu d'une maquette ne se juge que sur un appareil ou un simulateur, dont l'agent ne dispose pas. Les propositions resteront des wireframes textuels ; le choix final vous revient sur lecture du README.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 État des lieux chiffré de l'écran actuel : mots affichés et nombre de gestes pour atteindre chaque information, en état replié et déplié, sur la locale la plus courte et la plus longue, mesuré depuis les fichiers cités
- [ ] #2 Liste exhaustive des sources et plateformes réellement prises en charge, chaque entrée portant le fichier qui la prouve (SourcePlatform, classifiers.py, INGESTION_WORKERS_PROVIDERS.md, UPLOAD_PICKER_MIME_TYPES, DocumentFormat.supported_extensions(), whatsapp-share-payload-shapes.md), avec une section à part pour celles que l'écran actuel n'affiche pas — WhatsApp comprise
- [ ] #3 Au moins trois partis pris de présentation comparés, chacun avec un wireframe textuel et rattaché à au moins une implémentation de référence nommée ; ce qui n'a pas pu être consulté depuis l'environnement est listé explicitement comme non vérifié
- [ ] #4 Lexique de remplacement de « transcription » et des termes voisins proposé pour les onze locales, avec le coût de désalignement avec les descriptions d'abonnement d'App Store Connect et de la Play Console chiffré, et les chemins de menus exacts pour les mettre à jour
- [ ] #5 La question « afficher les logos des plateformes tierces sur un écran d'achat » est tranchée avec les règles de marque et les règles des stores citées, ou déclarée non vérifiable avec la raison
- [ ] #6 Un mécanisme est proposé pour que la liste des plateformes ne puisse pas redevenir fausse, compatible avec la règle « aucune figure ni aucun prix écrit côté mobile »
- [ ] #7 Le parti pris recommandé est vérifié tenable en arabe (RTL), en allemand et néerlandais (mots longs) et sur 375pt, et il conserve tout ce qui est exigé : prix issus du package store, conditions de renouvellement, liens CGU et confidentialité, aucun bouton « Restaurer les achats », aucun claim non vérifiable, trois états de chargement distincts
- [ ] #8 Réponse tranchée sur « un écran ou deux » — consultation de l'abonnement contre choix de formule — avec les conséquences sur le chemin de navigation depuis l'onglet Compte
- [ ] #9 Recommandation finale argumentée dans un docs/research/task-XXX-*/README.md portant owner_decision: pending, sans qu'aucun fichier de mobile/ ni de media_summarizer/ ne soit modifié
<!-- AC:END -->
