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
  envs/dev/       key = "env/dev/terraform.tfstate"      environment = "dev"    account 125313707865
  envs/prod/      key = "env/prod/terraform.tfstate"     environment = "prod"   account 866874944541
  envs/staging/   key = "env/staging/terraform.tfstate"  environment = "staging"  NOT DEPLOYED (see below)
  shared/         key = "env/shared/terraform.tfstate"   the ECR registry, in 125313707865
  modules/platform/   every resource, parameterised by `environment`
```

Nothing is interpolated into a backend key and nothing is passed on the command
line to select an environment. **The directory you `cd` into is the
environment.** That is the property the whole design rests on: a plan run in
`envs/prod` can only ever propose changes to resources present in prod's state,
so it structurally cannot touch dev.

Every physical resource name carries a mandatory `-${var.environment}` suffix
(`local.suffix` in `modules/platform/locals.tf`). There is no unsuffixed name
left in the module.

Since **task-248**, dev and prod are additionally in **two different AWS
accounts** (see "Two accounts, one set of keys"). The suffix discipline is kept
anyway: it is what keeps the two states readable side by side, it is what
`tf_plan_guard.sh` layer 3 asserts, and it is what would still protect a future
third environment sharing an account with an existing one.

> **Never** run Terraform from `infrastructure/terraform/` itself — it is not a
> root module. The historical single-root layout, where you copied
> `terraform.tfvars` and edited `environment` to switch target, is **gone**. It
> was unsafe by construction: one state file, one set of names, and a one-word
> edit between "I am changing dev" and "I am changing prod".

### `envs/staging/` exists but staging does not

staging was torn down by task-248 (145 resources destroyed, runtime secret
force-deleted) and **promoted into prod**: the environment token is part of every
physical name and is ForceNew, so there is no such thing as renaming an
environment — promoting one is `destroy` then `apply` elsewhere. It was safe
precisely because staging held nothing: 0 rows across 24 tables, 0 objects across
11 buckets, 0 messages across 26 queues, 0 keys in the secret, all verified with
`scan --select COUNT` / `list-object-versions` before the destroy.

The **directory stays**, unapplied, on purpose. It is 40 lines whose value is
being a proven, disposable rehearsal target: `terraform apply` there builds a
full third copy of the platform in the dev account for an afternoon of testing,
and the teardown path has now actually been walked end to end. Deleting the
directory would save nothing and lose that.

If you do apply it, remember it lands **in the dev account** (its backend and
provider are dev's), which is the one case where `tf_plan_guard.sh` layer 4 still
does real work — see below.

## Two accounts, one set of keys

Since task-248 the two live environments are in two AWS accounts of one AWS
organization (`o-7sf5u7j5hd`):

| Account | Id | Holds |
|---|---|---|
| management / dev | `125313707865` | `envs/dev`, `shared/` (the ECR registry), the whole billing history |
| `media-summarizer-prod` | `866874944541` | `envs/prod` only |

This is the only isolation AWS actually enforces. Inside one account, "dev
cannot touch prod" rests on discipline — a name suffix, a directory, a review.
Across accounts it rests on IAM: a dev credential cannot even *name* a prod
resource, a `terraform destroy` run with the wrong profile fails on an
authorization error instead of deleting the wrong thing, and the bill splits per
account at no cost. Tag-based "Resource Groups" would have given a view, not a
boundary.

**There is no second access key.** The prod account is driven by assuming into it
from the dev keys, through the `OrganizationAccountAccessRole` that AWS
Organizations creates in every member account. The `[profile prod]` block that
does it is tracked, so a new workstation copies it rather than retyping it:

```bash
install -m 600 -D infrastructure/aws/config.example ~/.aws/config   # from the repo root
```

That file holds no credential — only this account id and role name, which
`envs/prod/main.tf` and `gha_oidc.tf` already state in plain text. Its sibling
`~/.aws/credentials`, which does hold the key, is untracked and untrackable; see
`docs/DEVBOX_SETUP.md` §4.

Then every prod command is the normal command with one prefix:

```bash
AWS_PROFILE=prod aws sts get-caller-identity          # must print 866874944541
AWS_PROFILE=prod terraform -chdir=envs/prod plan
```

Two independent safety nets make a mistyped profile a hard failure rather than a
silent one:

- `envs/prod/main.tf` sets `allowed_account_ids = ["866874944541"]`, so a plan
  run with dev's credentials aborts before touching anything. Without it,
  forgetting `AWS_PROFILE=prod` would build a **second copy of prod inside the
  dev account** while writing it to prod's state file — an error that is
  invisible in the state and expensive to unpick.
- prod's backend bucket lives in prod's account, so the dev profile cannot even
  read prod's state, let alone lock it.

The state backend of each account is bootstrapped by
`scripts/bootstrap_tf_backend.sh` (idempotent; versioned + encrypted bucket,
public access blocked, TLS-only bucket policy, `media-summarizer-tfstate-lock`
table). Run it once per new account:

```bash
AWS_PROFILE=prod scripts/bootstrap_tf_backend.sh     # prints the backend block to paste
```

The lock table is **not** shared between the accounts. `media-summarizer-tfstate-lock`
in the dev account serves `envs/dev`, `envs/staging` and `shared/`; prod has its
own table of the same name in its own account. Sharing one would have meant
granting cross-account write access to the single resource whose entire job is to
be trustworthy.

`AWS_REGION` deserves a warning of its own: the shell used for this project has
`AWS_REGION=us-east-1` exported, while every resource lives in `eu-west-3`. A
`describe-table` without an explicit region silently reports "not found". Pass
`AWS_REGION=eu-west-3` (or `--region`) on every ad-hoc AWS CLI call.

## Plan and apply

```bash
cd infrastructure/terraform/envs/dev        # the directory IS the environment
terraform init
terraform plan -out=tfplan

