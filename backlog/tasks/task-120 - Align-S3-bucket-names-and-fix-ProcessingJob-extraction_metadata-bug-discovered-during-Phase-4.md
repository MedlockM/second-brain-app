---
id: task-120
title: Align S3 bucket names env↔terraform and fix ProcessingJob.extraction_metadata bug discovered during Phase 4
status: Done
assignee: []
created_date: '2026-06-08 21:30'
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

Discovered while testing Phase 4 (V1 launch plan §4) — running real ingestion jobs against the AWS dev API endpoint `https://jji077bi8e.execute-api.eu-west-3.amazonaws.com`. The first article ingestion (`POST /api/media/ingest-url` with `https://en.wikipedia.org/wiki/Personal_knowledge_management`) extracted the article successfully but failed at the S3 upload step. Job stayed in `transcribing` state forever.

## Bug 1 — S3 bucket names diverge between `.env` and Terraform (CRITICAL)

The runtime secret `media-summarizer-runtime-dev` (sourced from `.env` racine) declares bucket names that **do not match** the buckets actually created by Terraform.

### Discrepancies

| Env var | `.env` value | Terraform-created bucket (dev) |
|---|---|---|
| `AUDIO_BUCKET` | `media-summarizer-audio` | `media-summarizer-audio-125313707865-dev` |
| `TRANSCRIPT_BUCKET` | `media-summarizer-transcriptions` *(typo: "ions")* | `media-summarizer-transcripts-125313707865-dev` |
| `SUMMARY_BUCKET` | `media-summarizer-summaries` | `media-summarizer-summaries-125313707865-dev` |
| `ARCHIVE_BUCKET` | `media-summarizer-archives` | `media-summarizer-archives-125313707865-dev` |
| `SUMMARY_SHORT_BUCKET` | `media-summarizer-summaries-short` | **NOT CREATED** |
| `SUMMARY_DETAILED_BUCKET` | `media-summarizer-summaries-detailed` | **NOT CREATED** |
| `NOTES_BUCKET` | `media-summarizer-notes` | **NOT CREATED** |
| `QUIZ_BUCKET` | `media-summarizer-quizzes` | **NOT CREATED** |
| `FLASHCARDS_BUCKET` | `media-summarizer-flashcards` | **NOT CREATED** |
| `DOCUMENT_BUCKET` | `media-summarizer-documents` | **NOT CREATED** |

Two distinct issues compounded:

1. **Naming convention mismatch**: Terraform uses `${project_name}-${role}-${account_id}-${environment}` (account-scoped, env-suffixed) but `.env` uses the legacy short names from before the V1 cleanup. `account_id-environment` suffixes are missing everywhere.
2. **Missing buckets**: 6 buckets referenced by workers (`notes`, `flashcards`, `quizzes`, `documents`, `summary_short`, `summary_detailed`) are not declared in `infrastructure/terraform/s3.tf` at all.

### Symptom in production

S3 upload from `article_extraction_worker` fails with `NoSuchBucket: media-summarizer-transcriptions`. Job freezes in `transcribing` state. Same will happen for every other worker that uploads (notes, flashcards, etc.).

### Fix — **Option A.1 validated by owner 2026-06-08**

Extend `s3.tf` to create the 6 missing buckets, and **stop putting bucket names in `secret_payload`** at all. Terraform owns these resources and must inject their names as **plain Lambda env vars** (alongside `RUNTIME_SECRET_NAME`, `ENVIRONMENT`, `PRESTART_INFRA_CHECK`) directly in the `environment.variables` block of each Lambda function (`lambda_workers.tf` + `lambda_api.tf`).

Bucket names are not secrets — they're resource references. The clean separation is:
- **Secrets Manager** ← actual secret values (API keys, JWT keys, OAuth secrets, etc.)
- **Lambda env vars** ← infra references (bucket names, table names, queue URLs) that Terraform owns

This is the only pattern that survives multi-env (dev/staging/prod) and resource renames cleanly without manual `.env` editing.

#### Implementation steps

