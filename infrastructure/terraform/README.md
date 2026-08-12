# Terraform -- Media Summarizer

Provisions all AWS resources for the V1 stack: DynamoDB tables, S3 buckets,
SQS queues, Lambda functions (API + workers), API Gateway HTTP API, ECR,
Secrets Manager, IAM, CloudWatch dashboards/alarms.

## Layout: one root per environment over one shared module

Per the validated benchmark
(`docs/research/task-221-terraform-multi-env-isolation/README.md`, owner
decision: **option B**), each environment is a **separate root directory** with
its own **literal** backend key and its own **literal** `environment` value:

```
infrastructure/terraform/
  envs/dev/       key = "env/dev/terraform.tfstate"        environment = "dev"
  envs/staging/   key = "env/staging/terraform.tfstate"    environment = "staging"
  envs/prod/      key = "env/prod/terraform.tfstate"       environment = "prod"   # NEVER APPLIED YET
  shared/         key = "env/shared/terraform.tfstate"     account-scoped singletons (ECR)
  modules/platform/   every resource, parameterised by `environment`
```

Nothing is interpolated into a backend key and nothing is passed on the command
line to select an environment. **The directory you `cd` into is the
environment.** That is the property the whole design rests on: a plan run in
`envs/staging` can only ever propose changes to resources present in staging's
state, so it structurally cannot touch dev.

Every physical resource name carries a mandatory `-${var.environment}` suffix
(`local.suffix` in `modules/platform/locals.tf`). There is no unsuffixed name
left in the module.

> **Never** run Terraform from `infrastructure/terraform/` itself — it is not a
> root module. The historical single-root layout, where you copied
> `terraform.tfvars` and edited `environment` to switch target, is **gone**. It
> was unsafe by construction: one state file, one set of names, and a one-word
> edit between "I am changing dev" and "I am changing prod".

## Plan and apply

```bash
cd infrastructure/terraform/envs/dev        # the directory IS the environment
terraform init
terraform plan -out=tfplan

# Gate the plan before applying it. From the repo root:
scripts/tf_plan_guard.sh dev tfplan staging   # cross-check against staging names

terraform apply tfplan                       # apply the reviewed plan, not a fresh one
```

Applying the **saved plan file** rather than re-planning is deliberate: it
guarantees what the guard inspected is exactly what gets applied.

`scripts/tf_plan_guard.sh <env> <planfile> [other-env ...]` implements layers
2-4 of the proof suite from the benchmark §6: it refuses a plan that deletes a
table, bucket, secret or the ECR repository; it verifies every created name ends
in `-<env>`; and, given other environment names, it verifies the plan touches
none of them. Pass `--allow-replace` only when replacing genuinely stateless
resources, and read what it lists before accepting.

Checking for drift:

```bash
terraform plan -detailed-exitcode      # 0 = no changes, 2 = changes pending
```

Note that `plan -refresh-only -detailed-exitcode` returns `2` even on a freshly
applied environment with the aws 5.x provider — that is computed-attribute
normalisation, not real drift. The assertion that means something is
`plan -detailed-exitcode` = `0`.

## Where do secrets live?

Application code reads every secret via `os.getenv(...)`. The config module
never calls Secrets Manager directly. Where the env var comes from depends on
the runtime:

| Runtime | Source |
|---|---|
| Local dev (`uvicorn`, `docker-compose`) | `.env` at repo root, loaded automatically by `python-dotenv` (declared in `media_summarizer/__init__.py`) |
| Lambda (API + workers) | Fetched from Secrets Manager at cold start by the handler init code (`lambda_handler.py` / `lambda_handlers.py`) and injected into `os.environ` |
| GitHub Actions (mobile builds, infra deploys) | repo secrets injected as env vars in the workflow |

**AWS resource names are not secrets and do not come from this path.** Terraform
injects all of them into the Lambdas from
`modules/platform/runtime_env.tf`, and `media_summarizer/utils/required_env()`
raises if one is missing. There is deliberately no fallback: a Lambda with a
missing `USERS_TABLE` used to silently read and write the *dev* `users` table,
which with three environments in one account is a cross-environment corruption
bug. Loud failure is the intended behaviour.

### Populating a runtime secret (out-of-band, never via Terraform)

Terraform creates the secret **shell only** and never writes its value
(benchmark §7.3): `secret_string` is stored in **plaintext inside the state
file**, so letting Terraform manage it would mean three plaintext copies of
every third-party credential in the state bucket. `secrets.tf` carries
`lifecycle { ignore_changes = [secret_string] }`, so Terraform will never
propose to overwrite what you put there.

```bash
aws secretsmanager put-secret-value \
  --secret-id media-summarizer-runtime-<env> \
  --region eu-west-3 \
  --secret-string file://runtime-secrets.json

rm runtime-secrets.json      # do not leave it on disk
```

Then redeploy the consumers so a cold start picks up the new values.

Each environment **must** get its **own** third-party credentials — RevenueCat
sandbox vs live, a distinct `JWT_SECRET_KEY`, separate Apify / Deepgram /
OpenAI keys (at minimum for cost attribution) and a distinct
`ALGOLIA_INDEX_NAME`. Do **not** copy dev's payload into staging: it would
point staging at dev's Algolia index and bill both environments to the same
keys.

Renaming or deleting a secret is not free: Secrets Manager holds a deleted name
for a 7-30 day recovery window during which it cannot be reused.

## Cost switches: what an idle environment bills, and how to stop it

Three independent booleans, set in the environment's `main.tf` — not in a tfvars
file. They exist because an environment with **zero users** is not free:
creating staging took the whole account from **$0.233/day to $0.295/day
(+27%)**, on an account that billed $8.11 in July. Figures below are measured on
Cost Explorer, not estimated.

