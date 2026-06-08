# IAM Roles and Policies for Lambda functions (workers + API).

# =============================================================================
# Shared Worker Lambda Execution Role
# =============================================================================

resource "aws_iam_role" "lambda_worker" {
  name = "${var.project_name}-lambda-worker"

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
    Name        = "${var.project_name}-lambda-worker"
    Environment = var.environment
    Project     = var.project_name
  }
}

resource "aws_iam_policy" "lambda_worker" {
  name        = "${var.project_name}-lambda-worker-policy"
  description = "Policy for all worker Lambda functions"

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
          "sqs:ReceiveMessage",
          "sqs:DeleteMessage",
          "sqs:GetQueueAttributes",
          "sqs:GetQueueUrl",
          "sqs:ChangeMessageVisibility",
          "sqs:SendMessage"
        ]
        Resource = [
          aws_sqs_queue.rss_resolution.arn,
          aws_sqs_queue.article_extraction.arn,
          aws_sqs_queue.x_ingestion.arn,
          aws_sqs_queue.youtube_ingestion.arn,
          aws_sqs_queue.tiktok_ingestion.arn,
          aws_sqs_queue.deepgram_transcription.arn,
          aws_sqs_queue.summarization.arn,
          aws_sqs_queue.document_parsing.arn,
          aws_sqs_queue.search_indexing.arn,
          aws_sqs_queue.rss_feed_poll.arn,
          aws_sqs_queue.media_completed_events.arn,
          aws_sqs_queue.flashcards.arn,
          aws_sqs_queue.notes.arn,
        ]
      },
      {
        Effect = "Allow"
        Action = [
          "s3:GetObject",
          "s3:PutObject",
          "s3:DeleteObject"
        ]
        Resource = [
          "${aws_s3_bucket.audio.arn}/*",
          "${aws_s3_bucket.transcripts.arn}/*",
          "${aws_s3_bucket.summaries.arn}/*",
          "${aws_s3_bucket.summary_short.arn}/*",
          "${aws_s3_bucket.summary_detailed.arn}/*",
          "${aws_s3_bucket.notes.arn}/*",
          "${aws_s3_bucket.flashcards.arn}/*",
          "${aws_s3_bucket.quiz.arn}/*",
          "${aws_s3_bucket.documents.arn}/*",
          "${aws_s3_bucket.archives.arn}/*"
        ]
      },
      {
        Effect = "Allow"
        Action = [
          "s3:ListBucket"
        ]
        Resource = [
          aws_s3_bucket.audio.arn,
          aws_s3_bucket.transcripts.arn,
          aws_s3_bucket.summaries.arn,
          aws_s3_bucket.summary_short.arn,
          aws_s3_bucket.summary_detailed.arn,
          aws_s3_bucket.notes.arn,
          aws_s3_bucket.flashcards.arn,
          aws_s3_bucket.quiz.arn,
          aws_s3_bucket.documents.arn,
          aws_s3_bucket.archives.arn
        ]
      },
      {
        Effect = "Allow"
        Action = [
          "dynamodb:GetItem",
          "dynamodb:PutItem",
          "dynamodb:UpdateItem",
          "dynamodb:DeleteItem",
          "dynamodb:Query",
          "dynamodb:Scan",
          "dynamodb:BatchGetItem",
          "dynamodb:BatchWriteItem"
        ]
        Resource = "arn:aws:dynamodb:${var.aws_region}:${data.aws_caller_identity.current.account_id}:table/*"
      },
      {
        # ListTables is account-wide (no per-table ARN). Used by /health check.
        Effect   = "Allow"
        Action   = ["dynamodb:ListTables"]
        Resource = "*"
      },
      {
        Effect = "Allow"
        Action = [
          "secretsmanager:GetSecretValue",
          "secretsmanager:DescribeSecret"
        ]
        Resource = aws_secretsmanager_secret.runtime.arn
      },
      {
        Effect = "Allow"
        Action = [
          "cloudwatch:PutMetricData"
        ]
        Resource = "*"
      }
    ]
  })

  tags = {
    Name        = "${var.project_name}-lambda-worker-policy"
    Environment = var.environment
    Project     = var.project_name
  }
}

