---
id: task-341
title: >-
  Apply Terraform automatically on dev when a push to main touches
  infrastructure
status: Done
assignee: []
created_date: '2026-09-03 10:14'
updated_date: '2026-09-03 08:40'
labels:
  - infrastructure
  - terraform
  - ci
dependencies: []
priority: high
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Owner decision, 2026-09-02: **`terraform apply` runs automatically on a push to
`main`, on the dev account only.** Prod stays 100 % manual, mirroring the shape
`deploy-lambda.yml` already uses for `promote-prod`.

## Nothing runs Terraform today. Not even `validate`.

Audited 2026-09-02/03, all six workflows:

- `main.yml` and `pr.yml` run ruff, mypy, four guard scripts, plus the mobile typecheck
  and lint. The string `terraform` appears in them only inside grep paths.
- `deploy-lambda.yml` filters on `media_summarizer/**`, `pyproject.toml`, two
  Dockerfiles and its own file. **`infrastructure/terraform/**` is not in that list**,
  so a commit that touches only Terraform triggers nothing at all — no apply, no plan,
  no validate, no fmt check.
- `scripts/tf_plan_guard.sh` (215 lines, built by `task-221` §6 to implement layers 2-4
  of the isolation proof suite) is invoked by **no workflow**. It exists and is unused.

The cost is not hypothetical. Of the commits currently unpushed on `main`, two add
CloudWatch alarms (`e2cae8d`, `aebbb73`) that no `terraform apply` has ever seen — the
dev runtime is not HEAD, and nothing in CI would have said so.

## Why the existing role cannot do this

`infrastructure/terraform/envs/dev/gha_oidc.tf` manages `media-summarizer-gha-deploy`,
and its inline policy is deliberately narrow: ECR auth plus push/pull on one repository
ARN, `lambda:ListFunctions`, `lambda:Update*` scoped to
`arn:aws:lambda:eu-west-3:125313707865:function:media-summarizer-*-dev`,
`tag:GetResources`, `apigateway:GET`. **No state bucket, no lock table, no IAM.** It
cannot run `terraform init` against the S3 backend, let alone apply.

Do not widen it. That narrowness is load-bearing and documented at length in the file's
header comment (`task-256`): the `-dev` suffix on the Lambda grant is what stops a push
to `main` overwriting a staging function, and the ECR asymmetry is what stops a prod job
minting an unpromoted image. Add a **second, separate role** instead.

## What to build

### 1. A privileged Terraform role in the dev root

`media-summarizer-gha-terraform-dev`, declared in
`infrastructure/terraform/envs/dev/`. Its trust policy references the **existing**
`aws_iam_openid_connect_provider.github` resource — there is one OIDC provider per
account and creating a second one at the same URL fails — and pins `sub` with
`StringLike` to `repo:${var.github_repository}:ref:${var.github_ref}`, reusing the
variables already declared in `gha_oidc.tf`. Expose its ARN through an output,
symmetrically with the existing `gha_deploy_role_arn`.

**Be honest in the code about what this role is.** The dev root manages 23 DynamoDB
tables, 26 SQS queues, 21 metric alarms, 25 log metric filters, 4 Lambda functions,
6 IAM roles, 7 IAM policies, 9 policy attachments, the OIDC provider itself and a
Secrets Manager secret. Applying that requires `iam:CreateRole`,
`iam:AttachRolePolicy` and `iam:PassRole` — which means the role can grant itself
anything in the account. **It is effectively administrator on dev, and no amount of
policy text changes that.** Write that in a comment rather than composing a long
policy that pretends otherwise. The mitigations that are real, and that the comment
should name:

1. the account boundary — dev and prod are separate AWS accounts (`task-248`), so no
   prod ARN is nameable from here at all;
2. the trust policy pins `ref:refs/heads/main`, so only a job on `main` can assume it;
3. prod and `shared/` are out of this workflow's reach by construction (see below).

### 2. `.github/workflows/terraform-dev.yml`

- `on: push` on `main` with `paths` covering `infrastructure/terraform/**` and the
  workflow file itself, plus `workflow_dispatch`.
- `permissions: { id-token: write, contents: read }`.
- `concurrency` with **`cancel-in-progress: false`**. The DynamoDB lock table
  (`media-summarizer-tfstate-lock`) already prevents state corruption, but cancelling
  an apply mid-flight leaves a stale lock somebody has to force-unlock by hand. Two
  pushes must queue, never interrupt each other.
- `hashicorp/setup-terraform` pinned to an **exact** `terraform_version` satisfying the
  `required_version = ">= 1.9"` that all four roots declare. Not `latest`.