1. Add `aws_s3_bucket` resources for the 6 missing buckets in `s3.tf` with the convention `${var.project_name}-${role}-${data.aws_caller_identity.current.account_id}-${var.environment}` (same as existing `audio`, `transcripts`, `summaries`, `archives`).
2. Update `lambda_workers.tf` and `lambda_api.tf` `environment.variables` blocks to inject `AUDIO_BUCKET`, `TRANSCRIPT_BUCKET`, `SUMMARY_BUCKET`, `SUMMARY_SHORT_BUCKET`, `SUMMARY_DETAILED_BUCKET`, `NOTES_BUCKET`, `FLASHCARDS_BUCKET`, `QUIZ_BUCKET`, `DOCUMENT_BUCKET`, `ARCHIVE_BUCKET` from the corresponding `aws_s3_bucket.*.bucket` outputs.
3. Remove the bucket-name keys from `secret_payload` in `terraform.tfvars.example` (none should be there — but verify) and from `.env.example` keep them for **local-dev only** (where there's no Terraform layer; local-dev still reads `.env` directly via `python-dotenv`).
4. For local-dev, document in `.env.example` that bucket names are local-dev-only and that on Lambda they come from Terraform-injected env vars.
5. Verify no other code path reads bucket names from Secrets Manager assuming they are there (grep `os.getenv("AUDIO_BUCKET")` etc. — should be unchanged since `os.getenv` reads from env, regardless of source).

#### Alternative options (rejected)

- **A.2** — Generate a `secret_payload` block dynamically in Terraform that includes bucket names. Rejected because it conflates secrets with infra references in a single secret blob and forces every Lambda cold start to fetch the secret to know its bucket names (extra latency + Secrets Manager API calls).
- **B** — Hardcode the Terraform naming convention in `.env` manually per environment. Rejected as fragile: any rename or env switch silently breaks workers.

## Bug 2 — `ProcessingJob.extraction_metadata` field does not exist (HIGH)

`media_summarizer/workers/article_extraction_worker.py` lines 315, 320, 386 do `job.extraction_metadata = ...` but `ProcessingJob` Pydantic model (in `media_summarizer/core/models/processing_job.py`) has **no such field**. Pydantic raises `ValueError: "ProcessingJob" object has no field "extraction_metadata"`.

### Worse symptom

This bug is in the **error-handling path** of the worker (`_mark_job_failed` at line 315). Result: when the article extraction fails for any reason (404, network error, etc.), the worker crashes a *second* time trying to mark the job as failed → SQS message goes to retry → another crash → eventually DLQ → job stays `transcribing` forever.

The field also gets set in the success path (line 386), but I don't know if Pydantic's strict mode trips there too — possibly the success path was reached zero times in production yet because the bucket bug (Bug 1) blocks it earlier.

### Fix

Either:
- Add `extraction_metadata: Optional[Dict[str, Any]]` to `ProcessingJob` model, **or**
- Remove the `job.extraction_metadata = ...` lines if the field is genuinely meant to be ephemeral and not persisted (in which case use a local variable, not a field assignment).

Need to check what called `extraction_metadata` later down the chain (e.g. summarization worker) — if downstream workers read it from the DB, then the field must exist on the model and be persisted.

## Out of scope

- Adding new ingestion sources
- Changing the Pydantic schema beyond what's strictly needed
- Migrating to a new S3 region

## References

- V1 launch plan §Phase 4 (`docs/V1_LAUNCH_PLAN.md`)
- `infrastructure/terraform/s3.tf`
- `media_summarizer/workers/article_extraction_worker.py`
- `media_summarizer/core/models/processing_job.py`
- `.env.example` racine (sections 3-5 list bucket names)
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 All 10 buckets used by workers are created by Terraform (audio, transcripts, summaries, summary_short, summary_detailed, notes, flashcards, quiz, documents, archives) following the convention `${project_name}-${role}-${account_id}-${environment}`
- [ ] #2 `lambda_workers.tf` and `lambda_api.tf` inject all bucket names as plain Lambda env vars from `aws_s3_bucket.*.bucket` outputs (NOT via `secret_payload`)
- [ ] #3 `secret_payload` in `terraform.tfvars.example` does not contain any `*_BUCKET` key (verify and clean if any present)
- [ ] #4 `.env.example` racine documents that bucket names are local-dev only; on Lambda they come from Terraform-injected env vars
- [ ] #5 `ProcessingJob.extraction_metadata` either added to the Pydantic model in `processing_job.py` or removed from `article_extraction_worker.py` (lines 315, 320, 386). Decision must consider whether downstream workers (summarization, notes, flashcards) read this field from DynamoDB
- [ ] #6 `terraform apply` against existing dev env succeeds and creates only the missing buckets + updates Lambda env vars (no destroy of existing buckets)
- [ ] #7 Re-deploy Lambda image after fixing extraction_metadata bug (`docker buildx build --platform linux/arm64 --provenance=false --sbom=false ... --push`) and update all 14 container Lambdas to the new digest
- [ ] #8 Re-test Phase 4 ingestion via the dev API endpoint `https://jji077bi8e.execute-api.eu-west-3.amazonaws.com` with a Wikipedia URL — job reaches `completed` status with all artifacts (transcript on S3, summaries, notes, flashcards generated)
- [ ] #9 Same re-test for at least 1 other source (YouTube or podcast) to validate non-article paths
<!-- AC:END -->
