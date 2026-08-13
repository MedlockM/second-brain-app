# GitHub Actions deploy identity for the PROD account (task-221 §7.2 points 3-4,
# task-248 volet 3).
#
# It lives in this root rather than in a bootstrap script because, unlike the
# state bucket, nothing about it is a chicken-and-egg problem: prod's state
# already exists by the time this is applied, so the role can be reviewed as
# code. dev's equivalent (media-summarizer-gha-deploy in 125313707865) was
# created by hand out-of-band and is still unmanaged; that is a known gap, not a
# pattern to copy.
#
# The isolation claim, in two independent layers:
#
#   1. Account boundary. This role only exists in 866874944541 and every ARN in
#      its policy is an 866874944541 ARN. It is structurally incapable of naming
#      a dev resource. Symmetrically, media-summarizer-gha-deploy in the dev
#      account grants lambda:UpdateFunctionCode on
#      arn:aws:lambda:eu-west-3:125313707865:function:media-summarizer-* — an ARN
#      that cannot match anything in prod.
#   2. OIDC subject. The trust policy pins `sub` to
#      repo:<owner>/<repo>:environment:production, which GitHub only mints for a
#      job that declares `environment: production`. A workflow job without that
#      declaration cannot assume this role even with the ARN in hand, and the
#      GitHub environment carries the owner's required-reviewer gate.

data "aws_caller_identity" "current" {}

locals {
  # Repeated from the module call rather than read out of it: a root-level
  # resource cannot reach a module's variables, and hardcoding "prod" here is the
  # same literal-per-directory discipline the backend key uses.
  project_name = "media-summarizer"
  environment  = "prod"
  aws_region   = "eu-west-3"
}

variable "shared_ecr_repository_arn" {
  description = "ARN of the shared Lambda ECR repository in the dev/management account. Companion of shared_ecr_repository_url; the CI role needs the ARN, the Lambdas need the URL."
  type        = string
  default     = "arn:aws:ecr:eu-west-3:125313707865:repository/media-summarizer-lambda"
}

variable "github_repository" {
  description = "owner/repo whose Actions jobs may assume the prod deploy role."
  type        = string
  default     = "MedlockM/second-brain-app"
}

variable "github_environment" {
  description = "GitHub Environment name pinned in the OIDC subject claim. Must match `environment:` in the deploy job, or the trust policy rejects the token."
  type        = string
  default     = "production"
}

# GitHub's OIDC identity provider. One per account: the dev account already has
# its own at the same URL, and the two are unrelated objects.
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

    # StringEquals, not StringLike: no wildcard means no other repository, no
    # other environment and no pull_request context can produce a matching
    # subject.
    condition {
      test     = "StringEquals"
      variable = "token.actions.githubusercontent.com:sub"
      values   = ["repo:${var.github_repository}:environment:${var.github_environment}"]
    }
  }
}

resource "aws_iam_role" "gha_deploy" {
  name               = "${local.project_name}-gha-deploy-${local.environment}"
  description        = "GitHub Actions deploy role for ${local.environment}. Assumable only by a job declaring the '${var.github_environment}' GitHub environment."
  assume_role_policy = data.aws_iam_policy_document.gha_deploy_assume.json

  tags = {
    Name = "${local.project_name}-gha-deploy-${local.environment}"
  }
}

data "aws_iam_policy_document" "gha_deploy" {
  # Pulling the shared image out of the dev account's registry. The matching
  # grant on the other side is the ConsumerAccountImagePull statement in
  # shared/ecr.tf; both are required, an ECR repository policy alone does not
  # grant anything to a principal whose own account denies it.
  statement {
    sid       = "EcrAuth"
    effect    = "Allow"
    actions   = ["ecr:GetAuthorizationToken"]
    resources = ["*"]
  }

  statement {
    sid    = "EcrPullSharedRepository"
    effect = "Allow"
    actions = [
      "ecr:BatchCheckLayerAvailability",
      "ecr:GetDownloadUrlForLayer",
      "ecr:BatchGetImage",
      "ecr:DescribeImages"
    ]
    resources = [var.shared_ecr_repository_arn]
  }

  # NO push actions on purpose. Images are built once in dev and promoted by
  # digest (task-221 §7.1); a prod job that could push could mint an artifact
  # that never went through dev.

  statement {
    sid       = "LambdaList"
    effect    = "Allow"
    actions   = ["lambda:ListFunctions"]
    resources = ["*"]
  }

  statement {
    sid    = "LambdaDeployProdOnly"
    effect = "Allow"
    actions = [
      "lambda:UpdateFunctionCode",
      "lambda:GetFunction",
      "lambda:GetFunctionConfiguration",
      "lambda:InvokeFunction"
    ]
    resources = ["arn:aws:lambda:${local.aws_region}:${data.aws_caller_identity.current.account_id}:function:${local.project_name}-*-${local.environment}"]
  }

  # Function and API discovery by Environment tag, which is how deploy-lambda.yml
  # avoids name-prefix wildcards.
  statement {
    sid       = "TagDiscovery"
    effect    = "Allow"
    actions   = ["tag:GetResources"]
    resources = ["*"]
  }

  statement {
    sid       = "ApiGatewayRead"
    effect    = "Allow"
    actions   = ["apigateway:GET"]
    resources = ["arn:aws:apigateway:${local.aws_region}::/apis/*"]
  }
}

resource "aws_iam_role_policy" "gha_deploy" {
  # An inline policy name is already scoped to its role, so the "-prod" token
  # buys no uniqueness here — it is carried anyway because tf_plan_guard.sh
  # layer 3 asserts it on EVERY created name, and an exception list is a worse
  # trade than a slightly redundant name.
  name   = "deploy-${local.environment}"
  role   = aws_iam_role.gha_deploy.id
  policy = data.aws_iam_policy_document.gha_deploy.json
}

output "gha_deploy_role_arn" {
  description = "Value to store as the AWS_DEPLOY_ROLE_ARN secret of the GitHub 'production' environment."
  value       = aws_iam_role.gha_deploy.arn
}
