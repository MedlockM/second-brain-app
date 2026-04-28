---
id: task-13
title: Remove Spotify sync and playlist tracking feature across stack
status: Done
assignee:
  - '@codex'
created_date: '2026-02-23 22:08'
updated_date: '2026-02-24 00:07'
labels: []
dependencies:
  - task-16
  - task-17
priority: high
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Current state (to remove): Spotify sync and playlist tracking is still spread across API routes, frontend screens/services, worker logic, user model fields, tests/scripts/docs, and infra resources.

Goal: fully remove the Spotify sync/playlist tracking product surface so the roadmap is focused on share-first URL ingestion and post-transcription artifacts.

Scope:
- Remove Spotify sync/playlist product flows end-to-end (backend/frontend/workers/infra/config/docs/tests/scripts).
- Ensure no dead references remain in router wiring, UI navigation, env templates, test fixtures, CI scripts, or runbooks.
- Preserve non-Spotify core capabilities (auth baseline, ingestion/transcription pipelines, billing/minutes behavior).

Must remove/refactor in this task:
- API/router
  - Remove router wiring in `media_summarizer/api/main.py` for `spotify_sync` and `spotify_playlists` endpoints.
  - Remove Spotify endpoints module files if no longer used: `media_summarizer/api/endpoints/spotify_sync.py`, `media_summarizer/api/endpoints/spotify_playlists.py`.
  - In `media_summarizer/api/endpoints/auth_social.py`, remove only Spotify-specific endpoints/vars (`/spotify/auth-url`, `/spotify/login`, `/spotify/callback`, `/spotify/status`, `/spotify/unlink`, Spotify env vars/scopes), keep Google/Apple flows intact.
- Domain/services/utils
  - Remove Spotify-only workers/services/utils: `media_summarizer/workers/spotify_sync/*`, `media_summarizer/utils/spotify.py`, `media_summarizer/utils/spotify_follows_db.py`, `media_summarizer/core/models/spotify.py`.
  - Remove Spotify-only fields from `media_summarizer/core/models/user.py` if no longer needed by any runtime path.
  - Remove/retire Spotify sync orchestrators `media_summarizer/core/services/playlist_sync.py` and `media_summarizer/core/services/tosum_sync.py` after extracting reusable non-Spotify logic (see keep section).
- Frontend
  - Remove Spotify UX and API clients: `front/src/services/spotifyService.ts`, `front/src/components/ui/spotify-integration-home.tsx`, `front/src/components/SpotifyPlaylists.tsx`, `front/src/components/SpotifySync.tsx`.
  - Refactor dependent screens/services: `front/src/components/Dashboard.tsx`, `front/src/components/AccountSettings.tsx`, `front/src/services/settingsService.ts`, `front/src/components/OAuthCallback.tsx`, plus any Spotify-specific copy in Terms/Privacy/Landing/error mapping.
- Infra/config
  - Remove Spotify IaC/resources: `infrastructure/terraform/aws/spotify_sync.tf`, `infrastructure/terraform/dynamodb_spotify_follows.tf`, Spotify resources/vars in `infrastructure/terraform/localstack/main.tf`, and related docker-compose env wiring.
  - Remove Spotify lambda artifacts/scripts and scheduler scripts if dedicated to Spotify only.
  - Deprecate/remove Spotify env vars from `.env.example` and deployment docs.
- Tests/docs/scripts
  - Remove or refactor Spotify-only tests and localstack fixtures referencing spotify workers/endpoints/resources.
  - Archive or update Spotify-specific docs/runbooks/manual test guides.

Must keep / reusable (do not lose):
- Keep non-Spotify OAuth providers and baseline auth flows in `auth_social.py` (Google/Apple).
- Keep generic dedup/processing primitives (`user_episode_submissions`, `episode_submission`, minute pool, queue workers not Spotify-specific).
- Before deleting `playlist_sync.py`/`tosum_sync.py`, extract reusable podcast title-matching normalization/heuristics (`_normalize`, `_best_match_episode`) to a provider-agnostic module for future podcast platform resolution.

Out of scope:
- Removing unrelated social auth providers (Google/Apple/local auth).
- Implementing new ingestion/artifact functionality (covered by other tasks).

