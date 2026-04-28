---
id: task-12
title: Build notes generation capability as a first-class artifact
status: Done
assignee: []
created_date: '2026-02-23 22:08'
updated_date: '2026-03-15 21:01'
labels: []
dependencies:
  - task-11
  - task-34
priority: high
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Add a new notes artifact type with a structured output suitable for study/review workflows, consistent with the post-transcription experience.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 A notes artifact can be generated from an existing transcription through the shared artifact workflow.
- [x] #2 Notes output follows a documented structure usable by the client UI.
- [x] #3 Validation handles malformed model outputs with safe fallback behavior.
- [x] #4 Notes artifacts are stored and retrievable with the same durability guarantees as other artifacts.
- [x] #5 A validation checklist covers success and key failure paths for notes generation.
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Implémentation runtime du support `notes` démarrée et livrée sur le dépôt: `artifact_service` accepte désormais `notes` dans les types requestables et les defaults `ARTIFACT_TYPES_ALLOWED` sont alignés sur `summary,quiz,notes`.

Ajout d’un worker canonique `media_summarizer/workers/notes/worker.py` avec message identique aux autres artefacts, prompt study/review structuré, validation stricte du JSON (`objectives`, `concepts`, `key_points`, `action_items`, `glossary`) et échec explicite en `VALIDATION_ERROR` si la sortie modèle est mal formée.

Infra/dev alignée pour `notes`: nouveau service `notes-worker` dans `docker-compose.dev.yml`, bucket `media-summarizer-notes`, queue `notes-queue` + DLQ dans LocalStack/Terraform local, et helpers LocalStack mis à jour pour reconnaître les nouvelles ressources.

Documentation canonique mise à jour dans `docs/CANONICAL_MEDIA_API_CONTRACT.md` et `docs/CANONICAL_MEDIA_API_OPENAPI.yaml` pour figer la forme du contenu `notes` côté client.

Vérifications effectuées: import Python via `uv run python` de `artifact_service` et du nouveau worker `notes` OK; compilation en mémoire des fichiers Python modifiés OK; `bash -n infrastructure/localstack/init-aws.sh` OK; `docker compose -f docker-compose.dev.yml config` OK. Limite restante: pas de smoke end-to-end SQS/S3/Dynamo exécuté dans cette session.

Clôture demandée par l'utilisateur sur la base de l'implémentation livrée. Les critères d'acceptation sont considérés atteints pour cette tâche. Rappel: aucun smoke end-to-end SQS/S3/Dynamo supplémentaire n'a été exécuté dans cette session au moment du passage à Done.
<!-- SECTION:NOTES:END -->
