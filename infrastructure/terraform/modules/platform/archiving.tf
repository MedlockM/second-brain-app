# Archiving infrastructure for Media Summarizer

# S3 Bucket for Job Archives
resource "aws_s3_bucket" "archives" {
  bucket = "${var.project_name}-archives-${data.aws_caller_identity.current.account_id}-${var.environment}"

  tags = {
    Name = "${var.project_name}-archives${local.suffix}"
  }

  lifecycle {
    prevent_destroy = true
  }
}

# Lifecycle policy for archives (Move to Glacier immediately, delete after 1 year)
resource "aws_s3_bucket_lifecycle_configuration" "archives" {
  bucket = aws_s3_bucket.archives.id

  rule {
    id     = "archive-to-glacier"
    status = "Enabled"

    # Empty filter matches all objects in the bucket
    filter {}

    transition {
      days          = 0            # Move immediately upon creation
      storage_class = "GLACIER_IR" # Instant Retrieval (good balance for occasional audit)
    }

    expiration {
      days = 365
    }
  }
}

# IAM Role for Archiver Lambda
resource "aws_iam_role" "lambda_archiver" {
  name = "${var.project_name}-lambda-archiver${local.suffix}"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "lambda.amazonaws.com"
        }
      }
    ]
  })

  tags = {
    Name = "${var.project_name}-lambda-archiver${local.suffix}"
  }
}

# IAM Policy for Archiver Lambda
resource "aws_iam_policy" "lambda_archiver" {
  name        = "${var.project_name}-lambda-archiver-policy${local.suffix}"
  description = "Policy for Job Archiver Lambda"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "logs:CreateLogGroup",
          "logs:CreateLogStream",
          "logs:PutLogEvents"
        ]
        Resource = "arn:aws:logs:*:*:*"
      },
      {
        Effect = "Allow"
        Action = [
          "dynamodb:GetRecords",
          "dynamodb:GetShardIterator",
          "dynamodb:DescribeStream",
          "dynamodb:ListStreams"
        ]
        Resource = aws_dynamodb_table.processing_jobs_v1.stream_arn
      },
      {
        Effect = "Allow"
        Action = [
          "s3:PutObject"
        ]
        Resource = "${aws_s3_bucket.archives.arn}/*"
      }
    ]
  })
}

resource "aws_iam_role_policy_attachment" "lambda_archiver" {
  role       = aws_iam_role.lambda_archiver.name
  policy_arn = aws_iam_policy.lambda_archiver.arn
}

# Placeholder deployment package, generated at plan time.
#
# This used to be `filename = "job_archiver.zip"`: an untracked 477-byte zip
# that happened to sit in the old flat root directory. Any operator on a fresh
# clone — and any environment other than dev — could not even plan. The
# placeholder is generated here instead, so every environment can be created
# from a clean checkout. task-242 owns the real implementation; until then the
# TTL that feeds this Lambda's stream filter is frozen off (task-239), so the
# handler is never invoked.
data "archive_file" "job_archiver" {
  type        = "zip"
  output_path = "${path.module}/.build/job_archiver${local.suffix}.zip"

  source {
    filename = "job_archiver.py"
    content  = <<-PY
      """Placeholder job archiver. Implemented by task-242."""


      def lambda_handler(event, context):
          records = event.get("Records", [])
          print(f"job-archiver placeholder: {len(records)} record(s) ignored")
          return {"archived": 0, "ignored": len(records)}
    PY
  }
}

# Lambda Function for Archiving
resource "aws_lambda_function" "job_archiver" {
  filename         = data.archive_file.job_archiver.output_path
  source_code_hash = data.archive_file.job_archiver.output_base64sha256
  function_name    = "${var.project_name}-job-archiver${local.suffix}"
  role             = aws_iam_role.lambda_archiver.arn
  handler          = "job_archiver.lambda_handler"
  runtime          = "python3.11"
  timeout          = 60
  memory_size      = 128

  environment {
    variables = {
      ARCHIVE_BUCKET = aws_s3_bucket.archives.id
    }
  }

  tags = {
    Name = "${var.project_name}-job-archiver${local.suffix}"
  }
}

# CloudWatch Log Group for Archiver
resource "aws_cloudwatch_log_group" "lambda_archiver" {
  name              = "/aws/lambda/${var.project_name}-job-archiver${local.suffix}"
  retention_in_days = 7
}

# DynamoDB Stream Event Source Mapping
resource "aws_lambda_event_source_mapping" "job_archiver" {
  event_source_arn  = aws_dynamodb_table.processing_jobs_v1.stream_arn
  function_name     = aws_lambda_function.job_archiver.arn
  starting_position = "LATEST"
  batch_size        = 100

  # Filter: Only process REMOVE events (TTL deletions)
  #
  # Not every REMOVE is a retention expiry: the account purge (task-224) deletes a
  # user's job rows explicitly, and archiving those would copy the data of an
  # account being erased into the archive bucket. The purge stamps
  # `purge_reason = "account_deletion"` on each row before deleting it, so the
  # OLD_IMAGE carries the signal. The real archiver (task-242, placeholder above)
  # must skip those records; the filter stays as-is because a stream filter cannot
  # match on the absence of an attribute.
  filter_criteria {
    filter {
      pattern = jsonencode({
        eventName = ["REMOVE"]
      })
    }
  }
}
