---
owner_decision: more
---

# Benchmark: Lambda-only deployment for V1 backend (workers + FastAPI API)

## Owner Validation

**Decision**: re-vérifier l'hypothèse ffmpeg
**Validated at**: _(ISO date to be filled by owner)_

---

## Recommendation

**Deploy the entire V1 backend as Lambda functions using container images (ECR), with API Gateway HTTP API as the front door for the FastAPI API.**

Key points:
- One Lambda per SQS worker (8-10 functions), triggered by `aws_lambda_event_source_mapping`
- One Lambda for the FastAPI API, using Mangum as ASGI adapter
- API Gateway HTTP API for custom domain, CORS, and OAuth callback compatibility
- Container image deployment (mandatory for yt-dlp + ffmpeg binary dependencies)
- ARM/Graviton2 for all functions (20% cost saving vs x86)
- No VPC required (all services accessible via public endpoints)
- Estimated cost: $3-8/month at 100 users, $15-50/month at 1000 users

---

## 1. FastAPI on Lambda: Mangum vs AWS Lambda Web Adapter

### Analysis

The codebase uses FastAPI with the following key dependencies relevant to Lambda:
- **FastAPI + Pydantic v2** -- pure Python, fully compatible
- **boto3 / aioboto3** -- native Lambda SDK, fully compatible
- **python-jose[cryptography]** -- requires `cryptography` C extension (pre-built manylinux wheels available)
- **passlib[bcrypt]** -- requires `bcrypt` C extension (manylinux wheels available)
- **slowapi + redis** -- slowapi works in-memory per invocation; Redis used for rate limiting requires external Redis (can be simplified for Lambda with API Gateway throttling)
- **openai, httpx, tenacity, feedparser, trafilatura, algoliasearch** -- pure Python or have manylinux wheels
- **yt-dlp** -- pure Python but requires ffmpeg binary for some operations
- **openai-whisper** -- not used in V1 active path (Deepgram is active; whisper disabled)

### Mangum (Recommended)

| Attribute | Detail |
|-----------|--------|
| Maturity | v0.21.0, 2026-02-01; widely used in production |
| Mechanism | Python ASGI adapter; `handler = Mangum(app, lifespan="off")` |
| Supported events | API Gateway HTTP API, REST API, ALB, Function URLs, Lambda@Edge |
| Dependencies | Zero -- pure Python, ~100 LOC |
| FastAPI compat | Full (any ASGI framework) |
| Drawback | Lifespan events partially supported (startup runs per cold start) |

### AWS Lambda Web Adapter

| Attribute | Detail |
|-----------|--------|
| Maturity | AWS-maintained Lambda extension |
| Mechanism | Runs uvicorn inside Lambda, proxies events as HTTP; zero code change |
| Supported events | API Gateway, ALB, Function URLs |
| Dependencies | Adds ~15MB Lambda Layer (Go binary) |
| FastAPI compat | Full (app runs unchanged) |
| Drawback | Extra layer, slight cold start overhead from spawning uvicorn process |

### Verdict: Mangum

Mangum is simpler, lighter, zero-dependency, and the standard approach for FastAPI on Lambda. It requires a one-line adapter (`handler = Mangum(app, lifespan="off")`). The codebase already separates `app` creation in `media_summarizer/api/main.py`, making integration trivial.

**Note on redis/slowapi**: The current rate limiter uses `slowapi` with a Redis backend. On Lambda, replace with API Gateway built-in throttling (per-route/per-stage) and remove the Redis dependency for V1. This is a minor code change (remove `SlowAPIMiddleware`, rely on API Gateway throttle settings).

---

## 2. Front Door: API Gateway HTTP API vs Lambda Function URL

| Criterion | API Gateway HTTP API | Lambda Function URL |
|-----------|---------------------|---------------------|
| **Cost** | $1.00/million requests (first 300M) | Free (included in Lambda pricing) |
| **Custom domain** | Native (`aws_apigatewayv2_domain_name`) | Requires CloudFront distribution in front |
| **WAF** | Not directly (HTTP API lacks WAF; REST API has it) | Not directly (needs CloudFront) |
| **CORS** | Built-in configuration | Must handle in application code |
| **OAuth callbacks** | Supports redirect URIs with custom domains | Redirect works but ugly URL |
| **Throttling** | Per-route, per-stage configurable | Only Lambda concurrency controls |
| **JWT Authorizer** | Built-in JWT authorizer for API Gateway | Must implement in app code |
| **Response streaming** | Not supported (HTTP API) | Supported |

### Verdict: API Gateway HTTP API

