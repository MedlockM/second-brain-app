terraform {
  required_version = ">= 1.3.0"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

variable "localstack_endpoint" {
  description = "Base endpoint for LocalStack services"
  type        = string
  default     = "http://localhost:4566"
}

variable "podcastindex_api_key" {
  description = "Podcast Index API Key"
  type        = string
  default     = ""
}

variable "podcastindex_api_secret" {
  description = "Podcast Index API Secret"
  type        = string
  default     = ""
  sensitive   = true
}

variable "spotify_client_id" {
  description = "Spotify OAuth Client ID"
  type        = string
  default     = ""
}

variable "spotify_client_secret" {
  description = "Spotify OAuth Client Secret"
  type        = string
  default     = ""
  sensitive   = true
}

provider "aws" {
  region                      = "us-east-1"
  access_key                  = "test"
  secret_key                  = "test"
  skip_credentials_validation = true
  skip_requesting_account_id  = true
  skip_metadata_api_check     = true
  s3_use_path_style           = true

  endpoints {
    dynamodb = var.localstack_endpoint
    s3       = var.localstack_endpoint
    sqs      = var.localstack_endpoint
    ses      = var.localstack_endpoint
    lambda   = var.localstack_endpoint
    iam      = var.localstack_endpoint
  }
}

locals {
  project     = "media-summarizer"
  environment = "local"
}

# -------------------- DynamoDB Tables --------------------
resource "aws_dynamodb_table" "subscriptions" {
  name         = "subscriptions"
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
  attribute {
    name = "stripe_subscription_id"
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

  global_secondary_index {
    name            = "stripe-index"
    hash_key        = "stripe_subscription_id"
    projection_type = "ALL"
  }

  tags = { Name = "subscriptions", Environment = local.environment, Project = local.project }
}

resource "aws_dynamodb_table" "minute_buckets" {
  name         = "minute_buckets"
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
    name = "expires_at"
    type = "S"
  }

  global_secondary_index {
    name            = "user-index"
    hash_key        = "user_id"
    projection_type = "ALL"
  }

  global_secondary_index {
    name            = "expiry-index"
    hash_key        = "expires_at"
    projection_type = "ALL"
  }

  tags = { Name = "minute_buckets", Environment = local.environment, Project = local.project }
}

resource "aws_dynamodb_table" "minute_usage" {
  name         = "minute_usage"
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
    name = "job_id"
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
    name            = "job-index"
    hash_key        = "job_id"
    projection_type = "ALL"
  }

  global_secondary_index {
    name            = "status-index"
    hash_key        = "status"
    projection_type = "ALL"
  }

  tags = { Name = "minute_usage", Environment = local.environment, Project = local.project }
}

resource "aws_dynamodb_table" "follows" {
  name         = "follows"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "user_id"
  range_key    = "feed_id"

  attribute {
    name = "user_id"
    type = "S"
  }
  attribute {
    name = "feed_id"
    type = "S"
  }

  tags = { Name = "follows", Environment = local.environment, Project = local.project }
}

resource "aws_dynamodb_table" "spotify_sync_dlq" {
  name         = "spotify-sync-dlq"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "feed_id"

  attribute {
    name = "feed_id"
    type = "S"
  }

  tags = { Name = "spotify-sync-dlq", Environment = local.environment, Project = local.project }
}

# -------------------- SES --------------------
resource "aws_ses_email_identity" "default_sender" {
  email = "noreply@media-summarizer.com"
}

# Episode watchers table
resource "aws_dynamodb_table" "episode_watchers" {
  name         = "episode_watchers"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "episode_guid"
  range_key    = "user_id"

  attribute {
    name = "episode_guid"
    type = "S"
  }
  attribute {
    name = "user_id"
    type = "S"
  }

  tags = { Name = "episode_watchers", Environment = local.environment, Project = local.project }
}

# Spotify playlist follows
resource "aws_dynamodb_table" "spotify_playlist_follows" {
  name         = "spotify_playlist_follows"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "user_id"
  range_key    = "playlist_id"

  attribute {
    name = "user_id"
    type = "S"
  }
  attribute {
    name = "playlist_id"
    type = "S"
  }

  tags = { Name = "spotify_playlist_follows", Environment = local.environment, Project = local.project }
}

