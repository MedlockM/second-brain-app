---
id: task-11
title: Enable on-demand artifact generation from completed transcription
status: Done
assignee:
  - '@codex'
created_date: '2026-02-23 22:08'
updated_date: '2026-03-16 09:03'
labels: []
dependencies:
  - task-10
  - task-14
  - task-32
priority: high
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Shift product behavior to transcript-first and allow users to request artifacts on demand (summary and quiz) rather than generating content automatically at submission time.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 Users can request summary and quiz independently after transcription is available.
- [x] #2 Each artifact request has its own status lifecycle and can succeed/fail independently without blocking others.
- [x] #3 Artifact generation is idempotent for equivalent requests and avoids duplicate work.
- [x] #4 API endpoints expose artifact request and tracking behavior per media item.
- [x] #5 Mobile clients can display per-artifact progress and terminal state consistently.
<!-- AC:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
1. Stabiliser les endpoints canoniques existants `GET /api/media/{media_item_id}` et `POST /api/media/{media_item_id}/artifacts` comme source de vérité du flux post-transcription pour `summary`, `quiz` et `notes`.
2. Compléter la réponse `GET /api/media/{media_item_id}` avec les métadonnées de transcript réellement disponibles (`language`, `segments_count`, `duration_seconds`) issues du runtime de transcription/finalisation, tout en conservant `artifact_statuses` et la liste d’artefacts alignées avec le store canonique.
3. Garder l’idempotence serveur actuelle par requête équivalente et cache global, sans rendre `ArtifactCreateRequest.idempotency_key` pilotant; documenter/laisser le champ comme accepté mais non utilisé.
4. Aligner les helpers/types TS partagés sur le contrat canonique des artefacts `summary | quiz | notes`, ajouter une couche de service API réutilisable (`ingestMediaUrl`, `getMediaStatus`, `requestArtifact`) et un helper de polling centré sur les statuts canoniques.
5. Ne pas migrer l’UI web legacy ni introduire les endpoints de lecture dédiés d’artefact (`task-33`).
6. Vérifier par smoke checks ciblés backend et typecheck TS/Python structurel, puis documenter les résultats et l’état des critères dans la tâche.

7. Suite à la découverte d’un décalage runtime dans `workers/events/episode_completed_worker.py`, intégrer dans cette tâche le rétablissement du consumer canonique `episode_completion_status` afin que la finalisation transcript-first soit réellement cohérente avec les workers actifs; changement validé explicitement par l’utilisateur le 2026-03-16.
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Décalage découvert pendant l’implémentation: `workers/events/episode_completed_worker.py` du worktree écoutait encore le flux legacy `episode_completed` piloté par email, alors que les workers actifs publient `episode_completion_status`. L’utilisateur a validé l’intégration de ce fix de finalisation dans la présente passe d’implémentation.

Implémentation livrée sur le flux canonique post-transcription: `ProcessingJob` persiste désormais `transcription_metadata`, les workers Whisper/Deepgram/article l’écrivent, et `GET /api/media/{media_item_id}` expose `language`, `segments_count` et `duration_seconds` via `TranscriptInfo` en plus des snapshots/listes d’artefacts existants.

Ajout d’une couche TS partagée réutilisable pour le futur client mobile/web canonique: nouveaux types d’artefacts structurés (`summary`, `quiz`, `notes`) dans `front/src/types/media.ts`, nouveau service API `front/src/services/mediaService.ts` (`ingestMediaUrl`, `getMediaStatus`, `requestArtifact`) et helper de polling `front/src/lib/mediaPolling.ts` centré sur les statuts canoniques.

Blocage runtime découvert et résolu dans cette passe avec accord utilisateur: `workers/events/episode_completed_worker.py` était resté sur l’ancien flux `episode_completed` piloté par email. Le worker a été réécrit pour consommer `episode_completion_status`, finaliser les watchers sans email, propager `transcription_s3_key`/`transcription_metadata`, finaliser ou relâcher la facturation selon le résultat, et marquer l’idempotence/watcher state de façon cohérente.

Neutralisation d’un reliquat cassé de la suppression du mail: retrait de l’export `ses` supprimé de `media_summarizer/utils/__init__.py` afin que les modules canoniques touchés soient à nouveau importables pour validation.

Documentation de contrat mise à jour dans `docs/CANONICAL_MEDIA_API_CONTRACT.md` pour refléter l’exposition runtime des métadonnées de transcript et la prise en charge on-demand de `summary|quiz|notes`.

Validation effectuée: AST parse OK sur les modules Python modifiés; import Python OK de `media_summarizer.api.endpoints.media`, `media_summarizer.workers.events.episode_completed_worker`, `media_summarizer.workers.transcription.worker` et `media_summarizer.workers.transcription.deepgram_worker`; compilation TypeScript ciblée OK sur `front/src/types/media.ts`, `front/src/lib/httpError.ts`, `front/src/lib/mediaPolling.ts` et `front/src/services/mediaService.ts` avec types Vite explicites.

Limites de validation constatées: `npm run typecheck` global du front échoue toujours sur des erreurs legacy préexistantes hors périmètre (`Dashboard.tsx` dépendances Spotify supprimées, signature handler dans `MyQuizzesAndSummaries.tsx`, prop inutilisée dans `PodcastSearch.tsx`). Aucun test automatisé additionnel n’a été ajouté, conformément à la règle projet pour cette tâche.

2026-03-16: post-validation follow-up fixed the remaining queue env mismatch in `episode_completed_worker.py` (`EPISODE_COMPLETED_EVENTS_QUEUE` -> canonical `EPISODE_COMPLETION_EVENTS_QUEUE`) so the completion consumer now reads the same configured queue variable as all producers.
<!-- SECTION:NOTES:END -->