For V1, API Gateway HTTP API is the right choice:
1. **Custom domain is essential** for OAuth callbacks (Apple/Google require a stable callback URL like `https://api.media-summarizer.app/api/v1/auth/apple/callback`).
2. **Built-in CORS** eliminates app-level CORS middleware complexity.
3. **Throttling** replaces the need for slowapi/Redis.
4. **Cost is negligible**: at 1000 users with 100 API calls/day = 3M requests/month = $3/month.
5. No WAF needed for V1 (future consideration for REST API if DDoS becomes a concern).

Reference: https://aws.amazon.com/api-gateway/pricing/

---

## 3. Workers: SQS-triggered Lambdas -- Runtime Analysis

Each existing worker polls an SQS queue in a `while True` loop. On Lambda, this becomes an `aws_lambda_event_source_mapping` that invokes the handler per batch of messages. The handler processes one message and returns success/failure.

### Per-worker runtime analysis

| Worker | Queue | What it does | Expected p95 duration | Lambda 15-min OK? |
|--------|-------|--------------|----------------------|-------------------|
| **podcastindex_resolution** | `podcastindex-resolution-queue` | HTTP call to PodcastIndex API + DynamoDB write | 5-10s | YES |
| **article_extraction** | `article-extraction-queue` | HTTP fetch + trafilatura extraction + S3 upload | 10-20s | YES |
| **x_ingestion** | `x-ingestion-queue` | HTTP call to X API v2 + S3 upload | 5-10s | YES |
| **youtube_ingestion** | `youtube-ingestion-queue` | YouTube transcript API OR yt-dlp metadata extraction (no download) + S3 upload | 20-40s | YES |
| **tiktok_ingestion** | `tiktok-ingestion-queue` | yt-dlp metadata extraction (no download) + subtitle fetch + S3 upload | 20-40s | YES |
| **download** | `audio-download-queue` | HTTP stream download audio file (~50-200MB) + S3 upload | 60-180s | YES |
| **deepgram_transcription** | `deepgram-transcription-queue` | HTTP POST to Deepgram API (URL-based, Deepgram fetches audio) + S3 upload | 30-120s (depends on audio length; 2h audio = ~30s with Nova-3) | YES |
| **summarization** | `summarization-queue` | S3 download transcript + OpenAI API call + S3 upload summary | 15-60s | YES |
| **document_parsing** | `document-parsing-queue` | S3 download + LlamaParse API (polling) OR Unstructured API + S3 upload | 30-180s (big PDFs with LlamaParse polling) | YES |
| **search_indexing** | `search-indexing-queue` | S3 download transcript + Algolia index call | 5-10s | YES |
| **rss_feed_poll** | `rss-feed-poll-queue` | Parse RSS feeds + route items | 10-30s | YES |
| **media_completed_events** | `episode-completed-events` | DynamoDB reads + fan-out | 5-10s | YES |
| **flashcards** | `flashcards-queue` | S3 download + OpenAI API + S3/DynamoDB write | 15-60s | YES |
| **notes** | (notes queue) | S3 download + OpenAI API + S3/DynamoDB write | 15-60s | YES |
| **summary** | (summary queue) | Similar to summarization | 15-60s | YES |

**Critical observation**: None of the workers download and process audio locally. The Deepgram worker sends a URL to Deepgram's API, which fetches and transcribes audio server-side. The download_worker streams audio to S3, which fits within Lambda's 15-min timeout even for large files. yt-dlp is used only for metadata extraction (no actual download), so it completes in under 60s.

**Whisper worker**: Listed in Terraform but the V1 active path uses Deepgram exclusively. Whisper (openai-whisper) requires large model files and GPU/CPU-intensive local processing -- it is NOT deployed in Lambda. For V1, remove the whisper worker entirely.

---

## 4. Deployment Format: Zip vs Container Image

### Requirements analysis

| Dependency | Binary? | Size | Zip-compatible? |
|-----------|---------|------|----------------|
| ffmpeg | System binary | ~80-120MB | NO (exceeds 250MB unzipped limit with other deps) |
| yt-dlp | Pure Python | ~15MB | YES (but useless without ffmpeg for some ops) |
| cryptography | C extension | ~5MB wheel | YES (manylinux wheel) |
| bcrypt | C extension | ~1MB wheel | YES (manylinux wheel) |
| trafilatura + lxml | C extensions | ~15MB | YES (manylinux wheels) |
| All Python deps total | Mixed | ~200-300MB estimated | BORDERLINE for 250MB unzipped limit |

### Verdict: Container Image (mandatory)

