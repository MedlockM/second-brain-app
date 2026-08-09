---
owner_decision: ok
---

# Benchmark : Terraform multi-environment isolation strategies for dev, staging and prod

> Task: `task-221` — research only. **No file under `infrastructure/terraform/` is modified by this task.**
> Evidence base: repository code at `main` (`d1cc7f2`), `infrastructure/terraform/*.tf`, `.github/workflows/deploy-lambda.yml`, and a **read-only live inspection of AWS account `125313707865` in `eu-west-3` performed on 2026-08-09** (`sts`, `s3api`, `dynamodb describe-table` / `describe-continuous-backups`, `sqs get-queue-attributes`, `lambda list-functions`, `ecr describe-images`, `apigatewayv2 get-apis`, `cloudwatch describe-alarms`, plus a streamed read of the remote state object).

## Owner Validation

**Decision**: option B
**Validated at**: 2026-08-09

---

## Recommendation

**Adopt Option B — three per-environment root directories (`infrastructure/terraform/envs/{dev,staging,prod}`) over one shared module (`infrastructure/terraform/modules/platform`), each root declaring a *literal* backend key and a *literal* `environment` value — combined with a mandatory `-${environment}` suffix on 100 % of physical resource names, and a migration of dev that never lets Terraform replace a DynamoDB table.**

The single argument that decides this benchmark:

> **The expensive and risky part of this task is renaming ~86 physical AWS resources. Every one of the four candidate options requires exactly that same rename.** Workspaces do not avoid it (`terraform.workspace` still has to be interpolated into all 86 names). Separate state keys do not avoid it. Terragrunt does not avoid it. So the choice must be made on the *cheap* part — state layout, ergonomics, and the ability to *prove* that staging cannot touch dev — and on that axis per-environment directories win outright.

Why the other options lose:

| Option | Verdict | One-line reason |
|---|---|---|
| **A. CLI workspaces** | **Rejected** | HashiCorp's own documentation states workspaces "are not a suitable isolation mechanism" for separate deployment stages; the active workspace is invisible in the code and is a hidden global that a tired operator gets wrong at 23:00. It saves zero rename work. |
| **B. Per-env dirs + shared module** | **Recommended** | The environment is a literal in the filesystem path, in the backend `key` and in the module input. There is no flag, no CLI state and no env var to forget. `terraform -chdir=envs/staging apply` is *structurally incapable* of writing dev's state. |
| **C. One root + `-backend-config` per env** | **Rejected as primary** | Cheapest to build (no module refactor), but reintroduces the exact hazard this task exists to remove: a forgotten `-reconfigure` / `-backend-config` silently points staging code at the dev state. The backend cannot be interpolated, so nothing in the configuration can catch the mismatch. |
| **D. Terragrunt** | **Rejected (for now)** | Terragrunt's value is DRY backends across *many* modules; this repo has **one** module and **three** environments. It adds a binary, a DSL and a CI dependency to save ~20 lines of duplicated backend blocks. Revisit only if the number of independently-applied stacks exceeds ~4. |

Three additional decisions that are part of the recommendation and are **not optional**:

1. **The ECR repository stays a single, shared, account-scoped resource** — moved out of the per-env module into a small `infrastructure/terraform/shared/` root. Images are environment-agnostic; promotion is dev then staging then prod of the *same content digest*. Per-environment repositories would force rebuilds and destroy digest equality, which is the whole point of a release pipeline.
2. **The application's hardcoded resource-name fallbacks must be removed before staging exists.** `media_summarizer/core/config.py:23`, `media_summarizer/utils/database_async.py:37-47`, `media_summarizer/utils/sqs.py:55` and ~20 other modules resolve tables and queues as `os.environ.get("USERS_TABLE", "users")`. A staging Lambda missing one injected variable will silently resolve **dev's** table and **dev's** queue URL. Combined with finding §1.5 (the Lambda IAM policy grants DynamoDB access on `table/*`), this is a live cross-environment data-corruption path that state isolation alone does **not** close.
3. **Dev is renamed, not aliased and not recreated.** The blockers usually cited against renaming dev do not apply here (§5): the S3 buckets are already environment-suffixed so **no blob moves**, the API Gateway keeps its ID and URL because `aws_apigatewayv2_api.name` is not `ForceNew`, all 26 SQS queues are empty, and the entire dev dataset is **427 items / ~180 KB across 21 DynamoDB tables** — a 2-minute scripted copy.

---

## Table of contents

