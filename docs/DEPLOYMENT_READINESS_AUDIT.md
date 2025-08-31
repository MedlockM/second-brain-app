Here’s a focused gap analysis for getting a first production (SaaS) version online, based on what’s actually in the repo.

Executive summary
•  You can run the full system in dev (LocalStack) with Docker Compose. Containers and workers are present and functional.
•  To ship a first prod version, the main blockers are: real authentication, real payments (Stripe) with webhooks, production deploy config (Compose/Infra) and secrets/certificates. There are also a few consistency and safety gaps to address before exposing the API publicly.

What’s missing or needs adjustment to deploy v0

1) Authentication and access control (blocker)
•  Current state:
•  media_summarizer/api/dependencies/auth.py returns a mock user regardless of token and has a TODO to implement verification.
•  Jobs endpoints (media_summarizer/api/endpoints/jobs.py) depend on get_current_user, compare user IDs, and will effectively 403 for real users because the “current user” is always test-user-id.
•  What’s needed:
•  Implement a basic auth flow with JWT issuance and validation (token endpoint + password or email-magic-link). You already have python-jose and passlib in pyproject.toml.
•  Enforce auth consistently: jobs, credits, and any user-scoped reads/writes.
•  Decide short-term identity model: either require login up front, or for v0 allow “email-based identity” via a signed token sent by email (magic link) and remove the current mock shortcut.
•  Fix CORS env naming mismatch: main.py expects ALLOWED_ORIGINS, .env files define CORS_ORIGINS. Align to one key.

2) Payments and credits (blocker)
•  Current state:
•  Credits endpoints (media_summarizer/api/endpoints/credits.py) modify balances directly and write CreditTransaction rows; no interaction with Stripe; no webhook.
•  Stripe SDK is listed as a dependency and STRIPE_* envs exist, but there’s no endpoint to initiate checkout or handle webhooks.
•  What’s needed:
•  Add minimal Stripe flows:
◦  POST /billing/checkout to create a Checkout Session (test first, then live).
◦  POST /webhooks/stripe to receive events (checkout.session.completed, payment_intent.succeeded), verify signature (STRIPE_WEBHOOK_SECRET), credit the user via database_async.update_user_credits and create CreditTransaction (purchase).
◦  Optional: customer portal endpoint.
•  Remove any credit-modifying public endpoints that bypass payment, or guard them behind admin auth.
•  Ensure idempotency in webhook handlers.

3) Production deployment configuration (blocker)
•  Current state:
•  Dev only compose file: docker-compose.dev.yml (LocalStack + API + workers).
•  Dockerfiles exist for API, Whisper/transcription, and generic workers.
•  There is no docker-compose.prod.yml, and no ECS/EKS manifests. Terraform file infrastructure/terraform/scaling.tf is a partial scaffold (cluster, queues, policy skeletons, S3/DDB), but it does not define ECS task definitions, ECS services, an ALB, or ECR repos.
•  What’s needed (pick one path to v0):
•  Minimal single-VM (fastest path):
◦  Add docker-compose.prod.yml to run API + workers without LocalStack (omit AWS_ENDPOINT_URL so the SDKs hit real AWS).
◦  Front the API with Nginx/Caddy + Let’s Encrypt or use a managed LB/Ingress on a VM provider. Configure TLS and set ALLOWED_ORIGINS for your domain(s).
◦  Provide systemd units or a restart policy for resilience.
•  AWS ECS Fargate (recommended path):
◦  Create ECR repositories and GitHub Actions to build/push API and worker images on main tags.
◦  Terraform: add aws_ecs_task_definition and aws_ecs_service for:
◦  API service behind an ALB with HTTPS listener, target group on port 8000, security groups, health check on /api/v1/health.
◦  Workers: download-worker, transcription (use whisper image), summarization, email.
◦  Add SSM Parameter Store/Secrets Manager for secrets; reference them from task definitions.
◦  Make S3/DDB/SES/SQS resources consistent with app env names. Your code defaults to users, processing_jobs, credit_transactions tables and explicit S3 bucket names; make sure Terraform outputs are wired to container envs.
◦  Add CloudWatch Logs to task definitions (you already create log groups in scaling.tf).

4) Email delivery (SES) productionization
•  Current state:
•  Email worker (media_summarizer/workers/notification/email_worker.py) uses SES utils. LocalStack dev setup verifies emails.
•  What’s needed:
•  Verify a real SES domain and FROM_EMAIL.
•  Warm up sending and handle SES sandbox if applicable.
•  Ensure bounce/complaint handling later (not required for v0).

