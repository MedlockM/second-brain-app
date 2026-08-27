---
id: task-321
title: >-
  Appliquer les améliorations P1 aux prompts d'artefacts (task-316) — corpus
  hétérogène, couverture, importance, faits datés, transcription, langue
status: Done
assignee: []
created_date: '2026-08-25 11:42'
updated_date: '2026-08-27 10:16'
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
- [x] #1 Les prompts summary_short et summary_detailed distinguent explicitement le corpus homogene du corpus heterogene, et interdisent de titrer l'artefact d'apres une seule source quand il en couvre plusieurs
- [x] #2 Un fragment partage impose une repartition des items proportionnelle a la contribution de chaque source, utilise par quiz, flashcards et summary_detailed
- [x] #3 Le prompt notes donne un critere operationnel pour distinguer core de supporting et attend une minorite de core ; le champ et son badge mobile sont conserves
- [x] #4 L'en-tete de corpus porte la date de publication de chaque source, et un fragment partage impose l'ancrage temporel des faits vrais a un instant donne tout en interdisant d'en faire des flashcards ou des questions de quiz
- [x] #5 Un fragment partage decrit la nature de transcript automatique des sources, le role de >> et des tags entre crochets, qui ne doivent pas etre analyses comme du contenu
- [x] #6 language_instruction() impose la langue cible pour toutes les chaines produites, glossaire et titres inclus, avec glose a la premiere occurrence d'un terme laisse en langue d'origine
- [x] #7 Les cinq entrees de get_generator_version() sont passees de prompt-v3 a prompt-v4
- [x] #8 P1-7 n'est pas implemente, et aucune proposition P2 ne l'est non plus
- [x] #9 source_ref_instruction(required=True), _shuffle_options() et l'ordre corpus vers instructions sont inchanges
- [x] #10 L'exigence d'exhaustivite posee par task-320 n'est pas affaiblie par les regles de repartition ajoutees ici

- [x] #11 ruff et mypy passent sur les fichiers modifies
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
P1-1 à P1-6 du §4 de `docs/research/task-316-artifact-prompts/README.md`, plus le bump de version. P1-7 et les P2 sont hors périmètre et n'ont pas été touchés.

## Livré

**P1-1 — corpus hétérogène.** Nouveau fragment partagé `corpus.corpus_shape_instruction()`, inclus par `summary_short` et `summary_detailed` en remplacement de « Cover the sources as a whole; do not summarise them one by one » (summary_short) et de « Treat the sources as one body of material » (summary_detailed). Règle à deux branches : les sources partagent un sujet → synthèse ; elles n'en partagent pas → une phrase le disant, puis une ligne par source. Le volet titre est allé dans `title_instruction()`, donc il s'applique aux cinq types et pas seulement aux deux résumés : « When the corpus holds several sources, the title must not name only one of them ». Un fragment plutôt qu'un paragraphe recopié dans deux fichiers, comme les six fragments déjà en place.

**P1-2 — couverture multi-sources.** Nouveau `corpus.source_balance_instruction(unit, unit_plural)`, utilisé par `quiz` (`question`), `flashcards` (`card`) et `summary_detailed` (`bullet point`). Il remplace les deux lignes qualitatives « Spread the questions/cards across the sources rather than covering only the first one », qui n'obtenaient rien (5/1/1 sur un corpus 51/24/24 %). Deux puces : la part d'items suivant la part de matière et aucune source à zéro, puis la subordination explicite à l'exhaustivité (voir AC #10).

**P1-3 — cadrage d'`importance`.** `notes.py` remplace « `importance` must be either `core` or `supporting` » par un critère opérationnel (`core` = le lecteur ne peut pas utiliser la matière sans, `supporting` = contexte / raffinement / exemple / nom à reconnaître) avec l'attente chiffrée d'une minorité de `core`. La variante « supprimer le champ » proposée par le README n'a pas été retenue, conformément à la consigne : le champ `NotesConcept.importance` et le badge mobile de `mobile/app/artifacts/[artifactId].tsx` sont inchangés.