1. **ffmpeg is required** by the download_worker (audio format detection) and potentially by yt-dlp for audio extraction fallback.
2. **Total dependency size exceeds 250MB unzipped** when including ffmpeg + all Python packages.
3. Container images support **up to 10GB** uncompressed, giving ample room.
4. The project already has `infrastructure/docker/lambda.Dockerfile` as a starting point.
5. **Single ECR repository** with tagged images per function (or a shared base image with per-function CMD overrides).

Recommended approach:
- **Base image**: `public.ecr.aws/lambda/python:3.11` (ARM variant: `public.ecr.aws/lambda/python:3.11-arm64`)
- Install ffmpeg via `yum install -y ffmpeg` or copy a static build
- Install all Python deps via `uv pip install`
- Override `CMD` per function in Terraform (`image_config { command = ["handler.module"] }`)

Container image size estimate: ~500-700MB compressed (well within 10GB limit).

---

## 5. Cold Starts

### ARM/Graviton2 baseline

Lambda on Graviton2 (ARM) provides:
- 20% lower cost per GB-second ($0.0000133334 vs $0.0000166667)
- Comparable or better cold start times vs x86 for Python workloads
- All dependencies (cryptography, bcrypt, lxml) have `manylinux_aarch64` wheels

**Cold start estimates** (container image, ARM, 1024MB memory):
- **API Lambda**: 3-8s cold start (FastAPI app init + import overhead)
- **Worker Lambdas**: 2-5s cold start (simpler init)

### Mitigation strategy

| Lambda | Cold start impact | Mitigation |
|--------|------------------|------------|
| API | Noticeable (mobile user sees delay) | Provisioned Concurrency = 1 ($13/month at 1024MB) |
| Workers | Invisible (async, user not waiting) | None needed |

**Recommendation for V1**:
- Start with **no Provisioned Concurrency** -- cold starts are 3-8s but only affect the first request after idle. With 100-1000 users, the API Lambda will stay warm most of the time during active hours.
- If cold starts become a problem in practice, add Provisioned Concurrency = 1 for the API Lambda only.
- Use `LAMBDA_INIT_TIMEOUT` and lazy imports to minimize cold start time.

Reference: https://aws.amazon.com/lambda/pricing/ (Provisioned Concurrency section)

---

## 6. VPC Requirements

### Services accessed by Lambdas

| Service | Access method | VPC needed? |
|---------|--------------|-------------|
| DynamoDB | Public endpoint (or VPC endpoint) | NO |
| S3 | Public endpoint (or VPC endpoint) | NO |
| SQS | Public endpoint (or VPC endpoint) | NO |
| Secrets Manager | Public endpoint (or VPC endpoint) | NO |
| Deepgram API | Public internet | NO |
| OpenAI API | Public internet | NO |
| LlamaParse API | Public internet | NO |
| Unstructured API | Public internet | NO |
| PodcastIndex API | Public internet | NO |
| X API | Public internet | NO |
| Algolia API | Public internet | NO |

### Verdict: No VPC required

None of the services accessed by any Lambda function require VPC placement. All AWS services (DynamoDB, S3, SQS, Secrets Manager) are reachable via public endpoints, and all third-party APIs are on the public internet.

**Benefits of no VPC**:
- No cold start penalty from ENI attachment (adds 1-5s)
- No NAT Gateway cost ($0.045/hour + data transfer = ~$32/month minimum)
- Simpler Terraform (no subnet/security group configuration for Lambdas)
- Current VPC resources in `scaling.tf` (security groups, subnet refs) are only needed for ECS and can be removed

---

## 7. Secrets Manager Integration

### Current state

The V1 launch plan describes a consolidated secret (`media-summarizer-runtime-<env>`) containing all API keys as a JSON object. The `terraform.tfvars.example` shows a `secret_payload` variable with ~20 keys.

Currently in `scaling.tf`:
- `aws_secretsmanager_secret.openai_api_key` (lines 650-658)
- `aws_secretsmanager_secret.deepgram_api_key` (lines 666-676)
- ECS containers reference these via `secrets` block in task definitions (lines 617-627)

### Lambda integration approach

For Lambda with container images, secrets are loaded at function init time:

```python
# In each Lambda handler's init (outside handler function):
import boto3
import json

secrets_client = boto3.client("secretsmanager")
response = secrets_client.get_secret_value(SecretId="media-summarizer-runtime-prod")
secrets = json.loads(response["SecretString"])

# Inject into os.environ for compatibility with existing code
for key, value in secrets.items():
    os.environ.setdefault(key, value)
```

**Alternative (recommended)**: Use AWS Lambda Powertools `get_secret` utility or simply set environment variables directly in the Lambda function configuration, referencing Secrets Manager ARNs via Terraform `dynamic` blocks. However, for a consolidated secret with 20+ keys, the init-time fetch approach is cleanest and compatible with the existing `os.getenv(...)` pattern used throughout the codebase.