# Feed forecasts (shared cache): PK (feed_id, month_key)
resource "aws_dynamodb_table" "feed_forecasts" {
  name         = "feed_forecasts"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "feed_id"
  range_key    = "month_key"

  attribute {
    name = "feed_id"
    type = "S"
  }
  attribute {
    name = "month_key"
    type = "S"
  }

  ttl {
    attribute_name = "ttl"
    enabled        = true
  }

  tags = { Name = "feed_forecasts", Environment = local.environment, Project = local.project }
}

resource "aws_dynamodb_table" "users" {
  name         = "users"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "id"

  attribute {
    name = "id"
    type = "S"
  }
  attribute {
    name = "email"
    type = "S"
  }

  global_secondary_index {
    name            = "email-index"
    hash_key        = "email"
    projection_type = "ALL"
  }

  tags = { Name = "users", Environment = local.environment, Project = local.project }
}

resource "aws_dynamodb_table" "processing_jobs" {
  name         = "processing_jobs"
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
    name = "job_status"
    type = "S"
  }

  global_secondary_index {
    name            = "user-index"
    hash_key        = "user_id"
    projection_type = "ALL"
  }

  global_secondary_index {
    name            = "status-index"
    hash_key        = "job_status"
    projection_type = "ALL"
  }

  tags = { Name = "processing_jobs", Environment = local.environment, Project = local.project }
}

# Episode idempotence: per-user, per-episode GUID reservation table
resource "aws_dynamodb_table" "episode_idempotence" {
  name         = "episode_idempotence"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "episode_guid"

  attribute {
    name = "episode_guid"
    type = "S"
  }

  tags = { Name = "episode_idempotence", Environment = local.environment, Project = local.project }
}

# User episode submissions table: prevent per-user re-submissions
resource "aws_dynamodb_table" "user_episode_submissions" {
  name         = "user_episode_submissions"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "user_id"
  range_key    = "episode_guid"

  attribute {
    name = "user_id"
    type  = "S"
  }
  attribute {
    name = "episode_guid"
    type  = "S"
  }

  tags = { Name = "user_episode_submissions", Environment = local.environment, Project = local.project }
}

resource "aws_dynamodb_table" "credit_transactions" {
  name         = "credit_transactions"
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

  global_secondary_index {
    name            = "user-index"
    hash_key        = "user_id"
    projection_type = "ALL"
  }

  tags = { Name = "credit_transactions", Environment = local.environment, Project = local.project }
}

resource "aws_dynamodb_table" "auth_tokens" {
  name         = "auth_tokens"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "id"

  attribute {
    name = "id"
    type = "S"
  }
  attribute {
    name = "token"
    type = "S"
  }
  attribute {
    name = "user_id"
    type = "S"
  }
  attribute {
    name = "token_type"
    type = "S"
  }

  global_secondary_index {
    name            = "token-index"
    hash_key        = "token"
    projection_type = "ALL"
  }

  global_secondary_index {
    name            = "user-index"
    hash_key        = "user_id"
    projection_type = "ALL"
  }

  global_secondary_index {
    name            = "user-type-index"
    hash_key        = "user_id"
    range_key       = "token_type"
    projection_type = "ALL"
  }

  tags = { Name = "auth_tokens", Environment = local.environment, Project = local.project }
}

resource "aws_dynamodb_table" "stripe_events" {
  name         = "stripe_events"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "id"

  attribute {
    name = "id"
    type = "S"
  }

  tags = { Name = "stripe_events", Environment = local.environment, Project = local.project }
}

