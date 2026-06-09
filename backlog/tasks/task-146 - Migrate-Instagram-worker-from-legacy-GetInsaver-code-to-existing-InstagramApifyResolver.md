---
id: task-146
title: Migrate Instagram worker from legacy GetInsaver code to existing InstagramApifyResolver
status: To Do
assignee: []
created_date: '2026-06-09 21:35'
labels:
  - bug
  - backend
  - ingestion
dependencies: []
priority: high
dispatchable: true
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
## Context

The V1 launch plan §0 declares Instagram support via "Apify resolver (Reel/Post/Comment Scrapers) + orchestrator dispatch câblés". The Apify resolver code is present at `media_summarizer/infrastructure/resolvers/instagram_apify_resolver.py`. However, **the actual worker in production (`media_summarizer/workers/instagram_ingestion_worker.py`) does not use it** — it still calls **GetInsaver**, an older third-party service that was supposed to be retired.

GetInsaver is **legacy** (per owner statement 2026-06-09). The worker should use the Apify resolver instead. This is a wiring bug, not a service-credential issue.

## Symptom

`pytest -m e2e tests/e2e/test_phase4_other_sources.py::test_instagram_ingestion` fails. Job lands in `failed` with the user message `"Instagram media extraction is temporarily unavailable. Please retry."`.

CloudWatch `/aws/lambda/media-summarizer-worker-instagram_ingestion`:

```json
{
  "level": "ERROR",
  "event": "transcription.failed",
  "provider": "getinsaver",
  "error_code": "auth_failed",
  "detail": "missing_getinsaver_api_key"
}
```

The worker is **calling GetInsaver** (provider field in the log), and obviously fails because `GETINSAVER_API_KEY` is not in Secrets Manager. The fix is NOT to add the key — the fix is to remove the GetInsaver code path entirely and route the worker through the existing Apify resolver.

## Evidence

`media_summarizer/workers/instagram_ingestion_worker.py:46-50`:

```python
GETINSAVER_API_BASE_URL = os.environ.get(
    "GETINSAVER_API_BASE_URL", "https://getinsaver.com/api/v1"
)
GETINSAVER_API_KEY = os.environ.get("GETINSAVER_API_KEY", "").strip()
GETINSAVER_TIMEOUT_SECONDS = float(...)
```

And line 182:

```python
endpoint = f"{GETINSAVER_API_BASE_URL}/download/instagram"
```

Meanwhile, `media_summarizer/infrastructure/resolvers/instagram_apify_resolver.py` defines `InstagramApifyResolver` (used by Apify Reel/Post/Comment Scrapers), but no caller path inside `instagram_ingestion_worker.py` references it.

## Root cause

The Apify resolver was added in a task that introduced the resolver class but did not finish wiring it into the worker. The worker still has the legacy GetInsaver calls. The migration was started but never completed. Probably the planning was: "create Apify resolver" (done), "wire it into worker" (skipped or merged from a draft branch).

## Fix

1. **Read `instagram_apify_resolver.py`** to understand the public interface — what input it takes (presumably Reel/Post URL), what output it returns (transcript text + metadata).
2. **Read `instagram_ingestion_worker.py`** end-to-end. Identify all GetInsaver call sites and the surrounding control flow (success path, error path, fallback Deepgram, etc.).
3. **Replace the GetInsaver call** with a call to `InstagramApifyResolver` (or whatever its public callable is). Output structure should match what the worker expects downstream (transcript, audio_url for Deepgram fallback if needed, video_url for archiving, etc.).
4. **Remove all GetInsaver constants and code** — this is dead code now. Don't leave it as a "fallback" because it doesn't have a key configured anyway.
5. **Verify env vars**: `APIFY_INSTAGRAM_API_TOKEN` is in Secrets Manager (per task-127 split). The 3 Apify Instagram actor IDs (Reel/Post/Comment Scrapers) — check if the resolver picks them from env or from elsewhere; ensure they're set if needed.
6. **Audit other files** for GetInsaver references and remove:
   ```bash
   grep -rE "getinsaver|GetInsaver|GETINSAVER" media_summarizer/ infrastructure/ .env* terraform.tfvars*
   ```
7. **Lambda image rebuilt + redeployed**.
8. **Retest**: `pytest -m e2e tests/e2e/test_phase4_other_sources.py::test_instagram_ingestion`.

## Out of scope

- Refactoring the broader Instagram pipeline beyond the GetInsaver→Apify swap
- Adding new Instagram features (Stories, Highlights, etc.)
- Changing the Apify actor IDs

## References

- task-127 (introduced Apify per-source split, including `APIFY_INSTAGRAM_API_TOKEN`)
- task-135 (Instagram queue + worker provisioning — at the time the worker was already on GetInsaver and this wasn't caught)
- task-141 (Instagram worker Pydantic schema bugs — fixed mark_extracting/episode_url, but did not touch the GetInsaver vs Apify question)
- V1 launch plan §0 (declares Instagram via Apify Reel/Post/Comment Scrapers)
- `media_summarizer/workers/instagram_ingestion_worker.py:46-187` (GetInsaver code path to remove)
- `media_summarizer/infrastructure/resolvers/instagram_apify_resolver.py` (resolver to use instead)
- `media_summarizer/core/config.py:113-114` (also has GetInsaver legacy reference, remove)
- CloudWatch `/aws/lambda/media-summarizer-worker-instagram_ingestion` 2026-06-09 ~21:16 UTC
- `tests/e2e/test_phase4_other_sources.py::test_instagram_ingestion`
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 All GetInsaver references removed from `media_summarizer/` and `infrastructure/`
- [ ] #2 `instagram_ingestion_worker.py` calls `InstagramApifyResolver` (or its module-level entry point)
- [ ] #3 Required env vars present in Secrets Manager (`APIFY_INSTAGRAM_API_TOKEN` + actor IDs); validated by `aws secretsmanager get-secret-value`
- [ ] #4 Lambda image rebuilt + `media-summarizer-worker-instagram_ingestion` redeployed
- [ ] #5 `pytest -m e2e tests/e2e/test_phase4_other_sources.py::test_instagram_ingestion` passes (job reaches `completed`)
- [ ] #6 No regression on the 11 already-passing tests
- [ ] #7 `.env.example` and `terraform.tfvars.example` cleaned of `GETINSAVER_*` lines if any
<!-- AC:END -->