### IAM policy required

```hcl
{
  Effect = "Allow"
  Action = [
    "secretsmanager:GetSecretValue"
  ]
  Resource = [
    aws_secretsmanager_secret.runtime_config.arn
  ]
}
```

This is straightforward and does not require changes to the existing secret structure.

---

## 8. What Stays (existing Terraform resources)

| File | Resources | Status |
|------|-----------|--------|
| `dynamodb_core_tables.tf` | users, processing_jobs, auth_tokens, episode_idempotence, user_episode_submissions, episode_watchers, user_tags, user_folders, pricing_config | **STAYS** (unchanged) |
| `dynamodb_digest_tables.tf` | Digest-related tables | **STAYS** (unchanged) |
| `dynamodb_minutes_tables.tf` | Minutes/credit tables | **STAYS** (unchanged) |
| `dynamodb_revenucat_events.tf` | RevenueCat events table | **STAYS** (unchanged) |
| `archiving.tf` | S3 archives bucket, job_archiver Lambda, DynamoDB stream mapping | **STAYS** (already Lambda-based) |
| `monitoring.tf` | ops_alerts SNS topic, CloudWatch metric filters, alarms, dashboard | **PARTIALLY STAYS** -- SNS topic and alarms stay; log group references need updating from `/ecs/...` to `/aws/lambda/...` |
| `pipeline_alerts.tf` | Pipeline stage alerting | **STAYS** (metric namespace unchanged) |
| `pipeline_dashboard.tf` | CloudWatch dashboard | **PARTIALLY STAYS** -- log source references need updating |
| `scaling.tf` -- SQS queues | All 8 SQS queues + DLQs (lines 264-471) | **STAYS** (unchanged) |
| `scaling.tf` -- S3 buckets | audio, transcripts, summaries (lines 474-499) | **STAYS** (unchanged) |
| `scaling.tf` -- DynamoDB tables | processing_jobs, users (lines 502-561) | **DELETE** (duplicated in `dynamodb_core_tables.tf`) |
| `scaling.tf` -- Secrets Manager | openai_api_key, deepgram_api_key (lines 649-681) | **REPLACE** with consolidated runtime secret |
| `scaling.tf` -- CloudWatch log groups | `/ecs/...` worker logs (lines 250-261) | **REPLACE** with `/aws/lambda/...` log groups |

---

## 9. What Gets Deleted

| File/Resource | Lines | Reason |
|--------------|-------|--------|
| `scaling.tf` -- ECS cluster | 68-81 | No longer needed |
| `scaling.tf` -- Security group for Fargate | 84-102 | No VPC/Fargate |
| `scaling.tf` -- IAM roles for ECS (task execution + task) | 105-247 | Replaced by Lambda IAM roles |
| `scaling.tf` -- ECS task definitions | 565-647 | Replaced by Lambda functions |
| `scaling.tf` -- Scaling controller Lambda | 684-930 | No ECS to scale; SQS triggers Lambda directly |
| `scaling.tf` -- ECR repository (ephemeral-worker) | 932-946 | Replaced by new ECR repo(s) for Lambda images |
| `scaling.tf` -- CloudWatch alarms for queue→scaling | 840-871 | Replaced by Lambda concurrency (auto-scaling) |
| `scaling.tf` -- SNS topic for scaling alerts | 874-898 | No scaling controller |
| `scaling.tf` -- EventBridge rule (2-min scaling check) | 901-930 | No scaling controller |
| VPC variables | `vpc_id`, `subnet_ids` | No longer needed |

---

## 10. What Gets Created

### New Terraform resources

