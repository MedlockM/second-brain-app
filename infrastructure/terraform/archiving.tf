# Archiving infrastructure for Media Summarizer

# S3 Bucket for Job Archives
resource "aws_s3_bucket" "archives" {
  bucket = "${var.project_name}-archives-${data.aws_caller_identity.current.account_id}-${var.environment}"
  
  tags = {
    Name        = "${var.project_name}-archives"
    Environment = var.environment
    Project     = var.project_name
  }
}

# Lifecycle policy for archives (Move to Glacier immediately, delete after 1 year)
resource "aws_s3_bucket_lifecycle_configuration" "archives" {
  bucket = aws_s3_bucket.archives.id

  rule {
    id     = "archive-to-glacier"
    status = "Enabled"

    transition {
      days          = 0 # Move immediately upon creation
      storage_class = "GLACIER_IR" # Instant Retrieval (good balance for occasional audit)
    }

    expiration {
      days = 365
    }
  }
}

# IAM Role for Archiver Lambda
resource "aws_iam_role" "lambda_archiver" {
  name = "${var.project_name}-lambda-archiver"

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
    Name        = "${var.project_name}-lambda-archiver"
    Environment = var.environment
    Project     = var.project_name
  }
}

# IAM Policy for Archiver Lambda
resource "aws_iam_policy" "lambda_archiver" {
  name        = "${var.project_name}-lambda-archiver-policy"
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

# Lambda Function for Archiving
resource "aws_lambda_function" "job_archiver" {
  filename         = "job_archiver.zip" # Placeholder, will be built by CI/CD
  function_name    = "${var.project_name}-job-archiver"
  role            = aws_iam_role.lambda_archiver.arn
  handler         = "job_archiver.lambda_handler"
  runtime         = "python3.11"
  timeout         = 60
  memory_size     = 128

  environment {
    variables = {
      ARCHIVE_BUCKET = aws_s3_bucket.archives.id
    }
  }

  tags = {
    Name        = "${var.project_name}-job-archiver"
    Environment = var.environment
    Project     = var.project_name
  }
}

# CloudWatch Log Group for Archiver
resource "aws_cloudwatch_log_group" "lambda_archiver" {
  name              = "/aws/lambda/${var.project_name}-job-archiver"
  retention_in_days = 7
}

# DynamoDB Stream Event Source Mapping
resource "aws_lambda_event_source_mapping" "job_archiver" {
  event_source_arn  = aws_dynamodb_table.processing_jobs_v1.stream_arn
  function_name     = aws_lambda_function.job_archiver.arn
  starting_position = "LATEST"
  batch_size        = 100
  
  # Filter: Only process REMOVE events (TTL deletions)
  filter_criteria {
    filter {
      pattern = jsonencode({
        eventName = ["REMOVE"]
      })
    }
  }
}
