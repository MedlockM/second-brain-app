# ECR repository for two independently built Lambda artifacts. API and workers
# share storage, but use distinct tag families and content digests.

resource "aws_ecr_repository" "lambda" {
  name                 = "${var.project_name}-lambda"
  image_tag_mutability = "MUTABLE"

  image_scanning_configuration {
    scan_on_push = true
  }

  tags = {
    Name        = "${var.project_name}-lambda"
    Environment = var.environment
    Project     = var.project_name
  }
}

# Keep three independently deployable/rollback-safe versions for each runtime.
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
        description  = "Keep only the 3 most recent dedicated API images"
        selection = {
          tagStatus     = "tagged"
          tagPrefixList = ["api-"]
          countType     = "imageCountMoreThan"
          countNumber   = 3
        }
        action = {
          type = "expire"
        }
      },
      {
        rulePriority = 3
        description  = "Keep only the 3 most recent shared worker images"
        selection = {
          tagStatus     = "tagged"
          tagPrefixList = ["worker-"]
          countType     = "imageCountMoreThan"
          countNumber   = 3
        }
        action = {
          type = "expire"
        }
      }
    ]
  })
}

# Outputs

output "lambda_ecr_repository_url" {
  description = "URL of the ECR repository for Lambda container images"
  value       = aws_ecr_repository.lambda.repository_url
}