```
# ECR
aws_ecr_repository.lambda_workers          # Shared repo for all Lambda container images

# Lambda Functions (workers)
aws_lambda_function.worker["podcastindex_resolution"]
aws_lambda_function.worker["article_extraction"]
aws_lambda_function.worker["x_ingestion"]
aws_lambda_function.worker["youtube_ingestion"]
aws_lambda_function.worker["tiktok_ingestion"]
aws_lambda_function.worker["download"]
aws_lambda_function.worker["deepgram_transcription"]
aws_lambda_function.worker["summarization"]
aws_lambda_function.worker["document_parsing"]
aws_lambda_function.worker["search_indexing"]
aws_lambda_function.worker["rss_feed_poll"]
aws_lambda_function.worker["media_completed_events"]
aws_lambda_function.worker["flashcards"]
aws_lambda_function.worker["notes"]

# Lambda Function (API)
aws_lambda_function.api

# SQS Event Source Mappings (one per worker)
aws_lambda_event_source_mapping.worker["podcastindex_resolution"]
aws_lambda_event_source_mapping.worker["article_extraction"]
... (one per queue)

# API Gateway HTTP API
aws_apigatewayv2_api.main
aws_apigatewayv2_stage.default
aws_apigatewayv2_integration.lambda_api
aws_apigatewayv2_route.default            # $default route -> Lambda
aws_apigatewayv2_domain_name.api
aws_apigatewayv2_api_mapping.api
aws_acm_certificate.api                   # TLS cert for custom domain
aws_route53_record.api                    # DNS record

# IAM
aws_iam_role.lambda_worker                # Shared role for all worker Lambdas
aws_iam_role.lambda_api                   # Role for API Lambda
aws_iam_policy.lambda_worker_policy       # SQS + S3 + DynamoDB + Secrets Manager + Logs
aws_iam_policy.lambda_api_policy          # S3 + DynamoDB + SQS (SendMessage) + Secrets Manager + Logs

# CloudWatch Log Groups
aws_cloudwatch_log_group.lambda_worker["..."]  # One per worker
aws_cloudwatch_log_group.lambda_api

# Secrets Manager (consolidated)
aws_secretsmanager_secret.runtime_config
aws_secretsmanager_secret_version.runtime_config

# Lambda Permissions
aws_lambda_permission.api_gateway         # Allow API Gateway to invoke API Lambda
```

### Per-worker Lambda configuration

| Worker | Memory | Timeout | Concurrency | Notes |
|--------|--------|---------|-------------|-------|
| podcastindex_resolution | 256 MB | 60s | unreserved | Light HTTP call |
| article_extraction | 512 MB | 60s | unreserved | trafilatura needs ~256MB |
| x_ingestion | 256 MB | 60s | unreserved | Light HTTP call |
| youtube_ingestion | 512 MB | 120s | unreserved | yt-dlp metadata extraction |
| tiktok_ingestion | 512 MB | 120s | unreserved | yt-dlp metadata extraction |
| download | 1024 MB | 300s | unreserved | Streams large audio to S3, needs memory for httpx buffer |
| deepgram_transcription | 512 MB | 600s | unreserved | Waits for Deepgram API (up to 5min for very long audio) |
| summarization | 512 MB | 300s | unreserved | OpenAI API call with timeout=120s |
| document_parsing | 512 MB | 600s | unreserved | LlamaParse polling can take minutes |
| search_indexing | 256 MB | 60s | unreserved | Algolia index call |
| rss_feed_poll | 512 MB | 120s | unreserved | Multiple HTTP fetches |
| media_completed_events | 256 MB | 60s | unreserved | DynamoDB reads + SQS sends |
| flashcards | 512 MB | 300s | unreserved | OpenAI API call |
| notes | 512 MB | 300s | unreserved | OpenAI API call |
| **API** | 1024 MB | 30s | unreserved (or PC=1) | FastAPI with Mangum |

---

## 11. Migration Plan

### Approach: Hard cutover (recommended for V1)

Blue-green is possible but adds complexity for a pre-launch system with no production traffic yet.

**Migration steps**:
1. Write new Terraform module (`infrastructure/terraform/lambda.tf` or split into `lambda_workers.tf` + `lambda_api.tf` + `api_gateway.tf`)
2. Build and push container images to ECR
3. Remove ECS resources from `scaling.tf` (cluster, task defs, scaling controller, ECR ephemeral-worker)
4. Apply Terraform: creates Lambda functions + API Gateway, deletes ECS resources
5. SQS queues stay the same -- messages route to Lambda instead of ECS tasks
6. Verify API via custom domain
7. Update V1_LAUNCH_PLAN.md to reflect Lambda-only architecture

**If incremental migration is preferred**:
- Phase 1: Deploy API Lambda + API Gateway alongside existing infra (no conflict)
- Phase 2: Add Lambda workers with SQS event source mappings (SQS delivers to Lambda instead of being polled by ECS)
- Phase 3: Delete ECS resources

Since there is no production traffic, hard cutover is simpler and recommended.

---

## 12. Cost Projection

### Assumptions

- Typical user: 5 media submissions/week
- Per submission: 1 API call (ingest) + 1 worker invocation chain (~3-5 Lambda invocations: resolver -> download/extract -> transcription -> summarization -> events)
- Average Lambda duration per worker invocation: 30s at 512MB
- API: 100 requests/user/day (checking status, browsing artifacts, search)
- Architecture: ARM/Graviton2

### Pricing references

