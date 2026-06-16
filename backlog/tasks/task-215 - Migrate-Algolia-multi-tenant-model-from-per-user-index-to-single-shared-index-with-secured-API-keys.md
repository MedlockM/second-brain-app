---
id: task-215
title: >-
  Migrate Algolia multi-tenant model from per-user index to single shared index
  with secured API keys
status: Done
assignee: []
created_date: '2026-06-16 15:10'
labels:
  - backend
  - search
  - infrastructure
  - refactor
dependencies: []
priority: medium
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
## Context

Task-205 introduced "one Algolia index per user" as the multi-tenant isolation model. After verification against Algolia's official documentation, **this is not the pattern Algolia recommends**, and it doesn't scale within the limits of the Grow / Grow Plus plans (50 indices max per application). At 100 users we'd already need Elevate (paid). Algolia's official guidance (doc: *"User-restricted access to data"*) explicitly states:

> *"This doesn't mean you need one index per user."*

We should migrate to the recommended pattern **before the data volume makes the migration painful**, while we still have <100 users and the app is not in production.

## Recommended pattern (per Algolia docs)

**Single shared index with secured API keys + a filterable `user_id` attribute on every record.**

Key elements (verify against the live Algolia documentation — links below):

1. **Indexing**: every record carries a `user_id` attribute. Configure `attributesForFaceting` with `filterOnly(user_id)` for best performance (no facet count is computed). Optionally also `unretrievableAttributes: ["user_id"]` so the attribute is never returned to clients.
2. **Search-time security**: the **backend** generates a *secured API key* derived from a parent search-only key, with the filter `user_id:<currentUserId>` embedded inside the key signature. The key is opaque and tamper-proof — the client cannot remove or alter the filter.
3. **Key lifecycle**: short TTL on the secured key (`validUntil`), refreshed by the backend on demand or alongside the auth token.
4. **Data deletion**: when a user is deleted, run `deleteBy({ filters: 'user_id:<id>' })` instead of dropping a whole index.

The implementer must read the **current** Algolia documentation before writing code. Patterns and SDK methods evolve. Authoritative starting points:

- Multi-tenant pattern: https://www.algolia.com/doc/guides/security/api-keys/how-to/user-restricted-access-to-data/
- Secured API keys: https://www.algolia.com/doc/guides/security/api-keys/how-to/generating-api-keys/
- API key restrictions: https://www.algolia.com/doc/guides/security/api-keys/in-depth/api-key-restrictions/
- Filtering: https://www.algolia.com/doc/guides/managing-results/refine-results/filtering/
- Pricing & plan limits: https://www.algolia.com/pricing/

If any of those URLs 404, navigate from `https://www.algolia.com/doc/` and use site search. **Do not implement this from training-data memory** — Algolia's SDK signatures and recommended config flags change across major versions.

## Why migrate now (and not later)

- Grow / Grow Plus = max **50 indices per application**. With one index per user we hit the wall at 51 users.
- Build plan is a dev/test playground; not a production answer.
- "Build operations" (index settings updates, batch operations) are billed per index. Per-user indices multiply these calls (settings sync after every refactor of ranking/searchableAttributes).
- Analytics, A/B tests, ranking tuning, dictionaries — all are scoped per index in Algolia. Per-user indices fragment them and make tuning impossible.
- A single shared index is the path the rest of the Algolia ecosystem (Insights, Recommend, NeuralSearch) is built around.

## Scope

This task covers the full migration:

1. **Read the docs** (links above) and confirm the exact pattern + SDK calls before touching code. If anything in this description conflicts with current Algolia docs, **the docs win** — flag the discrepancy in a comment on this task.

2. **Indexing path** (`media_summarizer/workers/search_indexing_worker.py` and any helper in `media_summarizer/utils/algolia*` — confirm by grep): switch from "compute per-user index name then `saveObject`" to "always write to a single index, with `user_id` set on the record". Decide a single canonical index name (e.g. `media_items` or `media_items_<env>` for dev/staging/prod separation — env-based, not user-based).

3. **Index settings**: configure `attributesForFaceting: ["filterOnly(user_id)"]` (plus any existing facets the app uses); set `unretrievableAttributes: ["user_id"]` if we want stricter API hygiene; review `searchableAttributes` and `customRanking` so they remain coherent with a multi-tenant corpus.

