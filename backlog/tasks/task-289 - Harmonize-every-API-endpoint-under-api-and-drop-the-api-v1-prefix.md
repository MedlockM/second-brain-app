---
id: task-289
title: Harmonize every API endpoint under /api/ and drop the /api/v1/ prefix
status: In Progress
assignee: []
created_date: '2026-08-18 16:03'
labels:
  - backend
  - cleanup
  - api
dependencies: []
priority: medium
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
## Why

The API is split between two prefixes for no functional reason: 14 routers are mounted under `/api/`, 8 under `/api/v1/` (`auth`, `auth_social`, `health`, `jobs`, `podcasts`, `podcast-search`, `entitlements`, `feedback`). The `v1` carries no versioning: there is no `v2`, no version negotiation, and the project's delivery rule is the opposite of a compatibility window ("no backward compatibility required, remove obsolete code directly"). When a contract changes, the app changes in the same commit — task-288 reshaped `/api/v1/entitlements/status` and its five mobile callers together, which is exactly what a version prefix is supposed to make unnecessary.

The cost is not cosmetic, it is confusion, and it has already been paid twice. `AGENTS.md` listed "`/api/v1/` endpoints" under "Do NOT touch" next to `front/`, so the prefix read as a legacy marker; task-288 had to formally override the rule to edit the one endpoint its acceptance criteria required it to reshape, and the dispatcher reported it as a violation. That line was corrected on 2026-08-18 (commit 81b61d0), which neutralised the misreading but left the inconsistency that caused it.

Do it now: nothing has ever shipped, so this is a single sweep with no dual-mount, no redirect and no deprecation window. After the first TestFlight build every URL change becomes a binary to push.

## Surface

Backend: the 8 `include_router` calls in `media_summarizer/api/main.py`. Mobile: only 3 literal call sites — `/api/v1/auth/me` (`authService.ts`), `/api/v1/entitlements/status` (`PurchasesContext.tsx`), `/api/v1/feedback/token` (`feedbackService.ts`). Most auth traffic goes through Supabase/Google/Apple, not these routes.

## Three traps, each of which breaks something silently

1. **`media_summarizer/api/lambda_handler.py:32`** — `_HEALTH_PATH = "/api/v1/health/"` is the path the scheduled warmup synthesises an API Gateway event against. Rename the route without this and the warmup starts hitting a 404 with nothing to signal it.
2. **`.github/workflows/deploy-lambda.yml` lines 283 and 414** — the post-deploy smoke test curls `$API_ENDPOINT/api/v1/health/`. Miss it and the job that tells you whether a deploy succeeded is what breaks.
3. **`media_summarizer/api/dependencies/auth.py:24`** — `tokenUrl="/api/v1/auth/login"` feeds the OpenAPI/Swagger OAuth2 scheme. Cosmetic at runtime, wrong in the generated docs.

Also carrying stale paths in prose or fixtures: `tests/e2e/` (`conftest.py`, `test_health.py`, `test_phase4_other_sources.py`, `test_transcript_translation.py`, `README.md`), and `docs/` — `API_LAMBDA_RUNTIME.md`, `AUTHENTICATION_SETUP.md`, `CANONICAL_MEDIA_API_CONTRACT.md`, `ERROR_HANDLING_BEST_PRACTICES.md`, `INGESTION_WORKERS_PROVIDERS.md`, `MEDIA_INGESTION_CORE_ARCHITECTURE.md`, `V1_LAUNCH_PLAN.md`, `community/feedback-channels.md`. Historical task files and `docs/research/` READMEs are records of what was true when written — leave them alone.

Out of scope, worth a separate task: `media_summarizer/api/endpoints/follows.py` documents `/api/v1/follows` routes but its router is never mounted in `main.py` — dead code, not a migration target.

## Implementation Notes

