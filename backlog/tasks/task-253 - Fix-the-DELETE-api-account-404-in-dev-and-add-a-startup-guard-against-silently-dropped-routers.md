---
id: task-253
title: >-
  Fix the DELETE /api/account 404 in dev and add a startup guard against
  silently dropped routers
status: To Do
assignee: []
created_date: '2026-08-13 13:10'
labels:
  - bug
  - api
  - compliance
  - implementation
dependencies: []
priority: high
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
`DELETE /api/account`, shipped by task-224, returns `404` against the dev API. The route itself is correct — `media_summarizer/api/endpoints/account.py:27` declares `@router.delete("", status_code=204)` and `media_summarizer/api/main.py:148` mounts it under `/api/account`. The 404 has two candidate causes and the first must be ruled out before touching any code.

**Cause 1 — the code was very likely never deployed.** `deploy-lambda.yml` only fires on `push` to `main`, and task-224 (`24e9e3f`, 2026-08-12) is one of 53 commits sitting unpushed on local `main`; `origin/main` is still at `1d337e4`. A dev Lambda running a pre-task-224 image legitimately 404s, because the route did not exist in that image. Verify this first: compare the deployed dev Lambda image digest against the commit that introduced the route. If the image predates it, the fix is a push/deploy, not a code change — confirm the endpoint answers `204`/`401` (not `404`) on the redeployed image and close this task there.

**Cause 2 — an import-time crash on a missing environment variable.** Importing `media_summarizer.api.endpoints.account` transitively reaches `media_summarizer/utils/artifact_idempotence.py:18`, which calls `required_env("ARTIFACT_IDEMPOTENCE_TABLE")` at module scope and raises `RuntimeError` when it is unset. The chain is `account.py` → `account_deletion_service.py:65` → `media_purge_service.py:40` → `artifact_idempotence.py`. That import is reproducible locally today. In `main.py` the endpoint imports are a single unguarded `from ... import (...)` block, so a raise there kills the whole app rather than dropping one router — meaning under a plain ASGI server this would produce a total outage, not a per-route 404. If the Lambda handler or an adapter above it swallows import errors, or if a partially-initialised app is served, a single missing router is the shape you would see. Determine which of the two it is from the dev Lambda's cold-start logs before changing anything.

**Why this went unnoticed.** `tests/e2e/conftest.py:199-207` calls `DELETE /api/account` in teardown as best-effort and only prints the status code, so a `404` never fails a run. That masking is part of the bug: the teardown is the one place that exercises the shipped deletion path.

This matters beyond a broken route: in-app account deletion is required by App Store guideline 5.1.1(v), and `mobile/src/services/accountService.ts:22` is wired to this exact endpoint. If it 404s in prod, the mobile deletion flow is broken and the store commitment is not met.

Do not widen this into a refactor of every endpoint import. The guard asked for is a narrow startup assertion that the expected routers are actually mounted, so a dropped router fails loudly at boot instead of surfacing as a 404 months later.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 The root cause is established from evidence and written into the task's Implementation Notes: either the deployed dev image predates the commit that added the route, or an import-time failure is shown in the dev Lambda cold-start logs — not both, and not a guess
- [ ] #2 DELETE /api/account on the dev API no longer returns 404: an unauthenticated call returns 401 and an authenticated call on a throwaway account returns 204, verified against a deployed image whose digest is confirmed to contain the route
- [ ] #3 If the cause is the import-time RuntimeError, the module-scope required_env call reached via account.py no longer runs at import time, and importing media_summarizer.api.main with an unset ARTIFACT_IDEMPOTENCE_TABLE no longer raises
- [ ] #4 A startup check asserts that the routers main.py intends to mount are present in app.routes and fails loudly at boot when one is missing, covering at minimum the account router
- [ ] #5 The e2e teardown in tests/e2e/conftest.py no longer silently accepts a 404 from DELETE /api/account: an unexpected status is surfaced rather than only printed
- [ ] #6 A regression test exercises DELETE /api/account through the app (401 unauthenticated, 204 on a purgeable account) so the route's absence would fail the suite
- [ ] #7 ruff and mypy stay clean on the touched files
<!-- AC:END -->
