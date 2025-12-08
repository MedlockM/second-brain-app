# Spotify Sync Lambda and EventBridge Configuration for AWS Production
# This file defines the infrastructure for the Spotify sync feature in production.
#
# Architecture:
# EventBridge (cron) -> Dispatcher Lambda -> SQS -> Worker Lambda -> Processing Pipeline

terraform {
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

# Variables
variable "environment" {
  description = "Environment name (e.g., prod, staging)"
  type        = string
  default     = "prod"
}

variable "aws_region" {
  description = "AWS region"
  type        = string
  default     = "us-east-1"
}

variable "spotify_sync_schedule" {
  description = "Cron expression for Spotify sync schedule"
  type        = string
  default     = "cron(0 4 * * ? *)" # Daily at 4 AM UTC
}

variable "lambda_memory_size" {
  description = "Memory size for Lambda functions"
  type        = number
  default     = 512
}

variable "ecr_repository_url" {
  description = "ECR repository URL for Lambda container images"
  type        = string
}

variable "lambda_image_tag" {
  description = "Docker image tag for Lambda functions"
  type        = string
  default     = "latest"
}

variable "podcastindex_api_key" {
  description = "Podcast Index API Key for searching podcasts"
  type        = string
  sensitive   = false
}

variable "podcastindex_api_secret" {
  description = "Podcast Index API Secret for searching podcasts"
  type        = string
  sensitive   = true
}

# Data sources for existing resources
data "aws_dynamodb_table" "users" {
  name = "users"
}

data "aws_dynamodb_table" "spotify_playlist_follows" {
  name = "spotify_playlist_follows"
}

data "aws_dynamodb_table" "processing_jobs" {
  name = "processing_jobs"
}

data "aws_sqs_queue" "spotify_sync" {
  name = "spotify-sync-queue"
}

data "aws_sqs_queue" "audio_download" {
  name = "audio-download-queue"
}

# -------------------- IAM Role for Lambda --------------------
resource "aws_iam_role" "spotify_sync_lambda_role" {
  name = "spotify-sync-lambda-role-${var.environment}"

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
    Environment = var.environment
    Project     = "media-summarizer"
    Component   = "spotify-sync"
  }
}

resource "aws_iam_role_policy" "spotify_sync_lambda_policy" {
  name = "spotify-sync-lambda-policy"
  role = aws_iam_role.spotify_sync_lambda_role.id

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
          "dynamodb:GetItem",
          "dynamodb:PutItem",
          "dynamodb:UpdateItem",
          "dynamodb:Query",
          "dynamodb:Scan"
        ]
        Resource = [
          data.aws_dynamodb_table.users.arn,
          data.aws_dynamodb_table.spotify_playlist_follows.arn,
          data.aws_dynamodb_table.processing_jobs.arn,
          "${data.aws_dynamodb_table.users.arn}/index/*",
          "${data.aws_dynamodb_table.spotify_playlist_follows.arn}/index/*",
          "${data.aws_dynamodb_table.processing_jobs.arn}/index/*"
        ]
      },
      {
        Effect = "Allow"
        Action = [
          "sqs:SendMessage",
          "sqs:ReceiveMessage",
          "sqs:DeleteMessage",
          "sqs:GetQueueAttributes"
        ]
        Resource = [
          data.aws_sqs_queue.spotify_sync.arn,
          data.aws_sqs_queue.audio_download.arn
        ]
      }
    ]
  })
}

# -------------------- Dispatcher Lambda --------------------
resource "aws_lambda_function" "spotify_sync_dispatcher" {
  function_name = "spotify-sync-dispatcher-${var.environment}"
  role          = aws_iam_role.spotify_sync_lambda_role.arn
  package_type  = "Image"
  image_uri     = "${var.ecr_repository_url}:${var.lambda_image_tag}"
  timeout       = 60
  memory_size   = 256

  image_config {
    command = ["media_summarizer.workers.spotify_sync.dispatcher.lambda_handler"]
  }

  environment {
    variables = {
      ENVIRONMENT              = var.environment
      AWS_REGION              = var.aws_region
      USERS_TABLE             = data.aws_dynamodb_table.users.name
      SPOTIFY_FOLLOWS_TABLE   = data.aws_dynamodb_table.spotify_playlist_follows.name
      SPOTIFY_SYNC_QUEUE_URL  = data.aws_sqs_queue.spotify_sync.url
    }
  }

  tags = {
    Environment = var.environment
    Project     = "media-summarizer"
    Component   = "spotify-sync"
    Function    = "dispatcher"
  }
}

