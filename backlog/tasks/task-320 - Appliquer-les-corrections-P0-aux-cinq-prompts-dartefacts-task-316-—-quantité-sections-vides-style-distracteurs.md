---
id: task-320
title: >-
  Appliquer les corrections P0 aux cinq prompts d'artefacts (task-316) —
  quantité, sections vides, style, distracteurs
status: To Do
assignee: []
created_date: '2026-08-25 11:42'
updated_date: '2026-08-25 11:44'
labels:
  - artifacts
  - prompt-engineering
  - backend
dependencies: []
priority: high
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
## Contexte

L'analyse `docs/research/task-316-artifact-prompts/README.md` (`owner_decision: ok`) mesure les défauts des cinq prompts de génération d'artefacts sur les 14 artefacts `prompt-v2` produits en dev. Cette tâche implémente **les quatre propositions P0** de la section 4 du README, plus l'exigence d'exhaustivité posée par l'owner dans sa décision.

Lis le README avant de commencer : il donne pour chaque proposition le fichier et la ligne où intervenir, le texte à écrire, et la mesure à rejouer. Les P1 sont traités par task-321 qui dépend de celle-ci, et **les P2 sont hors périmètre — n'y touche pas** (pas de structured outputs sur les trois types restants, pas de changement de modèle ni de repli, pas d'instrumentation des reasoning tokens).

## Périmètre

- **P0-1** — rendre la quantité fonction de la matière : abaisser `MIN_FLASHCARDS` (`flashcards.py:17-18`) et `MIN_QUESTIONS` (`quiz.py:19-20`) de 5 à 1, ne garder en rejet dur que le cas zéro élément dans les `validate()` (`flashcards.py:155`, `quiz.py:223`), et remplacer les fourchettes dures des cinq blocs d'instructions par des règles adossées à la matière réellement enseignée.
- **Exhaustivité, dans le même mouvement** — la décision de l'owner demande que l'artefact soit **exhaustif** : « le quiz doit adapter sa longueur pour couvrir tous les points du media ». C'est le pendant haut de P0-1, dont le README ne traite que le pendant bas. Le plafond dur de 15 items doit donc devenir lui aussi fonction de la matière : la borne haute est le nombre de points distincts que les sources enseignent, pas une constante. Cette exigence est structurelle et non cosmétique, parce que task-322 rend la génération d'un artefact de média **unique** : il n'y a pas de seconde passe pour rattraper une couverture partielle. Applique la même logique de couverture aux cinq types, chacun dans sa forme (items de quiz, cartes, puces, concepts).
- **P0-2** — autoriser une section, et un artefact, vide : clause de sortie explicite dans les cinq prompts ; rendre `takeaway` facultatif dans le prompt **et** dans `SummaryShortContent` (`summary_short.py:33-40`, aujourd'hui contraint non vide par `_non_empty_text`). Aucun changement mobile nécessaire — l'écran masque déjà les sections vides. Cette clause et l'exhaustivité ne se contredisent pas : couvrir tout ce que les sources enseignent, et rien de plus, c'est la même règle vue des deux bouts.
- **P0-3** — interdire le style méta-référentiel : nouveau fragment partagé dans `corpus.py` (sur le modèle de `title_instruction()`), inclus par les cinq types, avec l'unique exception de `notable_quotes` qui est verbatim par construction.
- **P0-4** — casser le biais de longueur des distracteurs de quiz (`quiz.py:103-125`) : contrainte de calibre comparable entre les quatre options, distracteurs rédigés avant la bonne réponse. Commence par le prompt seul ; le garde-fou optionnel dans `validate()` ne se décide qu'après mesure, donc ne l'ajoute pas.
- **Bump de version** — passer les cinq entrées de `get_generator_version()` (`artifact_service.py:203-225`) de `prompt-v2` à `prompt-v3`. Sans ce bump l'historique ne permet plus de rattacher un artefact au prompt qui l'a produit, et c'est ce champ qui a permis d'isoler les 14 artefacts analysés.

## Hors périmètre

- Les P1 (corpus hétérogène, couverture multi-sources, `importance`, faits datés, marqueurs de transcription, langue) — task-321.
- Tous les P2.
- Le cycle de vie génération unique / cache / régénération de collection — task-322. Ne touche pas à `build_artifact_id()` ni à `plan_artifact_generation()`.
- **P1-7 est annulé** par la décision de l'owner : il n'y aura pas de régénération au niveau d'un média, donc aucun levier de diversité à la régénération n'est à construire.

## Notes à l'owner (non vérifiables par l'agent)

Après déploiement, le plus court chemin pour juger l'effet est de régénérer les cinq types sur le sketch de 414 o (`mi_6c142cb699dc4d8dbd0df65500660df0`, cas dégénéré) et sur le cours de surf de 17,7 ko (cas dense), puis de recalculer les ratios des §2.1, §2.2, §2.4 et §2.5. Cibles indiquées par le README : ratio sortie/source < 1 sur la source courte, volume en hausse sur la source dense, part des bonnes réponses les plus longues proche de 25 % (contre 66 %), questions méta-référentielles en net recul (contre 39 %). Le point à juger en propre sur l'exhaustivité est le cas dense : le quiz du cours de surf doit couvrir sensiblement plus de points qu'aujourd'hui, sans remplissage.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 Les planchers de quantite de flashcards et quiz sont abaisses a 1 dans les constantes, et les validate() correspondants ne rejettent plus que le cas zero element
- [ ] #2 Les cinq blocs d'instructions expriment la quantite comme une fonction de la matiere enseignee par les sources, sans fourchette plancher dure, et interdisent explicitement le remplissage
- [ ] #3 Le plafond dur de 15 items ne borne plus la sortie : les cinq prompts demandent de couvrir tous les points distincts enseignes par les sources, chacun dans sa forme propre
- [ ] #4 Les cinq prompts autorisent explicitement une section vide, et SummaryShortContent n'impose plus takeaway non vide
- [ ] #5 Un fragment partage de corpus.py interdit le style meta-referentiel et est inclus par les cinq generateurs, avec l'exception notable_quotes
- [ ] #6 Le prompt quiz impose des options de calibre comparable et l'ordre de redaction distracteurs-puis-bonne-reponse, sans nouveau rejet dans validate()
- [ ] #7 Les cinq entrees de get_generator_version() dans artifact_service.py sont passees de prompt-v2 a prompt-v3
- [ ] #8 Aucune proposition P1 ni P2 du README n'est implementee, et build_artifact_id() comme plan_artifact_generation() sont inchanges

- [ ] #9 ruff et mypy passent sur les fichiers modifies
<!-- AC:END -->