# Media artifacts table (canonical artifact records + request pointers)
resource "aws_dynamodb_table" "media_artifacts" {
  name         = "media_artifacts"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "artifact_id"

  attribute {
    name = "artifact_id"
    type = "S"
  }
  attribute {
    name = "media_item_id"
    type = "S"
  }
  attribute {
    name = "request_fingerprint"
    type = "S"
  }
  attribute {
    name = "generation_fingerprint"
    type = "S"
  }

  global_secondary_index {
    name            = "media-item-index"
    hash_key        = "media_item_id"
    projection_type = "ALL"
  }

  global_secondary_index {
    name            = "request-fingerprint-index"
    hash_key        = "request_fingerprint"
    projection_type = "ALL"
  }

  global_secondary_index {
    name            = "generation-fingerprint-index"
    hash_key        = "generation_fingerprint"
    projection_type = "ALL"
  }

  tags = { Name = "media_artifacts", Environment = local.environment, Project = local.project }
}

# Artifact idempotence table (generation locks)
resource "aws_dynamodb_table" "artifact_idempotence" {
  name         = "artifact_idempotence"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "generation_fingerprint"

  attribute {
    name = "generation_fingerprint"
    type = "S"
  }

  tags = { Name = "artifact_idempotence", Environment = local.environment, Project = local.project }
}

# Review schedule table (FSRS spaced repetition)
resource "aws_dynamodb_table" "review_schedule" {
  name         = "review_schedule"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "user_id"
  range_key    = "card_id"

  attribute {
    name = "user_id"
    type = "S"
  }
  attribute {
    name = "card_id"
    type = "S"
  }

  tags = { Name = "review_schedule", Environment = local.environment, Project = local.project }
}

# User review settings table (FSRS preferences)
resource "aws_dynamodb_table" "user_review_settings" {
  name         = "user_review_settings"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "user_id"

  attribute {
    name = "user_id"
    type = "S"
  }

  tags = { Name = "user_review_settings", Environment = local.environment, Project = local.project }
}

# -------------------- S3 Buckets --------------------
resource "aws_s3_bucket" "audio" {
  bucket        = "media-summarizer-audio"
  force_destroy = true
  tags          = { Name = "audio", Environment = local.environment, Project = local.project }
}

resource "aws_s3_bucket" "transcripts" {
  bucket        = "media-summarizer-transcriptions"
  force_destroy = true
  tags          = { Name = "transcripts", Environment = local.environment, Project = local.project }
}

resource "aws_s3_bucket" "summaries" {
  bucket        = "media-summarizer-summaries"
  force_destroy = true
  tags          = { Name = "summaries", Environment = local.environment, Project = local.project }
}

resource "aws_s3_bucket" "flashcards" {
  bucket        = "media-summarizer-flashcards"
  force_destroy = true
  tags          = { Name = "flashcards", Environment = local.environment, Project = local.project }
}

# -------------------- SQS Queues (+ DLQs) --------------------
resource "aws_sqs_queue" "audio_download_dlq" {
  name = "audio-download-dlq"
}

resource "aws_sqs_queue" "audio_download" {
  name = "audio-download-queue"

  redrive_policy = jsonencode({
    deadLetterTargetArn = aws_sqs_queue.audio_download_dlq.arn
    maxReceiveCount     = 3
  })
}

resource "aws_sqs_queue" "transcription_dlq" { name = "transcription-dlq" }
resource "aws_sqs_queue" "transcription" {
  name = "transcription-queue"

  redrive_policy = jsonencode({
    deadLetterTargetArn = aws_sqs_queue.transcription_dlq.arn
    maxReceiveCount     = 3
  })
}

resource "aws_sqs_queue" "podcastindex_resolution_dlq" {
  name = "podcastindex-resolution-dlq"
}

resource "aws_sqs_queue" "podcastindex_resolution" {
  name = "podcastindex-resolution-queue"

  redrive_policy = jsonencode({
    deadLetterTargetArn = aws_sqs_queue.podcastindex_resolution_dlq.arn
    maxReceiveCount     = 3
  })
}

resource "aws_sqs_queue" "deepgram_transcription_dlq" {
  name = "deepgram-transcription-dlq"
}

resource "aws_sqs_queue" "deepgram_transcription" {
  name = "deepgram-transcription-queue"

  redrive_policy = jsonencode({
    deadLetterTargetArn = aws_sqs_queue.deepgram_transcription_dlq.arn
    maxReceiveCount     = 3
  })
}

