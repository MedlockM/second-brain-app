---
id: task-283
title: Corriger l’échec DynamoDB lors de la finalisation des artefacts IA
status: Done
assignee:
  - Codex
created_date: '2026-08-18 00:39'
updated_date: '2026-08-18 00:40'
labels:
  - backend
  - ai
  - bug
dependencies: []
priority: high
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
La génération LLM aboutit mais la finalisation de tout nouvel artefact échoue depuis le déploiement de task-270, car le coût mesuré est sérialisé comme float alors que DynamoDB exige Decimal. Le statut de repli doit également conserver un code d’erreur exploitable.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 La représentation DynamoDB d’un artefact terminé ne contient aucun float et conserve le coût LLM mesuré.
- [x] #2 Un échec interne sans code spécialisé persiste et expose le code INTERNAL_ERROR.
- [x] #3 ruff et mypy passent sur les fichiers backend concernés.
<!-- AC:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
1. Adapter MediaArtifactRecord.to_dynamodb_item pour sérialiser cost_eur en Decimal à la frontière DynamoDB, sans changer le type applicatif ni le JSON S3/API.
2. Garantir que fail_artifact_generation remplace un code absent par INTERNAL_ERROR afin que le statut failed reste typé.
3. Exécuter ruff et mypy de façon ciblée, inspecter le diff pour éviter secrets et changements hors périmètre, puis consigner les résultats et terminer la tâche.
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
## Correctif

- `MediaArtifactRecord.to_dynamodb_item()` convertit désormais `llm_usage.cost_eur` via `Decimal(str(...))` à la seule frontière DynamoDB. Le modèle applicatif reste en `float` et le contenu JSON S3 n’est pas modifié.
- `fail_artifact_generation()` accepte explicitement l’absence de code spécialisé et la normalise en `INTERNAL_ERROR` pour la persistance et les logs.

## Vérifications

- `ruff` ciblé : clean.
- `mypy` ciblé : clean sur les 2 fichiers modifiés.
- Vérification directe avec `boto3.dynamodb.types.TypeSerializer` : la représentation complète est acceptée et le coût `0.000123` ressort en `Decimal` sans perte textuelle.
- `git diff --check` et contrôle anti-secrets sur les fichiers du correctif : clean.
- Un passage `ruff` global a aussi été tenté, mais le worktree contient en parallèle des modifications Apify étrangères à cette tâche avec 19 erreurs en cours. Elles n’ont pas été touchées ; les fichiers de task-283 restent propres.
<!-- SECTION:NOTES:END -->
