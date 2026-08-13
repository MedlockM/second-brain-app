# GitHub Actions deploy identity for the DEV/management account (task-256).
#
# WHY THIS FILE EXISTS, and what its absence cost
#
# The role and the OIDC provider below were created by hand on 2026-06-12 and
# lived outside every Terraform state until task-256. The consequence was not
# theoretical: when task-248 gave the prod role a `tag:GetResources` grant —
# because deploy-lambda.yml discovers its targets by `Environment` tag rather
# than by name prefix — there was no dev code to change, so dev never got it.
# Every `deploy-workers` run from 2026-08-10 onwards died on
# `AccessDeniedException ... not authorized to perform: tag:GetResources`, while
# `deploy-api` kept going green because it names its single function directly and
# needs no discovery call at all. A half-green pipeline that deploys the API and
# silently deploys zero workers is the exact failure mode an unmanaged role
# produces: the divergence was only visible in a red run, never in a diff.
#
# ADOPTED, NOT RECREATED. The three resources here were brought in with
# `terraform import` (see the runbook comment at the bottom of this file), so the
# first plan after this file landed was in-place updates only. Recreating them
# instead would have deleted the trust relationship every deploy depends on and
# invalidated the ARN stored in the AWS_DEPLOY_ROLE_ARN GitHub secret.
#
# WHERE DEV DIVERGES FROM PROD, deliberately. envs/prod/gha_oidc.tf is the
# reference shape; the differences below are real and each one is load-bearing:
#
#   1. Physical names carry no "-dev" token (`media-summarizer-gha-deploy`, inline
#      policy `deploy`). Both are ForceNew attributes, so aligning them with
#      prod's `-prod`-suffixed names would mean destroying and recreating the very
#      resources this task exists to preserve. The names are the ones AWS has had
#      since 2026-06-12 and they stay.
#   2. The trust policy pins `sub` to repo:<owner>/<repo>:ref:refs/heads/main with
#      StringLike, not to an `environment:` subject with StringEquals. dev is
#      deployed automatically by a push to main, by jobs that declare no GitHub
#      environment — that is the whole point of the split, and it is what makes
#      the prod role unassumable from those same jobs. Moving dev behind a GitHub
#      environment would be a workflow change, not an IAM one.
#   3. dev may PUSH to the shared ECR repository; prod may only pull. Images are
#      built once here and promoted to prod by digest (task-221 §7.1), so a prod
#      job that could push would be able to mint an artifact that never went
#      through dev.
#
# Isolation, for the record: every ARN in the policy below is a 125313707865 ARN,
# so this role is structurally incapable of naming a prod resource — the account
# boundary from task-248 does that half of the job on its own. Within the account
# the Lambda grant is suffixed `-dev`, which matters because envs/staging/main.tf
# is a live blueprint that lands in THIS account: a bare `media-summarizer-*` (what
# the hand-made policy carried) would have let a push to main overwrite a staging
# function's code the day someone applies that root.

data "aws_caller_identity" "current" {}

locals {
  # Repeated from the module call rather than read out of it: a root-level
  # resource cannot reach a module's variables, and hardcoding "dev" here is the
  # same literal-per-directory discipline the backend key uses.
  gha_project_name = "media-summarizer"
  gha_environment  = "dev"
  gha_aws_region   = "eu-west-3"

  # The registry lives in THIS account (shared/ecr.tf), so the caller identity is
  # the right account id — unlike prod, which has to hardcode 125313707865. The
  # name comes from the shared state so the two roots cannot drift apart; only the
  # ARN shape is assembled here, because shared/ exposes the URL and the name but
  # no ARN output.
  shared_ecr_repository_arn = "arn:aws:ecr:${local.gha_aws_region}:${data.aws_caller_identity.current.account_id}:repository/${data.terraform_remote_state.shared.outputs.lambda_ecr_repository_name}"
}

variable "github_repository" {
  description = "owner/repo whose Actions jobs may assume the dev deploy role."
  type        = string
  default     = "MedlockM/second-brain-app"
}

variable "github_ref" {
  description = "Git ref pinned in the OIDC subject claim. Only a job running on this ref can assume the dev deploy role."
  type        = string
  default     = "refs/heads/main"
}

# GitHub's OIDC identity provider. One per account: the prod account has its own
# at the same URL (envs/prod/gha_oidc.tf) and the two are unrelated objects.
resource "aws_iam_openid_connect_provider" "github" {
  url = "https://token.actions.githubusercontent.com"

  client_id_list = ["sts.amazonaws.com"]

  # GitHub rotates its signing keys and AWS has validated the provider against
  # the host's certificate chain since 2023, but the argument is still required.
  thumbprint_list = ["6938fd4d98bab03faadb97b34396831e3780aea1"]

  tags = {
    Name = "github-actions-oidc"
  }
}

data "aws_iam_policy_document" "gha_deploy_assume" {
  statement {
    effect  = "Allow"
    actions = ["sts:AssumeRoleWithWebIdentity"]

    principals {
      type        = "Federated"
      identifiers = [aws_iam_openid_connect_provider.github.arn]
    }

    condition {
      test     = "StringEquals"
      variable = "token.actions.githubusercontent.com:aud"
      values   = ["sts.amazonaws.com"]
    }

    # StringLike is what the hand-made role has carried since 2026-06-12 and it is
    # reproduced verbatim so adopting the role changes no live trust decision. The
    # value holds no wildcard, so it is exactly as tight as StringEquals would be:
    # a pull_request context, another branch or another repository all produce a
    # different subject and are all rejected.
    condition {
      test     = "StringLike"
      variable = "token.actions.githubusercontent.com:sub"
      values   = ["repo:${var.github_repository}:ref:${var.github_ref}"]
    }
  }
}