resource "aws_sqs_queue" "article_extraction_dlq" {
  name = "article-extraction-dlq"
}

resource "aws_sqs_queue" "article_extraction" {
  name = "article-extraction-queue"

  redrive_policy = jsonencode({
    deadLetterTargetArn = aws_sqs_queue.article_extraction_dlq.arn
    maxReceiveCount     = 3
  })
}

resource "aws_sqs_queue" "x_ingestion_dlq" {
  name = "x-ingestion-dlq"
}

resource "aws_sqs_queue" "x_ingestion" {
  name = "x-ingestion-queue"

  redrive_policy = jsonencode({
    deadLetterTargetArn = aws_sqs_queue.x_ingestion_dlq.arn
    maxReceiveCount     = 3
  })
}

resource "aws_sqs_queue" "youtube_ingestion_dlq" {
  name = "youtube-ingestion-dlq"
}

resource "aws_sqs_queue" "youtube_ingestion" {
  name = "youtube-ingestion-queue"

  redrive_policy = jsonencode({
    deadLetterTargetArn = aws_sqs_queue.youtube_ingestion_dlq.arn
    maxReceiveCount     = 3
  })
}

resource "aws_sqs_queue" "tiktok_ingestion_dlq" {
  name = "tiktok-ingestion-dlq"
}

resource "aws_sqs_queue" "tiktok_ingestion" {
  name = "tiktok-ingestion-queue"

  redrive_policy = jsonencode({
    deadLetterTargetArn = aws_sqs_queue.tiktok_ingestion_dlq.arn
    maxReceiveCount     = 3
  })
}

resource "aws_sqs_queue" "summarization_dlq" { name = "summarization-dlq" }
resource "aws_sqs_queue" "summarization" {
  name = "summarization-queue"

  redrive_policy = jsonencode({
    deadLetterTargetArn = aws_sqs_queue.summarization_dlq.arn
    maxReceiveCount     = 3
  })
}

# Flashcards artifact generation queue
resource "aws_sqs_queue" "flashcards_dlq" { name = "flashcards-dlq" }
resource "aws_sqs_queue" "flashcards" {
  name = "flashcards-queue"

  redrive_policy = jsonencode({
    deadLetterTargetArn = aws_sqs_queue.flashcards_dlq.arn
    maxReceiveCount     = 3
  })
}

resource "aws_sqs_queue" "email_notification_dlq" { name = "email-notification-dlq" }
resource "aws_sqs_queue" "email_notification" {
  name = "email-notification-queue"

  redrive_policy = jsonencode({
    deadLetterTargetArn = aws_sqs_queue.email_notification_dlq.arn
    maxReceiveCount     = 3
  })
}

# Episode completed events (fan-out to watchers)
resource "aws_sqs_queue" "episode_completed_dlq" { name = "episode-completed-dlq" }
resource "aws_sqs_queue" "episode_completed" {
  name = "episode-completed-events"

  redrive_policy = jsonencode({
    deadLetterTargetArn = aws_sqs_queue.episode_completed_dlq.arn
    maxReceiveCount     = 3
  })
}

# -------------------- SES Email Identities --------------------
resource "aws_ses_email_identity" "noreply_prod" {
  email = "noreply@media-summarizer.com"
}

resource "aws_ses_email_identity" "noreply_example" {
  email = "noreply@example.com"
}

resource "aws_ses_email_identity" "test_example" {
  email = "test@example.com"
}

# -------------------- Outputs --------------------
output "dynamodb_tables" {
  value = [
    aws_dynamodb_table.users.name,
    aws_dynamodb_table.processing_jobs.name,
    aws_dynamodb_table.credit_transactions.name,
    aws_dynamodb_table.auth_tokens.name,
    aws_dynamodb_table.stripe_events.name,
    aws_dynamodb_table.subscriptions.name,
    aws_dynamodb_table.minute_buckets.name,
    aws_dynamodb_table.minute_usage.name,
    aws_dynamodb_table.follows.name,
    aws_dynamodb_table.spotify_playlist_follows.name,
    aws_dynamodb_table.feed_forecasts.name,
    aws_dynamodb_table.episode_idempotence.name,
    aws_dynamodb_table.episode_watchers.name,
    aws_dynamodb_table.user_episode_submissions.name,
    aws_dynamodb_table.media_artifacts.name,
    aws_dynamodb_table.artifact_idempotence.name,
    aws_dynamodb_table.review_schedule.name,
    aws_dynamodb_table.user_review_settings.name,
  ]
}

