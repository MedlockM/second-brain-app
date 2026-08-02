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

# Lifecycle policy: keep last 10 images, expire untagged after 7 days.
# NOTE: every deploy pushes per-SHA tags (api-<sha>/worker-<sha>) that are never
# untagged, so an "untagged only" rule lets tagged images accumulate forever and
# the TimedStorage-ByteHrs bill grows linearly. The "keep last 10 (any)" rule
# below bounds total storage. A rule with tagStatus = "any" must have the highest
# rulePriority, so it is evaluated last.
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
        description  = "Keep only the 3 most recent images"
        # Each image is ~0.39 GB (base + Python deps), close to the 0.5 GB-month
        # ECR free tier on its own. A deps change creates a fresh ~0.39 GB layer
        # set, so keeping many images can transiently stack several of them and
        # blow past free tier. 3 is enough for rollback while bounding that peak.
        selection = {
          tagStatus   = "any"
          countType   = "imageCountMoreThan"
          countNumber = 3
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
