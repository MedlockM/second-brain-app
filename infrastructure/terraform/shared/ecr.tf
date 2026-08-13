# ECR repository for two independently built Lambda artifacts. API and workers
# share storage, but use distinct tag families and content digests.
#
# ONE repository for ALL environments, on purpose (task-221 §7.1): the image
# validated in dev must be bit-identical to the one released to prod, so
# the tags carry no environment token and promotion happens by digest. The
# environment lives entirely in the Lambda's environment variables and IAM role.
# This is why the repository name is NOT suffixed.
#
# WHERE THE REGISTRY LIVES, and why (task-248 volet 3 decision)
#
# It stays in the dev/management account 125313707865 and is consumed
# cross-account by the prod account. It was NOT moved to prod, because moving it
# means re-pushing every image into a new registry, and a re-push mints new
# digests — which destroys the single property this shared repository exists to
# guarantee. "The digest running in prod is the digest validated in dev" cannot
# survive a registry migration.
#
# The accepted cost of that decision: prod has a hard runtime dependency on a
# resource owned by the dev account. Deleting this repository breaks every prod
# Lambda cold start, so it is now a production asset that happens to be billed to
# the dev account (~$0.0022/day). The clean long-term shape is a third
# "shared-services" account owning the registry, which is over-engineering for a
# single-developer organisation and is a pure lift-and-shift the day it is wanted.

resource "aws_ecr_repository" "lambda" {
  name = "${var.project_name}-lambda"

  # IMMUTABLE so a rebuilt api-<sha> cannot silently change what prod runs,
  # with an exclusion for the two bootstrap *-latest tags that Terraform needs
  # to be able to overwrite when creating a brand new environment.
  image_tag_mutability = "IMMUTABLE_WITH_EXCLUSION"

  image_tag_mutability_exclusion_filter {
    filter      = "*-latest"
    filter_type = "WILDCARD"
  }

  image_scanning_configuration {
    scan_on_push = true
  }

  tags = {
    Name = "${var.project_name}-lambda"
  }
}

# Retention must cover every environment's rollback target at once: with three
# environments, keeping only 3 images per prefix expires a prod rollback
# candidate after two dev pushes. 15 per prefix is ~5 GB, ~$0.53/month.
resource "aws_ecr_lifecycle_policy" "lambda" {
  repository = aws_ecr_repository.lambda.name

  policy = jsonencode({
    rules = [
      {
        rulePriority = 1
        description  = "Expire untagged images after 7 days"
        selection = {
          tagStatus   = "untagged"
          countType   = "sinceImagePushed"
          countUnit   = "days"
          countNumber = 7
        }
        action = {
          type = "expire"
        }
      },
      {
        rulePriority = 2
        description  = "Keep the ${var.image_retention_count} most recent dedicated API images"
        selection = {
          tagStatus     = "tagged"
          tagPrefixList = ["api-"]
          countType     = "imageCountMoreThan"
          countNumber   = var.image_retention_count
        }
        action = {
          type = "expire"
        }
      },
      {
        rulePriority = 3
        description  = "Keep the ${var.image_retention_count} most recent shared worker images"
        selection = {
          tagStatus     = "tagged"
          tagPrefixList = ["worker-"]
          countType     = "imageCountMoreThan"
          countNumber   = var.image_retention_count
        }
        action = {
          type = "expire"
        }
      }
    ]
  })
}

# -----------------------------------------------------------------------------
# Repository policy: who may pull the image.
#
# Until task-248 this policy was NOT managed by Terraform — Lambda wrote it
# itself the first time a function in this account was created from an image, and
# it was therefore locked to
#   "aws:sourceArn": "arn:aws:lambda:eu-west-3:125313707865:function:*"
# i.e. to this account's functions only. Lambda auto-writes that statement only
# when the function and the repository share an account, so a prod Lambda in
# member account 866874944541 would fail its cold start with an image-pull error
# and nothing would have widened the policy for it.
#
# The first statement is a byte-for-byte reproduction of what Lambda wrote,
# including the three SetRepositoryPolicy/DeleteRepositoryPolicy/
# GetRepositoryPolicy actions, so adopting the policy into Terraform does not
# quietly narrow what dev already relies on.
# -----------------------------------------------------------------------------

resource "aws_ecr_repository_policy" "lambda" {
  repository = aws_ecr_repository.lambda.name

  policy = jsonencode({
    Version = "2008-10-17"
    Statement = [
      {
        Sid    = "LambdaECRImageRetrievalPolicy"
        Effect = "Allow"
        Principal = {
          Service = "lambda.amazonaws.com"
        }
        Action = [
          "ecr:BatchGetImage",
          "ecr:GetDownloadUrlForLayer",
          "ecr:SetRepositoryPolicy",
          "ecr:DeleteRepositoryPolicy",
          "ecr:GetRepositoryPolicy"
        ]
        Condition = {
          StringLike = {
            "aws:sourceArn" = "arn:aws:lambda:${var.aws_region}:${data.aws_caller_identity.current.account_id}:function:*"
          }
        }
      },
      {
        # The Lambda service pulling on behalf of a function in another account.
        # Narrower than the statement above on purpose: the prod service
        # principal has no business rewriting this repository's policy.
        Sid    = "LambdaECRImageCrossAccountRetrievalPolicy"
        Effect = "Allow"
        Principal = {
          Service = "lambda.amazonaws.com"
        }
        Action = [
          "ecr:BatchGetImage",
          "ecr:GetDownloadUrlForLayer"
        ]
        Condition = {
          StringLike = {
            "aws:sourceArn" = [
              for account in var.consumer_account_ids :
              "arn:aws:lambda:${var.aws_region}:${account}:function:*"
            ]
          }
        }
      },
      {
        # The IAM principal that CREATES or UPDATES a cross-account function must
        # itself be able to read the image, otherwise CreateFunction fails before
        # the service principal above is ever consulted. That principal is
        # Terraform's role in the prod account, and later the prod GitHub Actions
        # deploy role.
        Sid    = "ConsumerAccountImagePull"
        Effect = "Allow"
        Principal = {
          AWS = [for account in var.consumer_account_ids : "arn:aws:iam::${account}:root"]
        }
        Action = [
          "ecr:BatchGetImage",
          "ecr:GetDownloadUrlForLayer",
          "ecr:BatchCheckLayerAvailability",
          "ecr:DescribeImages",
          "ecr:ListImages",
          "ecr:GetRepositoryPolicy"
        ]
      }
    ]
  })
}