**P1-4 — faits datés.** Deux volets, comme le README.
- En-tête de corpus : `build_corpus_block()` émet désormais `published: YYYY-MM-DD` et `captured: YYYY-MM-DD` après `title` et `language`. Deux clés distinctes plutôt qu'une seule floue, parce que les deux dates n'ont pas la même provenance ni la même fiabilité : `published` n'est émis que quand le pipeline a réellement résolu une date de publication (`ProcessingJob.media_date_published`, aujourd'hui alimenté par le seul chemin podcast), `captured` est le jour d'entrée du texte dans la bibliothèque (`UserMediaRecord.saved_at`), toujours connu — et c'est exactement le jour auquel se réfère le « aujourd'hui » d'une page-bulletin comme Le Grand Crohot. Étiqueter la date de capture `published` aurait été factuellement faux pour toute vidéo ancienne.
- Plomberie : `ResolvedSource` porte les deux champs, `resolve_source()` calcule `published` depuis le job qu'il détient déjà et reçoit `captured` de `resolve_scope_sources()` qui détient la ligne durable — aucune requête supplémentaire, aucune donnée nouvelle à ingérer. Le message SQS de `plan_artifact_generation()` les transporte et `_download_transcripts()` les recopie dans les dicts de corpus. `_iso_date()` normalise datetime et timestamp Unix en `YYYY-MM-DD` : l'heure serait du bruit à relire sur chaque source.
- Instruction : `corpus.dated_facts_instruction()`, incluse par les cinq types. Le paramètre `review_item` ajoute l'interdiction de transformer une mesure datée en item de révision, posée sur `flashcards` (`flashcard`) et `quiz` (`quiz question`) uniquement — les deux types qui alimentent la file FSRS et l'auto-test.

**P1-5 — marqueurs de transcription.** `corpus.transcript_markers_instruction()`, inclus par les cinq types : transcripts automatiques de parole, `>>` = changement de locuteur, tags entre crochets (`[laughs]`, `[music]`, `[coughs]`, `[applause]`) = annotations non verbales à utiliser pour attribuer la parole et jamais à analyser, erreurs de transcription attendues et reproduites seulement dans une citation verbatim.

**P1-6 — langue jusqu'au vocabulaire.** `language_instruction()` réécrite : toutes les chaînes produites dans la langue cible, en nommant les champs qui dérivaient réellement (titre, intitulés, questions/réponses, et surtout termes et définitions de glossaire ou de liste de concepts), y compris quand les sources les énoncent dans une autre langue. Exception unique et son prix : un terme reste en langue d'origine seulement à défaut d'équivalent accepté, et il est alors glosé dans la langue cible à sa première occurrence. La branche « pas de langue cible » retombe sur « the language of the sources » dans la même phrase, sans second code path.

**Bump de version.** Les cinq entrées de `get_generator_version()` passent de `prompt-v3` à `prompt-v4`. `docs/CANONICAL_MEDIA_API_CONTRACT.md` porte un `generator_version` d'exemple qui annonçait encore `prompt-v3` : mis à jour, sinon le contrat documente une valeur que le code ne produit plus.

## Hors périmètre, vérifié

- **P1-7 non implémenté** : aucun `seed`, aucune variation d'instruction de régénération, aucune injection des titres déjà produits. `worker.py:_call_llm()` et `_question_rng()` sont inchangés.
- **Aucun P2** : `response_format_schema()` renvoie toujours `None` pour `summary_short`, `summary_detailed` et `notes` (pas de structured outputs) ; le repli de modèle de `notes` reste `gpt-4o-mini-2024-07-18` ; `_read_llm_usage()` ne lit toujours pas `completion_tokens_details` ; le modèle de `summary_short` est inchangé.
- **AC #9** : `source_ref_instruction()`, `_shuffle_options()`, `_question_rng()`, `PROMPT_PREAMBLE`, `build_prompt()` et donc l'ordre corpus → instructions n'apparaissent pas au diff. `MIN_FLASHCARDS`, `MIN_QUESTIONS` et les deux `validate()` posés par task-320 non plus.
- **AC #10** : `coverage_instruction()` est identique au byte près (absente du diff), donc « cover every one of those points » et « no target count and no maximum » tiennent. La seconde puce de `source_balance_instruction()` subordonne explicitement la répartition à l'exhaustivité : « Covering every point of every source comes first. Never drop a point from one source to even out the counts », et interdit symétriquement d'ajouter un item de remplissage à une source pauvre pour équilibrer.

## Vérification

- `ruff check media_summarizer/` : All checks passed.
- `mypy media_summarizer/` : Success, no issues found in 173 source files.
- Les huit fichiers Python modifiés passent aussi ruff et mypy pris isolément.
- Diff relu ligne à ligne : aucune chaîne de type identifiant, aucun email, aucun token. Les correspondances d'un grep de secrets étaient toutes le `sk-3` de « task-316 ».
- Aucun test automatisé ajouté ni exécuté (règle de livraison du dépôt).

## Non atteignable depuis le worktree

Les vérifications listées dans « Notes à l'owner » de la description sont des régénérations d'artefacts sur `-dev` : elles supposent l'image Lambda du worker reconstruite et redéployée, ce qui se déclenche au push sur `main`, après la sortie de l'agent. Aucun AC ne les portait — elles restent la checklist de l'owner. Les six mesures du README (§2.1, §2.2, §2.4, §2.5, §2.8, §2.9) sont rejouables telles quelles une fois le déploiement fait, en filtrant sur `generator_version` en `:prompt-v4`.
<!-- SECTION:NOTES:END -->