# Gate the plan before applying it. From the repo root:
scripts/tf_plan_guard.sh dev tfplan

terraform apply tfplan                       # apply the reviewed plan, not a fresh one
```

For prod, the same three commands with `AWS_PROFILE=prod` in front of each.

Applying the **saved plan file** rather than re-planning is deliberate: it
guarantees what the guard inspected is exactly what gets applied.

`scripts/tf_plan_guard.sh <env> <planfile> [other-env ...]` implements layers
2-4 of the proof suite from the benchmark §6: it refuses a plan that deletes a
table, bucket, secret or the ECR repository; it verifies every created name ends
in `-<env>`; and, given other environment names, it verifies the plan touches
none of them. Pass `--allow-replace` only when replacing genuinely stateless
resources, and read what it lists before accepting. The plan file path is
resolved **relative to the environment directory**, so pass the bare `tfplan`,
not a path.

### Layer 4 no longer does the same job between dev and prod

Layer 4 loads the *other* environment's state and asserts the plan names none of
its resources. Between two environments in one account that was the real
protection. Across the dev/prod account boundary it is now **both impossible and
redundant**:

- **Impossible.** It runs `terraform show` against the other environment's
  backend using the *ambient* credentials. With `AWS_PROFILE=prod` it hits dev's
  state bucket and gets exactly what account isolation is supposed to produce:

  ```
  == Layer 4: no name collision with the live environments ==========
  Error: Failed to load state: Unable to access object "env/dev/terraform.tfstate"
  in S3 bucket "media-summarizer-tfstate-125313707865": ... StatusCode: 403 ...
  ```

  Reading both states in one command would require a principal with rights in
  both accounts, i.e. re-creating by hand the shared blast radius the split just
  removed. Not worth it for a redundant check.

- **Redundant.** DynamoDB tables, SQS queues, Lambda functions, log groups and
  IAM roles are all scoped to *account* + region. A plan executed with prod's
  credentials cannot create, modify or delete an object in the dev account even
  if the names were byte-identical. S3 bucket names are global, but the module
  suffixes them with the account id as well as the environment.

So: **run layers 2-3 for prod (`scripts/tf_plan_guard.sh prod tfplan`, no third
argument) and do not pass `dev`.** Layer 4 keeps its full value in the one place
it still applies — two environments sharing the dev account, i.e. the day
`envs/staging` gets applied, where `scripts/tf_plan_guard.sh staging tfplan dev`
is exactly the check that matters.

If you ever want the cross-account comparison anyway, it has to be done as two
commands, one per profile, comparing the extracted name lists offline. Done once
for the prod promotion, the only intersection between prod's 154 planned names
and dev's 170 live names was `$default` — the fixed API Gateway v2 stage literal,
which is scoped to an API id, not a global name.

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
sandbox vs live, a distinct `JWT_SECRET_KEY`, and separate Apify / Deepgram /
OpenAI keys (at minimum for cost attribution). Do **not** copy dev's payload into
prod: it would bill both environments to the same keys and hand prod a JWT signing
key that dev also holds.

Algolia is not among the values to differentiate: the index name is not
configurable at all. The code derives it as `media_items_{ENVIRONMENT}`
(`utils/algolia_client.py`), so the environments are separated structurally — no
secret value can point prod at dev's index.
`media-summarizer-runtime-prod` currently exists as an **empty shell**; filling
its 37 keys is owner-only work (task-252).

Renaming or deleting a secret is not free: Secrets Manager holds a deleted name
for a 7-30 day recovery window during which it cannot be reused. The module
deliberately sets no `recovery_window_in_days`, so a `terraform destroy`
*schedules* the deletion rather than performing it, and the name stays blocked
for 30 days. To free the name immediately — required when destroying an
environment you intend to rebuild under the same name:

```bash
aws secretsmanager restore-secret --secret-id media-summarizer-runtime-<env> --region eu-west-3
aws secretsmanager delete-secret  --secret-id media-summarizer-runtime-<env> --region eu-west-3 \
  --force-delete-without-recovery
