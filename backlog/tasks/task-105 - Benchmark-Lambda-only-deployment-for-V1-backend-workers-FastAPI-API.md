---
id: task-105
title: Benchmark Lambda-only deployment for V1 backend (workers + FastAPI API)
status: To Do
assignee: []
created_date: '2026-05-20 10:43'
labels:
  - benchmark
  - infra
  - scoping
dependencies: []
priority: high
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
## Context

Today the Terraform under `infrastructure/terraform/` provisions:
- ECS Fargate cluster + 8 ephemeral worker task definitions (rss/x/youtube/tiktok/download/deepgram/whisper/summarization) — `scaling.tf`
- 2 Lambdas only: `scaling_controller` (EventBridge every 2 min, decides how many ECS tasks to run) and `job_archiver` (DynamoDB Stream → S3 Glacier)
- DynamoDB tables, S3 buckets, SQS queues, ECR repo
- **Nothing for the FastAPI API** (no ALB, no API Gateway, no ECS service, no App Runner)
- The Dockerfile entrypoint references `media_summarizer.workers.ephemeral_worker` which does not exist in the codebase

The V1 launch plan (`docs/V1_LAUNCH_PLAN.md`) currently says "deploy backend ECS/Lambda via Terraform", which is inaccurate (workers are 100% ECS, API isn't deployed at all).

The owner has expressed strong preference for a **Lambda-only architecture** for V1, given:
- Solo dev, KISS philosophy (cf. user memory)
- Bursty workload (100-1000 users in soft launch)
- Deepgram is async + handles transcription in 15-30s for 2h audio (no risk of hitting Lambda 15-min timeout for transcription)
- All worker processes complete in well under 15 min in practice

## Goal of this benchmark

Produce a recommendation for an end-to-end Lambda-only architecture for V1, validated against the realities of this codebase. The recommendation must answer the following questions explicitly, with citations of code paths and AWS pricing references:

### Compute
1. **FastAPI on Lambda**: Mangum vs AWS Lambda Web Adapter — pros/cons given the libs we use (FastAPI, pydantic v2, boto3, jose, passlib, openai, deepgram-sdk, algoliasearch, yt-dlp, llamaindex/llama-parse-client, unstructured-client). Note any lib that requires native binaries or filesystem access incompatible with Lambda zip deployment.
2. **Front door**: API Gateway HTTP API vs Lambda Function URL. Trade-offs: cost, WAF, custom domain, CORS, OAuth callback compatibility (Apple/Google return URLs).
3. **Workers**: each SQS queue triggers a dedicated Lambda via `aws_lambda_event_source_mapping`. Verify per-worker max runtime is OK (especially: `youtube_ingestion_worker` with yt-dlp, `tiktok_ingestion_worker`, `document_parsing_worker` for big PDFs via LlamaParse polling). Document expected p95 duration per worker based on what the code actually does today.
4. **Deployment format**: zip vs container image. Container image is mandatory if we ship ffmpeg/yt-dlp binaries; otherwise zip is simpler. Decide.
5. **Cold starts**: ARM Graviton2 baseline acceptable? Provisioned Concurrency for the API only? Quantify.

### Networking & secrets
6. **VPC requirements**: do any Lambdas need to be in a VPC? (DynamoDB, S3, SQS, Secrets Manager are all reachable via public endpoints — check if anything else forces VPC).
7. **Secrets Manager integration**: today `infrastructure/terraform/secrets.tf` provisions a consolidated secret. Confirm Lambdas can pull at init from Secrets Manager (e.g., AWS Lambda Powertools Parameters utility) and the IAM policy already in place works.

### Migration scope
8. **What stays**: list explicitly which existing `.tf` files stay (DynamoDB, S3, SQS, secrets, monitoring, archiving Lambda) and which get rewritten or deleted (`scaling.tf` ECS portion, ECR, ephemeral_worker references).
9. **What gets created**: list the new `.tf` resources needed (one Lambda per worker, one Lambda for API, API Gateway/Function URL, Lambda layers if needed for ffmpeg/yt-dlp, IAM roles).
10. **Migration plan**: blue-green possible (new Lambdas alongside old ECS, then DNS/queue cutover), or hard cutover only?

### Cost projection
11. Project monthly AWS cost at 3 levels: 100 users / 1000 users / 10000 users. Assume a typical user submits 5 medias/week. Compare with current ECS Fargate baseline cost. Consider Lambda + API Gateway + Deepgram pass-through + DynamoDB on-demand + S3 + SQS.

### Risks
12. List concrete risks for the V1 launch with this architecture (e.g., yt-dlp on Lambda is well-documented but ffmpeg layer size, large file uploads to API > 6 MB Lambda response limit, etc.). For each risk, propose a mitigation or note "acceptable for V1".

## Deliverable

A single document at `docs/research/task-XX-lambda-migration/README.md` (replace XX with this task's actual ID) with:
- Front-matter: `owner_decision: pending`, all benchmark metadata fields per the project's research conventions
- Sections matching the 12 questions above
- A clear "Recommended architecture" section at the end with a Terraform-level sketch (resource list, no full code)
- A **Decision** section left empty for the owner to fill once reviewed

## Constraints

- This is a research task. Do NOT modify any `.tf` file, do NOT modify worker code. Output is the README only.
- Cite real Lambda limits and AWS pricing pages (URLs).
- For each library used today, verify Lambda compatibility (zip or container) — read `pyproject.toml` and `media_summarizer/workers/` to enumerate.
- Cite the existing Terraform files line-by-line where relevant (e.g., `scaling.tf:565-647` for ECS task defs that get replaced).
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 docs/research/task-XX-lambda-migration/README.md exists with `owner_decision: pending` in front-matter
- [ ] #2 All 12 questions from the description have a dedicated section with a factual answer
- [ ] #3 Recommended architecture section lists every Terraform resource that stays, gets created, and gets deleted
- [ ] #4 Cost projection covers 100/1000/10000 users with explicit assumptions and AWS pricing URL citations
- [ ] #5 All libraries from pyproject.toml that are loaded by workers or API are checked for Lambda zip-vs-container compatibility
- [ ] #6 Risks section lists at least 5 concrete risks with mitigation or 'acceptable for V1' tag
- [ ] #7 Decision section is empty (left for owner)
<!-- AC:END -->
