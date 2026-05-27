# Terraform — Media Summarizer

Provisions all AWS resources for the V1 stack: DynamoDB tables, S3 buckets,
SQS queues, ECS Fargate workers, Lambda functions, Secrets Manager, IAM,
CloudWatch dashboards/alarms.

## Where do secrets live?

Application code (`media_summarizer/core/config.py`) reads every secret via
`os.getenv(...)`. The config module never calls Secrets Manager directly.
Where the env var comes from depends on the runtime:

| Runtime | Source |
|---|---|
| Local dev (`uvicorn`, `docker-compose`) | `.env` at repo root, loaded automatically by `python-dotenv` (declared in `media_summarizer/__init__.py`) |
| Lambda | env vars wired in the Lambda definition — pulled from the consolidated runtime secret via `secrets` block (when supported) or a `data` source (see "Wiring a Lambda" below) |
| ECS Fargate worker | container `secrets` block referencing `aws_secretsmanager_secret.runtime.arn` — AWS injects each JSON key as an env var at boot |
| GitHub Actions (mobile builds, infra deploys) | repo secrets injected as env vars in the workflow |

The single source of truth in production is the `media-summarizer-runtime-<env>`
Secrets Manager entry created by `secrets.tf`.

## Bootstrapping a new environment

```bash
cd infrastructure/terraform
cp terraform.tfvars.example terraform.tfvars
# Edit terraform.tfvars: set environment (dev/staging/prod), VPC, secret_payload
terraform init
terraform plan
terraform apply
```

`secret_payload` is `sensitive = true` and the resource has
`lifecycle { ignore_changes = [secret_string] }` so once applied, operators can
rotate values directly in the AWS Console without Terraform reverting them.

To force-update from Terraform after a rotation, comment out the
`ignore_changes` line, run `apply`, then restore it.

## Wiring a new Lambda to the runtime secret

The Lambda's execution role needs the read policy:

```hcl
resource "aws_iam_role_policy_attachment" "my_lambda_runtime_secret" {
  role       = aws_iam_role.my_lambda.name
  policy_arn = aws_iam_policy.runtime_secret_read.arn
}
```

Then inject the secret values as env vars. Two options:

**Option A — at apply time (simpler, redeploy on rotation):**

```hcl
data "aws_secretsmanager_secret_version" "runtime" {
  secret_id = aws_secretsmanager_secret.runtime.id
}

resource "aws_lambda_function" "my_lambda" {
  # ...
  environment {
    variables = jsondecode(data.aws_secretsmanager_secret_version.runtime.secret_string)
  }
}
```

**Option B — at runtime (Lambda fetches on cold start):**

The Lambda code calls `boto3.client('secretsmanager').get_secret_value(...)`
itself and merges the result into `os.environ` before importing
`media_summarizer`. Use this only if cold-start latency is acceptable; Option A
is preferred for V1.

## Wiring an ECS task

Already done in `scaling.tf` for the existing per-secret entries. To add the
consolidated secret:

```hcl
container_definitions = jsonencode([
  {
    # ...
    secrets = [
      { name = "OPENAI_API_KEY",   valueFrom = "${aws_secretsmanager_secret.runtime.arn}:OPENAI_API_KEY::" },
      { name = "DEEPGRAM_API_KEY", valueFrom = "${aws_secretsmanager_secret.runtime.arn}:DEEPGRAM_API_KEY::" },
      # one entry per key the worker actually needs
    ]
  }
])
```

The `:KEY::` suffix tells ECS to pull a single field out of the JSON secret.

## Files

| File | Role |
|---|---|
| `secrets.tf` | Consolidated runtime secret + read policy + outputs |
| `terraform.tfvars.example` | Template for `terraform.tfvars` (gitignored) |
| `scaling.tf` | ECS Fargate workers, Lambda scaling controller, SQS queues, S3 buckets, per-secret entries (legacy) |
| `dynamodb_*.tf` | DynamoDB tables |
| `monitoring.tf`, `pipeline_*.tf` | CloudWatch dashboards, alarms |
| `archiving.tf` | Archive bucket + lifecycle |
| `localstack/` | Stripped-down stack used by `docker-compose.dev.yml` for offline dev |
