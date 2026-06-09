---
id: task-153
title: Fix Instagram Apify resolver — missing APIFY_INSTAGRAM_API_TOKEN after task-146 migration
status: Done
assignee: []
created_date: '2026-06-09 23:00'
updated_date: '2026-06-09'
labels:
  - bug
  - infrastructure
  - ingestion
dependencies: []
priority: high
dispatchable: true
---

## Resolution (2026-06-09 23:15)

Owner pushed the 4 Apify Instagram keys (`APIFY_INSTAGRAM_API_TOKEN`, `APIFY_INSTAGRAM_REEL_ACTOR_ID`, `APIFY_INSTAGRAM_POST_ACTOR_ID`, `APIFY_INSTAGRAM_COMMENT_ACTOR_ID`) directly to Secrets Manager via `aws secretsmanager put-secret-value`, bypassing the `lifecycle { ignore_changes }` block. Lambda cold-started.

**Confirmed working**: the Apify resolver now contacts Apify successfully (no more `apify_retryable: media resolution unavailable` error). The remaining test failure is due to the Reel fixture URL (`reel/CzHnAVRo6Cf/`) being deleted or geo-restricted; Apify returns `apify_non_retryable: Unable to resolve transcribable media from this Instagram URL`. **Fixture URL needs to be replaced** — separate concern, not a code bug.

The root cause confirmed:
- `.env` racine had the keys ✅
- `terraform.tfvars` had the keys ✅
- Secrets Manager **did NOT** have them because of `lifecycle { ignore_changes = [secret_string] }` in `secrets.tf` — Terraform skipped pushing them after the initial provisioning.

This is a **systemic gotcha**: any new secret added to `terraform.tfvars` after initial deployment must be manually pushed to Secrets Manager. Documenting this in `infrastructure/terraform/README.md` would prevent re-occurrence (e.g. for tasks 154/155 which may have the same issue).

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
## Context

After task-146 (migrate Instagram worker from GetInsaver to InstagramApifyResolver), the Instagram E2E test progresses past the previous GetInsaver auth_failed bug — but now fails with a different message:

```
"Worker handler failed for message <id>: apify_retryable:Instagram media resolution is temporarily unavailable."
```

`status` reaches `downloading` (progress 25%) and stays there. The Apify resolver inside the worker is being called but is itself failing.

Verification of `media-summarizer-runtime-dev` Secrets Manager confirmed:

```
APIFY_INSTAGRAM_API_TOKEN: <MISSING>
```

So the resolver gets a missing/empty token and returns `apify_retryable`. task-127 (Apify per-source token split) created the env var name but it was never added to the Lambda's Secrets Manager payload.

## Symptom

`pytest -m e2e tests/e2e/test_phase4_other_sources.py::test_instagram_ingestion` times out at `downloading` 25%.

CloudWatch `/aws/lambda/media-summarizer-worker-instagram_ingestion`:

```json
{
  "level": "ERROR",
  "event": "log.record",
  "message": "Worker handler failed for message <id>: apify_retryable:Instagram media resolution is temporarily unavailable."
}
```

## Root cause

The Apify Instagram resolver reads `APIFY_INSTAGRAM_API_TOKEN` from `os.environ`. The variable is empty in the Lambda's runtime env because:

- `terraform.tfvars` already has `APIFY_INSTAGRAM_API_TOKEN = "<APIFY_INSTAGRAM_API_TOKEN>"` (added at line 28 during a previous task)
- But `secrets.tf` (or wherever `secret_payload` is wired into Secrets Manager) may not include this key

OR

- The key IS in Terraform but `secrets.tf` has `lifecycle { ignore_changes = [secret_string] }` (cf. `infrastructure/terraform/README.md`), so subsequent `terraform apply` runs don't push new keys. The initial provisioning was done before `APIFY_INSTAGRAM_API_TOKEN` was added.

## Fix

1. Verify what `terraform.tfvars` `secret_payload` block contains for `APIFY_INSTAGRAM_API_TOKEN`. Should be the real token (`<APIFY_INSTAGRAM_API_TOKEN>` per `.env` racine).
2. Push the missing key directly to Secrets Manager via AWS CLI (because of the `ignore_changes` lifecycle):

```bash
aws secretsmanager get-secret-value --secret-id media-summarizer-runtime-dev \
  --region eu-west-3 --query 'SecretString' --output text > /tmp/secret.json

python3 -c "
import json
with open('/tmp/secret.json') as f: d = json.load(f)
d['APIFY_INSTAGRAM_API_TOKEN'] = '<APIFY_INSTAGRAM_API_TOKEN>'
# Also check if Apify Instagram actor IDs are needed:
# d['APIFY_INSTAGRAM_REEL_ACTOR_ID'] = '...'
# d['APIFY_INSTAGRAM_POST_ACTOR_ID'] = '...'
# d['APIFY_INSTAGRAM_COMMENT_ACTOR_ID'] = '...'
with open('/tmp/secret-new.json', 'w') as f: json.dump(d, f)
"

aws secretsmanager put-secret-value --secret-id media-summarizer-runtime-dev \
  --region eu-west-3 --secret-string file:///tmp/secret-new.json
```

3. Force a Lambda cold start:
```bash
aws lambda update-function-configuration --region eu-west-3 \
  --function-name media-summarizer-worker-instagram_ingestion \
  --description "Force cold start after Instagram Apify token fix $(date +%s)"
```

4. Verify the resolver also reads the 3 actor IDs (Reel/Post/Comment Scrapers) from env. If they're hardcoded inside `instagram_apify_resolver.py`, no extra env var needed. If they're env-driven, ensure they're in Secrets Manager too.

5. Retest: `pytest -m e2e tests/e2e/test_phase4_other_sources.py::test_instagram_ingestion -v`.

## Out of scope

- Fixing the broader pattern of "secret added to terraform.tfvars but not pushed because of ignore_changes" (separate hardening task — maybe revisit the `lifecycle` block)
- Adding Apify rate-limit handling (separate concern)
- Mobile UX for "instagram unavailable" messages

## References

- task-127 (Apify per-source split, introduced `APIFY_INSTAGRAM_API_TOKEN`)
- task-146 (Instagram worker migration to Apify)
- `media_summarizer/infrastructure/resolvers/instagram_apify_resolver.py`
- `infrastructure/terraform/secrets.tf` (lifecycle ignore_changes)
- CloudWatch `/aws/lambda/media-summarizer-worker-instagram_ingestion` 2026-06-09 ~22:50 UTC
- `tests/e2e/test_phase4_other_sources.py::test_instagram_ingestion`
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 `APIFY_INSTAGRAM_API_TOKEN` value pushed directly to Secrets Manager via AWS CLI
- [ ] #2 If actor IDs (Reel/Post/Comment) are env-driven, they're present in Secrets Manager too
- [ ] #3 Lambda cold-start triggered; CloudWatch confirms env var is now populated
- [ ] #4 `pytest -m e2e tests/e2e/test_phase4_other_sources.py::test_instagram_ingestion` passes
- [ ] #5 No regression on the 11 already-passing tests
- [ ] #6 (Optional) Document the `ignore_changes` lifecycle gotcha in `infrastructure/terraform/README.md` so future agents push secrets manually after adding them to `terraform.tfvars`
<!-- AC:END -->