- Steps: `fmt -check -recursive` → `init` → `validate` →
  `plan -out=tfplan -input=false -lock-timeout=5m` →
  **`scripts/tf_plan_guard.sh dev tfplan`** → `apply -input=false tfplan`.
- Two details in that chain are the whole safety story:
  - The guard already exists and its contract is documented at the top of the script:
    exit 0 means safe to apply. Call it **without `--allow-replace`** — a replacement on
    dev should stop the pipeline and fetch a human, since `--allow-replace` is precisely
    what makes deleting a queue or a Lambda acceptable.
  - Apply the **saved plan file**, never `terraform apply -auto-approve`. Otherwise what
    gets applied is a fresh plan nobody guarded.
- Scope the job to `envs/dev` only. No `envs/prod`, no `envs/staging`, no `shared/`.
  `shared/` is deliberately excluded too: it holds the ECR registry prod pulls images
  from, so an automated apply there would reach across the account boundary the
  isolation work exists to hold.
- **No new GitHub secret.** The role ARN can be a literal in the workflow: the dev
  account id `125313707865` is already in the state bucket name, in
  `allowed_account_ids` and in the import runbook of `gha_oidc.tf`, and `AGENTS.md` is
  explicit that identifiers Terraform needs are not secrets. The output added in step 1
  is the source of truth the literal mirrors. Keeping this task free of owner
  prerequisites beyond the one bootstrap apply is the point.

### 3. Close the "Terraform-only PR is checked by nothing" hole

Add to `pr.yml`: `terraform fmt -check -recursive`, then `terraform init -backend=false`
plus `terraform validate` over `envs/dev`, `envs/prod`, `envs/staging`, `shared/` and
`modules/platform/`. `-backend=false` is the point — validate needs neither credentials
nor state, so prod and staging get syntax-checked without any prod identity being
involved anywhere in a PR.

Residual, and deliberately out of scope: every workflow in this repo pins actions by
tag (`actions/checkout@v4`) rather than by commit SHA. That is the remaining
supply-chain surface, and it now sits in front of an admin-on-dev role. Worth a separate
task; do not fix it here.

## Owner notes — not acceptance criteria

- **Bootstrap is chicken-and-egg, and only you can break it.** The workflow cannot
  create the role it needs to assume. After this merges and `main` is pushed, run one
  **local** `terraform -chdir=infrastructure/terraform/envs/dev apply` with your own
  admin credentials to create the role. Until that apply happens, every run of the new
  workflow dies on `AssumeRoleWithWebIdentity`, and that is expected.
- **Read the first automated plan before letting it through.** It will contain
  everything currently unapplied, including the two alarm commits above — not just this
  task's role.
- Prod remains a manual `terraform apply` from your machine, by decision, not by
  omission.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 infrastructure/terraform/envs/dev/ declares an IAM role media-summarizer-gha-terraform-dev, distinct from media-summarizer-gha-deploy, whose assume-role policy references the existing aws_iam_openid_connect_provider.github resource and pins sub with StringLike to repo:${var.github_repository}:ref:${var.github_ref} using the already-declared variables
- [x] #2 No second aws_iam_openid_connect_provider is created, and media-summarizer-gha-deploy with its inline deploy policy is left byte-identical
- [x] #3 envs/prod/, envs/staging/, shared/ and modules/platform/ are unmodified by this task
- [x] #4 A comment on the new role states plainly that it is effectively administrator on the dev account, why no narrower scope is honest given the IAM resources the dev root manages, and names the three real mitigations (account boundary, refs/heads/main pin, prod and shared out of reach)
- [x] #5 An output exposes the new role ARN, symmetrically with the existing gha_deploy_role_arn output
- [x] #6 terraform fmt -check -recursive and terraform validate pass on infrastructure/terraform/envs/dev
- [x] #7 terraform plan on envs/dev proposes no destroy, and scripts/tf_plan_guard.sh dev <planfile> exits 0 on that plan file; the plan summary line and the guard output are pasted into the Implementation Notes
- [x] #8 .github/workflows/terraform-dev.yml triggers on push to main with paths covering infrastructure/terraform/**, declares id-token write, assumes the new role by OIDC, and runs Terraform against envs/dev only — the file names no other root
- [x] #9 The workflow calls scripts/tf_plan_guard.sh dev on the saved plan file between plan and apply, without --allow-replace, and the apply step applies that saved plan file rather than using -auto-approve
- [x] #10 The workflow declares a concurrency group with cancel-in-progress false and pins an exact terraform_version rather than latest
- [x] #11 The workflow references no GitHub secret: the role ARN is a literal whose source of truth is the Terraform output from AC#5, noted as such in a comment
- [x] #12 pr.yml runs terraform fmt -check -recursive and, for each of envs/dev, envs/prod, envs/staging, shared and modules/platform, terraform init -backend=false followed by terraform validate
- [x] #13 infrastructure/terraform/README.md records the 2026-09-02 decision — dev auto-applies on push to main, prod and shared/ stay manual — and the one-time local apply that bootstraps the role
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
All 13 acceptance criteria are met. Four files touched, two of them new:

