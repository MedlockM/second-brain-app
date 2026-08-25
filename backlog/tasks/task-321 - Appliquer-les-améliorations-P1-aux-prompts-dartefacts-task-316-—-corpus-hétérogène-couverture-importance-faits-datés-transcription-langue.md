---
id: task-321
title: >-
  Appliquer les améliorations P1 aux prompts d'artefacts (task-316) — corpus
  hétérogène, couverture, importance, faits datés, transcription, langue
status: To Do
assignee: []
created_date: '2026-08-25 11:42'
updated_date: '2026-08-25 11:45'
labels:
  - artifacts
  - prompt-engineering
  - backend
dependencies:
  - task-320
priority: medium
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
## Contexte

Suite de task-320 sur la même base d'analyse : `docs/research/task-316-artifact-prompts/README.md` (`owner_decision: ok`). Cette tâche implémente les propositions **P1 de la section 4, à l'exception de P1-7**. Lis le README avant de commencer — il donne pour chaque proposition le fichier, le texte à écrire et la mesure à rejouer.

Dépend de task-320 : les deux tâches éditent les mêmes cinq générateurs et le même `corpus.py`, et chacune bumpe `generator_version`. Ne démarre pas avant que les P0 soient sur `main`.

**Les P2 sont hors périmètre — n'y touche pas** : pas de structured outputs sur `summary_short`/`summary_detailed`/`notes`, pas d'alignement du repli de modèle de `notes`, pas d'instrumentation des reasoning tokens, pas de réexamen du modèle de `summary_short`.

## Périmètre

- **P1-1** — traiter le corpus hétérogène pour ce qu'il est (`summary_short.py`, `summary_detailed.py`) : règle à deux branches selon que les sources partagent un sujet ou non, au lieu de « Cover the sources as a whole ». Un artefact couvrant plusieurs sources ne doit plus être titré d'après une seule.
- **P1-2** — quantifier la couverture multi-sources : fragment partagé de `corpus.py` utilisé par `quiz`, `flashcards` et `summary_detailed`, répartissant les items à proportion de la contribution de chaque source.
- **P1-3** — cadrer `importance` dans les notes (`notes.py:106-147`) : critère opérationnel distinguant `core` de `supporting`, avec l'attente explicite d'une minorité de `core`. Le README propose en alternative de supprimer le champ et son badge mobile ; retiens la version qui cadre le champ, pas la suppression.
- **P1-4** — ancrer les faits datés : enrichir l'en-tête de corpus (`corpus.py:35-53`) d'un champ `published` à partir de ce que le message SQS transporte déjà ou de ce qu'il faut y ajouter (`artifact_service.py:731-741`), et instruire l'ancrage explicite des faits vrais à un instant donné, avec l'interdiction de transformer une mesure du jour en flashcard ou en question de quiz.
- **P1-5** — neutraliser les marqueurs de transcription : fragment partagé expliquant que les sources sont des transcripts automatiques, que `>>` marque un changement de locuteur et que les tags entre crochets (`[laughs]`, `[music]`) sont des annotations non verbales à ne jamais analyser comme du contenu.
- **P1-6** — tenir la langue jusqu'au vocabulaire (`corpus.py:71`, `language_instruction()`) : toutes les chaînes produites, y compris les termes de glossaire et les titres, dans la langue cible ; un terme reste en langue d'origine seulement à défaut d'équivalent, et il est alors glosé à la première occurrence.
- **Bump de version** — passer les cinq entrées de `get_generator_version()` (`artifact_service.py:203-225`) de `prompt-v3` (posé par task-320) à `prompt-v4`, pour la même raison de traçabilité.

## Hors périmètre

- **P1-7 est annulé** par la décision de l'owner sur le README : un artefact de média ne sera générable qu'une seule fois, donc il n'y a plus de régénération à diversifier. Ne construis ni seed, ni variation d'instruction, ni injection des titres déjà produits.
- Tous les P2, et les P0 déjà livrés par task-320.
- Ce que la section 5 du README classe comme non-problème de prompt : ne touche pas à `source_ref_instruction(required=True)`, ni à `_shuffle_options()`, ni à l'ordre corpus → instructions qui est un choix de coût validé par task-269.

## Notes à l'owner (non vérifiables par l'agent)

Vérifications proposées par le README après déploiement : régénérer `summary_short` sur la collection à trois sources hétérogènes du §2.8 (le titre ne doit plus annoncer le longboard seul) ; régénérer le quiz du corpus 4 642 / 2 165 / 2 210 o (la répartition 5/1/1 doit se rapprocher de 3/2/2) ; régénérer les notes du cours de surf (aujourd'hui 8 `core` sur 8) ; régénérer flashcards et notes sur la page Le Grand Crohot (plus aucune occurrence de « aujourd'hui », et la carte n° 1 ne doit plus porter sur la valeur du jour) ; régénérer `summary_short` sur le clip TikTok (la puce sur les rires et la musique doit disparaître) ; régénérer les notes de la page bilingue FR/EN (plus d'entrée de glossaire uniquement anglaise non glosée).
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 Les prompts summary_short et summary_detailed distinguent explicitement le corpus homogene du corpus heterogene, et interdisent de titrer l'artefact d'apres une seule source quand il en couvre plusieurs
- [ ] #2 Un fragment partage impose une repartition des items proportionnelle a la contribution de chaque source, utilise par quiz, flashcards et summary_detailed
- [ ] #3 Le prompt notes donne un critere operationnel pour distinguer core de supporting et attend une minorite de core ; le champ et son badge mobile sont conserves
- [ ] #4 L'en-tete de corpus porte la date de publication de chaque source, et un fragment partage impose l'ancrage temporel des faits vrais a un instant donne tout en interdisant d'en faire des flashcards ou des questions de quiz
- [ ] #5 Un fragment partage decrit la nature de transcript automatique des sources, le role de >> et des tags entre crochets, qui ne doivent pas etre analyses comme du contenu
- [ ] #6 language_instruction() impose la langue cible pour toutes les chaines produites, glossaire et titres inclus, avec glose a la premiere occurrence d'un terme laisse en langue d'origine
- [ ] #7 Les cinq entrees de get_generator_version() sont passees de prompt-v3 a prompt-v4
- [ ] #8 P1-7 n'est pas implemente, et aucune proposition P2 ne l'est non plus
- [ ] #9 source_ref_instruction(required=True), _shuffle_options() et l'ordre corpus vers instructions sont inchanges
- [ ] #10 L'exigence d'exhaustivite posee par task-320 n'est pas affaiblie par les regles de repartition ajoutees ici

- [ ] #11 ruff et mypy passent sur les fichiers modifies
<!-- AC:END -->