| Variable | What it provisions | Measured cost | dev | staging | prod |
|---|---|---|---|---|---|
| `enable_alarms` | 1 SNS topic + **43 alarms** | ~$3.30/mo | `false` | `false` | `true` |
| `enable_dashboard` | 1 CloudWatch dashboard | ~$3.00/mo | `true` | `false` | `true` |
| `enable_worker_polling` | 14 SQS event source mappings | ~$0.90/mo | `true` | `false` | `true` |

`enable_dashboard` is separate from `enable_alarms` on purpose: the dashboard
costs **more than the 43 alarms it visualises**, and it used to be ungated, so a
second environment silently doubled the account's CloudWatch bill the day it was
created. CloudWatch bills per dashboard past a 3-dashboard free tier.

`enable_worker_polling = false` keeps the mappings in the state but stops the
long-poll: 14 idle mappings otherwise issue ~74k SQS Tier-1 requests a day
against queues that never receive anything. The `job-archiver` mapping reads a
DynamoDB stream, not SQS, so it stays enabled and costs nothing.

The 43 alarms come from 7 alarm blocks, most fanned out per worker or per DLQ via
`for_each` — which is why the count is not the number of `resource` blocks. It is
the figure measured with `terraform state list`, not the estimate of 42 in the
benchmark. See `modules/platform/pipeline_alerts.tf`.

### Mothballing an environment (staging today)

**staging is mothballed as of 2026-08-12**: all three switches are `false`. Every
table, bucket, queue, Lambda and the runtime secret stay in place — the
environment is a validated prod rehearsal and rebuilding it costs far more than
the ~$7.60/month it was burning while empty. Only the metered extras are off.

Waking it up is Phase 9 step 1 of `docs/V1_LAUNCH_PLAN.md`: flip the three
booleans back to `true`, plan, gate, apply. Nothing else is needed.

Note that turning a switch off produces a plan full of `delete` actions, so
`tf_plan_guard.sh` will (correctly) refuse it until you re-run with
`--allow-replace`. Read the list first: it must contain **only** alarms, the
dashboard and the SNS topic. Layer 2 independently asserts that no table,
bucket, secret or ECR repository is deleted, and that assertion must stay `OK`.

## Feature flags injected into the runtime

`durable_media_enabled` (default `true`) drives `DURABLE_MEDIA_ENABLED` in the
Lambda environment. It gates the dual-write of the durable `user_media` library
table (task-240). The application reads it **at call time**, so an incident can be
stopped with `aws lambda update-function-configuration` without a redeploy; flip
the variable in `envs/<env>/main.tf` to make that rollback survive the next apply.
Reads still resolve through `processing_jobs` until task-220, which is why turning
the flag off is a complete rollback: the table is additive and orphan rows are
inert. See `infrastructure/observability/runbooks/durable-media.md`.

## Copying data between environments

`scripts/dynamo_copy_env.py` scans a table set and writes it into the
correspondingly suffixed tables of another environment. It was written for the
dev migration onto suffixed names and is the tool to reach for when seeding
staging from dev — with the same caveat as secrets: seed only data you are
willing to duplicate.

## Deploying code changes

After the infrastructure exists, deploy code by building and pushing the Lambda
container image:

```bash
# Build for ARM64
docker buildx build --platform linux/arm64 \
  -f infrastructure/docker/lambda.Dockerfile \
  -t <ecr-url>:worker-latest \
  -t <ecr-url>:api-latest \
  --push .

# Update Lambda functions to use the new image
aws lambda update-function-code --function-name media-summarizer-api-<env> --image-uri <ecr-url>:api-latest
aws lambda update-function-code --function-name media-summarizer-worker-<name>-<env> --image-uri <ecr-url>:worker-latest
```

This is automated by `.github/workflows/deploy-lambda.yml` on push to main.

## Files

| Path | Role |
|---|---|
| `envs/<env>/main.tf` | Backend key + provider + one `module "platform"` call with the literal environment |
| `envs/<env>/outputs.tf` | Environment outputs (API endpoint, secret name, ...) |
| `shared/ecr.tf` | The one ECR repository shared by all environments |
| `modules/platform/locals.tf` | `local.suffix = "-${var.environment}"` |
| `modules/platform/variables.tf` | `environment`, `aws_region`, `project_name`, `enable_alarms`, `enable_dashboard`, `enable_worker_polling`, `durable_media_enabled`, `ecr_repository_url` (`alert_email` is declared in `pipeline_dashboard.tf`) |
| `modules/platform/secrets.tf` | Runtime secret shell + read policy + outputs |
| `modules/platform/runtime_env.tf` | Single source of truth for the resource names injected into the Lambdas |
| `modules/platform/sqs.tf` | SQS queues and dead-letter queues |
| `modules/platform/s3.tf` | S3 buckets for the media pipeline |
| `modules/platform/iam_lambda.tf` | IAM roles and policies for the Lambdas |
| `modules/platform/lambda_workers.tf` | Worker Lambdas + SQS event source mappings + log groups |
| `modules/platform/lambda_api.tf` | API Lambda + API Gateway HTTP API + log group |
| `modules/platform/dynamodb_*.tf` | DynamoDB tables |
| `modules/platform/pipeline_alerts.tf` | Alerting rules + SNS topic |
| `modules/platform/pipeline_dashboard.tf` | Observability dashboard + metric filters |
| `modules/platform/archiving.tf` | Archive bucket + lifecycle + archiver Lambda |
| `scripts/tf_plan_guard.sh` | Refuses a plan that crosses environments or destroys stateful resources |
| `scripts/dynamo_copy_env.py` | Copies table contents between environment suffixes |
