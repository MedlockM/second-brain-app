# IAM Roles and Policies for Lambda functions (workers + API).

# =============================================================================
# Shared Worker Lambda Execution Role
# =============================================================================

resource "aws_iam_role" "lambda_worker" {
  name = "${var.project_name}-lambda-worker${local.suffix}"

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
    Name = "${var.project_name}-lambda-worker${local.suffix}"
  }
}

resource "aws_iam_policy" "lambda_worker" {
  name        = "${var.project_name}-lambda-worker-policy${local.suffix}"
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
          aws_sqs_queue.artifact_generator.arn,
          aws_sqs_queue.document_parsing.arn,
          aws_sqs_queue.search_indexing.arn,
          aws_sqs_queue.rss_feed_poll.arn,
          aws_sqs_queue.media_completed_events.arn,
          aws_sqs_queue.instagram_ingestion.arn,
          aws_sqs_queue.transcript_translation.arn,
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
          "${aws_s3_bucket.review_blurb.arn}/*",
          "${aws_s3_bucket.documents.arn}/*",
          "${aws_s3_bucket.archives.arn}/*",
          "${aws_s3_bucket.covers.arn}/*"
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
          aws_s3_bucket.review_blurb.arn,
          aws_s3_bucket.documents.arn,
          aws_s3_bucket.archives.arn,
          aws_s3_bucket.covers.arn
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
        # Scoped to THIS environment's tables only (task-237). The previous
        # "table/*" grant let a dev Lambda read and write every table in the
        # account, which with three environments means a dev bug can corrupt
        # prod data. local.table_arns covers the tables and their indexes.
        Resource = local.table_arns
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
    Name = "${var.project_name}-lambda-worker-policy${local.suffix}"
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
  name = "${var.project_name}-lambda-api${local.suffix}"

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
    Name = "${var.project_name}-lambda-api${local.suffix}"
  }
}

resource "aws_iam_policy" "lambda_api" {
  name        = "${var.project_name}-lambda-api-policy${local.suffix}"
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
          aws_sqs_queue.artifact_generator.arn,
          aws_sqs_queue.document_parsing.arn,
          aws_sqs_queue.search_indexing.arn,
          aws_sqs_queue.rss_feed_poll.arn,
          aws_sqs_queue.media_completed_events.arn,
          aws_sqs_queue.instagram_ingestion.arn,
          aws_sqs_queue.transcript_translation.arn,
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
          "${aws_s3_bucket.review_blurb.arn}/*",
          "${aws_s3_bucket.documents.arn}/*",
          "${aws_s3_bucket.archives.arn}/*",
          "${aws_s3_bucket.covers.arn}/*"
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
          aws_s3_bucket.review_blurb.arn,
          aws_s3_bucket.documents.arn,
          aws_s3_bucket.archives.arn,
          aws_s3_bucket.covers.arn
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
        # Scoped to THIS environment's tables only (task-237). The previous
        # "table/*" grant let a dev Lambda read and write every table in the
        # account, which with three environments means a dev bug can corrupt
        # prod data. local.table_arns covers the tables and their indexes.
        Resource = local.table_arns
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
    Name = "${var.project_name}-lambda-api-policy${local.suffix}"
  }
}

resource "aws_iam_role_policy_attachment" "lambda_api" {
  role       = aws_iam_role.lambda_api.name
  policy_arn = aws_iam_policy.lambda_api.arn
}
