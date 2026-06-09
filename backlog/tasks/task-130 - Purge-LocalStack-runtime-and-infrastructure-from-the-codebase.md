---
id: task-130
title: Purge LocalStack runtime and infrastructure from the codebase
status: Done
assignee: []
created_date: '2026-06-09 02:00'
labels:
  - cleanup
  - infrastructure
  - backend
dependencies: []
priority: medium
dispatchable: true
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
## Context

LocalStack was used early in the project to run AWS-shaped services locally for development without paying real-AWS costs. It was deprecated in V1 launch plan §Phase 4 (decision 2026-05-28) — the project decided to point dev workflows directly at the real AWS dev environment because:

- AWS dev costs (DynamoDB on-demand, S3, SQS, Lambda) are negligible compared to the variable OpenAI/Deepgram/LlamaParse costs (which are identical local or cloud)
- LocalStack introduces fidelity gaps with IAM, EventBridge, Secrets Manager, and SQS edge cases that waste more debugging time than they save

The decision was implemented partially: `.env` was updated to point at AWS dev (`AWS_ENDPOINT_URL=` empty, `AWS_REGION=eu-west-3`, `USE_LOCALSTACK=0`), and the E2E test suite (`tests/e2e/`) was built without depending on LocalStack. **But the runtime code, infra, and docker-compose still contain extensive LocalStack support.** This task removes it so that nobody can accidentally re-enable it, and so future agents don't waste time on a workflow nobody uses.

## Inventory of LocalStack references

### Runtime Python (must be cleaned)

- `media_summarizer/core/config.py:20-24` — `self.USE_LOCALSTACK`, `self.AWS_ENDPOINT_URL` defaults pointing at `http://localhost:4566`
- `media_summarizer/utils/database_async.py:30-31, 50-57` — `_IMPORT_TIME_AWS_ENDPOINT_URL`, `AWS_ENDPOINT_URL`, `_runtime_aws_endpoint_url()` and `_dynamodb_client_kwargs()` resolve LocalStack endpoint
- `media_summarizer/utils/sqs.py:23-50` — same pattern, `_runtime_aws_endpoint_url()`
- `media_summarizer/utils/minute_db.py` — ~17 references to `database_async.AWS_ENDPOINT_URL`, plus a hardcoded fallback at line 118 (`("http://localhost:4566")`)
- `media_summarizer/utils/s3.py:117-135` — LocalStack-specific boto3 fallback path (with hardcoded `"test"` credentials)
- `media_summarizer/utils/logging_config.py:267-296` — `get_runtime_aws_endpoint_url()` helper used by all of the above
- `media_summarizer/api/endpoints/health.py:104-121` — health endpoint queries `http://localhost:4566/_localstack/health` and reports it as part of system status

### Infrastructure (must be cleaned)

- `infrastructure/terraform/localstack/main.tf` + `tfplan` — entire LocalStack-specific Terraform module
- `infrastructure/localstack/init-aws.sh` + `init-aws-e2e.sh` — bootstrap scripts for LocalStack containers
- `docker-compose.dev.yml` — LocalStack service definition
- `infrastructure/terraform/README.md` — references LocalStack workflow

### Documentation (lower priority — historical accuracy can stay)

- `README.md` — references LocalStack as a dev workflow
- `docs/ADR/001-cloud-provider-aws.md` — historical context, can stay (or add a note: "LocalStack abandoned in 2026")
- `docs/research/task-73-cloud-provider-analysis/README.md` — historical research, leave as-is
- Backlog tasks (task-9, task-12, task-13, task-14, task-15, task-17, task-23, task-34, task-51, task-54, task-59, task-67, task-98, task-102, task-111) — historical task descriptions, leave as-is

### Test infrastructure (already cleaned)

- ✅ `tests/e2e/conftest.py` — was patching `database_async.AWS_ENDPOINT_URL`/`AWS_REGION` and stripping env vars at teardown to bypass LocalStack defaults. Already simplified in 2026-06-09 commit when `.env` stopped pointing at LocalStack.
- ✅ `.env` racine — `USE_LOCALSTACK=0`, `AWS_ENDPOINT_URL=` empty, `AWS_REGION=eu-west-3` as of 2026-06-09.
- ✅ `.env.example` — needs to be updated to remove the LocalStack section (still has it as of 2026-06-09).