# CloudWatch Log Group for Dispatcher
resource "aws_cloudwatch_log_group" "dispatcher_logs" {
  name              = "/aws/lambda/${aws_lambda_function.spotify_sync_dispatcher.function_name}"
  retention_in_days = 14

  tags = {
    Environment = var.environment
    Project     = "media-summarizer"
  }
}

# -------------------- Worker Lambda --------------------
resource "aws_lambda_function" "spotify_sync_worker" {
  function_name = "spotify-sync-worker-${var.environment}"
  role          = aws_iam_role.spotify_sync_lambda_role.arn
  package_type  = "Image"
  image_uri     = "${var.ecr_repository_url}:${var.lambda_image_tag}"
  timeout       = 300
  memory_size   = var.lambda_memory_size

  image_config {
    command = ["media_summarizer.workers.spotify_sync.worker.lambda_handler"]
  }

  environment {
    variables = {
      ENVIRONMENT                    = var.environment
      AWS_REGION                     = var.aws_region
      USERS_TABLE                    = data.aws_dynamodb_table.users.name
      SPOTIFY_FOLLOWS_TABLE          = data.aws_dynamodb_table.spotify_playlist_follows.name
      SPOTIFY_PLAYLIST_FOLLOWS_TABLE = data.aws_dynamodb_table.spotify_playlist_follows.name
      PROCESSING_JOBS_TABLE          = data.aws_dynamodb_table.processing_jobs.name
      AUDIO_DOWNLOAD_QUEUE           = data.aws_sqs_queue.audio_download.name
      PODCASTINDEXORG_API_KEY        = var.podcastindex_api_key
      PODCASTINDEXORG_API_SECRET     = var.podcastindex_api_secret
    }
  }

  tags = {
    Environment = var.environment
    Project     = "media-summarizer"
    Component   = "spotify-sync"
    Function    = "worker"
  }
}

# CloudWatch Log Group for Worker
resource "aws_cloudwatch_log_group" "worker_logs" {
  name              = "/aws/lambda/${aws_lambda_function.spotify_sync_worker.function_name}"
  retention_in_days = 14

  tags = {
    Environment = var.environment
    Project     = "media-summarizer"
  }
}

# SQS -> Lambda Event Source Mapping
resource "aws_lambda_event_source_mapping" "spotify_sync_sqs" {
  event_source_arn = data.aws_sqs_queue.spotify_sync.arn
  function_name    = aws_lambda_function.spotify_sync_worker.arn
  batch_size       = 1
  enabled          = true
}

# -------------------- EventBridge Schedule --------------------
resource "aws_cloudwatch_event_rule" "spotify_sync_schedule" {
  name                = "spotify-sync-schedule-${var.environment}"
  description         = "Trigger Spotify sync dispatcher on schedule"
  schedule_expression = var.spotify_sync_schedule

  tags = {
    Environment = var.environment
    Project     = "media-summarizer"
    Component   = "spotify-sync"
  }
}

resource "aws_cloudwatch_event_target" "spotify_sync_dispatcher" {
  rule      = aws_cloudwatch_event_rule.spotify_sync_schedule.name
  target_id = "SpotifySyncDispatcherLambda"
  arn       = aws_lambda_function.spotify_sync_dispatcher.arn
}

resource "aws_lambda_permission" "allow_eventbridge_dispatcher" {
  statement_id  = "AllowExecutionFromEventBridge"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.spotify_sync_dispatcher.function_name
  principal     = "events.amazonaws.com"
  source_arn    = aws_cloudwatch_event_rule.spotify_sync_schedule.arn
}

# -------------------- Outputs --------------------
output "dispatcher_lambda_arn" {
  description = "ARN of the Spotify Sync Dispatcher Lambda"
  value       = aws_lambda_function.spotify_sync_dispatcher.arn
}

output "worker_lambda_arn" {
  description = "ARN of the Spotify Sync Worker Lambda"
  value       = aws_lambda_function.spotify_sync_worker.arn
}

output "eventbridge_rule_arn" {
  description = "ARN of the EventBridge schedule rule"
  value       = aws_cloudwatch_event_rule.spotify_sync_schedule.arn
}

output "schedule_expression" {
  description = "The schedule expression for the Spotify sync"
  value       = var.spotify_sync_schedule
}