resource "aws_iam_role" "gha_deploy" {
  # No "-dev" suffix, and it must stay that way: `name` is ForceNew, the ARN is
  # stored in the AWS_DEPLOY_ROLE_ARN GitHub secret, and renaming would break
  # every deploy for the duration of the change. See divergence 1 in the header.
  name               = "${local.gha_project_name}-gha-deploy"
  description        = "GitHub Actions deploy role for ${local.gha_environment} (deploy-lambda.yml). Assumable only by a job running on ${var.github_ref} of ${var.github_repository}."
  assume_role_policy = data.aws_iam_policy_document.gha_deploy_assume.json

  tags = {
    Name = "${local.gha_project_name}-gha-deploy"
  }
}

data "aws_iam_policy_document" "gha_deploy" {
  statement {
    sid       = "EcrAuth"
    effect    = "Allow"
    actions   = ["ecr:GetAuthorizationToken"]
    resources = ["*"]
  }

  # dev is where images are BUILT, so unlike prod this role pushes. The shared
  # repository is IMMUTABLE except for the two *-latest bootstrap tags, so a push
  # cannot rewrite an existing api-<sha> or worker-<sha> digest.
  statement {
    sid    = "EcrPushPull"
    effect = "Allow"
    actions = [
      "ecr:BatchCheckLayerAvailability",
      "ecr:GetDownloadUrlForLayer",
      "ecr:BatchGetImage",
      "ecr:InitiateLayerUpload",
      "ecr:UploadLayerPart",
      "ecr:CompleteLayerUpload",
      "ecr:PutImage"
    ]
    resources = [local.shared_ecr_repository_arn]
  }

  statement {
    sid       = "LambdaList"
    effect    = "Allow"
    actions   = ["lambda:ListFunctions"]
    resources = ["*"]
  }

  statement {
    sid    = "LambdaDeploy"
    effect = "Allow"
    actions = [
      "lambda:UpdateFunctionCode",
      "lambda:GetFunction",
      "lambda:GetFunctionConfiguration",
      "lambda:InvokeFunction"
    ]
    resources = ["arn:aws:lambda:${local.gha_aws_region}:${data.aws_caller_identity.current.account_id}:function:${local.gha_project_name}-*-${local.gha_environment}"]
  }

  # Function and API discovery by Environment tag, which is how deploy-lambda.yml
  # avoids name-prefix wildcards. MISSING FROM THE HAND-MADE POLICY — this is the
  # grant whose absence broke deploy-workers (see the header).
  #
  # `tag:GetResources` takes no resource ARN: it is a service-level action of the
  # Resource Groups Tagging API, so "*" is the only valid scope, in dev exactly as
  # in prod. The narrowing that matters happens at the call site, which filters on
  # Key=Environment,Values=dev and then refuses any function whose name does not
  # end in -dev.
  statement {
    sid       = "TagDiscovery"
    effect    = "Allow"
    actions   = ["tag:GetResources"]
    resources = ["*"]
  }

  # `aws apigatewayv2 get-api` in the release-validation job, which resolves the
  # health-check URL from the API id that tag discovery returned. Also missing from
  # the hand-made policy; it had not failed yet only because the job that needs it
  # runs after deploy-workers, which died first.
  statement {
    sid       = "ApiGatewayRead"
    effect    = "Allow"
    actions   = ["apigateway:GET"]
    resources = ["arn:aws:apigateway:${local.gha_aws_region}::/apis/*"]
  }
}

resource "aws_iam_role_policy" "gha_deploy" {
  # "deploy", not "deploy-dev": ForceNew, same reason as the role name. An inline
  # policy name is already scoped to its role, so the token would buy no
  # uniqueness anyway. tf_plan_guard.sh layer 3 only inspects CREATED names, so an
  # imported policy updated in place never reaches that assertion.
  name   = "deploy"
  role   = aws_iam_role.gha_deploy.id
  policy = data.aws_iam_policy_document.gha_deploy.json
}

output "gha_deploy_role_arn" {
  description = "Value stored as the repository-level AWS_DEPLOY_ROLE_ARN secret used by the push-to-main deploy jobs."
  value       = aws_iam_role.gha_deploy.arn
}

# ADOPTION RUNBOOK (already executed by task-256 against env/dev/terraform.tfstate;
# kept because the next environment adopted this way will need it, and because a
# reader has to be able to tell an import from a create):
#
#   terraform -chdir=infrastructure/terraform/envs/dev import \
#     aws_iam_openid_connect_provider.github \
#     arn:aws:iam::125313707865:oidc-provider/token.actions.githubusercontent.com
#   terraform -chdir=infrastructure/terraform/envs/dev import \
#     aws_iam_role.gha_deploy media-summarizer-gha-deploy
#   terraform -chdir=infrastructure/terraform/envs/dev import \
#     aws_iam_role_policy.gha_deploy media-summarizer-gha-deploy:deploy
#
# A plan run before the imports proposes three creates and fails on
# EntityAlreadyExists at apply; after them it proposes in-place updates only.