## Goal

Eliminate all LocalStack-aware branches from the runtime and infrastructure so that:

- The codebase no longer reads `AWS_ENDPOINT_URL`, `USE_LOCALSTACK`, or any LocalStack-specific env var
- All boto3/aioboto3 client construction uses the standard credential + region chain (env, profile, IMDS, etc.)
- The `health` endpoint stops querying `http://localhost:4566` and reports an honest status
- Terraform/infrastructure files that only existed to support LocalStack (the `localstack/` subdirectories) are deleted
- Future agents can't accidentally re-enable LocalStack by setting an env var

## Constraints

- **Must not break the E2E suite** in `tests/e2e/`. Run `pytest -m e2e` before and after the change.
- **Must not break Lambda deploy**. The `lambda.Dockerfile` build + push + `aws lambda update-function-code` flow used in production must keep working.
- **Backwards-compat for the `.env`** — if someone still has `AWS_ENDPOINT_URL=http://localhost:4566` in their local `.env`, the code should ignore it (or fail loudly), not silently route to a dead endpoint.
- **Does not modify backlog task description files** older than task-130 — those are historical records.

## Out of scope

- Removing AWS-specific code (DynamoDB, S3, SQS, Lambda) — we still need real AWS, just not LocalStack
- Migrating to a different local-dev strategy (containerized AWS-like emulator, dev sandbox account, etc.) — V1 already decided against any local-dev sandbox
- Cleaning up backlog historical task files — they capture what the task was at the time

## References

- V1 launch plan §Phase 4 ("Décision 2026-05-28: on n'utilise pas LocalStack en V1")
- `tests/e2e/conftest.py` (already cleaned)
- `.env` (already cleaned)
- `.env.example` (LocalStack section still present, to be removed)
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 `media_summarizer/core/config.py` no longer references `USE_LOCALSTACK` or LocalStack endpoint defaults
- [ ] #2 `media_summarizer/utils/database_async.py` no longer has `_IMPORT_TIME_AWS_ENDPOINT_URL`, `_runtime_aws_endpoint_url()`, or LocalStack-aware kwargs in `_dynamodb_client_kwargs()`
- [ ] #3 `media_summarizer/utils/sqs.py` cleaned of equivalent constructs
- [ ] #4 `media_summarizer/utils/minute_db.py` cleaned: all `endpoint_url=database_async.AWS_ENDPOINT_URL` arguments removed, hardcoded `http://localhost:4566` fallback at line 118 removed
- [ ] #5 `media_summarizer/utils/s3.py` LocalStack-specific boto3 branch removed; only the standard aioboto3 path remains
- [ ] #6 `media_summarizer/utils/logging_config.py` — `get_runtime_aws_endpoint_url()` helper removed (or kept with a deprecation if any caller is still on it)
- [ ] #7 `media_summarizer/api/endpoints/health.py` no longer queries `http://localhost:4566/_localstack/health`; system status report cleaned of LocalStack section
- [ ] #8 `infrastructure/terraform/localstack/` directory deleted (main.tf + tfplan)
- [ ] #9 `infrastructure/localstack/` directory deleted (init-aws.sh, init-aws-e2e.sh)
- [ ] #10 `docker-compose.dev.yml` LocalStack service block deleted (or whole file deleted if it had no other purpose)
- [ ] #11 `.env.example` — section `2. AWS / LOCALSTACK` renamed to `2. AWS`; `USE_LOCALSTACK` line removed; `AWS_ENDPOINT_URL` line removed (or kept commented out as documentation that it's deprecated)
- [ ] #12 `infrastructure/terraform/README.md` mention of LocalStack workflow removed
- [ ] #13 `README.md` mention of LocalStack workflow removed
- [ ] #14 `pytest -m e2e` passes after the change (no regression on the 7 happy-path tests)
- [ ] #15 `ruff check .` and `mypy media_summarizer` pass (existing CI gates)
- [ ] #16 `terraform plan` from `infrastructure/terraform/` succeeds (no broken refs to deleted modules)
<!-- AC:END -->