- Lambda: $0.20/million requests + $0.0000133334/GB-second (ARM) -- https://aws.amazon.com/lambda/pricing/
- API Gateway HTTP API: $1.00/million requests -- https://aws.amazon.com/api-gateway/pricing/
- DynamoDB on-demand: $1.25/million writes, $0.25/million reads -- https://aws.amazon.com/dynamodb/pricing/on-demand/
- S3 Standard: $0.023/GB-month storage, $0.005/1000 PUT, $0.0004/1000 GET -- https://aws.amazon.com/s3/pricing/
- SQS: $0.40/million requests (first 1M free) -- https://aws.amazon.com/sqs/pricing/
- Secrets Manager: $0.40/secret/month + $0.05/10000 API calls -- https://aws.amazon.com/secrets-manager/pricing/

### Cost table

| Component | 100 users | 1,000 users | 10,000 users |
|-----------|-----------|-------------|--------------|
| **Lambda (workers)** | | | |
| - Requests (5 media * 4 invocations * 4.3 weeks) | 8,600 req ($0.00) | 86,000 req ($0.02) | 860,000 req ($0.17) |
| - Duration (avg 30s @ 512MB = 15 GB-s each) | 129,000 GB-s ($1.72) | 1,290,000 GB-s ($17.20) | 12,900,000 GB-s ($172.00) |
| **Lambda (API)** | | | |
| - Requests (100/user/day * 30 days) | 300,000 req ($0.06) | 3,000,000 req ($0.60) | 30,000,000 req ($6.00) |
| - Duration (avg 100ms @ 1024MB = 0.1 GB-s) | 30,000 GB-s ($0.40) | 300,000 GB-s ($4.00) | 3,000,000 GB-s ($40.00) |
| **API Gateway HTTP API** | 300,000 req ($0.30) | 3,000,000 req ($3.00) | 30,000,000 req ($30.00) |
| **DynamoDB** | ~500K RCU + 200K WCU ($0.75) | ~5M RCU + 2M WCU ($3.75) | ~50M RCU + 20M WCU ($37.50) |
| **S3** | ~5GB storage ($0.12) + requests ($0.05) | ~50GB ($1.15) + requests ($0.50) | ~500GB ($11.50) + requests ($5.00) |
| **SQS** | ~35K messages (free tier) ($0.00) | ~350K messages (free tier) ($0.00) | ~3.5M messages ($1.00) |
| **Secrets Manager** | 1 secret ($0.40) | 1 secret ($0.40) | 1 secret ($0.40) |
| **CloudWatch Logs** | ~1GB ($0.50) | ~10GB ($5.00) | ~100GB ($50.00) |
| **ECR** | ~2GB images ($0.20) | ~2GB images ($0.20) | ~2GB images ($0.20) |
| | | | |
| **TOTAL (Lambda architecture)** | **~$4.50/month** | **~$35.82/month** | **~$353.77/month** |
| **Free tier offset (year 1)** | -$2.50 | -$5.00 | -$8.00 |
| **Net (year 1)** | **~$2.00/month** | **~$31/month** | **~$346/month** |

### Comparison: ECS Fargate baseline

ECS Fargate costs for always-on workers (minimum viable):
- 1 task running 24/7 at 0.25 vCPU / 0.5 GB: $0.25 * $0.04048/hr * 730h + 0.5 * $0.004446/hr * 730h = ~$9.02/month per task
- With 3-4 tasks running for minimal coverage: **$27-36/month baseline** even with zero traffic
- Plus scaling controller Lambda, ECR storage, VPC NAT Gateway (~$32/month if used)

**Lambda wins decisively** at low-to-medium traffic due to pay-per-use with no idle cost.

| Scale | Lambda | ECS Fargate (estimated) | Savings |
|-------|--------|------------------------|---------|
| 100 users | $4.50/month | ~$40-70/month | 85-93% |
| 1,000 users | $36/month | ~$80-150/month | 55-76% |
| 10,000 users | $354/month | ~$200-400/month | ~0% (comparable) |

At 10,000 users, Lambda and ECS converge. Beyond that, ECS becomes more cost-effective. For V1 (100-1000 users), Lambda is 5-20x cheaper.

---

## 13. Risks