4. **Secured API key generation** (new code, likely in `media_summarizer/api/endpoints/search.py` or a new helper). The backend must:
   - Hold the parent **search-only** API key (NOT the admin key) in a Lambda env var (`ALGOLIA_SEARCH_API_KEY`) — terraform-wired.
   - Generate a secured key with `filters: 'user_id:<id>'` and a short `validUntil` (e.g. 1h, refreshed by mobile when expired).
   - Return `{appId, securedKey, indexName, validUntil}` from a new endpoint (e.g. `GET /api/search/credentials`) called by the mobile client.

5. **Mobile**: replace the current "fetch per-user index name" logic with "fetch credentials, init Algolia client with the secured key, search the shared index". Keep the secured key in memory only; do not persist it. Refresh on 401/403 from Algolia or before `validUntil`.

6. **Migration script** (`scripts/migrate_algolia_to_shared_index.py` or similar):
   - Iterate over all per-user indices in the Algolia app, copy each record into the new shared index with `user_id` attribute set, then delete the old per-user index.
   - Idempotent and resumable. Log per-user counts.
   - Guard with a `--dry-run` flag and an explicit `--apply` to actually write.
   - Run once on dev to validate, then on prod (when prod exists).

7. **Cleanup**:
   - Remove the per-user index naming helper(s).
   - Remove env vars / config that referenced per-user indices.
   - Update any tests in `tests/` that mock the old behaviour.
   - Update task-205 follow-up notes / docs if any internal architecture doc mentions per-user indices.

8. **Verification**:
   - Add a unit test: secured-key generation embeds the right filter and is unique per `user_id`.
   - Add an integration test: indexing two users' records into the shared index, then searching with each user's secured key, returns only that user's records (use a test Algolia app or `respx`-style mock).
   - End-to-end smoke: mobile app → save a YouTube video → search a transcript word → result appears for owner only.
   - Try with two test accounts on dev and confirm cross-user leak is impossible (search with user A's key should never return user B's records).

## What NOT to do

- Do **not** ship the parent admin or write API key to the mobile client. Only secured *search* keys are safe for the client.
- Do **not** rely on client-side `filters: 'user_id:<id>'` in addition to or instead of the secured key — clients can strip or alter raw filter strings.
- Do **not** keep both per-user and shared indexing live in parallel "for safety". The migration script + a single deploy is enough; running both doubles cost and complexity.
- Do **not** invent a security pattern from training-data memory. Read `https://www.algolia.com/doc/guides/security/api-keys/` first and follow what's there today.
- Do **not** put the parent search key in mobile-bundled config files. Backend-only.

## Acceptance Criteria
<!-- AC:BEGIN -->
See the explicit list. The implementer should also amend or add a short architecture note (≤30 lines) in `docs/research/` or wherever existing search docs live, summarising the chosen pattern and linking to the Algolia doc URLs that informed the decision.
<!-- SECTION:DESCRIPTION:END -->

- [ ] #1 Implementer has read the current Algolia docs on user-restricted access and secured API keys (links in description) and confirmed the SDK calls used match the live docs (any drift flagged in a task comment)
- [ ] #2 All media records are indexed into a single shared Algolia index (one per environment: dev/staging/prod), each carrying a user_id attribute
- [ ] #3 Index settings include attributesForFaceting=["filterOnly(user_id)"] and unretrievableAttributes=["user_id"]; searchableAttributes and customRanking reviewed for multi-tenant correctness
- [ ] #4 Backend exposes an endpoint that returns {appId, securedKey, indexName, validUntil}; the secured key embeds filters="user_id:<id>" and is generated server-side from a parent search-only key (never the admin key)
- [ ] #5 Parent search API key is wired via Lambda env var (terraform); admin key is never reachable from the mobile client
- [ ] #6 Mobile client uses the secured key returned by the backend, initializes the Algolia client against the shared index, and refreshes the key on expiry (validUntil) or auth failure
- [ ] #7 One-shot migration script copies records from existing per-user indices into the shared index (with user_id set), then deletes the old indices; supports --dry-run and --apply; idempotent
- [ ] #8 Per-user index naming helpers and related config removed from the codebase; no dead references remain
- [ ] #9 Unit test: secured-key generation produces a tamper-proof key for the right user_id (different user_id → different key)
- [ ] #10 Integration test: two users indexed into the shared index can each only retrieve their own records via their secured key (cross-tenant leak test)
- [ ] #11 End-to-end smoke on dev: save a YouTube video for user A, search a transcript word from both user A and user B — only user A finds the result
- [ ] #12 Architecture note added (≤30 lines) summarizing the chosen pattern with links to the Algolia docs that informed the decision
<!-- AC:END -->
