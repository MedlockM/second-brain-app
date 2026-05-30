# Terraform -- Media Summarizer

Provisions all AWS resources for the V1 stack: DynamoDB tables, S3 buckets,
SQS queues, Lambda functions (API + workers), API Gateway HTTP API, ECR,
Secrets Manager, IAM, CloudWatch dashboards/alarms.

## Architecture (Lambda-only, no ECS)

All backend compute runs as AWS Lambda functions deployed as ARM64 container
images from a shared ECR repository. The FastAPI API is fronted by API Gateway
HTTP API. Workers are triggered by SQS event source mappings (one Lambda per
queue). No VPC is required.

## Where do secrets live?

Application code (`media_summarizer/core/config.py`) reads every secret via
`os.getenv(...)`. The config module never calls Secrets Manager directly.
Where the env var comes from depends on the runtime:

| Runtime | Source |
|---|---|
| Local dev (`uvicorn`, `docker-compose`) | `.env` at repo root, loaded automatically by `python-dotenv` (declared in `media_summarizer/__init__.py`) |
| Lambda (API + workers) | Fetched from Secrets Manager at cold start by the handler init code (`lambda_handler.py` / `lambda_handlers.py`) and injected into `os.environ` |
| GitHub Actions (mobile builds, infra deploys) | repo secrets injected as env vars in the workflow |

The single source of truth in production is the `media-summarizer-runtime-<env>`
Secrets Manager entry created by `secrets.tf`.

## Bootstrapping a new environment

```bash
cd infrastructure/terraform
cp terraform.tfvars.example terraform.tfvars
# Edit terraform.tfvars: set environment (dev/staging/prod), secret_payload
terraform init
terraform plan
terraform apply
```

`secret_payload` is `sensitive = true` and the resource has
`lifecycle { ignore_changes = [secret_string] }` so once applied, operators can
rotate values directly in the AWS Console without Terraform reverting them.

To force-update from Terraform after a rotation, comment out the
`ignore_changes` line, run `apply`, then restore it.

## Deploying code changes

After `terraform apply` creates the infrastructure, deploy code by building and
pushing the Lambda container image:

```bash
# Build for ARM64
docker buildx build --platform linux/arm64 \
  -f infrastructure/docker/lambda.Dockerfile \
  -t <ecr-url>:worker-latest \
  -t <ecr-url>:api-latest \
  --push .

# Update Lambda functions to use the new image
aws lambda update-function-code --function-name media-summarizer-api --image-uri <ecr-url>:api-latest
aws lambda update-function-code --function-name media-summarizer-worker-<name> --image-uri <ecr-url>:worker-latest
```

This is automated by `.github/workflows/deploy-lambda.yml` on push to main.

## Files

| File | Role |
|---|---|
| `main.tf` | Provider configuration, shared variables, data sources |
| `secrets.tf` | Consolidated runtime secret + read policy + outputs |
| `terraform.tfvars.example` | Template for `terraform.tfvars` (gitignored) |
| `sqs.tf` | SQS queues and dead-letter queues |
| `s3.tf` | S3 buckets for media pipeline |
| `ecr.tf` | ECR repository for Lambda container images |
| `iam_lambda.tf` | IAM roles and policies for Lambda functions |
| `lambda_workers.tf` | Worker Lambda functions + SQS event source mappings |
| `lambda_api.tf` | API Lambda + API Gateway HTTP API |
| `dynamodb_*.tf` | DynamoDB tables |
| `monitoring.tf` | CloudWatch alarms, metric filters, dashboard |
| `pipeline_alerts.tf` | Pipeline-specific alerting rules |
| `pipeline_dashboard.tf` | Pipeline observability dashboard + metric filters |
| `archiving.tf` | Archive bucket + lifecycle + archiver Lambda |
| `localstack/` | Stripped-down stack used by `docker-compose.dev.yml` for offline dev |
