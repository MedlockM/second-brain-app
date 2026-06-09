---
id: task-136
title: Fix document search indexing — Algolia API key corrupted by trailing comment in Secrets Manager
status: To Do
assignee: []
created_date: '2026-06-09 16:50'
labels:
  - bug
  - infrastructure
  - backend
dependencies: []
priority: high
dispatchable: true
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
## Context

Discovered during E2E re-run after task-133 was merged. Document parsing now succeeds (LlamaParse OK after the circular-import fix), but the downstream `search_indexing_worker` rejects the Algolia API key. Result: PDFs are parsed but never indexed in Algolia → search broken.

The same Algolia key works elsewhere (manually, in `.env`) — it's a corruption introduced when the key was copy-pasted into `terraform.tfvars` `secret_payload`.

## Symptom

`pytest -m e2e tests/e2e/test_phase4_other_sources.py::test_document_upload` times out. The job stays in some intermediate state because indexing fails and never reaches `completed`.

CloudWatch `/aws/lambda/media-summarizer-worker-search_indexing`:

```
RequestException: Invalid API key
  at search_indexing.py:143 → client.save_objects(...)
```

## Root cause

`infrastructure/terraform/terraform.tfvars` line 22:

```
ALGOLIA_API_KEY = "<ALGOLIA_ADMIN_KEY>              # admin key (backend-only, never expose to frontend)"
```

The trailing comment `# admin key (backend-only, never expose to frontend)` was supposed to be a Terraform/HCL comment but is **inside the string literal** (after the quoted hex value, with whitespace and `#` ending up as data). Terraform stores it verbatim in the `secret_payload`, Secrets Manager pushes it to Lambda as `os.environ["ALGOLIA_API_KEY"] = "<ALGOLIA_ADMIN_KEY>              # admin..."`, and Algolia's API rejects everything past `<ALGOLIA_ADMIN_KEY>`.

Confirmed empirically by reading the secret value:

```bash
aws secretsmanager get-secret-value --secret-id media-summarizer-runtime-dev --region eu-west-3 \
  --query 'SecretString' --output text \
  | python3 -c "import sys,json; print(repr(json.loads(sys.stdin.read())['ALGOLIA_API_KEY'][:80]))"
# '<ALGOLIA_ADMIN_KEY>              # admin key (backend-only, never e'
```

## Fix

1. Edit `infrastructure/terraform/terraform.tfvars` line 22. Strip the trailing comment from the string literal:
   ```diff
   - ALGOLIA_API_KEY = "<ALGOLIA_ADMIN_KEY>              # admin key (backend-only, never expose to frontend)"
   + ALGOLIA_API_KEY = "<ALGOLIA_ADMIN_KEY>"  # admin key (backend-only, never expose to frontend)
   ```
   (The `#` after the closing `"` is a real HCL comment, not part of the value.)
2. `terraform apply` — pushes the new value to Secrets Manager.
3. Trigger a Lambda cold start (re-run a Lambda or `aws lambda update-function-configuration` to force re-init).
4. Audit other entries in `terraform.tfvars` `secret_payload` for the same bug (trailing comments inside string literals). E.g. grep for `"\s+#` patterns.
5. Re-run the document E2E test.

## Reproduction

```bash
.venv/bin/pytest -m e2e tests/e2e/test_phase4_other_sources.py::test_document_upload -v
```

## Out of scope

- Other source-specific bugs (TikTok episode_url, Instagram queue, podcast Decimal, podcast routing) — separate tasks 134, 135, 137, 138

## References

- `infrastructure/terraform/terraform.tfvars:22`
- `media_summarizer/workers/search_indexing_worker.py`
- `media_summarizer/core/services/search_indexing.py:143`
- `tests/e2e/test_phase4_other_sources.py::test_document_upload`
- CloudWatch `/aws/lambda/media-summarizer-worker-search_indexing` 2026-06-09 ~14:43 UTC
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 `terraform.tfvars:22` `ALGOLIA_API_KEY` cleaned (trailing comment moved outside the string literal)
- [ ] #2 Audit performed on the rest of `secret_payload` for the same bug pattern; document any other corrupted values
- [ ] #3 `terraform apply` clean; verify with `aws secretsmanager get-secret-value ... | jq .ALGOLIA_API_KEY` that the value is exactly 32 hex chars (no trailing whitespace or comment)
- [ ] #4 Lambda cold-start triggered (any update); the search_indexing worker reads the corrected key
- [ ] #5 `pytest -m e2e tests/e2e/test_phase4_other_sources.py::test_document_upload` passes (job reaches `completed`, document indexed in Algolia)
- [ ] #6 No regression on the 9 already-passing tests
<!-- AC:END -->