Definition of done emphasis:
- A new chat/new agent can execute this removal safely from this task alone.
- Repository builds/tests pass with Spotify sync surface removed and no orphan references.
- Reusable matching logic is preserved in a non-Spotify module before Spotify service deletion.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 Spotify sync/playlist endpoints are removed from API routing and are no longer reachable in the public surface.
- [x] #2 Frontend no longer exposes Spotify connect, playlist management, or Spotify sync tracking UX.
- [x] #3 Spotify-sync-only workers/services/utilities are removed (or fully disabled with no runtime path), with no dead imports/references remaining.
- [x] #4 Infrastructure resources dedicated to Spotify sync (tables/queues/lambdas/schedules/permissions) are removed or explicitly decommissioned in IaC.
- [x] #5 Configuration/docs/env templates are updated to deprecate Spotify-sync-only variables and operational steps.

- [x] #6 Regression checks confirm non-Spotify core flows still work (auth baseline, content submission/processing path, and primary user navigation).
- [x] #7 A migration note is documented for existing environments/data (what to clean up and in which order).

- [x] #8 Google/Apple social auth flows continue to work after Spotify endpoint removal from `auth_social.py` (no regression on non-Spotify providers).
- [ ] #9 Reusable podcast title-matching logic previously embedded in Spotify sync services is extracted to a provider-agnostic module and covered by tests before those services are deleted.

- [x] #10 Deletion of `playlist_sync.py`/`tosum_sync.py` is blocked until task-16 is completed (extract-first rule).
- [x] #11 Deletion/removal of per-user duplicate-guard behavior is blocked until task-17 provides media-keyed parity behavior (adapt-first rule).

- [x] #12 Because the product is pre-production, no backward-compatibility shim for Spotify legacy APIs/workers is retained after reusable logic extraction; legacy paths are removed, not preserved behind flags.
<!-- AC:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
1) Backend API: retirer le wiring des routes Spotify dans `api/main.py`, supprimer `api/endpoints/spotify_sync.py` et `api/endpoints/spotify_playlists.py`, puis nettoyer `api/endpoints/auth_social.py` pour ne garder que Google/Apple.
2) Domaine/services/workers: supprimer les modules Spotify dédiés (`core/services/playlist_sync.py`, `core/services/tosum_sync.py`, `utils/spotify.py`, `utils/spotify_follows_db.py`, `core/models/spotify.py`, `workers/spotify_sync/*`) et retirer les champs Spotify du modèle `User`.
3) Frontend: retirer l’UX Spotify (`spotifyService`, composants Spotify), refactorer `Dashboard`, `AccountSettings`, `OAuthCallback`, `settingsService` et nettoyer les textes/copy Spotify.
4) Infra/config/scripts/docs: retirer ressources Terraform/env Spotify, nettoyer `docker-compose.dev.yml`/`Makefile`, supprimer scripts/runbooks Spotify dédiés et mettre à jour la doc opérationnelle.
5) Validation & finition: recherche globale des références Spotify résiduelles, corrections des imports cassés, vérification syntaxique légère des fichiers Python/TS modifiés, puis mise à jour des notes et critères du ticket (sans ajout de tests selon consigne utilisateur).
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Legacy policy for this project: because the application is not yet in production, backward compatibility is NOT required for Spotify-related legacy surfaces. The implementing agent should remove legacy code and all references directly once reusable logic has been extracted/preserved in non-Spotify modules (see task-16/task-17). Prefer deletion over feature flags/shims for Spotify legacy paths.

Consigne utilisateur explicite: ne pas implémenter de nouveaux tests pour ce ticket.

Suppression finale des surfaces Spotify sync/playlist tracking: modules API/workers/services/utils dédiés retirés, routes Spotify supprimées, UI/frontend Spotify retirée, modèles/champs Spotify du user retirés.

Nettoyage infra/scripts/docs dédiés: suppression des fichiers Terraform Spotify (`infrastructure/terraform/aws/spotify_sync.tf`, `infrastructure/terraform/dynamodb_spotify_follows.tf`), artefacts/schedulers/scripts Spotify, runbooks Spotify dédiés, et MAJ docs auth/frontend.

Ajout d'une note de migration/décommissionnement pour environnements existants: `docs/SPOTIFY_SYNC_DECOMMISSIONING.md` (ordre de cleanup: schedule -> lambda/event mapping -> queues -> tables -> config/secrets).

Validation technique: `openapi.json` régénéré (0 route Spotify), présence confirmée des routes OAuth Google/Apple, parsing syntaxique Python OK sur fichiers modifiés.

Vérification frontend: `npm run -s typecheck` exécuté, échec sur erreurs préexistantes non liées Spotify (`MyQuizzesAndSummaries.tsx` handler typing, `PodcastSearch.tsx` variable inutilisée).

Conformément à la consigne utilisateur explicite, pas d'ajout de tests pour ce ticket; le critère de tests liés à l'extraction (AC #9) reste non coché.
<!-- SECTION:NOTES:END -->
