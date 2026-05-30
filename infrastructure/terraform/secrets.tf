# Consolidated Secrets Manager entry for all runtime secrets the application
# reads via os.getenv(). One JSON secret per environment (dev, staging, prod).
# ECS task definitions and Lambda functions reference its ARN under their
# `secrets` block — AWS injects each JSON key as an env var at boot time, so
# media_summarizer/core/config.py keeps reading os.getenv("...") unchanged.
#
# Update flow:
#   1. Edit values in AWS Console (Secrets Manager → media-summarizer-runtime-<env>)
#      OR pass secret_payload via terraform.tfvars (then `terraform apply`).
#   2. Restart the consumer (Lambda redeploy or ECS service force-new-deployment)
#      so it picks up the new env values.

variable "secret_payload" {
  description = <<EOT
Map of runtime secrets to push into Secrets Manager. Keys become env var names
when injected into Lambda/ECS containers (e.g. OPENAI_API_KEY, DEEPGRAM_API_KEY,
PODCASTINDEXORG_API_KEY, GOOGLE_CLIENT_ID, APPLE_PRIVATE_KEY, etc.).

Pass via terraform.tfvars or -var-file. Empty by default so plan/apply on a
fresh checkout doesn't fail; populate before any real deploy.
EOT
  type        = map(string)
  default     = {}
  sensitive   = true
}

resource "aws_secretsmanager_secret" "runtime" {
  name        = "${var.project_name}-runtime-${var.environment}"
  description = "Consolidated runtime secrets for ${var.project_name} ${var.environment} (read by Lambdas/ECS)."

  tags = {
    Name        = "${var.project_name}-runtime-${var.environment}"
    Environment = var.environment
    Project     = var.project_name
  }
}

resource "aws_secretsmanager_secret_version" "runtime" {
  secret_id     = aws_secretsmanager_secret.runtime.id
  secret_string = jsonencode(var.secret_payload)

  lifecycle {
    # Allow operators to rotate the value out-of-band via the AWS console
    # without Terraform reverting it on the next apply.
    ignore_changes = [secret_string]
  }
}

# IAM policy granting GetSecretValue on the runtime secret. Attach it to any
# role that needs to read secrets (Lambda execution roles, ECS task execution
# role for `secrets` injection).
resource "aws_iam_policy" "runtime_secret_read" {
  name        = "${var.project_name}-runtime-secret-read-${var.environment}"
  description = "Allows reading the consolidated runtime secret."

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "secretsmanager:GetSecretValue",
          "secretsmanager:DescribeSecret"
        ]
        Resource = aws_secretsmanager_secret.runtime.arn
      }
    ]
  })
}

# Outputs so other modules / Lambda definitions can wire the secret into their
# `environment` or `secrets` blocks without re-declaring it.
output "runtime_secret_arn" {
  description = "ARN of the consolidated runtime secret. Reference under aws_lambda_function.environment via aws_secretsmanager_secret_version.runtime, or under ECS container `secrets` valueFrom."
  value       = aws_secretsmanager_secret.runtime.arn
}

output "runtime_secret_name" {
  description = "Name of the consolidated runtime secret (for AWS CLI lookups)."
  value       = aws_secretsmanager_secret.runtime.name
}
