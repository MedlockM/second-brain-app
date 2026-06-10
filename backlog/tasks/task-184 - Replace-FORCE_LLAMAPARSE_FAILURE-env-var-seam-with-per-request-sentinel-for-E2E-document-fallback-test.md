---
id: task-184
title: >-
  Replace FORCE_LLAMAPARSE_FAILURE env-var seam with per-request sentinel for
  E2E document fallback test
status: Done
assignee: []
created_date: '2026-06-10 14:26'
updated_date: '2026-06-10 15:05'
labels:
  - test
  - ingestion
  - cleanup
dependencies: []
priority: medium
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
The current `tests/e2e/test_fallback_chains.py::test_document_unstructured_fallback` design forces the Unstructured fallback by toggling `FORCE_LLAMAPARSE_FAILURE` on the document-parsing Lambda via `lambda:UpdateFunctionConfiguration` before submitting the file, then restoring the previous env in `finally`.

**Why it's broken:**
- AWS propagates Lambda config asynchronously: a warm container can serve the next invocation with the *previous* environment for 5–30s
- E2E run 2026-06-10 confirmed this: the test invocation hit `LlamaParse upload successful` / `document_parsing.primary_success` (provider=llamaparse) — the `FORCE_LLAMAPARSE_FAILURE` value was never read by that container
- Adding a `lambda:UpdateFunctionConfiguration` waiter would fix the race but lengthens the test by 5–30s and keeps the global env-var seam

**Proposed redesign — per-request sentinel:**
- Move the test seam from a global Lambda env var to a request-scoped hook inside the LlamaParse resolver
- The resolver returns `ParseError` early when the incoming request carries a sentinel marker (e.g. uploaded filename starts with `__e2e_force_llamaparse_failure__`)
- The test simply uploads `__e2e_force_llamaparse_failure__sample.pdf` — no Lambda config touched, no waiter, no `try/finally` restore, no `lambda:UpdateFunctionConfiguration` IAM requirement on the runner
- Deterministic on the very first invocation; no cold-start dance

This also removes `_set_lambda_env_var` / `_restore_lambda_env` helpers from `test_fallback_chains.py` and the `pytest.skip` branch on missing IAM permission.

Out of scope: removing `FORCE_LLAMAPARSE_FAILURE` from any other tooling that currently uses it (none known beyond this test, but verify before deletion).
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 LlamaParseResolver detects a request-scoped sentinel (filename-based or equivalent) and returns a `ParseError` simulating a transient failure that triggers the Unstructured fallback
- [ ] #2 The sentinel is documented in code (a single comment near the check) so it cannot be confused with a feature flag
- [ ] #3 `test_document_unstructured_fallback` no longer calls `boto3.client('lambda').update_function_configuration` and no longer requires `lambda:UpdateFunctionConfiguration` IAM permission to run
- [ ] #4 The test passes deterministically against AWS dev on the first invocation, with no waits or retries
- [ ] #5 The legacy `FORCE_LLAMAPARSE_FAILURE` env-var branch in `infrastructure/resolvers/llamaparse_resolver.py` is removed (after verifying no other tooling uses it)
- [ ] #6 Unit test added to verify the resolver short-circuits when the sentinel is present and behaves normally when it is absent
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Merged via cherry-pick on main as commit 51a5026 (2026-06-10). Resolved conflicts manually: kept the per-request filename sentinel branch in llamaparse_resolver.py (restored missing `import os` for the unrelated env-var constants), took task-184's full rewrite of tests/e2e/test_fallback_chains.py (boto3 helpers and DOCUMENT_PARSING_LAMBDA constant removed as no longer needed), and updated docs/INGESTION_WORKERS_PROVIDERS.md to document the new sentinel-filename seam.
<!-- SECTION:NOTES:END -->