resource "aws_iam_role_policy_attachment" "lambda_worker" {
  role       = aws_iam_role.lambda_worker.name
  policy_arn = aws_iam_policy.lambda_worker.arn
}

# =============================================================================
# API Lambda Execution Role
# =============================================================================

resource "aws_iam_role" "lambda_api" {
  name = "${var.project_name}-lambda-api"

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
    Name        = "${var.project_name}-lambda-api"
    Environment = var.environment
    Project     = var.project_name
  }
}

resource "aws_iam_policy" "lambda_api" {
  name        = "${var.project_name}-lambda-api-policy"
  description = "Policy for the API Lambda function"

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
          "sqs:SendMessage",
          "sqs:GetQueueUrl"
        ]
        Resource = [
          aws_sqs_queue.rss_resolution.arn,
          aws_sqs_queue.article_extraction.arn,
          aws_sqs_queue.x_ingestion.arn,
          aws_sqs_queue.youtube_ingestion.arn,
          aws_sqs_queue.tiktok_ingestion.arn,
          aws_sqs_queue.deepgram_transcription.arn,
          aws_sqs_queue.summarization.arn,
          aws_sqs_queue.document_parsing.arn,
          aws_sqs_queue.search_indexing.arn,
          aws_sqs_queue.rss_feed_poll.arn,
          aws_sqs_queue.media_completed_events.arn,
          aws_sqs_queue.flashcards.arn,
          aws_sqs_queue.notes.arn,
        ]
      },
      {
        Effect = "Allow"
        Action = [
          "s3:GetObject",
          "s3:PutObject",
          "s3:DeleteObject"
        ]
        Resource = [
          "${aws_s3_bucket.audio.arn}/*",
          "${aws_s3_bucket.transcripts.arn}/*",
          "${aws_s3_bucket.summaries.arn}/*",
          "${aws_s3_bucket.summary_short.arn}/*",
          "${aws_s3_bucket.summary_detailed.arn}/*",
          "${aws_s3_bucket.notes.arn}/*",
          "${aws_s3_bucket.flashcards.arn}/*",
          "${aws_s3_bucket.quiz.arn}/*",
          "${aws_s3_bucket.documents.arn}/*",
          "${aws_s3_bucket.archives.arn}/*"
        ]
      },
      {
        Effect = "Allow"
        Action = [
          "s3:ListBucket"
        ]
        Resource = [
          aws_s3_bucket.audio.arn,
          aws_s3_bucket.transcripts.arn,
          aws_s3_bucket.summaries.arn,
          aws_s3_bucket.summary_short.arn,
          aws_s3_bucket.summary_detailed.arn,
          aws_s3_bucket.notes.arn,
          aws_s3_bucket.flashcards.arn,
          aws_s3_bucket.quiz.arn,
          aws_s3_bucket.documents.arn,
          aws_s3_bucket.archives.arn
        ]
      },
      {
        Effect = "Allow"
        Action = [
          "dynamodb:GetItem",
          "dynamodb:PutItem",
          "dynamodb:UpdateItem",
          "dynamodb:DeleteItem",
          "dynamodb:Query",
          "dynamodb:Scan",
          "dynamodb:BatchGetItem",
          "dynamodb:BatchWriteItem"
        ]
        Resource = "arn:aws:dynamodb:${var.aws_region}:${data.aws_caller_identity.current.account_id}:table/*"
      },
      {
        # ListTables is account-wide (no per-table ARN). Used by /health check.
        Effect   = "Allow"
        Action   = ["dynamodb:ListTables"]
        Resource = "*"
      },
      {
        Effect = "Allow"
        Action = [
          "secretsmanager:GetSecretValue",
          "secretsmanager:DescribeSecret"
        ]
        Resource = aws_secretsmanager_secret.runtime.arn
      },
      {
        Effect = "Allow"
        Action = [
          "cloudwatch:PutMetricData"
        ]
        Resource = "*"
      }
    ]
  })

  tags = {
    Name        = "${var.project_name}-lambda-api-policy"
    Environment = var.environment
    Project     = var.project_name
  }
}

resource "aws_iam_role_policy_attachment" "lambda_api" {
  role       = aws_iam_role.lambda_api.name
  policy_arn = aws_iam_policy.lambda_api.arn
}