1. [The blocker, with evidence](#1-the-blocker-with-evidence) — AC #1
2. [What actually happens if you apply staging today](#2-what-actually-happens-if-you-apply-staging-today) — AC #1
3. [The four options, compared](#3-the-four-options-compared) — AC #2, AC #3
4. [The naming convention](#4-the-naming-convention)
5. [Migrating the existing dev environment](#5-migrating-the-existing-dev-environment) — AC #4
6. [Proving a staging plan cannot touch dev](#6-proving-a-staging-plan-cannot-touch-dev) — AC #5
7. [GitHub Actions and ECR requirements](#7-github-actions-and-ecr-requirements) — AC #6
8. [Cost](#8-cost)
9. [Sequenced execution plan](#9-sequenced-execution-plan)
10. [Risks, rollback and what this benchmark does not decide](#10-risks-rollback-and-what-this-benchmark-does-not-decide)
11. [Sources](#11-sources)

---

## 1. The blocker, with evidence

### 1.1 One state, one key, one lineage

`infrastructure/terraform/main.tf:17-24`:

```hcl
backend "s3" {
  bucket         = "media-summarizer-tfstate-125313707865"
  key            = "infrastructure/terraform.tfstate"
  region         = "eu-west-3"
  encrypt        = true
  dynamodb_table = "media-summarizer-tfstate-lock"
}
```

Live check of the state object (streamed, never written to disk):

| Property | Value |
|---|---|
| S3 key | `infrastructure/terraform.tfstate` (**the only state object in the bucket**) |
| Size / last write | 450 395 bytes, `2026-08-06T00:46:49Z` |
| `terraform_version` | `1.9.8` |
| `serial` | 19 |
| `lineage` | `02a91c92-8370-9b54-2f13-c02eaa06a888` |
| Managed resource blocks | **103** |
| Managed resource **instances** | **145** |
| Root outputs | 40 |

Mitigating facts worth recording, because they are the rollback net for everything in §5:

- The state bucket **has versioning enabled** (`Status: Enabled`) — 10+ historical versions of the state object exist, back to 2026-06-15. Any state surgery is reversible by restoring an object version.
- The bucket is SSE-AES256 encrypted with all four public-access blocks on.
- The lock table `media-summarizer-tfstate-lock` exists. Note that the S3 backend's `dynamodb_table` locking is now **deprecated** in favour of `use_lockfile`; `use_lockfile` requires Terraform >= 1.10 and the installed CLI is 1.9.8, so this is a follow-up, not a blocker.

`terraform.tfvars.example` sets `environment = "dev"`, and the only Secrets Manager entry in the account is `media-summarizer-runtime-dev` — confirming that this single state *is* the dev environment.

### 1.2 Inventory of the names that would collide

AWS scopes DynamoDB table names, SQS queue names, Lambda function names, CloudWatch log-group / alarm / dashboard names and Secrets Manager names to **account + region**; IAM role and policy names are scoped to the **account** globally. Every name below is therefore a hard collision the moment a second environment is applied in account `125313707865` / `eu-west-3`.

| Family | Instances in state | Env-discriminated today? | Collides |
|---|---:|---|---:|
| `aws_sqs_queue` | 26 | NO — `podcastindex-resolution-queue`, `*-dlq`, ... | **26** |
| `aws_dynamodb_table` | 21 | NO — `users`, `processing_jobs`, `auth_tokens`, ... | **21** |
| `aws_lambda_function` | 15 | NO — `media-summarizer-api`, `media-summarizer-worker-*`, `media-summarizer-job-archiver` | **15** |
| `aws_cloudwatch_log_group` | 15 | NO — `/aws/lambda/media-summarizer-*` | **15** |
| `aws_iam_role` | 3 | NO — `media-summarizer-lambda-{worker,api,archiver}` | **3** |
| `aws_iam_policy` | 5 | PARTIAL — 2 of 5 suffixed (`-runtime-secret-read-dev`, `-bug-reports-s3-dev`) | **3** |
| `aws_ecr_repository` | 1 | NO — `media-summarizer-lambda` | **1** (deliberately shared — see §7) |
| `aws_cloudwatch_dashboard` | 1 | NO — `media-summarizer-pipeline-observability` | **1** |
| `aws_cloudwatch_event_rule` | 1 | NO — `media-summarizer-api-warmup` | **1** |
| `aws_cloudwatch_log_metric_filter` | 13 | PARTIAL — unique per log group only | 13 (transitive) |
| `aws_cloudwatch_metric_alarm` | 0 today (`enable_alarms = false`) | NO — `media-summarizer-api-5xx-rate-breach`, ... | **42 when enabled** |
| `aws_apigatewayv2_api` | 1 | NO — name `media-summarizer-api` | soft — see §1.4 |
| `aws_s3_bucket` | 11 | YES — `*-125313707865-dev` | 0 |
| `aws_secretsmanager_secret` (+ version) | 2 | YES — `media-summarizer-runtime-dev` | 0 |
| `aws_sns_topic` | 0 today | YES — `*-pipeline-alerts-dev` | 0 |
| ARN/ID-identified (event source mappings, permissions, integration, route, stage, bucket sub-resources) | 22 | n/a | 0 |

**86 hard name collisions today, 128 once `enable_alarms = true`.** Only S3, Secrets Manager and SNS are already environment-safe — i.e. **11 % of the named surface**.

Live confirmation (2026-08-09) that these are real deployed objects and not just HCL: 21 application DynamoDB tables (`users`, `processing_jobs`, ... plus the out-of-band `media-summarizer-tfstate-lock`), 26 SQS queues, 15 Lambda functions and 15 log groups, all carrying the unsuffixed names above.

### 1.3 The application code repeats the same mistake, in a worse way

Terraform injects only **6 of 21** table names and **0 of 13** queue names into the Lambdas (`lambda_api.tf:104-134`, `lambda_workers.tf:126-150`: `MEDIA_ARTIFACTS_TABLE`, `ARTIFACT_IDEMPOTENCE_TABLE`, `TRANSLATION_IDEMPOTENCE_TABLE`, `MEDIA_IDEMPOTENCE_TABLE`, `USER_MEDIA_SUBMISSIONS_TABLE`, `MEDIA_WATCHERS_TABLE`, plus the 10 buckets).

Everything else is resolved in Python with a **hardcoded fallback to the unsuffixed dev name**:

```python
# media_summarizer/utils/database_async.py:37-47
USERS_TABLE           = os.environ.get("USERS_TABLE", "users")
PROCESSING_JOBS_TABLE = os.environ.get("PROCESSING_JOBS_TABLE", "processing_jobs")
AUTH_TOKENS_TABLE     = os.environ.get("AUTH_TOKENS_TABLE", "auth_tokens")

# media_summarizer/api/endpoints/media.py:78
DEEPGRAM_TRANSCRIPTION_QUEUE = os.environ.get("DEEPGRAM_TRANSCRIPTION_QUEUE", "deepgram-transcription-queue")
```

and queues are resolved **by name at runtime**:

```python
# media_summarizer/utils/sqs.py:55
response = sqs_client.get_queue_url(QueueName=queue_name)
```

Consequence: a staging Lambda missing a single injected variable does not crash — it happily reads and writes **dev's** table and pushes messages into **dev's** queue, where dev's workers consume them. This is silent, and no amount of Terraform state isolation prevents it.

### 1.4 The deploy workflow is environment-blind

`.github/workflows/deploy-lambda.yml` contains three environment-unsafe lookups:

```yaml
# hardcoded: hits whichever environment owns that exact name
--function-name media-summarizer-api

# prefix wildcard: with 3 environments this returns all 39-45 worker functions
--query "Functions[?starts_with(FunctionName, 'media-summarizer-worker-')].FunctionName"

# API Gateway names are NOT unique; the `| [0]` selector is non-deterministic
--query "Items[?Name=='media-summarizer-api'].ApiEndpoint | [0]"
```

Left as-is, the first `main` push after staging exists would push the same image to **every** environment's workers, including production, and then health-check a randomly chosen API. Fixing this is a hard prerequisite, not a nice-to-have (§7).

### 1.5 IAM grants no isolation either

`iam_lambda.tf:122` and `:275` (worker role and API role):

```hcl
Resource = "arn:aws:dynamodb:${var.aws_region}:${data.aws_caller_identity.current.account_id}:table/*"
```

Both Lambda roles hold `GetItem` / `PutItem` / `UpdateItem` / `DeleteItem` / `Query` / `Scan` / `BatchGetItem` / `BatchWriteItem` on **every table in the account**. SQS (`iam_lambda.tf:56-70`) and S3 (`:79-109`) *are* correctly ARN-scoped, and Secrets Manager is scoped to the environment's own secret — DynamoDB is the outlier. With three environments in one account this is the difference between "a bug corrupts staging" and "a bug corrupts production".

### 1.6 No safety net on the data

`describe-table` + `describe-continuous-backups` on all 21 tables, 2026-08-09:

```
artifact_idempotence     31 items    20 503 B   PITR DISABLED
auth_tokens              69 items    19 263 B   PITR DISABLED
bug_reports               1 item         210 B  PITR DISABLED
feed_forecasts            0                0 B  PITR DISABLED
follows                   0                0 B  PITR DISABLED
media_artifacts         158 items    92 438 B   PITR DISABLED
media_idempotence        18 items     3 978 B   PITR DISABLED
media_watchers            0                0 B  PITR DISABLED
pricing_config            8 items     3 621 B   PITR DISABLED
processing_jobs          13 items    14 105 B   PITR DISABLED
revenucat_events          0                0 B  PITR DISABLED
subscriptions             1 item         462 B  PITR DISABLED
translation_idempotence  11 items     2 963 B   PITR DISABLED
user_digest_settings      0                0 B  PITR DISABLED
user_digests              7 items     3 056 B   PITR DISABLED
user_folders              7 items     1 350 B   PITR DISABLED
user_media_submissions   18 items     4 167 B   PITR DISABLED
user_tags                 1 item         190 B  PITR DISABLED
user_usage_daily          3 items       291 B   PITR DISABLED
user_usage_monthly       76 items    11 075 B   PITR DISABLED
users                     5 items     1 552 B   PITR DISABLED
                       ---------------------------------------
TOTAL                   427 items   ~183 KB
```

No table has `point_in_time_recovery`, no table has `deletion_protection_enabled`, and no resource in the whole configuration carries `lifecycle { prevent_destroy = true }` (verified by grep over all 18 `.tf` files). **Today, a single mistyped `terraform destroy` deletes the entire dev dataset with no restore path.** This is independently corroborated by the accepted `task-218` benchmark, which found PITR disabled on `processing_jobs` and `user_folders` and concluded that already-lost rows are unrecoverable.

The upside of the same table: **427 items / 183 KB is a trivially migratable dataset** (§5).

### 1.7 What is *not* at risk

- **All 11 S3 buckets are already named `${project}-${purpose}-${account_id}-${env}`.** Live: `media-summarizer-transcripts-125313707865-dev` (169 objects), `*-documents-*-dev` (16), `*-summaries-*-dev` (6), `*-audio-*-dev` (4), `*-archives-*-dev` (0). Adopting the convention changes nothing for them: **no blob is copied or moved by this migration.**
- **All 26 SQS queues are empty** (`ApproximateNumberOfMessages` = 0 and `ApproximateNumberOfMessagesNotVisible` = 0 on every queue, 2026-08-09). Recreating them loses nothing, provided depth is re-checked immediately before the apply.
- **Algolia is already environment-aware**: `media_summarizer/utils/algolia_client.py:78-84` returns `f"media_items_{ENVIRONMENT}"`, and `ENVIRONMENT` is injected from `var.environment`. It is the one external service that already isolates correctly.
- **`aws_apigatewayv2_api.name` is not `ForceNew`** in the AWS provider (schema: `Required`, `ValidateFunc StringLenBetween(1,128)`, no `ForceNew`) — renaming the API updates it in place, so **the dev endpoint `https://jji077bi8e.execute-api.eu-west-3.amazonaws.com` survives the migration**. This matters because that host is wired into the Apple Service ID return URLs, the Google OAuth redirect URI, `APPLE_REDIRECT_URI` in Secrets Manager, `mobile/eas.json` and the pytest E2E suite.

---

## 2. What actually happens if you apply staging today

Three concrete failure modes, all worse than "it errors out". This section is why the historical `V1_LAUNCH_PLAN.md` instruction (copy `terraform.tfvars` with a different `environment`) must never be executed.

### Scenario 1 — same state, `environment = "staging"` (the literal historical instruction)

Terraform reads the existing dev state and, for the 86 unsuffixed resources, sees **no name change at all**. It does not create a staging stack; it **relabels dev as staging**, and then for the 13 resources that *are* suffixed it plans a rename:

- `aws_secretsmanager_secret.runtime`: `media-summarizer-runtime-dev` becomes `*-staging`. The secret `name` is `ForceNew`, so **destroy + create**, and the deleted secret enters a 7-30 day recovery window during which the old name cannot be reused.
- 11 `aws_s3_bucket`: `*-dev` becomes `*-staging`. Bucket names are `ForceNew`, so **destroy + create**. The destroy fails on non-empty buckets (no `force_destroy` is set anywhere), leaving a **half-applied state** — the worst possible outcome, because dev is now partially relabelled and no environment is coherent.
- The 169 transcripts, 16 documents, 6 summaries and 4 audio objects in dev are the only thing standing between this plan and total data loss.

### Scenario 2 — new state key, `environment = "staging"`, unchanged names

No dev *state* is touched, but Terraform now tries to **create** objects that already exist. Each service reacts differently, and the differences are the danger:

| Service | Behaviour on create-with-existing-name | Result |
|---|---|---|
| **SQS** | *"If you specify the name of an existing queue and provide the exact same names and values for all its attributes, the `CreateQueue` action will return the URL of the existing queue instead of creating a new one."* | **Silent adoption.** All 26 of dev's queues are absorbed into the staging state. Both environments' workers then consume from the same queues, and a later `terraform destroy` on staging **deletes dev's queues**. |
| DynamoDB | `ResourceInUseException` | apply aborts |
| Lambda | `ResourceConflictException` | apply aborts |
| IAM | `EntityAlreadyExists` | apply aborts |
| ECR | `RepositoryAlreadyExistsException` | apply aborts |
| CloudWatch log group | `ResourceAlreadyExistsException` | apply aborts |
| S3 / Secrets Manager | suffixed, so **created successfully** | staging half-built |

The realistic outcome: staging's buckets and secret get created, dev's queues get silently hijacked, and the apply dies partway through, leaving two entangled environments and a staging state that is a lie. Recovery requires manual `terraform state rm` on whatever got adopted.

### Scenario 3 — CLI workspace `staging`, unchanged names

Identical to Scenario 2. `terraform workspace new staging` yields an empty state at `env:/staging/infrastructure/terraform.tfstate` and changes **nothing** about physical names. Workspaces isolate state; they do not isolate resources.

**Conclusion: state isolation is necessary but not remotely sufficient. The naming scheme is the load-bearing change.**

---

## 3. The four options, compared

### 3.1 Option A — Terraform CLI workspaces

`terraform workspace new staging`, with `terraform.workspace` (or `var.environment` derived from it) interpolated into all 86 names. With the S3 backend, non-default workspaces automatically get their own key at `<workspace_key_prefix>/<workspace>/<key>`, default prefix `env:`, giving `env:/staging/infrastructure/terraform.tfstate`.

**For:** zero refactor of the existing flat root; state separation comes free with no `-backend-config` to pass; one code path, so environments cannot drift; `terraform workspace show` is a cheap sanity check.

**Against:**

- HashiCorp's own documentation rejects this use case explicitly: *"organizations commonly want to create a strong separation between multiple deployments of the same infrastructure serving different development stages... CLI workspaces within a working directory use the same backend, so they are not a suitable isolation mechanism for this scenario"*, and recommends *"separate Terraform configurations"* with *"different backends"* instead.
- The active environment lives in `.terraform/environment` on the operator's laptop and in CI runner state — **not in the code, not in the pull-request diff, not in the review**. Gruntwork's analysis lists exactly this: *"Hard to navigate environments and understand what's deployed where"*, *"One backend for all workspaces, so no isolation between environments"*, *"One version for all workspaces, so no immutable infrastructure"*.
- There is no way to make `terraform plan` refuse to run in the wrong workspace, because the workspace *is* the selector. Every guard is a wrapper script — i.e. exactly the class of guard a human bypasses by invoking `terraform` directly.
- All three environments share one backend bucket, one lock table and one credential path. That is acceptable today (single AWS account) but forecloses the account split that AWS Well-Architected `SEC01-BP01` recommends before production.
- **It saves none of the rename work.**

**Verdict: rejected.** Its only real advantage over Option B (no code duplication) is also delivered by Option B's shared module.

### 3.2 Option B — per-environment directories over a shared module (recommended)

```
infrastructure/terraform/
  modules/platform/          # every resource that exists today, parameterised
    variables.tf             # environment, aws_region, project_name, enable_alarms,
                             # ecr_repository_url, api_custom_domain, api_zone_id, ...
    locals.tf                # local.suffix = "-${var.environment}"
    dynamodb_*.tf sqs.tf s3.tf lambda_*.tf iam_lambda.tf secrets.tf
    pipeline_alerts.tf pipeline_dashboard.tf archiving.tf bug_reports.tf
    outputs.tf               # NO backend block, NO provider block
  shared/                    # account-scoped singletons
    backend.tf               # key = "env/shared/terraform.tfstate"
    ecr.tf                   # the one repository shared by all environments
  envs/
    dev/       backend key "env/dev/terraform.tfstate"      environment = "dev"
    staging/   backend key "env/staging/terraform.tfstate"  environment = "staging"
    prod/      backend key "env/prod/terraform.tfstate"     environment = "prod"
```

Each `envs/<env>/main.tf` is roughly 40 lines and contains two literals that cannot desynchronise:

```hcl
terraform {
  required_version = "~> 1.9"
  required_providers { aws = { source = "hashicorp/aws", version = "~> 5.0" } }

  backend "s3" {
    bucket         = "media-summarizer-tfstate-125313707865"
    key            = "env/staging/terraform.tfstate"   # literal #1
    region         = "eu-west-3"
    encrypt        = true
    dynamodb_table = "media-summarizer-tfstate-lock"
  }
}

provider "aws" {
  region = "eu-west-3"
  default_tags {
    tags = { Project = "media-summarizer", Environment = "staging", ManagedBy = "terraform" }
  }
}

data "terraform_remote_state" "shared" {
  backend = "s3"
  config  = { bucket = "media-summarizer-tfstate-125313707865", key = "env/shared/terraform.tfstate", region = "eu-west-3" }
}

module "platform" {
  source             = "../../modules/platform"
  environment        = "staging"                      # literal #2
  ecr_repository_url = data.terraform_remote_state.shared.outputs.lambda_ecr_repository_url
  enable_alarms      = true
  api_custom_domain  = "api-staging.secondbrainlabs.com"
}
```

**For:**

- **The safety property is structural, not procedural.** `terraform -chdir=envs/staging apply` reads a backend key that is a compile-time constant of that directory. There is no CLI flag, no workspace, no environment variable and no wrapper script standing between the operator and the correct state. Combined with the naming suffix derived from literal #2, a staging plan physically cannot name a dev resource. This is the strongest possible answer to AC #5.
- The environment is visible in the diff, in the pull request, in the CI job name and in a directory listing.
- Environments are allowed to *legitimately* differ: `enable_alarms = false` in dev and `true` in staging/prod, a different `api_custom_domain`, different reserved concurrency — without a single `count = var.environment == "prod" ? ...` inside the module. This matches HashiCorp's stated rule of thumb: *"Use workspaces for environments that do not greatly deviate from one another... To separate environments with potential configuration differences, use a directory structure."* This project already deviates: `lambda_api.tf:45` branches on `var.environment == "dev"` for reserved concurrency, and `enable_alarms` exists purely to keep dev cheap.
- Prod can later be moved to its own AWS account by changing one provider block and one backend bucket in one directory, with no impact on dev or staging. That is the migration path towards `SEC01-BP01` without a rewrite.
- Per-environment `init` and `plan` in CI are trivially parallelisable, and each job assumes a different OIDC role (§7).

**Against:**

- Requires a one-off refactor: 103 resource blocks move from the root into `module.platform`. This is a **state-address-only** change (no AWS API call), expressed declaratively with `moved` blocks (Terraform >= 1.1; the installed CLI is 1.9.8) so it goes through normal review, and validated by the "plan shows 0 changes" gate (§9, step 1). S3 state versioning is the rollback.
- Roughly 40 lines of near-duplicate boilerplate per environment (backend + provider + module call). Accepted: this is the duplication that buys the literal-key safety property, and it is the *only* duplication — all 103 resources stay defined once.
- Cross-environment references (ECR) need `terraform_remote_state` or a plain variable. Kept to exactly one.

**Verdict: recommended.**

### 3.3 Option C — one root, separate state keys via `-backend-config`

Keep the current flat root; commit `envs/dev.s3.tfbackend`, `envs/staging.s3.tfbackend`, `envs/prod.s3.tfbackend`; run `terraform init -reconfigure -backend-config=envs/staging.s3.tfbackend` then `terraform plan -var-file=envs/staging.tfvars`.

**For:** by far the smallest diff — no module refactor, no state moves, keeps the "one code path" property. State isolation is genuine once the correct `init` has been run.

**Against — and this is disqualifying for a solo operator:**

- A backend block **"cannot refer to named values (like input variables, locals, or data source attributes)"**. There is therefore *no* way for the configuration to assert that the loaded state matches `var.environment`. The two selectors — the `-backend-config` file and the `-var-file` — are independent, and nothing checks their agreement.
- The merged backend configuration is cached in `.terraform/`. Running `terraform plan -var-file=envs/staging.tfvars` in a directory last initialised for dev produces a plan that **renames every dev resource to `-staging`**: a full destroy/create of the environment, presented as a perfectly normal plan. The only defence is remembering `-reconfigure` every single time.
- Every guard is a Makefile wrapper, and wrappers get bypassed precisely on the day someone is debugging at 23:00 — which is the scenario this task exists to prevent.

**Verdict: rejected as the primary mechanism.** It is a reasonable *fallback* if the owner refuses the module refactor; in that case §6's automated gates become mandatory rather than belt-and-braces, and a `make` wrapper that always passes `-reconfigure` must be documented as the only supported entry point.

### 3.4 Option D — Terragrunt (and the OpenTofu variant)

**Terragrunt** solves a real problem: Terraform's backend block accepts no expressions, so a repo with N stacks times M environments must duplicate N times M backend blocks. Terragrunt's `remote_state` / `generate` blocks emit them from `path_relative_to_include()`, and `run-all` orchestrates dependency-ordered applies across stacks.

**For:** eliminates the ~40 lines per environment of boilerplate in Option B; `run-all` matters if the stack count grows; it can auto-provision the backend bucket and lock table.

**Against:** this repo has **one** stack and **three** environments — the exact case where Terragrunt's leverage is smallest. Gruntwork itself lists the cost: *"requires installing a new, separate tool and learning an extra layer of abstraction, and is not natively supported by Terraform Cloud and Terraform Enterprise"*. It also adds a version-pinned binary to every CI job and to the owner's laptop, and puts its own error messages between the operator and Terraform. AGENTS.md mandates KISS where no architecture is already in place.

**OpenTofu** deserves a mention as a *variant of Option C rather than a fifth option*: since 1.8 it supports **early variable evaluation**, which allows input variables inside `backend` blocks — the single limitation that makes Option C unsafe. `tofu init -var="environment=staging"` genuinely removes the backend/var-file desync. It also ships client-side state encryption (AWS KMS, GCP KMS, PBKDF2, OpenBao), which is attractive given that `secret_payload` is stored in plaintext in the state today. **But** it means migrating the whole project off Terraform, and it does not remove the rename work either.

**Verdict: both rejected for now.** Re-evaluate Terragrunt if the repo grows past roughly 4 independently-applied stacks; re-evaluate OpenTofu if state-side secret encryption becomes a compliance requirement (a cheaper mitigation is §7.3's "stop putting secrets in the state").

### 3.5 Comparison matrix (AC #3)

Scale: `++` excellent, `+` good, `~` acceptable, `-` poor, `--` disqualifying.

| Criterion | A. Workspaces | **B. Per-env dirs** | C. `-backend-config` | D. Terragrunt |
|---|:--:|:--:|:--:|:--:|
| **State isolation guarantee** | `+` separate key per workspace, same bucket and credentials; HashiCorp explicitly says it is not an isolation mechanism | `++` literal key per directory; cannot be mis-selected | `+` separate key, but selection is a forgettable CLI flag | `++` generated per-path key |
| **Can the selection be wrong?** | `-` hidden CLI/global state (`.terraform/environment`) | `++` no: the directory *is* the selection | `--` the `.terraform/` cache silently persists the previous environment | `+` derived from the path |
| **Resource-naming ergonomics** | `~` `terraform.workspace` everywhere; the default workspace is named `default`, not `dev` | `++` one `local.suffix` from a literal input | `++` same as B | `++` same as B |
| **Rename work avoided** | `--` none | `--` none | `--` none | `--` none |
| **Blast radius of one mistake** | `-` one state holds N environments' worth of context; wrong workspace means wrong environment | `++` one directory, one environment, one state | `-` a wrong `init` yields a full-environment rename plan | `+` |
| **Env-specific differences (`enable_alarms`, domains, concurrency)** | `~` needs `lookup(var.by_env, terraform.workspace)` maps | `++` plain module inputs | `+` per-environment tfvars | `++` per-environment inputs |
| **Fit with the existing `deploy-lambda.yml`** | `~` one job plus a `workspace select` step | `++` one job per environment, `working-directory` + GitHub Environment + per-env OIDC role | `+` one job plus a `-reconfigure` step | `~` needs the binary installed in every job |
| **Secrets per environment** | `~` 3 payloads in 1 backend | `++` 3 states, 3 secrets; a per-env role can be denied read on the other prefixes | `~` 3 states, but the same init directory | `++` |
| **ECR per environment** | shared repo either way | `++` explicit `shared/` root, promotion by digest | shared repo either way | `++` |
| **Path to a separate prod AWS account** | `--` one backend for all workspaces | `++` change one provider and one backend in one directory | `~` needs a 4th backend file and separate credentials | `++` |
| **Marginal AWS cost** | `$0` | `$0` (3 state objects, ~1.3 MB) | `$0` | `$0` |
| **Operational complexity** | `++` lowest | `+` one module plus 3 thin roots | `++` lowest | `-` extra binary and DSL |
| **One-off migration effort** | `~` rename only | `-` rename plus 103 `moved` blocks (mechanical, state-only) | `++` rename only | `-` rename plus Terragrunt adoption |
| **Reviewability (environment visible in the diff)** | `--` no | `++` yes | `~` only in the tfvars filename | `++` yes |

---

## 4. The naming convention

One local, applied to every physical name in the module:

```hcl
locals {
  suffix = "-${var.environment}"                   # "-dev" | "-staging" | "-prod"
  prefix = "${var.project_name}-${var.environment}"
}
```

`var.environment` gets `validation { condition = contains(["dev", "staging", "prod"], var.environment) }` and **no default** — the current `default = "production"` in `main.tf:38` is itself a hazard, since an apply without tfvars targets an environment token that no resource currently uses.

| Family | Today | Target | AWS limit | Longest result |
|---|---|---|---|---|
| DynamoDB | `users` | `users${suffix}` -> `users-staging` | 3-255, `[a-zA-Z0-9_.-]` | 30 |
| SQS | `podcastindex-resolution-queue` | `...-queue${suffix}` | 80, `[a-zA-Z0-9_-]` | 37 |
| Lambda | `media-summarizer-worker-podcastindex_resolution` | `...${suffix}` | 64 | **55** with `-staging` |
| Log group | `/aws/lambda/media-summarizer-api` | derived from the function name | 512 | n/a |
| IAM role | `media-summarizer-lambda-worker` | `...${suffix}` | 64 | 40 |
| IAM policy | `media-summarizer-lambda-worker-policy` | `...${suffix}` | 128 | 47 |
| CloudWatch alarm | `media-summarizer-llamaparse-fallback-rate-breach` | `...${suffix}` | 255 | 55 |
| CloudWatch dashboard | `media-summarizer-pipeline-observability` | `...${suffix}` | 255 | 47 |
| EventBridge rule | `media-summarizer-api-warmup` | `...${suffix}` | 64 | 35 |
| API Gateway | `media-summarizer-api` | `...${suffix}` (in-place update, ID preserved) | 128 | 28 |
| S3 | `*-125313707865-dev` | unchanged | 63 | 52 |
| Secret / SNS | `*-dev` | unchanged | n/a | n/a |
| **ECR** | `media-summarizer-lambda` | **unchanged — deliberately shared** | n/a | n/a |

The prod token must be `prod`, not `production`, purely to keep the Lambda name budget comfortable (55 rather than 61 of the 64 allowed characters).

Two structural additions come with the convention:

- `provider "aws" { default_tags { ... Environment = "<literal>" } }` in each environment root, so **every** resource carries `Environment` without per-resource repetition. §7's CI discovery depends on this tag.
- `lifecycle { prevent_destroy = true }` on the 21 DynamoDB tables and 11 S3 buckets, plus `deletion_protection_enabled = true` on the tables (supported by `aws_dynamodb_table` in AWS provider v5) and `point_in_time_recovery { enabled = true }` (already requested by `task-218`). `prevent_destroy` **errors at plan time**, which turns "I destroyed prod" into "the plan refused to run". Note its documented caveat: *"This rule doesn't prevent Terraform from destroying a resource if you remove its configuration"* — hence the plan-JSON gate in §6 as a second layer.

---

## 5. Migrating the existing dev environment (AC #4)

### 5.1 Why `terraform state mv` / `moved` does **not** solve renaming

This is the most common misconception about this problem and it must be stated plainly:

> `terraform state mv` and `moved` blocks change a resource's **Terraform address**. They do not, and cannot, change the resource's **physical name in AWS**.

`aws_dynamodb_table.name` is `ForceNew` in the AWS provider — as it must be, because **the DynamoDB API has no rename operation**; the table name is fixed at creation. The same holds for `aws_sqs_queue.name` (`ForceNew: true`, verified in the provider schema), `aws_lambda_function.function_name` (`ForceNew: true`), CloudWatch log groups and IAM roles.

So the four candidate techniques named in the task split into two unrelated jobs:

| Job | Tool | Data risk |
|---|---|---|
| Move `aws_dynamodb_table.users_v2` to `module.platform.aws_dynamodb_table.users_v2` (Option B's refactor) | `moved` block or `terraform state mv` | **none** — state-only, no AWS call |
| Change the table's physical name `users` to `users-dev` | **nothing can do this in place** | destroy + create unless the data is copied first |

`terraform import` is likewise irrelevant to the rename: importing binds an *existing* physical object to an address, which is useful for the ECR extraction in §9 step 2, but it cannot rename anything.

### 5.2 The four candidate strategies for dev's physical rename

| Strategy | Mechanism | Data-loss risk | Downtime | Residual cost |
|---|---|---|---|---|
| **M1. Let Terraform replace** | change `name`, then `terraform apply` | **Total.** 427 items destroyed; no PITR, no backup; `destroy` runs before `create` for DynamoDB | minutes | none |
| **M2. Legacy alias for dev only** | `local.suffix = var.use_legacy_names ? "" : "-${var.environment}"` | **none** | none | dev permanently stops being a faithful rehearsal of prod; one boolean threaded through the module forever; the unsuffixed names stay as landmines for any future fourth environment |
| **M3. Forget-and-copy (recommended)** | `terraform state rm` the 21 tables (leaving them alive in AWS), `apply` to create the suffixed tables, scripted `Scan` to `BatchWriteItem` of 427 items, soak, then `delete-table` on the legacy names | **very low**: Terraform deletes nothing at any point; the source tables survive the whole operation and are removed manually only after verification | ~10 min of dev write-freeze | one reusable script |
| **M4. Cold recreate** | destroy dev, re-apply with the new names | loses 5 users including the owner, 158 `media_artifacts` rows, 18 submissions and 76 usage-counter rows; orphans the 169 transcripts and 16 documents already in S3 | hours | none |

**Recommendation: M3.** M2 is the tempting shortcut and is genuinely zero-risk, but it permanently forks the one code path this whole task exists to make trustworthy — the first time a staging apply behaves differently from a dev apply, the benchmark's value evaporates. M4 destroys real data for no gain given how cheap M3 is. M1 must never be run.

Crucially, **the extra work M3 requires over M2 is work that has to happen anyway**: every table and queue name must be injected as an environment variable and the Python fallbacks removed (§1.3), otherwise staging cannot function at all. Once that is done, M3 is a scan-and-put script over 183 KB.

### 5.3 The M3 runbook for dev

Preconditions, all verified on 2026-08-09 and to be re-verified immediately before execution:

- all 26 SQS queues at depth 0, both visible and in flight;
- no in-flight processing job (`processing_jobs` has no row in a running state);
- the mobile dev client and the E2E suite are not running.

```
Step 0  Safety net
  for each of the 21 tables:
      aws dynamodb create-backup --table-name <T> --backup-name pre-task221-<T>
  aws s3api list-object-versions --bucket media-summarizer-tfstate-125313707865 \
      --prefix env/dev/terraform.tfstate      # note the VersionId to roll back to
  On-demand backups of 183 KB cost about $0.00. Keep them 30 days.

Step 1  Freeze dev writes
  Disable every SQS event source mapping (Terraform variable or CLI) and set the
  API Lambda's reserved concurrency to 0.

Step 2  Detach the 21 tables from Terraform WITHOUT destroying them
  for A in $(terraform -chdir=envs/dev state list | grep aws_dynamodb_table); do
      terraform -chdir=envs/dev state rm "$A"
  done
  `terraform state rm` removes the binding only; the AWS tables are untouched.
  The declarative equivalent is a `removed { ... lifecycle { destroy = false } }`
  block, but here the address is being KEPT, so the CLI form is the right tool.

Step 3  Create the suffixed tables
  terraform -chdir=envs/dev plan -out=tfplan     # MUST show 21 creates, 0 destroys
  ./scripts/tf_plan_guard.sh tfplan dev          # the §6 gate
  terraform -chdir=envs/dev apply tfplan

Step 4  Copy the 427 items
  ./scripts/dynamo_copy_env.py --from users --to users-dev      (x21)
  Implementation: paginated Scan into BatchWriteItem in chunks of 25, with
  unprocessed-item retry. 183 KB total; expected runtime under 60 s for all tables.
  Verify with `aws dynamodb scan --table-name <new> --select COUNT`.
  Do NOT trust DescribeTable.ItemCount: it is refreshed only about every 6 hours.

Step 5  Deploy code that reads the injected names
  All 21 table names and 13 queue names injected by Terraform into both Lambda
  environment blocks; Python fallbacks removed so a missing variable fails fast.

Step 6  Unfreeze and smoke-test
  Re-enable the event source mappings and the API concurrency, then run the pytest
  E2E suite against https://jji077bi8e.execute-api.eu-west-3.amazonaws.com
  (unchanged, per §1.7).

Step 7  Soak for 7 days, then delete the legacy tables
  aws dynamodb delete-table --table-name <legacy>      (x21)
  Keep the Step 0 backups for a further 30 days.
```

Rollback at any point before Step 7: re-enable the event source mappings and redeploy the previous image; the legacy tables still exist and still hold the authoritative data. If Terraform's state itself is wrong, restore the noted S3 object version of `env/dev/terraform.tfstate`.

### 5.4 The other resource families

| Family | Treatment | Loss |
|---|---|---|
| 26 SQS queues | let Terraform replace (verified empty) | none, if depth is re-checked at T-0 |
| 15 Lambda functions | let Terraform replace; Terraform rewires the API Gateway integration and all 14 event source mappings | none |
| 15 log groups | let Terraform replace | dev log history (retention is 14 days anyway) |
| 3 IAM roles and 3 policies | let Terraform replace | none |
| API Gateway | **in-place rename**, ID and URL preserved | none, so no Apple / Google / EAS reconfiguration |
| Dashboard, EventBridge rule, metric filters | let Terraform replace | the dashboard is declarative; metric-filter history is per log group and is lost with it |
| 11 S3 buckets | **untouched** (already suffixed) | none |
| Secret and SNS topic | **untouched** (already suffixed) | none |
| ECR | **untouched** (deliberately shared) | none |

---

## 6. Proving a staging plan cannot touch dev (AC #5)

Five layers, of which the first is structural and the rest are automated gates. **No `terraform apply` is run in staging until layers 1 to 4 pass.**

### Layer 1 — structural (Option B's core property)

`envs/staging/` declares `key = "env/staging/terraform.tfstate"` as a literal and `environment = "staging"` as a literal. A Terraform plan can only propose `update` or `delete` on resources **present in its own state**. The staging state starts empty. Therefore *no first staging plan can contain a single `update` or `delete` action*, and no subsequent one can reference a dev address. This is a property of the tool, not of a script.

### Layer 2 — plan-JSON gate: zero destructive actions

```bash
terraform -chdir=envs/staging plan -out=tfplan -detailed-exitcode   # 0 none, 1 error, 2 changes
terraform -chdir=envs/staging show -json tfplan > plan.json

test "$(jq '[.resource_changes[] | select(.change.actions | index("delete"))] | length' plan.json)" -eq 0
```

### Layer 3 — plan-JSON gate: every created name carries the environment token

Every name-bearing attribute in every planned `create` must end with `-staging`, except S3 buckets which are already suffixed. The shared ECR repository is not managed by the staging root at all, so it never appears here.

```bash
jq -r '
  .resource_changes[]
  | select(.change.actions | index("create"))
  | .change.after
  | [.name, .bucket, .function_name, .repository_name, .alarm_name, .dashboard_name]
  | .[] | select(. != null)
' plan.json | grep -vE -- '-staging$' && { echo "FAIL: un-suffixed name in staging plan"; exit 1; }
```

### Layer 4 — cross-check against dev's live physical names

The decisive test. Build the set of dev's actual physical names and assert that the intersection with staging's planned names is empty.

```bash
terraform -chdir=envs/dev show -json | jq -r '
   .values.root_module | .. | .values? // empty
   | [.name, .bucket, .function_name, .repository_name] | .[] | select(. != null)' \
  | sort -u > dev_names.txt

jq -r '.resource_changes[].change.after
       | [.name, .bucket, .function_name, .repository_name] | .[] | select(. != null)' plan.json \
  | sort -u > staging_names.txt

comm -12 dev_names.txt staging_names.txt > collisions.txt
test ! -s collisions.txt      # a non-empty file is a hard fail: no apply
```

### Layer 5 — post-apply assertion that dev is unchanged

Immediately after the staging apply, in CI, against the dev directory:

```bash
terraform -chdir=envs/dev plan -detailed-exitcode -refresh-only   # exit 0 required: no drift
terraform -chdir=envs/dev plan -detailed-exitcode                 # exit 0 required: no changes
```

Exit code 0 means "succeeded with an empty diff"; exit code 2 means changes are pending and **fails the pipeline**. This converts "we believe dev is fine" into a recorded, reproducible artefact.

### Belt and braces

- `prevent_destroy = true` on all 21 tables and 11 buckets, in the module, for **all** environments — errors at plan time.
- `deletion_protection_enabled = true` on the tables — AWS itself rejects `DeleteTable`.
- PITR enabled, giving a 35-day restore window if everything above fails.
- The per-environment CI role (§7) is granted `dynamodb:DeleteTable` and `s3:DeleteBucket` on **nothing**; destructive operations require the owner's admin identity.

---

## 7. GitHub Actions and ECR requirements (AC #6)

### 7.1 ECR: one repository, environment-agnostic images, digest promotion

Keep **one** `media-summarizer-lambda` repository, owned by `infrastructure/terraform/shared/`. Rationale: the artefact tested in staging must be **bit-identical** to the one released to prod. Per-environment repositories force a rebuild per environment and make that guarantee impossible.

| Item | Today | Target | Why |
|---|---|---|---|
| Tag mutability | `MUTABLE` (verified live) | `IMMUTABLE`, with an exclusion filter for `*-latest` | Prevents a rebuilt `api-<sha>` from silently changing what prod runs. ECR supports `IMMUTABLE_WITH_EXCLUSION` with wildcard filters, so the bootstrap `api-latest` and `worker-latest` tags Terraform needs can stay mutable. |
| Tag scheme | `api-<sha>`, `worker-<sha>`, `api-latest`, `worker-latest` | **unchanged — do not add an environment token** | The image is not environment-specific; the environment lives entirely in the Lambda's environment variables and IAM role. Adding `-staging` to a tag would mean rebuilding per environment. |
| Deployment reference | already `repo@sha256:<digest>` | unchanged | Already correct: `update-function-code --image-uri ...@${{ steps.build.outputs.digest }}`. |
| Lifecycle policy | keep **3** per `api-` / `worker-` prefix (`ecr.tf:36-59`) | keep **at least 15** per prefix | With 3 environments, a prod rollback target is expired after **two** dev pushes. Live check: 5 images, ~1.8 GB total (worker ~404 MB, api ~297 MB). 15 per prefix is roughly 5 GB, about **$0.53/month**. |
| Cross-account | n/a | add a repository policy granting `ecr:BatchGetImage` and `ecr:GetDownloadUrlForLayer` to the future prod account | Only needed the day prod moves accounts; noted now so it is not discovered during a release. |

### 7.2 `deploy-lambda.yml`: environment awareness

1. **Build once per commit**, in a `build` job, pushing `api-<sha>` and `worker-<sha>` plus the two bootstrap `latest` tags. Emit both digests as job outputs.
2. **Three deploy jobs** (`deploy-dev`, `deploy-staging`, `deploy-prod`), each declaring `environment: dev | staging | production` and consuming the digests from `build`. Never rebuild.
3. **Per-environment OIDC role.** `secrets.AWS_DEPLOY_ROLE_ARN` becomes an **environment-scoped** secret; GitHub environment secrets are only accessible to jobs using that environment and are revealed only after protection rules pass. Each role's trust policy must pin the OIDC subject claim to that environment — GitHub's `sub` for a job referencing an environment is `repo:<org>/<repo>:environment:<name>` — so the dev role literally cannot be assumed by a job that did not declare `environment: dev`.
4. **Protection rules**: `production` gets required reviewers (the owner) plus a deployment branch policy restricted to `main` or to release tags; `staging` gets a branch policy; `dev` auto-deploys on push to `main`.
5. **Function discovery by tag, not by name prefix.** The module already tags every resource and §4 adds `default_tags`, so:

   ```bash
   aws resourcegroupstaggingapi get-resources \
     --resource-type-filters lambda:function \
     --tag-filters Key=Environment,Values=${{ inputs.environment }} \
     --query 'ResourceTagMappingList[].ResourceARN' --output text
   ```

   This replaces the `starts_with(FunctionName, 'media-summarizer-worker-')` wildcard, which once staging exists would return **every** environment's workers and push the same image to production.
6. **API function name** becomes `media-summarizer-api-${env}`, passed as a job input, never hardcoded.
7. **Health check by API ID, not by name.** API Gateway names are not unique, so `Items[?Name=='media-summarizer-api'].ApiEndpoint | [0]` is non-deterministic across environments. The environment's `api_endpoint` Terraform output, or an `Environment` tag filter, must be the source of truth. The health gate stays blocking, per environment.
8. **A staging deploy must not be able to reach dev.** Guaranteed by point 3: the staging role's policies target `*-staging` ARNs only.

### 7.3 Secrets per environment

- One `media-summarizer-runtime-<env>` per environment already exists as a pattern; staging and prod need theirs created with **distinct third-party credentials**: RevenueCat sandbox versus live, a separate `JWT_SECRET_KEY`, separate Apify / Deepgram / OpenAI keys (or at minimum separate keys for cost attribution), and a distinct `ALGOLIA_INDEX_NAME`. Algolia is already isolated at the code level through `media_items_{ENVIRONMENT}`.
- **Stop passing `secret_payload` through Terraform for staging and prod.** `secret_string` is stored in **plaintext inside the state file**, mitigated only by SSE-S3 at rest; with three environments that is three copies. `secrets.tf` already carries `lifecycle { ignore_changes = [secret_string] }`, so the clean pattern is: Terraform creates the empty secret shell, and the owner populates it once with `aws secretsmanager put-secret-value`. This also removes the need for three secret-bearing `terraform.tfvars` files on the laptop.
- Deleting or renaming a secret is not free: Secrets Manager holds a deleted name for a 7 to 30 day recovery window. Another reason the already-suffixed secret must not be touched during the migration.

---

## 8. Cost

Marginal monthly cost of adding staging (and later prod) in the same account and region, at current volumes:

| Item | dev today | plus staging | Note |
|---|---|---|---|
| DynamoDB (on-demand, 21 tables) | ~$0 | ~$0 | 183 KB; storage is $0.25 per GB-month |
| DynamoDB PITR (recommended) | $0 | under $0.01 | $0.20 per GB-month |
| S3 (11 buckets, ~200 objects) | ~$0 | ~$0 | |
| SQS (26 queues) | $0 | $0 | 1 M requests/month free tier, per account |
| Lambda (15 functions) | ~$0 | ~$0 | the free tier is per account and is shared across environments |
| Secrets Manager | $0.40 | **+$0.40** | $0.40 per secret per month |
| CloudWatch alarms | $0 (`enable_alarms = false`) | **+$4.20** | 42 alarms at $0.10; the project's own Terraform README states this figure |
| CloudWatch Logs ingestion | low | proportional to staging traffic | 14-day retention already set |
| ECR storage | ~$0.18 (1.8 GB) | **+$0.35** | only if the lifecycle policy is raised to 15 images per prefix, as §7.1 requires |
| Terraform state (3 objects, ~450 KB each) and lock table | ~$0 | ~$0 | |
| **Total marginal** | | **about $5/month** | dominated entirely by the CloudWatch alarms the owner *wants* in staging |

No option in §3 differs on cost: all four produce the same AWS resources. A separate AWS account for prod (AWS Well-Architected `SEC01-BP01`) is also free in itself, but the AWS Free Tier is granted per organization, so a second account does not double the free allowances — the real cost of the account split is operational, not financial.

---

## 9. Sequenced execution plan

Each step is independently revertible and ends with a verifiable gate. Steps 1 and 2 are pure refactors that must produce **zero** AWS changes.

| # | Step | Gate |
|---|---|---|
| **1** | Create `modules/platform/` by relocating the 18 `.tf` files (preserving history); strip the `backend` and `provider` blocks; add `variables.tf` and `outputs.tf`. Create `envs/dev/` with the literal backend key `env/dev/terraform.tfstate` and `environment = "dev"`. Copy the state object to the new key within the bucket. Add `envs/dev/moved.tf` with one `moved` block per resource block (103), generated from `terraform state list`. **No name changes yet.** | `terraform -chdir=envs/dev plan -detailed-exitcode` returns **exit 0**, "No changes." Then delete `moved.tf`. |
| **2** | Extract the ECR repository into `shared/` (cross-state move: `terraform state rm` in dev plus an `import` block in `shared/`). Wire `ecr_repository_url` as a module input. | dev plan exit 0; `shared` plan exit 0 after import. |
| **3** | Add `local.suffix`, `var.environment` validation with no default, `default_tags`, `prevent_destroy`, `deletion_protection_enabled` and PITR. Apply **only the non-renaming parts** to dev. | dev plan shows only tag / PITR / protection updates and **0 destroys**. |
| **4** | Inject all 21 table names and 13 queue names into both Lambda environment blocks; remove every hardcoded fallback in Python so a missing variable fails fast. Deploy to dev **before** any rename. | dev E2E suite green with the injected (still legacy) names. |
| **5** | Scope the Lambda DynamoDB IAM policy from `table/*` down to the environment's explicit table ARNs. | dev E2E green. |
| **6** | **Rename dev** per the §5.3 M3 runbook. | 21 legacy tables still present; item counts match by full `Scan --select COUNT`; E2E green; dev API URL unchanged. |
| **7** | Create `envs/staging/`, run the §6 gate suite, then apply. | Layers 1 to 4 pass **before** apply; layer 5 passes after. |
| **8** | Rework `deploy-lambda.yml` per §7: build once, three gated deploy jobs, tag-based discovery, per-environment OIDC roles, ECR lifecycle at 15 or more. | A staging deploy leaves dev's Lambdas' `CodeSha256` unchanged. |
| **9** | Create `envs/prod/` with `enable_alarms = true`, required reviewers on the `production` GitHub environment, and its own secret. | The same gate suite, run against **both** dev and staging. |
| **10** | Delete the legacy dev tables after the 7-day soak; update `docs/V1_LAUNCH_PLAN.md` (remove the "copy `terraform.tfvars`" instruction) and `infrastructure/terraform/README.md`. | — |

Steps 1 to 6 unblock nothing on their own but are prerequisites; **step 7 is the one that unblocks Phase 9**.

---

## 10. Risks, rollback and what this benchmark does not decide

| Risk | Mitigation |
|---|---|
| The 103 `moved` blocks are wrong and Terraform plans a destroy | The step 1 gate is `plan == "No changes."` A non-empty plan means stop. The state is restorable from an S3 object version. |
| Someone runs Terraform inside `modules/platform/` directly | The module has no `backend` and no `provider` block, so `terraform plan` there fails immediately. |
| The dev copy script drops items | Full `Scan --select COUNT` on both sides; legacy tables kept for 7 days and on-demand backups for 30. |
| A staging apply collides on a name anyway | §6 layers 2 to 4 fail the pipeline **before** apply. |
| CI pushes a dev image to prod | Per-environment OIDC roles pinned to `repo:...:environment:<name>`, plus tag-based function discovery. |
| A prod rollback image is expired from ECR | Lifecycle policy raised to 15 or more per prefix. |
| Secrets multiply across three states | Stop passing `secret_payload` through Terraform for staging and prod. |
| A fourth environment (ephemeral PR environments) is wanted later | Option B extends by adding a directory; if the count grows past roughly 4 stacks, revisit Terragrunt (§3.4). |

**Explicitly out of scope of this benchmark**, called out so the owner can decide separately:

- **Separate AWS accounts per environment.** AWS Well-Architected `SEC01-BP01` recommends account-level separation, and it is the only mechanism that makes cross-environment access *impossible* rather than *policed*. Option B is the layout that makes that migration a one-directory change later. Doing it now would delay Phase 9 by weeks.
- **Migrating the S3 backend lock from `dynamodb_table` to `use_lockfile`** — deprecated, and `use_lockfile` requires Terraform 1.10 or later while the installed CLI is 1.9.8.
- **State-side secret encryption**, which would mean OpenTofu (§3.4).
- **The `user_media` table from `task-218` / `task-219` / `task-220`.** It must be created *with* the new naming convention. If `task-219` lands before step 6, the table is created as `user_media` and joins the M3 migration list; if after, it is born as `user_media-dev`. Sequencing those two is an owner decision.

---

## 11. Sources

**Repository and live evidence**

- `infrastructure/terraform/*.tf` (18 files, 103 resource blocks), `.github/workflows/deploy-lambda.yml`, `media_summarizer/core/config.py`, `media_summarizer/utils/database_async.py`, `media_summarizer/utils/sqs.py`, `media_summarizer/utils/algolia_client.py`, `docs/V1_LAUNCH_PLAN.md`, `docs/research/task-218-durable-media-library-persistence/README.md`.
- Read-only AWS inspection, account `125313707865`, region `eu-west-3`, 2026-08-09: `sts get-caller-identity`; `s3api list-buckets`, `list-objects-v2`, `list-object-versions`, `get-bucket-versioning`, `get-bucket-encryption`; `dynamodb list-tables`, `describe-table`, `describe-continuous-backups`; `sqs list-queues`, `get-queue-attributes`; `lambda list-functions`; `ecr describe-repositories`, `describe-images`; `apigatewayv2 get-apis`; `cloudwatch describe-alarms`, `list-dashboards`; `logs describe-log-groups`; and a streamed read of `s3://media-summarizer-tfstate-125313707865/infrastructure/terraform.tfstate`.

**Terraform, OpenTofu, Terragrunt**

- Manage workspaces, including the "not a suitable isolation mechanism" statement: https://developer.hashicorp.com/terraform/cli/workspaces
- S3 backend: `workspace_key_prefix`, the `env:/` layout, `use_lockfile`, and the DynamoDB locking deprecation: https://developer.hashicorp.com/terraform/language/backend/s3
- Backend partial configuration, including "A backend block cannot refer to named values": https://developer.hashicorp.com/terraform/language/backend
- Organize configuration for multiple environments, directories versus workspaces: https://developer.hashicorp.com/terraform/tutorials/modules/organize-configuration
- `lifecycle` meta-argument: `prevent_destroy` errors at plan time, and its removal caveat: https://developer.hashicorp.com/terraform/language/meta-arguments/lifecycle
- Refactoring with `moved` blocks: https://developer.hashicorp.com/terraform/language/modules/develop/refactoring
- `terraform state mv` command reference: https://developer.hashicorp.com/terraform/cli/commands/state/mv
- `terraform plan` and `-detailed-exitcode` (0 no changes, 1 error, 2 changes): https://developer.hashicorp.com/terraform/cli/commands/plan
- Gruntwork, managing multiple environments with workspaces (the five drawbacks): https://www.gruntwork.io/blog/how-to-manage-multiple-environments-with-terraform-using-workspaces
- Gruntwork, managing multiple environments with Terragrunt (the cost of the extra tool): https://www.gruntwork.io/blog/how-to-manage-multiple-environments-with-terraform-using-terragrunt
- Terragrunt, keeping the state backend DRY: https://docs.terragrunt.com/features/state-backend/
- OpenTofu, early variable evaluation (variables inside `backend` blocks, 1.8 and later) and state encryption: https://opentofu.org/
- AWS provider, `aws_dynamodb_table` (`deletion_protection_enabled`; `name` forces replacement): https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/dynamodb_table
- AWS provider schemas verified in source at https://github.com/hashicorp/terraform-provider-aws : `internal/service/dynamodb/table.go` (top-level `name` is `Required` and `ForceNew`), `internal/service/sqs/queue.go:107-113` (`ForceNew: true`), `internal/service/lambda/function.go:243-248` (`function_name` is `ForceNew: true`), `internal/service/apigatewayv2/api.go:142-146` (`name` has **no** `ForceNew`).

**AWS**

- SQS `CreateQueue`: idempotent adoption of an identically configured existing queue, `QueueNameExists` otherwise: https://docs.aws.amazon.com/AWSSimpleQueueService/latest/APIReference/API_CreateQueue.html
- DynamoDB basic table operations: table names are unique per account per region, and there is no rename API: https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/WorkingWithTables.Basics.html
- DynamoDB, restoring a table from a backup (a restore always creates a **new** table name): https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/Restore.Tutorial.html
- DynamoDB point-in-time recovery: https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/PointInTimeRecovery.html
- DynamoDB on-demand pricing: https://aws.amazon.com/dynamodb/pricing/on-demand/
- ECR image tag mutability, including `IMMUTABLE_WITH_EXCLUSION`: https://docs.aws.amazon.com/AmazonECR/latest/userguide/image-tag-mutability.html
- ECR pricing: https://aws.amazon.com/ecr/pricing/
- Secrets Manager pricing and the deletion recovery window: https://aws.amazon.com/secrets-manager/pricing/
- CloudWatch pricing, $0.10 per alarm metric per month: https://aws.amazon.com/cloudwatch/pricing/
- Resource Groups Tagging API, `GetResources` with tag filters: https://docs.aws.amazon.com/resourcegroupstagging/latest/APIReference/API_GetResources.html
- AWS Well-Architected `SEC01-BP01`, separate workloads using accounts: https://docs.aws.amazon.com/wellarchitected/latest/framework/sec_securely_operate_multi_accounts.html
- AWS Control Tower, multi-account strategy for a landing zone: https://docs.aws.amazon.com/controltower/latest/userguide/aws-multi-account-landing-zone.html

**GitHub Actions**

- Managing environments: environment secrets, required reviewers, deployment branch policies: https://docs.github.com/en/actions/how-tos/deploy/configure-and-manage-deployments/manage-environments
- OpenID Connect subject claims (`repo:<org>/<repo>:environment:<name>`) for scoping cloud trust policies: https://docs.github.com/en/actions/concepts/security/openid-connect
- `aws-actions/configure-aws-credentials`: https://github.com/aws-actions/configure-aws-credentials