```

`restore-secret` first is not optional: `--force-delete-without-recovery` is
rejected on a secret that is already scheduled for deletion.

## Cost switches: what an idle environment bills, and how to stop it

Three independent booleans, set in the environment's `main.tf` — not in a tfvars
file. They exist because an environment with **zero users** is not free:
creating staging took the whole account from **$0.233/day to $0.295/day
(+27%)**, on an account that billed $8.11 in July. Figures below are measured on
Cost Explorer, not estimated.

| Variable | What it provisions | Measured cost | dev | prod | staging (if applied) |
|---|---|---|---|---|---|
| `enable_alarms` | 1 SNS topic + **43 alarms** | ~$3.30/mo | `false` | `false` (mothballed) | `false` |
| `enable_dashboard` | 1 CloudWatch dashboard | ~$3.00/mo | `true` | `false` (mothballed) | `false` |
| `enable_worker_polling` | 14 SQS event source mappings | ~$0.90/mo | `true` | `false` (mothballed) | `false` |

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

### Mothballing an environment (prod today)

**prod is mothballed since its creation on 2026-08-13**: all three switches are
`false`. Every table, bucket, queue, Lambda and the runtime secret shell exist —
only the metered CloudWatch extras are off, saving ~$7.20/month.

This is a deliberate, *temporary* exception to the rule that production is
watched. It is defensible only because prod currently has zero users, zero rows
and zero objects, and the launch it is waiting for is blocked on App Store
products and a domain that does not resolve yet. **Waking prod up is a
prerequisite of taking the first paying user, not a follow-up to it** — the day a
real account exists in prod, an unwatched prod is a fault.

Waking it up is flip the three booleans to `true`, plan, gate, apply. Nothing
else: no data move, no resource recreation, and the SQS event source mappings
stay in the state the whole time.

Note that turning a switch off produces a plan full of `delete` actions, so
`tf_plan_guard.sh` will (correctly) refuse it until you re-run with
`--allow-replace`. Read the list first: it must contain **only** alarms, the
dashboard and the SNS topic. Layer 2 independently asserts that no table,
bucket, secret or ECR repository is deleted, and that assertion must stay `OK`.

## Copying data between environments

`scripts/dynamo_copy_env.py` scans a table set and writes it into the
correspondingly suffixed tables of another environment. It was written for the
dev migration onto suffixed names, and it assumes **one** set of credentials
reaching both table sets — which is true between two environments of the same
account, and no longer true between dev and prod. Copying dev data into prod is
not a supported operation anyway: prod must start empty, with its own
credentials and its own Algolia index.

## Deploying code changes

One registry serves every environment, and it stays in the **dev** account:
`125313707865.dkr.ecr.eu-west-3.amazonaws.com/media-summarizer-lambda`. Tags
carry no environment token and promotion happens **by digest**, so the image
running in prod is bit-identical to the one validated in dev. Moving the registry
into the prod account would have meant re-pushing every image, and a re-push
mints new digests, which destroys that guarantee. The accepted trade: prod has a
runtime dependency on a dev-account resource — deleting the repository breaks
every prod Lambda cold start. See the header of `shared/ecr.tf`.

Cross-account pulls need **both** sides granted, which is why
`shared/ecr.tf` now manages the repository policy (Lambda used to auto-write it,
locked to this account's functions only):

- repository side: `LambdaECRImageCrossAccountRetrievalPolicy` for the Lambda
  service principal with an `aws:sourceArn` in each `consumer_account_ids`, plus
  `ConsumerAccountImagePull` for the consumer account root — the IAM principal
  that *creates* the function must be able to read the image, or `CreateFunction`
  fails before the service principal is ever consulted;
- consumer side: `ecr:BatchGetImage` / `GetDownloadUrlForLayer` in prod's own IAM
  (`envs/prod/gha_oidc.tf`). A repository policy alone grants nothing to a
  principal whose own account does not allow the call.

Adding a fourth account later is one line: append its id to
`consumer_account_ids` in `shared/` and apply.

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

This is automated by `.github/workflows/deploy-lambda.yml`: push to main deploys
**dev**, and `workflow_dispatch` with `environment: prod` deploys prod.

### One deploy role per account

| Environment | Role | Assumable by | Declared in |
|---|---|---|---|
| dev | `media-summarizer-gha-deploy` in `125313707865` | jobs with no GitHub environment (push to main) | `envs/dev/gha_oidc.tf` |
| prod | `media-summarizer-gha-deploy-prod` in `866874944541` | only jobs declaring GitHub environment `production` | `envs/prod/gha_oidc.tf` |

Both roles are Terraform-managed since task-256. The dev one was created by hand
in June 2026 and drifted outside every state until then, which is exactly how it
came to be missing the `tag:GetResources` grant that `deploy-lambda.yml` needs to
discover its targets by `Environment` tag: prod got the permission from a code
change, dev had no code to change and `deploy-workers` failed for three days.
Both were adopted with `terraform import`, never recreated — the role ARN is the
`AWS_DEPLOY_ROLE_ARN` secret and its trust relationship is what every deploy
depends on, so a replacement would break CI for the duration of the change. The
dev file lists the three permission divergences from prod (unsuffixed name,
branch-pinned OIDC subject, ECR push) and why each one is intentional.

Neither role can reach the other environment, for two independent reasons: every
ARN in a role's policy belongs to its own account, and the prod role's trust
policy pins the OIDC `sub` claim with `StringEquals` to
`repo:<owner>/<repo>:environment:production`. GitHub only mints that subject for
a job that declares `environment: production`, and that GitHub environment
carries the owner's protection rules. Having the ARN is not enough.

The prod role's ARN goes in the `AWS_DEPLOY_ROLE_ARN` **environment** secret of
the GitHub `production` environment (not a repository secret — a repository
secret would be readable by every job, including the dev one). It is `terraform
output gha_deploy_role_arn` in `envs/prod`. The prod role deliberately has **no**
ECR push permission: images are built once in dev and promoted, so a prod job
must not be able to mint an artifact that never went through dev.

## Files

| Path | Role |
|---|---|
| `envs/<env>/main.tf` | Backend key + provider + one `module "platform"` call with the literal environment |
| `envs/<env>/outputs.tf` | Environment outputs (API endpoint, secret name, ...) |
| `envs/dev/gha_oidc.tf` | GitHub OIDC provider + push-to-main deploy role in the dev/management account (imported, not created) |
| `envs/prod/gha_oidc.tf` | GitHub OIDC provider + prod-only deploy role in the prod account |
| `shared/ecr.tf` | The one ECR repository shared by all environments, and its cross-account pull policy |
| `modules/platform/locals.tf` | `local.suffix = "-${var.environment}"` |
| `modules/platform/variables.tf` | `environment`, `aws_region`, `project_name`, `enable_alarms`, `enable_dashboard`, `enable_worker_polling`, `ecr_repository_url` (`alert_email` is declared in `pipeline_dashboard.tf`) |
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
| `scripts/bootstrap_tf_backend.sh` | Creates a new account's state bucket + lock table (chicken-and-egg, so not Terraform) |
| `scripts/dynamo_copy_env.py` | Copies table contents between environment suffixes (same account only) |
