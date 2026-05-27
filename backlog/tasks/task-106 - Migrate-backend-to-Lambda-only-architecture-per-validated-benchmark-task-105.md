---
id: task-106
title: Migrate backend to Lambda-only architecture per validated benchmark (task-105)
status: To Do
assignee: []
created_date: '2026-05-20 10:44'
labels:
  - infra
  - feature
dependencies:
  - task-105
priority: high
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
## Context

This task implements the Lambda-only deployment architecture chosen by the owner in `docs/research/task-105-lambda-migration/README.md`. Read that README first — both the front-matter `owner_decision` field and the `Decision` section under `Owner Validation`. The Decision field is the source of truth: the implementer follows what the owner wrote there, not the initial recommendation.

The current Terraform under `infrastructure/terraform/` has:
- ECS Fargate workers (`scaling.tf`) — to be removed per benchmark recommendation
- 2 utility Lambdas (`scaling_controller`, `job_archiver`) — `scaling_controller` to be removed, `job_archiver` to be kept
- DynamoDB / S3 / SQS / secrets / monitoring — to be kept (the benchmark will confirm exactly which files)
- No FastAPI deployment — to be added

## Scope

Implement the architecture documented in the validated benchmark README. Concretely:

1. Create new Terraform files for:
   - Lambda functions for each worker (one per SQS queue or grouped per the benchmark's recommendation)
   - Lambda function for the FastAPI API (using the front door technology chosen in the benchmark — API Gateway HTTP API or Function URL)
   - Lambda layers if needed (e.g., ffmpeg, yt-dlp binaries)
   - IAM roles + policies (Secrets Manager read, DynamoDB read/write, S3 read/write, SQS receive/send)
   - SQS event source mappings
   - CloudWatch log groups + alarms equivalent to the current ones

2. Adapt application code:
   - Add a Lambda handler entrypoint for the FastAPI API (Mangum or Lambda Web Adapter, per the benchmark)
   - Convert each worker from `while True` SQS polling to an SQS-event-triggered handler. Keep the existing per-message processing logic intact — only swap the entrypoint shell.
   - Remove the (non-existent) `media_summarizer.workers.ephemeral_worker` reference from any docs/Dockerfile

3. Remove old Terraform:
   - Delete the ECS portion of `scaling.tf` (cluster, task definitions, service auto-scaling, scaling Lambda + EventBridge rule, ECR repo if no longer used)
   - Delete the Dockerfile that targets the obsolete ephemeral_worker entrypoint, OR repurpose it as the Lambda container image base if the benchmark chose container deployment.

4. Update `docs/V1_LAUNCH_PLAN.md`:
   - Replace any "ECS/Lambda" wording with the validated Lambda-only architecture
   - Update Phase 3 (infra) and Phase 7 (CI/CD) sections accordingly

5. Add a CI/CD GitHub Actions workflow (or update the existing one) that packages and deploys Lambdas on push to `main`.

## Out of scope

- Local development setup (LocalStack) is not required to be re-architected. Keep the current local docker-compose as-is unless the benchmark explicitly calls for change.
- Mobile and front-end are unaffected.

## Acceptance criteria are at the implementation level — see below. The "what to build" is whatever the README's Decision says.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 The benchmark task-105 README.md has owner_decision: ok before this task starts
- [ ] #2 All Terraform resources listed under 'gets created' in the validated README are implemented and pass `terraform plan` against a clean state
- [ ] #3 All Terraform resources listed under 'gets deleted' in the validated README are removed; `terraform plan` shows no leftover ECS Fargate, ECR, scaling Lambda, EventBridge scaling rule
- [ ] #4 FastAPI API is reachable via the validated front door (API Gateway or Function URL), exercising at least one endpoint end-to-end against a deployed dev environment
- [ ] #5 Each worker SQS queue has an event source mapping to a Lambda; submitting a test message to each queue triggers the corresponding Lambda and produces the expected DynamoDB/S3 side effects
- [ ] #6 docs/V1_LAUNCH_PLAN.md no longer references 'ECS/Lambda' or ECS deployment; Phases 3 and 7 reflect the Lambda-only architecture
- [ ] #7 GitHub Actions workflow deploys the Lambdas (and front door) on push to main; first deploy must be reproducible from a clean checkout
<!-- AC:END -->
