# ECR repository for two independently built Lambda artifacts. API and workers
# share storage, but use distinct tag families and content digests.
#
# ONE repository for ALL environments, on purpose (task-221 §7.1): the image
# validated in staging must be bit-identical to the one released to prod, so
# the tags carry no environment token and promotion happens by digest. The
# environment lives entirely in the Lambda's environment variables and IAM role.
# This is why the repository name is NOT suffixed.

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