| File | Change |
|---|---|
| `infrastructure/terraform/envs/dev/gha_terraform.tf` | **new** — the role, its trust policy, the `AdministratorAccess` attachment and the ARN output |
| `.github/workflows/terraform-dev.yml` | **new** — fmt → init → validate → plan → guard → apply, on `envs/dev` only |
| `.github/workflows/pr.yml` | new `terraform` job: fmt + `init -backend=false` / `validate` over the five directories |
| `.github/workflows/main.yml` | the same job, see "One deliberate addition" below |
| `infrastructure/terraform/README.md` | new section "Terraform in CI", the third dev role, the bootstrap runbook, two table rows |

`envs/dev/gha_oidc.tf` is **untouched** — `git diff` lists it nowhere, so AC#2's
byte-identical requirement holds by construction rather than by inspection. Same for
`envs/prod/`, `envs/staging/`, `shared/` and `modules/platform/` (AC#3).

### AC#7 — the real plan and the real guard run

Run from the worktree with the owner's admin credentials on `125313707865`
(`aws sts get-caller-identity --query Account` → `125313707865`), against the live
`env/dev/terraform.tfstate`. Plan summary line:

```
Plan: 5 to add, 0 to change, 0 to destroy.

Changes to Outputs:
  + gha_terraform_role_arn = (known after apply)
```

The five creates, from `terraform show -json tfplan`:

```
create  aws_iam_role.gha_terraform
create  aws_iam_role_policy_attachment.gha_terraform_admin
create  module.platform.aws_cloudwatch_log_metric_filter.llm_generation_failed["artifact_generator"]
create  module.platform.aws_cloudwatch_log_metric_filter.llm_generation_failed["transcript_translation"]
create  module.platform.aws_cloudwatch_log_metric_filter.revenucat_subscription_unmatched
```

Two of this task's, three from the unapplied alarm commits (`e2cae8d`, `aebbb73`) — the
drift the task predicted, visible in a plan for the first time. `scripts/tf_plan_guard.sh dev tfplan`:

```
== Layer 2: no destructive action in the dev plan ==========
OK: 0 delete actions on tables, buckets, secrets or the ECR repository.
OK: 0 delete actions at all.

== Layer 3: every created name carries the '-dev' token ====
OK: every created name ends with -dev.

== Layer 4: skipped (no other environment given) ==================

PASS: the dev plan is safe to apply.
guard exit=0
```

**Nothing was applied.** The plan file was written, gated and deleted; the account is
still in the state the plan describes. That first apply is the owner's bootstrap step.

### Verification commands run

- `terraform fmt -check -recursive infrastructure/terraform` → exit 0 (AC#6)
- `terraform -chdir=infrastructure/terraform/envs/dev init -input=false` → aws 5.100.0, archive 2.8.0
- `terraform -chdir=infrastructure/terraform/envs/dev validate` → Success (AC#6)
- `terraform -chdir=infrastructure/terraform/envs/dev plan -out=tfplan -input=false -lock-timeout=5m` → see above
- `scripts/tf_plan_guard.sh dev tfplan` → exit 0
- The exact `pr.yml` loop replayed on a scratch copy of `infrastructure/terraform`, in a
  directory with no `.terraform` and no lock file, to prove it works from a cold
  checkout: `init -backend=false` + `validate` → **Success on all five**
  (`envs/dev`, `envs/prod`, `envs/staging`, `shared`, `modules/platform`), with no AWS
  call and no state read. `modules/platform` validates fine even though it declares no
  backend and no provider, which is the case worth having checked.
- `python3 -c "yaml.safe_load(...)"` on the three workflow files → jobs parse as
  `terraform-dev.yml: [apply]`, `pr.yml: [backend, terraform, mobile]`,
  `main.yml: [backend, terraform, mobile]`. `actionlint` is not installed here, so the
  YAML was checked for parseability rather than for Actions-specific lint.
- `grep -nE "envs/[a-z]+|shared/|modules/" .github/workflows/terraform-dev.yml` → three
  hits, all `envs/dev` (AC#8, "the file names no other root").
- `grep -n "secrets\." .github/workflows/terraform-dev.yml` → nothing (AC#11).

### Why `AdministratorAccess` and not an enumerated policy

The task asked for honesty over policy text, and the enumeration would have been a lie
of a specific kind: this root manages 6 IAM roles, 7 policies and 9 attachments, so the
policy must include `iam:CreateRole`, `iam:PutRolePolicy`, `iam:AttachRolePolicy` and
`iam:PassRole`. A principal with those four can mint a role with any permission in the
account and pass it to a Lambda, so a 400-line policy enumerating `dynamodb:*`,
`sqs:*`, `lambda:*` … `iam:*` would be exactly as privileged as `AdministratorAccess`,
only longer, and silently wrong the first time a new resource type is added to the
module. The header of `gha_terraform.tf` states that the role is administrator on dev
and names the three mitigations that are structural: the account boundary, the
`ref:refs/heads/main` subject pin, and the workflow naming one root directory.

It also names one thing that is **not** a mitigation and is easy to mistake for one:
`tf_plan_guard.sh` gates the diff Terraform proposes, not what the credentials can do. A
job on `main` that ran `aws iam create-user` instead of `terraform plan` never reaches
the guard.

### One deliberate addition beyond the ACs

AC#12 asks for the checks in `pr.yml`; I added the identical job to `main.yml` as well.
Reason: `main` is not a protected branch and this project commits straight to it, so a
PR-only check is a check that runs almost never — which is the same argument `main.yml`
already makes in its own comment about the four grep guards ("Keep the two lists in
sync — a guard that only runs on PRs is a guard the shortest path around it disables").
`terraform-dev.yml` does cover `fmt` and the dev root on a push, but only when the push
touched `infrastructure/terraform/**`, and it names no other root by design, so prod,
staging, `shared/` and `modules/platform/` would otherwise be validated nowhere on the
branch that actually receives commits. The cost is one extra ~1 min job per push to
main. Drop the `main.yml` job if that trade is not wanted; nothing else depends on it.

### Choices worth knowing about

- **`terraform_version: 1.9.8`**, the version installed on the owner's machine. `>= 1.9`
  in all four roots would let `latest` pull a future 2.x, and `terraform show -json` is
  parsed by the guard, so the CI binary matches the local one instead of floating. The
  literal appears in three workflow files; the pin in `terraform-dev.yml` carries the
  comment, the two others point at it.
- **`terraform_wrapper: false`** on every `setup-terraform`. The wrapper re-emits command
  output to expose it as a step output; `tf_plan_guard.sh` redirects
  `terraform show -json` into a file and parses it with `jq`, so anything the wrapper
  adds breaks the guard rather than just the log.
- **An account assertion before the apply.** `aws sts get-caller-identity` must return
  `125313707865`, mirroring what `promote-prod` does in `deploy-lambda.yml`. It turns a
  mistyped role ARN into an immediate, legible failure instead of a confusing plan.
- **`-lock-timeout=5m` on init, plan and apply**, so a run that queues behind another
  waits rather than failing on the lock — the queueing `concurrency` already implies.
- **The role name carries the `-dev` suffix** where the deploy role does not. The deploy
  role's bare name is a consequence of having been adopted by `terraform import` from a
  hand-made object with a ForceNew `name`; this role is created by Terraform, so it takes
  the suffix the module enforces — which also makes it pass guard layer 3, as the plan
  output above shows.

### Out of scope, as instructed

Actions are still pinned by tag (`actions/checkout@v4`, `hashicorp/setup-terraform@v3`,
`aws-actions/configure-aws-credentials@v4`) rather than by commit SHA, including in the
new workflow that now sits in front of an admin-on-dev role. Left alone per the task
description; worth its own task.

### No tests added

Per the project rule, no automated tests were written. No AC asked for any.

### For the owner

1. **The bootstrap apply is still owed** and only you can run it — the workflow cannot
   create the role it assumes. Runbook in `infrastructure/terraform/README.md`
   § "Bootstrap: one local apply". Until it runs, every `terraform-dev.yml` run dies on
   `AssumeRoleWithWebIdentity`, as expected.
2. The plan pasted above is what that apply will contain (plus anything committed
   between now and then). It is clean: 5 creates, 0 destroys, guard green.
3. The very first *automated* run after the bootstrap will find nothing left to do,
   since your local apply will have applied it.
<!-- SECTION:NOTES:END -->