output "sqs_queues" {
  value = [
    aws_sqs_queue.audio_download.name,
    aws_sqs_queue.transcription.name,
    aws_sqs_queue.podcastindex_resolution.name,
    aws_sqs_queue.deepgram_transcription.name,
    aws_sqs_queue.article_extraction.name,
    aws_sqs_queue.x_ingestion.name,
    aws_sqs_queue.youtube_ingestion.name,
    aws_sqs_queue.tiktok_ingestion.name,
    aws_sqs_queue.summarization.name,
    aws_sqs_queue.flashcards.name,
    aws_sqs_queue.email_notification.name,
    aws_sqs_queue.episode_completed.name,
    aws_sqs_queue.spotify_sync.name,
  ]
}

# Spotify Sync Queue
resource "aws_sqs_queue" "spotify_sync_dlq" { name = "spotify-sync-dlq" }
resource "aws_sqs_queue" "spotify_sync" {
  name = "spotify-sync-queue"

  redrive_policy = jsonencode({
    deadLetterTargetArn = aws_sqs_queue.spotify_sync_dlq.arn
    maxReceiveCount     = 3
  })
}

# -------------------- IAM Role for Lambda --------------------
resource "aws_iam_role" "lambda_execution_role" {
  name = "lambda-execution-role"

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
}

resource "aws_iam_role_policy" "lambda_policy" {
  name = "lambda-policy"
  role = aws_iam_role.lambda_execution_role.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "logs:CreateLogGroup",
          "logs:CreateLogStream",
          "logs:PutLogEvents",
          "dynamodb:*",
          "s3:*",
          "sqs:*",
          "ses:*"
        ]
        Resource = "*"
      }
    ]
  })
}

# -------------------- Lambda Functions --------------------
# Lambda functions are deployed as optimized zip packages in LocalStack (dev)
# The zip is built by the lambda-builder Docker service before Terraform runs
# Optimization: Unused botocore service models are pruned to reduce size from ~21MB to ~8MB

# Spotify Sync Dispatcher Lambda
# Triggered by EventBridge on schedule, scans playlists and sends jobs to SQS
resource "aws_lambda_function" "spotify_sync_dispatcher" {
  filename         = "${path.module}/spotify_sync_lambda.zip"
  source_code_hash = filebase64sha256("${path.module}/spotify_sync_lambda.zip")
  function_name    = "spotify-sync-dispatcher"
  role             = aws_iam_role.lambda_execution_role.arn
  handler          = "media_summarizer.workers.spotify_sync.dispatcher.lambda_handler"
  runtime          = "python3.11"
  timeout          = 60
  memory_size      = 256

  environment {
    variables = {
      AWS_ENDPOINT_URL           = "http://172.17.0.1:4566"
      AWS_REGION                 = "us-east-1"
      USERS_TABLE                = aws_dynamodb_table.users.name
      SPOTIFY_FOLLOWS_TABLE      = aws_dynamodb_table.spotify_playlist_follows.name
      SPOTIFY_SYNC_QUEUE_URL     = aws_sqs_queue.spotify_sync.url
    }
  }

  depends_on = [aws_iam_role_policy.lambda_policy]
}