| # | Risk | Severity | Mitigation |
|---|------|----------|-----------|
| 1 | **ffmpeg binary on Lambda ARM** -- static ffmpeg builds for aarch64 exist but must be tested. Some community layers may be x86-only. | Medium | Use container image with `yum install ffmpeg` from Amazon Linux 2023 repos, or bundle a static ffmpeg binary from https://johnvansickle.com/ffmpeg/ (provides aarch64 builds). Test in CI. **Acceptable for V1** with container images. |
| 2 | **API response payload > 6MB** -- Lambda synchronous invocation has a 6MB response limit. Large artifact responses (e.g., full transcript text) could exceed this. | Low | Transcripts and summaries are stored in S3; API returns pre-signed URLs for large content (already the pattern in `summarization_worker.py` line 369-376). No full-text responses > 6MB expected. **Acceptable for V1**. |
| 3 | **File upload > 6MB request body** -- Lambda request payload limit is 6MB (synchronous). Document uploads (PDF, DOCX) could exceed this. | Medium | The current architecture uses **S3 pre-signed upload URLs** -- the mobile app uploads directly to S3, then sends only the S3 key to the API. This pattern avoids the 6MB limit entirely. Verify this is the current flow for document ingestion. If direct upload to API exists, refactor to pre-signed URL pattern. **Mitigated by architecture pattern**. |
| 4 | **Cold start latency for API** -- 3-8s cold start for the first request after idle period could frustrate mobile users. | Medium | At 100+ active users, the API Lambda stays warm during business hours. For off-peak hours, consider: (a) CloudWatch EventBridge ping every 5 min to keep warm, or (b) Provisioned Concurrency = 1 ($13/month). **Acceptable for V1** -- monitor and add PC if needed. |
| 5 | **SQS visibility timeout vs Lambda timeout mismatch** -- If Lambda times out (e.g., document_parsing at 600s) but SQS visibility timeout is shorter, the message becomes visible again and gets reprocessed. | Medium | Set SQS `visibility_timeout_seconds` = 6x Lambda timeout for each queue. Current values: deepgram=1800s (fine for 600s timeout), download=300s (fine for 300s). Terraform handles this. **Mitigated by configuration**. |
| 6 | **yt-dlp version pinning** -- yt-dlp is updated frequently (sometimes multiple times per day) to fix extractor breakage. On Lambda container images, updates require image rebuild and redeploy. | Low | Pin yt-dlp to a working version in `pyproject.toml`. Rebuild and redeploy when extractors break (same as Docker-based deployment). CI/CD pipeline should support quick image rebuilds. **Acceptable for V1**. |
| 7 | **Concurrent execution limit** -- Default Lambda concurrency is 1000 per region. With 10+ Lambda functions sharing this pool, a burst of submissions could hit the limit. | Low | At V1 scale (100-1000 users), peak concurrency will be <50. Request concurrency increase if needed later. Set reserved concurrency on critical functions (API=100, deepgram=50) to prevent noisy-neighbor starvation. **Acceptable for V1**. |
| 8 | **Redis removal for rate limiting** -- Current `slowapi` uses Redis. Removing Redis means relying on API Gateway throttling, which is less granular (per-stage, not per-user). | Low | For V1, per-stage throttling (e.g., 1000 req/s globally) is sufficient. Per-user rate limiting can be added later via DynamoDB-backed token bucket if needed. The existing rate limits are generous for V1 scale. **Acceptable for V1**. |
| 9 | **Container image size and build time** -- With all dependencies + ffmpeg, images could be 1-2GB, making CI/CD builds slow (5-10 min). | Low | Use multi-stage builds with dependency caching. Share a base layer across all functions. ECR layer caching reduces subsequent pushes to delta-only. **Acceptable for V1**. |
| 10 | **openai-whisper dependency** -- Listed in `pyproject.toml` but not used in active V1 path. It pulls PyTorch (~2GB), which would bloat the container image massively. | High | **Remove `openai-whisper` from `pyproject.toml`** before building Lambda images. The V1 transcription path is 100% Deepgram. Whisper is a dead dependency. This is a prerequisite for the Lambda migration. |

---

## 14. Library Compatibility Check (pyproject.toml)

