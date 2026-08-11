---
id: task-219
title: Establish durable canonical persistence for saved user media
status: To Do
assignee: []
created_date: '2026-08-02 22:38'
updated_date: '2026-08-11 14:22'
labels: []
dependencies:
  - task-218
priority: high
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Implement the durable persistence foundation selected by the owner in docs/research/task-218-durable-media-library-persistence/README.md. Saved user media and its organization metadata must have a durable source of truth independent of processing-job retention, while processing jobs remain free to expire according to their operational lifecycle.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 The implementation reads and follows the owner's final Decision in the task-218 research document
- [ ] #2 Every successful user save creates or reuses one durable user-owned media record through an idempotent path
- [ ] #3 The durable record preserves the identifiers and metadata required for library display, ownership, source attribution, folder membership, tags, lifecycle status, and artifact association
- [ ] #4 Deleting an expired processing job cannot delete or make the corresponding saved media record undiscoverable
- [ ] #5 Processing-job retention remains explicitly separate from user-library retention
- [ ] #6 Repeated submission of the same canonical media by the same user does not create duplicate durable library entries
- [ ] #7 Concurrent or partially failed ingestion cannot leave contradictory authoritative ownership or organization state
- [ ] #8 Infrastructure, runtime configuration, and deployment ordering support a safe rollout in the AWS dev environment
- [ ] #9 Durable records participate in the defined account-deletion, retention, backup, and recovery lifecycle
- [ ] #10 AWS dev verification demonstrates that a saved media record remains available after its associated processing job is absent
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
2026-08-10 — Dispatch interrompu : le run `dispatch_backlog.sh --max-dispatch 3` a été tué par un 403 Bedrock (`BedrockOfficeHoursDenyPolicy`, deny explicite sur `us.anthropic.claude-opus-5`), pas par une fin normale. Travail partiel sauvegardé sur la branche `recover/task-219` (commit c56c9d8, basé sur bcf0cfa) : ajout de `media_summarizer/core/models/user_media.py`, `core/services/user_media_service.py`, `utils/user_media.py` et modification de `core/models/__init__.py`. L'agent était encore en phase de reconnaissance/amorce — RIEN n'est relu ni testé, aucun critère d'acceptation vérifié. À la reprise : lire ce snapshot avant de recommencer, mais le considérer comme une piste, pas comme un acquis.

2026-08-11 — Deuxième tentative, également interrompue. L'agent est resté en phase de reconnaissance (routes du routeur media, gate d'ownership des artefacts, variables d'env des workers, tests et workflows CI, écritures de statut dans les workers) sans produire un seul fichier modifié — rien à sauvegarder pour ce run. `recover/task-219` (c56c9d8) reste le seul snapshot existant, inchangé. Deux runs consécutifs ont échoué à dépasser la phase d'analyse sur cette tâche : ses 10 critères couvrent modèle de données, idempotence, concurrence, rétention, infra et vérification AWS dev. Envisager de la découper avant un troisième dispatch.
<!-- SECTION:NOTES:END -->
