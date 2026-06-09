---
id: task-127
title: Split APIFY_API_TOKEN into per-account tokens (Instagram + YouTube)
status: Done
assignee: []
created_date: '2026-06-09 10:33'
labels:
  - backend
  - refactor
  - config
  - ingestion
dependencies: []
priority: high
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
## Context

The repo currently exposes a single `APIFY_API_TOKEN` env var (cf. `media_summarizer/core/config.py:93`). It is consumed only by the Instagram extraction stack (`InstagramApifyResolver` in `media_summarizer/infrastructure/resolvers/instagram_apify_resolver.py`, see lines 61-76 for the env reads, and lines 693-792 for the `_run_actor()` HTTP plumbing).

The owner now operates **two distinct Apify accounts** — one for Instagram (the existing one) and a new one dedicated to YouTube (used by the upcoming task that bascule the YouTube worker on Apify, gated on task-126). Both accounts must be addressable side-by-side from the backend with isolated quotas/billing.

This task is the prerequisite refactor: split the single token into two named tokens, and add the YouTube actor placeholder so the follow-up task can wire the worker without touching config again.

This task does NOT need a benchmark — pure mechanical split of an env var, no architecture decision.

## Scope

### Code changes

1. **`media_summarizer/core/config.py:93-105`**
   - Remove `APIFY_API_TOKEN`.
   - Add `APIFY_INSTAGRAM_API_TOKEN` (string, default `""`) — receives the value previously held by `APIFY_API_TOKEN`.
   - Add `APIFY_YOUTUBE_API_TOKEN` (string, default `""`).
   - Add `APIFY_YOUTUBE_TRANSCRIPT_ACTOR_ID` (string, default `""`) — placeholder for the follow-up task; left empty here on purpose.
   - Keep `APIFY_INSTAGRAM_REEL_ACTOR_ID`, `APIFY_INSTAGRAM_POST_ACTOR_ID`, `APIFY_INSTAGRAM_COMMENT_ACTOR_ID`, `APIFY_TIMEOUT_SECONDS` as-is.

2. **`media_summarizer/infrastructure/resolvers/instagram_apify_resolver.py`**
   - Replace every `os.environ.get("APIFY_API_TOKEN", ...)` (and every reference to the old name in fallback chains, comments, error messages) by `APIFY_INSTAGRAM_API_TOKEN`. Approx. lines 61-76, plus any other occurrence in the file.
   - Resolver constructor still accepts an optional `api_token` argument; only the default fallback name changes.

3. **`media_summarizer/tests/test_instagram_apify_resolver.py`**
   - Update every fixture / `monkeypatch.setenv` / `patch.dict(os.environ, ...)` that injects `APIFY_API_TOKEN` to use `APIFY_INSTAGRAM_API_TOKEN`.

4. **`.env.example` (lines 192-203, "Instagram (via Apify actors)" section)**
   - Rename `APIFY_API_TOKEN=` to `APIFY_INSTAGRAM_API_TOKEN=`.
   - Add a new section "YouTube (via Apify actor)" with `APIFY_YOUTUBE_API_TOKEN=` and `APIFY_YOUTUBE_TRANSCRIPT_ACTOR_ID=` (both blank).
   - Keep the existing `APIFY_TIMEOUT_SECONDS`, `APIFY_POLL_INTERVAL_SECONDS`, `APIFY_MAX_POLLS`, `INSTAGRAM_TRANSCRIPT_MIN_LENGTH`, `INSTAGRAM_USE_APIFY_TRANSCRIPT` as-is (shared across providers).

5. **`docs/MEDIA_INGESTION_CORE_ARCHITECTURE.md` (around lines 223-231) and any other docs**
   - Search the whole `docs/` tree for `APIFY_API_TOKEN` and rename to `APIFY_INSTAGRAM_API_TOKEN` everywhere except `docs/research/` (those are historical benchmark snapshots and must stay untouched).

### Infrastructure (Terraform)

`infrastructure/terraform/secrets.tf` does not need code changes — it uses a generic `secret_payload` map injected at `terraform apply` time. The deployer must instead update the runtime secret payload at deploy time:
- Add key `APIFY_INSTAGRAM_API_TOKEN` (= the value previously stored under `APIFY_API_TOKEN`)
- Add key `APIFY_YOUTUBE_API_TOKEN` (new, owner provisions the value when ready)
- Add key `APIFY_YOUTUBE_TRANSCRIPT_ACTOR_ID` (left empty here — the follow-up task will fill it)
- Remove key `APIFY_API_TOKEN`

The PR description must call this out explicitly so the deploy step is not skipped.

## Constraints

- **Pre-production, no backwards compatibility**: do not add a fallback "if `APIFY_INSTAGRAM_API_TOKEN` empty, read `APIFY_API_TOKEN`". Hard rename only.
- **Do not touch the YouTube worker** (`media_summarizer/workers/youtube_ingestion_worker.py`) — that's the follow-up task's scope.
- **Do not create the YouTube Apify resolver yet** — only add the empty `APIFY_YOUTUBE_*` config slots so the follow-up task can wire on top.
- Instagram ingestion must keep working unchanged after this refactor (verified by the existing test suite).

## Verification

- `grep -r "APIFY_API_TOKEN" media_summarizer/ infrastructure/ docs/MEDIA_INGESTION_CORE_ARCHITECTURE.md docs/CANONICAL_MEDIA_API_CONTRACT.md docs/ADR/ .env.example` returns no result (only `docs/research/` may still mention the old name; that's expected).
- `pytest media_summarizer/tests/test_instagram_apify_resolver.py -v` passes.
- `python -c "from media_summarizer.core.config import settings; print(settings.APIFY_INSTAGRAM_API_TOKEN, settings.APIFY_YOUTUBE_API_TOKEN, settings.APIFY_YOUTUBE_TRANSCRIPT_ACTOR_ID)"` runs without `AttributeError`.

## References

- `media_summarizer/core/config.py:93-105` (current `APIFY_*` declarations)
- `media_summarizer/infrastructure/resolvers/instagram_apify_resolver.py:61-76` (env-var reads)
- `media_summarizer/tests/test_instagram_apify_resolver.py` (fixtures)
- `.env.example:192-203` (Instagram Apify section)
- `infrastructure/terraform/secrets.tf` (generic `secret_payload` mechanism — no code change required)
- `docs/research/task-107-instagram-extraction-benchmark/README.md` (historical, do not modify)
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 No occurrence of `APIFY_API_TOKEN` remains under `media_summarizer/`, `infrastructure/`, top-level docs (excluding `docs/research/`), or `.env.example`
- [ ] #2 `APIFY_INSTAGRAM_API_TOKEN`, `APIFY_YOUTUBE_API_TOKEN`, and `APIFY_YOUTUBE_TRANSCRIPT_ACTOR_ID` are exposed by `media_summarizer/core/config.py` and documented in `.env.example`
- [ ] #3 `InstagramApifyResolver` reads `APIFY_INSTAGRAM_API_TOKEN` and Instagram extraction tests pass unchanged
- [ ] #4 PR description explicitly instructs the deployer to update the Terraform `secret_payload` (rename Instagram key, add YouTube keys, drop the legacy key) before merging to dev/prod
<!-- AC:END -->
