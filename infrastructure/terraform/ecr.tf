# ECR Repository for Lambda container images.
# All worker and API Lambda functions share a single repository with per-function
# image tags (e.g. :api-latest, :worker-latest, :api-<sha>, :worker-<sha>).

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

# Lifecycle policy: keep last 10 images, expire untagged after 7 days
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
      }
    ]
  })
}

# Outputs

output "lambda_ecr_repository_url" {
  description = "URL of the ECR repository for Lambda container images"
  value       = aws_ecr_repository.lambda.repository_url
}
