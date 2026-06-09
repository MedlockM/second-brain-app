---
id: task-155
title: Fix PodcastIndex resolver — PODCASTINDEXORG_API_KEY/SECRET not loaded by Lambda despite being in Secrets Manager
status: To Do
assignee: []
created_date: '2026-06-09 23:00'
labels:
  - bug
  - backend
  - infrastructure
dependencies: []
priority: high
dispatchable: true
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
## Context

After task-148 (URL classification on the producer side), the PodcastIndex resolver worker receives the correct `source_platform: apple_podcasts` and starts the Apple-specific path. **But it then fails when calling the PodcastIndex.org API** because it can't find the API credentials.

```
"Error getting podcast by iTunes ID:
 PODCASTINDEXORG_API_KEY and PODCASTINDEXORG_API_SECRET must be set"
```

Verification of `media-summarizer-runtime-dev` Secrets Manager:

```
PODCASTINDEXORG_API_KEY: present (20 chars)
PODCASTINDEXORG_API_SECRET: present (40 chars)
```

So the credentials ARE in Secrets Manager, but the worker doesn't see them at runtime. This is a different bug from task-153 (where the value was simply missing from Secrets Manager).

## Symptom

`pytest -m e2e tests/e2e/test_phase4_other_sources.py::test_podcast_via_podcastindex` times out at `rss_resolving` 10%.

CloudWatch `/aws/lambda/media-summarizer-worker-podcastindex_resolution`:

```
"message": "Error getting podcast by iTunes ID:
 PODCASTINDEXORG_API_KEY and PODCASTINDEXORG_API_SECRET must be set"
"message": "Worker handler failed for message <id>:
 Podcast URL could not be resolved. code=invalid_platform_url"
```

The error message is misleading: the Apple normalizer DID succeed (we have an iTunes ID to look up), but the lookup itself fails because the PodcastIndex client can't authenticate. The `invalid_platform_url` code is then surfaced as a generic catch-all.

## Root cause hypotheses

The values are in Secrets Manager but not visible in the worker's `os.environ` at runtime. Possible reasons:

1. **Cold-start cache stale**: the worker Lambda was warm with an older secret payload. The secret was updated AFTER the worker last cold-started. Forcing a cold start would fix it for THIS instance but not for any subsequent warm invocations until they expire.
2. **Worker reads the secret directly, not via env var**: if the PodcastIndex client reads `os.environ.get("PODCASTINDEXORG_API_KEY")` but the secret is loaded under a different name (or via a different mechanism), the env var stays empty even though the secret has a value.
3. **Secret loader doesn't include this Lambda**: each Lambda's `lambda_handler.py` reads `RUNTIME_SECRET_NAME` and injects keys into `os.environ`. If the PodcastIndex worker uses a different handler that doesn't do this injection, the credentials never reach the env.
4. **Initialization order**: the PodcastIndex client is constructed at module import time, but the secret loader runs in the handler init. If the client caches an empty token at import, it never picks up the loaded value.

## Investigation step (do FIRST)

```bash
# 1. Check the worker's lambda_handler — does it use the standard secret loader?
grep -nE "RUNTIME_SECRET_NAME|get_secret_value|os.environ" \
  media_summarizer/workers/lambda_handlers.py \
  media_summarizer/workers/podcastindex_resolution_worker.py | head -20

# 2. Check where the PodcastIndex API key is read (module-level vs lazy)
grep -nE "PODCASTINDEXORG_API_KEY|PODCASTINDEXORG_API_SECRET" \
  media_summarizer/ -r | head -20

# 3. Check what the cached aiobotocore session sees (force cold start, check logs):
aws lambda update-function-configuration --region eu-west-3 \
  --function-name media-summarizer-worker-podcastindex_resolution \
  --description "Force cold start $(date +%s)"
```

## Fix

Once root cause identified:

- **Hypothesis 1** (cold start): force the cold start (already done by image redeploy when task-148 lands; but verify it actually happened)
- **Hypothesis 2** (different env var name): align the variable name across `.env` / `terraform.tfvars` / worker code
- **Hypothesis 3** (handler doesn't inject): check whether the worker uses the same `lambda_handler` skeleton as other workers (article_extraction, summarization, etc.). If it does, it should get the same secret injection. If not, refactor.
- **Hypothesis 4** (init order): make the PodcastIndex client lazy — instantiate on first call, after secrets are loaded.

## Reproduction

```bash
.venv/bin/pytest -m e2e tests/e2e/test_phase4_other_sources.py::test_podcast_via_podcastindex -v
```

Wait at `rss_resolving` 10%. CloudWatch shows the credentials error.

## Out of scope

- Adding a different podcast index provider (PodcastIndex.org is the V1 choice)
- Caching the PodcastIndex API client (separate concern)

## References

- task-148 (URL classification fix; now uncovered the credentials bug)
- `media_summarizer/workers/podcastindex_resolution_worker.py`
- `media_summarizer/workers/podcast_platform_resolvers.py` (probably where the PodcastIndex client lives)
- `media_summarizer/workers/lambda_handlers.py` (secret-injection skeleton)
- CloudWatch `/aws/lambda/media-summarizer-worker-podcastindex_resolution` 2026-06-09 ~22:50 UTC
- `tests/e2e/test_phase4_other_sources.py::test_podcast_via_podcastindex`
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 Investigation step run; root cause documented (which of the 4 hypotheses, with evidence)
- [ ] #2 Targeted fix applied
- [ ] #3 Lambda image rebuilt + redeployed if needed
- [ ] #4 `pytest -m e2e tests/e2e/test_phase4_other_sources.py::test_podcast_via_podcastindex` passes
- [ ] #5 No regression on the 11 already-passing tests, especially `test_podcast_via_direct_audio_url` which uses the same Deepgram path the PodcastIndex resolver routes to
<!-- AC:END -->