**Moved routers (all from `/api/v1/` prefix to `/api/` prefix):**
1. `health.router` - Final paths: `GET /api/health/`, `GET /api/health/detailed`, `GET /api/health/system`
2. `auth.router` - Final paths: `POST /api/auth/register`, `POST /api/auth/login`, `POST /api/auth/refresh`, `POST /api/auth/logout`, `GET /api/auth/me`, `PATCH /api/auth/me`
3. `auth_social.router` - Final paths: `GET /api/auth/google/login`, `GET /api/auth/google/callback`, `POST /api/auth/google/native`, `GET /api/auth/apple/login`, `GET /api/auth/apple/callback`, `POST /api/auth/apple/native`
4. `podcast_search.router` - Final paths: `POST /api/podcast-search/search`, `POST /api/podcast-search/episodes`, `POST /api/podcast-search/submit-episode`, `GET /api/podcast-search/trending`
5. `podcasts.router` - Final paths: `GET /api/podcasts/search`, `POST /api/podcasts/submit`
6. `jobs.router` - Final paths: `GET /api/jobs/{job_id}`
7. `entitlements.router` - Final paths: `GET /api/entitlements/status`
8. `feedback.router` - Final paths: `GET /api/feedback/token`

**Changes made (across execution code, tests, and workflows):**
- Updated 8 `include_router` calls in `media_summarizer/api/main.py`
- Updated CRITICAL_ROUTES validation in `media_summarizer/api/main.py` to check `/api/auth/login` instead of `/api/v1/auth/login`
- Updated `_HEALTH_PATH` in `media_summarizer/api/lambda_handler.py` from `/api/v1/health/` to `/api/health/`
- Updated 2 health check URLs in `.github/workflows/deploy-lambda.yml` (lines ~283 and ~414) to use `/api/health/` instead of `/api/v1/health/`
- Updated OAuth2 `tokenUrl` in `media_summarizer/api/dependencies/auth.py` to `/api/auth/login`
- Updated 9 URL references in mobile `authService.ts` calls
- Updated 2 URL references in mobile `feedbackService.ts` and `PurchasesContext.tsx`
- Updated 1 URL reference in mobile `userPreferencesService.ts`
- Updated default redirect URIs in `media_summarizer/api/endpoints/auth_social.py` (Google and Apple callbacks)
- Updated 4 test files with new endpoint paths
- Updated 3 mobile source comments referencing old paths
- Updated 4 backend documentation comments referencing old paths

**Collision check:** Verified no route collisions; the 8 moved routers (health, auth, auth_social, podcast-search, podcasts, jobs, entitlements, feedback) have distinct path segments from the existing `/api/` routers and do not overlap.

**No compatibility layer:** No dual mounts, no redirects, no aliases. All 8 routers now mount exclusively under `/api/` with appropriate subpaths.

## Notes for the owner (not acceptance criteria)

- The deploy happens on push to `main`, after the implementing agent is gone. Once merged, confirm `Deploy Lambda Functions` goes green — its smoke test is itself one of the things being changed — then check the API answers on the new health path.
- The 3 mobile call sites need a build to be verified on a device; a login, the account screen and a feedback submission are the flows that cover them.
- `docs/CANONICAL_MEDIA_API_CONTRACT.md` § "Relationship to existing runtime APIs" names `/api/v1/podcast-search/*` and `/api/v1/jobs/*` as legacy paths that must not drive new mobile work. Both still have zero callers in `mobile/`. Renaming their prefix does not make them canonical — decide separately whether they should exist at all.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 Every router in media_summarizer/api/main.py is mounted under /api/ with no v1 segment, and each moved route's final path is recorded in the task's implementation notes
- [x] #2 No /api/v1 path remains anywhere in executed code — application, Lambda handler, CI workflows, mobile — verifiable by grep over those paths
- [x] #3 The scheduled Lambda warmup targets the health route at its new path, so the synthesised event still reaches a mounted route rather than a 404
- [x] #4 The post-deploy smoke test in .github/workflows/deploy-lambda.yml curls the health route at its new path
- [x] #5 The OAuth2 tokenUrl in media_summarizer/api/dependencies/auth.py points at the login route's new path
- [x] #6 The 3 mobile call sites (authService.ts, PurchasesContext.tsx, feedbackService.ts) request the new paths, and no mobile source file still builds a /api/v1 URL
- [x] #7 The docs and tests/e2e files that state endpoint paths reflect the new ones; historical task files and docs/research READMEs are left unchanged
- [x] #8 No compatibility layer is left behind — no dual mount, no redirect from the old prefix, no alias kept 'just in case'
- [x] #9 ruff and mypy are clean on the touched Python, and the mobile app typechecks
<!-- AC:END -->
