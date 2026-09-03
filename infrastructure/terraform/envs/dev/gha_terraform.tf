# GitHub Actions *Terraform* identity for the DEV account (task-341).
#
# Separate from `media-summarizer-gha-deploy` in gha_oidc.tf, and deliberately so.
# That role ships container images: ECR push/pull on one repository, `lambda:Update*`
# scoped to `media-summarizer-*-dev`, tag discovery, `apigateway:GET`. It holds no
# grant on the state bucket, none on the lock table and none on IAM, so it cannot
# even run `terraform init`. Widening it was the wrong fix: its narrowness is what
# stops a push to main overwriting a staging Lambda and what stops a prod job minting
# an unpromoted image (see the header of gha_oidc.tf, task-256). Two identities with
# two blast radii beat one identity with the union of both.
#
# THIS ROLE IS ADMINISTRATOR ON THE DEV ACCOUNT. Say it plainly rather than dress it
# up. The dev root manages 23 DynamoDB tables, 26 SQS queues, 21 metric alarms, 25 log
# metric filters, 4 Lambda functions, 6 IAM roles, 7 IAM policies, 9 policy
# attachments, the OIDC provider above and a Secrets Manager secret. Applying that
# needs `iam:CreateRole`, `iam:PutRolePolicy`, `iam:AttachRolePolicy` and
# `iam:PassRole` — i.e. the power to mint a principal with any permission in the
# account and then pass it to a Lambda. A hand-written 400-line policy enumerating
# dynamodb:*, sqs:*, lambda:*, logs:*, cloudwatch:*, s3:*, secretsmanager:*, sns:*,
# apigateway:* and iam:* on this account would be exactly as privileged, only longer
# and quietly wrong the first time a new resource type is added. `AdministratorAccess`
# is the honest spelling of what a Terraform apply role is.
#
# The mitigations that are real, and they are structural rather than textual:
#
#   1. THE ACCOUNT BOUNDARY. Since task-248 dev and prod are two separate AWS
#      accounts (125313707865 and 866874944541). Admin here can name no prod
#      resource at all, cannot read prod's state bucket — which lives in prod's own
#      account — and cannot take prod's lock. This is the only isolation AWS
#      enforces, and it is doing the heavy lifting.
#   2. THE REF PIN. The trust policy below accepts one OIDC subject:
#      repo:<owner>/<repo>:ref:refs/heads/main. A pull_request context, another
#      branch, another repository or a fork all mint a different `sub` and are all
#      rejected. Only a job running on main can assume this role, so the review gate
#      on what reaches main is the gate on what this role can do.
#   3. PROD AND THE SHARED ECR REGISTRY ARE OUT OF THE WORKFLOW'S REACH BY
#      CONSTRUCTION. .github/workflows/terraform-dev.yml runs Terraform in exactly
#      one directory, this one. Production stays a manual apply from the owner's
#      machine (decision of 2026-09-02), and the registry prod pulls its images from
#      stays manual for the same reason: an automated apply there would cross the
#      account boundary the isolation work exists to hold.
#
# What is NOT a mitigation, and should not be mistaken for one: `scripts/tf_plan_guard.sh`
# in the workflow. It gates the *plan Terraform proposes*, not what the credentials
# can do. A job on main that ran `aws iam create-user` instead of `terraform plan`
# would never reach the guard. The guard's job is to catch a destructive diff, and
# that is worth having; it is not a permission boundary.

data "aws_iam_policy_document" "gha_terraform_assume" {
  statement {
    effect  = "Allow"
    actions = ["sts:AssumeRoleWithWebIdentity"]

    principals {
      type = "Federated"
      # The provider declared in gha_oidc.tf. There is exactly ONE OIDC provider per
      # AWS account: declaring a second `aws_iam_openid_connect_provider` at
      # https://token.actions.githubusercontent.com fails with EntityAlreadyExists.
      identifiers = [aws_iam_openid_connect_provider.github.arn]
    }

    condition {
      test     = "StringEquals"
      variable = "token.actions.githubusercontent.com:aud"
      values   = ["sts.amazonaws.com"]
    }

    # Same shape as the deploy role: StringLike over a value that holds no wildcard,
    # so it is exactly as tight as StringEquals. var.github_repository and
    # var.github_ref are declared in gha_oidc.tf and default to
    # MedlockM/second-brain-app and refs/heads/main.
    condition {
      test     = "StringLike"
      variable = "token.actions.githubusercontent.com:sub"
      values   = ["repo:${var.github_repository}:ref:${var.github_ref}"]
    }
  }
}

resource "aws_iam_role" "gha_terraform" {
  # Suffixed `-dev`, unlike the deploy role — which carries no suffix only because
  # `name` is ForceNew and it was adopted by import from a hand-made object. This one
  # is created by Terraform, so it takes the suffix the whole module enforces, and
  # tf_plan_guard.sh layer 3 (every created name ends in `-<env>`) accepts it.
  name               = "${local.gha_project_name}-gha-terraform-${local.gha_environment}"
  description        = "GitHub Actions Terraform apply role for ${local.gha_environment}. Administrator on this account by necessity; assumable only by a job running on ${var.github_ref} of ${var.github_repository}."
  assume_role_policy = data.aws_iam_policy_document.gha_terraform_assume.json

  tags = {
    Name = "${local.gha_project_name}-gha-terraform-${local.gha_environment}"
  }
}

resource "aws_iam_role_policy_attachment" "gha_terraform_admin" {
  role = aws_iam_role.gha_terraform.name
  # See the header. This is not laziness: any policy that can apply this root can
  # grant itself the rest, so an enumerated policy would claim a boundary it does not
  # have. The boundary is the account, and the gate is the ref pin.
  policy_arn = "arn:aws:iam::aws:policy/AdministratorAccess"
}

output "gha_terraform_role_arn" {
  description = "Value hardcoded as TERRAFORM_ROLE_ARN in .github/workflows/terraform-dev.yml. Not a secret (an ARN authenticates nobody), and not a GitHub secret on purpose: this output is its source of truth and `terraform output gha_terraform_role_arn` is how you check the two agree."
  value       = aws_iam_role.gha_terraform.arn
}
