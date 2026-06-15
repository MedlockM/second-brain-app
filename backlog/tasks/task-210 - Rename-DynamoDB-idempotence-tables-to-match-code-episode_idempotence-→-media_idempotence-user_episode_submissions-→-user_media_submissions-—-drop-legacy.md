---
id: task-210
title: >-
  Rename DynamoDB idempotence tables to match code (episode_idempotence →
  media_idempotence, user_episode_submissions → user_media_submissions) — drop
  legacy
status: Done
assignee: []
created_date: '2026-06-15 16:41'
labels:
  - infrastructure
  - backend
  - bug
  - critical
dependencies: []
priority: high
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
## Context

Follow-up to task-209. After wiring `MEDIA_IDEMPOTENCE_TABLE = aws_dynamodb_table.episode_idempotence_v1.name` on the Lambdas, ingestion still fails with HTTP 500. CloudWatch shows:

```
ValidationException: The provided key element does not match the schema
  at media_summarizer/utils/media_idempotence.py:43 — table.get_item(Key={"media_key": ...})
```

Root cause: task-49 renamed identifiers in code (`episode_*` → `media_*`) but never renamed the DynamoDB tables or their key schemas. The current state is incoherent:

| Code expects (env-var default + key)         | AWS table actually has              |
| -------------------------------------------- | ----------------------------------- |
| Table `media_idempotence`, PK `media_key`    | Table `episode_idempotence`, PK `episode_guid` |
| Table `user_media_submissions`, PK `user_id` + SK `media_key` | Table `user_episode_submissions`, PK `user_id` + SK `episode_guid` |

Both legacy tables are **empty** (verified via `aws dynamodb scan --limit 3` returns `Count=0`), and the app is **not yet in production**, so we don't need a data migration or a transition window.

## Scope

Replace the legacy tables outright in Terraform. Drop the old, create the new with the correct names and key schemas. No mapping shims in the code, no compat env vars, no data migration.

### File: `infrastructure/terraform/dynamodb_core_tables.tf`

1. Rename resource `aws_dynamodb_table.episode_idempotence_v1` → `aws_dynamodb_table.media_idempotence_v1`:
   - `name = "media_idempotence"`
   - `hash_key = "media_key"`
   - `attribute { name = "media_key"; type = "S" }`
   - Update `tags.Name` to `media_idempotence`.

2. Rename resource `aws_dynamodb_table.user_episode_submissions_v1` → `aws_dynamodb_table.user_media_submissions_v1`:
   - `name = "user_media_submissions"`
   - Keep `hash_key = "user_id"`, change `range_key = "media_key"`
   - Replace the `episode_guid` `attribute` block with `media_key`.
   - Update `tags.Name`.

3. Update the output block at the bottom: rename `episode_idempotence_table_name` → `media_idempotence_table_name`, point to the new resource.

### File: `infrastructure/terraform/lambda_api.tf`

- Line 77: change `MEDIA_IDEMPOTENCE_TABLE = aws_dynamodb_table.episode_idempotence_v1.name` → `aws_dynamodb_table.media_idempotence_v1.name`. Also add `USER_MEDIA_SUBMISSIONS_TABLE = aws_dynamodb_table.user_media_submissions_v1.name` (the env var is read in `media_summarizer/utils/user_media_submissions.py:22-24` and currently falls back to the default which won't exist after rename).

### File: `infrastructure/terraform/lambda_workers.tf`

- Line 142: same change as `lambda_api.tf`. Add `USER_MEDIA_SUBMISSIONS_TABLE` next to it.

### IAM

- Find the IAM policy attached to API + workers granting access to `episode_idempotence` / `user_episode_submissions` (search `infrastructure/terraform/` for those resource refs in `aws_iam_*` blocks). Update the resource ARNs to point to the new tables. If the policy was using `aws_dynamodb_table.<name>.arn` interpolations, the rename will flow through automatically.

## What NOT to do

- Do **not** keep `episode_idempotence` / `user_episode_submissions` around as compat tables.
- Do **not** add mapping logic (`media_key → episode_guid`) in the Python code.
- Do **not** introduce `EPISODE_IDEMPOTENCE_TABLE` env var as a fallback. The code is already correct; only the infra is out of date.

## Verification

1. `terraform plan` should show: 2 tables destroyed (`episode_idempotence`, `user_episode_submissions`), 2 tables created (`media_idempotence`, `user_media_submissions`), env var changes on `media-summarizer-api` and the worker Lambdas, IAM resource references updated.
2. After `terraform apply`, run `aws dynamodb describe-table --table-name media_idempotence` and confirm `KeySchema[0].AttributeName == "media_key"`. Same for `user_media_submissions` (PK `user_id`, SK `media_key`).
3. Trigger a save from the mobile app for each source (YouTube URL, web article, shared text, shared audio). All should return 202.
4. Tail `/aws/lambda/media-summarizer-api` logs and confirm no `ValidationException` or `ResourceNotFoundException` on idempotence calls.

## Notes for the implementer

- The code that hits these tables is already aligned: `media_summarizer/utils/media_idempotence.py` (uses `Key={"media_key": ...}`), `media_summarizer/utils/user_media_submissions.py` (uses `Key={"user_id", "media_key"}`), `media_summarizer/core/media_ingestion/adapters/orchestrators.py:169-205,699,716`, `media_summarizer/core/services/media_submission.py`. No code changes required.
- `episode_guid` still appears in domain logic for podcasts (e.g. `media_summarizer/api/endpoints/podcast_search.py`, `media_summarizer/workers/rss_feed_poll_worker.py`) but those are RSS feed identifiers, not DB keys. Leave them alone.
- After the rename, the comment `Renamed from legacy "episode_watchers" (episode_guid PK)` near `dynamodb_core_tables.tf:289` becomes a useful precedent for what we're doing here.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 Terraform resources renamed: episode_idempotence_v1 → media_idempotence_v1 (name=media_idempotence, hash_key=media_key); user_episode_submissions_v1 → user_media_submissions_v1 (name=user_media_submissions, hash_key=user_id, range_key=media_key)
- [ ] #2 Output block episode_idempotence_table_name renamed to media_idempotence_table_name and points to the new resource
- [ ] #3 lambda_api.tf and lambda_workers.tf both wire MEDIA_IDEMPOTENCE_TABLE and USER_MEDIA_SUBMISSIONS_TABLE to the new resources
- [ ] #4 IAM policies on API + workers updated to reference the new table ARNs (no dangling refs to the old names)
- [ ] #5 terraform plan shows 2 tables destroyed (episode_idempotence, user_episode_submissions) and 2 created (media_idempotence, user_media_submissions); no other DynamoDB resource changes
- [ ] #6 After deploy: aws dynamodb describe-table confirms KeySchema is media_key (HASH) for media_idempotence and user_id (HASH) + media_key (RANGE) for user_media_submissions
- [ ] #7 Mobile save succeeds end-to-end for YouTube URL, web article, shared text, and shared audio (HTTP 202, no 500)
- [ ] #8 CloudWatch logs show no ValidationException or ResourceNotFoundException on idempotence GetItem/PutItem calls
- [ ] #9 No code changes in media_summarizer/ — fix is infra-only
<!-- AC:END -->
