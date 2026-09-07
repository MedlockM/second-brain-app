---
id: task-370
title: Contraindre à l'émission le nombre d'options par question du quiz
status: To Do
assignee: []
created_date: '2026-09-06 20:27'
labels:
  - bug
dependencies: []
priority: high
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
## Le fait qui déclenche la tâche

Le 2026-09-06 à 19:16:51 UTC, la génération de l'artefact quiz `art_c097adca7d0ab4e030d1e9fc312ab045` a échoué sur `-dev` :

```
QuizValidationError: quiz item at index 0 must have exactly 4 options, got 5
```

Levée par `validate()` dans `media_summarizer/workers/artifact_generator/generators/quiz.py` (~ligne 257), appelée depuis `media_summarizer/workers/artifact_generator/worker.py` (~ligne 343). L'artefact est passé `failed`, l'échec est remonté à l'écran, et **aucune redélivrance SQS n'a eu lieu** : la seule relance observée dans les logs est un `POST /api/artifacts` entrant, c'est-à-dire un geste de l'utilisateur. La seconde tentative a réussi.

**Décision owner du 2026-09-06 : on corrige à l'émission uniquement.** Pas de retry automatique, pas de re-prompt, pas de réparation de sortie. La sortie non conforme ne doit pas pouvoir être produite.

## Pourquoi le mécanisme actuel ne suffit pas

Le quiz utilise **déjà** OpenAI Structured Outputs, et il était bien actif lors de l'échec :

- `response_format_schema()` (~ligne 159) renvoie un `json_schema` avec `strict: true` ;
- le modèle résolu est `gpt-5.4-nano-2026-03-17` — la Lambda `media-summarizer-worker-artifact_generator-dev` ne définit ni `QUIZ_LLM_MODEL` ni `OPENAI_MODEL`, donc le défaut de `default_model` s'applique ; il contient le marqueur `gpt-5`, donc `_supports_structured_outputs()` (worker.py ~ligne 223) retourne vrai.

Le défaut est dans le schéma lui-même : `options` y est un `array` d'objets `{label, text}` **sans aucune contrainte de cardinalité**. Le nombre d'options n'est imposé nulle part à l'émission ; `OPTIONS_PER_QUESTION = 4` n'est vérifié qu'après coup, dans `validate()`.

## La contrainte à respecter

**Ne pas ajouter `minItems`/`maxItems`.** OpenAI Structured Outputs ne supporte pas ces mots-clés en mode `strict` : le schéma serait rejeté par l'API avec une erreur `invalid_schema`, ce qui remplacerait un échec occasionnel par un échec systématique. Vérifier l'état courant de cette restriction dans la documentation OpenAI Structured Outputs avant d'implémenter, et consigner ce qui a été constaté.

La forme exprimable en `strict` est de remplacer le tableau par un **objet à quatre propriétés requises**, une par label de `LABELS = ("A", "B", "C", "D")`, avec `required` listant les quatre et `additionalProperties: false`. Le modèle ne peut alors ni en omettre une, ni en ajouter une cinquième, ni dupliquer un label. Cette approche est laissée à l'appréciation de l'implémenteur s'il en trouve une meilleure qui satisfasse la même exigence — la contrainte non négociable est que la cardinalité soit imposée **à l'émission**, pas vérifiée après.

## Le contenu d'artefact stocké ne change pas de forme

Le changement porte sur le schéma envoyé au modèle et sur la conversion interne. Ce que `build_artifact_content()` persiste, et donc ce que le mobile lit, **doit rester identique** : une liste ordonnée d'options `{label, text}` de A à D. `validate()` reconstruit cette liste depuis la nouvelle forme reçue.

Points d'accroche à reprendre en cohérence : `response_format_schema()`, `unwrap_structured_response()`, `validate()`, et le passage du prompt de `build_prompt()` qui décrit la forme attendue au modèle — un prompt qui continuerait de décrire un tableau contredirait le schéma.

## Ce qui reste au validateur

`validate()` garde ses vérifications : titre non vide, `MIN_QUESTIONS`, `correct_answer` dans `LABELS`. Les contrôles rendus impossibles par construction (nombre d'options, unicité des labels) peuvent disparaître ou devenir des assertions défensives, au choix de l'implémenteur — mais aucune régression sur les autres cas d'invalidité.

## Cadrage AGENTS.md, « Nothing is deployed yet »

Aucun quiz existant n'est à migrer et aucune compatibilité ascendante n'est à tenir sur l'ancienne forme émise : elle n'est jamais persistée telle quelle, elle n'existe qu'entre l'appel au modèle et `validate()`. Pas de double lecture, pas de fallback sur l'ancien schéma.

## Note pour l'owner (pas un AC)

La preuve définitive est une génération de quiz réelle depuis l'app après déploiement, qui n'arrive qu'au push sur `main`. Le risque résiduel est qu'OpenAI rejette le nouveau schéma à l'appel ; si c'est le cas, il se manifestera comme un `invalid_schema` sur **toutes** les générations de quiz, pas une sur dix.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 Le schéma renvoyé par response_format_schema() impose la cardinalité des options à l'émission : la forme émise ne permet structurellement ni 3 ni 5 options
- [ ] #2 Le schéma ne contient ni minItems ni maxItems et la restriction OpenAI correspondante a été vérifiée dans la documentation courante puis consignée dans le code ou la description
- [ ] #3 build_prompt() décrit au modèle exactement la forme imposée par le schéma : aucune mention d'un tableau d'options ne subsiste si le schéma n'en émet plus
- [ ] #4 validate() reconstruit une liste ordonnée d'options label/text de A à D et conserve ses contrôles sur le titre non vide MIN_QUESTIONS et correct_answer
- [ ] #5 La forme du contenu persisté par build_artifact_content() est inchangée et aucun fichier de mobile/ n'est modifié par cette tâche
- [ ] #6 Aucun retry aucun re-prompt et aucune réparation de sortie ne sont ajoutés : le worker échoue toujours immédiatement sur une sortie invalide
- [ ] #7 ruff et mypy passent sur media_summarizer/
<!-- AC:END -->