| Library | Version | Lambda zip? | Lambda container? | Notes |
|---------|---------|-------------|-------------------|-------|
| fastapi | >=0.104.0 | YES | YES | Pure Python |
| uvicorn | >=0.24.0 | YES | YES | Not needed on Lambda (Mangum replaces it) |
| aioboto3 | >=15.0.0 | YES | YES | Pure Python wrapper |
| boto3 | >=1.38.23 | YES | YES | Pre-installed in Lambda runtime |
| botocore | >=1.38.23 | YES | YES | Pre-installed in Lambda runtime |
| openai | >=1.3.0 | YES | YES | Pure Python |
| **openai-whisper** | >=20231117 | **NO** | **NO** (2GB+ with PyTorch) | **REMOVE** -- not used in V1 |
| feedparser | >=6.0.10 | YES | YES | Pure Python |
| httpx | >=0.25.0 | YES | YES | Pure Python |
| pydantic | >=2.5.0 | YES | YES | Pure Python + Rust extension (manylinux wheel) |
| tenacity | >=8.2.0 | YES | YES | Pure Python |
| python-multipart | >=0.0.6 | YES | YES | Pure Python |
| python-jose[cryptography] | >=3.3.0 | MAYBE | YES | cryptography needs C ext (manylinux wheel, ~5MB) |
| passlib[bcrypt] | >=1.7.4 | MAYBE | YES | bcrypt C ext (manylinux wheel) |
| bcrypt | >=3.2.0,<4.0.0 | MAYBE | YES | C extension (manylinux wheel) |
| email-validator | >=2.0.0 | YES | YES | Pure Python |
| docker | >=6.1.0 | YES | YES | **Not needed on Lambda** (dev dependency, remove from main deps) |
| slowapi | >=0.1.8 | YES | YES | **Remove for Lambda** (use API Gateway throttling) |
| redis | >=5.0.0 | YES | YES | **Remove for Lambda** (no Redis needed) |
| Jinja2 | >=3.1.3 | YES | YES | Pure Python |
| trafilatura | >=1.12.0 | MAYBE | YES | Has C dependencies (lxml); manylinux wheels exist |
| youtube-transcript-api | any | YES | YES | Pure Python |
| yt-dlp | any | YES | YES | Pure Python (but needs ffmpeg system binary) |
| fsrs | >=1.0.0 | YES | YES | Pure Python |
| algoliasearch | >=4.0.0 | YES | YES | Pure Python |
| python-dotenv | >=1.0.0 | YES | YES | Pure Python |

### Dependencies to REMOVE before Lambda migration

1. `openai-whisper` -- pulls PyTorch, not used in V1
2. `docker` -- dev utility, not needed at runtime
3. `slowapi` + `redis` -- replaced by API Gateway throttling

### Dependencies to ADD

1. `mangum` -- ASGI adapter for Lambda (~0.1MB)

---

## 15. Recommended Architecture (Terraform Resource Sketch)

### File structure

```
infrastructure/terraform/
  |- dynamodb_core_tables.tf      (unchanged)
  |- dynamodb_digest_tables.tf    (unchanged)
  |- dynamodb_minutes_tables.tf   (unchanged)
  |- dynamodb_revenucat_events.tf (unchanged)
  |- archiving.tf                 (unchanged -- already Lambda)
  |- sqs.tf                       (extracted from scaling.tf -- queues + DLQs only)
  |- s3.tf                        (extracted from scaling.tf -- buckets only)
  |- secrets.tf                   (NEW -- consolidated runtime secret)
  |- lambda_workers.tf            (NEW -- all worker Lambda functions + event source mappings)
  |- lambda_api.tf                (NEW -- API Lambda + API Gateway HTTP API)
  |- ecr.tf                       (NEW -- ECR repository for Lambda images)
  |- iam_lambda.tf                (NEW -- IAM roles and policies for Lambda)
  |- monitoring.tf                (UPDATED -- references Lambda log groups)
  |- pipeline_alerts.tf           (unchanged)
  |- pipeline_dashboard.tf        (UPDATED -- log sources)
  |- scaling.tf                   (DELETED or gutted -- ECS/scaling portions removed)
```

### Architecture diagram (logical)

```
Mobile App
    |
    v
API Gateway HTTP API (custom domain: api.media-summarizer.app)
    |
    v
Lambda: API (FastAPI + Mangum, 1024MB, 30s timeout)
    |
    v (sends messages to SQS queues)
    |
    +---> SQS: podcastindex-resolution-queue ---> Lambda: podcastindex_resolution
    +---> SQS: article-extraction-queue -------> Lambda: article_extraction
    +---> SQS: x-ingestion-queue --------------> Lambda: x_ingestion
    +---> SQS: youtube-ingestion-queue --------> Lambda: youtube_ingestion
    +---> SQS: tiktok-ingestion-queue ---------> Lambda: tiktok_ingestion
    +---> SQS: audio-download-queue -----------> Lambda: download
    +---> SQS: deepgram-transcription-queue ---> Lambda: deepgram_transcription
    +---> SQS: summarization-queue ------------> Lambda: summarization
    +---> SQS: document-parsing-queue ---------> Lambda: document_parsing
    +---> SQS: search-indexing-queue ----------> Lambda: search_indexing
    +---> SQS: rss-feed-poll-queue ------------> Lambda: rss_feed_poll
    +---> SQS: episode-completed-events -------> Lambda: media_completed_events
    +---> SQS: flashcards-queue ---------------> Lambda: flashcards

DynamoDB Stream (processing_jobs) ---> Lambda: job_archiver (existing, unchanged)
```

---

## Owner Decision

_(to be filled by owner after review -- text describing the final decision: accept recommendation, reject because Y, accept with modifications Z)_
