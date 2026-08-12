# Bug Reports infrastructure (task-128)
#
# Resources:
# - DynamoDB table for bug report persistence
# - S3 bucket for attachment storage with 90-day lifecycle
# - IAM policy for presigned URL generation

# DynamoDB table for bug reports
resource "aws_dynamodb_table" "bug_reports" {
  name         = "bug_reports${local.suffix}"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "id"

  attribute {
    name = "id"
    type = "S"
  }
  attribute {
    name = "user_id"
    type = "S"
  }
  attribute {
    name = "status"
    type = "S"
  }

  global_secondary_index {
    name            = "user-index"
    hash_key        = "user_id"
    projection_type = "ALL"
  }

  global_secondary_index {
    name            = "status-index"
    hash_key        = "status"
    projection_type = "ALL"
  }

  tags = {
    Name = "bug_reports${local.suffix}"
  }

  point_in_time_recovery {
    enabled = true
  }

  deletion_protection_enabled = true

  lifecycle {
    prevent_destroy = true
  }
}

# S3 Bucket for Bug Report Attachments
resource "aws_s3_bucket" "bug_reports" {
  bucket = "${var.project_name}-bug-reports-${data.aws_caller_identity.current.account_id}-${var.environment}"

  tags = {
    Name = "${var.project_name}-bug-reports${local.suffix}"
  }

  lifecycle {
    prevent_destroy = true
  }
}

# Block public access (attachments are internal only)
resource "aws_s3_bucket_public_access_block" "bug_reports" {
  bucket = aws_s3_bucket.bug_reports.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

# Lifecycle: delete attachments 90 days after creation (RGPD retention policy)
resource "aws_s3_bucket_lifecycle_configuration" "bug_reports" {
  bucket = aws_s3_bucket.bug_reports.id

  rule {
    id     = "expire-attachments-90-days"
    status = "Enabled"

    # Empty filter matches all objects in the bucket. Required by the provider:
    # exactly one of filter / prefix must be set.
    filter {}

    expiration {
      days = 90
    }
  }
}

# Server-side encryption
resource "aws_s3_bucket_server_side_encryption_configuration" "bug_reports" {
  bucket = aws_s3_bucket.bug_reports.id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

# IAM Policy for API to generate presigned URLs and head objects
resource "aws_iam_policy" "bug_reports_s3" {
  name        = "${var.project_name}-bug-reports-s3${local.suffix}"
  description = "Allows the API to generate presigned PUT URLs and validate uploaded bug report attachments."

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "s3:PutObject",
          "s3:GetObject",
          "s3:HeadObject"
        ]
        Resource = "${aws_s3_bucket.bug_reports.arn}/*"
      }
    ]
  })
}

# Attach to Lambda API + worker execution roles (ECS removed in task-106).
# Both need access: API writes user-submitted bug reports; workers may write
# error contexts for failed jobs.
resource "aws_iam_role_policy_attachment" "lambda_api_bug_reports_s3" {
  role       = aws_iam_role.lambda_api.name
  policy_arn = aws_iam_policy.bug_reports_s3.arn
}

resource "aws_iam_role_policy_attachment" "lambda_worker_bug_reports_s3" {
  role       = aws_iam_role.lambda_worker.name
  policy_arn = aws_iam_policy.bug_reports_s3.arn
}

# Outputs
output "bug_reports_table_name" {
  description = "Name of the bug_reports DynamoDB table."
  value       = aws_dynamodb_table.bug_reports.name
}

output "bug_reports_bucket_name" {
  description = "Name of the bug reports attachment S3 bucket."
  value       = aws_s3_bucket.bug_reports.id
}
