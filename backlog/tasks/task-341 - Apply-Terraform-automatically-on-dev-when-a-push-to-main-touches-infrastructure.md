---
id: task-341
title: Apply Terraform automatically on dev when a push to main touches infrastructure
status: To Do
assignee: []
created_date: '2026-09-03 10:14'
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
- [ ] #1 infrastructure/terraform/envs/dev/ declares an IAM role media-summarizer-gha-terraform-dev, distinct from media-summarizer-gha-deploy, whose assume-role policy references the existing aws_iam_openid_connect_provider.github resource and pins sub with StringLike to repo:${var.github_repository}:ref:${var.github_ref} using the already-declared variables
- [ ] #2 No second aws_iam_openid_connect_provider is created, and media-summarizer-gha-deploy with its inline deploy policy is left byte-identical
- [ ] #3 envs/prod/, envs/staging/, shared/ and modules/platform/ are unmodified by this task
- [ ] #4 A comment on the new role states plainly that it is effectively administrator on the dev account, why no narrower scope is honest given the IAM resources the dev root manages, and names the three real mitigations (account boundary, refs/heads/main pin, prod and shared out of reach)
- [ ] #5 An output exposes the new role ARN, symmetrically with the existing gha_deploy_role_arn output
- [ ] #6 terraform fmt -check -recursive and terraform validate pass on infrastructure/terraform/envs/dev
- [ ] #7 terraform plan on envs/dev proposes no destroy, and scripts/tf_plan_guard.sh dev <planfile> exits 0 on that plan file; the plan summary line and the guard output are pasted into the Implementation Notes
- [ ] #8 .github/workflows/terraform-dev.yml triggers on push to main with paths covering infrastructure/terraform/**, declares id-token write, assumes the new role by OIDC, and runs Terraform against envs/dev only — the file names no other root
- [ ] #9 The workflow calls scripts/tf_plan_guard.sh dev on the saved plan file between plan and apply, without --allow-replace, and the apply step applies that saved plan file rather than using -auto-approve
- [ ] #10 The workflow declares a concurrency group with cancel-in-progress false and pins an exact terraform_version rather than latest
- [ ] #11 The workflow references no GitHub secret: the role ARN is a literal whose source of truth is the Terraform output from AC#5, noted as such in a comment
- [ ] #12 pr.yml runs terraform fmt -check -recursive and, for each of envs/dev, envs/prod, envs/staging, shared and modules/platform, terraform init -backend=false followed by terraform validate
- [ ] #13 infrastructure/terraform/README.md records the 2026-09-02 decision — dev auto-applies on push to main, prod and shared/ stay manual — and the one-time local apply that bootstraps the role
<!-- AC:END -->