5) Data model and infrastructure consistency
•  Current state:
•  App expects DDB tables: users, processing_jobs, credit_transactions (+ podcasts, episodes).
•  Dev LocalStack init script creates these exact tables and SQS queues.
•  Terraform scaling.tf defines many resources but appears incomplete/inconsistent; for instance, it references aws_dynamodb_table.users and a jobs table with different attribute names; ensure these match code expectations (USERS_TABLE, PROCESSING_JOBS_TABLE, CREDIT_TRANSACTIONS_TABLE) and required GSIs (email-index, user-index, status-index).
•  What’s needed:
•  Align Terraform to code: same table names and GSI keys (email-index, user-index, status-index).
•  Ensure queues match code: audio-download-queue, transcription-queue, summarization-queue, email-notification-queue; configure DLQs/redrive policies in Terraform (your LocalStack script 02-setup-dlq.sh does this in dev).
•  Use unique bucket names in prod (S3 global namespace). Parameterize via envs and set them from Terraform outputs.

6) API hardening and productization
•  Current state:
•  Episode submission (media_summarizer/api/endpoints/podcast_search.py) is unauthenticated and creates users by email if missing, then immediately deducts credits and enqueues a job.
•  Jobs endpoints require auth but current auth is a stub.
•  What’s needed:
•  Decide minimum viable gating for v0:
◦  Either require login before submission, or issue a short-lived signed token tied to the email used in submission and use it for job status reads.
•  Edge cases:
◦  Refund credits automatically when jobs fail (workers set job to failed; tie that to a credit refund call).
◦  Input validation: enforce HTTPS audio URLs and protect against SSRF (you already check http(s) scheme; consider allowlist or fetch via a sandboxed downloader).
•  Rate limiting: You have RATE_LIMIT_PER_MINUTE in envs but no implementation. Add a simple limiter (e.g., slowapi) at least for submission endpoints or put it at the edge (ALB/WAF/Cloudflare) for v0.

7) OpenAI integration details
•  Current state:
•  Summarization worker calls OpenAI’s chat/completions API directly via aiohttp with model "gpt-4".
•  What’s needed:
•  Confirm the model name (OpenAI now recommends model names like gpt-4o/gpt-4.1). Consider making the model name an env var (LLM_MODEL) and default to a current model. Keep your current code if you’ve validated it works with your account quota.

8) Observability and ops
•  Current state:
•  Logging is in place. Health endpoints exist. GH Actions run tests and integration tests.
•  What’s needed:
•  CI/CD: add a pipeline to build/push images (API, worker, whisper) to ECR on main release tags.
•  Alarms: basic CloudWatch alarms on API 5xx and queue age for SQS (high age -> stuck worker).
•  Optionally add Sentry (SENTRY_DSN exists in env example) for API exceptions.

9) Smaller consistency fixes
•  CORS env mismatch: use ALLOWED_ORIGINS or switch app to read CORS_ORIGINS consistently.
•  Secrets: SECRET_KEY in .env.* is not used by current auth; once JWT is implemented, use it.
•  API surface: expose /api/v1/health (already present). If you want a plain /health for LB checks, add a quick alias.

Minimal prioritized plan to ship v0

Must-have (before go-live)
1) Real auth:
•  Implement JWT login + token validation (password or email magic link).
•  Protect jobs, credits, and submission routes appropriately.
2) Real payments:
•  Implement Stripe Checkout + webhook to add credits. Remove or restrict any direct credit-adding endpoints.
3) Production deployment path:
•  Choose ECS Fargate or a single VM with docker-compose.prod.yml.
•  Provision S3, SQS, DynamoDB tables (names and GSIs matching code), SES verified domain, IAM roles/policies.
•  Store secrets in SSM/Secrets Manager; inject into task definitions.
4) CORS and TLS:
•  Set ALLOWED_ORIGINS to your domain(s). Terminate TLS at ALB or a reverse proxy.

Should-have (soon after)
5) Refund on failure:
•  Automatically refund credits when a job ends in FAILED.
6) CI/CD to ECR:
•  Build and push API/worker/whisper images on release; deploy via Terraform or GitHub Actions.
7) SQS DLQs in prod:
•  Redrive policies for all queues with alarms on DLQ depth and queue age.

Nice-to-have (later)
8) Rate limiting (API or edge), user email verification flow, SSO/OAuth, structured JSON logging, metrics, and customer portal for Stripe.

Concrete file-level pointers
•  Auth stub to replace: media_summarizer/api/dependencies/auth.py
•  Credit purchase without Stripe: media_summarizer/api/endpoints/credits.py
•  Episode submission (deducts credits unauthenticated): media_summarizer/api/endpoints/podcast_search.py
•  Workers (entrypoints OK):
•  Download: media_summarizer/workers/download_worker.py
•  Transcription (Whisper): media_summarizer/workers/transcription/worker.py (whisper.Dockerfile has ffmpeg + model preload)
•  Summarization: media_summarizer/workers/summarization/summarization_worker.py
•  Email: media_summarizer/workers/notification/email_worker.py
•  Dev infra: docker-compose.dev.yml and infrastructure/localstack/*.sh
•  Terraform scaffold (incomplete for compute): infrastructure/terraform/scaling.tf
