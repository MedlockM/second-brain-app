# ADR-001: Cloud Provider Selection - Stay with AWS

**Status:** Accepted
**Date:** 2026-04-29
**Decision makers:** Owner (validated benchmark task-73)
**Benchmark reference:** `docs/research/task-73-cloud-provider-analysis/README.md`

## Context

The project needed to formally validate its cloud provider choice before moving to production deployment. A comprehensive benchmark (task-73) evaluated 8 providers:

- AWS (current)
- Google Cloud Platform
- Railway
- Fly.io
- Render
- Supabase
- Cloudflare Workers
- Hetzner Cloud

The evaluation covered cost projections, local development experience, migration effort, vendor lock-in risk, and operational complexity for a solo-developer V1 launch targeting <100 initial users growing to 1000-2000 users over 6 months.

## Decision

**Stay with AWS.**

The owner validated this recommendation on 2026-04-29.

## Rationale

1. **Already implemented** - The entire infrastructure (DynamoDB, SQS, S3, ECS/Fargate, Lambda, EventBridge, CloudWatch, Secrets Manager, ECR) is battle-tested in the codebase with working Terraform configurations.

2. **Best local development experience** - LocalStack provides complete offline emulation of all AWS services used. No other provider offers an equivalent. This is critical for a solo developer iterating quickly.

3. **Cost-effective at launch** - AWS free tier covers the initial phase generously. Estimated $15-50/month after free tier exhaustion for low traffic.

4. **Production-ready infrastructure already exists** - Terraform modules for both local (LocalStack) and production are in place. Deployment scripts, scaling controllers, operational runbooks, and SLO definitions are all AWS-native.

5. **Clear migration path if needed later** - The project wraps AWS services in abstraction layers (`utils/database_async.py`, `utils/sqs.py`, `utils/s3.py`). S3 API is standard, Docker containers are portable, and DynamoDB-to-Postgres is the only costly migration (~2-4 weeks).

## Consequences

- Infrastructure code remains as-is (no migration needed).
- Deployment targets AWS ECS/Fargate for compute, DynamoDB for data, SQS for messaging, S3 for storage.
- Future cost optimization should focus on:
  - AWS Cost Explorer + budget alerts
  - Lambda for intermittent workers (vs always-on Fargate)
  - S3 Intelligent-Tiering for storage
  - Fargate Spot for non-critical workers
- If cost or complexity becomes problematic post-launch, Railway is the recommended migration target (simplest DX, predictable pricing).

## AWS Service Inventory (Production)

| Service | Usage |
|---------|-------|
| DynamoDB | 20+ tables (users, jobs, artifacts, auth, billing, organization) |
| SQS | 12+ queues with DLQs (ingestion, transcription, summarization, notifications) |
| S3 | 4 buckets (audio, transcriptions, summaries, flashcards) |
| ECS/Fargate | Ephemeral workers (8 task definitions: rss, x, youtube, tiktok, download, deepgram, whisper, summarization) |
| Lambda | Scaling controller, Spotify sync dispatcher/worker |
| EventBridge | Periodic scaling checks, Spotify sync schedule |
| CloudWatch | Logs (7-day retention), metrics, alarms, dashboard |
| Secrets Manager | API keys (OpenAI, Deepgram) |
| ECR | Container registry for worker images |
| SNS | Scaling alerts |
| SES | Email notifications |
| IAM | Least-privilege roles for tasks, Lambda, execution |

## Infrastructure Layout

```
infrastructure/
  docker/              # Dockerfiles for all services
  localstack/          # LocalStack init scripts
  observability/
    runbooks/          # Operational runbooks (pipeline-alerts.md)
    slo-definitions.yaml
  scaling/
    deploy.sh          # Production deployment script
    scaling_controller.py  # Lambda scaling controller
    README.md          # Scaling setup documentation
  terraform/
    localstack/main.tf # Dev environment (LocalStack)
    scaling.tf         # Production infrastructure (ECS, SQS, S3, DynamoDB, Lambda, etc.)
    monitoring.tf      # CloudWatch monitoring
    pipeline_alerts.tf # Pipeline alert definitions
    pipeline_dashboard.tf
    archiving.tf       # DynamoDB Streams archiving
    dynamodb_*.tf      # Additional DynamoDB table definitions
```

## Related Documents

- `infrastructure/scaling/README.md` - Deployment guide and troubleshooting
- `infrastructure/observability/runbooks/pipeline-alerts.md` - Operational runbook
- `infrastructure/observability/slo-definitions.yaml` - SLO definitions
- `.env.prod` - Production environment configuration
- `.env.example` - Configuration reference with all AWS settings documented