# Spotify Sync Worker Lambda
# Triggered by SQS, processes each user's playlists
resource "aws_lambda_function" "spotify_sync_worker" {
  filename         = "${path.module}/spotify_sync_lambda.zip"
  source_code_hash = filebase64sha256("${path.module}/spotify_sync_lambda.zip")
  function_name    = "spotify-sync-worker"
  role             = aws_iam_role.lambda_execution_role.arn
  handler          = "media_summarizer.workers.spotify_sync.worker.lambda_handler"
  runtime          = "python3.11"
  timeout          = 300
  memory_size      = 512

  environment {
    variables = {
      AWS_ENDPOINT_URL               = "http://172.17.0.1:4566"
      AWS_REGION                     = "us-east-1"
      USERS_TABLE                    = aws_dynamodb_table.users.name
      SPOTIFY_FOLLOWS_TABLE          = aws_dynamodb_table.spotify_playlist_follows.name
      SPOTIFY_PLAYLIST_FOLLOWS_TABLE = aws_dynamodb_table.spotify_playlist_follows.name
      PROCESSING_JOBS_TABLE          = aws_dynamodb_table.processing_jobs.name
      AUDIO_DOWNLOAD_QUEUE           = aws_sqs_queue.audio_download.name
      PODCASTINDEXORG_API_KEY        = var.podcastindex_api_key
      PODCASTINDEXORG_API_SECRET     = var.podcastindex_api_secret
      SPOTIFY_CLIENT_ID              = var.spotify_client_id
      SPOTIFY_CLIENT_SECRET          = var.spotify_client_secret
    }
  }

  depends_on = [aws_iam_role_policy.lambda_policy]
}

# SQS -> Lambda Event Source Mapping
# Automatically triggers worker Lambda when messages arrive in spotify-sync-queue
resource "aws_lambda_event_source_mapping" "spotify_sync_sqs" {
  event_source_arn = aws_sqs_queue.spotify_sync.arn
  function_name    = aws_lambda_function.spotify_sync_worker.arn
  batch_size       = 1
  enabled          = true
}

# -------------------- EventBridge Schedule --------------------
# Note: EventBridge resources are created via null_resource + AWS CLI
# because Terraform's EventBridge provider has auth issues with LocalStack

resource "null_resource" "eventbridge_setup" {
  # Re-run if Lambda function changes
  triggers = {
    dispatcher_arn = aws_lambda_function.spotify_sync_dispatcher.arn
  }

  provisioner "local-exec" {
    environment = {
      AWS_ACCESS_KEY_ID     = "test"
      AWS_SECRET_ACCESS_KEY = "test"
      AWS_DEFAULT_REGION    = "us-east-1"
    }
    command = <<-EOT
      # Wait for Lambda to be ready
      sleep 5

      # Create EventBridge rule (rate: 1 minute for dev)
      aws --endpoint-url=http://localstack:4566 events put-rule \
        --name spotify-sync-schedule \
        --schedule-expression "rate(1 minute)" \
        --state ENABLED || true

      # Add Lambda as target
      aws --endpoint-url=http://localstack:4566 events put-targets \
        --rule spotify-sync-schedule \
        --targets "Id=SpotifySyncDispatcherLambda,Arn=${aws_lambda_function.spotify_sync_dispatcher.arn}" || true

      # Grant EventBridge permission to invoke Lambda
      aws --endpoint-url=http://localstack:4566 lambda add-permission \
        --function-name spotify-sync-dispatcher \
        --statement-id AllowEventBridgeInvoke \
        --action lambda:InvokeFunction \
        --principal events.amazonaws.com \
        --source-arn arn:aws:events:us-east-1:000000000000:rule/spotify-sync-schedule 2>/dev/null || true

      echo "EventBridge schedule configured successfully"
    EOT
  }

  depends_on = [aws_lambda_function.spotify_sync_dispatcher]
}

# -------------------- Outputs --------------------

output "s3_buckets" {
  value = [
    aws_s3_bucket.audio.id,
    aws_s3_bucket.transcripts.id,
    aws_s3_bucket.summaries.id,
    aws_s3_bucket.flashcards.id,
  ]
}

output "lambda_functions" {
  description = "Spotify Sync Lambda functions"
  value = [
    aws_lambda_function.spotify_sync_dispatcher.function_name,
    aws_lambda_function.spotify_sync_worker.function_name,
  ]
}

output "eventbridge_schedule" {
  description = "EventBridge schedule for Spotify Sync"
  value       = "rate(1 minute)"
}
